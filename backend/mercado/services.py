"""
Proxy de cotações (Brapi, brapi.dev) — inspirado no widget de mercado do
Google Notícias. Igual a `enderecos/services.py`: toda saída passa por
`config.egress.SessaoEgress` (SSRF), cache no Django cache, e o app fica
inerte (sem gerar erro, só devolve vazio) sem `BRAPI_API_KEY` configurada
— mesmo padrão de "secret ausente = recurso desligado" do AdSense
(`frontend/components/AdsSlot.tsx`).

Índices da B3 (ex.: ^BVSP) exigem token na Brapi; ações individuais não.
Aqui só expomos índices — cada símbolo tem nome fixo porque a Brapi não
tem tradução de nome amigável, e o rótulo apontado para "ação" seria
inventado.
"""

from __future__ import annotations

import logging

import requests
from django.conf import settings
from django.core.cache import cache

from config.egress import EgressBloqueado, SessaoEgress

logger = logging.getLogger(__name__)

# symbol Brapi -> rótulo de exibição (fixo, não vem da API — Brapi não
# devolve nome amigável de índice).
INDICES = {
    "^BVSP": "Ibovespa",
    "^IFIX": "IFIX",
}


def _api_key() -> str:
    return getattr(settings, "BRAPI_API_KEY", "") or ""


def _base_url() -> str:
    return getattr(settings, "MERCADO_BRAPI_BASE_URL", "https://brapi.dev/api")


def _timeout() -> int:
    return int(getattr(settings, "MERCADO_UPSTREAM_TIMEOUT_SEGUNDOS", 8))


def _cache_ttl() -> int:
    return int(getattr(settings, "MERCADO_CACHE_SEGUNDOS", 900))


def habilitado() -> bool:
    return bool(_api_key())


class ServicoMercadoIndisponivelError(RuntimeError):
    """Upstream fora do ar, timeout ou resposta inválida."""


def obter_indices() -> list[dict]:
    """
    Cotações dos índices em `INDICES`, cacheadas (`MERCADO_CACHE_SEGUNDOS`,
    padrão 15min — igual ao TTL do feed, não há razão pra atualizar mais
    rápido que isso). `[]` sem API key configurada (recurso desligado).
    """
    if not habilitado():
        return []

    chave = "mercado:indices:" + ",".join(sorted(INDICES))
    cacheado = cache.get(chave)
    if cacheado is not None:
        return cacheado

    simbolos = ",".join(INDICES)
    url = f"{_base_url()}/quote/{simbolos}"
    try:
        with SessaoEgress() as sessao:
            resposta = sessao.get(
                url,
                params={"token": _api_key()},
                timeout=_timeout(),
            )
    except EgressBloqueado as exc:
        logger.error("mercado upstream bloqueado pela política de saída: %s", exc)
        raise ServicoMercadoIndisponivelError("Serviço de cotações indisponível no momento.") from exc
    except requests.RequestException as exc:
        logger.warning("mercado upstream inalcançável: %s (%s)", url, exc)
        raise ServicoMercadoIndisponivelError("Serviço de cotações indisponível no momento.") from exc

    if resposta.status_code >= 400:
        logger.warning("mercado upstream HTTP %s: %s", resposta.status_code, url)
        raise ServicoMercadoIndisponivelError("Serviço de cotações indisponível no momento.")

    try:
        dados = resposta.json()
    except ValueError as exc:
        raise ServicoMercadoIndisponivelError("Resposta inválida do serviço de cotações.") from exc

    resultados = dados.get("results") if isinstance(dados, dict) else None
    if not isinstance(resultados, list):
        raise ServicoMercadoIndisponivelError("Resposta inválida do serviço de cotações.")

    indices = []
    for item in resultados:
        simbolo = item.get("symbol")
        if simbolo not in INDICES:
            continue
        preco = item.get("regularMarketPrice")
        variacao = item.get("regularMarketChangePercent")
        if preco is None or variacao is None:
            continue
        indices.append(
            {
                "simbolo": simbolo,
                "nome": INDICES[simbolo],
                "preco": preco,
                "variacao_percentual": variacao,
            }
        )

    cache.set(chave, indices, timeout=_cache_ttl())
    return indices
