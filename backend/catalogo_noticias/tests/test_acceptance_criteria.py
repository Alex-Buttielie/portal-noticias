"""
Suite formal do `tester` — cobre explicitamente cada um dos 7 critérios de
aceite de `implementation-contract.md` (run-20260902-0727-ingestao-noticias).
Cada classe de teste referencia o número do critério ("AC-N") no nome, para
rastreabilidade.

Esta suíte é independente de `catalogo_noticias/tests/test_sanity.py`
(escrita pelo executor apenas para autovalidação durante o desenvolvimento):
não reaproveita os dublês do executor, usa cenários de borda adicionais
(falha real de rede/HTTP/parsing via `RSSNewsSourceProvider` mockado no nível
de `requests.get`, bypass de `save()` via `bulk_create`, provider de resumo
mal-comportado que devolve uma cópia literal do bruto) e, no caso do AC-4,
inclui deliberadamente um teste que expõe um cenário adversarial em vez de
apenas confirmar o caminho feliz.

Nenhum teste faz chamada de rede real: `requests.get`/`SummarizationProvider`
são sempre mockados/dublês.
"""

from __future__ import annotations

from datetime import timedelta
from difflib import SequenceMatcher
from unittest.mock import MagicMock, patch

import pytest
import requests
from django.db import IntegrityError
from django.core.exceptions import ValidationError
from django.test import override_settings
from django.utils import timezone

from catalogo_noticias.models import NewsCluster, NewsItem, RegistroExecucaoIngestao
from catalogo_noticias.providers.news_source import (
    FonteIndisponivelError,
    ItemBruto,
    NewsSourceProvider,
    RSSNewsSourceProvider,
)
from catalogo_noticias.providers.summarization import ResultadoResumo, SummarizationProvider
from catalogo_noticias.services.deduplicacao import agrupar_itens_brutos
from catalogo_noticias.services.ingestao import executar_ingestao

pytestmark = pytest.mark.django_db


# ---------------------------------------------------------------------------
# Dublês genéricos (independentes dos usados em test_sanity.py)
# ---------------------------------------------------------------------------


class FonteDeTeste(NewsSourceProvider):
    def __init__(self, nome_fonte, itens=None, erro=None):
        self.nome_fonte = nome_fonte
        self._itens = itens or []
        self._erro = erro

    def buscar_itens(self):
        if self._erro is not None:
            raise self._erro
        return self._itens


class ProviderResumoGenuino(SummarizationProvider):
    """Dublê 'bem comportado': sempre produz um resumo textualmente diferente do bruto."""

    def __init__(self, categoria="geral", urgente=False):
        self.categoria = categoria
        self.urgente = urgente
        self.chamadas = 0
        self.ultimo_grupo_tamanho = 0

    def resumir_e_classificar(self, itens_brutos):
        self.chamadas += 1
        self.ultimo_grupo_tamanho = len(itens_brutos)
        return ResultadoResumo(
            resumo=(
                f"Sintese jornalistica autoral sobre o acontecimento relatado por "
                f"{len(itens_brutos)} fonte(s); ver apuracao completa nas fontes originais."
            ),
            categoria=self.categoria,
            urgente=self.urgente,
            tokens_utilizados=17,
            custo_estimado_usd=0.0005,
        )


def _item(titulo, nome_fonte, url, conteudo="Texto bruto original ingerido da materia jornalistica.", categoria=""):
    return ItemBruto(
        titulo=titulo,
        url_fonte_original=url,
        nome_fonte=nome_fonte,
        conteudo_bruto=conteudo,
        categoria=categoria,
    )


def _rss_bytes(titulo: str, link: str, descricao: str) -> bytes:
    return (
        "<?xml version=\"1.0\"?><rss version=\"2.0\"><channel><title>Feed</title>"
        f"<item><title>{titulo}</title><link>{link}</link><description>{descricao}</description></item>"
        "</channel></rss>"
    ).encode("utf-8")


# ===========================================================================
# AC-1: falha real de UMA fonte (timeout/HTTP 500/parsing) não impede as
# demais; erro registrado, não propagado como exceção fatal da task inteira.
# ===========================================================================


class TestAC1ResilienciaDeFontes:
    def test_timeout_de_rede_gera_fonteindisponivelerror_nao_excecao_generica(self):
        provider = RSSNewsSourceProvider(nome_fonte="CNN Brasil", url_feed="https://cnn/feed")
        with patch(
            "catalogo_noticias.providers.news_source.requests.get",
            side_effect=requests.exceptions.Timeout("timed out"),
        ):
            with pytest.raises(FonteIndisponivelError):
                provider.buscar_itens()

    def test_http_500_gera_fonteindisponivelerror(self):
        provider = RSSNewsSourceProvider(nome_fonte="G1", url_feed="https://g1/feed")
        resposta = MagicMock()
        resposta.raise_for_status.side_effect = requests.exceptions.HTTPError("500 Server Error")
        with patch("catalogo_noticias.providers.news_source.requests.get", return_value=resposta):
            with pytest.raises(FonteIndisponivelError):
                provider.buscar_itens()

    def test_feed_malformado_sem_entries_gera_fonteindisponivelerror(self):
        provider = RSSNewsSourceProvider(nome_fonte="UOL", url_feed="https://uol/feed")
        resposta = MagicMock()
        resposta.raise_for_status.side_effect = None
        resposta.content = b"isto definitivamente nao e um XML valido <<<"
        with patch("catalogo_noticias.providers.news_source.requests.get", return_value=resposta):
            with pytest.raises(FonteIndisponivelError):
                provider.buscar_itens()

    def test_pipeline_completo_com_4_fontes_uma_falhando_por_timeout_real(self):
        """
        Simula as 4 fontes-semente reais via `RSSNewsSourceProvider`
        (não via um dublê de alto nível que já pré-fabrica a exceção) — uma
        delas falha por timeout de rede simulado em `requests.get`, as
        outras 3 respondem com um feed RSS válido. Confirma que o pipeline
        inteiro (`executar_ingestao`) processa as 3 fontes saudáveis e
        registra (não propaga) o erro da 4a.
        """
        fontes = [
            RSSNewsSourceProvider(nome_fonte="G1", url_feed="https://g1/feed"),
            RSSNewsSourceProvider(nome_fonte="UOL", url_feed="https://uol/feed"),
            RSSNewsSourceProvider(nome_fonte="CNN Brasil", url_feed="https://cnn/feed"),
            RSSNewsSourceProvider(nome_fonte="Folha", url_feed="https://folha/feed"),
        ]

        conteudo_por_url = {
            "https://g1/feed": _rss_bytes("Chuvas atingem regiao sul", "https://g1/n1", "Texto G1."),
            "https://uol/feed": _rss_bytes("Selecao vence amistoso", "https://uol/n1", "Texto UOL."),
            "https://folha/feed": _rss_bytes("Novo aeroporto e inaugurado", "https://folha/n1", "Texto Folha."),
        }

        def fake_get(url, timeout=None, headers=None):
            if url == "https://cnn/feed":
                raise requests.exceptions.Timeout("timeout simulado da fonte CNN Brasil")
            resposta = MagicMock()
            resposta.raise_for_status.side_effect = None
            resposta.content = conteudo_por_url[url]
            return resposta

        with patch("catalogo_noticias.providers.news_source.requests.get", side_effect=fake_get):
            registro = executar_ingestao(fontes=fontes, summarization_provider=ProviderResumoGenuino())

        assert "CNN Brasil" in registro.erros_por_fonte
        assert registro.itens_por_fonte["CNN Brasil"] == 0
        assert registro.itens_por_fonte["G1"] == 1
        assert registro.itens_por_fonte["UOL"] == 1
        assert registro.itens_por_fonte["Folha"] == 1
        # os itens das 3 fontes saudaveis foram de fato persistidos, nao so contados
        assert NewsItem.objects.count() == 3
        assert not NewsItem.objects.filter(nome_fonte="CNN Brasil").exists()

    def test_excecao_inesperada_nao_documentada_tambem_nao_derruba_as_demais_fontes(self):
        """
        Além de `FonteIndisponivelError`, uma exceção genuinamente
        inesperada (ex.: bug em uma implementação futura de
        `NewsSourceProvider`) também não pode propagar como falha fatal da
        task — o contrato pede "não impede que as demais sejam
        processadas" de forma ampla, não só para o tipo de erro esperado.
        """
        fontes = [
            FonteDeTeste("G1", itens=[_item("Noticia G1", "G1", "https://g1/x")]),
            FonteDeTeste("Fonte Bugada", erro=RuntimeError("bug interno inesperado do provider")),
            FonteDeTeste("UOL", itens=[_item("Noticia UOL", "UOL", "https://uol/x")]),
        ]

        registro = executar_ingestao(fontes=fontes, summarization_provider=ProviderResumoGenuino())

        assert "Fonte Bugada" in registro.erros_por_fonte
        assert NewsItem.objects.count() == 2


# ===========================================================================
# AC-2: itens de fontes diferentes sobre o mesmo acontecimento -> mesmo
# NewsCluster.
# ===========================================================================


class TestAC2DeduplicacaoEAgrupamento:
    def test_tres_fontes_sobre_mesmo_acontecimento_formam_um_unico_cluster(self):
        fontes = [
            FonteDeTeste("G1", itens=[_item("Presidente sanciona novo pacote fiscal", "G1", "https://g1/fiscal")]),
            FonteDeTeste(
                "UOL", itens=[_item("Presidente sanciona pacote fiscal anunciado ontem", "UOL", "https://uol/fiscal")]
            ),
            FonteDeTeste(
                "CNN Brasil",
                itens=[_item("Pacote fiscal e sancionado pelo presidente", "CNN Brasil", "https://cnn/fiscal")],
            ),
        ]

        executar_ingestao(fontes=fontes, summarization_provider=ProviderResumoGenuino())

        assert NewsCluster.objects.count() == 1
        cluster = NewsCluster.objects.get()
        assert cluster.itens.count() == 3
        assert cluster.numero_fontes_distintas == 3

    def test_acontecimentos_diferentes_nao_sao_agrupados_no_mesmo_cluster(self):
        fontes = [
            FonteDeTeste("G1", itens=[_item("Selecao vence amistoso na Europa", "G1", "https://g1/futebol")]),
            FonteDeTeste("UOL", itens=[_item("Banco Central mantem taxa de juros", "UOL", "https://uol/juros")]),
        ]

        registro = executar_ingestao(fontes=fontes, summarization_provider=ProviderResumoGenuino())

        assert NewsCluster.objects.count() == 0
        assert registro.total_grupos_formados == 2
        assert registro.total_duplicatas_agrupadas == 0
        assert all(item.cluster is None for item in NewsItem.objects.all())

    def test_summarization_provider_e_chamado_uma_vez_por_item_nao_uma_vez_por_cluster(self):
        """
        REVERTIDO (code-review-contract.md run 20260902-0727-ingestao-noticias,
        3a passada, Finding 1, major — mudanca de estrategia): a decisao
        tecnica original (implementation-history.md, decisao tecnica 2 do
        executor — uma chamada por grupo/cluster, compartilhando
        `resumo_proprio` entre todos os itens do cluster) foi revertida
        porque criava um risco estrutural de misattribution (BRD secao 18)
        sempre que o algoritmo de deduplicacao (heuristica de similaridade de
        titulo, nunca uma garantia) agrupasse itens que na verdade sao sobre
        fatos diferentes — ver `TestFinding2FalsoPositivoPorPadraoSintaticoComum`
        e `TestFinding1FalsoPositivoEmLotesPequenosReaberto` para casos reais
        disso acontecendo com vocabulario diferente a cada rodada de revisao.

        A partir desta correcao, o `SummarizationProvider` e chamado UMA VEZ
        POR ITEM, sempre — mesmo quando varios itens formam um `NewsCluster`
        (util para a experiencia do usuario), cada `NewsItem` tem seu PROPRIO
        `resumo_proprio`, gerado exclusivamente a partir do seu PROPRIO
        `conteudo_bruto`. Custo (AC-6) sobe proporcionalmente ao numero de
        itens em vez de ao numero de clusters — tradeoff deliberado, aceito
        porque a correcao/compliance foi explicitamente priorizada sobre
        custo pelo `implementation-contract.md` ("bug bloqueante, nao
        estetico").
        """
        fontes = [
            FonteDeTeste("G1", itens=[_item("Novo aeroporto e inaugurado na capital", "G1", "https://g1/aero")]),
            FonteDeTeste(
                "UOL", itens=[_item("Aeroporto novo e inaugurado na capital do estado", "UOL", "https://uol/aero")]
            ),
        ]
        provider = ProviderResumoGenuino()

        executar_ingestao(fontes=fontes, summarization_provider=provider)

        assert provider.chamadas == 2
        assert provider.ultimo_grupo_tamanho == 1
        # Mesmo pertencendo ao MESMO NewsCluster (a deduplicacao continua
        # funcionando para fins de exibicao), os dois itens tem resumo_proprio
        # gerado de forma independente — nao ha mais UM resultado
        # compartilhado aplicado aos dois.
        itens = list(NewsItem.objects.all())
        assert NewsCluster.objects.count() == 1
        assert {item.cluster_id for item in itens} == {NewsCluster.objects.get().id}

    def test_agrupar_itens_brutos_e_pura_e_nao_toca_banco(self):
        itens = [
            _item("Chuva forte causa alagamentos em SP", "G1", "https://g1/chuva"),
            _item("Alagamentos em SP apos chuva forte", "UOL", "https://uol/chuva"),
            _item("Novo filme bate recorde de bilheteria", "CNN Brasil", "https://cnn/filme"),
        ]
        grupos = agrupar_itens_brutos(itens, limiar_similaridade=0.5)
        assert NewsItem.objects.count() == 0  # nenhuma escrita no banco
        assert sorted(len(g) for g in grupos) == [1, 2]


# ===========================================================================
# Finding 2 (code-review-contract.md run 20260902-0727-ingestao-noticias,
# major): manchetes que compartilham o MESMO padrao sintatico jornalistico
# ("<Orgao> anuncia/investiga <algo> ...") mas descrevem fatos DIFERENTES
# nao podem virar o mesmo NewsCluster so por causa da estrutura compartilhada
# — a heuristica anterior (`max(jaccard, SequenceMatcher sobre tokens
# ordenados)`) confundia esses casos, causando misattribution de conteudo
# (BRD secao 18): um NewsItem cuja fonte fala de "mobilidade urbana" acabava
# com resumo_proprio sobre "seguranca publica" (ou vice-versa), porque
# `_persistir_grupo` usa um unico resumo por cluster.
#
# Os 3 pares abaixo sao os do reviewer. Isolar so o par (sem outros itens de
# contexto no lote) nao fornece sinal suficiente para NENHUMA heuristica
# baseada em frequencia-no-lote (ver `services/deduplicacao.py`); por isso
# o teste usa um lote maior e mais realista (15 itens, incluindo variacoes
# do mesmo "molde" sintatico com assuntos diferentes — o cenario onde a
# heuristica antiga falhava — e um par genuinamente duplicado, para provar
# que a correcao nao vira so "nunca mais agrupa nada").
# ===========================================================================


class TestFinding2FalsoPositivoPorPadraoSintaticoComum:
    def _lote_realista_com_falsos_positivos_do_reviewer(self):
        return [
            _item(
                "Prefeitura de São Paulo anuncia novo plano de segurança pública",
                "G1",
                "https://g1/seguranca-publica",
            ),
            _item(
                "Prefeitura de São Paulo anuncia novo plano de mobilidade urbana",
                "UOL",
                "https://uol/mobilidade-urbana",
            ),
            _item(
                "Governo anuncia pacote de medidas econômicas para pequenas empresas",
                "G1",
                "https://g1/medidas-economicas",
            ),
            _item(
                "Governo anuncia pacote de medidas educacionais para pequenas escolas",
                "UOL",
                "https://uol/medidas-educacionais",
            ),
            _item(
                "Polícia investiga homicídio em bairro nobre de São Paulo",
                "G1",
                "https://g1/homicidio",
            ),
            _item(
                "Polícia investiga fraude fiscal em empresa de São Paulo",
                "UOL",
                "https://uol/fraude-fiscal",
            ),
            # itens de contexto adicionais — reforcam, via repeticao real no
            # lote, que "prefeitura anuncia novo plano de", "governo anuncia
            # pacote de medidas" e "policia investiga" sao linguagem de
            # molde comum a VARIOS acontecimentos diferentes deste lote, nao
            # so do par sendo comparado.
            _item(
                "Prefeitura do Rio anuncia novo plano de habitação popular",
                "CNN Brasil",
                "https://cnn/habitacao",
            ),
            _item(
                "Governo anuncia pacote de medidas trabalhistas para autônomos",
                "CNN Brasil",
                "https://cnn/medidas-trabalhistas",
            ),
            _item(
                "Polícia investiga esquema de contrabando na fronteira",
                "Folha",
                "https://folha/contrabando",
            ),
            _item(
                "Prefeitura de Salvador anuncia novo plano de saneamento básico",
                "Folha",
                "https://folha/saneamento",
            ),
            _item(
                "Governo anuncia pacote de medidas ambientais para o Cerrado",
                "G1",
                "https://g1/medidas-ambientais",
            ),
            _item(
                "Polícia investiga rede de furtos em bairro central",
                "UOL",
                "https://uol/furtos",
            ),
            _item(
                "Seleção brasileira estreia na Copa do Mundo",
                "CNN Brasil",
                "https://cnn/copa-do-mundo",
            ),
            # par genuinamente duplicado no MESMO lote — prova que a correcao
            # nao degenera em "nunca mais agrupa nada".
            _item(
                "Banco Central eleva taxa de juros para 12%",
                "G1",
                "https://g1/juros-finding2",
            ),
            _item(
                "Banco Central eleva taxa de juros a 12% ao ano",
                "UOL",
                "https://uol/juros-finding2",
            ),
        ]

    def test_pares_com_padrao_sintatico_comum_mas_assunto_diferente_nao_formam_o_mesmo_grupo(self):
        itens = self._lote_realista_com_falsos_positivos_do_reviewer()

        grupos = agrupar_itens_brutos(
            itens, limiar_similaridade=0.55
        )  # 0.55 == CATALOGO_NOTICIAS_DEDUP_LIMIAR_SIMILARIDADE default

        def grupo_de(url: str) -> int:
            for indice, grupo in enumerate(grupos):
                if any(item.url_fonte_original == url for item in grupo):
                    return indice
            raise AssertionError(f"URL {url} nao apareceu em nenhum grupo")

        # os 3 pares do reviewer: mesmo "molde" sintatico, assunto diferente
        # -> grupos DIFERENTES (nao viram o mesmo NewsCluster).
        assert grupo_de("https://g1/seguranca-publica") != grupo_de("https://uol/mobilidade-urbana")
        assert grupo_de("https://g1/medidas-economicas") != grupo_de("https://uol/medidas-educacionais")
        assert grupo_de("https://g1/homicidio") != grupo_de("https://uol/fraude-fiscal")

        # controle: um par GENUINAMENTE duplicado no mesmo lote continua
        # formando um unico grupo — a correcao do Finding 2 nao "quebra"
        # deduplicacao real ao custo de nunca mais agrupar nada.
        assert grupo_de("https://g1/juros-finding2") == grupo_de("https://uol/juros-finding2")

    def test_pares_com_padrao_sintatico_comum_ponta_a_ponta_via_executar_ingestao_nao_compartilham_cluster(self):
        """
        Mesmo cenario, mas ponta a ponta via `executar_ingestao` (nao so a
        funcao pura de agrupamento): confirma que, na pratica, os NewsItem
        persistidos para os 3 pares do reviewer NAO acabam com o mesmo
        `cluster` (o que causaria misattribution de `resumo_proprio` — BRD
        secao 18 — ja que `_persistir_grupo` usa um unico resumo por
        cluster).
        """
        itens = self._lote_realista_com_falsos_positivos_do_reviewer()
        agrupados_por_fonte: dict[str, list] = {}
        for item_bruto in itens:
            agrupados_por_fonte.setdefault(item_bruto.nome_fonte, []).append(item_bruto)
        fontes = [FonteDeTeste(nome, itens=grupo) for nome, grupo in agrupados_por_fonte.items()]

        executar_ingestao(fontes=fontes, summarization_provider=ProviderResumoGenuino())

        def mesmo_cluster(url_a: str, url_b: str) -> bool:
            cluster_a = NewsItem.objects.get(url_fonte_original=url_a).cluster_id
            cluster_b = NewsItem.objects.get(url_fonte_original=url_b).cluster_id
            # cluster_id=None significa "sem cobertura duplicada encontrada"
            # (item standalone) — dois itens standalone NUNCA compartilham
            # cobertura, mesmo com cluster_id igual (None == None).
            return cluster_a is not None and cluster_a == cluster_b

        assert not mesmo_cluster("https://g1/seguranca-publica", "https://uol/mobilidade-urbana")
        assert not mesmo_cluster("https://g1/medidas-economicas", "https://uol/medidas-educacionais")
        assert not mesmo_cluster("https://g1/homicidio", "https://uol/fraude-fiscal")

        def cluster_de(url: str):
            return NewsItem.objects.get(url_fonte_original=url).cluster_id

        # controle: o par genuinamente duplicado continua no mesmo cluster.
        cluster_juros = cluster_de("https://g1/juros-finding2")
        assert cluster_juros is not None
        assert cluster_juros == cluster_de("https://uol/juros-finding2")


# ===========================================================================
# Finding 1 REABERTO (code-review-contract.md run 20260902-0727-ingestao-noticias,
# 2a passada, major): a correcao acima (`TestFinding2FalsoPositivoPorPadraoSintaticoComum`)
# so neutraliza o falso-positivo em lotes >= 6 itens com o padrao repetido
# >= 4 vezes (o mecanismo DINAMICO de `_pesos_por_frequencia_no_lote`). O
# reviewer reproduziu, de forma independente, que em um lote PEQUENO e
# REALISTA (4 itens — as 4 fontes-semente do contrato rodando por ciclo de
# 15 min) o falso-positivo original volta a ocorrer, porque o sinal dinamico
# nunca tem dados suficientes para ativar.
#
# A correcao desta rodada complementa o mecanismo dinamico com uma lista
# curada de conectores jornalisticos comuns em portugues (peso reduzido
# INCONDICIONALMENTE, ver `_CONECTORES_JORNALISTICOS_COMUNS_PT` em
# services/deduplicacao.py). Os testes abaixo usam VARIOS lotes pequenos
# (2 a 5 itens) e VARIADOS — nao so o exato cenario relatado pelo reviewer —
# para evitar uma correcao que so funciona para o caso de teste especifico.
# ===========================================================================


class TestFinding1FalsoPositivoEmLotesPequenosReaberto:
    def test_cenario_exato_do_reviewer_lote_de_4_itens_com_4_fontes_semente(self):
        """
        Reproducao literal do cenario do Finding 1 reaberto (2a passada):
        lote de 4 itens, plausivel para um unico ciclo de 15 min com as 4
        fontes-semente do contrato (task-plan.md) — G1/UOL cobrindo
        acontecimentos DIFERENTES com o mesmo molde sintatico
        ("Prefeitura ... anuncia novo plano de X"), mais 2 itens de fontes
        nao relacionadas (CNN Brasil, Folha).
        """
        itens = [
            _item(
                "Prefeitura de Sao Paulo anuncia novo plano de seguranca publica",
                "G1",
                "https://g1/seg-publica-reaberto",
            ),
            _item(
                "Prefeitura de Sao Paulo anuncia novo plano de mobilidade urbana",
                "UOL",
                "https://uol/mobilidade-reaberto",
            ),
            _item(
                "Selecao brasileira vence amistoso por 2 a 0",
                "CNN Brasil",
                "https://cnn/futebol-reaberto",
            ),
            _item(
                "Dolar fecha em alta nesta quinta-feira",
                "Folha",
                "https://folha/dolar-reaberto",
            ),
        ]

        grupos = agrupar_itens_brutos(itens, limiar_similaridade=0.55)

        tamanhos = sorted(len(g) for g in grupos)
        assert tamanhos == [1, 1, 1, 1], (
            "os 2 itens sobre 'plano de seguranca publica' vs. 'plano de "
            "mobilidade urbana' NAO podem cair no mesmo grupo mesmo em um "
            "lote pequeno de 4 itens — misattribution de conteudo (BRD "
            f"secao 18). Grupos obtidos: {[[i.titulo for i in g] for g in grupos]}"
        )

    def test_cenario_exato_do_reviewer_ponta_a_ponta_via_executar_ingestao(self):
        itens = [
            _item(
                "Prefeitura de Sao Paulo anuncia novo plano de seguranca publica",
                "G1",
                "https://g1/seg-publica-e2e",
            ),
            _item(
                "Prefeitura de Sao Paulo anuncia novo plano de mobilidade urbana",
                "UOL",
                "https://uol/mobilidade-e2e",
            ),
            _item(
                "Selecao brasileira vence amistoso por 2 a 0",
                "CNN Brasil",
                "https://cnn/futebol-e2e",
            ),
            _item(
                "Dolar fecha em alta nesta quinta-feira",
                "Folha",
                "https://folha/dolar-e2e",
            ),
        ]
        agrupados_por_fonte: dict[str, list] = {}
        for item_bruto in itens:
            agrupados_por_fonte.setdefault(item_bruto.nome_fonte, []).append(item_bruto)
        fontes = [FonteDeTeste(nome, itens=grupo) for nome, grupo in agrupados_por_fonte.items()]

        # Provider que devolve um resumo IDENTIFICAVEL por chamada — permite
        # provar que os 2 itens do "molde comum" foram resumidos
        # SEPARADAMENTE (nao com um unico resumo compartilhado indevidamente,
        # o que seria a materializacao concreta da misattribution, BRD secao
        # 18, caso a deteccao de falso-positivo tivesse falhado).
        class ProviderResumoIdentificavelPorChamada(SummarizationProvider):
            def __init__(self):
                self.chamadas = 0

            def resumir_e_classificar(self, itens_brutos):
                self.chamadas += 1
                return ResultadoResumo(
                    resumo=f"Sintese autoral (chamada {self.chamadas}) sobre: {itens_brutos[0].titulo}",
                    categoria="geral",
                    urgente=False,
                )

        provider = ProviderResumoIdentificavelPorChamada()
        executar_ingestao(fontes=fontes, summarization_provider=provider)

        item_seguranca = NewsItem.objects.get(url_fonte_original="https://g1/seg-publica-e2e")
        item_mobilidade = NewsItem.objects.get(url_fonte_original="https://uol/mobilidade-e2e")
        assert item_seguranca.cluster_id is None
        assert item_mobilidade.cluster_id is None
        # garantia final contra misattribution (BRD secao 18): os 2 itens
        # foram resumidos em chamadas SEPARADAS ao provider (nao um unico
        # resumo de grupo aplicado aos dois), com resumo_proprio distinto.
        assert provider.chamadas == 4  # 4 itens, todos standalone nesta execucao
        assert item_seguranca.resumo_proprio != item_mobilidade.resumo_proprio

    @pytest.mark.parametrize(
        "titulo_a,titulo_b,contexto",
        [
            (
                "Governo anuncia pacote de medidas economicas para pequenas empresas",
                "Governo anuncia pacote de medidas educacionais para pequenas escolas",
                ["Time local vence campeonato estadual de futebol"],
            ),
            (
                "Policia investiga homicidio em bairro nobre de Sao Paulo",
                "Policia investiga fraude fiscal em empresa de Sao Paulo",
                [],
            ),
            (
                "Ministerio da saude lanca novo programa de vacinacao infantil",
                "Ministerio da educacao lanca novo programa de bolsas de estudo",
                [
                    "Bolsa de valores fecha em queda",
                    "Chuva forte atinge litoral norte",
                    "Novo aeroporto e inaugurado na capital",
                ],
            ),
            (
                "Prefeito de Curitiba apresenta projeto de revitalizacao do centro",
                "Prefeito de Curitiba apresenta projeto de mobilidade ciclistica",
                [],
            ),
            (
                "Governo divulga novo pacote de auxilio a agricultores do sul",
                "Governo divulga novo pacote de auxilio a pescadores do nordeste",
                ["Selecao feminina de volei vence torneio internacional"],
            ),
        ],
        ids=[
            "governo-pacote-economico-vs-educacional",
            "policia-investiga-homicidio-vs-fraude",
            "ministerio-vacinacao-vs-bolsas-lote-5",
            "prefeito-revitalizacao-vs-mobilidade",
            "governo-auxilio-agricultores-vs-pescadores",
        ],
    )
    def test_variacoes_de_falso_positivo_por_molde_comum_em_lotes_pequenos_e_variados(
        self, titulo_a, titulo_b, contexto, request
    ):
        """
        Cobertura ALÉM do cenário exato do reviewer (evita corrigir só para
        o caso de teste relatado): vários outros pares de manchetes que
        compartilham conectores jornalísticos comuns diferentes
        ("pacote de medidas", "investiga", "lança programa", "apresenta
        projeto", "divulga pacote") mas descrevem fatos DIFERENTES, em
        lotes de 2 a 5 itens.
        """
        slug = request.node.callspec.id  # id determinístico do parametrize (ver `ids=` acima)
        itens = [
            _item(titulo_a, "G1", f"https://g1/fp-{slug}-a"),
            _item(titulo_b, "UOL", f"https://uol/fp-{slug}-b"),
        ] + [
            _item(t, "CNN Brasil", f"https://cnn/fp-{slug}-ctx-{i}")
            for i, t in enumerate(contexto)
        ]

        grupos = agrupar_itens_brutos(itens, limiar_similaridade=0.55)

        def grupo_de(url: str) -> int:
            for indice, grupo in enumerate(grupos):
                if any(item.url_fonte_original == url for item in grupo):
                    return indice
            raise AssertionError(f"URL {url} nao apareceu em nenhum grupo")

        assert grupo_de(itens[0].url_fonte_original) != grupo_de(itens[1].url_fonte_original)

    def test_pares_genuinos_continuam_agrupados_em_lotes_pequenos_apos_a_correcao(self):
        """
        Salvaguarda: a lista curada de conectores nao pode fazer a correcao
        degenerar em 'nunca mais agrupa nada' nos lotes pequenos (2-3 itens)
        onde o mecanismo dinamico nunca ativava mesmo — os mesmos pares
        genuinos ja cobertos por test_sanity.py/TestAC2 continuam formando
        grupo.
        """
        casos_genuinos = [
            (
                "Presidente sanciona novo pacote fiscal",
                "Presidente sanciona pacote fiscal anunciado ontem",
            ),
            (
                "Grande incendio atinge deposito industrial na zona leste",
                "Deposito na zona leste e atingido por grande incendio",
            ),
            (
                "Nova vacina e aprovada pela agencia reguladora",
                "Agencia reguladora aprova nova vacina",
            ),
        ]
        for indice, (titulo_a, titulo_b) in enumerate(casos_genuinos):
            itens = [
                _item(titulo_a, "G1", f"https://g1/genuino-{indice}"),
                _item(titulo_b, "UOL", f"https://uol/genuino-{indice}"),
            ]
            grupos = agrupar_itens_brutos(itens, limiar_similaridade=0.55)
            assert len(grupos) == 1, (
                f"par genuino '{titulo_a}' vs '{titulo_b}' deveria continuar "
                f"formando um unico grupo em lote pequeno; grupos obtidos: "
                f"{[[i.titulo for i in g] for g in grupos]}"
            )


# ===========================================================================
# AC-3: url_fonte_original/nome_fonte obrigatórios — ausência impede
# CRIAÇÃO (validação, não best-effort), em duas camadas independentes.
# ===========================================================================


class TestAC3FonteObrigatoriaEmDuasCamadas:
    def test_camada_1_save_recusa_sem_url_fonte_original(self):
        with pytest.raises(ValidationError):
            NewsItem.objects.create(titulo="Teste", url_fonte_original="", nome_fonte="G1")
        assert NewsItem.objects.count() == 0

    def test_camada_1_save_recusa_sem_nome_fonte(self):
        with pytest.raises(ValidationError):
            NewsItem.objects.create(titulo="Teste", url_fonte_original="https://g1/x", nome_fonte="")
        assert NewsItem.objects.count() == 0

    def test_camada_2_check_constraint_de_banco_recusa_mesmo_contornando_save(self):
        """
        Defesa em profundidade (implementation-history.md, decisão técnica
        9): mesmo um caminho de escrita que NÃO passa por `save()`/`clean()`
        (ex.: `bulk_create`, usado deliberadamente aqui para simular esse
        contorno) deve ser barrado pela CheckConstraint do próprio banco —
        confirmado tanto em SQLite (usado neste ambiente) quanto esperado em
        PostgreSQL (mesma sintaxe de CHECK constraint via Django ORM).
        """
        from django.db import transaction

        with pytest.raises(IntegrityError):
            with transaction.atomic():
                NewsItem.objects.bulk_create(
                    [NewsItem(titulo="Bypass de save()", url_fonte_original="", nome_fonte="G1")]
                )
        assert NewsItem.objects.count() == 0

    def test_camada_2_check_constraint_de_banco_recusa_nome_fonte_vazio_via_bulk_create(self):
        from django.db import transaction

        with pytest.raises(IntegrityError):
            with transaction.atomic():
                NewsItem.objects.bulk_create(
                    [NewsItem(titulo="Bypass de save()", url_fonte_original="https://g1/x", nome_fonte="")]
                )
        assert NewsItem.objects.count() == 0

    def test_pipeline_de_ingestao_so_produz_itens_com_fonte_preenchida(self):
        """Verificação de ponta a ponta: todo item que sai do pipeline real tem os dois campos preenchidos."""
        fontes = [
            FonteDeTeste("G1", itens=[_item("Noticia qualquer", "G1", "https://g1/qualquer")]),
        ]
        executar_ingestao(fontes=fontes, summarization_provider=ProviderResumoGenuino())
        item = NewsItem.objects.get()
        assert item.url_fonte_original == "https://g1/qualquer"
        assert item.nome_fonte == "G1"


# ===========================================================================
# AC-4: resumo_proprio preenchido pelo SummarizationProvider — NUNCA cópia
# do texto bruto. Critério mais crítico (risco jurídico, BRD §18).
# ===========================================================================


class TestAC4ResumoProprioNuncaECopia:
    def test_caminho_feliz_resumo_de_provider_bem_comportado_nao_e_identico_ao_bruto(self):
        conteudo_original = (
            "O governo anunciou nesta terca-feira um novo pacote de medidas economicas "
            "que preve reducao de impostos para pequenas empresas e ampliacao de credito."
        )
        fontes = [
            FonteDeTeste(
                "G1",
                itens=[
                    _item(
                        "Governo anuncia pacote de medidas economicas",
                        "G1",
                        "https://g1/pacote-economico",
                        conteudo=conteudo_original,
                    )
                ],
            )
        ]

        executar_ingestao(fontes=fontes, summarization_provider=ProviderResumoGenuino())

        item = NewsItem.objects.get()
        assert item.resumo_proprio != conteudo_original
        assert item.conteudo_bruto == conteudo_original
        similaridade = SequenceMatcher(None, item.resumo_proprio, conteudo_original).ratio()
        assert similaridade < 0.5

    def test_resumo_do_provider_e_persistido_no_campo_correto_nunca_no_lugar_do_bruto(self):
        fontes = [FonteDeTeste("UOL", itens=[_item("Alguma noticia", "UOL", "https://uol/x")])]
        provider = ProviderResumoGenuino()
        executar_ingestao(fontes=fontes, summarization_provider=provider)
        item = NewsItem.objects.get()
        resultado_esperado = ResultadoResumo(
            resumo=(
                f"Sintese jornalistica autoral sobre o acontecimento relatado por "
                f"1 fonte(s); ver apuracao completa nas fontes originais."
            ),
            categoria="geral",
        )
        assert item.resumo_proprio == resultado_esperado.resumo

    def test_provider_mal_comportado_que_devolve_copia_literal_do_bruto_e_bloqueado(self):
        """
        REMEDIATION (code-review-contract.md run 20260902-0727-ingestao-noticias,
        Finding 1, blocker): este teste era `xfail(strict=True)` — documentava um
        gap de cobertura critico em que `services/ingestao.py::_persistir_grupo`
        confiava cegamente no retorno de `SummarizationProvider` sem comparar
        `resumo_proprio` com `conteudo_bruto`. Corrigido via
        `_resumo_e_copia_ou_quase_copia()` em `services/ingestao.py`: agora, se o
        provider devolver uma copia literal (ou quase-copia, ver teste seguinte)
        do bruto como "resumo", o item e forcado para status_revisao=pendente em
        vez de ser publicado automaticamente — este teste passa de verdade agora,
        sem xfail.
        """
        conteudo = "O governo anunciou nesta terca-feira um pacote de medidas economicas para pequenas empresas."

        class ProviderCopiaLiteral(SummarizationProvider):
            def resumir_e_classificar(self, itens_brutos):
                # Simula um LLM que "alucina" e devolve o proprio texto bruto como resumo,
                # ou uma implementacao futura com bug de copy-paste.
                return ResultadoResumo(resumo=itens_brutos[0].conteudo_bruto, categoria="esportes", urgente=False)

        fontes = [
            FonteDeTeste(
                "G1",
                itens=[
                    _item(
                        "Governo anuncia pacote de medidas economicas",
                        "G1",
                        "https://g1/copia-literal",
                        conteudo=conteudo,
                        categoria="esportes",  # categoria NAO sensivel, fonte unica -> nao aciona AC-5 por outro motivo
                    )
                ],
            )
        ]

        executar_ingestao(fontes=fontes, summarization_provider=ProviderCopiaLiteral())

        item = NewsItem.objects.get()
        # Comportamento agora garantido pelo pipeline: publicacao automatica e
        # recusada (forca revisao humana) quando resumo_proprio == conteudo_bruto.
        assert item.resumo_proprio == item.conteudo_bruto  # o campo ainda grava o valor devolvido pelo provider...
        assert item.status_revisao == NewsItem.STATUS_PENDENTE  # ...mas NUNCA e publicado sem revisao humana
        assert item.publicado_automaticamente is False

    def test_provider_mal_comportado_que_devolve_quase_copia_parafraseada_tambem_e_bloqueado(self):
        """
        Variante mais realista do teste acima: o provider nao devolve uma copia
        EXATA (SequenceMatcher ratio == 1.0), mas uma "parafrase" superficial que
        ainda e, na pratica, uma quase-copia do texto bruto (poucas palavras
        trocadas) — deve ser bloqueada pelo mesmo mecanismo, nao so o caso de
        copia 100% literal.
        """
        conteudo = (
            "O governo anunciou nesta terca-feira um pacote de medidas economicas "
            "que preve reducao de impostos para pequenas empresas e ampliacao de credito."
        )
        quase_copia = (
            "O governo anunciou hoje um pacote de medidas economicas "
            "que preve reducao de impostos para pequenas empresas e ampliacao de credito."
        )

        class ProviderQuaseCopia(SummarizationProvider):
            def resumir_e_classificar(self, itens_brutos):
                return ResultadoResumo(resumo=quase_copia, categoria="economia", urgente=False)

        fontes = [
            FonteDeTeste(
                "G1",
                itens=[
                    _item(
                        "Governo anuncia pacote de medidas economicas",
                        "G1",
                        "https://g1/quase-copia",
                        conteudo=conteudo,
                    )
                ],
            )
        ]

        executar_ingestao(fontes=fontes, summarization_provider=ProviderQuaseCopia())

        item = NewsItem.objects.get()
        assert item.status_revisao == NewsItem.STATUS_PENDENTE
        assert item.publicado_automaticamente is False

    def test_provider_falhando_produz_resumo_vazio_nunca_copia_do_bruto_como_fallback(self):
        """Caso de erro do provider (AC-1/AC-4 combinados): o fallback usa resumo vazio, nunca o bruto."""

        class ProviderQuebrado(SummarizationProvider):
            def resumir_e_classificar(self, itens_brutos):
                from catalogo_noticias.providers.summarization import SummarizationProviderError

                raise SummarizationProviderError("provedor fora do ar (simulado)")

        conteudo = "Texto bruto que jamais deveria acabar em resumo_proprio."
        fontes = [FonteDeTeste("G1", itens=[_item("Noticia X", "G1", "https://g1/y", conteudo=conteudo)])]

        executar_ingestao(fontes=fontes, summarization_provider=ProviderQuebrado())

        item = NewsItem.objects.get()
        assert item.resumo_proprio != conteudo
        assert item.resumo_proprio == ""
        assert item.status_revisao == NewsItem.STATUS_PENDENTE

    # -----------------------------------------------------------------------
    # Finding 2 (code-review-contract.md run 20260902-0727-ingestao-noticias,
    # 2a passada, major): a checagem de similaridade sobre o TEXTO INTEIRO
    # (`SequenceMatcher(None, resumo, bruto).ratio()`) e insensivel a copia
    # VERBATIM de um trecho CURTO dentro de um `conteudo_bruto` bem mais
    # longo, porque a formula 2*M/T penaliza pela diferenca de tamanho entre
    # os dois textos — o reviewer reproduziu isso com um resumo = primeira
    # frase de uma materia real de 7 frases, copiada literalmente
    # (ratio() == 0.41, abaixo do limiar 0.6). Os testes abaixo cobrem o
    # cenario exato do reviewer MAIS variacoes (trecho copiado do meio da
    # materia, dois trechos nao-adjacentes concatenados) para nao corrigir
    # so para o caso relatado.
    # -----------------------------------------------------------------------

    MATERIA_LONGA_SETE_FRASES = (
        "A policia civil de Sao Paulo prendeu nesta terca-feira um homem suspeito de "
        "participar de um esquema de furtos a lojas de eletronicos na regiao central "
        "da capital paulista. Segundo as investigacoes, o grupo agia ha pelo menos "
        "seis meses, revendendo os produtos furtados em feiras livres e pela internet. "
        "A operacao contou com apoio da policia civil e da guarda municipal, que "
        "monitoraram os suspeitos por semanas antes da prisao. As autoridades ainda "
        "buscam outros dois integrantes da quadrilha, que permanecem foragidos. "
        "A pena prevista para o crime de furto qualificado pode chegar a oito anos "
        "de reclusao, segundo o delegado responsavel pelo caso. O material recuperado "
        "sera devolvido as lojas assim que os tramites judiciais forem concluidos."
    )

    def test_provider_devolve_copia_verbatim_da_primeira_frase_de_materia_longa_e_bloqueado(self):
        """Cenario exato reproduzido pelo reviewer na 2a passada."""
        resumo_copiado = (
            "A policia civil de Sao Paulo prendeu nesta terca-feira um homem suspeito de "
            "participar de um esquema de furtos a lojas de eletronicos na regiao central "
            "da capital paulista."
        )
        # confirma a premissa do finding: a checagem 1 sozinha (ratio sobre o
        # texto inteiro) NAO pegaria este caso.
        assert (
            SequenceMatcher(None, resumo_copiado, self.MATERIA_LONGA_SETE_FRASES).ratio() < 0.6
        )

        class ProviderCopiaTrechoCurto(SummarizationProvider):
            def resumir_e_classificar(self, itens_brutos):
                return ResultadoResumo(resumo=resumo_copiado, categoria="geral", urgente=False)

        fontes = [
            FonteDeTeste(
                "G1",
                itens=[
                    _item(
                        "Homem e preso suspeito de furtos a lojas em SP",
                        "G1",
                        "https://g1/copia-trecho-primeira-frase",
                        conteudo=self.MATERIA_LONGA_SETE_FRASES,
                    )
                ],
            )
        ]

        executar_ingestao(fontes=fontes, summarization_provider=ProviderCopiaTrechoCurto())

        item = NewsItem.objects.get()
        assert item.status_revisao == NewsItem.STATUS_PENDENTE
        assert item.publicado_automaticamente is False

    def test_provider_devolve_copia_verbatim_de_frase_do_meio_da_materia_e_bloqueado(self):
        """
        Variacao: o trecho copiado nao esta no INICIO do bruto (a checagem
        precisa achar o trecho em QUALQUER posicao, nao so no prefixo).
        """
        resumo_copiado = (
            "A operacao contou com apoio da policia civil e da guarda municipal, que "
            "monitoraram os suspeitos por semanas antes da prisao."
        )

        class ProviderCopiaTrechoDoMeio(SummarizationProvider):
            def resumir_e_classificar(self, itens_brutos):
                return ResultadoResumo(resumo=resumo_copiado, categoria="geral", urgente=False)

        fontes = [
            FonteDeTeste(
                "UOL",
                itens=[
                    _item(
                        "Operacao prende suspeito de furtos em SP",
                        "UOL",
                        "https://uol/copia-trecho-meio",
                        conteudo=self.MATERIA_LONGA_SETE_FRASES,
                    )
                ],
            )
        ]

        executar_ingestao(fontes=fontes, summarization_provider=ProviderCopiaTrechoDoMeio())

        item = NewsItem.objects.get()
        assert item.status_revisao == NewsItem.STATUS_PENDENTE
        assert item.publicado_automaticamente is False

    def test_provider_devolve_duas_frases_nao_adjacentes_copiadas_e_concatenadas_e_bloqueado(self):
        """
        Variacao adicional: duas frases NAO adjacentes do bruto, copiadas
        literalmente e concatenadas (simula um "resumo" preguicoso que
        recorta trechos em vez de sintetizar) — cada trecho isolado ja e
        maior que o tamanho minimo de bloco considerado (ver
        `_TAMANHO_MINIMO_TRECHO_COPIADO_CARACTERES`).
        """
        resumo_copiado = (
            "As autoridades ainda buscam outros dois integrantes da quadrilha, que "
            "permanecem foragidos. O material recuperado sera devolvido as lojas assim "
            "que os tramites judiciais forem concluidos."
        )

        class ProviderCopiaDoisTrechos(SummarizationProvider):
            def resumir_e_classificar(self, itens_brutos):
                return ResultadoResumo(resumo=resumo_copiado, categoria="geral", urgente=False)

        fontes = [
            FonteDeTeste(
                "CNN Brasil",
                itens=[
                    _item(
                        "Caso de furtos em SP segue em investigacao",
                        "CNN Brasil",
                        "https://cnn/copia-dois-trechos",
                        conteudo=self.MATERIA_LONGA_SETE_FRASES,
                    )
                ],
            )
        ]

        executar_ingestao(fontes=fontes, summarization_provider=ProviderCopiaDoisTrechos())

        item = NewsItem.objects.get()
        assert item.status_revisao == NewsItem.STATUS_PENDENTE
        assert item.publicado_automaticamente is False

    def test_resumo_autoral_genuino_em_materia_longa_nao_e_bloqueado_pela_checagem_de_trecho(self):
        """
        Salvaguarda: a nova checagem de trecho copiado nao pode degenerar em
        bloquear qualquer resumo que reaproveita vocabulario/nomes proprios
        de uma materia longa — um resumo genuinamente sintetizado (parafrase
        real, nao um recorte literal) continua publicavel automaticamente.
        """
        resumo_autoral = (
            "Uma investigacao da policia paulista culminou na detencao de um suspeito "
            "ligado a furtos de eletronicos na regiao central. O esquema, segundo "
            "apuracao, durava meses e envolvia revenda em feiras e pela internet."
        )

        class ProviderResumoAutoralEmMateriaLonga(SummarizationProvider):
            def resumir_e_classificar(self, itens_brutos):
                return ResultadoResumo(resumo=resumo_autoral, categoria="geral", urgente=False)

        fontes = [
            FonteDeTeste(
                "Folha",
                itens=[
                    _item(
                        "Homem e preso suspeito de furtos a lojas em SP",
                        "Folha",
                        "https://folha/resumo-autoral-materia-longa",
                        conteudo=self.MATERIA_LONGA_SETE_FRASES,
                    )
                ],
            )
        ]

        executar_ingestao(fontes=fontes, summarization_provider=ProviderResumoAutoralEmMateriaLonga())

        item = NewsItem.objects.get()
        assert item.status_revisao == NewsItem.STATUS_NAO_APLICAVEL
        assert item.publicado_automaticamente is True

    def test_proporcao_copiada_e_funcao_pura_e_normalizada_pelo_tamanho_do_proprio_resumo(self):
        """
        Teste unitario direto de `_proporcao_do_resumo_copiada_literalmente`
        (sem tocar banco/pipeline), confirmando a propriedade central do
        fix: normalizacao pelo tamanho do PROPRIO resumo, nao pelo tamanho
        combinado dos dois textos — por isso um resumo curto 100% copiado de
        um bruto bem mais longo tem proporcao ~1.0, mesmo que o
        `SequenceMatcher.ratio()` combinado seja baixo.
        """
        from catalogo_noticias.services.ingestao import _proporcao_do_resumo_copiada_literalmente

        resumo_curto_verbatim = (
            "A policia civil de Sao Paulo prendeu nesta terca-feira um homem suspeito de "
            "participar de um esquema de furtos a lojas de eletronicos na regiao central "
            "da capital paulista."
        )
        proporcao = _proporcao_do_resumo_copiada_literalmente(
            resumo_curto_verbatim, self.MATERIA_LONGA_SETE_FRASES
        )
        ratio_combinado = SequenceMatcher(
            None, resumo_curto_verbatim, self.MATERIA_LONGA_SETE_FRASES
        ).ratio()

        assert proporcao > 0.95
        assert ratio_combinado < 0.6
        assert proporcao > ratio_combinado


# ===========================================================================
# AC-5: alta relevância (categoria sensível OU limiar de fontes) ->
# status_revisao=pendente, NÃO publicado; senão -> nao_aplicavel, publicável.
# Os dois ramos são testados separadamente, além do caso "baixa relevância
# não fica presa em revisão".
# ===========================================================================


class TestAC5FilaDeRevisaoHumana:
    @override_settings(CATALOGO_NOTICIAS_CATEGORIAS_SENSIVEIS=["saude publica"], CATALOGO_NOTICIAS_LIMIAR_FONTES_ALTA_RELEVANCIA=5)
    def test_ramo_categoria_sensivel_isoladamente_aciona_revisao_mesmo_com_1_fonte(self):
        """Só a categoria sensível deve bastar — limiar de fontes alto (5) deliberadamente não seria atingido."""
        fontes = [FonteDeTeste("G1", itens=[_item("Surto de doenca e identificado na regiao", "G1", "https://g1/saude")])]

        executar_ingestao(fontes=fontes, summarization_provider=ProviderResumoGenuino(categoria="saude publica"))

        item = NewsItem.objects.get()
        assert item.status_revisao == NewsItem.STATUS_PENDENTE
        assert item.publicado_automaticamente is False

    @override_settings(CATALOGO_NOTICIAS_CATEGORIAS_SENSIVEIS=["saude publica"], CATALOGO_NOTICIAS_LIMIAR_FONTES_ALTA_RELEVANCIA=3)
    def test_ramo_limiar_de_fontes_isoladamente_aciona_revisao_com_categoria_nao_sensivel(self):
        """Só o número de fontes deve bastar — categoria deliberadamente fora da lista sensível."""
        fontes = [
            FonteDeTeste("G1", itens=[_item("Novo estadio e inaugurado na cidade", "G1", "https://g1/estadio")]),
            FonteDeTeste("UOL", itens=[_item("Estadio novo e inaugurado na cidade", "UOL", "https://uol/estadio")]),
            FonteDeTeste("CNN Brasil", itens=[_item("Cidade inaugura novo estadio", "CNN Brasil", "https://cnn/estadio")]),
        ]

        executar_ingestao(fontes=fontes, summarization_provider=ProviderResumoGenuino(categoria="esportes"))

        itens = list(NewsItem.objects.all())
        assert len(itens) == 3
        assert all(i.status_revisao == NewsItem.STATUS_PENDENTE for i in itens)
        assert all(i.publicado_automaticamente is False for i in itens)

    @override_settings(CATALOGO_NOTICIAS_CATEGORIAS_SENSIVEIS=["saude publica"], CATALOGO_NOTICIAS_LIMIAR_FONTES_ALTA_RELEVANCIA=3)
    def test_item_de_baixa_relevancia_nao_fica_preso_em_revisao(self):
        """Nem categoria sensível, nem número de fontes suficiente -> nao_aplicavel, publicável, não em fila."""
        fontes = [FonteDeTeste("UOL", itens=[_item("Time vence partida amistosa", "UOL", "https://uol/esporte")])]

        executar_ingestao(fontes=fontes, summarization_provider=ProviderResumoGenuino(categoria="esportes"))

        item = NewsItem.objects.get()
        assert item.status_revisao == NewsItem.STATUS_NAO_APLICAVEL
        assert item.publicado_automaticamente is True
        # confirma que nao aparece na fila (queryset que o admin usaria para a fila de revisao)
        assert item not in NewsItem.objects.filter(status_revisao=NewsItem.STATUS_PENDENTE)

    @override_settings(CATALOGO_NOTICIAS_CATEGORIAS_SENSIVEIS=["saude publica"], CATALOGO_NOTICIAS_LIMIAR_FONTES_ALTA_RELEVANCIA=2)
    def test_ambos_os_ramos_simultaneos_ainda_resultam_em_pendente_uma_vez_so(self):
        """Categoria sensível E limiar de fontes atingido ao mesmo tempo — ainda um único status pendente coerente."""
        fontes = [
            FonteDeTeste("G1", itens=[_item("Alerta de surto de doenca na regiao norte", "G1", "https://g1/saude2")]),
            FonteDeTeste("UOL", itens=[_item("Surto de doenca e registrado na regiao norte", "UOL", "https://uol/saude2")]),
        ]

        executar_ingestao(fontes=fontes, summarization_provider=ProviderResumoGenuino(categoria="saude publica"))

        itens = list(NewsItem.objects.all())
        assert len(itens) == 2
        assert all(i.status_revisao == NewsItem.STATUS_PENDENTE for i in itens)


# ===========================================================================
# AC-6: registro consultável por execução (itens por fonte, duplicatas,
# chamadas/custo do SummarizationProvider).
# ===========================================================================


class TestAC6RegistroDeExecucaoConsultavel:
    def test_registro_persistido_com_metricas_corretas_incluindo_erro_de_fonte(self):
        fontes = [
            FonteDeTeste("G1", itens=[_item("Taxa de juros e alterada pelo Banco Central", "G1", "https://g1/juros2")]),
            FonteDeTeste(
                "UOL", itens=[_item("Banco Central altera taxa de juros", "UOL", "https://uol/juros2")]
            ),
            FonteDeTeste("CNN Brasil", itens=[_item("Noticia isolada sem par", "CNN Brasil", "https://cnn/isolada")]),
            FonteDeTeste("Folha", erro=FonteIndisponivelError("feed fora do ar")),
        ]
        provider = ProviderResumoGenuino()

        registro = executar_ingestao(fontes=fontes, summarization_provider=provider)

        assert isinstance(registro, RegistroExecucaoIngestao)
        assert registro.itens_por_fonte == {"G1": 1, "UOL": 1, "CNN Brasil": 1, "Folha": 0}
        assert registro.erros_por_fonte == {"Folha": "feed fora do ar"}
        assert registro.total_itens_ingeridos == 3
        assert registro.total_grupos_formados == 2  # G1+UOL juntos, CNN Brasil isolado
        assert registro.total_duplicatas_agrupadas == 1
        # code-review-contract.md run 20260902-0727-ingestao-noticias, 3a
        # passada, Finding 1: cada item e resumido de forma INDEPENDENTE
        # (nunca um resumo combinado compartilhado) — `provider.chamadas`
        # (contador interno do dublê, incrementado a cada chamada de
        # `resumir_e_classificar`) confirma isso: G1+UOL (grupo de 2) + CNN
        # Brasil (grupo de 1) = 3 chamadas ao metodo de item-unico, nao 2
        # (mesmo havendo so 2 grupos formados).
        #
        # `registro.chamadas_summarization_provider` agora mede algo
        # DIFERENTE (posterior a esta correcao — reducao de custo pedida
        # pelo usuario apos configurar uma chave real de LLM): quantas
        # chamadas HTTP EM LOTE `executar_ingestao` de fato fez
        # (`resumir_e_classificar_em_lote`), nao quantos itens foram
        # resumidos. Os 3 itens desta execucao cabem todos no mesmo lote
        # (tamanho padrao 10, ver CATALOGO_NOTICIAS_LLM_TAMANHO_LOTE) — 1
        # chamada em lote, ainda que o dublê (que nao sobrescreve
        # `resumir_e_classificar_em_lote`) processe cada item
        # individualmente por dentro.
        assert provider.chamadas == 3
        assert registro.chamadas_summarization_provider == 1
        assert registro.tokens_utilizados_summarization == 51  # 17 tokens x 3 chamadas
        assert registro.custo_estimado_summarization_usd == pytest.approx(0.0015)

        # consultavel de fato via banco, em uma query nova (nao so o objeto em memoria)
        do_banco = RegistroExecucaoIngestao.objects.get(pk=registro.pk)
        assert do_banco.itens_por_fonte == registro.itens_por_fonte
        assert do_banco.erros_por_fonte == {"Folha": "feed fora do ar"}

    def test_execucoes_sucessivas_geram_registros_distintos_consultaveis_no_historico(self):
        fontes_1 = [FonteDeTeste("G1", itens=[_item("Primeira noticia", "G1", "https://g1/primeira")])]
        fontes_2 = [FonteDeTeste("UOL", itens=[_item("Segunda noticia", "UOL", "https://uol/segunda")])]

        registro_1 = executar_ingestao(fontes=fontes_1, summarization_provider=ProviderResumoGenuino())
        registro_2 = executar_ingestao(fontes=fontes_2, summarization_provider=ProviderResumoGenuino())

        assert RegistroExecucaoIngestao.objects.count() == 2
        assert registro_1.pk != registro_2.pk
        assert registro_1.total_itens_ingeridos == 1
        assert registro_2.total_itens_ingeridos == 1


# ===========================================================================
# AC-7: categorias sensíveis e limiar de fontes configuráveis SEM alteração
# de código.
# ===========================================================================


class TestAC7ConfiguravelSemAlterarCodigo:
    @override_settings(CATALOGO_NOTICIAS_LIMIAR_FONTES_ALTA_RELEVANCIA=2)
    def test_reduzir_limiar_via_override_settings_muda_comportamento_em_runtime(self):
        fontes = [
            FonteDeTeste("G1", itens=[_item("Nova vacina e aprovada pela agencia", "G1", "https://g1/vac2")]),
            FonteDeTeste("UOL", itens=[_item("Agencia aprova nova vacina", "UOL", "https://uol/vac2")]),
        ]
        executar_ingestao(fontes=fontes, summarization_provider=ProviderResumoGenuino(categoria="saude"))
        assert all(i.status_revisao == NewsItem.STATUS_PENDENTE for i in NewsItem.objects.all())

    @override_settings(CATALOGO_NOTICIAS_LIMIAR_FONTES_ALTA_RELEVANCIA=99)
    def test_aumentar_limiar_via_override_settings_tambem_muda_comportamento(self):
        """O mesmo cenário de 3 fontes que antes acionava revisão (limiar default=3) deixa de acionar com limiar=99."""
        fontes = [
            FonteDeTeste("G1", itens=[_item("Show de musica reune multidao no parque", "G1", "https://g1/show2")]),
            FonteDeTeste("UOL", itens=[_item("Multidao lota parque para show de musica", "UOL", "https://uol/show2")]),
            FonteDeTeste("CNN Brasil", itens=[_item("Parque recebe multidao em show de musica", "CNN Brasil", "https://cnn/show2")]),
        ]
        executar_ingestao(fontes=fontes, summarization_provider=ProviderResumoGenuino(categoria="cultura"))
        assert all(i.status_revisao == NewsItem.STATUS_NAO_APLICAVEL for i in NewsItem.objects.all())

    @override_settings(CATALOGO_NOTICIAS_CATEGORIAS_SENSIVEIS=["cultura"])
    def test_mudar_lista_de_categorias_sensiveis_via_override_settings_muda_comportamento(self):
        fontes = [FonteDeTeste("G1", itens=[_item("Festival de cultura acontece na cidade", "G1", "https://g1/cult")])]
        executar_ingestao(fontes=fontes, summarization_provider=ProviderResumoGenuino(categoria="cultura"))
        item = NewsItem.objects.get()
        assert item.status_revisao == NewsItem.STATUS_PENDENTE

    def test_configuracao_e_lida_de_verdade_via_variavel_de_ambiente_no_settings_py(self):
        """
        Teste mais forte que `override_settings` (utilitário de teste do
        Django): sobe um subprocesso Python isolado que importa
        `config.settings` com `CATALOGO_NOTICIAS_LIMIAR_FONTES_ALTA_RELEVANCIA`
        e `CATALOGO_NOTICIAS_CATEGORIAS_SENSIVEIS` definidos via variável de
        ambiente (o mecanismo real de configuração em produção, não um
        artifício só do ambiente de teste), confirmando que `settings.py` de
        fato lê `os.environ` para esses dois parâmetros, sem nenhuma
        alteração de código/redeploy de lógica de negócio.
        """
        import os
        import subprocess
        import sys

        env = dict(os.environ)
        env["DJANGO_SETTINGS_MODULE"] = "config.settings_test"
        env["DJANGO_DB_ENGINE"] = "sqlite3"
        env["CATALOGO_NOTICIAS_LIMIAR_FONTES_ALTA_RELEVANCIA"] = "7"
        env["CATALOGO_NOTICIAS_CATEGORIAS_SENSIVEIS"] = "clima,tecnologia"

        codigo = (
            "import django; django.setup(); "
            "from django.conf import settings; "
            "print(settings.CATALOGO_NOTICIAS_LIMIAR_FONTES_ALTA_RELEVANCIA); "
            "print(','.join(settings.CATALOGO_NOTICIAS_CATEGORIAS_SENSIVEIS))"
        )
        resultado = subprocess.run(
            [sys.executable, "-c", codigo],
            cwd=os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            env=env,
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert resultado.returncode == 0, resultado.stderr
        linhas = resultado.stdout.strip().splitlines()
        assert linhas[0] == "7"
        assert linhas[1] == "clima,tecnologia"


# ===========================================================================
# Finding 3 (code-review-contract.md run 20260902-0727-ingestao-noticias,
# major): `agrupar_itens_brutos()` so comparava itens do LOTE ATUAL entre si
# — um `NewsItem` ja persistido em uma execucao anterior da task Celery
# nunca era reavaliado contra cobertura que chega em execucoes futuras.
# Cenario do reviewer: G1 publica algo as 10:00 (ingerido no ciclo das
# 10:00, vira NewsItem standalone), as 10:15 UOL e CNN Brasil publicam
# cobertura do MESMO fato — antes da correcao, esses dois se agrupavam
# ENTRE SI mas NUNCA com o item do G1 ja persistido, entao o criterio de
# "3+ fontes -> revisao humana" nunca era atingido para um fato coberto por
# 3 fontes reais.
# ===========================================================================


class TestFinding3DeduplicacaoEntreExecucoesDaTask:
    def test_item_persistido_em_execucao_anterior_e_agrupado_com_cobertura_que_chega_depois(self):
        """
        Simula 2 ciclos da task periodica (2 chamadas a `executar_ingestao`):
        1o ciclo, 1 fonte (G1) cobre o fato -> vira NewsItem standalone,
        publicado automaticamente (1 fonte, categoria nao sensivel). 2o
        ciclo, pouco depois (dentro da janela default de
        `CATALOGO_NOTICIAS_DEDUP_JANELA_RECENTE_HORAS`), 2 outras fontes
        (UOL, CNN Brasil) cobrem o MESMO fato. Depois do 2o ciclo, as 3
        fontes (a antiga + as 2 novas) devem estar no MESMO NewsCluster —
        e, como isso atinge o limiar default de 3 fontes, TODOS os 3 itens
        (incluindo o antigo, que ja estava `nao_aplicavel`) devem virar
        `status_revisao=pendente`.
        """
        fontes_ciclo_1 = [
            FonteDeTeste(
                "G1",
                itens=[
                    _item(
                        "Grande incendio atinge deposito industrial na zona leste",
                        "G1",
                        "https://g1/incendio-finding3",
                    )
                ],
            )
        ]
        executar_ingestao(fontes=fontes_ciclo_1, summarization_provider=ProviderResumoGenuino(categoria="cidades"))

        item_g1 = NewsItem.objects.get(url_fonte_original="https://g1/incendio-finding3")
        assert item_g1.cluster is None
        assert item_g1.status_revisao == NewsItem.STATUS_NAO_APLICAVEL
        assert item_g1.publicado_automaticamente is True

        fontes_ciclo_2 = [
            FonteDeTeste(
                "UOL",
                itens=[
                    _item(
                        "Incendio de grandes proporcoes atinge deposito na zona leste",
                        "UOL",
                        "https://uol/incendio-finding3",
                    )
                ],
            ),
            FonteDeTeste(
                "CNN Brasil",
                itens=[
                    _item(
                        "Deposito na zona leste e atingido por grande incendio",
                        "CNN Brasil",
                        "https://cnn/incendio-finding3",
                    )
                ],
            ),
        ]
        executar_ingestao(fontes=fontes_ciclo_2, summarization_provider=ProviderResumoGenuino(categoria="cidades"))

        item_g1.refresh_from_db()
        item_uol = NewsItem.objects.get(url_fonte_original="https://uol/incendio-finding3")
        item_cnn = NewsItem.objects.get(url_fonte_original="https://cnn/incendio-finding3")

        # as 3 fontes (a antiga + as 2 novas) no MESMO cluster.
        assert item_g1.cluster_id is not None
        assert item_g1.cluster_id == item_uol.cluster_id == item_cnn.cluster_id
        assert item_g1.cluster.numero_fontes_distintas == 3

        # limiar default de 3 fontes atingido -> TODOS os itens do cluster
        # (incluindo o antigo, ja `nao_aplicavel`) viram pendente.
        assert item_g1.status_revisao == NewsItem.STATUS_PENDENTE
        assert item_uol.status_revisao == NewsItem.STATUS_PENDENTE
        assert item_cnn.status_revisao == NewsItem.STATUS_PENDENTE

        # o item antigo NAO foi re-resumido (decisao de design documentada em
        # `_persistir_grupo_mesclado`) — seu resumo_proprio nao muda so por
        # ter sido incorporado ao cluster.
        assert item_g1.resumo_proprio == (
            "Sintese jornalistica autoral sobre o acontecimento relatado por 1 fonte(s); "
            "ver apuracao completa nas fontes originais."
        )

    def test_status_revisao_ja_decidido_por_humano_nunca_e_sobrescrito_pela_mesclagem(self):
        """
        Variante do teste acima focada na salvaguarda mais importante do
        Finding 3: um item cujo `status_revisao` ja foi decidido por um
        humano (`aprovado`/`rejeitado`) NUNCA pode ser sobrescrito so porque
        o cluster cresceu e cruzou o limiar de fontes numa execucao
        automatica posterior.
        """
        fontes_ciclo_1 = [
            FonteDeTeste(
                "G1",
                itens=[_item("Prefeito anuncia reforma de praca publica", "G1", "https://g1/praca-finding3")],
            )
        ]
        executar_ingestao(fontes=fontes_ciclo_1, summarization_provider=ProviderResumoGenuino(categoria="cidades"))

        item_g1 = NewsItem.objects.get(url_fonte_original="https://g1/praca-finding3")
        item_g1.status_revisao = NewsItem.STATUS_REJEITADO
        item_g1.save(update_fields=["status_revisao"])

        fontes_ciclo_2 = [
            FonteDeTeste(
                "UOL",
                itens=[_item("Reforma de praca publica e anunciada pelo prefeito", "UOL", "https://uol/praca-finding3")],
            ),
            FonteDeTeste(
                "CNN Brasil",
                itens=[_item("Praca publica sera reformada, anuncia prefeito", "CNN Brasil", "https://cnn/praca-finding3")],
            ),
        ]
        executar_ingestao(fontes=fontes_ciclo_2, summarization_provider=ProviderResumoGenuino(categoria="cidades"))

        item_g1.refresh_from_db()
        item_uol = NewsItem.objects.get(url_fonte_original="https://uol/praca-finding3")
        item_cnn = NewsItem.objects.get(url_fonte_original="https://cnn/praca-finding3")

        # o item G1 se junta ao cluster (cobertura do mesmo fato)...
        assert item_g1.cluster_id is not None
        assert item_g1.cluster_id == item_uol.cluster_id == item_cnn.cluster_id
        # ...mas a decisao humana (`rejeitado`) e preservada, mesmo com o
        # cluster cruzando o limiar de 3 fontes.
        assert item_g1.status_revisao == NewsItem.STATUS_REJEITADO
        # os itens NOVOS, sem decisao humana previa, seguem a reavaliacao normal.
        assert item_uol.status_revisao == NewsItem.STATUS_PENDENTE
        assert item_cnn.status_revisao == NewsItem.STATUS_PENDENTE

    @override_settings(CATALOGO_NOTICIAS_DEDUP_JANELA_RECENTE_HORAS=1)
    def test_item_fora_da_janela_configurada_nao_e_considerado(self):
        """
        Com a janela reduzida para 1h, um `NewsItem` persistido ha mais de
        1h (simulado empurrando `timestamp_ingestao` para tras diretamente
        no banco, sem depender de `time.sleep`/mock de tempo) NAO deve ser
        trazido para o agrupamento de uma execucao posterior, mesmo cobrindo
        o mesmo fato — permanece com `cluster=None` e o `status_revisao`
        que ja tinha.
        """
        fontes_ciclo_1 = [
            FonteDeTeste(
                "G1",
                itens=[
                    _item(
                        "Grande incendio atinge deposito industrial na zona leste",
                        "G1",
                        "https://g1/incendio-janela-finding3",
                    )
                ],
            )
        ]
        executar_ingestao(fontes=fontes_ciclo_1, summarization_provider=ProviderResumoGenuino(categoria="cidades"))

        NewsItem.objects.filter(url_fonte_original="https://g1/incendio-janela-finding3").update(
            timestamp_ingestao=timezone.now() - timedelta(hours=48)
        )
        item_g1_antes = NewsItem.objects.get(url_fonte_original="https://g1/incendio-janela-finding3")
        status_original = item_g1_antes.status_revisao

        fontes_ciclo_2 = [
            FonteDeTeste(
                "UOL",
                itens=[
                    _item(
                        "Incendio de grandes proporcoes atinge deposito na zona leste",
                        "UOL",
                        "https://uol/incendio-janela-finding3",
                    )
                ],
            ),
            FonteDeTeste(
                "CNN Brasil",
                itens=[
                    _item(
                        "Deposito na zona leste e atingido por grande incendio",
                        "CNN Brasil",
                        "https://cnn/incendio-janela-finding3",
                    )
                ],
            ),
        ]
        executar_ingestao(fontes=fontes_ciclo_2, summarization_provider=ProviderResumoGenuino(categoria="cidades"))

        item_g1_antes.refresh_from_db()
        item_uol = NewsItem.objects.get(url_fonte_original="https://uol/incendio-janela-finding3")
        item_cnn = NewsItem.objects.get(url_fonte_original="https://cnn/incendio-janela-finding3")

        # item fora da janela: nao foi trazido para o agrupamento, continua
        # standalone e com o status_revisao que ja tinha.
        assert item_g1_antes.cluster is None
        assert item_g1_antes.status_revisao == status_original

        # os 2 itens novos (dentro do lote atual, entre si) ainda se
        # agrupam normalmente — so nao com o item antigo fora da janela.
        assert item_uol.cluster_id is not None
        assert item_uol.cluster_id == item_cnn.cluster_id


# ===========================================================================
# Finding 4 (code-review-contract.md run 20260902-0727-ingestao-noticias, 2a
# passada, minor): quando `_persistir_grupo_mesclado` descobre que dois
# NewsCluster diferentes sao, na verdade, o MESMO acontecimento (um item novo
# fazendo ponte entre eles), o NewsCluster nao-canonico deve ser DELETADO
# apos seus NewsItem serem movidos para o canonico — nao deixado orfao (zero
# itens) poluindo a fila de auditoria do admin.
#
# Teste direto/unitario de `_persistir_grupo_mesclado` (nao via
# `executar_ingestao` ponta a ponta): reproduzir de forma confiavel, via
# pipeline completo, o cenario raro de "dois clusters diferentes revelados
# como o mesmo fato por um item-ponte" dependeria de calibrar manchetes para
# o algoritmo de similaridade encadear exatamente dessa forma — frágil e
# indireto para testar uma regra de limpeza de dados. Testar a funcao
# diretamente com dois `NewsCluster` já existentes é mais direto e
# igualmente valido (a funcao já é testada ponta a ponta pelo Finding 3).
# ===========================================================================


class TestFinding4ClusterOrfaoAposMesclagemERemovido:
    def test_cluster_nao_canonico_e_deletado_apos_itens_serem_movidos_para_o_canonico(self):
        from catalogo_noticias.services.ingestao import _persistir_grupo_mesclado

        cluster_canonico = NewsCluster.objects.create(
            titulo_acontecimento="Fato A", categoria_dominante="cidades"
        )
        cluster_nao_canonico = NewsCluster.objects.create(
            titulo_acontecimento="Fato A (outra redacao)", categoria_dominante="cidades"
        )
        # garante que cluster_canonico.id < cluster_nao_canonico.id, como
        # `_persistir_grupo_mesclado` exige (min(id) vira o canonico)
        assert cluster_canonico.id < cluster_nao_canonico.id

        item_no_canonico = NewsItem.objects.create(
            titulo="Manchete A",
            resumo_proprio="Resumo A",
            conteudo_bruto="Bruto A",
            url_fonte_original="https://g1/finding4-canonico",
            nome_fonte="G1",
            categoria="cidades",
            status_revisao=NewsItem.STATUS_NAO_APLICAVEL,
            cluster=cluster_canonico,
        )
        item_no_nao_canonico = NewsItem.objects.create(
            titulo="Manchete A (outra fonte)",
            resumo_proprio="Resumo A outra fonte",
            conteudo_bruto="Bruto A outra fonte",
            url_fonte_original="https://uol/finding4-nao-canonico",
            nome_fonte="UOL",
            categoria="cidades",
            status_revisao=NewsItem.STATUS_NAO_APLICAVEL,
            cluster=cluster_nao_canonico,
        )

        item_bruto_ponte = _item(
            "Manchete A (item ponte)", "CNN Brasil", "https://cnn/finding4-ponte"
        )
        resultado = ResultadoResumo(resumo="Resumo do item ponte", categoria="cidades", urgente=False)

        cluster_resultante, _ = _persistir_grupo_mesclado(
            resultados_por_item=[(item_bruto_ponte, resultado)],
            news_items_existentes=[item_no_canonico, item_no_nao_canonico],
        )

        assert cluster_resultante.id == cluster_canonico.id
        # o cluster nao-canonico foi DELETADO (nao so esvaziado) — Finding 4
        assert not NewsCluster.objects.filter(pk=cluster_nao_canonico.id).exists()
        assert NewsCluster.objects.filter(pk=cluster_canonico.id).exists()
        # os itens que estavam no nao-canonico foram movidos para o canonico
        # (nao perdidos/apagados junto com o cluster — SET_NULL protegeria,
        # mas o codigo os move ANTES de deletar).
        item_no_nao_canonico.refresh_from_db()
        assert item_no_nao_canonico.cluster_id == cluster_canonico.id
        item_no_canonico.refresh_from_db()
        assert item_no_canonico.cluster_id == cluster_canonico.id
        # nenhum NewsItem ficou orfao (cluster=None) por causa da limpeza
        assert NewsItem.objects.filter(cluster_id=cluster_nao_canonico.id).count() == 0


# ===========================================================================
# Finding 5 (code-review-contract.md run 20260902-0727-ingestao-noticias, 2a
# passada, minor/performance): `_itens_recentes_persistidos` deve respeitar
# um teto superior de itens (`CATALOGO_NOTICIAS_DEDUP_MAX_ITENS_RECENTES`),
# alem do filtro por janela de tempo — evita que o lote combinado passado a
# `agrupar_itens_brutos` (O(n^2)) cresca sem limite em dias de alto volume.
# ===========================================================================


class TestFinding5TetoDeItensRecentesTrazidosParaOAgrupamento:
    def test_itens_recentes_respeita_teto_configurado_priorizando_os_mais_novos(self):
        from catalogo_noticias.services.ingestao import _itens_recentes_persistidos

        agora = timezone.now()
        # 5 NewsItem dentro da janela padrao, com timestamps distintos e
        # conhecidos (o mais recente por ultimo).
        urls_por_ordem = []
        for i in range(5):
            url = f"https://g1/finding5-{i}"
            urls_por_ordem.append(url)
            item = NewsItem.objects.create(
                titulo=f"Noticia {i}",
                resumo_proprio=f"Resumo {i}",
                conteudo_bruto=f"Bruto {i}",
                url_fonte_original=url,
                nome_fonte="G1",
                categoria="geral",
                status_revisao=NewsItem.STATUS_NAO_APLICAVEL,
            )
            # timestamp_ingestao tem auto_now_add — sobrescreve explicitamente
            # para garantir ordem conhecida e independente da velocidade do
            # teste.
            NewsItem.objects.filter(pk=item.pk).update(
                timestamp_ingestao=agora - timedelta(minutes=(5 - i))
            )

        with override_settings(CATALOGO_NOTICIAS_DEDUP_MAX_ITENS_RECENTES=3):
            itens_pseudo, por_url = _itens_recentes_persistidos()

        assert len(itens_pseudo) == 3
        assert len(por_url) == 3
        # os 3 mais RECENTES (indices 2, 3, 4 — timestamps mais proximos de
        # "agora") sao os priorizados, nao os 3 primeiros por ordem de
        # criacao.
        urls_esperadas = set(urls_por_ordem[-3:])
        assert set(por_url.keys()) == urls_esperadas

    def test_itens_recentes_sem_exceder_janela_nem_teto_quando_volume_e_baixo(self):
        """Salvaguarda: com poucos itens (abaixo do teto), nenhum e descartado."""
        from catalogo_noticias.services.ingestao import _itens_recentes_persistidos

        for i in range(2):
            NewsItem.objects.create(
                titulo=f"Noticia baixo volume {i}",
                resumo_proprio=f"Resumo {i}",
                conteudo_bruto=f"Bruto {i}",
                url_fonte_original=f"https://uol/finding5-baixo-volume-{i}",
                nome_fonte="UOL",
                categoria="geral",
                status_revisao=NewsItem.STATUS_NAO_APLICAVEL,
            )

        with override_settings(CATALOGO_NOTICIAS_DEDUP_MAX_ITENS_RECENTES=300):
            itens_pseudo, por_url = _itens_recentes_persistidos()

        assert len(itens_pseudo) == 2
        assert len(por_url) == 2


# ===========================================================================
# code-review-contract.md run 20260902-0727-ingestao-noticias, 3a passada,
# Finding 1 (major — MUDANCA DE ESTRATEGIA): garantia estrutural de que um
# agrupamento INDEVIDO (o algoritmo de deduplicacao e uma heuristica, nao uma
# garantia) nunca resulta em CONTEUDO de um fato atribuido a uma fonte que
# noticiou outro fato. Testado chamando `_persistir_grupo` DIRETAMENTE com
# itens de fatos claramente diferentes, contornando o algoritmo de dedup real
# (o ponto a provar aqui e sobre a PERSISTENCIA/atribuicao de resumo, nao
# sobre a qualidade do agrupamento em si — essa ja e coberta por
# `TestFinding1FalsoPositivoEmLotesPequenosReaberto` e
# `TestFinding2FalsoPositivoPorPadraoSintaticoComum`).
# ===========================================================================


class TestFinding1MisattributionDeConteudoMesmoComAgrupamentoIndevido:
    def test_persistir_grupo_nunca_atribui_resumo_de_um_item_a_outro_do_mesmo_grupo(self):
        """
        Simula o pior caso possivel: o algoritmo de deduplicacao (por
        qualquer falha, presente ou futura) agrupou incorretamente 2 itens
        sobre fatos completamente diferentes no mesmo grupo. Mesmo assim,
        `_persistir_grupo` NUNCA deve atribuir o resumo de um item ao outro —
        cada `NewsItem` deve ficar com o `resumo_proprio` correspondente
        exclusivamente ao seu PROPRIO `ItemBruto`/`ResultadoResumo`.
        """
        from catalogo_noticias.services.ingestao import _persistir_grupo

        item_dengue = _item(
            "Ministerio da Saude confirma novo surto de dengue",
            "G1",
            "https://g1/surto-dengue-finding1-3a",
            conteudo="Texto bruto original sobre o surto de dengue.",
            categoria="saude",
        )
        item_sarampo = _item(
            "Ministerio da Saude confirma novo surto de sarampo",
            "UOL",
            "https://uol/surto-sarampo-finding1-3a",
            conteudo="Texto bruto original sobre o surto de sarampo.",
            categoria="saude",
        )
        resultado_dengue = ResultadoResumo(
            resumo="Sintese autoral: casos de DENGUE confirmados pelo Ministerio da Saude.",
            categoria="saude",
            urgente=False,
        )
        resultado_sarampo = ResultadoResumo(
            resumo="Sintese autoral: casos de SARAMPO confirmados pelo Ministerio da Saude.",
            categoria="saude",
            urgente=False,
        )

        # Agrupamento FORCADO manualmente (bypass deliberado do algoritmo de
        # dedup real) — simula exatamente o cenario que o reviewer reproduziu
        # na 3a passada: 2 fatos diferentes, mesmo "molde" institucional,
        # agrupados no mesmo NewsCluster.
        cluster, itens_criados = _persistir_grupo(
            [(item_dengue, resultado_dengue), (item_sarampo, resultado_sarampo)]
        )

        assert cluster is not None
        assert len(itens_criados) == 2

        news_item_dengue = NewsItem.objects.get(url_fonte_original="https://g1/surto-dengue-finding1-3a")
        news_item_sarampo = NewsItem.objects.get(url_fonte_original="https://uol/surto-sarampo-finding1-3a")

        # a garantia central: cada item tem o resumo do SEU PROPRIO fato,
        # nunca o do outro membro do grupo.
        assert "DENGUE" in news_item_dengue.resumo_proprio
        assert "SARAMPO" not in news_item_dengue.resumo_proprio
        assert "SARAMPO" in news_item_sarampo.resumo_proprio
        assert "DENGUE" not in news_item_sarampo.resumo_proprio
        assert news_item_dengue.resumo_proprio != news_item_sarampo.resumo_proprio

        # ambos pertencem ao mesmo NewsCluster (o agrupamento em si nao foi
        # desfeito — so o CONTEUDO de cada item permanece corretamente
        # atribuido), residual conhecido e aceito (ver comentario acima de
        # `_persistir_grupo` em services/ingestao.py sobre a tensao com AC-7).
        assert news_item_dengue.cluster_id == news_item_sarampo.cluster_id == cluster.id

    def test_persistir_grupo_mesclado_tambem_nunca_atribui_resumo_de_um_item_a_outro(self):
        """
        Mesma garantia, mas no caminho de mesclagem entre execucoes
        (`_persistir_grupo_mesclado`) — um item NOVO que se junta
        (indevidamente) a um `NewsItem` JA PERSISTIDO de um fato diferente
        nao pode fazer o item antigo ser re-escrito com o resumo do novo, nem
        o novo nascer com o resumo do antigo.
        """
        from catalogo_noticias.services.ingestao import _persistir_grupo_mesclado

        item_existente = NewsItem.objects.create(
            titulo="Ministerio da Saude confirma novo surto de dengue",
            resumo_proprio="Sintese autoral original: casos de DENGUE confirmados.",
            conteudo_bruto="Texto bruto original sobre o surto de dengue.",
            url_fonte_original="https://g1/surto-dengue-finding1-3a-mesclado",
            nome_fonte="G1",
            categoria="saude",
            status_revisao=NewsItem.STATUS_NAO_APLICAVEL,
        )

        item_sarampo_novo = _item(
            "Ministerio da Saude confirma novo surto de sarampo",
            "UOL",
            "https://uol/surto-sarampo-finding1-3a-mesclado",
            conteudo="Texto bruto original sobre o surto de sarampo.",
            categoria="saude",
        )
        resultado_sarampo = ResultadoResumo(
            resumo="Sintese autoral: casos de SARAMPO confirmados pelo Ministerio da Saude.",
            categoria="saude",
            urgente=False,
        )

        cluster, itens_criados = _persistir_grupo_mesclado(
            resultados_por_item=[(item_sarampo_novo, resultado_sarampo)],
            news_items_existentes=[item_existente],
        )

        item_existente.refresh_from_db()
        news_item_sarampo = NewsItem.objects.get(url_fonte_original="https://uol/surto-sarampo-finding1-3a-mesclado")

        # o item ANTIGO nunca e re-escrito (mantem seu proprio resumo original).
        assert item_existente.resumo_proprio == "Sintese autoral original: casos de DENGUE confirmados."
        # o item NOVO tem o SEU PROPRIO resumo, nao o do item antigo.
        assert news_item_sarampo.resumo_proprio == resultado_sarampo.resumo
        assert news_item_sarampo.resumo_proprio != item_existente.resumo_proprio
        assert item_existente.cluster_id == news_item_sarampo.cluster_id == cluster.id
