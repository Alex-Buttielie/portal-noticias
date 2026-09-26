"""
P1-01 (WS-08, gate GP-5) — ingestao: limites de campo e isolamento de falha.

Criterio de saida do backlog:

    "Valores grandes nao causam ``DataError``; erro nao aborta todos os grupos"

Os limites NAO sao chutados neste arquivo: sao lidos do proprio modelo
(`NewsItem._meta.get_field(...).max_length` / `NewsCluster._meta...`), que e a
mesma fonte de verdade usada por `services/limites.py`. Se o `max_length` do
modelo mudar, estes testes passam a medir o limite novo sem edicao aqui.

Cada teste abaixo documenta o defeito que ele prova. Os testes marcados
`regressao` falhavam na base `06745d1` (ver
`docs/evidencias/p1-01-defeito-antes.txt`).
"""

from __future__ import annotations

import logging
import unicodedata
from unittest.mock import patch

import pytest
from django.db import DataError

from catalogo_noticias.models import NewsCluster, NewsItem
from catalogo_noticias.providers.news_source import (
    TETO_CONTEUDO_COMPLETO_CHARS,
    ItemBruto,
)
from catalogo_noticias.providers.summarization import (
    ResultadoResumo,
    SummarizationProvider,
)
from catalogo_noticias.services.ingestao import executar_ingestao

pytestmark = pytest.mark.django_db

# ---------------------------------------------------------------------------
# Limites REAIS do modelo (fonte de verdade, nao numeros chutados)
# ---------------------------------------------------------------------------


def _limite(modelo, campo: str) -> int:
    limite = modelo._meta.get_field(campo).max_length
    assert limite is not None, f"{modelo.__name__}.{campo} nao tem max_length"
    return limite


LIMITE_TITULO = _limite(NewsItem, "titulo")
LIMITE_URL = _limite(NewsItem, "url_fonte_original")
LIMITE_NOME_FONTE = _limite(NewsItem, "nome_fonte")
LIMITE_CATEGORIA = _limite(NewsItem, "categoria")
LIMITE_PAIS = _limite(NewsItem, "pais")
LIMITE_ESTADO = _limite(NewsItem, "estado")
LIMITE_IMAGEM_URL = _limite(NewsItem, "imagem_url")
LIMITE_TITULO_CLUSTER = _limite(NewsCluster, "titulo_acontecimento")
LIMITE_CATEGORIA_CLUSTER = _limite(NewsCluster, "categoria_dominante")

# Um valor comfortavelmente acima de qualquer varchar do modelo: 5000 chars
# estoura titulo(300), categoria(100) e titulo_acontecimento(300).
VALOR_ENORME = 5000


# ---------------------------------------------------------------------------
# Doubles
# ---------------------------------------------------------------------------


class _Fonte:
    """Fonte falsa minima: devolve os `ItemBruto` que recebeu."""

    def __init__(self, nome_fonte: str, itens: list[ItemBruto]):
        self.nome_fonte = nome_fonte
        self.itens = itens

    def buscar_itens(self) -> list[ItemBruto]:
        return list(self.itens)


class _ResumoConfiavel(SummarizationProvider):
    def resumir_e_classificar(self, itens_brutos):
        return ResultadoResumo(
            resumo=f"Resumo proprio do item {itens_brutos[0].url_fonte_original}.",
            categoria="cidades",
        )


class _ResumoComCategoria(SummarizationProvider):
    """Provider que devolve a categoria que o teste pedir."""

    def __init__(self, categoria: str):
        self.categoria = categoria

    def resumir_e_classificar(self, itens_brutos):
        return ResultadoResumo(
            resumo="Resumo proprio e legitimo do item.",
            categoria=self.categoria,
        )


def _item(
    titulo: str = "Materia legitima sobre a cidade",
    url: str = "https://fonte.test/noticia",
    fonte: str = "Fonte Boa",
    **extra,
) -> ItemBruto:
    base = dict(
        titulo=titulo,
        url_fonte_original=url,
        nome_fonte=fonte,
        conteudo_bruto="Conteudo bruto da fonte.",
    )
    base.update(extra)
    return ItemBruto(**base)


def _rodar(fontes, provider=None):
    return executar_ingestao(fontes=fontes, summarization_provider=provider or _ResumoConfiavel())


# ===========================================================================
# 1. ROBUSTEZ DE CAMPO — valor grande nunca pode estourar o varchar
# ===========================================================================


def test_regressao_titulo_enorme_nao_derruba_a_execucao_nem_os_itens_validos(caplog):
    """REGRESSAO (falhava na base): um titulo de 5000 chars estourava
    ``varchar(300)`` de ``NewsItem.titulo`` com ``django.db.DataError`` que
    PROPAGAVA de ``executar_ingestao`` e matava a execucao inteira — a fonte
    boa, subsequente, nunca era ingerida.

    Prova: os DOIS itens entram no banco e o titulo grande fica dentro do
    `max_length` real.
    """
    fontes = [
        _Fonte(
            "Fonte Gigante",
            [_item(titulo="X" * VALOR_ENORME, url="https://gigante.test/1", fonte="Fonte Gigante")],
        ),
        _Fonte("Fonte Boa", [_item(titulo="Materia boa", url="https://boa.test/1")]),
    ]

    with caplog.at_level(logging.ERROR):
        registro = _rodar(fontes)

    assert NewsItem.objects.count() == 2
    grande = NewsItem.objects.get(url_fonte_original="https://gigante.test/1")
    assert len(grande.titulo) <= LIMITE_TITULO
    assert NewsItem.objects.filter(url_fonte_original="https://boa.test/1").exists()
    assert registro.total_itens_ingeridos == 2


def test_regressao_url_enorme_e_registrada_sem_derrubar_o_resto(caplog):
    """REGRESSAO (falhava na base): ``url_fonte_original`` e
    ``varchar(1000) unique`` e vinha do RSS sem teto. Uma URL de 5000 chars
    estourava o banco.

    URL nao pode ser truncada: truncar uma URL produz uma URL DIFERENTE e
    errada (rastreabilidade — BRD secao 18). O item e DESCARTADO e a falha
    fica registrada com fonte + item + motivo; os demais itens persistem.
    """
    url_enorme = "https://enorme.test/" + "p" * VALOR_ENORME
    fontes = [
        _Fonte("Fonte Url Enorme", [_item(url=url_enorme, fonte="Fonte Url Enorme")]),
        _Fonte("Fonte Boa", [_item(titulo="Materia boa", url="https://boa.test/ok")]),
    ]

    with caplog.at_level(logging.ERROR):
        registro = _rodar(fontes)

    assert not NewsItem.objects.filter(nome_fonte="Fonte Url Enorme").exists()
    assert NewsItem.objects.filter(url_fonte_original="https://boa.test/ok").exists()

    # O erro tem que estar REGISTRADO (nao engolido): com fonte, item e motivo.
    registro_erros = registro.erros_por_fonte
    assert registro_erros, "a falha do item precisa aparecer no registro da execucao"
    texto_erro = " ".join(f"{k} {v}" for k, v in registro_erros.items())
    assert "Fonte Url Enorme" in texto_erro
    assert str(LIMITE_URL) in texto_erro, "o motivo precisa citar o limite real do campo"
    assert any(r.levelno >= logging.ERROR for r in caplog.records)


def test_regressao_categoria_enorme_do_llm_nao_derruba_a_execucao(caplog):
    """REGRESSAO (falhava na base): a categoria devolvida pelo
    ``SummarizationProvider`` ia crua para ``NewsItem.categoria``
    (``varchar(100)``). Um provider que devolve 500 chars derrubava a execucao
    inteira. O LLM nao e uma fonte confiavel de tamanho.
    """
    fontes = [
        _Fonte("Fonte Boa", [_item(titulo="Materia boa", url="https://boa.test/cat")]),
    ]

    with caplog.at_level(logging.ERROR):
        _rodar(fontes, provider=_ResumoComCategoria("C" * VALOR_ENORME))

    assert NewsItem.objects.count() == 1
    assert len(NewsItem.objects.get().categoria) <= LIMITE_CATEGORIA


def test_regressao_categoria_enorme_vinda_do_rss_nao_derruba_a_execucao():
    """REGRESSAO (falhava na base): a categoria tambem vem do RSS (tag do
    feed, `news_source.py`), caminho independente do LLM.
    """
    fontes = [
        _Fonte(
            "Fonte Tag Gigante",
            [
                _item(
                    titulo="Materia com tag gigante",
                    url="https://tag.test/1",
                    fonte="Fonte Tag Gigante",
                    categoria="T" * VALOR_ENORME,
                )
            ],
        )
    ]

    _rodar(fontes)

    assert NewsItem.objects.count() == 1
    assert len(NewsItem.objects.get().categoria) <= LIMITE_CATEGORIA


def test_regressao_imagem_url_enorme_e_descartada_sem_derrubar_o_item():
    """REGRESSAO (falhava na base): ``imagem_url`` e ``varchar(1000)``.
    Uma URL de imagem truncada seria uma URL quebrada, entao o campo e
    DESCARTADO (vira vazio) e o item segue sem imagem — a materia entra.
    """
    fontes = [
        _Fonte(
            "Fonte Imagem",
            [
                _item(
                    titulo="Materia com imagem gigante",
                    url="https://img.test/1",
                    imagem_url="https://img.test/" + "i" * VALOR_ENORME,
                )
            ],
        )
    ]

    _rodar(fontes)

    item = NewsItem.objects.get()
    assert item.imagem_url == ""
    assert item.url_fonte_original == "https://img.test/1"


def test_regressao_nome_fonte_e_localidade_enormes_sao_limitados():
    """REGRESSAO (falhava na base): ``nome_fonte`` (150), ``pais`` e
    ``estado`` (100) vinham do config do provider sem teto.
    """
    fontes = [
        _Fonte(
            "F" * VALOR_ENORME,
            [
                _item(
                    titulo="Materia com recorte enorme",
                    url="https://recorte.test/1",
                    fonte="F" * VALOR_ENORME,
                    pais_fonte="P" * VALOR_ENORME,
                    estado_fonte="E" * VALOR_ENORME,
                )
            ],
        )
    ]

    _rodar(fontes)

    item = NewsItem.objects.get()
    assert len(item.nome_fonte) <= LIMITE_NOME_FONTE
    assert len(item.pais) <= LIMITE_PAIS
    assert len(item.estado) <= LIMITE_ESTADO


def test_regressao_titulo_de_cluster_enorme_nao_derruba_a_execucao():
    """REGRESSAO (falhava na base): quando um grupo tem 2+ fontes, o titulo do
    primeiro item vira ``NewsCluster.titulo_acontecimento``
    (``varchar(300)``) em `_persistir_grupo`. Titulo enorme estourava o banco
    e matava a execucao — sem NENHUM `NewsItem` ser criado.
    """
    titulo_gigante = "G" * VALOR_ENORME
    fontes = [
        _Fonte("Fonte A", [_item(titulo=titulo_gigante, url="https://a.test/1", fonte="Fonte A")]),
        _Fonte("Fonte B", [_item(titulo=titulo_gigante, url="https://b.test/1", fonte="Fonte B")]),
    ]

    _rodar(fontes)

    assert NewsItem.objects.count() == 2
    cluster = NewsCluster.objects.get()
    assert len(cluster.titulo_acontecimento) <= LIMITE_TITULO_CLUSTER


def test_regressao_categoria_dominante_enorme_no_cluster_nao_derruba_a_execucao():
    """REGRESSAO (falhava na base): ``categoria_dominante`` do cluster tambem e
    ``varchar(100)`` e vinha da categoria (ja sem limite) do provider.
    """
    fontes = [
        _Fonte(
            "Fonte A",
            [_item(titulo="Fato um", url="https://a.test/1", fonte="Fonte A")],
        ),
        _Fonte(
            "Fonte B",
            [_item(titulo="Fato um", url="https://b.test/1", fonte="Fonte B")],
        ),
    ]

    _rodar(fontes, provider=_ResumoComCategoria("D" * VALOR_ENORME))

    cluster = NewsCluster.objects.get()
    assert len(cluster.categoria_dominante) <= LIMITE_CATEGORIA_CLUSTER


# ---------------------------------------------------------------------------
# 1b. Limite exato — sem off-by-one: valor == max_length passa intacto
# ---------------------------------------------------------------------------


def test_campo_exatamente_no_limite_passa_intacto(caplog):
    """Valor de tamanho EXATAMENTE igual ao ``max_length`` nao pode ser
    alterado: nem truncado, nem rejeitado. Prova que o limite esta no
    ponto certo (``<=`` e nao ``<``) — um off-by-one aqui perderia a ultima
    letra de um titulo legitimo.
    """
    titulo_no_limite = "T" * LIMITE_TITULO
    fontes = [_Fonte("Fonte Limite", [_item(titulo=titulo_no_limite, url="https://limite.test/1")])]

    with caplog.at_level(logging.ERROR):
        _rodar(fontes)

    assert NewsItem.objects.get().titulo == titulo_no_limite


def test_url_exatamente_no_limite_e_aceita():
    """URL de tamanho exatamente ``max_length`` e aceita (o limite so bites
    acima dele)."""
    url_no_limite = "https://limite.test/" + "u" * (LIMITE_URL - len("https://limite.test/"))
    assert len(url_no_limite) == LIMITE_URL
    fontes = [_Fonte("Fonte Limite", [_item(url=url_no_limite)])]

    _rodar(fontes)

    assert NewsItem.objects.filter(url_fonte_original=url_no_limite).exists()


def test_um_caractere_acima_do_limite_e_o_unico_que_muda():
    """Contraprova do off-by-one: com ``max_length + 1`` chars, o que sobra
    e o sufixo de elipse — o resto do texto continua identico.
    """
    titulo = "A" * LIMITE_TITULO + "B"
    fontes = [_Fonte("Fonte Limite", [_item(titulo=titulo, url="https://limite.test/2")])]

    _rodar(fontes)

    guardado = NewsItem.objects.get().titulo
    assert len(guardado) == LIMITE_TITULO
    assert guardado.startswith("A" * 10)
    assert not guardado.endswith("B")


# ---------------------------------------------------------------------------
# 1c. Truncagem nao quebra encoding / nao produz HTML malformado
# ---------------------------------------------------------------------------


def test_truncagem_nao_parte_sequencia_multiponto_de_grafema():
    """Cortar no meio de um cluster de grafemas (emoji ZWJ, bandeira com 2
    regional indicators, letra + acento combinante) produz glifo quebrado.

    Este teste prova que a truncagem RECUA ate um ponto seguro: o texto
    guardado e UTF-8 valido, nao termina em caractere combinante/ZWJ e nao
    deixa uma bandeira pela metade.
    """
    titulo = ("\U0001f468‍\U0001f469‍\U0001f467 " * 200) + "F" * LIMITE_TITULO
    fontes = [_Fonte("Fonte Emoji", [_item(titulo=titulo, url="https://emoji.test/1")])]

    _rodar(fontes)

    guardado = NewsItem.objects.get().titulo
    assert len(guardado) <= LIMITE_TITULO
    # Ultimo caractere nunca e combinante (Mn/Me), ZWJ (Cf) nem regional
    # indicator (o primeiro de uma bandeira de 2 pontos de codigo).
    ultimo = guardado[-1]
    assert unicodedata.category(ultimo) not in {"Mn", "Me", "Cf"}, f"cortou em {ultimo!r}"
    assert not 0x1F1E6 <= ord(ultimo) <= 0x1F1FF, "deixou bandeira pela metade"
    # E o round-trip pelo banco (utf8) devolve exatamente o mesmo texto.
    assert guardado.encode("utf-8").decode("utf-8") == guardado
    NewsItem.objects.get().refresh_from_db()
    assert NewsItem.objects.get().titulo == guardado


def test_html_com_script_no_titulo_e_neutralizado_antes_de_persistir():
    """REGRESSAO (falhava na base): o titulo do RSS ia CRU para o banco.
    ``<script>alert('xss')</script>`` ficava literalmente em
    ``NewsItem.titulo`` — e esse titulo chega ao
    ``<script type="application/ld+json">`` do frontend via
    ``JSON.stringify`` (que nao escapa ``<``/``/``), ou seja, vetor de XSS
    armazenado. A ingestao tem de gravar TEXTO, nao markup.
    """
    titulo_malicioso = "<script>alert('xss')</script>Titulo da materia"
    fontes = [
        _Fonte(
            "Fonte Hostil",
            [_item(titulo=titulo_malicioso, url="https://hostil.test/1", fonte="Fonte Hostil")],
        )
    ]

    _rodar(fontes)

    guardado = NewsItem.objects.get().titulo
    assert "<script" not in guardado.lower()
    assert "</script>" not in guardado.lower()
    assert "alert(" not in guardado
    assert "Titulo da materia" in guardado, "o texto legitimo precisa sobreviver"


def test_html_com_script_no_resumo_do_llm_e_neutralizado():
    """O mesmo vale para o ``resumo_proprio``: um provider que devolve HTML
    (o proprio LLM ecoando markup) nao pode gravar markup renderizavel.
    """
    class _ResumoHostil(SummarizationProvider):
        def resumir_e_classificar(self, itens_brutos):
            return ResultadoResumo(
                resumo="<script>alert('xss')</script><b>Resumo</b> legitimo",
                categoria="cidades",
            )

    fontes = [_Fonte("Fonte Boa", [_item(url="https://boa.test/resumo")])]

    _rodar(fontes, provider=_ResumoHostil())

    resumo = NewsItem.objects.get().resumo_proprio
    assert "<script" not in resumo.lower()
    assert "</script>" not in resumo.lower()
    assert "Resumo" in resumo and "legitimo" in resumo


def test_resumo_ou_conteudo_com_tag_desbalanceada_nao_gera_html_malformado_para_render():
    """Uma tag aberta e nunca fechada (ou atributo quebrado) nao pode virar
    texto que, re-renderizado, producira markup malformado. O que vai para o
    banco e texto puro.
    """
    titulo = 'Titulo com <a href="https://exemplo.test">link sem fechar'
    fontes = [_Fonte("Fonte Quebrada", [_item(titulo=titulo, url="https://quebrada.test/1")])]

    _rodar(fontes)

    guardado = NewsItem.objects.get().titulo
    assert "<" not in guardado and ">" not in guardado
    assert "link sem fechar" in guardado


# ---------------------------------------------------------------------------
# 2. ISOLAMENTO DE FALHA — um item/grupo ruim nao derruba os demais
# ===========================================================================


def test_regressao_item_invalido_no_meio_de_lote_valido_nao_derruba_o_lote(caplog):
    """REGRESSAO (falhava na base): um unico item com URL enorme no MEIO de
    um lote de itens validos derrubava a execucao inteira (``DataError`` no
    ``bulk_create`` do grupo) — zero dos itens validos eram persistidos.

    Prova: os validos entram, o invalido NAO entra, e a falha fica
    registrada com fonte, item e motivo.
    """
    url_enorme = "https://invalido.test/" + "x" * VALOR_ENORME
    fontes = [
        _Fonte(
            "Fonte Mista",
            [
                _item(titulo="Primeira materia valida", url="https://mista.test/1", fonte="Fonte Mista"),
                _item(titulo="Materia invalida", url=url_enorme, fonte="Fonte Mista"),
                _item(titulo="Terceira materia valida", url="https://mista.test/3", fonte="Fonte Mista"),
            ],
        )
    ]

    with caplog.at_level(logging.ERROR):
        registro = _rodar(fontes)

    # Os DOIS validos entraram: o invalido do meio nao os levou junto.
    assert NewsItem.objects.filter(
        url_fonte_original__in=["https://mista.test/1", "https://mista.test/3"]
    ).count() == 2
    assert NewsItem.objects.filter(nome_fonte="Fonte Mista").count() == 2
    assert registro.erros_por_fonte, "o item invalido tem de aparecer no placar de falha"
    assert any(
        "Fonte Mista" in k or "Fonte Mista" in str(v)
        for k, v in registro.erros_por_fonte.items()
    )


def test_regressao_grupo_inteiro_invalido_nao_derruba_os_outros_grupos(caplog):
    """REGRESSAO (falhava na base): nem o `_persistir_grupo` era protegido nem o
    provider. Um `RuntimeError` inesperado (nao `SummarizationProviderError`)
    dentro do provider derrubava `executar_ingestao` e TODOS os grupos
    restantes nunca eram processados.

    Aqui o item de uma fonte INTEIRA falha e provamos que os outros grupos
    seguem; o item que falhou entra em revisao humana (nunca publicado
    automaticamente — comportamento ja.documentado do
    `_resultado_fallback_erro`), e a falha fica registrada.
    """
    class _ProviderQueFalhaEmUmItem(SummarizationProvider):
        """Falha (erro generico, nao `SummarizationProviderError`) ao resumir
        um item especifico — o caso de erro inesperado que escapava."""

        def resumir_e_classificar(self, itens_brutos):
            if "estoura" in itens_brutos[0].url_fonte_original:
                raise RuntimeError("provider explodiu neste item")
            return ResultadoResumo(resumo="Resumo legitimo.", categoria="cidades")

    fontes = [
        _Fonte("Fonte Boa", [_item(titulo="Materia boa um", url="https://boa.test/1", fonte="Fonte Boa")]),
        _Fonte("Fonte Estoura", [_item(titulo="Materia que estoura", url="https://estoura.test/1", fonte="Fonte Estoura")]),
        _Fonte("Fonte Boa 2", [_item(titulo="Materia boa dois", url="https://boa.test/2", fonte="Fonte Boa 2")]),
    ]

    with caplog.at_level(logging.ERROR):
        registro = _rodar(fontes, provider=_ProviderQueFalhaEmUmItem())

    # As DUAS fontes boas entraram: a que falhou nao as levou junto.
    assert NewsItem.objects.filter(
        url_fonte_original__in=["https://boa.test/1", "https://boa.test/2"]
    ).count() == 2
    # O item que falhou nao e perdido: entra em revisao humana, nunca
    # publicado por falta de resumo proprio (BRD secao 18 / AC-4).
    item_com_falha = NewsItem.objects.get(url_fonte_original="https://estoura.test/1")
    assert item_com_falha.status_revisao == NewsItem.STATUS_PENDENTE
    assert not item_com_falha.publicado_automaticamente
    # E a falha de cada fonte/item fica registrada, com motivo.
    assert registro.erros_por_fonte, "a fonte que falhou tem de estar no registro"
    chaves = " ".join(registro.erros_por_fonte)
    assert "Fonte Estoura" in chaves
    assert any(
        "provider explodiu neste item" in str(v) for v in registro.erros_por_fonte.values()
    )


def test_erro_nao_e_engolido_registra_fonte_item_e_motivo(caplog):
    """A excecao NAO pode ser engolida em silencio: tem de aparecer em log de
    nivel ERROR (com traceback) e no registro, identificando fonte, item e
    motivo.
    """
    class _ProviderQueExplode(SummarizationProvider):
        def resumir_e_classificar(self, itens_brutos):
            raise RuntimeError("falha catastrofica do provider")

    fontes = [
        _Fonte("Fonte X", [_item(titulo="Item X", url="https://x.test/1", fonte="Fonte X")]),
        _Fonte("Fonte Y", [_item(titulo="Item Y", url="https://y.test/1", fonte="Fonte Y")]),
    ]

    with caplog.at_level(logging.ERROR):
        registro = _rodar(fontes, provider=_ProviderQueExplode())

    registros_error = [r for r in caplog.records if r.levelno >= logging.ERROR]
    assert registros_error, "erro nao pode ser engolido: nenhum log de ERROR"
    assert any(r.exc_info for r in registros_error), "o log de erro tem que trazer o traceback"
    # `caplog.text` omite registros com `exc_info` nesta versao de pytest;
    # `getMessage()` do record e a fonte confiavel.
    texto = " ".join(r.getMessage() for r in registros_error)
    assert "Fonte X" in texto and "Fonte Y" in texto, (
        "o log de erro tem que identificar a fonte de cada item que falhou"
    )
    assert "falha catastrofica do provider" in texto
    # E o registro da execucao guarda fonte, item e motivo.
    assert registro.erros_por_fonte
    chaves = " ".join(registro.erros_por_fonte)
    assert "Fonte X" in chaves and "Fonte Y" in chaves
    assert all(
        str(v).strip() for v in registro.erros_por_fonte.values()
    ), "nenhuma entrada de falha pode ter motivo vazio"


def test_placar_de_sucesso_e_falha_e_reportado_ao_final(caplog):
    """O item pede um placar de sucesso/falha ao final.

    Duas contagens que NAO podem ser confundidas, e que o placar precisa
    deixar separadas:
      * candidatos — quantos itens novos o lote trouxe (`itens_por_fonte` /
        `total_itens_ingeridos`, semantica preexistente do registro);
      * INGIRIDOS — quantos deles realmente ganharam `pk` no banco.
    A diferenca e a quantidade de itens que o pipeline isolou e recusou.
    """
    url_enorme = "https://grande.test/" + "z" * VALOR_ENORME
    fontes = [
        _Fonte(
            "Fonte Boa",
            [
                _item(titulo="Boa um", url="https://boa.test/1", fonte="Fonte Boa"),
                _item(titulo="Boa dois", url="https://boa.test/2", fonte="Fonte Boa"),
            ],
        ),
        _Fonte("Fonte Ruim", [_item(titulo="Ruim", url=url_enorme, fonte="Fonte Ruim")]),
    ]

    # INFO: o placar de sucesso/falha e logado em nivel INFO (nao e erro), e as
    # falhas que o compoem em ERROR. Precisa capturar os dois.
    with caplog.at_level(logging.INFO):
        registro = _rodar(fontes)

    # Candidatos: 3 (2 bons + 1 recusado). Semantica preexistente, inalterada.
    assert registro.itens_por_fonte["Fonte Boa"] == 2
    assert registro.itens_por_fonte["Fonte Ruim"] == 1
    assert registro.total_itens_ingeridos == 3

    # Sucesso real: so 2 entraram.
    assert NewsItem.objects.count() == 2

    # E o placar de sucesso/falha diz exatamente isso.
    infos = [r.getMessage() for r in caplog.records if r.levelno >= logging.INFO]
    placar = next((m for m in infos if "Placar de ingestao:" in m), None)
    assert placar is not None, "o placar de sucesso/falha tem que ser reportado ao final"
    assert "3 candidato(s)" in placar
    assert "2 INGIRIDO(S)" in placar
    assert "1 recusado(s)/isolado(s)" in placar

    # Falha: registrada com contexto de fonte/item/motivo.
    assert registro.erros_por_fonte
    assert any(
        "Ruim" in k and str(LIMITE_URL) in str(v)
        for k, v in registro.erros_por_fonte.items()
    ), "a falha precisa dizer a fonte e o limite real que foi estourado"


# ---------------------------------------------------------------------------
# 3. IDEMPOTENCIA / DEDUP / MEMORIA
# ===========================================================================


def test_reprocessar_o_mesmo_lote_nao_duplica(caplog):
    """Idempotencia: rodar o MESMO lote duas vezes nao cria duplicata (a
    `url_fonte_original` e unique e a consulta de URLs ja ingeridas filtra).
    """
    fontes = [
        _Fonte(
            "Fonte Boa",
            [
                _item(titulo="Materia um", url="https://idem.test/1"),
                _item(titulo="Materia dois", url="https://idem.test/2"),
            ],
        )
    ]

    _rodar([_Fonte("Fonte Boa", fontes[0].itens)])
    assert NewsItem.objects.count() == 2

    with caplog.at_level(logging.ERROR):
        segunda = _rodar([_Fonte("Fonte Boa", fontes[0].itens)])

    assert NewsItem.objects.count() == 2, "reexecucao duplicou item"
    assert segunda.total_itens_ingeridos == 0
    assert not segunda.erros_por_fonte


def test_reprocessar_item_enorme_que_foi_limitado_nao_cria_duplicata():
    """Idempotencia tambem no caminho ja truncado: reprocessar o mesmo item
    gigante nao duplica nem faz a segunda rodada estourar o banco."""
    fontes_in = lambda: [  # noqa: E731
        _Fonte("Fonte Gigante", [_item(titulo="G" * VALOR_ENORME, url="https://idem-g.test/1", fonte="Fonte Gigante")])
    ]

    _rodar(fontes_in())
    _rodar(fontes_in())

    assert NewsItem.objects.count() == 1
    assert len(NewsItem.objects.get().titulo) <= LIMITE_TITULO


def test_conteudo_bruto_enorme_e_limitado_em_memoria_e_na_persistencia():
    """Um ``conteudo_bruto`` gigante nao pode ser carregado inteiro nem
    persistido inteiro: o RSS e uma fonte externa e nao ha limite no
    ``TextField`` do banco. O teto e explicito e vale para o item.
    """
    from catalogo_noticias.services import limites

    enorme = "B" * 2_000_000
    fontes = [
        _Fonte("Fonte Gigante", [_item(titulo="Materia", url="https://mem.test/1", conteudo_bruto=enorme)])
    ]

    _rodar(fontes)

    assert NewsItem.objects.count() == 1
    assert len(NewsItem.objects.get().conteudo_bruto) <= limites.TETO_CONTEUDO_BRUTO_CHARS


def test_limpar_html_para_texto_e_limitado_antes_de_materializar(monkeypatch):
    """A limpeza de HTML nao pode materializar o blob inteiro: um feed com
    megabytes de HTML era convertido em megabytes de texto e SO DEPOIS
    truncado (``extrair_conteudo_completo``), multiplicando o pico de memoria
    da ingestao. O corte tem de vir ANTES da limpeza, com folga para o
    caso de expansao por entidades (``&nbsp;`` -> 1 char vira 6).
    """
    from catalogo_noticias.providers import news_source as ns

    entrada_html = "<p>" + ("palavra " * 500_000) + "</p>"
    assert len(entrada_html) > 1_000_000

    fornecidos: list[int] = []
    original = ns.limpar_html_para_texto

    def _espiao(html):
        fornecidos.append(len(html))
        return original(html)

    monkeypatch.setattr(ns, "limpar_html_para_texto", _espiao)
    texto = ns.extrair_conteudo_completo(
        type("Entrada", (), {"content": [{"value": entrada_html}], "summary": ""})()
    )

    assert fornecidos, "a limpeza nao foi chamada"
    assert fornecidos[0] <= 8 * TETO_CONTEUDO_COMPLETO_CHARS, (
        f"o HTML de {len(entrada_html)} chars foi entregue inteiro a limpeza "
        f"({fornecidos[0]} chars) — o corte precisa vir antes"
    )
    assert len(texto) <= TETO_CONTEUDO_COMPLETO_CHARS


def test_busca_rss_limita_campos_grandes_no_caminho_do_provider(monkeypatch):
    """O provider tambem precisa de teto, para nao segurar um feed enorme em
    memoria ate o fim da rodada. Confere que um item de RSS com titulo/URL
    gigantes ja sai limitado do `buscar_itens`.
    """
    from unittest.mock import MagicMock, patch

    from catalogo_noticias.providers import news_source as ns

    corpo = (
        "<?xml version='1.0'?><rss version='2.0'><channel><title>F</title>"
        f"<item><title>{'T' * 100_000}</title>"
        f"<link>https://rss.test/{'u' * 100_000}</link>"
        "<description>d</description></item></channel></rss>"
    ).encode("utf-8")
    resposta = MagicMock(status_code=200, content=corpo, headers={})
    resposta.raise_for_status.return_value = None
    provider = ns.RSSNewsSourceProvider(nome_fonte="RSS Gigante", url_feed="https://rss.test/f")

    # O dublê vai em `SessaoEgress.get`, não em `requests.get`: o P0-10
    # (eixo 2, SSRF) trocou a chamada direta por `SessaoEgress`, que valida o
    # destino antes de abrir a conexão. Dublê em `requests.get` deixaria o
    # egress real rodar, ele tentaria resolver `rss.test` e o teste morreria
    # em DNS — muito antes das asserções de limite, que são o que se quer
    # exercitar aqui. As asserções do P1-01 não mudaram: só o ponto onde a
    # rede é fingida.
    with patch.object(ns.SessaoEgress, "get", return_value=resposta):
        itens = provider.buscar_itens()

    assert len(itens) == 0, "URL acima do limite e item inutilizavel: e descartado"


def test_tetos_do_provider_batem_com_o_modelo():
    """Trava de nao-drift (P1-01).

    `providers/news_source.py` NAO importa `django.db.models` (e a camada de
    fonte), entao declara os limites numericos localmente em vez de ler
    `_meta`. Este teste e o que garante que esses numeros nao derivem do DDL:
    se alguem mudar um `max_length` no modelo e nao atualizar o provider, este
    teste falha em vez de o limite do provider ficar silenciosamente errado.
    """
    from catalogo_noticias.providers import news_source as ns

    esperados = {
        "_LIMITE_TITULO": ("NewsItem", "titulo"),
        "_LIMITE_URL": ("NewsItem", "url_fonte_original"),
        "_LIMITE_NOME_FONTE": ("NewsItem", "nome_fonte"),
        "_LIMITE_CATEGORIA": ("NewsItem", "categoria"),
        "_LIMITE_ESTADO": ("NewsItem", "estado"),
        "_LIMITE_PAIS": ("NewsItem", "pais"),
        "_LIMITE_IMAGEM_URL": ("NewsItem", "imagem_url"),
    }
    for nome_constante, (nome_modelo, nome_campo) in esperados.items():
        modelo = {"NewsItem": NewsItem}[nome_modelo]
        assert getattr(ns, nome_constante) == modelo._meta.get_field(nome_campo).max_length, (
            f"{nome_constante} do provider divergiu do max_length real de "
            f"{nome_modelo}.{nome_campo} — atualize os dois lados"
        )
    # Os tetos de TextField nao vem do modelo (sao `text`, sem limite); eles
    # tem de ser IGUAIS aos do servico, para provider e servico concordarem.
    from catalogo_noticias.services import limites as srv

    assert ns._TETO_CONTEUDO_BRUTO == srv.TETO_CONTEUDO_BRUTO_CHARS
    assert ns.TETO_CONTEUDO_COMPLETO_CHARS == srv.TETO_CONTEUDO_COMPLETO_CHARS


def test_url_acima_do_limite_e_descartada_pelo_provider_e_registrada(caplog):
    """O provider descarta a URL gigante com log de WARNING (fonte + tamanho +
    limite), em vez de devolver um item que o servico teria de recusar.
    Truncar a URL fabricaria outra materia, entao descartar e a unica saida
    segura."""
    from unittest.mock import MagicMock, patch

    from catalogo_noticias.providers import news_source as ns

    corpo = (
        "<?xml version='1.0'?><rss version='2.0'><channel><title>F</title>"
        "<item><title>Titulo normal</title>"
        f"<link>https://rss.test/{'u' * 5000}</link>"
        "<description>d</description></item></channel></rss>"
    ).encode("utf-8")
    resposta = MagicMock(status_code=200, content=corpo, headers={})
    resposta.raise_for_status.return_value = None
    provider = ns.RSSNewsSourceProvider(nome_fonte="RSS Url Gigante", url_feed="https://rss.test/f")

    with caplog.at_level(logging.WARNING):
        with patch.object(ns.SessaoEgress, "get", return_value=resposta):
            itens = provider.buscar_itens()

    assert itens == []
    avisos = " ".join(r.getMessage() for r in caplog.records if r.levelno >= logging.WARNING)
    assert "RSS Url Gigante" in avisos
    assert str(LIMITE_URL) in avisos


def test_imagem_url_acima_do_limite_e_descartada_pelo_provider(caplog):
    """Mesma politica para a imagem: URL cortada aponta para recurso
    inexistente, entao o campo e zerado e o item entra sem imagem."""
    from unittest.mock import MagicMock, patch

    from catalogo_noticias.providers import news_source as ns

    corpo = (
        "<?xml version='1.0'?><rss version='2.0'><channel><title>F</title>"
        "<item><title>Titulo normal</title><link>https://rss.test/ok</link>"
        f'<enclosure url="https://img.test/{"i" * 5000}" type="image/jpeg"/>'
        "<description>d</description></item></channel></rss>"
    ).encode("utf-8")
    resposta = MagicMock(status_code=200, content=corpo, headers={})
    resposta.raise_for_status.return_value = None
    provider = ns.RSSNewsSourceProvider(nome_fonte="RSS Imagem", url_feed="https://rss.test/f")

    with caplog.at_level(logging.WARNING):
        with patch.object(ns.SessaoEgress, "get", return_value=resposta):
            itens = provider.buscar_itens()

    assert len(itens) == 1
    assert itens[0].imagem_url == ""
    assert itens[0].titulo == "Titulo normal"
    assert "imagem_url" in " ".join(
        r.getMessage() for r in caplog.records if r.levelno >= logging.WARNING
    )


def test_html_e_entidades_do_rss_viram_texto_no_provider(caplog):
    """O provider ja entrega TEXTO: `<b>` some, `&mdash;`/`&nbsp;` viram
    caractere, e `<script>` nao sobrevive. E o que garante que o servico
    receba conteudo ja saneado mesmo quando um `ItemBruto` vier montado
    fora do RSS."""
    from unittest.mock import MagicMock, patch

    from catalogo_noticias.providers import news_source as ns

    corpo = (
        "<?xml version='1.0'?><rss version='2.0'><channel><title>F</title>"
        "<item><title>&lt;b&gt;Negrito&lt;/b&gt; &amp;mdash; &lt;script&gt;alert(1)&lt;/script&gt;</title>"
        "<link>https://rss.test/texto</link>"
        "<description>Descricao &amp;amp; com &amp;nbsp; entidade.</description>"
        "</item></channel></rss>"
    ).encode("utf-8")
    resposta = MagicMock(status_code=200, content=corpo, headers={})
    resposta.raise_for_status.return_value = None
    provider = ns.RSSNewsSourceProvider(nome_fonte="RSS Texto", url_feed="https://rss.test/f")

    with patch.object(ns.SessaoEgress, "get", return_value=resposta):
        itens = provider.buscar_itens()

    assert len(itens) == 1
    titulo = itens[0].titulo
    assert "<" not in titulo and ">" not in titulo
    assert "script" not in titulo.lower()
    assert "—" in titulo, "entidade &mdash; deve virar o caractere real"
    assert "Negrito" in titulo


def test_corte_do_html_bruto_respeita_fronteira_de_tag():
    """O corte do HTML bruto (antes da limpeza) cai no ultimo `>`, para nao
    deixar markup pela meia — a limpeza transformaria uma tag truncada em
    texto solto sem sentido."""
    from catalogo_noticias.providers import news_source as ns

    bruto = "".join(f"<p>paragrafo {i} com texto suficiente</p>" for i in range(5000))
    cortado = ns._cortar_html_bruto(bruto)
    assert len(cortado) < len(bruto)
    assert cortado.rstrip().endswith(">")
    # Nao deixa tag aberta pela metade.
    assert cortado.count("<") == cortado.count(">")


# ---------------------------------------------------------------------------
# 4. CAMADA DE DEFESA NO BANCO (DataError nunca mais escapa)
# ===========================================================================


def test_data_error_do_banco_nao_propaga_da_persistencia(caplog):
    """Ultima linha de defesa: mesmo que um `DataError` do banco apareca (campo
    novo sem limite, trigger, bug futuro), a persistencia em lote tem que
    isolar a linha ruim em vez de perder o grupo inteiro — e registrar qual
    item foi.

    O `DataError` e injetado de verdade aqui (`DataError` do Django, a mesma
    excecao que o psycopg2 produz).
    """
    from catalogo_noticias.services import ingestao as svc

    itens = [
        NewsItem(titulo="Item ok um", url_fonte_original="https://defesa.test/1", nome_fonte="Fonte"),
        NewsItem(titulo="Item ok dois", url_fonte_original="https://defesa.test/2", nome_fonte="Fonte"),
    ]
    real_bulk_create = NewsItem.objects.bulk_create

    def _bulk_create_que_explode(objs, *args, **kwargs):
        # Simula o banco recusando a PRIMEIRA linha do lote.
        raise DataError("value too long for type character varying(300)")

    with caplog.at_level(logging.ERROR):
        with patch.object(NewsItem.objects, "bulk_create", side_effect=_bulk_create_que_explode):
            resultado = svc._persistir_news_items_em_lote(itens)

    # Nao propagou: a funcao devolveu em vez de estourar a execucao.
    assert resultado == itens
    assert any(r.levelno >= logging.ERROR for r in caplog.records), (
        "o DataError tem de ser registrado, nao engolido em silencio"
    )
    assert real_bulk_create is not None


def test_persistencia_limita_item_montado_fora_do_construtor(caplog):
    """Prova a DEFESA EM PROFUNDIDADE de `_persistir_news_items_em_lote`: um
    `NewsItem` montado direto, sem passar por `_construir_news_item`, ainda e
    limitado na ultima porta antes do INSERT.

    E o que impede o limite de virar "so funciona no caminho feliz": um
    chamador novo (outro servico, script de carga, tarefa futura) herda a
    garantia sem precisar saber que `services.limites` existe.
    """
    from catalogo_noticias.services import ingestao as svc

    # Titulo gigante e `<script>`: nenhum dos dois passou pelo construtor.
    item = NewsItem(
        titulo="<script>alert(1)</script>" + "T" * VALOR_ENORME,
        url_fonte_original="https://defesa.test/backstop",
        nome_fonte="Fonte Backstop",
        conteudo_bruto="<b>bruto</b>",
    )

    with caplog.at_level(logging.ERROR):
        svc._persistir_news_items_em_lote([item])

    assert NewsItem.objects.count() == 1
    guardado = NewsItem.objects.get()
    assert len(guardado.titulo) <= LIMITE_TITULO
    assert "<script" not in guardado.titulo.lower()
    assert guardado.conteudo_bruto == "bruto", "o HTML bruto tambem vira texto"


def test_persistencia_recusa_item_com_url_fora_do_limite_montado_fora_do_construtor(caplog):
    """O outro lado da defesa: um item montado direto com URL gigante NAO pode
    entrar truncado nem derrubar o lote. E descartado, com a falha
    registrada, e os itens valios do mesmo lote entram."""
    from catalogo_noticias.services import ingestao as svc

    url_enorme = "https://defesa.test/" + "q" * VALOR_ENORME
    ruim = NewsItem(
        titulo="Item com URL gigante",
        url_fonte_original=url_enorme,
        nome_fonte="Fonte Backstop",
    )
    bons = [
        NewsItem(
            titulo="Item valido um",
            url_fonte_original="https://defesa.test/bom1",
            nome_fonte="Fonte Backstop",
        ),
        NewsItem(
            titulo="Item valido dois",
            url_fonte_original="https://defesa.test/bom2",
            nome_fonte="Fonte Backstop",
        ),
    ]

    with caplog.at_level(logging.ERROR):
        svc._persistir_news_items_em_lote([ruim, *bons])

    # O ruim nao entrou; os dois bons entraram.
    assert NewsItem.objects.count() == 2
    assert not NewsItem.objects.filter(titulo="Item com URL gigante").exists()
    # E a falha ficou registrada, com motivo e limite.
    erros = [r.getMessage() for r in caplog.records if r.levelno >= logging.ERROR]
    texto = " ".join(erros)
    assert "url_fonte_original" in texto
    assert str(LIMITE_URL) in texto
