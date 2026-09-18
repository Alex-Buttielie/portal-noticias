"""Extracao de texto a partir do HTML do RSS — Frente B.

- ``limpar_html_para_texto(html) -> str``: stdlib apenas (HTMLParser),
  remove script/style, decodifica entidades, colapsa espacos. Best-effort.
- ``extrair_conteudo_completo(entry) -> str``: prefere ``content:encoded``
  (maior bloco de ``content``), fallback para summary/description/
  content_html; teto de 8000 chars. Aceita entry feedparser OU dict bruto
  (chaves do ``rss.buscar_itens``).
"""
from __future__ import annotations

import html as _html
import re as _re
from html.parser import HTMLParser
from typing import Any

TETO_CONTEUDO_COMPLETO_CHARS = 8000


class _StripperDeHtml(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._partes: list[str] = []

    def handle_data(self, data: str) -> None:
        self._partes.append(data)

    def texto(self) -> str:
        return "".join(self._partes)


def limpar_html_para_texto(html: str | None) -> str:
    """Converte HTML em texto puro. Nunca levanta (best-effort)."""
    bruto = html or ""
    try:
        sem_script = _re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", bruto)
        com_quebras = _re.sub(r"(?i)<\s*(br|p|div|li|h[1-6])[^>]*>", "\n", sem_script)
        stripper = _StripperDeHtml()
        stripper.feed(com_quebras)
        texto = _html.unescape(stripper.texto())
    except Exception:  # noqa: BLE001 — fallback sem parser
        texto = _re.sub(r"<[^>]+>", " ", bruto)
    texto = _re.sub(r"[ \t\xa0]+", " ", texto)
    texto = _re.sub(r"\n\s*\n+", "\n\n", texto)
    return texto.strip()


def _campo(entry: Any, nome: str, default: Any = "") -> Any:
    if isinstance(entry, dict):
        return entry.get(nome, default)
    return getattr(entry, nome, default)


def extrair_conteudo_completo(entry: Any) -> str:
    """Texto integral do item, limpo de HTML, limitado a 8000 chars."""
    html_completo = ""
    for bloco in _campo(entry, "content", None) or []:
        valor = bloco.get("value") if isinstance(bloco, dict) else getattr(bloco, "value", "")
        if valor and len(str(valor)) > len(html_completo):
            html_completo = str(valor)
    if not html_completo.strip():
        html_completo = (
            _campo(entry, "content_html", "")
            or _campo(entry, "summary", "")
            or _campo(entry, "description", "")
            or ""
        )
    return limpar_html_para_texto(html_completo)[:TETO_CONTEUDO_COMPLETO_CHARS].strip()
