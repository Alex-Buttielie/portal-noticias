"""
Interface `NewsSourceProvider` (ARCHITECTURE.md secao 6) + implementacao
concreta via RSS (`RSSNewsSourceProvider`).

Qualquer fonte futura (API licenciada, outro RSS, etc.) deve implementar
`NewsSourceProvider.buscar_itens()` e devolver uma lista de `ItemBruto` — o
restante do pipeline (`services/ingestao.py`) nao conhece detalhes de
RSS/HTTP, apenas este contrato.
"""

from __future__ import annotations

import calendar
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone as dt_timezone
from html.parser import HTMLParser
from typing import Optional

import feedparser
import requests

logger = logging.getLogger(__name__)


class FonteIndisponivelError(Exception):
    """
    Levantada quando uma fonte nao pode ser acessada/parseada (erro de rede,
    HTTP nao-2xx, feed corrompido, etc.). `services/ingestao.py` captura essa
    excecao por fonte para que a falha de uma fonte nao derrube as demais
    (implementation-contract.md, criterio de aceite 1).
    """


def parece_pagina_html(corpo: bytes) -> bool:
    """Detecta homepage/página HTML cadastrada por engano no lugar do feed.

    Contexto real (2026-09-18): fontes cadastradas em Central > Robôs com a
    URL da homepage do portal (ex.: `https://www.bbc.com/portuguese`) em vez
    do endpoint RSS — o fetch retorna HTML 200, o feedparser acusa
    "malformado" e a ingestão zera para todas elas. O sniff é pelo corpo
    (não pelo Content-Type: há feeds legítimos servidos como `text/html`,
    ex.: Correio Braziliense), após BOM/whitespace.
    """
    try:
        inicio = (corpo or b"").lstrip(b"\xef\xbb\xbf \t\r\n").lower()[:20]
    except Exception:
        return False
    return inicio.startswith(b"<html") or inicio.startswith(b"<!doctype html")


def extrair_imagem_url(entrada) -> str:
    for key in ("enclosures", "media_content", "media_thumbnail"):
        vals = getattr(entrada, key, None)
        if vals:
            for v in vals:
                href = (v.get("url") if isinstance(v, dict) else getattr(v, "url", "")) or (v.get("href") if isinstance(v, dict) else getattr(v, "href", ""))
                if href and href.startswith("http"):
                    return href.strip()
    for key in ("image",):
        val = getattr(entrada, key, None)
        if val:
            href = val.get("href") if isinstance(val, dict) else getattr(val, "href", "")
            if href and href.startswith("http"):
                return href.strip()
            if isinstance(val, str) and val.startswith("http"):
                return val.strip()
    links = getattr(entrada, "links", None)
    if links:
        for lk in links:
            rel = lk.get("rel") if isinstance(lk, dict) else getattr(lk, "rel", "")
            href = lk.get("href") if isinstance(lk, dict) else getattr(lk, "href", "")
            tipo = lk.get("type") if isinstance(lk, dict) else getattr(lk, "type", "")
            if href and href.startswith("http") and (rel == "enclosure" or (tipo or "").startswith("image/")):
                return href.strip()
    summary = getattr(entrada, "summary", "") or ""
    if summary and "og:image" in summary:
        import re
        m = re.search(r'og:image["\']?\s*content=["\']([^"\']+)["\']', summary)
        if m and m.group(1).startswith("http"):
            return m.group(1).strip()
        m2 = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', summary)
        if m2 and m2.group(1).startswith("http"):
            return m2.group(1).strip()
    return ""


class _StripperDeHtml(HTMLParser):
    """Remove tags HTML mantendo o texto (stdlib, sem dependência nova)."""

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
    import re as _re

    bruto = html or ""
    try:
        sem_script = _re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", bruto)
        com_quebras = _re.sub(r"(?i)<\s*(br|p|div|li|h[1-6])[^>]*>", "\n", sem_script)
        stripper = _StripperDeHtml()
        stripper.feed(com_quebras)
        texto = _html.unescape(stripper.texto())
    except Exception:
        texto = _re.sub(r"<[^>]+>", " ", bruto)
    texto = _re.sub(r"[ \t\xa0]+", " ", texto)
    texto = _re.sub(r"\n\s*\n+", "\n\n", texto)
    return texto.strip()


TETO_CONTEUDO_COMPLETO_CHARS = 8000


def extrair_conteudo_completo(entrada) -> str:
    """Texto integral da matéria direto do RSS (`content:encoded` quando o
    feed traz; senão o summary/description), limpo de HTML e limitado a
    `TETO_CONTEUDO_COMPLETO_CHARS` chars. Best-effort: retorna "" se o feed
    só trouxer título/link. Exibido de forma TRUNCADA no frontend, sempre
    com crédito + link para a fonte original (BRD seção 18)."""
    html_completo = ""
    conteudos = getattr(entrada, "content", None)
    if conteudos:
        for bloco in conteudos:
            valor = (bloco.get("value") if isinstance(bloco, dict) else getattr(bloco, "value", "")) or ""
            if valor and len(valor) > len(html_completo):
                html_completo = valor
    if not html_completo.strip():
        html_completo = getattr(entrada, "summary", "") or getattr(entrada, "description", "") or ""
    texto = limpar_html_para_texto(html_completo)
    return texto[:TETO_CONTEUDO_COMPLETO_CHARS].strip()


@dataclass
class ItemBruto:
    titulo: str
    url_fonte_original: str
    nome_fonte: str
    conteudo_bruto: str = ""
    conteudo_completo: str = ""
    categoria: str = ""
    imagem_url: str = ""
    timestamp_publicacao_fonte: Optional[datetime] = None


class NewsSourceProvider(ABC):
    """
    Contrato que qualquer fonte de noticias (RSS hoje; API licenciada,
    integracao futura, etc.) deve implementar (ARCHITECTURE.md secao 6).
    """

    @abstractmethod
    def buscar_itens(self) -> list[ItemBruto]:
        """
        Retorna os itens brutos disponiveis nesta fonte no momento da
        chamada. Deve levantar `FonteIndisponivelError` (nao uma excecao
        generica) em caso de falha de rede/parsing, para que o chamador
        possa tratar essa falha de forma previsivel e isolada por fonte.
        """
        raise NotImplementedError


class RSSNewsSourceProvider(NewsSourceProvider):
    """
    Implementacao de `NewsSourceProvider` via feed RSS/Atom (biblioteca
    `feedparser`). Cada instancia representa uma unica fonte configurada
    (nome + URL do feed) — a lista de fontes-semente vive em
    `settings.CATALOGO_NOTICIAS_FONTES_RSS`, nunca hardcoded aqui.
    """

    def __init__(self, nome_fonte: str, url_feed: str, timeout_segundos: int = 15):
        self.nome_fonte = nome_fonte
        self.url_feed = url_feed
        self.timeout_segundos = timeout_segundos

    def buscar_itens(self) -> list[ItemBruto]:
        try:
            resposta = requests.get(
                self.url_feed,
                timeout=self.timeout_segundos,
                headers={"User-Agent": "BRDPortalNoticias/1.0 (+ingestao-catalogo-noticias)"},
            )
            resposta.raise_for_status()
        except requests.RequestException as exc:
            raise FonteIndisponivelError(
                f"Falha ao buscar o feed RSS de '{self.nome_fonte}' ({self.url_feed}): {exc}"
            ) from exc

        corpo = resposta.content or b""
        if parece_pagina_html(corpo):
            raise FonteIndisponivelError(
                f"URL cadastrada para '{self.nome_fonte}' ({self.url_feed}) não é um feed RSS/Atom "
                f"(retornou página HTML). Cadastre o endpoint do feed RSS em Central > Robôs > Fontes "
                f"— não a homepage do portal."
            )
        feed = feedparser.parse(corpo)
        if feed.bozo and not feed.entries:
            # `bozo=1` sinaliza XML malformado; se ainda assim vieram
            # entries, seguimos em frente (feedparser costuma extrair o que
            # da mesmo em feeds levemente invalidos) — so tratamos como
            # indisponivel quando NADA pode ser extraido.
            raise FonteIndisponivelError(
                f"Feed RSS de '{self.nome_fonte}' ({self.url_feed}) malformado: {feed.bozo_exception} "
                f"(se a URL for a homepage do portal, cadastre o endpoint do feed RSS em Central > Robôs > Fontes)"
            )

        itens: list[ItemBruto] = []
        for entrada in feed.entries:
            url_item = getattr(entrada, "link", "") or ""
            titulo_item = getattr(entrada, "title", "") or ""
            if not url_item or not titulo_item:
                # Item individual sem URL/titulo nao e publicavel (criterio
                # de aceite 3) — descartado aqui (nao e erro de fonte, so um
                # item malformado dentro de um feed bom no geral).
                logger.debug(
                    "Item descartado do feed '%s' por falta de titulo/URL.", self.nome_fonte
                )
                continue

            conteudo = getattr(entrada, "summary", "") or getattr(entrada, "description", "") or ""
            categoria = ""
            tags = getattr(entrada, "tags", None)
            if tags:
                categoria = getattr(tags[0], "term", "") or ""

            timestamp_publicacao = None
            published_parsed = getattr(entrada, "published_parsed", None)
            if published_parsed:
                timestamp_publicacao = datetime.fromtimestamp(
                    calendar.timegm(published_parsed), tz=dt_timezone.utc
                )

            itens.append(
                ItemBruto(
                    titulo=titulo_item.strip(),
                    url_fonte_original=url_item.strip(),
                    nome_fonte=self.nome_fonte,
                    conteudo_bruto=conteudo.strip(),
                    conteudo_completo=extrair_conteudo_completo(entrada),
                    categoria=categoria.strip().lower(),
                    imagem_url=extrair_imagem_url(entrada),
                    timestamp_publicacao_fonte=timestamp_publicacao,
                )
            )
        return itens
