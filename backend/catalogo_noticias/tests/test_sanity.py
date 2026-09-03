"""
Teste minimo de sanidade escrito pelo executor apenas para validar o proprio
codigo durante o desenvolvimento — a suite de testes formal, cobrindo todos
os criterios de aceite do implementation-contract.md, e responsabilidade do
`tester` (proximo agente do pipeline).

Nenhum teste aqui depende de rede real: fontes e SummarizationProvider sao
sempre dublês (fakes) injetados via `executar_ingestao(fontes=..., summarization_provider=...)`.
"""

from __future__ import annotations

from difflib import SequenceMatcher

import pytest
from django.test import override_settings

from catalogo_noticias.models import NewsCluster, NewsItem, RegistroExecucaoIngestao
from catalogo_noticias.providers.news_source import FonteIndisponivelError, ItemBruto, NewsSourceProvider
from catalogo_noticias.providers.summarization import ResultadoResumo, SummarizationProvider
from catalogo_noticias.services.deduplicacao import agrupar_itens_brutos
from catalogo_noticias.services.ingestao import executar_ingestao

pytestmark = pytest.mark.django_db


class FakeNewsSourceProvider(NewsSourceProvider):
    """Dublê de `NewsSourceProvider` — nunca acessa rede."""

    def __init__(self, nome_fonte, itens=None, erro=None):
        self.nome_fonte = nome_fonte
        self._itens = itens or []
        self._erro = erro

    def buscar_itens(self):
        if self._erro is not None:
            raise self._erro
        return self._itens


class FakeSummarizationProvider(SummarizationProvider):
    """Dublê de `SummarizationProvider` — resumo deliberadamente diferente do bruto."""

    def __init__(self, categoria="geral", urgente=False):
        self.categoria = categoria
        self.urgente = urgente
        self.chamadas = 0

    def resumir_e_classificar(self, itens_brutos):
        self.chamadas += 1
        titulo = itens_brutos[0].titulo
        return ResultadoResumo(
            resumo=f"[Resumo IA] Cobertura consolidada sobre '{titulo}', segundo {len(itens_brutos)} fonte(s).",
            categoria=self.categoria,
            urgente=self.urgente,
            tokens_utilizados=42,
            custo_estimado_usd=0.0012,
        )


def _item(titulo, nome_fonte, url, conteudo="Conteudo original bruto da materia, palavra por palavra.", categoria=""):
    return ItemBruto(
        titulo=titulo,
        url_fonte_original=url,
        nome_fonte=nome_fonte,
        conteudo_bruto=conteudo,
        categoria=categoria,
    )


# --- Criterio de aceite 1: falha de uma fonte nao impede as demais --------


def test_fonte_indisponivel_nao_impede_ingestao_das_demais():
    fontes = [
        FakeNewsSourceProvider("G1", itens=[_item("Chuvas atingem regiao sul", "G1", "https://g1/1")]),
        FakeNewsSourceProvider("CNN Brasil", erro=FonteIndisponivelError("timeout simulado")),
        FakeNewsSourceProvider("UOL", itens=[_item("Selecao brasileira vence amistoso", "UOL", "https://uol/1")]),
    ]

    registro = executar_ingestao(fontes=fontes, summarization_provider=FakeSummarizationProvider())

    assert registro.erros_por_fonte == {"CNN Brasil": "timeout simulado"}
    assert registro.itens_por_fonte["G1"] == 1
    assert registro.itens_por_fonte["UOL"] == 1
    assert registro.itens_por_fonte["CNN Brasil"] == 0
    assert NewsItem.objects.count() == 2


# --- Criterio de aceite 2: itens semanticamente equivalentes -> mesmo cluster


def test_itens_de_fontes_diferentes_sobre_mesmo_acontecimento_viram_um_cluster():
    fontes = [
        FakeNewsSourceProvider(
            "G1", itens=[_item("Banco Central eleva taxa de juros para 12%", "G1", "https://g1/juros")]
        ),
        FakeNewsSourceProvider(
            "UOL",
            itens=[_item("Banco Central eleva taxa de juros a 12% ao ano", "UOL", "https://uol/juros")],
        ),
        FakeNewsSourceProvider(
            "Folha - Em Cima da Hora",
            itens=[_item("Time local vence campeonato estadual de futebol", "Folha", "https://folha/futebol")],
        ),
    ]

    registro = executar_ingestao(fontes=fontes, summarization_provider=FakeSummarizationProvider())

    assert NewsCluster.objects.count() == 1
    cluster = NewsCluster.objects.get()
    assert cluster.itens.count() == 2
    assert set(cluster.itens.values_list("nome_fonte", flat=True)) == {"G1", "UOL"}

    # o item de futebol nao entra no cluster (nao similar) e nao gera cluster proprio (grupo de 1)
    item_futebol = NewsItem.objects.get(url_fonte_original="https://folha/futebol")
    assert item_futebol.cluster is None

    assert registro.total_duplicatas_agrupadas == 1  # 3 itens, 2 grupos


def test_agrupar_itens_brutos_isoladamente_sem_banco():
    itens = [
        _item("Presidente sanciona novo pacote economico", "G1", "https://g1/pacote"),
        _item("Presidente sanciona pacote economico anunciado ontem", "CNN Brasil", "https://cnn/pacote"),
        _item("Chuva forte causa alagamentos em SP", "UOL", "https://uol/chuva"),
    ]
    grupos = agrupar_itens_brutos(itens, limiar_similaridade=0.5)
    assert len(grupos) == 2
    tamanhos = sorted(len(g) for g in grupos)
    assert tamanhos == [1, 2]


# --- Criterio de aceite 3: url_fonte_original/nome_fonte obrigatorios -----


def test_newsitem_sem_url_fonte_original_nao_e_criado():
    from django.core.exceptions import ValidationError

    with pytest.raises(ValidationError):
        NewsItem.objects.create(titulo="Teste", url_fonte_original="", nome_fonte="G1")

    assert NewsItem.objects.count() == 0


def test_newsitem_sem_nome_fonte_nao_e_criado():
    from django.core.exceptions import ValidationError

    with pytest.raises(ValidationError):
        NewsItem.objects.create(titulo="Teste", url_fonte_original="https://g1/x", nome_fonte="")

    assert NewsItem.objects.count() == 0


# --- Criterio de aceite 4: resumo_proprio nunca e copia do bruto ----------


def test_resumo_proprio_nunca_e_identico_ou_quase_identico_ao_conteudo_bruto():
    conteudo_original = (
        "O governo anunciou nesta terca-feira um novo pacote de medidas economicas "
        "que preve reducao de impostos para pequenas empresas e ampliacao de credito."
    )
    fontes = [
        FakeNewsSourceProvider(
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

    executar_ingestao(fontes=fontes, summarization_provider=FakeSummarizationProvider())

    item = NewsItem.objects.get()
    assert item.resumo_proprio != conteudo_original
    assert item.conteudo_bruto == conteudo_original
    similaridade = SequenceMatcher(None, item.resumo_proprio, conteudo_original).ratio()
    assert similaridade < 0.5, "resumo_proprio esta suspeitosamente parecido com o texto bruto original"


# --- Criterio de aceite 5: alta relevancia -> pendente; senao -> nao_aplicavel


@override_settings(CATALOGO_NOTICIAS_CATEGORIAS_SENSIVEIS=["política", "economia", "segurança pública"])
def test_categoria_sensivel_aciona_fila_de_revisao_humana():
    fontes = [
        FakeNewsSourceProvider(
            "G1", itens=[_item("Camara aprova projeto de lei polemico", "G1", "https://g1/politica")]
        )
    ]

    executar_ingestao(fontes=fontes, summarization_provider=FakeSummarizationProvider(categoria="política"))

    item = NewsItem.objects.get()
    assert item.status_revisao == NewsItem.STATUS_PENDENTE
    assert item.publicado_automaticamente is False


@override_settings(CATALOGO_NOTICIAS_CATEGORIAS_SENSIVEIS=["política", "economia", "segurança pública"])
def test_categoria_nao_sensivel_e_publicado_automaticamente():
    fontes = [
        FakeNewsSourceProvider(
            "UOL", itens=[_item("Time vence partida decisiva do campeonato", "UOL", "https://uol/esporte")]
        )
    ]

    executar_ingestao(fontes=fontes, summarization_provider=FakeSummarizationProvider(categoria="esportes"))

    item = NewsItem.objects.get()
    assert item.status_revisao == NewsItem.STATUS_NAO_APLICAVEL
    assert item.publicado_automaticamente is True


@override_settings(
    CATALOGO_NOTICIAS_CATEGORIAS_SENSIVEIS=["política", "economia", "segurança pública"],
    CATALOGO_NOTICIAS_LIMIAR_FONTES_ALTA_RELEVANCIA=3,
)
def test_cluster_com_3_ou_mais_fontes_aciona_revisao_mesmo_com_categoria_nao_sensivel():
    fontes = [
        FakeNewsSourceProvider(
            "G1", itens=[_item("Grande incendio atinge deposito industrial na zona leste", "G1", "https://g1/inc")]
        ),
        FakeNewsSourceProvider(
            "UOL",
            itens=[_item("Incendio de grandes proporcoes atinge deposito na zona leste", "UOL", "https://uol/inc")],
        ),
        FakeNewsSourceProvider(
            "CNN Brasil",
            itens=[_item("Deposito na zona leste e atingido por grande incendio", "CNN Brasil", "https://cnn/inc")],
        ),
    ]

    executar_ingestao(fontes=fontes, summarization_provider=FakeSummarizationProvider(categoria="cidades"))

    itens = list(NewsItem.objects.all())
    assert len(itens) == 3
    assert all(item.status_revisao == NewsItem.STATUS_PENDENTE for item in itens)
    cluster = NewsCluster.objects.get()
    assert cluster.numero_fontes_distintas == 3


# --- Criterio de aceite 6: registro consultavel por execucao --------------


def test_registro_execucao_ingestao_registra_metricas_observaveis():
    fontes = [
        FakeNewsSourceProvider(
            "G1", itens=[_item("Banco Central eleva taxa de juros para 12%", "G1", "https://g1/juros-a")]
        ),
        FakeNewsSourceProvider(
            "UOL",
            itens=[_item("Banco Central eleva taxa de juros a 12% ao ano", "UOL", "https://uol/juros-a")],
        ),
        FakeNewsSourceProvider("CNN Brasil", erro=FonteIndisponivelError("DNS falhou")),
    ]
    provider = FakeSummarizationProvider()

    registro = executar_ingestao(fontes=fontes, summarization_provider=provider)

    assert isinstance(registro, RegistroExecucaoIngestao)
    assert registro.itens_por_fonte == {"G1": 1, "UOL": 1, "CNN Brasil": 0}
    assert registro.erros_por_fonte == {"CNN Brasil": "DNS falhou"}
    assert registro.total_itens_ingeridos == 2
    assert registro.total_grupos_formados == 1  # os dois itens sao similares -> 1 grupo
    assert registro.total_duplicatas_agrupadas == 1
    # code-review-contract.md run 20260902-0727-ingestao-noticias, 3a
    # passada, Finding 1: cada item e resumido de forma INDEPENDENTE — 2
    # itens no mesmo grupo geram 2 chamadas ao metodo de item-unico do
    # dublê (`provider.chamadas`), nao 1 por grupo/cluster.
    #
    # `registro.chamadas_summarization_provider` mede algo DIFERENTE
    # (reducao de custo/chamadas pedida pelo usuario, posterior a esta
    # correcao): quantas chamadas HTTP EM LOTE `executar_ingestao` fez de
    # fato — os 2 itens cabem no mesmo lote (tamanho padrao 10, ver
    # CATALOGO_NOTICIAS_LLM_TAMANHO_LOTE), entao e 1, mesmo o dublê
    # processando cada item individualmente por dentro (nao sobrescreve
    # `resumir_e_classificar_em_lote`).
    assert provider.chamadas == 2
    assert registro.chamadas_summarization_provider == 1
    assert registro.tokens_utilizados_summarization == 84
    assert registro.custo_estimado_summarization_usd == pytest.approx(0.0024)

    # consultavel depois via banco, nao so em memoria
    do_banco = RegistroExecucaoIngestao.objects.get(pk=registro.pk)
    assert do_banco.total_itens_ingeridos == 2


# --- Criterio de aceite 7: parametros configuraveis sem alteracao de codigo


@override_settings(CATALOGO_NOTICIAS_LIMIAR_FONTES_ALTA_RELEVANCIA=2)
def test_limiar_de_fontes_e_configuravel_via_settings():
    """Com limiar=2 (em vez do default 3), um cluster com 2 fontes ja deve acionar revisao."""
    fontes = [
        FakeNewsSourceProvider(
            "G1", itens=[_item("Nova vacina e aprovada pela agencia reguladora", "G1", "https://g1/vacina")]
        ),
        FakeNewsSourceProvider(
            "UOL",
            itens=[_item("Agencia reguladora aprova nova vacina", "UOL", "https://uol/vacina")],
        ),
    ]

    executar_ingestao(fontes=fontes, summarization_provider=FakeSummarizationProvider(categoria="saude"))

    itens = list(NewsItem.objects.all())
    assert len(itens) == 2
    assert all(item.status_revisao == NewsItem.STATUS_PENDENTE for item in itens)


def test_summarization_provider_falhando_forca_revisao_humana_em_vez_de_publicar():
    """Sem resumo confiavel do provider, o item nunca vai para publicacao automatica."""

    class SummarizationProviderQuebrado(SummarizationProvider):
        def resumir_e_classificar(self, itens_brutos):
            from catalogo_noticias.providers.summarization import SummarizationProviderError

            raise SummarizationProviderError("provedor de LLM fora do ar (simulado)")

    fontes = [
        FakeNewsSourceProvider(
            "G1", itens=[_item("Noticia qualquer sem categoria sensivel", "G1", "https://g1/qualquer")]
        )
    ]

    registro = executar_ingestao(fontes=fontes, summarization_provider=SummarizationProviderQuebrado())

    item = NewsItem.objects.get()
    assert item.status_revisao == NewsItem.STATUS_PENDENTE
    assert item.resumo_proprio == ""
    assert registro.total_itens_ingeridos == 1
