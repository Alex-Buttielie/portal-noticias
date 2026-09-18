"""Coletor RSS — Frente B (pipeline do microservico de ingestao).

Contrato congelado (frentes A/C integram por ele):
- ``buscar_itens(fonte: dict) -> list[dict]`` — cada dict bruto tem as chaves
  {titulo, url, nome_fonte, summary, content_html, imagem_url, categoria,
  publicado_em}. ``publicado_em`` e um ``datetime`` com tz (UTC) ou ``None``
  quando o feed nao informa data.
- ``extrair_imagem_url(entry) -> str`` — best-effort, nunca levanta.
- Falha de rede/feed (HTTP nao-2xx, timeout, XML malformado sem entries)
  levanta ``FonteIndisponivelError`` — nunca excecao generica.

Timeout 15s e User-Agent proprio em todas as requisicoes HTTP.
"""
from __future__ import annotations

import calendar
import logging
import re
from datetime import datetime, timezone as dt_timezone
from typing import Any

import feedparser
import requests

logger = logging.getLogger("ingestao.collectors.rss")

TIMEOUT_SEGUNDOS = 15
USER_AGENT = "BRDPortalNoticias-Ingestao/1.0 (+microservico-ingestao; contato: admin local)"


class FonteIndisponivelError(Exception):
    """Fonte inacessivel ou feed ilegiveis nesta execucao (rede/HTTP/parse)."""


def _campo(entry: Any, nome: str, default: Any = "") -> Any:
    """Le campo de entry feedparser OU dict (fixtures de teste usam dict)."""
    if isinstance(entry, dict):
        return entry.get(nome, default)
    return getattr(entry, nome, default)


def extrair_imagem_url(entry: Any) -> str:
    """URL da imagem do item (enclosure/media:content/thumb, links, <img>).

    Best-effort: retorna "" quando nada e encontrado; nunca levanta.
    """
    try:
        for key in ("enclosures", "media_content", "media_thumbnail"):
            vals = _campo(entry, key, None)
            if vals:
                for v in vals:
                    if isinstance(v, dict):
                        href = v.get("url") or v.get("href") or ""
                    else:
                        href = getattr(v, "url", "") or getattr(v, "href", "") or ""
                    if href and str(href).startswith("http"):
                        return str(href).strip()
        val = _campo(entry, "image", None)
        if val:
            if isinstance(val, dict):
                href = val.get("href") or ""
            elif isinstance(val, str):
                href = val
            else:
                href = getattr(val, "href", "") or ""
            if href and str(href).startswith("http"):
                return str(href).strip()
        links = _campo(entry, "links", None)
        if links:
            for lk in links:
                if isinstance(lk, dict):
                    rel, href, tipo = lk.get("rel"), lk.get("href"), lk.get("type")
                else:
                    rel, href, tipo = getattr(lk, "rel", ""), getattr(lk, "href", ""), getattr(lk, "type", "")
                if href and str(href).startswith("http") and (
                    rel == "enclosure" or str(tipo or "").startswith("image/")
                ):
                    return str(href).strip()
        # <img> (ou og:image) embutido no summary/content.
        for key in ("summary", "description"):
            html = _campo(entry, key, "") or ""
            if html:
                m = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', str(html), re.IGNORECASE)
                if m and m.group(1).startswith("http"):
                    return m.group(1).strip()
                m = re.search(r'og:image["\']?\s*content=["\']([^"\']+)["\']', str(html))
                if m and m.group(1).startswith("http"):
                    return m.group(1).strip()
            if key == "summary":
                for bloco in _campo(entry, "content", None) or []:
                    v = bloco.get("value") if isinstance(bloco, dict) else getattr(bloco, "value", "")
                    if v:
                        m = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', str(v), re.IGNORECASE)
                        if m and m.group(1).startswith("http"):
                            return m.group(1).strip()
    except Exception:  # noqa: BLE001 — best-effort deliberado
        return ""
    return ""


def _extrair_publicado_em(entry: Any) -> datetime | None:
    for key in ("published_parsed", "updated_parsed"):
        parsed = _campo(entry, key, None)
        if parsed:
            try:
                return datetime.fromtimestamp(calendar.timegm(parsed), tz=dt_timezone.utc)
            except Exception:  # noqa: BLE001 — data invalida vira None
                continue
    return None


def _extrair_categoria(entry: Any, fonte: dict) -> str:
    tags = _campo(entry, "tags", None)
    if tags:
        primeira = tags[0]
        if isinstance(primeira, dict):
            termo = primeira.get("term") or ""
        else:
            termo = getattr(primeira, "term", "") or ""
        if termo:
            return str(termo).strip().lower()
    return str(fonte.get("categoria_padrao") or "").strip().lower()


def _extrair_content_html(entry: Any, summary: str) -> str:
    """Maior bloco de content:encoded; fallback para o summary."""
    melhor = ""
    for bloco in _campo(entry, "content", None) or []:
        v = bloco.get("value") if isinstance(bloco, dict) else getattr(bloco, "value", "")
        if v and len(str(v)) > len(melhor):
            melhor = str(v)
    return melhor if melhor.strip() else summary


def buscar_itens(fonte: dict) -> list[dict]:
    """Busca e normaliza os itens do feed RSS/Atom de ``fonte``.

    ``fonte``: dict com ``nome`` (ou ``nome_fonte``), ``url`` (ou
    ``url_feed``) e, opcionalmente, ``categoria_padrao``.
    """
    nome = str(fonte.get("nome") or fonte.get("nome_fonte") or "fonte").strip()
    url = str(fonte.get("url") or fonte.get("url_feed") or "").strip()
    if not url:
        raise FonteIndisponivelError(f"Fonte '{nome}' sem URL de feed configurada.")

    try:
        resposta = requests.get(
            url, timeout=TIMEOUT_SEGUNDOS, headers={"User-Agent": USER_AGENT}
        )
        resposta.raise_for_status()
    except requests.RequestException as exc:
        raise FonteIndisponivelError(
            f"Falha ao buscar o feed RSS de '{nome}' ({url}): {exc}"
        ) from exc

    feed = feedparser.parse(resposta.content)
    if getattr(feed, "bozo", False) and not getattr(feed, "entries", None):
        raise FonteIndisponivelError(
            f"Feed RSS de '{nome}' ({url}) malformado: {getattr(feed, 'bozo_exception', '?')}"
        )

    itens: list[dict] = []
    for entrada in getattr(feed, "entries", []) or []:
        url_item = _campo(entrada, "link", "") or ""
        titulo_item = _campo(entrada, "title", "") or ""
        if not str(url_item).strip() or not str(titulo_item).strip():
            # Item sem URL/titulo nao e publicavel (regra do portal) —
            # descartado aqui; nao e erro da fonte.
            logger.debug("Item descartado do feed '%s' por falta de titulo/URL.", nome)
            continue
        summary = (
            _campo(entrada, "summary", "")
            or _campo(entrada, "description", "")
            or ""
        )
        itens.append(
            {
                "titulo": str(titulo_item).strip(),
                "url": str(url_item).strip(),
                "nome_fonte": nome,
                "summary": str(summary).strip(),
                "content_html": _extrair_content_html(entrada, str(summary)),
                "imagem_url": extrair_imagem_url(entrada),
                "categoria": _extrair_categoria(entrada, fonte),
                "publicado_em": _extrair_publicado_em(entrada),
            }
        )
    return itens
