"""
Cliente HTTP do microserviço de ingestão — Frente D.

Quando `MICROSERVICO_INGESTAO_URL` está configurada, as views de `feed/`
tentam servir leitura a partir do microserviço primeiro (mesmos shapes de
resposta do modo local: `FeedEntrySerializer`/`FeedDetalheSerializer`), com
fallback silencioso para o serviço local em `MicroserviceIndisponivelError`.

Contratos consumidos (outras frentes, `ingestao-service/`):
  - GET  {BASE}/api/v1/feed[?categoria=&busca=&page=&page_size=]
  - GET  {BASE}/api/v1/feed/urgentes[?limite=]
  - GET  {BASE}/api/v1/feed/cluster/{id}
  - GET  {BASE}/api/v1/feed/item/{id}
  - POST {BASE}/fontes/sincronizar  (corpo: {"fontes": [...]})
Autenticação: header `X-API-Token: <INGESTAO_API_TOKEN>`, timeout 10s.

Com `MICROSERVICO_INGESTAO_URL` vazia (default), o portal opera 100% local
e este módulo nunca é chamado para rede (`servico_ativo()` == False).
"""

from __future__ import annotations

import logging

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

TIMEOUT_SEGUNDOS = 10

_PATH_FEED = "/api/v1/feed"
_PATH_URGENTES = "/api/v1/feed/urgentes"
_PATH_CLUSTER = "/api/v1/feed/cluster/{id}"
_PATH_ITEM = "/api/v1/feed/item/{id}"
# Escrita sob o mesmo prefixo /api/v1 das rotas de leitura (alinhado ao
# roteador do serviço).
_PATH_SINCRONIZAR_FONTES = "/api/v1/fontes/sincronizar"


class MicroserviceIndisponivelError(Exception):
    """Qualquer falha de comunicação com o microserviço de ingestão
    (rede, timeout, HTTP não-2xx/inesperado, payload inválido). As views
    tratam como sinal para fallback silencioso ao serviço local."""


def servico_ativo() -> bool:
    """True quando `MICROSERVICO_INGESTAO_URL` está configurada (não vazia)."""
    return bool((getattr(settings, "MICROSERVICO_INGESTAO_URL", "") or "").strip())


def _base_url() -> str:
    base = (getattr(settings, "MICROSERVICO_INGESTAO_URL", "") or "").strip().rstrip("/")
    if not base:
        raise MicroserviceIndisponivelError("Microserviço de ingestão não configurado.")
    return base


def _headers() -> dict:
    return {"X-API-Token": getattr(settings, "INGESTAO_API_TOKEN", "") or ""}


def _get(path: str, params: dict | None = None):
    url = _base_url() + path
    try:
        resposta = requests.get(url, params=params or {}, headers=_headers(), timeout=TIMEOUT_SEGUNDOS)
    except requests.RequestException as exc:
        raise MicroserviceIndisponivelError(f"GET {path} falhou: {exc}") from exc
    if resposta.status_code == 404:
        return None
    if not resposta.ok:
        raise MicroserviceIndisponivelError(f"GET {path} retornou HTTP {resposta.status_code}.")
    try:
        return resposta.json()
    except ValueError as exc:
        raise MicroserviceIndisponivelError(f"GET {path} retornou corpo não-JSON.") from exc


def _converter_id_para_int(obj: dict) -> dict:
    """Compat com o frontend (`FeedEntrada.id: number`): o microserviço pode
    serializar ids como string (ex.: ObjectId do Mongo); converte para int
    quando possível, preservando o valor original caso contrário."""
    if isinstance(obj, dict) and "id" in obj:
        try:
            obj["id"] = int(obj["id"])
        except (TypeError, ValueError):
            pass
    return obj


def _normalizar_lista(payload) -> list:
    itens = payload if isinstance(payload, list) else (payload or {}).get("results", [])
    return [_converter_id_para_int(dict(e)) for e in itens]


def obter_feed(categoria=None, busca=None, page=1, page_size=None) -> dict:
    """GET /api/v1/feed — retorna o payload paginado do microserviço
    (`count`/`next`/`previous`/`results`, shapes iguais ao feed local)."""
    params: dict = {}
    if categoria:
        params["categoria"] = categoria
    if busca:
        params["busca"] = busca
    if page:
        params["page"] = page
    if page_size:
        params["page_size"] = page_size
    payload = _get(_PATH_FEED, params=params)
    if not isinstance(payload, dict):
        raise MicroserviceIndisponivelError("GET /api/v1/feed retornou payload inesperado.")
    if isinstance(payload.get("results"), list):
        payload["results"] = [_converter_id_para_int(dict(e)) for e in payload["results"]]
    # `next`/`previous` do serviço apontam para o host DELE — o portal
    # pagina por `?page=` (FeedPagination local), então nunca repassamos
    # URLs de outro host ao frontend.
    payload["next"] = None
    payload["previous"] = None
    return payload


def obter_urgentes(limite: int = 6) -> list:
    """GET /api/v1/feed/urgentes — retorna a lista de entradas urgentes."""
    payload = _get(_PATH_URGENTES, params={"limite": limite})
    if payload is None:
        return []
    return _normalizar_lista(payload)


def obter_detalhe_cluster(cluster_id) -> dict | None:
    """GET /api/v1/feed/cluster/{id} — None quando o microserviço dá 404."""
    payload = _get(_PATH_CLUSTER.format(id=cluster_id))
    if payload is None:
        return None
    if not isinstance(payload, dict):
        raise MicroserviceIndisponivelError("Detalhe de cluster com payload inesperado.")
    return _converter_id_para_int(payload)


def obter_detalhe_item(item_id) -> dict | None:
    """GET /api/v1/feed/item/{id} — None quando o microserviço dá 404."""
    payload = _get(_PATH_ITEM.format(id=item_id))
    if payload is None:
        return None
    if not isinstance(payload, dict):
        raise MicroserviceIndisponivelError("Detalhe de item com payload inesperado.")
    return _converter_id_para_int(payload)


def sincronizar_fontes(fontes) -> dict:
    """POST /fontes/sincronizar — envia as fontes (`FonteRobo` serializadas)
    ao microserviço. Qualquer falha levanta `MicroserviceIndisponivelError`
    (callers usam best-effort e nunca quebram a operação local)."""
    url = _base_url() + _PATH_SINCRONIZAR_FONTES
    try:
        resposta = requests.post(
            url, json={"fontes": list(fontes)}, headers=_headers(), timeout=TIMEOUT_SEGUNDOS
        )
    except requests.RequestException as exc:
        raise MicroserviceIndisponivelError(f"POST {_PATH_SINCRONIZAR_FONTES} falhou: {exc}") from exc
    if not resposta.ok:
        raise MicroserviceIndisponivelError(
            f"POST {_PATH_SINCRONIZAR_FONTES} retornou HTTP {resposta.status_code}."
        )
    try:
        payload = resposta.json()
    except ValueError as exc:
        raise MicroserviceIndisponivelError("POST /fontes/sincronizar retornou corpo não-JSON.") from exc
    return payload if isinstance(payload, dict) else {}
