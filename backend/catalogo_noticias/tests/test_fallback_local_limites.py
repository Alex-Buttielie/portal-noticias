"""
INVARIANTE CRITICA DO MERGE P1-01 x P1-02 — o fallback local passa pela
politica de limites de campo.

O problema que este arquivo existe para travar
==============================================
O P1-01 (limites de campo + isolamento de falha na ingestao) construiu
`NewsItem` por UM construtor unico, `_construir_news_item`, que aplica
`services.limites.limitar_textos` antes de qualquer escrita. O defeito que ele
fechou: um `titulo` de 5.000 chars estourava o `varchar(300)` de
`NewsItem.titulo`, o banco devolvia `StringDataRightTruncation`
(`django.db.DataError`) e a RODADA INTEIRA morria.

O P1-02 (fallback local deterministico) entrou depois e criou um NOVO caminho
de producao de `resumo_proprio`: quando o provedor de LLM falha, o texto passa
a ser montado LOCALMENTE por `providers/fallback_local.py::gerar_resumo_local`,
que concatena o `titulo` da fonte entre outras coisas. Esse caminho nao
existia quando o P1-01 desenhou a politica de limites, e o `resumo_proprio`
gerado localmente pode, sozinho, passar do teto de aplicacao.

A INVARIANTE: um item cujo resumo venha do fallback local tem de passar pela
politica de limites de campo do P1-01. Se nao passar, o `DataError` volta e a
rodada inteira morre de novo — exatamente o defeito que o P1-01 fechou. E e por
isso que este merge existe.

Por que isto e um teste de RESOLUCAO DE CONFLITO e nao mais um teste de item
============================================================================
O conflito de merge tinha duas construcoes legitimas e conflitantes de
`NewsItem` em `_persistir_grupo`/`_persistir_grupo_mesclado`: a do P1-01
(construtor unico + limites) e a do P1-02 (inline, para carregar
`tags=_tags_com_origem(resultado)`). A resolucao adotada mantem o construtor
unico e move o marcador para dentro dele. Se alguem, no futuro, reintroduzir a
construcao inline — "só para adicionar uma tag" —, o `resumo_proprio` do
fallback local deixa de ser limitado e a rodada volta a morrer. Estes testes
sao o alarme desse alarme.

O que NAO se prova aqui
=======================
Nao se prova que `verificar_sem_fabricacao` funciona (isso e do P1-02 e tem
`test_fallback_local.py`), nem que a metnica rotulada sobe no fallback e nao
no caminho feliz. Aqui so o caminho do LIMITE.
"""

from __future__ import annotations

import logging
from unittest.mock import patch

import pytest
from django.db import DataError

from catalogo_noticias.models import NewsItem
from catalogo_noticias.providers.fallback_local import (
    MOTIVO_ERRO_DO_PROVIDER,
    gerar_resumo_local,
    motivo_fallback_local,
    origem_fallback_local,
    verificar_sem_fabricacao,
)
from catalogo_noticias.providers.news_source import ItemBruto, NewsSourceProvider
from catalogo_noticias.providers.summarization import (
    SummarizationProvider,
    SummarizationProviderError,
)
from catalogo_noticias.services import limites, telemetria_resumo
from catalogo_noticias.services.ingestao import (
    _construir_news_item,
    executar_ingestao,
)

pytestmark = pytest.mark.django_db

# Tetos lidos da MESMA fonte de verdade do codigo de producao
# (`limites.limite_de` -> `_meta.get_field(campo).max_length`). Nenhum numero
# chutado aqui: se o `max_length` do modelo mudar, o teste mede o limite novo.
TETO_TITULO = limites.limite_de(NewsItem, "titulo")
TETO_RESUMO = limites.limite_de(NewsItem, "resumo_proprio")


class FonteFicticia(NewsSourceProvider):
    """Fonte sem rede: devolve itens pré-montados."""

    def __init__(self, itens, nome="Fonte Enorme"):
        self.nome_fonte = nome
        self._itens = itens

    def buscar_itens(self):
        return list(self._itens)


def _item(titulo: str, url: str, *, fonte: str = "Fonte Enorme", conteudo: str = "") -> ItemBruto:
    return ItemBruto(
        titulo=titulo,
        url_fonte_original=url,
        nome_fonte=fonte,
        conteudo_bruto=conteudo or "Conteudo qualquer da fonte.",
    )


def _item_acima_do_limite(url: str, *, fonte: str = "Fonte Enorme") -> ItemBruto:
    """Item cujo `titulo` esta ACIMA do `varchar(300)` do banco.

    Este e o cenario exato do defeito do P1-01 (`p1-01-defeito-antes.txt`):
    5.000 chars num `CharField(max_length=300)`.
    """
    return _item(
        "Materia real com manchete enorme " + ("X" * 5000),
        url,
        fonte=fonte,
    )


def _rovar(fontes, provider):
    """Roda a ingestao capturing qualquer `DataError` que tentasse escapar."""
    with patch(
        "catalogo_noticias.providers.summarization.SessaoEgress.post",
        side_effect=AssertionError("o fallback local nao pode chamar a rede"),
    ):
        return executar_ingestao(fontes=fontes, summarization_provider=provider)


# ===========================================================================
# 1. O RESUMO DO FALLBACK LOCAL, SOZINHO, JA ESTOURA O TETO
# ===========================================================================


def test_resumo_do_fallback_local_e_capaz_de_estourar_o_teto_de_aplicacao():
    """
    Prova de que o cenario e REAL, e nao teorico.

    Um `titulo` de 5.000 chars entra no `resumo_proprio` do fallback local
    (que concatena o titulo). O `resumo_proprio` e `TextField` — no banco e
    `text`, sem limite — entao quem limita e o teto de aplicacao do P1-01
    (`limites.TETO_RESUMO_PROPRIO_CHARS`). Sem esse limite, o banco aceitaria.
    """
    item = _item_acima_do_limite("https://fonte.test/enorme")

    gerado = gerar_resumo_local(item)
    assert gerado.suficiente is True
    assert len(gerado.resumo) > TETO_RESUMO, (
        "o fallback local tem de produzir um resumo ACIMA do teto para que este "
        "teste signifique alguma coisa"
    )
    # E o que chega ao item antes dos limites e o texto do fallback, nao o vazio.
    assert len(gerado.resumo) > len(item.titulo)


def test_item_do_fallback_local_passa_pelos_limites_antes_de_tocar_o_banco():
    """
    O CONSTRUTOR UNICO aplica os limites a um `ResultadoResumo` que veio do
    fallback local.

    Este e o teste que decide se a resolucao do conflito esta certa: e o
    caminho de construcao que o P1-02 threaten substitua por um `NewsItem(...)`
    inline (sem limites).
    """
    from catalogo_noticias.providers.summarization import ResultadoResumo
    from catalogo_noticias.services.ingestao import _resultado_fallback_local

    item = _item_acima_do_limite("https://fonte.test/enorme")
    resultado = _resultado_fallback_local(item, MOTIVO_ERRO_DO_PROVIDER)
    assert resultado.fallback is True
    assert resultado.motivo_fallback == MOTIVO_ERRO_DO_PROVIDER

    news_item = _construir_news_item(item, resultado, cluster=None)

    # Titulo: TRUNCADO (campo truncavel — perder a cauda e melhor que perder a materia).
    assert len(news_item.titulo) <= TETO_TITULO
    # Resumo do fallback local: TRUNCADO, e continuando com o texto real (nao esvaziado).
    assert len(news_item.resumo_proprio) <= TETO_RESUMO
    assert news_item.resumo_proprio != ""
    # O marcador de origem do P1-02 sobreviveu a passagem pelos limites.
    assert origem_fallback_local(news_item.tags) is True
    assert motivo_fallback_local(news_item.tags) == MOTIVO_ERRO_DO_PROVIDER


# ===========================================================================
# 2. O QUE CHEGA AO BANCO — a prova literal da invariante
# ===========================================================================


def test_item_do_fallback_local_e_persistido_com_campos_limitados_e_sem_dataerror(caplog):
    """
    A PROVA DA INVARIANTE CRITICA.

    O provedor de LLM falha; o item volta pelo fallback local; o `titulo` da
    fonte tem 5.000 chars (muito acima do `varchar(300)`). Resultado exigido:

      - a execucao TERMINA (nenhum `DataError` derruba a rodada);
      - o item do fallback ENTRA no banco;
      - o `titulo` gravado esta DENTRO do `max_length` real do modelo;
      - o `resumo_proprio` gravado esta dentro do teto de aplicacao;
      - o marcador de origem do fallback esta persistido.

    Sem os limites do P1-01, o passo "entra no banco" levanta
    `StringDataRightTruncation` e nada acima acontece.
    """

    class ProvedorForaDoAr(SummarizationProvider):
        def resumir_e_classificar(self, itens_brutos):
            raise SummarizationProviderError(
                "provedor de LLM fora do ar (simulado)",
                motivo=MOTIVO_ERRO_DO_PROVIDER,
            )

    item_enorme = _item_acima_do_limite("https://fonte.test/enorme")
    fontes = [FonteFicticia([item_enorme])]

    with caplog.at_level(logging.ERROR):
        registro = _rovar(fontes, ProvedorForaDoAr())

    # 1. A execucao NAO morreu: ha registro, e o item foi ingerido.
    assert registro is not None
    assert registro.total_itens_ingeridos == 1, (
        "o item do fallback local tem de entrar no banco; se o lote morreu, aqui quebra"
    )

    # 2. O que chegou ao banco tem o campo LIMITADO.
    item = NewsItem.objects.get(url_fonte_original="https://fonte.test/enorme")
    assert len(item.titulo) <= TETO_TITULO
    assert len(item.resumo_proprio) <= TETO_RESUMO
    assert item.titulo != "", "limitar nao pode esvaziar o titulo"
    assert item.resumo_proprio != "", "limitar nao pode esvaziar o resumo"

    # 3. O `max_length` do MODELO (o que o banco realmente cobra) e respeitado.
    assert len(item.titulo) <= NewsItem._meta.get_field("titulo").max_length

    # 4. O marcador de origem do P1-02 sobreviveu ate o banco.
    assert origem_fallback_local(item.tags) is True
    assert motivo_fallback_local(item.tags) == MOTIVO_ERRO_DO_PROVIDER

    # 5. Nenhum `DataError` foi registrado como falha isolada de persistencia.
    motivos = [f["motivo"] for f in registro.erros_por_fonte.values()]
    assert not any("DataError" in m for m in motivos), motivos


def test_item_grande_do_fallback_local_nao_mata_o_resto_do_lote(caplog):
    """
    A combinacao dos dois defeitos, que e o cenario que este merge precisa
    evitar: um item do FALLBACK LOCAL com campo gigante ao lado de itens
    normais.

    Se o fallback local nao passasse pelos limites, este lote inteiro morreria
    e os dois itens bons ficariam de fora do feed.
    """

    class ProvedorForaDoAr(SummarizationProvider):
        def resumir_e_classificar(self, itens_brutos):
            raise SummarizationProviderError(
                "provedor de LLM fora do ar (simulado)",
                motivo=MOTIVO_ERRO_DO_PROVIDER,
            )

    fontes = [
        FonteFicticia(
            [
                _item_acima_do_limite("https://fonte.test/enorme"),
                _item("Materia boa um", "https://fonte.test/boa-1"),
                _item("Materia boa dois", "https://fonte.test/boa-2"),
            ],
            nome="Fonte Mista",
        )
    ]

    with caplog.at_level(logging.ERROR):
        registro = _rovar(fontes, ProvedorForaDoAr())

    # Os TRES entraram: o item gigante foi limitado, nao recusado.
    assert NewsItem.objects.count() == 3
    assert registro.total_itens_ingeridos == 3

    grande = NewsItem.objects.get(url_fonte_original="https://fonte.test/enorme")
    assert len(grande.titulo) <= TETO_TITULO

    # E os dois bons estao no feed, como noticia normal.
    for url in ("https://fonte.test/boa-1", "https://fonte.test/boa-2"):
        assert NewsItem.objects.filter(url_fonte_original=url).exists()


# ===========================================================================
# 3. A INVARIANTE NAO DEPENDE DE O FALLBACK SER "PEQUENO"
# ===========================================================================


def test_teto_de_aplicacao_do_resumo_e_o_que_impede_o_dataerror_do_resumo_local():
    """
    Fecha o raciocinio do item 1 num so lugar: mede o `resumo_proprio` do
    fallback local contra o teto, e prova que o valor que o construtor entrega
    cabe.

    Sem este teste, um `TETO_RESUMO_PROPRIO_CHARS` que alguem acabasse de
    aumentar (ou um `max_length` alterado no modelo) passaria despercebido
    ate o dia em que o `DataError` voltasse em producao.
    """
    item = _item_acima_do_limite("https://fonte.test/enorme")
    gerado = gerar_resumo_local(item)

    # O texto bruto do fallback e maior que o teto...
    assert len(gerado.resumo) > TETO_RESUMO
    # ...e o que o construtor entrega cabe.
    from catalogo_noticias.services.ingestao import _resultado_fallback_local

    news_item = _construir_news_item(
        item, _resultado_fallback_local(item, MOTIVO_ERRO_DO_PROVIDER), cluster=None
    )
    assert len(news_item.resumo_proprio) <= TETO_RESUMO
    # O limite e truncagem com elipse, nao corte cego: o comeco do texto (que
    # e o que o leitor ve no card) sobrevive.
    assert news_item.resumo_proprio.startswith("Materia real com manchete enorme")


def test_verificar_sem_fabricacao_continua_sendo_chamado_em_toda_geracao(monkeypatch):
    """
    O fallback local nao pode fabricar fato — e a verificacao nao pode ser
    contornada por este merge.

    Este teste nao reimplementa a regra anti-fabricacao (ela e do P1-02 e tem
    cobertura propria em `test_fallback_local.py`); ele trava o ponto de
    chamada: `gerar_resumo_local` SEMPRE passa por
    `verificar_sem_fabricacao`, mesmo quando o material de origem e enorme e
    vai ser truncado logo depois.
    """
    chamadas: list[str] = []
    original = verificar_sem_fabricacao

    def _espiao(resumo, item):
        chamadas.append(resumo)
        return original(resumo, item)

    monkeypatch.setattr(
        "catalogo_noticias.providers.fallback_local.verificar_sem_fabricacao", _espiao
    )

    item = _item_acima_do_limite("https://fonte.test/enorme")
    gerado = gerar_resumo_local(item)

    assert gerado.suficiente is True
    assert chamadas, "gerar_resumo_local tem de chamar verificar_sem_fabricacao"
    # `conteudo_bruto`/`conteudo_completo` seguem EXCLUIDOS do resumo: o texto
    # integral vai na pagina de detalhe, com credito e link.
    assert "Conteudo qualquer da fonte." not in gerado.resumo
    assert verificar_sem_fabricacao(gerado.resumo, item) == []


def test_resumo_truncado_do_fallback_ainda_nao_fabrica_fato():
    """
    A truncagem NAO pode introduzir materia nova.

    A verificacao anti-fabricacao roda na GERACAO (`gerar_resumo_local`), e a
    truncagem roda DEPOIS, no construtor. A propriedade que interessa aqui e
    exatamente essa ordem: cortar um texto verificado so pode REMOVER conteudo,
    nunca acrescentar — entao o que chega ao banco e um prefixo do texto
    verificado (mais a elipse do corte).

    NOTA: nao se roda `verificar_sem_fabricacao` sobre o texto JA TRUNCADO.
    A verificacao compara PALAVRAS inteiras contra o material de origem, e o
    corte pode partir uma palavra ao meio (o titulo de teste e uma corrida de
    `X`), produzindo um falso positivo que nao indica fabricacao nenhuma. Isso
    foi observado por este proprio teste e e a raza de a verificacao viver na
    geracao, e nao na persistencia.
    """
    item = _item_acima_do_limite("https://fonte.test/enorme")
    from catalogo_noticias.services.ingestao import _resultado_fallback_local

    resultado = _resultado_fallback_local(item, MOTIVO_ERRO_DO_PROVIDER)
    # O texto GERADO e verificado (nenhuma palavra nem digito inventado).
    assert verificar_sem_fabricacao(resultado.resumo, item) == []

    news_item = _construir_news_item(item, resultado, cluster=None)

    # O que chegou ao banco e o texto gerado, cortado — nada acrescentado.
    assert len(news_item.resumo_proprio) <= TETO_RESUMO
    sem_elipse = news_item.resumo_proprio.removesuffix(limites.SUFIXO_ELLIPSIS)
    assert sem_elipse == resultado.resumo[: len(sem_elipse)]
    # O corte e o unico motivo de a diferenca existir: sem o limite, o texto
    # verificado inteiro chegaria intacto.
    assert resultado.resumo not in news_item.resumo_proprio
    assert news_item.resumo_proprio.startswith("Materia real com manchete enorme")


# ===========================================================================
# 4. A METRICA: SOBE NO FALLBACK, NAO SOBE NO CAMINHO FELIZ
# ===========================================================================


def test_metrica_de_fallback_sobe_neste_cenario_e_e_rotulada(caplog):
    """
    O item grande do fallback local tem de contar na metrica rotulada, com o
    motivo — e nao virar um silencio. Um "sistema degradado que parece saudavel"
    era parte do defeito do P1-02.
    """
    telemetria_resumo.zerar()

    class ProvedorForaDoAr(SummarizationProvider):
        def resumir_e_classificar(self, itens_brutos):
            raise SummarizationProviderError(
                "provedor de LLM fora do ar (simulado)",
                motivo=MOTIVO_ERRO_DO_PROVIDER,
            )

    _rovar([FonteFicticia([_item_acima_do_limite("https://fonte.test/enorme")])], ProvedorForaDoAr())

    snap = telemetria_resumo.snapshot()
    assert snap["fallback"][MOTIVO_ERRO_DO_PROVIDER] == 1
    # E no caminho feliz nao sobe (o provedor respondeu).
    assert snap["sucesso"]["total"] == 0


# ===========================================================================
# 5. O CONSTRUTOR UNICO (a causa raiz da invariante)
# ===========================================================================


def test_news_item_e_construido_em_um_unico_lugar_do_pipeline():
    """
    Se `NewsItem(...)` voltar a aparecer em dois pontos do pipeline, a
    invariante deste arquivo passa a depender de qual ponto rodou — e um dos
    dois nao vai aplicar limites. Este teste e o trava-fusivel.

    A contagem e feita sobre o CODIGO (via `ast`), e nao por `grep`: um
    `NewsItem(` dentro de um comentario ou de uma string nao e uma segunda
    construcao, e um `NewsItem` importado/apelido tambem nao conta.
    """
    import ast
    import pathlib

    caminho = pathlib.Path(__file__).resolve().parents[1] / "services" / "ingestao.py"
    arvore = ast.parse(caminho.read_text(encoding="utf-8"))

    construcoes: list[str] = []
    for no in ast.walk(arvore):
        if not isinstance(no, ast.Call):
            continue
        func = no.func
        if isinstance(func, ast.Name) and func.id == "NewsItem":
            construcoes.append(f"NewsItem() na linha {no.lineno}")

    # O unico ponto de construcao e o construtor unico do P1-01, que aplica
    # `limites.limitar_textos`. Nem `_persistir_grupo` nem
    # `_persistir_grupo_mesclado` podem construir um `NewsItem` por conta propria.
    assert len(construcoes) == 1, (
        f"o pipeline deve construir `NewsItem` em UM unico lugar (o construtor "
        f"que aplica os limites); foram encontrados {len(construcoes)}: {construcoes}"
    )
    assert construcoes[0].endswith(f"linha {_linha_do_construtor_unico()}"), construcoes


def _linha_do_construtor_unico() -> int:
    """Linha do `NewsItem(` que esta DENTRO de `_construir_news_item`."""
    import ast
    import pathlib

    caminho = pathlib.Path(__file__).resolve().parents[1] / "services" / "ingestao.py"
    arvore = ast.parse(caminho.read_text(encoding="utf-8"))
    for no in ast.walk(arvore):
        if isinstance(no, ast.FunctionDef) and no.name == "_construir_news_item":
            for interno in ast.walk(no):
                if (
                    isinstance(interno, ast.Call)
                    and isinstance(interno.func, ast.Name)
                    and interno.func.id == "NewsItem"
                ):
                    return interno.lineno
    raise AssertionError("nenhuma construcao de NewsItem dentro de _construir_news_item")


def test_ambos_os_caminhos_de_persistencia_passam_pelo_construtor_unico():
    """
    `_persistir_grupo` e `_persistir_grupo_mesclado` chamam
    `_construir_news_item` — nenhum dos dois constroi `NewsItem` por conta.
    """
    import ast
    import pathlib

    caminho = pathlib.Path(__file__).resolve().parents[1] / "services" / "ingestao.py"
    arvore = ast.parse(caminho.read_text(encoding="utf-8"))

    por_funcao: dict[str, list[str]] = {}
    for no in ast.walk(arvore):
        if not isinstance(no, ast.FunctionDef):
            continue
        chamadas = [
            interno.func.id
            for interno in ast.walk(no)
            if isinstance(interno, ast.Call)
            and isinstance(interno.func, ast.Name)
        ]
        if "_construir_news_item" in chamadas or "NewsItem" in chamadas:
            por_funcao[no.name] = chamadas

    for funcao in ("_persistir_grupo", "_persistir_grupo_mesclado"):
        assert funcao in por_funcao, f"{funcao} naoFound — ver a arvore"
        chamadas = por_funcao[funcao]
        assert "_construir_news_item" in chamadas, (
            f"{funcao} tem de passar pelo construtor unico (que aplica os limites)"
        )
        assert "NewsItem" not in chamadas, (
            f"{funcao} constroi `NewsItem` diretamente, contornando os limites: "
            f"{chamadas}"
        )


# ===========================================================================
# 6. DataError CRESCO: o limite e mesmo o que segura o banco
# ===========================================================================


def test_sem_os_limites_o_item_do_fallback_local_estouraria_o_varchar(caplog):
    """
    Prova causal de que o limite (e nao outra coisa) e o que segura o banco.

    Faz o INSERT SEM passar por `limites.limitar_textos` e mostra que o banco
    recusa com `DataError`. Se este teste deixar de estourar, o motivo do
    `DataError` mudou e a politica de limites precisa ser revista.

    Este e o teste que o item 1 torna credivel: sem ele, "o banco aceitou" seria
    indistinguivel de "o limite funcionou".
    """
    item = _item_acima_do_limite("https://fonte.test/enorme")
    assert len(item.titulo) > TETO_TITULO

    sem_limite = NewsItem(
        titulo=item.titulo,
        resumo_proprio=gerar_resumo_local(item).resumo,
        url_fonte_original="https://fonte.test/enorme",
        nome_fonte=item.nome_fonte,
    )
    with pytest.raises(DataError):
        sem_limite.save()
