"""
Utilitarios de TEXTO puros, sem dependencia de Django nem de models
(P1-01 — workstream WS-08, gate GP-5).

Vem aqui o que o provider RSS e o servico de ingestao precisam calcular
**igualmente** — e nao podem implementar duas vezes, senao os dois
caminhos divergem e um deles volta a ser o "caminho feliz" que so funciona
enquanto o outro nao e exercitado:

* ``limpar_html_para_texto`` — remove ``<script>``/``<style>`` e as demais
  tags, decodifica entidades e colapsa espacos. RSS e LLM sao fontes
  externas: o que vem delas e markup, nao texto.
* ``truncar`` / ``cortar_em_limite_seguro`` — truncagem que respeita
  ``max_length`` de ``varchar(N)`` sem partir cluster de grafemas.

Este modulo nao importa nada do projeto de proposito: assim tanto
``providers/news_source.py`` (camada de fonte) quanto
``services/limites.py`` (camada de servico, que le os limites do MODELO)
podem usar a MESMA implementacao sem ciclo de importacao.
"""

from __future__ import annotations

import logging
import re
import unicodedata
from html.parser import HTMLParser
from typing import Any

logger = logging.getLogger(__name__)

# Elipse de 1 caractere Unicode: "cortar em 300" continua dando exatamente
# 300 caracteres, entao o orcamento do `varchar(N)` do banco nao e furado.
SUFIXO_ELLIPSIS = "…"

# Fator de folga aplicado ANTES de limpar o HTML, para que a limpeza nao
# precise materializar o blob inteiro. Remover tags so SHRINKS o texto, mas a
# expansao de entidades pode INFLAR: 1 caractere vira 6 (`&nbsp;` -> U+00A0) ou
# ate 8 (`&mdash;`). 8x absorve o pior caso de expansao com folga.
FOLGA_ANTES_DE_LIMPAR_HTML = 8


class _StripperDeHtml(HTMLParser):
    """Remove tags HTML mantendo o texto (stdlib, sem dependencia nova)."""

    def __init__(self):
        super().__init__()
        self._partes: list[str] = []

    def handle_data(self, data: str):
        self._partes.append(data)

    def texto(self) -> str:
        return "".join(self._partes)


def limpar_html_para_texto(html: str) -> str:
    """Converte HTML do RSS em texto puro: remove tags/scripts, decodifica
    entidades e colapsa espaços. Nunca lança exceção (best-effort)."""
    import html as _html

    bruto = html or ""
    try:
        sem_script = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", bruto)
        com_quebras = re.sub(r"(?i)<\s*(br|p|div|li|h[1-6])[^>]*>", "\n", sem_script)
        stripper = _StripperDeHtml()
        stripper.feed(com_quebras)
        texto = _html.unescape(stripper.texto())
    except Exception:
        texto = re.sub(r"<[^>]+>", " ", bruto)
    texto = re.sub(r"[ \t\xa0]+", " ", texto)
    texto = re.sub(r"\n\s*\n+", "\n\n", texto)
    return texto.strip()


# ---------------------------------------------------------------------------
# Truncagem que nao quebra encoding
# ---------------------------------------------------------------------------

# Categorias Unicode que nao podem ficar orfas no fim de um texto cortado:
#   Mn/Me = acento combinante ("e" + U+0301 viraria "e" solto e o acento
#           grudado no caractere seguinte);
#   Cf    = formatadores invisiveis, entre eles o ZWJ (U+200D) das sequencias
#           de emoji, que ficaria pendurado apontando para nada;
#   Regional indicators (U+1F1E6..U+1F1FF) formam bandeira em PARES: cortar
#           entre os dois deixa meia bandeira.
_INDICADOR_REGIONAL_INICIO = 0x1F1E6
_INDICADOR_REGIONAL_FIM = 0x1F1FF


def _insegmentavel(caractere: str) -> bool:
    if unicodedata.category(caractere) in {"Mn", "Me", "Cf"}:
        return True
    return _INDICADOR_REGIONAL_INICIO <= ord(caractere) <= _INDICADOR_REGIONAL_FIM


def cortar_em_limite_seguro(texto: str, limite: int) -> str:
    """Corta `texto` em no maximo `limite` caracteres SEM partir um cluster de
    grafemas.

    `len()` em Python conta code points, e o ``character varying(N)`` do
    PostgreSQL tambem conta caracteres (a coluna e ``utf8``, nao bytes) — logo
    `len()` e a unidade correta para o limite do banco. O que `len()` nao
    garante e que o corte caia numa fronteira de grafema: "e" + acento
    combinante, uma bandeira de 2 pontos de codigo, ou um emoji ligado por ZWJ
    viram glifo quebrado se o corte cair no meio. Por isso, depois de cortar,
    recuamos enquanto o ultimo caractere for insegmentavel.
    """
    if limite <= 0:
        return ""
    if len(texto) <= limite:
        return texto
    corte = texto[:limite]
    while corte and _insegmentavel(corte[-1]):
        corte = corte[:-1]
    return corte


def truncar(valor: Any, limite: int, *, sufixo: str = SUFIXO_ELLIPSIS) -> str:
    """Trunca `valor` em no maximo `limite` caracteres, com elipse.

    Idempotente: truncar um valor que ja cabe devolve o proprio valor, sem
    alteracao. E por isso que pode ser aplicado em camadas (provider ->
    servico -> persistencia) sem corromper o texto duas vezes nem empilhar
    duas elipses.
    """
    texto = "" if valor is None else str(valor)
    if limite <= 0:
        return ""
    if len(texto) <= limite:
        return texto
    orcamento_para_o_texto = max(limite - len(sufixo), 0)
    return cortar_em_limite_seguro(texto, orcamento_para_o_texto) + sufixo


__all__ = [
    "FOLGA_ANTES_DE_LIMPAR_HTML",
    "SUFIXO_ELLIPSIS",
    "cortar_em_limite_seguro",
    "limpar_html_para_texto",
    "truncar",
]
