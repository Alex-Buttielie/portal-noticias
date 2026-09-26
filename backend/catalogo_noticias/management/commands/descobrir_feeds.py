"""Descobre o endpoint RSS/Atom real a partir da homepage do portal.

Uso:
    python manage.py descobrir_feeds --entrada catalogo_noticias/fontes_candidatas.json --saida /tmp/feeds.json

Para cada {nome, pagina, uf}: busca `<link rel="alternate" type="...rss/atom...">`
na homepage e testa padrões comuns (/feed, /rss.xml, ...). Cada candidato é
validado de verdade (GET + parse com entries>0). O relatório JSON indica o
feed funcional ou o motivo da falha — sem adivinhação.

Somente descoberta: não altera banco nem settings.
"""

from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urljoin, urlparse

import feedparser
import requests
from django.core.management.base import BaseCommand, CommandError

from config.egress import EgressBloqueado, SessaoEgress

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
)

LINK_RE = re.compile(
    r'<link[^>]+rel=["\']alternate["\'][^>]*>',
    re.IGNORECASE,
)
HREF_RE = re.compile(r'href=["\']([^"\']+)["\']', re.IGNORECASE)
TYPE_RE = re.compile(r'type=["\']([^"\']+)["\']', re.IGNORECASE)

PADROES_FALLBACK = [
    "/feed",
    "/feed/",
    "/rss",
    "/rss.xml",
    "/feed.xml",
    "/rss/feed.xml",
    "/feed/rss.xml",
    "/atom.xml",
]


def _get(url: str, timeout: int = 20):
    """
    GET com controle de saída.

    Este comando é o pior caso de SSRF do projeto: a lista de ENTRADA é um
    JSON de candidatos e os candidatos de feed saem de `<link rel=
    "alternate">` extraídos de homepages arbitrárias, com `urljoin` — ou
    seja, de conteúdo controlado por terceiro. Sem o controle, ele varre a
    rede interna de quem rodar a manutenção. O `allow_redirects=True`
    é seguro porque a `SessaoEgress` revalida cada `Location`.
    """
    with SessaoEgress(user_agent=UA) as sessao:
        return sessao.get(url, timeout=timeout, headers={"User-Agent": UA}, allow_redirects=True)


def _e_feed_valido(url: str, timeout: int = 20) -> tuple[bool, str, int]:
    """Retorna (ok, titulo_ou_erro, n_itens)."""
    try:
        r = _get(url, timeout)
    except EgressBloqueado as exc:
        return False, f"destino bloqueado: {exc}", 0
    except requests.RequestException as exc:
        return False, f"rede: {exc.__class__.__name__}", 0
    if r.status_code >= 400:
        return False, f"http-{r.status_code}", 0
    corpo = r.content or b""
    inicio = corpo.lstrip(b"\xef\xbb\xbf \t\r\n").lower()[:20]
    if inicio.startswith(b"<html") or inicio.startswith(b"<!doctype html"):
        return False, "retornou HTML", 0
    try:
        feed = feedparser.parse(corpo)
    except Exception as exc:  # pragma: no cover - defensivo
        return False, f"parse: {exc}", 0
    if not feed.entries:
        detalhe = f"bozo: {feed.bozo_exception}" if feed.bozo else "sem entries"
        return False, detalhe, 0
    titulo = (feed.feed.get("title", "") or "").strip()[:80]
    return True, titulo or "(sem título)", len(feed.entries)


def descobrir(nome: str, pagina: str, timeout: int = 20) -> dict:
    candidatos: list[str] = []
    try:
        r = _get(pagina, timeout)
        html = r.text or ""
        for tag in LINK_RE.findall(html):
            tipo = (TYPE_RE.search(tag) or [None, ""])[1].lower()
            href = HREF_RE.search(tag)
            if href and ("rss" in tipo or "atom" in tipo or "xml" in tipo):
                candidatos.append(urljoin(r.url, href.group(1)))
    except EgressBloqueado as exc:
        return {"nome": nome, "pagina": pagina, "feed": None, "erro": f"destino bloqueado: {exc}"}
    except requests.RequestException as exc:
        return {"nome": nome, "pagina": pagina, "feed": None, "erro": f"homepage inacessível: {exc.__class__.__name__}"}

    base = pagina.rstrip("/")
    for padrao in PADROES_FALLBACK:
        candidatos.append(base + padrao)
    # Globo/G1: feeds vivem em /rss/g1/<caminho-da-editoria>/ — padrão que
    # os fallbacks genéricos acima não cobrem (ex.: nacional /rss/g1/).
    try:
        partes = urlparse(pagina)
        if "g1.globo.com" in (partes.netloc or ""):
            caminho = partes.path if partes.path not in ("", "/") else "/"
            candidatos.append(f"https://g1.globo.com/rss/g1{caminho}")
    except Exception:
        pass

    vistos: set[str] = set()
    erros: list[str] = []
    for url in candidatos:
        if url in vistos:
            continue
        vistos.add(url)
        ok, detalhe, n = _e_feed_valido(url, timeout)
        if ok:
            return {"nome": nome, "pagina": pagina, "feed": url, "titulo_feed": detalhe, "itens": n}
        erros.append(f"{urlparse(url).path or '/'}: {detalhe}")
    return {"nome": nome, "pagina": pagina, "feed": None, "erro": " | ".join(erros[:6])}


class Command(BaseCommand):
    help = (
        "Descobre o endpoint RSS/Atom real a partir da homepage do portal "
        "(somente descoberta: não altera banco nem settings)."
    )

    def add_arguments(self, parser):
        parser.add_argument("--entrada", required=True)
        parser.add_argument("--saida", required=True)
        parser.add_argument("--workers", type=int, default=10)
        parser.add_argument("--timeout", type=int, default=20)

    def handle(self, *args, **opcoes):
        import json

        with open(opcoes["entrada"], encoding="utf-8") as fh:
            entradas = json.load(fh)
        if not isinstance(entradas, list) or not entradas:
            raise CommandError("Arquivo de entrada deve ser uma lista JSON não vazia.")

        resultados: list[dict] = []
        with ThreadPoolExecutor(max_workers=opcoes["workers"]) as pool:
            futuros = {
                pool.submit(descobrir, e["nome"], e["pagina"], opcoes["timeout"]): e
                for e in entradas
            }
            for fut in as_completed(futuros):
                e = futuros[fut]
                try:
                    r = fut.result()
                except Exception as exc:  # pragma: no cover - defensivo
                    r = {"nome": e["nome"], "pagina": e["pagina"], "feed": None, "erro": f"exceção: {exc}"}
                r["uf"] = e.get("uf")
                resultados.append(r)
                status = "OK " if r["feed"] else "FALHA "
                self.stdout.write(f"[{status}] {r['nome']} -> {r['feed'] or r['erro']}")

        with open(opcoes["saida"], "w", encoding="utf-8") as fh:
            json.dump(resultados, fh, ensure_ascii=False, indent=1)
        ok = sum(1 for r in resultados if r["feed"])
        self.stdout.write(self.style.SUCCESS(f"\n{ok}/{len(resultados)} feeds verificados. Relatório em {opcoes['saida']}"))
