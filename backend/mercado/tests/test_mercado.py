"""Proxy de cotações (Brapi): inerte sem API key, parse e cache com key."""

from __future__ import annotations

import pytest
import requests
from django.core.cache import cache
from rest_framework.test import APIClient

from mercado import services


class _Resp:
    def __init__(self, payload, status=200):
        self._payload = payload
        self.status_code = status

    def json(self):
        return self._payload


@pytest.fixture(autouse=True)
def _cache_limpo(settings):
    settings.CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "test-mercado-locmem",
        }
    }
    cache.clear()
    yield
    cache.clear()


def test_sem_api_key_devolve_204(settings):
    settings.BRAPI_API_KEY = ""
    client = APIClient()
    resposta = client.get("/api/mercado/indices/")
    assert resposta.status_code == 204


def test_com_api_key_devolve_indices_parseados(settings, monkeypatch):
    settings.BRAPI_API_KEY = "chave-teste"
    payload = {
        "results": [
            {"symbol": "^BVSP", "regularMarketPrice": 209066.90, "regularMarketChangePercent": 1.38},
            {"symbol": "^IFIX", "regularMarketPrice": 3200.5, "regularMarketChangePercent": -0.2},
            {"symbol": "OUTRO", "regularMarketPrice": 1, "regularMarketChangePercent": 1},
        ]
    }
    monkeypatch.setattr(services.SessaoEgress, "get", lambda *a, **k: _Resp(payload))

    client = APIClient()
    resposta = client.get("/api/mercado/indices/")

    assert resposta.status_code == 200
    indices = resposta.data["indices"]
    assert len(indices) == 2  # "OUTRO" não está em services.INDICES, fica de fora
    por_simbolo = {i["simbolo"]: i for i in indices}
    assert por_simbolo["^BVSP"]["nome"] == "Ibovespa"
    assert por_simbolo["^BVSP"]["preco"] == 209066.90
    assert por_simbolo["^BVSP"]["variacao_percentual"] == 1.38


def test_resultado_e_cacheado(settings, monkeypatch):
    settings.BRAPI_API_KEY = "chave-teste"
    chamadas = {"n": 0}

    def _fake(*a, **k):
        chamadas["n"] += 1
        return _Resp({"results": [{"symbol": "^BVSP", "regularMarketPrice": 1, "regularMarketChangePercent": 1}]})

    monkeypatch.setattr(services.SessaoEgress, "get", _fake)

    services.obter_indices()
    services.obter_indices()

    assert chamadas["n"] == 1


def test_upstream_fora_do_ar_vira_502(settings, monkeypatch):
    settings.BRAPI_API_KEY = "chave-teste"

    def _boom(*a, **k):
        raise requests.Timeout("boom")

    monkeypatch.setattr(services.SessaoEgress, "get", _boom)

    client = APIClient()
    resposta = client.get("/api/mercado/indices/")

    assert resposta.status_code == 502
