"""
P1-02 — Fallback local do OpenAI (workstream WS-08, gate GP-5).

Criterio de saida do backlog: "Fallback executa, publica e e distinguivel em
metrica/log". Os tres requisitos sao cobertos por tres grupos de testes:

1. EXECUTA  — sem credencial, credencial invalida (401/500), rate limit
   (429) e timeout produzem conteudo pelo caminho local deterministico, sem
   quebrar o pipeline. `TestFallbackExecuta`.
2. PUBLICA  — o conteudo do fallback entra no fluxo normal de publicacao
   (mesmo contrato de campos, visivel no feed) e NUNCA vira copia do texto
   bruto. `TestFallbackPublica`, `TestFallbackNaoFabricaFato`.
3. DISTINGUIVEL — metrica rotulada (`sucesso`/`fallback` + motivo), log
   estruturado com o motivo, marcador de origem persistido e painel.
   `TestMetrica`, `TestLog`, `TestMarcadorDeOrigem`.

NENHUM teste faz chamada de rede real: a chamada de saida do provedor e sempre
mockada e nenhuma credencial real e usada. O caminho feliz e testado com um
dublê de resposta HTTP valida, o que prova que o provedor EXTERNAL e de fato
chamado quando tudo funciona — sem esse teste a suite passaria mesmo com o
provedor totalmente desconectado.

ONDE O DUBLE DEVE APONTAR (conflito P0-10 x P1-02)
-------------------------------------------------
Este arquivo nasceu no P1-02, quando `_chamar_api` ainda usava
`requests.post` direto, e por isso apontava o dublê para `requests.post`. O
P0-10, no mesmo `providers/summarization.py`, trocou essa chamada por
`config.egress.SessaoEgress` (eixo SSRF: `api_base_url` e administravel e a
base de um POST que leva `Authorization: Bearer <api_key>`, entao a saida
precisa passar pela politica de bloqueio de destino) — e teve de reidenciar os
dubles de `test_summarization_provider.py` para `SessaoEgress.post` pelo
mesmo motivo. O merge dos dois nao pode reintroduzir o alvo antigo: dublê em
`requests.post` deixa de interceptar a chamada e o teste passa a exercitar a
REDE REAL (o que ja aconteceu na primeira rodada desta resolucao: um 401 de
`api.openai.com` em vez do timeout simulado). `_ALVO_POST` abaixo e o alvo
correto, e os guardas de "nenhuma chamada de rede" cobrem os DOIS alvos para
nao enfraquecer a garantia.
"""

from __future__ import annotations

import json
import logging
from unittest.mock import MagicMock, patch

import pytest
import requests

from catalogo_noticias.models import NewsItem
from catalogo_noticias.providers.fallback_local import (
    MOTIVO_CONTEUDO_INSUFICIENTE,
    MOTIVO_ERRO_HTTP,
    MOTIVO_RATE_LIMIT,
    MOTIVO_SEM_CREDENCIAL,
    MOTIVO_TIMEOUT,
    TAG_ORIGEM_FALLBACK,
    eh_tag_tecnica,
    gerar_resumo_local,
    marcadores_tags,
    motivo_fallback_local,
    normalizar_motivo,
    origem_fallback_local,
    verificar_sem_fabricacao,
)
from catalogo_noticias.providers.news_source import ItemBruto, NewsSourceProvider
from catalogo_noticias.providers.summarization import (
    LLMHttpSummarizationProvider,
    ResultadoResumo,
    SummarizationProvider,
    SummarizationProviderError,
)
from catalogo_noticias.services import telemetria_resumo
from catalogo_noticias.services.ingestao import executar_ingestao
from feed import services as feed_services

pytestmark = pytest.mark.django_db

# Credencial FICTICIA, usada apenas dentro dos mocks. O valor e escolhido para
# ser gritantemente reconhecivel num log caso algo vaze.
CHAVE_FICTICIA = "sk-fallback-p102-NAO-LOGAR-0000"

#: Alvo real da chamada de saida do `LLMHttpSummarizationProvider` depois do
#: P0-10 (eixo SSRF): `SessaoEgress.post`, e nao `requests.post`. Ver o
#: docstring do modulo para o porque do merge.
_ALVO_POST = "catalogo_noticias.providers.summarization.SessaoEgress.post"

CONTEXTO_PUBLICO = (
    "OCarmen e Veronica,%20a22a20mostram%20o20avanco%20da20reforma%20do%20centro."
)


def _item(
    titulo="Prefeitura anuncia obras no centro",
    nome_fonte="G1 Goias",
    url="https://g1/noticia/1",
    conteudo="A prefeitura anunciou obras no centro nesta semana.",
    categoria="",
    estado="",
    pais="",
):
    return ItemBruto(
        titulo=titulo,
        url_fonte_original=url,
        nome_fonte=nome_fonte,
        conteudo_bruto=conteudo,
        categoria=categoria,
        estado_fonte=estado,
        pais_fonte=pais,
    )


class FonteFicticia(NewsSourceProvider):
    """Fonte sem rede: devolve itens pré-montados."""

    def __init__(self, itens, nome="G1 Goias"):
        self.nome_fonte = nome
        self._itens = itens

    def buscar_itens(self):
        return list(self._itens)


def _resposta_http(conteudo_json, status_code=200, total_tokens=None):
    """Dublê de `requests.Response` com JSON de Chat Completions válido."""
    corpo = {"choices": [{"message": {"content": conteudo_json}}]}
    if total_tokens is not None:
        corpo["usage"] = {"total_tokens": total_tokens}
    resposta = MagicMock()
    resposta.status_code = status_code
    resposta.json.return_value = corpo
    resposta.raise_for_status.side_effect = (
        None if status_code < 400 else requests.HTTPError(f"{status_code} erro")
    )
    return resposta


def _resposta_lote(valores):
    """`valores`: lista de (id, resumo, categoria) -> JSON de lote válido."""
    return json.dumps(
        [
            {"id": i, "resumo": resumo, "categoria": categoria, "urgente": False}
            for i, resumo, categoria in valores
        ]
    )


def _roda_ingestao(provider, itens=None):
    itens = itens if itens is not None else [_item()]
    return executar_ingestao(
        fontes=[FonteFicticia(itens)],
        summarization_provider=provider,
    )


@pytest.fixture(autouse=True)
def _zera_telemetria():
    """O contador de `telemetria_resumo` e DE PROCESSO: zera entre testes."""
    telemetria_resumo.zerar()
    yield
    telemetria_resumo.zerar()


# ===========================================================================
# 1. EXECUTA — o fallback roda quando o provedor externo esta indisponivel
# ===========================================================================


class TestFallbackExecuta:
    def test_sem_credencial_configurada_usa_fallback_local_e_registra_metrica(self):
        """
        `CATALOGO_NOTICIAS_LLM_API_KEY` vazia -> nenhum acesso a rede, o
        pipeline NAO quebra e a metrica registra `fallback`/`sem_credencial`.
        """
        provider = LLMHttpSummarizationProvider(api_key="")

        with patch(_ALVO_POST, side_effect=AssertionError("rede nao pode ser chamada")), patch(
            "requests.post", side_effect=AssertionError("rede nao pode ser chamada")
        ):
            _roda_ingestao(provider)

        assert telemetria_resumo.snapshot()["fallback"]["sem_credencial"] == 1
        assert telemetria_resumo.snapshot()["sucesso"]["total"] == 0
        assert NewsItem.objects.get().resumo_proprio != ""

    def test_timeout_do_provedor_usa_fallback_local_e_registra_metrica(self):
        provider = LLMHttpSummarizationProvider(api_key=CHAVE_FICTICIA)

        with patch(_ALVO_POST, side_effect=requests.Timeout("estourou o prazo")):
            _roda_ingestao(provider)

        assert telemetria_resumo.snapshot()["fallback"]["timeout"] == 1
        assert NewsItem.objects.get().resumo_proprio != ""

    def test_credencial_invalida_401_usa_fallback_local_com_motivo_erro_http(self):
        """401 = chave errada/nao autorizada: nao e timeout, nao e rate limit."""
        provider = LLMHttpSummarizationProvider(api_key=CHAVE_FICTICIA)
        resposta = _resposta_http("{}", status_code=401)

        with patch(_ALVO_POST, return_value=resposta):
            _roda_ingestao(provider)

        assert telemetria_resumo.snapshot()["fallback"][MOTIVO_ERRO_HTTP] == 1
        item = NewsItem.objects.get()
        assert item.resumo_proprio != ""
        assert motivo_fallback_local(item.tags) == MOTIVO_ERRO_HTTP

    def test_erro_500_do_provedor_usa_fallback_local_com_motivo_erro_http(self):
        provider = LLMHttpSummarizationProvider(api_key=CHAVE_FICTICIA)

        with patch(_ALVO_POST, return_value=_resposta_http("{}", status_code=500)):
            _roda_ingestao(provider)

        assert telemetria_resumo.snapshot()["fallback"][MOTIVO_ERRO_HTTP] == 1

    def test_rate_limit_429_tem_motivo_proprio_distinto_de_erro_http(self):
        """
        429 e um motivo SEPARADO de "erro http": o provedor esta recusando por
        cota, nao por falha. Um rotulo umbrella ("erro") esconderia exatamente
        a informacao que o operador precisa para agir.
        """
        provider = LLMHttpSummarizationProvider(api_key=CHAVE_FICTICIA)

        with patch(_ALVO_POST, return_value=_resposta_http("{}", status_code=429)):
            _roda_ingestao(provider)

        assert telemetria_resumo.snapshot()["fallback"][MOTIVO_RATE_LIMIT] == 1
        assert telemetria_resumo.snapshot()["fallback"].get(MOTIVO_ERRO_HTTP) is None
        assert motivo_fallback_local(NewsItem.objects.get().tags) == MOTIVO_RATE_LIMIT

    def test_falha_de_conexao_usa_fallback_com_motivo_erro_http(self):
        provider = LLMHttpSummarizationProvider(api_key=CHAVE_FICTICIA)

        with patch(_ALVO_POST, side_effect=requests.ConnectionError("recusada")):
            _roda_ingestao(provider)

        assert telemetria_resumo.snapshot()["fallback"][MOTIVO_ERRO_HTTP] == 1

    def test_resposta_malformada_do_provedor_usa_fallback_com_motivo_resposta_invalida(self):
        provider = LLMHttpSummarizationProvider(api_key=CHAVE_FICTICIA)

        with patch(_ALVO_POST, return_value=_resposta_http("isto nao e json")):
            _roda_ingestao(provider)

        assert "resposta_invalida" in telemetria_resumo.snapshot()["fallback"]

    def test_timeout_configurado_invalido_e_corrigido_para_nao_haver_chamada_sem_limite(self):
        """
        `timeout=None` em `requests` = esperar para sempre; `timeout<=0` levanta
        `ValueError`, que NAO e `RequestException` e escaparia do tratamento de
        erro derrubando a ingestao. Configuracao invalida e normalizada.
        """
        for indice, valor_invalido in enumerate((0, -5, None, "abc")):
            provider = LLMHttpSummarizationProvider(
                api_key=CHAVE_FICTICIA, timeout_segundos=valor_invalido
            )
            assert provider.timeout_segundos >= 1
            with patch(_ALVO_POST, return_value=_resposta_http(_resposta_lote([(1, "R.", "geral")]))) as mock_post:
                provider.resumir_e_classificar_em_lote([_item(url=f"https://g1/t/{indice}")])
            assert mock_post.call_args.kwargs["timeout"] >= 1

    def test_chamada_externa_sempre_recebe_timeout_explicito_e_positivo(self):
        provider = LLMHttpSummarizationProvider(api_key=CHAVE_FICTICIA, timeout_segundos=7)

        with patch(_ALVO_POST, return_value=_resposta_http(_resposta_lote([(1, "R.", "geral")]))) as mock_post:
            provider.resumir_e_classificar_em_lote([_item()])

        assert mock_post.call_args.kwargs["timeout"] == 7

    def test_fallback_e_deterministico_para_o_mesmo_material(self):
        item = _item()
        primeiro = gerar_resumo_local(item)
        segundo = gerar_resumo_local(item)
        assert primeiro == segundo
        assert primeiro.suficiente is True

    def test_fallback_nao_faz_nenhuma_chamada_de_rede(self):
        """O caminho local e, por definicao, offline."""
        item = _item()
        with patch("requests.get", side_effect=AssertionError("rede")), patch(
            _ALVO_POST, side_effect=AssertionError("rede")
        ), patch(
            "requests.post", side_effect=AssertionError("rede")
        ), patch(
            "urllib.request.urlopen", side_effect=AssertionError("rede")
        ):
            resultado = gerar_resumo_local(item)
        assert resultado.suficiente is True
        assert resultado.resumo != ""


# ===========================================================================
# 2. PUBLICA — o conteudo do fallback entra no fluxo normal de publicacao
# ===========================================================================


class TestFallbackPublica:
    def test_item_do_fallback_entra_no_feed_publico_como_noticia_completa(self):
        """
        O ponto do backlog: antes, o fallback produzia `resumo_proprio=""` ->
        `status_revisao=pendente` -> item INVISIVEL em
        `feed/services.py::itens_publicaveis` (o "rascunho fantasma").
        Agora o leitor ve a noticia no feed, e o detalhe traz o texto integral
        com credito e link para a fonte.
        """
        provider = LLMHttpSummarizationProvider(api_key="")

        with patch(_ALVO_POST, side_effect=AssertionError("rede")), patch(
            "requests.post", side_effect=AssertionError("rede")
        ):
            _roda_ingestao(provider)

        item = NewsItem.objects.get()
        assert item.status_revisao == NewsItem.STATUS_NAO_APLICAVEL
        assert item.publicado_automaticamente is True
        publicaveis = list(feed_services.itens_publicaveis())
        assert [i.pk for i in publicaveis] == [item.pk]
        # A listagem do feed expoe o mesmo contrato de campos de sempre.
        assert publicaveis[0].titulo == item.titulo
        assert publicaveis[0].resumo_proprio == item.resumo_proprio
        assert publicaveis[0].nome_fonte == item.nome_fonte

    def test_item_do_fallback_tem_o_mesmo_contrato_de_campos_do_item_normal(self):
        """
        Mesmo contrato: nao falta nenhum campo obrigatorio.

        Usa `clean()` (e nao `full_clean()`) de proposito: e o que o pipeline
        aplica, e a propria docstring de `_persistir_news_items_em_lote` explica
        por que `full_clean` foi avaliado e rejeitado (ele recusaria URLs
        históricas aceitas pelo pipeline, ex.: host sem sufixo publico).
        """
        _roda_ingestao(LLMHttpSummarizationProvider(api_key=""))
        item = NewsItem.objects.get()
        item.clean()
        assert item.url_fonte_original
        assert item.nome_fonte
        assert item.titulo
        assert item.timestamp_ingestao is not None
        assert item.categoria == ""
        assert item.urgente is False
        assert item.resumo_proprio != ""

    def test_sem_manchete_o_fallback_sinaliza_e_nao_publica(self):
        """
        "Se o fallback nao tem material suficiente, ele deve sinalizar isso
        explicitamente em vez de preencher." Sem titulo nao ha materia a
        descrever: o motivo vira `conteudo_insuficiente`, o item vai para
        revisao humana e NAO aparece no feed.
        """
        provider = LLMHttpSummarizationProvider(api_key=CHAVE_FICTICIA)
        sem_manchete = _item(titulo="", url="https://g1/noticia/sem-manchete")

        with patch(_ALVO_POST, side_effect=requests.Timeout("prazo")):
            _roda_ingestao(provider, itens=[sem_manchete])

        item = NewsItem.objects.get()
        assert item.resumo_proprio == ""
        assert item.status_revisao == NewsItem.STATUS_PENDENTE
        assert item.pk not in set(
            feed_services.itens_publicaveis().values_list("pk", flat=True)
        )
        assert telemetria_resumo.snapshot()["fallback"][MOTIVO_CONTEUDO_INSUFICIENTE] == 1
        assert motivo_fallback_local(item.tags) == MOTIVO_CONTEUDO_INSUFICIENTE

    def test_lote_inteiro_cai_junto_sem_perder_nenhum_item(self):
        """Falha da chamada em lote nao pode descartar as noticias do lote."""
        provider = LLMHttpSummarizationProvider(api_key=CHAVE_FICTICIA)
        itens = [_item(url=f"https://g1/noticia/{i}") for i in range(3)]

        with patch(_ALVO_POST, side_effect=requests.Timeout("prazo")):
            _roda_ingestao(provider, itens=itens)

        assert NewsItem.objects.count() == 3
        assert all(item.resumo_proprio != "" for item in NewsItem.objects.all())
        assert telemetria_resumo.snapshot()["fallback"]["total"] == 3

    def test_provider_que_devolve_numero_errado_de_resultados_ainda_nao_atribui_resumo_ao_item_errado(self):
        """
        Garantia anti-misattribution (BRD secao 18) preservada: um provider
        desalinhado descarta o lote INTEIRO; o fallback local nao "adivinha" o
        alinhamento — cada item recebe o SEU proprio resumo local.
        """
        class ProviderDesalinhado(SummarizationProvider):
            def resumir_e_classificar(self, itens_brutos):
                raise AssertionError("nao deve ser chamado: o lote esta desalinhado")

            def resumir_e_classificar_em_lote(self, itens_brutos):
                return [ResultadoResumo(resumo="Resumo do item 1")]  # 1 para 3 itens

        itens = [
            _item(titulo=f"Materia numero {i}", url=f"https://g1/noticia/d{i}")
            for i in range(3)
        ]
        _roda_ingestao(ProviderDesalinhado(), itens=itens)

        por_url = {i.url_fonte_original: i for i in NewsItem.objects.all()}
        assert len(por_url) == 3
        for indice in range(3):
            resumo = por_url[f"https://g1/noticia/d{indice}"].resumo_proprio
            assert f"Materia numero {indice}" in resumo
            for outro in range(3):
                if outro != indice:
                    assert f"Materia numero {outro}" not in resumo


# ===========================================================================
# 2b. NAO FABRICA MATERIA — o fallback nao inventa fato, numero ou fonte
# ===========================================================================


class TestFallbackNaoFabricaFato:
    def test_resumo_nao_contem_nenhum_digito_ausente_do_material_de_origem(self):
        item = _item(
            titulo="Inflacao de 4,5% em agosto",
            nome_fonte="Valor Economico",
            categoria="economia",
            pais="Brasil",
        )
        resultado = gerar_resumo_local(item)
        assert resultado.suficiente is True
        digitos_da_origem = {
            c
            for valor in (item.titulo, item.nome_fonte, item.categoria, item.pais_fonte, item.estado_fonte)
            for c in str(valor)
            if c.isdigit()
        }
        assert digitos_da_origem == {"4", "5"}  # o material tem digitos...
        assert {c for c in resultado.resumo if c.isdigit()} <= digitos_da_origem

    def test_resumo_nao_introduz_nome_de_fonte_que_nao_esta_no_material(self):
        item = _item(nome_fonte="G1 Goias")
        resultado = gerar_resumo_local(item)
        for nome_proibido in ("Reuters", "Bloomberg", "Folha", "CNN", "UOL"):
            assert nome_proibido not in resultado.resumo
        assert "G1 Goias" in resultado.resumo

    def test_verificador_acusa_texto_com_fato_inventado(self):
        """O verificador anti-fabricacao NAO e decorativo: acusa e rejeita."""
        item = _item(titulo="Prefeitura anuncia obras", nome_fonte="G1 Goias")
        texto_inventado = "Prefeitura anunciou obras 47 bilhoes, Reuters."
        violacoes = verificar_sem_fabricacao(texto_inventado, item)
        assert violacoes, "o verificador deveria acusar nome de fonte e digitos inventados"
        assert any(v.startswith("digitos_ausentes") for v in violacoes)
        # O verificador normaliza (minusculas, sem acento) para casar de forma
        # insensivel — por isso a comparacao aqui tambem.
        junto = " ".join(violacoes).casefold()
        assert "reuters" in junto
        assert "bilhoes" in junto

    def test_verificador_aceita_resumo_vazio_sem_acusar_falsos_positivos(self):
        """Resumo vazio nao tem o que fabricar: nao pode gerar violacao."""
        assert verificar_sem_fabricacao("", _item()) == []

    def test_gerador_rejeita_o_resumo_quando_a_verificacao_acusa_violacao(self, monkeypatch):
        """
        Defesa em profundidade: se a montagem violar a regra, o gerador NAO
        publica o texto — sinaliza insuficiencia. Verificado por monkeypatch
        para simular a violacao, ja que a montagem real respeita a regra por
        construcao.
        """
        monkeypatch.setattr(
            "catalogo_noticias.providers.fallback_local.verificar_sem_fabricacao",
            lambda resumo, item: ["digitos_ausentes_do_material:99"],
        )
        resultado = gerar_resumo_local(_item())
        assert resultado.suficiente is False
        assert resultado.resumo == ""
        assert resultado.violacoes == ("digitos_ausentes_do_material:99",)

    def test_resumo_do_fallback_passa_no_verificador_para_variacoes_de_material(self):
        variacoes = [
            _item(titulo="Vacinacao comeca em 12 escolas", nome_fonte="UOL", categoria="saude", estado="SP", pais="Brasil"),
            _item(titulo="Prefeitura de Goiania anuncia obras no centro", nome_fonte="G1 Goias", categoria="politica", estado="GO", pais="Brasil"),
            _item(titulo="Final do campeonato decide o titulo amanha a noite", nome_fonte="GE"),
        ]
        for item in variacoes:
            resultado = gerar_resumo_local(item)
            assert resultado.suficiente is True
            assert verificar_sem_fabricacao(resultado.resumo, item) == []

    def test_fallback_nunca_devolve_o_texto_bruto_como_resumo(self):
        """AC-4: `conteudo_bruto`/`conteudo_completo` nunca viram `resumo_proprio`."""
        bruto = "OCarmen e Veronica,%20a22a20mostram%20o20avanco%20da%20reforma%20do%20centro."
        provider = LLMHttpSummarizationProvider(api_key=CHAVE_FICTICIA)

        with patch(_ALVO_POST, side_effect=requests.Timeout("prazo")):
            _roda_ingestao(provider, itens=[_item(conteudo=bruto)])

        item = NewsItem.objects.get()
        assert item.resumo_proprio != bruto
        assert bruto not in item.resumo_proprio

    def test_resumo_gerado_pelo_fallback_nao_dispara_o_bloqueio_de_copia(self):
        """
        O pipeline bloqueia resumo que seja copia/quase-copia do bruto
        (`_resumo_e_copia_ou_quase_copia`). O fallback local nao pode cair
        nesse bloqueio — se caísse, voltaria ao "rascunho fantasma".
        """
        bruto = (
            "A prefeitura de Goiania anunciou nesta semana o inicio das obras "
            "de revitalizacao do corredor central, com prazo previsto de seis meses."
        )
        provider = LLMHttpSummarizationProvider(api_key="")
        with patch(_ALVO_POST, side_effect=AssertionError("rede")), patch(
            "requests.post", side_effect=AssertionError("rede")
        ):
            _roda_ingestao(provider, itens=[_item(conteudo=bruto)])

        item = NewsItem.objects.get()
        assert item.status_revisao == NewsItem.STATUS_NAO_APLICAVEL


# ===========================================================================
# 3. DISTINGUIVEL — metrica, log, marcador persistido e painel
# ===========================================================================


class TestMetrica:
    def test_caminho_feliz_chama_o_provedor_externo_e_conta_sucesso(self):
        """
        TESTE DO CAMINHO FELIZ — o mais importante desta suite.

        Prova, com mock de HTTP, que o provedor EXTERNO e realmente chamado
        quando ha credencial e tudo funciona. Sem este teste, a suite inteira
        passaria mesmo com o provedor 100% desconectado (basta o fallback
        local ALWAYS succeed). E prova que a metrica de fallback NAO sobe no
        caminho feliz.
        """
        provider = LLMHttpSummarizationProvider(api_key=CHAVE_FICTICIA)
        itens = [_item(url=f"https://g1/noticia/ok{i}") for i in range(2)]
        conteudo = _resposta_lote(
            [(1, "Resumo autoral da materia um.", "geral"), (2, "Resumo autoral da materia dois.", "geral")]
        )

        with patch(
            _ALVO_POST,
            return_value=_resposta_http(conteudo, total_tokens=80),
        ) as mock_post:
            _roda_ingestao(provider, itens=itens)

        # O provedor foi CHAMADO, com o cabecalho de autenticacao e o timeout.
        assert mock_post.call_count == 1
        assert mock_post.call_args.kwargs["headers"]["Authorization"] == f"Bearer {CHAVE_FICTICIA}"
        assert mock_post.call_args.kwargs["timeout"] >= 1

        # O resumo do PROVEDOR foi o aplicado (nao o fallback local).
        itens_db = {i.url_fonte_original: i for i in NewsItem.objects.all()}
        assert itens_db["https://g1/noticia/ok0"].resumo_proprio == "Resumo autoral da materia um."
        assert itens_db["https://g1/noticia/ok1"].resumo_proprio == "Resumo autoral da materia dois."

        # Metrica: sucesso subiu, fallback NAO subiu.
        snapshot = telemetria_resumo.snapshot()
        assert snapshot["sucesso"]["total"] == 2
        assert snapshot["fallback"]["total"] == 0
        assert telemetria_resumo.total("fallback") == 0

    def test_metrica_de_fallback_sobe_no_fallback_e_nao_sobe_no_caminho_feliz(self):
        """
        O par de asserts que impede o falso verde: a mesma metrica precisa
        SUBIR no fallback e NAO SUBIR no caminho feliz.

        URLs distintas em (a) e (b) de proposito: dentro de um mesmo teste o
        banco nao sofre rollback entre as duas execucoes, e a mesma URL ja
        ingerida em (a) faria (b) nao chamar o provedor — um falso verde
        silencioso.
        """
        # (a) fallback
        _roda_ingestao(
            LLMHttpSummarizationProvider(api_key=""),
            itens=[_item(url="https://g1/noticia/metrica-a")],
        )
        assert telemetria_resumo.total("fallback") == 1
        assert telemetria_resumo.total("sucesso") == 0

        telemetria_resumo.zerar()

        # (b) caminho feliz
        provider = LLMHttpSummarizationProvider(api_key=CHAVE_FICTICIA)
        with patch(
            _ALVO_POST,
            return_value=_resposta_http(_resposta_lote([(1, "Resumo autoral.", "geral")])),
        ):
            _roda_ingestao(provider, itens=[_item(url="https://g1/noticia/metrica-b")])
        assert telemetria_resumo.total("fallback") == 0
        assert telemetria_resumo.total("sucesso") == 1

    def test_motivo_desconhecido_e_normalizado_para_nao_inflar_cardinalidade(self):
        """
        Um rotulo livre permitiria cardinalidade ilimitada na metrica (e,
        no pior caso, vazar texto sensivel para dentro do nome do rotulo).
        """
        telemetria_resumo.registrar_fallback("motivo-inesperado-que-nao-existe")
        assert "erro_interno" in telemetria_resumo.snapshot()["fallback"]
        assert "motivo-inesperado-que-nao-existe" not in telemetria_resumo.snapshot()["fallback"]
        assert normalizar_motivo("qualquer-coisa") == "erro_interno"
        assert normalizar_motivo(MOTIVO_TIMEOUT) == MOTIVO_TIMEOUT

    def test_resultado_desconhecido_e_contado_como_fallback_nao_como_sucesso(self):
        telemetria_resumo.registrar("resultado-inexistente", MOTIVO_TIMEOUT)
        assert telemetria_resumo.total("fallback") == 1
        assert telemetria_resumo.total("sucesso") == 0

    def test_snapshot_agrupa_por_resultado_e_soma_os_motivos(self):
        telemetria_resumo.registrar_sucesso(2)
        telemetria_resumo.registrar_fallback(MOTIVO_TIMEOUT)
        telemetria_resumo.registrar_fallback(MOTIVO_TIMEOUT)
        telemetria_resumo.registrar_fallback(MOTIVO_SEM_CREDENCIAL)
        snapshot = telemetria_resumo.snapshot()
        assert snapshot["sucesso"] == {"aplicado": 2, "total": 2}
        assert snapshot["fallback"]["timeout"] == 2
        assert snapshot["fallback"]["sem_credencial"] == 1
        assert snapshot["fallback"]["total"] == 3

    def test_quantidade_invalida_ou_nao_positiva_e_normalizada_para_1(self):
        """Um lote de 0 ou uma quantidade nao numerica nao pode zerar a metrica."""
        for quantidade in (0, -3, "abc", None):
            telemetria_resumo.zerar()
            telemetria_resumo.registrar_fallback(MOTIVO_TIMEOUT, quantidade)
            assert telemetria_resumo.total("fallback") == 1

    def test_total_sem_argumento_soma_os_dois_rotulos_e_ignora_rotulo_desconhecido(self):
        telemetria_resumo.registrar_sucesso(3)
        telemetria_resumo.registrar_fallback(MOTIVO_TIMEOUT, 2)
        assert telemetria_resumo.total() == 5
        assert telemetria_resumo.total("rotulo-que-nao-existe") == 0
        assert telemetria_resumo.total(None) == 5

    def test_motivos_conhecidos_expoe_o_conjunto_fechado_de_rotulos(self):
        for motivo in (
            MOTIVO_SEM_CREDENCIAL,
            MOTIVO_TIMEOUT,
            MOTIVO_ERRO_HTTP,
            MOTIVO_RATE_LIMIT,
            MOTIVO_CONTEUDO_INSUFICIENTE,
        ):
            assert motivo in telemetria_resumo.motivos_conhecidos()

    def test_painel_expoe_a_metrica_duravel_de_fallback_derivada_do_banco(self, client, django_user_model):
        """
        A leitura DURAVEL do painel vem do marcador persistido em
        `NewsItem.tags` (sobrevive a reinicio), nao do contador em memoria.
        """
        from metricas import services as metricas_services

        _roda_ingestao(LLMHttpSummarizationProvider(api_key=""))
        telemetria_resumo.zerar()  # zera so o contador: o banco continua

        painel = metricas_services.painel(30)
        ingestao = painel["kpis"]["ingestao"]
        assert ingestao["noticias_resumo_fallback_local"] == 1
        assert ingestao["taxa_resumo_fallback_local"] == 1.0
        assert ingestao["resumo_fallback_local_por_motivo"] == {MOTIVO_SEM_CREDENCIAL: 1}

    def test_painel_nao_confunde_item_normal_com_item_de_fallback(self):
        """Um item do provedor NAO pode inflar a contagem de fallback."""
        from metricas import services as metricas_services

        provider = LLMHttpSummarizationProvider(api_key=CHAVE_FICTICIA)
        with patch(
            _ALVO_POST,
            return_value=_resposta_http(_resposta_lote([(1, "Resumo autoral.", "geral")])),
        ):
            _roda_ingestao(provider)

        ingestao = metricas_services.painel(30)["kpis"]["ingestao"]
        assert ingestao["noticias_resumo_fallback_local"] == 0
        assert ingestao["taxa_resumo_fallback_local"] == 0.0
        assert ingestao["resumo_fallback_local_por_motivo"] == {}

    def test_painel_conta_a_taxa_sobre_o_acervo_inteiro_e_agrupa_por_motivo(self):
        """1 fallback entre 2 itens -> 0.5; e o agrupamento por motivo."""
        from metricas import services as metricas_services

        _roda_ingestao(
            LLMHttpSummarizationProvider(api_key=""),
            itens=[
                _item(url="https://g1/noticia/p1"),
                _item(url="https://g1/noticia/p2"),
            ],
        )
        ingestao = metricas_services.painel(30)["kpis"]["ingestao"]
        assert ingestao["noticias_resumo_fallback_local"] == 2
        assert ingestao["taxa_resumo_fallback_local"] == 1.0
        assert ingestao["resumo_fallback_local_por_motivo"] == {MOTIVO_SEM_CREDENCIAL: 2}

    def test_painel_sobrevive_a_falha_da_metrica_de_fallback(self, monkeypatch):
        """
        `painel()` nao pode levantar por causa da metrica nova — o mesmo
        padrao defensive (`try/except`) que o resto do modulo ja usava. Um
        `NameError` aqui derrubaria o painel inteiro de observabilidade.
        """
        from metricas import services as metricas_services

        _roda_ingestao(LLMHttpSummarizationProvider(api_key=""))

        def _explode(*args, **kwargs):
            raise RuntimeError("falha simulada")

        # Quebra DENTRO do bloco try da metrica nova (a contagem por motivo).
        monkeypatch.setattr(metricas_services, "motivo_fallback_local", _explode)
        ingestao = metricas_services.painel(30)["kpis"]["ingestao"]
        assert ingestao["taxa_resumo_fallback_local"] == 0.0
        assert ingestao["noticias_resumo_fallback_local"] == 0
        assert ingestao["resumo_fallback_local_por_motivo"] == {}

    def test_painel_devolve_metricas_neutras_quando_o_acervo_inteiro_falha(self, monkeypatch):
        """
        Cobre o ramo em que `total_noticias` fica indisponivel (inclusive o
        `NameError` classico de variavel nao inicializada): a metrica nova
        precisa devolver 0.0, nunca derrubar o painel.
        """
        from metricas import services as metricas_services

        def _explode(*args, **kwargs):
            raise RuntimeError("falha simulada de banco")

        class _NewsItemIndisponivel:
            """Dublê que faz TODA consulta a `NewsItem` falhar."""

            class objects:
                @staticmethod
                def count(*args, **kwargs):
                    return _explode()

                @staticmethod
                def filter(*args, **kwargs):
                    return _explode()

                @staticmethod
                def all(*args, **kwargs):
                    return _explode()

        monkeypatch.setattr(metricas_services, "NewsItem", _NewsItemIndisponivel)
        ingestao = metricas_services.painel(30)["kpis"]["ingestao"]
        assert ingestao["taxa_resumo_fallback_local"] == 0.0
        assert ingestao["noticias_resumo_fallback_local"] == 0
        assert ingestao["resumo_fallback_local_por_motivo"] == {}


class TestLog:
    def test_log_do_fallback_traz_o_motivo(self, caplog):
        with caplog.at_level(logging.INFO, logger="catalogo_noticias.services.telemetria_resumo"):
            _roda_ingestao(LLMHttpSummarizationProvider(api_key=""))
        mensagens = [registro.getMessage() for registro in caplog.records]
        assert any("resultado=fallback" in m for m in mensagens)
        assert any(f"motivo={MOTIVO_SEM_CREDENCIAL}" in m for m in mensagens)

    def test_log_do_timeout_traz_o_motivo_e_a_excecao(self, caplog):
        """O motivo E a excecao, sem a credencial e sem o corpo da resposta."""
        provider = LLMHttpSummarizationProvider(api_key=CHAVE_FICTICIA)
        with caplog.at_level(logging.INFO):
            with patch(_ALVO_POST, side_effect=requests.Timeout("prazo estourado")):
                _roda_ingestao(provider)

        mensagens = [registro.getMessage() for registro in caplog.records]
        assert any(f"motivo={MOTIVO_TIMEOUT}" in m for m in mensagens)
        assert any("SummarizationProvider falhou" in m and "Timeout" in m for m in mensagens)

    def test_log_nao_contem_o_valor_da_credencial(self, caplog):
        """
        Segredo em log eIncident de seguranca. Este teste existe para travar
        esse invariante: qualquerrotulo novo de erro/log tem de continuar sem
        credencial.
        """
        provider = LLMHttpSummarizationProvider(api_key=CHAVE_FICTICIA)
        cenarios = [
            {"side_effect": requests.Timeout("prazo")},
            {"side_effect": requests.ConnectionError("recusada")},
            {"return_value": _resposta_http("{}", status_code=401)},
            {"return_value": _resposta_http("{}", status_code=429)},
            {"return_value": _resposta_http("conteudo-inline-secreto-do-provedor")},
        ]
        with caplog.at_level(logging.DEBUG):
            for cenario in cenarios:
                with patch(_ALVO_POST, **cenario):
                    _roda_ingestao(provider, itens=[_item(url=f"https://g1/x{id(cenario)}")])

        assert caplog.records, "os cenarios deveriam ter produzido log"
        texto = "\n".join(registro.getMessage() for registro in caplog.records)
        assert CHAVE_FICTICIA not in texto
        # E o corpo da resposta do provedor tambem nao e logado integralmente.
        assert "conteudo-inline-secreto-do-provedor" not in texto

    def test_log_nao_contem_o_valor_da_credencial_quando_o_teto_de_gasto_bloqueia(self, caplog):
        provider = LLMHttpSummarizationProvider(api_key=CHAVE_FICTICIA)
        from catalogo_noticias.models import RegistroExecucaoIngestao

        RegistroExecucaoIngestao.objects.create(custo_estimado_summarization_usd=999.0)
        with caplog.at_level(logging.DEBUG):
            _roda_ingestao(provider)

        texto = "\n".join(registro.getMessage() for registro in caplog.records)
        assert CHAVE_FICTICIA not in texto


class TestMarcadorDeOrigem:
    def test_item_persistido_carrega_o_marcador_de_fallback(self):
        _roda_ingestao(LLMHttpSummarizationProvider(api_key=""))
        item = NewsItem.objects.get()
        assert TAG_ORIGEM_FALLBACK in item.tags
        assert origem_fallback_local(item.tags) is True
        assert motivo_fallback_local(item.tags) == MOTIVO_SEM_CREDENCIAL

    def test_item_do_provedor_nao_carrega_marcador_de_fallback(self):
        provider = LLMHttpSummarizationProvider(api_key=CHAVE_FICTICIA)
        with patch(
            _ALVO_POST,
            return_value=_resposta_http(_resposta_lote([(1, "Resumo autoral.", "geral")])),
        ):
            _roda_ingestao(provider)

        item = NewsItem.objects.get()
        assert origem_fallback_local(item.tags) is False
        assert motivo_fallback_local(item.tags) == ""
        assert not any(eh_tag_tecnica(tag) for tag in item.tags)

    def test_marcador_usa_prefixo_reservado_e_motivo_conhecido(self):
        tags = marcadores_tags(MOTIVO_TIMEOUT)
        assert tags[0] == TAG_ORIGEM_FALLBACK
        assert all(eh_tag_tecnica(tag) for tag in tags)
        assert motivo_fallback_local(tags) == MOTIVO_TIMEOUT

    def test_marcador_esta_exposto_na_fila_editorial(self, client, django_user_model):
        """O editorial precisa ver, na fila, o que veio do fallback e por que."""
        _roda_ingestao(LLMHttpSummarizationProvider(api_key=""))

        admin = django_user_model.objects.create_user(
            email="admin-fallback@p102.test", password="x", papel="admin", is_active=True
        )
        admin.set_password("x")
        admin.save()
        client.force_login(admin)
        resposta = client.get("/api/admin/fila/?status=nao_aplicavel")
        assert resposta.status_code == 200
        itens = resposta.json()["results"]
        assert len(itens) == 1
        assert itens[0]["resumo_fallback_local"] is True
        assert itens[0]["motivo_fallback_resumo"] == MOTIVO_SEM_CREDENCIAL

    def test_marcador_tecnico_nao_influencia_a_relevancia_da_busca(self):
        """
        Um marcador interno de pipeline nao pode virar sinal de busca: o
        token "local" casaria com "p1-02:origem_resumo_fallback_local" e
        inflaria a pontuacao de toda noticia degradada.
        """
        from feed.busca import _relevancia

        item = NewsItem.objects.create(
            titulo="Assunto qualquer",
            url_fonte_original="https://g1/busca/1",
            nome_fonte="G1",
            resumo_proprio="texto",
            tags=[TAG_ORIGEM_FALLBACK, "eleicoes"],
        )
        sem_marcador = NewsItem.objects.create(
            titulo="Assunto qualquer",
            url_fonte_original="https://g1/busca/2",
            nome_fonte="G1",
            resumo_proprio="texto",
            tags=["eleicoes"],
        )
        # A busca por "local" nao pode pontuar o item por causa do marcador.
        assert _relevancia(item, "local", ["local"])[0] == _relevancia(
            sem_marcador, "local", ["local"]
        )[0]
        # ...mas a tag editorial legitima continua pontuando.
        assert _relevancia(item, "eleicoes", ["eleicoes"])[0] > 0


# ===========================================================================
# Contrato do provider (regressao do que ja existia)
# ===========================================================================


class TestContratoDoProvider:
    def test_resposta_malformada_ainda_levanta_summarizationprovidererror(self):
        """O contrato de levantar a excecao (teste preexistente) foi preservado."""
        provider = LLMHttpSummarizationProvider(api_key=CHAVE_FICTICIA)
        with patch(_ALVO_POST, return_value=_resposta_http("formato invalido")):
            with pytest.raises(SummarizationProviderError) as erro:
                provider.resumir_e_classificar_em_lote([_item()])
        assert erro.value.motivo == "resposta_invalida"

    def test_erro_carrega_o_motivo_classificado(self):
        provider = LLMHttpSummarizationProvider(api_key=CHAVE_FICTICIA)
        with patch(_ALVO_POST, side_effect=requests.Timeout("prazo")):
            with pytest.raises(SummarizationProviderError) as erro:
                provider.resumir_e_classificar([_item()])
        assert erro.value.motivo == MOTIVO_TIMEOUT

    def test_summarizationprovidererror_sem_motivo_mantem_o_contrato_antigo(self):
        """Dubles de terceiros levantam sem `motivo=`; continua funcionando."""
        erro = SummarizationProviderError("mensagem qualquer")
        assert str(erro) == "mensagem qualquer"
        assert erro.motivo == ""

    def test_lote_vazio_nao_faz_chamada_http(self):
        provider = LLMHttpSummarizationProvider(api_key=CHAVE_FICTICIA)
        with patch(_ALVO_POST) as mock_post:
            assert provider.resumir_e_classificar_em_lote([]) == []
        mock_post.assert_not_called()

    def test_resumir_e_classificar_sem_itens_levanta_valueerror(self):
        provider = LLMHttpSummarizationProvider(api_key=CHAVE_FICTICIA)
        with pytest.raises(ValueError):
            provider.resumir_e_classificar([])

    def test_resultado_resumo_marcado_como_fallback_e_ignorado_quando_falso(self):
        """`ResultadoResumo` novo: campos com default, retrocompativel."""
        resultado = ResultadoResumo(resumo="x", categoria="geral", urgente=False)
        assert resultado.fallback is False
        assert resultado.motivo_fallback == ""

    def test_estimar_custo_e_zero_sem_credencial(self):
        assert LLMHttpSummarizationProvider(api_key="").estimar_custo_em_lote(10) == 0.0
