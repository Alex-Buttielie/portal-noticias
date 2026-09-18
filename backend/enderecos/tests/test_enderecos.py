"""FRENTE 5 — proxy de endereços: validação, mapeamento de erro e cache."""

from __future__ import annotations

import pytest
import requests
from django.core.cache import cache

from enderecos import services


class _Resp:
    def __init__(self, payload, status=200):
        self._payload = payload
        self.status_code = status

    def json(self):
        return self._payload


@pytest.fixture(autouse=True)
def _cache_limpo():
    cache.clear()
    yield
    cache.clear()


def test_cep_invalido_nao_chama_upstream(monkeypatch):
    chamadas = []
    monkeypatch.setattr(services.requests, "get", lambda *a, **k: chamadas.append(a) or _Resp({}))
    with pytest.raises(services.EnderecoInvalidoError):
        services.consultar_cep("123")
    assert chamadas == []


def test_cep_inexistente_vira_lookup(monkeypatch):
    monkeypatch.setattr(services.requests, "get", lambda *a, **k: _Resp({"erro": "true"}))
    with pytest.raises(services.CepNaoEncontradoError):
        services.consultar_cep("00000000")


def test_cep_ok_e_cacheado(monkeypatch):
    payload = {"cep": "01310-100", "logradouro": "Av. Paulista", "localidade": "São Paulo", "uf": "SP"}
    chamadas = []

    def _fake(url, timeout):
        chamadas.append(url)
        return _Resp(payload)

    monkeypatch.setattr(services.requests, "get", _fake)
    assert services.consultar_cep("01310-100") == payload
    assert services.consultar_cep("01310100") == payload  # máscara diferente, mesmo cache
    assert len(chamadas) == 1


def test_timeout_vira_502(monkeypatch):
    def _boom(*a, **k):
        raise requests.Timeout("x")

    monkeypatch.setattr(services.requests, "get", _boom)
    with pytest.raises(services.ServicoEnderecoIndisponivelError):
        services.consultar_cep("01310100")


def test_busca_valida_uf_cidade_logradouro(monkeypatch):
    monkeypatch.setattr(services.requests, "get", lambda *a, **k: _Resp([]))
    with pytest.raises(services.EnderecoInvalidoError):
        services.buscar_por_endereco("S", "São Paulo", "Paulista")
    with pytest.raises(services.EnderecoInvalidoError):
        services.buscar_por_endereco("SP", "SP", "Paulista")
    with pytest.raises(services.EnderecoInvalidoError):
        services.buscar_por_endereco("SP", "São Paulo", "Av")


def test_busca_sem_resultado_vira_404(monkeypatch):
    monkeypatch.setattr(services.requests, "get", lambda *a, **k: _Resp([]))
    with pytest.raises(services.CepNaoEncontradoError):
        services.buscar_por_endereco("SP", "São Paulo", "Rua Inexistente Xyz")


def test_estados_cacheado(monkeypatch):
    chamadas = []
    payload = [{"sigla": "SP", "nome": "São Paulo"}]

    def _fake(url, timeout):
        chamadas.append(url)
        return _Resp(payload)

    monkeypatch.setattr(services.requests, "get", _fake)
    assert services.listar_estados() == [{"sigla": "SP", "nome": "São Paulo"}]
    assert services.listar_estados() == [{"sigla": "SP", "nome": "São Paulo"}]
    assert len(chamadas) == 1


def test_municipios_uf_invalida():
    with pytest.raises(services.EnderecoInvalidoError):
        services.listar_municipios("SPP")


def test_views_mapeiam_status(client, monkeypatch):
    # 400 — validação
    r = client.get("/api/enderecos/cep/123/")
    assert r.status_code == 400

    # 404 — inexistente
    monkeypatch.setattr(services, "consultar_cep", lambda cep: (_ for _ in ()).throw(services.CepNaoEncontradoError("x")))
    r = client.get("/api/enderecos/cep/00000000/")
    assert r.status_code == 404

    # 200 — ok
    monkeypatch.setattr(services, "consultar_cep", lambda cep: {"cep": "01310-100"})
    r = client.get("/api/enderecos/cep/01310100/")
    assert r.status_code == 200 and r.json()["cep"] == "01310-100"

    # busca exige params
    r = client.get("/api/enderecos/busca/?uf=SP&cidade=SP&logradouro=Av")
    assert r.status_code == 400

    # estados ok
    monkeypatch.setattr(services, "listar_estados", lambda: [])
    r = client.get("/api/enderecos/estados/")
    assert r.status_code == 200
