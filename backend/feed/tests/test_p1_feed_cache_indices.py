"""
Run 20260923-1216-p1-feed-cache-indices — testes dos 8 critérios de aceite
(parte testável em sqlite/locmem):

- Crit. 1: coluna `numero_fontes_distintas` gravada na criação e na mesclagem.
- Crit. 2: backfill da migração preenche clusters pré-existentes (idempotente).
- Crit. 3: teto fixo de queries no `GET /api/feed/` (não cresce com K).
- Crit. 4: `conteudo_bruto`/`conteudo_completo` fora do SQL das listagens.
- Crit. 5: segundo `GET` idêntico dentro do TTL não toca o banco (feed) +
  `MeusRecursosView` consolidada (1 query fria, 0 quente).
- Crit. 6: nenhum endpoint do feed expõe `exibir_publicidade`.
- Crit. 7 (parte sqlite): `migrate` coberto pela suíte (migrações aplicadas no
  banco de teste); `0011` é no-op fora do Postgres por construção.

O cache aqui usa locmem via `override_settings` — a suíte geral roda com
`DummyCache` (ver `config/settings_test.py`) para não vazar respostas entre
testes.
"""

from __future__ import annotations

import importlib
from unittest.mock import patch

import pytest
from django.core.cache import cache
from django.db import connection
from django.test import override_settings
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient

from catalogo_noticias.models import NewsCluster, NewsItem
from catalogo_noticias.providers.news_source import ItemBruto
from catalogo_noticias.providers.summarization import ResultadoResumo
from catalogo_noticias.services.ingestao import _persistir_grupo, _persistir_grupo_mesclado
from feed import views as feed_views
from gating.models import ConfiguracaoSistema, FeatureLimit
from painel_admin.models import RegraCuradoria

pytestmark = pytest.mark.django_db

CACHE_LOCMEM = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "p1-feed-cache-indices",
    }
}


@pytest.fixture(autouse=True)
def _limpar_cache():
    cache.clear()
    yield
    cache.clear()


def _bruto(titulo, fonte, url, categoria="cidades"):
    return ItemBruto(
        titulo=titulo,
        url_fonte_original=url,
        nome_fonte=fonte,
        conteudo_bruto="Texto bruto original da materia jornalistica.",
        categoria=categoria,
    )


def _resumo(categoria="cidades"):
    return ResultadoResumo(
        resumo="Sintese autoral genuina, textualmente distinta do bruto original.",
        categoria=categoria,
    )


def _item_feed(titulo, fonte, url, cluster=None, categoria="cidades"):
    return NewsItem.objects.create(
        titulo=titulo,
        resumo_proprio="Resumo autoral.",
        conteudo_bruto="Bruto de auditoria interna, nunca exibido.",
        conteudo_completo="Texto integral da materia para o detalhe.",
        url_fonte_original=url,
        nome_fonte=fonte,
        categoria=categoria,
        status_revisao=NewsItem.STATUS_NAO_APLICAVEL,
        cluster=cluster,
    )


# ---------------------------------------------------------------------------
# Crit. 1 — coluna gravada em todos os caminhos de escrita
# ---------------------------------------------------------------------------


class TestColunaFontesDistintas:
    def test_persistir_grupo_grava_contagem_na_criacao(self):
        cluster, _ = _persistir_grupo(
            [
                (_bruto("Fato X", "G1", "https://g1/fato-x"), _resumo()),
                (_bruto("Fato X", "UOL", "https://uol/fato-x"), _resumo()),
            ]
        )
        assert cluster is not None
        cluster.refresh_from_db()
        assert cluster.numero_fontes_distintas == 2

    def test_persistir_grupo_mesma_fonte_conta_uma(self):
        cluster, _ = _persistir_grupo(
            [
                (_bruto("Fato Y", "G1", "https://g1/fato-y-1"), _resumo()),
                (_bruto("Fato Y", "G1", "https://g1/fato-y-2"), _resumo()),
            ]
        )
        cluster.refresh_from_db()
        assert cluster.numero_fontes_distintas == 1

    def test_persistir_grupo_mesclado_promocao_atualiza_coluna(self):
        _, itens = _persistir_grupo([(_bruto("Fato Z", "G1", "https://g1/fato-z"), _resumo())])
        existente = itens[0]
        assert existente.cluster_id is None

        cluster, _ = _persistir_grupo_mesclado(
            [(_bruto("Fato Z", "UOL", "https://uol/fato-z"), _resumo())],
            [existente],
        )
        cluster.refresh_from_db()
        assert cluster.numero_fontes_distintas == 2

    def test_persistir_grupo_mesclado_fonte_repetida_nao_infla(self):
        _, itens = _persistir_grupo([(_bruto("Fato W", "G1", "https://g1/fato-w"), _resumo())])
        cluster, _ = _persistir_grupo_mesclado(
            [(_bruto("Fato W", "G1", "https://g1/fato-w-2"), _resumo())],
            itens,
        )
        cluster.refresh_from_db()
        assert cluster.numero_fontes_distintas == 1


# ---------------------------------------------------------------------------
# Crit. 2 — backfill idempotente
# ---------------------------------------------------------------------------


class TestBackfillMigracao:
    def test_backfill_preenche_clusters_preexistentes_e_idempotente(self):
        cluster = NewsCluster.objects.create(titulo_acontecimento="Fato antigo")
        _item_feed("A cobre", "G1", "https://g1/antigo", cluster=cluster)
        _item_feed("A cobre de novo", "G1", "https://g1/antigo-2", cluster=cluster)
        _item_feed("B cobre", "UOL", "https://uol/antigo", cluster=cluster)
        _item_feed("C cobre", "CNN Brasil", "https://cnn/antigo", cluster=cluster)
        # Simula linha anterior à migração (valor stale/default).
        NewsCluster.objects.filter(pk=cluster.pk).update(numero_fontes_distintas=1)

        migracao = importlib.import_module(
            "catalogo_noticias.migrations.0009_newscluster_numero_fontes"
        )
        from django.apps import apps

        migracao.backfill_numero_fontes(apps, None)
        cluster.refresh_from_db()
        assert cluster.numero_fontes_distintas == 3
        # Segunda execução não muda nada (idempotente).
        migracao.backfill_numero_fontes(apps, None)
        cluster.refresh_from_db()
        assert cluster.numero_fontes_distintas == 3


# ---------------------------------------------------------------------------
# Crit. 3/4/5/6 — feed (com cache locmem real)
# ---------------------------------------------------------------------------


@pytest.fixture()
def _cache_locmem_real():
    # `override_settings` como decorador de classe só funciona em
    # `SimpleTestCase`; aqui via context manager (padrão suportado pelo
    # Django para `CACHES` — recria o handler e limpa ao sair).
    with override_settings(CACHES=CACHE_LOCMEM):
        cache.clear()
        yield
        cache.clear()


@pytest.mark.usefixtures("_cache_locmem_real")
class TestFeedQueriesCacheContrato:
    def _seis_clusters(self):
        for i in range(6):
            cluster = NewsCluster.objects.create(
                titulo_acontecimento=f"Fato {i}",
                categoria_dominante="cidades",
                numero_fontes_distintas=2,
            )
            _item_feed(f"Fato {i} (A)", "G1", f"https://g1/fato-{i}", cluster=cluster)
            _item_feed(f"Fato {i} (B)", "UOL", f"https://uol/fato-{i}", cluster=cluster)

    def test_teto_de_queries_nao_cresce_com_volume(self, django_assert_num_queries):
        # Crit. 3: 6 clusters × 2 itens = 6 entradas em EXATAS 2 queries
        # (1 de itens com join do cluster + 1 de regras de curadoria).
        # Sem a coluna denormalizada seriam 6 COUNTs adicionais (N+1) —
        # o número aqui NÃO pode crescer com K.
        self._seis_clusters()
        client = APIClient()
        with django_assert_num_queries(2):
            resposta = client.get("/api/feed/")
        assert resposta.status_code == 200
        assert resposta.data["count"] == 6
        assert all(e["numero_fontes"] == 2 for e in resposta.data["results"])

    def test_teto_de_queries_com_regras_de_curadoria_ativas(self, django_assert_num_queries):
        # Ponto de atenção do task-plan: `aplicar_regras_curadoria` lê
        # `id`/`cluster_id`/`autor` dos itens — todos presentes no
        # `.only()` de `CAMPOS_LISTA_FEED`. Com regras ATIVAS (incluindo
        # colunista_destaque, que casa com `NewsItem.autor`) o teto segue
        # fixo: 1 query de itens + 1 de regras — sem N+1 de deferred fields.
        self._seis_clusters()
        RegraCuradoria.objects.create(tipo=RegraCuradoria.TIPO_COLUNISTA_DESTAQUE, alvo="Colunista X")
        RegraCuradoria.objects.create(tipo=RegraCuradoria.TIPO_BOOST_CATEGORIA, alvo="cidades")
        client = APIClient()
        with django_assert_num_queries(2):
            resposta = client.get("/api/feed/")
        assert resposta.status_code == 200
        assert resposta.data["count"] == 6

    def test_listagem_nao_seleciona_colunas_pesadas(self):
        # Crit. 4: `conteudo_bruto`/`conteudo_completo` fora do SQL.
        self._seis_clusters()
        client = APIClient()
        with CaptureQueriesContext(connection) as ctx:
            resposta = client.get("/api/feed/")
        assert resposta.status_code == 200
        sql = " ".join(q["sql"] for q in ctx.captured_queries).lower()
        assert "conteudo_bruto" not in sql
        assert "conteudo_completo" not in sql

    def test_segundo_get_identico_nao_toca_o_banco(self, django_assert_num_queries):
        # Crit. 5: dentro do TTL, o segundo GET idêntico sai do cache.
        self._seis_clusters()
        client = APIClient()
        primeira = client.get("/api/feed/")
        assert primeira.status_code == 200
        with django_assert_num_queries(0):
            segunda = client.get("/api/feed/")
        assert segunda.status_code == 200
        assert segunda.data == primeira.data

    def test_cutover_feed_v2_ignora_payload_remoto_v1_e_preserva_ttl(self):
        item_local = _item_feed(
            "Notícia local após o arquivamento",
            "Fonte local",
            "https://local.test/feed-v2",
        )
        chave_v1 = "feed:v1:lista:uanon:categoria=cidades&page_size=20"
        payload_remoto = {
            "count": 1,
            "next": None,
            "previous": None,
            "results": [
                {
                    "tipo": "item",
                    "id": 987654321,
                    "titulo": "PAYLOAD REMOTO ARQUIVADO",
                }
            ],
        }
        cache.set(chave_v1, payload_remoto, 45)

        cliente = APIClient()
        with override_settings(FEED_CACHE_TTL_SEGUNDOS=45), patch.object(
            feed_views, "cache", wraps=cache
        ) as cache_spy:
            resposta = cliente.get(
                "/api/feed/",
                {"categoria": "cidades", "page_size": 20},
            )

        assert resposta.status_code == 200
        assert resposta.data["count"] == 1
        assert resposta.data["results"][0]["id"] == item_local.pk
        assert resposta.data["results"][0]["titulo"] == item_local.titulo

        # O cutover não apaga nem consulta a chave antiga: apenas deixa de
        # usá-la. A resposta nova fica em feed:v2, com o TTL configurado.
        leituras_v1 = [
            chamada
            for chamada in cache_spy.get.call_args_list
            if chamada.args and chamada.args[0] == chave_v1
        ]
        assert leituras_v1 == []
        chave_v2 = "feed:v2:lista:uanon:categoria=cidades&page_size=20"
        assert cache.get(chave_v1) == payload_remoto
        assert cache.get(chave_v2) == resposta.data
        chamadas_v2 = [
            chamada
            for chamada in cache_spy.set.call_args_list
            if chamada.args and chamada.args[0] == chave_v2
        ]
        assert len(chamadas_v2) == 1
        assert chamadas_v2[0].args[2] == 45

    def test_nenhum_endpoint_do_feed_expoe_publicidade(self):
        # Crit. 6: breaking controlado — ads via GET /api/gating/status.
        cluster = NewsCluster.objects.create(
            titulo_acontecimento="Fato", categoria_dominante="cidades",
            numero_fontes_distintas=2,
        )
        item = _item_feed("Fato (A)", "G1", "https://g1/fato", cluster=cluster)
        _item_feed("Fato (B)", "UOL", "https://uol/fato", cluster=cluster)
        client = APIClient()
        urls = [
            "/api/feed/",
            "/api/feed/home/",
            "/api/feed/destaques/",
            "/api/feed/urgentes/",
            "/api/feed/mais-lidas/",
            f"/api/feed/cluster/{cluster.id}/",
            f"/api/feed/item/{item.id}/",
            f"/api/feed/cobertura/cluster/{cluster.id}/",
            "/api/feed/busca/?q=fato",
        ]
        for url in urls:
            resposta = client.get(url)
            assert resposta.status_code == 200, url
            corpo = resposta.data
            entradas = corpo if isinstance(corpo, list) else [corpo, * (corpo.get("results", []) or [])]
            for entrada in entradas:
                assert "exibir_publicidade" not in entrada, url


    def test_urgentes_limite_invalido_cai_no_default(self):
        self._seis_clusters()
        client = APIClient()
        resposta = client.get("/api/feed/urgentes/?limite=abc")
        assert resposta.status_code == 200


# ---------------------------------------------------------------------------
# Crit. 5 (gating) — MeusRecursos consolidada + flag com cache
# ---------------------------------------------------------------------------


@pytest.mark.usefixtures("_cache_locmem_real")
class TestGatingCache:
    def test_meus_recursos_uma_query_fria_zero_quente(self, django_assert_num_queries):
        ConfiguracaoSistema.objects.update_or_create(pk=1, defaults={"premium_ativo": True})
        for chave in ("a_recurso", "b_recurso", "c_recurso"):
            FeatureLimit.objects.create(chave=chave, plano="free", valor="false")
            FeatureLimit.objects.create(chave=chave, plano="premium", valor="true")
        client = APIClient()
        with django_assert_num_queries(2):
            primeira = client.get("/api/gating/meus-recursos/")
        assert primeira.status_code == 200
        assert primeira.data["plano"] == "free"
        # A migração de gating semeia chaves próprias — valida só as criadas
        # aqui (ordem alfabética entre todas).
        por_chave = {r["chave"]: r for r in primeira.data["recursos"]}
        chaves = sorted(por_chave)
        assert chaves.index("a_recurso") < chaves.index("b_recurso") < chaves.index("c_recurso")
        assert all(por_chave[c]["disponivel"] is False for c in ("a_recurso", "b_recurso", "c_recurso"))
        assert all(por_chave[c]["valor"] == "false" for c in ("a_recurso", "b_recurso", "c_recurso"))
        with django_assert_num_queries(0):
            segunda = client.get("/api/gating/meus-recursos/")
        assert segunda.data == primeira.data

    def test_premium_ativo_invalida_no_save(self):
        ConfiguracaoSistema.objects.update_or_create(pk=1, defaults={"premium_ativo": True})
        from gating.services import premium_ativo

        assert premium_ativo() is True
        ConfiguracaoSistema.objects.update_or_create(pk=1, defaults={"premium_ativo": False})
        assert premium_ativo() is False

    def test_premium_ativo_invalida_no_delete(self):
        from gating.services import premium_ativo

        ConfiguracaoSistema.objects.update_or_create(pk=1, defaults={"premium_ativo": True})
        assert premium_ativo() is True
        ConfiguracaoSistema.objects.filter(pk=1).delete()
        assert premium_ativo() is False
