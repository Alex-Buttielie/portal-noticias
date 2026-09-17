"""
Extração do texto integral da matéria (`content:encoded` ou summary) para
exibição DENTRO da leitura, sempre com crédito + link (BRD secao 18).
"""

from __future__ import annotations

import pytest

from catalogo_noticias.providers.news_source import (
    TETO_CONTEUDO_COMPLETO_CHARS,
    extrair_conteudo_completo,
    limpar_html_para_texto,
)


class _Entrada:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


def test_prefere_content_encoded_ao_summary():
    entrada = _Entrada(
        content=[{"value": "<p>Texto completo da matéria com vários parágrafos.</p>"}],
        summary="<p>Só um teaser.</p>",
    )

    texto = extrair_conteudo_completo(entrada)

    assert "Texto completo" in texto
    assert "Teaser" not in texto
    assert "<p>" not in texto


def test_fallback_para_summary_quando_sem_content():
    entrada = _Entrada(summary="<p>Resumo do feed com <b>negrito</b>.</p>")

    texto = extrair_conteudo_completo(entrada)

    assert texto == "Resumo do feed com negrito."


def test_remove_script_e_decodifica_entidades():
    html = "<script>alert(1)</script><p>Not&iacute;cia &amp; fato</p>"

    assert limpar_html_para_texto(html) == "Notícia & fato"


def test_vazio_quando_feed_so_traz_titulo():
    assert extrair_conteudo_completo(_Entrada()) == ""


def test_respeita_teto_de_chars():
    entrada = _Entrada(content=[{"value": "<p>" + ("x" * 20000) + "</p>"}])

    texto = extrair_conteudo_completo(entrada)

    assert len(texto) <= TETO_CONTEUDO_COMPLETO_CHARS
    assert len(texto) > 0


@pytest.mark.django_db
def test_ingestao_persiste_conteudo_completo():
    from catalogo_noticias.models import NewsItem

    item = NewsItem.objects.create(
        titulo="T",
        resumo_proprio="R",
        conteudo_bruto="snippet",
        conteudo_completo="Texto integral da matéria.",
        url_fonte_original="https://example.com/conteudo-1",
        nome_fonte="G1",
    )

    assert NewsItem.objects.get(pk=item.pk).conteudo_completo == "Texto integral da matéria."
