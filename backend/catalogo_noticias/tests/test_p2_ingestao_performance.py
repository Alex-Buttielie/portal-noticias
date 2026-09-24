"""Testes P2-2: HTTP condicional, bulk_create e snapshot de configuração."""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import MagicMock, patch

import pytest
import requests
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.db import connection, transaction
from django.test import override_settings
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from catalogo_noticias.models import (
    ConfiguracaoRobo,
    FonteRobo,
    NewsItem,
    RegistroExecucaoIngestao,
)
from catalogo_noticias.providers.news_source import ItemBruto, RSSNewsSourceProvider
from catalogo_noticias.providers.summarization import ResultadoResumo, SummarizationProvider
from catalogo_noticias.robos_serializers import FonteRoboSerializer
from catalogo_noticias.services.config_robo import cache_por_execucao, categorias_sensiveis, cfg_valor
from catalogo_noticias.services.ingestao import (
    _persistir_grupo,
    _persistir_grupo_mesclado,
    executar_ingestao,
)

pytestmark = pytest.mark.django_db


def _rss_bytes(titulo="Notícia condicional", link="https://p2.test/item-1"):
    return (
        "<?xml version=\"1.0\"?><rss version=\"2.0\"><channel><title>Feed</title>"
        f"<item><title>{titulo}</title><link>{link}</link>"
        "<description>Texto original do feed.</description></item>"
        "</channel></rss>"
    ).encode("utf-8")


class _FonteFake:
    nome_fonte = "Fonte Fake"

    def __init__(self, item):
        self.item = item

    def buscar_itens(self):
        return [self.item]


class _FonteComDuplicatas(_FonteFake):
    def buscar_itens(self):
        return [self.item, self.item]


class _ResumoFake(SummarizationProvider):
    def resumir_e_classificar(self, itens_brutos):
        item = itens_brutos[0]
        return ResultadoResumo(
            resumo=f"Síntese original do item {item.titulo}.",
            categoria="cidades",
        )


def test_rss_envia_validators_e_persiste_resposta_200():
    fonte = FonteRobo.objects.create(
        nome="Fonte condicional P2",
        url="https://p2.test/rss",
        ativo=True,
    )
    resposta = MagicMock(
        status_code=200,
        content=_rss_bytes(),
        headers={"ETag": '"versao-1"', "Last-Modified": "Wed, 23 Sep 2026 12:00:00 GMT"},
    )
    resposta.raise_for_status.return_value = None
    provider = RSSNewsSourceProvider(
        nome_fonte=fonte.nome,
        url_feed=fonte.url,
        fonte_robo=fonte,
    )

    with patch("catalogo_noticias.providers.news_source.requests.get", return_value=resposta) as get:
        itens = provider.buscar_itens()

    assert len(itens) == 1
    headers = get.call_args.kwargs["headers"]
    assert "If-None-Match" not in headers
    assert "If-Modified-Since" not in headers
    # A gravação é explícita para simular a confirmação pós-persistência.
    provider.confirmar_validadores()
    fonte.refresh_from_db()
    assert fonte.etag == '"versao-1"'
    assert fonte.last_modified == "Wed, 23 Sep 2026 12:00:00 GMT"


def test_pipeline_confirma_validators_somente_apos_persistir_itens():
    fonte = FonteRobo.objects.create(
        nome="Fonte pipeline P2",
        url="https://p2.test/pipeline-rss",
        ativo=True,
    )
    resposta_200 = MagicMock(
        status_code=200,
        content=_rss_bytes(
            titulo="Item do pipeline condicional",
            link="https://p2.test/pipeline-item",
        ),
        headers={"ETag": '"pipeline-1"', "Last-Modified": "Wed, 23 Sep 2026 14:00:00 GMT"},
    )
    resposta_200.raise_for_status.return_value = None
    provider = RSSNewsSourceProvider(
        nome_fonte=fonte.nome,
        url_feed=fonte.url,
        fonte_robo=fonte,
    )
    with patch(
        "catalogo_noticias.providers.news_source.requests.get",
        return_value=resposta_200,
    ):
        executar_ingestao(
            fontes=[provider],
            summarization_provider=_ResumoFake(),
        )

    fonte.refresh_from_db()
    assert fonte.etag == '"pipeline-1"'
    assert NewsItem.objects.filter(url_fonte_original="https://p2.test/pipeline-item").exists()

    resposta_304 = MagicMock(status_code=304, content=b"", headers={})
    with patch(
        "catalogo_noticias.providers.news_source.requests.get",
        return_value=resposta_304,
    ) as get:
        executar_ingestao(
            fontes=[provider],
            summarization_provider=_ResumoFake(),
        )
    assert get.call_args.kwargs["headers"]["If-None-Match"] == '"pipeline-1"'
    assert NewsItem.objects.filter(url_fonte_original="https://p2.test/pipeline-item").count() == 1


def test_validator_nao_avanca_se_a_persistencia_do_lote_falhar():
    fonte = FonteRobo.objects.create(
        nome="Fonte worker perdido P2",
        url="https://p2.test/worker-perdido",
        ativo=True,
    )
    resposta = MagicMock(
        status_code=200,
        content=_rss_bytes(
            titulo="Item antes da queda",
            link="https://p2.test/worker-item",
        ),
        headers={"ETag": '"nao-confirmar"', "Last-Modified": "Wed, 23 Sep 2026 15:00:00 GMT"},
    )
    resposta.raise_for_status.return_value = None
    provider = RSSNewsSourceProvider(
        nome_fonte=fonte.nome,
        url_feed=fonte.url,
        fonte_robo=fonte,
    )
    with patch(
        "catalogo_noticias.providers.news_source.requests.get",
        return_value=resposta,
    ):
        with patch(
            "catalogo_noticias.services.ingestao._persistir_grupo",
            side_effect=RuntimeError("worker caiu"),
        ):
            with pytest.raises(RuntimeError, match="worker caiu"):
                executar_ingestao(
                    fontes=[provider],
                    summarization_provider=_ResumoFake(),
                )

    fonte.refresh_from_db()
    assert fonte.etag == ""
    assert fonte.last_modified == ""


def test_troca_de_url_invalida_validators_http():
    fonte = FonteRobo.objects.create(
        nome="Fonte trocada P2",
        url="https://p2.test/feed-antigo",
        ativo=True,
        etag='"antigo"',
        last_modified="Wed, 23 Sep 2026 10:00:00 GMT",
    )
    serializer = FonteRoboSerializer(
        fonte,
        data={"url": "https://p2.test/feed-novo"},
        partial=True,
    )
    assert serializer.is_valid(), serializer.errors
    serializer.save()
    fonte.refresh_from_db()
    assert fonte.etag == ""
    assert fonte.last_modified == ""
    assert fonte.ultima_revalidacao_completa is None


def test_rss_304_nao_faz_parse_e_reenvia_validators():
    fonte = FonteRobo.objects.create(
        nome="Fonte 304 P2",
        url="https://p2.test/rss-304",
        ativo=True,
        etag='"versao-2"',
        last_modified="Wed, 23 Sep 2026 13:00:00 GMT",
        ultima_revalidacao_completa=timezone.now(),
    )
    resposta = MagicMock(status_code=304, content=b"", headers={})
    provider = RSSNewsSourceProvider(
        nome_fonte=fonte.nome,
        url_feed=fonte.url,
        etag=fonte.etag,
        last_modified=fonte.last_modified,
        fonte_robo=fonte,
    )

    with patch("catalogo_noticias.providers.news_source.requests.get", return_value=resposta) as get:
        with patch("catalogo_noticias.providers.news_source.feedparser.parse") as parse:
            assert provider.buscar_itens() == []

    parse.assert_not_called()
    headers = get.call_args.kwargs["headers"]
    assert headers["If-None-Match"] == '"versao-2"'
    assert headers["If-Modified-Since"] == "Wed, 23 Sep 2026 13:00:00 GMT"
    fonte.refresh_from_db()
    assert fonte.etag == '"versao-2"'
    assert fonte.last_modified == "Wed, 23 Sep 2026 13:00:00 GMT"
    assert provider.not_modified is True


def test_cfg_valor_consulta_configuracao_uma_vez_por_execucao():
    ConfiguracaoRobo.objects.create(
        pk=1,
        dedup_max_itens=321,
        resumo_similaridade_maxima=0.61,
        categorias_sensiveis="cidades,politica",
    )

    with CaptureQueriesContext(connection) as ctx:
        with cache_por_execucao():
            assert cfg_valor("CATALOGO_NOTICIAS_DEDUP_MAX_ITENS_RECENTES", "dedup_max_itens", int) == 321
            assert cfg_valor("CATALOGO_NOTICIAS_RESUMO_SIMILARIDADE_MAXIMA", "resumo_similaridade_maxima", float) == 0.61
            assert categorias_sensiveis() == ["cidades", "politica"]

    assert len(ctx.captured_queries) == 1

    ConfiguracaoRobo.objects.filter(pk=1).update(dedup_max_itens=999)
    with cache_por_execucao():
        assert cfg_valor("CATALOGO_NOTICIAS_DEDUP_MAX_ITENS_RECENTES", "dedup_max_itens", int) == 999


def test_persistencia_em_lote_faz_um_insert_de_newsitem():
    resultados = [
        (
            ItemBruto(
                titulo=f"Fato em lote {indice}",
                url_fonte_original=f"https://p2.test/lote/{indice}",
                nome_fonte="Fonte Lote",
                conteudo_bruto=f"Texto bruto original número {indice}.",
            ),
            ResultadoResumo(
                resumo=f"Síntese autoral distinta número {indice}.",
                categoria="cidades",
            ),
        )
        for indice in range(6)
    ]

    with CaptureQueriesContext(connection) as ctx:
        cluster, criados = _persistir_grupo(resultados)

    assert cluster is not None
    assert len(criados) == 6
    assert all(item.pk is not None for item in criados)
    inserts_newsitem = [
        query["sql"]
        for query in ctx.captured_queries
        if "insert into" in query["sql"].lower() and "newsitem" in query["sql"].lower()
    ]
    assert len(inserts_newsitem) == 1
    assert NewsItem.objects.filter(cluster=cluster).count() == 6


def test_caminho_de_mesclagem_tambem_persiste_o_lote_em_uma_operacao():
    existente = NewsItem.objects.create(
        titulo="Fato que ganhou cobertura",
        url_fonte_original="https://p2.test/mesclagem-antigo",
        nome_fonte="Fonte Antiga",
        conteudo_bruto="Texto antigo.",
        status_revisao=NewsItem.STATUS_NAO_APLICAVEL,
    )
    novo = (
        ItemBruto(
            titulo="Fato que ganhou cobertura",
            url_fonte_original="https://p2.test/mesclagem-novo",
            nome_fonte="Fonte Nova",
            conteudo_bruto="Texto novo, suficientemente diferente.",
        ),
        ResultadoResumo(
            resumo="Síntese original da cobertura nova.",
            categoria="cidades",
        ),
    )

    with CaptureQueriesContext(connection) as ctx:
        cluster, criados = _persistir_grupo_mesclado([novo], [existente])

    assert cluster is not None
    assert len(criados) == 1
    assert NewsItem.objects.filter(cluster=cluster).count() == 2
    inserts_newsitem = [
        query["sql"]
        for query in ctx.captured_queries
        if "insert into" in query["sql"].lower() and "newsitem" in query["sql"].lower()
    ]
    assert len(inserts_newsitem) == 1


def test_bulk_create_preserva_validacao_de_url_e_fonte():
    with pytest.raises(ValidationError):
        _persistir_grupo(
            [
                (
                    ItemBruto(
                        titulo="Item inválido",
                        url_fonte_original="",
                        nome_fonte="Fonte",
                    ),
                    ResultadoResumo(resumo="Resumo", categoria="cidades"),
                )
            ]
        )
    assert NewsItem.objects.count() == 0


def test_ingestao_reentrega_nao_duplica_url():
    item = ItemBruto(
        titulo="Fato idempotente",
        url_fonte_original="https://p2.test/idempotente",
        nome_fonte="Fonte Fake",
        conteudo_bruto="Texto bruto suficientemente diferente.",
    )
    fonte = _FonteFake(item)
    provider = _ResumoFake()

    with CaptureQueriesContext(connection) as primeira:
        executar_ingestao(fontes=[fonte], summarization_provider=provider)
    with CaptureQueriesContext(connection) as segunda:
        executar_ingestao(fontes=[fonte], summarization_provider=provider)

    assert NewsItem.objects.filter(url_fonte_original=item.url_fonte_original).count() == 1
    config_queries_primeira = [
        query for query in primeira.captured_queries if "configuracaorobo" in query["sql"].lower()
    ]
    config_queries_segunda = [
        query for query in segunda.captured_queries if "configuracaorobo" in query["sql"].lower()
    ]


def test_revalidacao_periodica_forca_fetch_sem_validator_e_recupera_item():
    fonte = FonteRobo.objects.create(
        nome="Fonte TTL P2",
        url="https://p2.test/ttl-rss",
        ativo=True,
        etag='"antigo"',
        last_modified="Wed, 23 Sep 2026 10:00:00 GMT",
        ultima_revalidacao_completa=timezone.now() - timedelta(hours=7),
    )
    resposta = MagicMock(
        status_code=200,
        content=_rss_bytes(
            titulo="Item recuperado após 304 antigo",
            link="https://p2.test/ttl-item",
        ),
        headers={"ETag": '"novo"', "Last-Modified": "Thu, 24 Sep 2026 10:00:00 GMT"},
    )
    resposta.raise_for_status.return_value = None
    provider = RSSNewsSourceProvider(
        nome_fonte=fonte.nome,
        url_feed=fonte.url,
        etag=fonte.etag,
        last_modified=fonte.last_modified,
        fonte_robo=fonte,
    )

    with patch(
        "catalogo_noticias.providers.news_source.requests.get",
        return_value=resposta,
    ) as get:
        executar_ingestao(
            fontes=[provider],
            summarization_provider=_ResumoFake(),
        )

    headers = get.call_args.kwargs["headers"]
    assert "If-None-Match" not in headers
    assert "If-Modified-Since" not in headers
    assert NewsItem.objects.filter(url_fonte_original="https://p2.test/ttl-item").exists()
    fonte.refresh_from_db()
    assert fonte.etag == '"novo"'
    assert fonte.ultima_revalidacao_completa is not None


def test_304_falso_nao_prende_o_feed_para_sempre():
    fonte = FonteRobo.objects.create(
        nome="Fonte 304 falso P2",
        url="https://p2.test/304-falso",
        ativo=True,
        etag='"mesmo-etag"',
        last_modified="Wed, 23 Sep 2026 10:00:00 GMT",
        ultima_revalidacao_completa=timezone.now() - timedelta(hours=7),
    )
    resposta_304 = MagicMock(status_code=304, content=b"", headers={})
    provider = RSSNewsSourceProvider(
        nome_fonte=fonte.nome,
        url_feed=fonte.url,
        etag=fonte.etag,
        last_modified=fonte.last_modified,
        fonte_robo=fonte,
    )
    with patch(
        "catalogo_noticias.providers.news_source.requests.get",
        return_value=resposta_304,
    ) as get:
        executar_ingestao(
            fontes=[provider],
            summarization_provider=_ResumoFake(),
        )
    assert "If-None-Match" not in get.call_args.kwargs["headers"]
    assert NewsItem.objects.filter(url_fonte_original="https://p2.test/304-falso-item").count() == 0

    # Simula o próximo vencimento do TTL: a mesma resposta 304 não deve
    # deixar o validator travado para sempre quando o XML foi alterado.
    FonteRobo.objects.filter(pk=fonte.pk).update(
        ultima_revalidacao_completa=timezone.now() - timedelta(hours=7)
    )
    fonte.refresh_from_db()
    resposta_200 = MagicMock(
        status_code=200,
        content=_rss_bytes(link="https://p2.test/304-falso-item"),
        headers={"ETag": '"corrigido"'},
    )
    resposta_200.raise_for_status.return_value = None
    provider = RSSNewsSourceProvider(
        nome_fonte=fonte.nome,
        url_feed=fonte.url,
        etag=fonte.etag,
        last_modified=fonte.last_modified,
        fonte_robo=fonte,
    )
    with patch(
        "catalogo_noticias.providers.news_source.requests.get",
        return_value=resposta_200,
    ) as get:
        executar_ingestao(
            fontes=[provider],
            summarization_provider=_ResumoFake(),
        )
    assert "If-None-Match" not in get.call_args.kwargs["headers"]
    assert NewsItem.objects.filter(url_fonte_original="https://p2.test/304-falso-item").exists()


def test_erro_de_fetch_invalida_validator_antigo_para_proxima_tentativa():
    fonte = FonteRobo.objects.create(
        nome="Fonte erro TTL P2",
        url="https://p2.test/erro-rss",
        ativo=True,
        etag='"velho"',
        last_modified="Wed, 23 Sep 2026 10:00:00 GMT",
        ultima_revalidacao_completa=timezone.now(),
    )
    provider = RSSNewsSourceProvider(
        nome_fonte=fonte.nome,
        url_feed=fonte.url,
        etag=fonte.etag,
        last_modified=fonte.last_modified,
        fonte_robo=fonte,
    )
    with patch(
        "catalogo_noticias.providers.news_source.requests.get",
        side_effect=requests.RequestException("rede caiu"),
    ):
        executar_ingestao(
            fontes=[provider],
            summarization_provider=_ResumoFake(),
        )

    fonte.refresh_from_db()
    assert fonte.etag == ""
    assert fonte.last_modified == ""
    assert fonte.ultima_revalidacao_completa is None


def test_confirmacao_de_validator_nao_sobrescreve_url_alterada():
    fonte = FonteRobo.objects.create(
        nome="Fonte corrida URL P2",
        url="https://p2.test/feed-antes-da-corrida",
        ativo=True,
        etag='"antes"',
        last_modified="Wed, 23 Sep 2026 10:00:00 GMT",
        ultima_revalidacao_completa=timezone.now(),
    )
    resposta = MagicMock(
        status_code=200,
        content=_rss_bytes(link="https://p2.test/corrida-url"),
        headers={"ETag": '"depois"', "Last-Modified": "Thu, 24 Sep 2026 10:00:00 GMT"},
    )
    resposta.raise_for_status.return_value = None
    provider = RSSNewsSourceProvider(
        nome_fonte=fonte.nome,
        url_feed=fonte.url,
        etag=fonte.etag,
        last_modified=fonte.last_modified,
        fonte_robo=fonte,
    )
    with patch("catalogo_noticias.providers.news_source.requests.get", return_value=resposta):
        provider.buscar_itens()

    # Simula outra alteração concorrente que não passou pelo save() do model.
    FonteRobo.objects.filter(pk=fonte.pk).update(
        url="https://p2.test/feed-depois-da-corrida",
        etag="",
        last_modified="",
        ultima_revalidacao_completa=None,
    )
    provider.confirmar_validadores()

    fonte.refresh_from_db()
    assert fonte.url == "https://p2.test/feed-depois-da-corrida"
    assert fonte.etag == ""
    assert fonte.last_modified == ""
    assert fonte.ultima_revalidacao_completa is None


def test_duplicate_url_no_lote_e_entre_fontes_nao_quebra_ingestao():
    item = ItemBruto(
        titulo="URL repetida",
        url_fonte_original="https://p2.test/duplicada-no-lote",
        nome_fonte="Fonte Duplicada",
        conteudo_bruto="Texto bruto.",
    )
    executar_ingestao(
        fontes=[_FonteComDuplicatas(item)],
        summarization_provider=_ResumoFake(),
    )
    executar_ingestao(
        fontes=[_FonteFake(item)],
        summarization_provider=_ResumoFake(),
    )

    assert NewsItem.objects.filter(url_fonte_original=item.url_fonte_original).count() == 1


def test_segundo_lote_com_url_concorrente_nao_levanta_integrity_error():
    resultado = (
        ItemBruto(
            titulo="Corrida de URL",
            url_fonte_original="https://p2.test/concorrente-direta",
            nome_fonte="Fonte Concorrente",
            conteudo_bruto="Texto bruto.",
        ),
        ResultadoResumo(resumo="Resumo", categoria="cidades"),
    )
    _persistir_grupo([resultado])
    # Este segundo lote ignora o SELECT de idempotência e exerce diretamente
    # o caminho de retry do helper contra a unique do banco.
    _persistir_grupo([resultado])
    assert NewsItem.objects.filter(
        url_fonte_original=resultado[0].url_fonte_original
    ).count() == 1


class _ResumoComReserva(_ResumoFake):
    def estimar_custo_em_lote(self, quantidade_itens):
        return 0.25

    def resumir_e_classificar(self, itens_brutos):
        registro = RegistroExecucaoIngestao.objects.order_by("-id").first()
        assert registro is not None
        assert registro.custo_estimado_summarization_usd == pytest.approx(0.25)
        return super().resumir_e_classificar(itens_brutos)


class _ResumoQueCaiDepoisDaReserva(_ResumoComReserva):
    def resumir_e_classificar(self, itens_brutos):
        super().resumir_e_classificar(itens_brutos)
        raise RuntimeError("worker caiu depois da resposta do LLM")


def test_custo_llm_e_reservado_antes_da_chamada_e_sobrevive_a_queda():
    item = ItemBruto(
        titulo="Custo reservado",
        url_fonte_original="https://p2.test/custo-reservado",
        nome_fonte="Fonte Custo",
        conteudo_bruto="Texto bruto.",
    )
    with pytest.raises(RuntimeError, match="worker caiu"):
        executar_ingestao(
            fontes=[_FonteFake(item)],
            summarization_provider=_ResumoQueCaiDepoisDaReserva(),
        )

    registro = RegistroExecucaoIngestao.objects.order_by("-id").first()
    assert registro is not None
    assert registro.custo_estimado_summarization_usd == pytest.approx(0.25)
    assert registro.chamadas_summarization_provider == 1


@pytest.mark.django_db(transaction=True)
def test_ingestao_invalida_cache_de_autocomplete():
    cache_locmem = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "p2-ingestao-autocomplete",
        }
    }
    with override_settings(CACHES=cache_locmem):
        cache.clear()
        cache.set("feed:autocomplete:v2:titulos", ["snapshot-antigo"], 300)
        _persistir_grupo(
            [
                (
                    ItemBruto(
                        titulo="Título novo para autocomplete",
                        url_fonte_original="https://p2.test/cache-invalidation",
                        nome_fonte="Fonte Cache",
                    ),
                    ResultadoResumo(resumo="Resumo", categoria="cidades"),
                )
            ]
        )
        assert cache.get("feed:autocomplete:v2:titulos") is None
        cache.clear()


@pytest.mark.django_db(transaction=True)
def test_rollback_da_ingestao_nao_invalida_cache_de_autocomplete():
    cache_locmem = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "p2-ingestao-autocomplete-rollback",
        }
    }
    chaves = [
        "feed:autocomplete:v2:categorias",
        "feed:autocomplete:v2:titulos",
        "feed:autocomplete:v2:populares",
    ]
    with override_settings(CACHES=cache_locmem):
        cache.clear()
        for chave in chaves:
            cache.set(chave, ["snapshot-antigo"], 300)

        from feed.busca import invalidar_cache_autocomplete

        with patch(
            "feed.busca.invalidar_cache_autocomplete",
            wraps=invalidar_cache_autocomplete,
        ) as invalidar:
            with pytest.raises(RuntimeError, match="rollback de ingestao"):
                with transaction.atomic():
                    _persistir_grupo(
                        [
                            (
                                ItemBruto(
                                    titulo="Titulo que deve sofrer rollback",
                                    url_fonte_original="https://p2.test/cache-rollback",
                                    nome_fonte="Fonte Rollback",
                                ),
                                ResultadoResumo(resumo="Resumo", categoria="cidades"),
                            )
                        ]
                    )
                    invalidar.assert_not_called()
                    assert all(cache.get(chave) == ["snapshot-antigo"] for chave in chaves)
                    raise RuntimeError("rollback de ingestao")

            invalidar.assert_not_called()

        assert all(cache.get(chave) == ["snapshot-antigo"] for chave in chaves)
        assert not NewsItem.objects.filter(
            url_fonte_original="https://p2.test/cache-rollback"
        ).exists()
        cache.clear()
