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
def _cache_limpo(settings):
    # CI roda sem Redis (IGNORE_EXCEPTIONS => cache vira no-op silencioso e
    # os testes de cache falham). Isola um LocMemCache próprio, mesmo padrão
    # de `config/tests/test_throttling.py::cache_locmem_isolado`.
    settings.CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "test-enderecos-locmem",
        }
    }
    cache.clear()
    yield
    cache.clear()


def test_cep_invalido_nao_chama_upstream(monkeypatch):
    chamadas = []
    monkeypatch.setattr(services.SessaoEgress, "get", lambda *a, **k: chamadas.append(a) or _Resp({}))
    with pytest.raises(services.EnderecoInvalidoError):
        services.consultar_cep("123")
    assert chamadas == []


def test_cep_inexistente_vira_lookup(monkeypatch):
    monkeypatch.setattr(services.SessaoEgress, "get", lambda *a, **k: _Resp({"erro": "true"}))
    with pytest.raises(services.CepNaoEncontradoError):
        services.consultar_cep("00000000")


def test_cep_ok_e_cacheado(monkeypatch):
    payload = {"cep": "01310-100", "logradouro": "Av. Paulista", "localidade": "São Paulo", "uf": "SP"}
    chamadas = []

    def _fake(_self, url, timeout):
        chamadas.append(url)
        return _Resp(payload)

    monkeypatch.setattr(services.SessaoEgress, "get", _fake)
    assert services.consultar_cep("01310-100") == payload
    assert services.consultar_cep("01310100") == payload  # máscara diferente, mesmo cache
    assert len(chamadas) == 1


def test_timeout_vira_502(monkeypatch):
    def _boom(*a, **k):
        raise requests.Timeout("x")

    monkeypatch.setattr(services.SessaoEgress, "get", _boom)
    with pytest.raises(services.ServicoEnderecoIndisponivelError):
        services.consultar_cep("01310100")


def test_busca_valida_uf_cidade_logradouro(monkeypatch):
    monkeypatch.setattr(services.SessaoEgress, "get", lambda *a, **k: _Resp([]))
    with pytest.raises(services.EnderecoInvalidoError):
        services.buscar_por_endereco("S", "São Paulo", "Paulista")
    with pytest.raises(services.EnderecoInvalidoError):
        services.buscar_por_endereco("SP", "SP", "Paulista")
    with pytest.raises(services.EnderecoInvalidoError):
        services.buscar_por_endereco("SP", "São Paulo", "Av")


def test_busca_sem_resultado_vira_404(monkeypatch):
    monkeypatch.setattr(services.SessaoEgress, "get", lambda *a, **k: _Resp([]))
    with pytest.raises(services.CepNaoEncontradoError):
        services.buscar_por_endereco("SP", "São Paulo", "Rua Inexistente Xyz")


def test_estados_cacheado(monkeypatch):
    chamadas = []
    payload = [{"sigla": "SP", "nome": "São Paulo"}]

    def _fake(_self, url, timeout):
        chamadas.append(url)
        return _Resp(payload)

    monkeypatch.setattr(services.SessaoEgress, "get", _fake)
    assert services.listar_estados() == [{"sigla": "SP", "nome": "São Paulo"}]
    assert services.listar_estados() == [{"sigla": "SP", "nome": "São Paulo"}]
    assert len(chamadas) == 1


def test_municipios_uf_invalida():
    with pytest.raises(services.EnderecoInvalidoError):
        services.listar_municipios("SPP")


def _resp_reverso(address):
    return _Resp({"address": address})


def test_reverso_ok_e_cacheado(monkeypatch):
    chamadas = []

    def _fake(_self, url, timeout, headers=None):
        chamadas.append(url)
        return _resp_reverso({
            "city": "Goiânia", "state": "Goiás", "state_code": "GO",
            "country": "Brasil", "postcode": "74000-000",
            "suburb": "Centro", "road": "Av. Goiás",
        })

    monkeypatch.setattr(services.SessaoEgress, "get", _fake)
    r1 = services.reverter_coordenadas(-16.68, -49.25)
    r2 = services.reverter_coordenadas(-16.6801, -49.2501)  # ~mesmo ponto, mesmo cache
    assert r1["cidade"] == "Goiânia" and r1["estado"] == "GO" and r1["pais"] == "Brasil"
    assert r1["bairro"] == "Centro" and r1["logradouro"] == "Av. Goiás"
    assert r2 == r1
    assert len(chamadas) == 1


def test_reverso_coordenadas_invalidas():
    with pytest.raises(services.EnderecoInvalidoError):
        services.reverter_coordenadas("abc", -49.25)
    with pytest.raises(services.EnderecoInvalidoError):
        services.reverter_coordenadas(-100, -49.25)


def test_reverso_sem_cidade_vira_404(monkeypatch):
    monkeypatch.setattr(services.SessaoEgress, "get", lambda *a, **k: _resp_reverso({}))
    with pytest.raises(services.CepNaoEncontradoError):
        services.reverter_coordenadas(0, 0)


def test_reverso_upstream_fora_vira_502(monkeypatch):
    def _boom(*a, **k):
        raise requests.Timeout("x")

    monkeypatch.setattr(services.SessaoEgress, "get", _boom)
    with pytest.raises(services.ServicoEnderecoIndisponivelError):
        services.reverter_coordenadas(-16.68, -49.25)


def test_view_reverso_mapeia_status(client, monkeypatch):
    monkeypatch.setattr(
        services, "reverter_coordenadas",
        lambda lat, lon: {"cidade": "Goiânia", "estado": "GO", "pais": "Brasil"},
    )
    r = client.get("/api/enderecos/reverso/?lat=-16.68&lon=-49.25")
    assert r.status_code == 200 and r.json()["estado"] == "GO"

    monkeypatch.setattr(
        services, "reverter_coordenadas",
        lambda lat, lon: (_ for _ in ()).throw(services.EnderecoInvalidoError("x")),
    )
    assert client.get("/api/enderecos/reverso/?lat=abc&lon=x").status_code == 400


def _resp_ip(city="Goiânia", region="GO", country="Brasil", status="success"):
    return _Resp({"status": status, "city": city, "region": region, "country": country, "zip": "74000-000"})


def test_por_ip_ok_e_cacheado(monkeypatch):
    chamadas = []

    def _fake(_self, url, timeout):
        chamadas.append(url)
        return _resp_ip()

    monkeypatch.setattr(services.SessaoEgress, "get", _fake)
    r1 = services.localizar_por_ip("189.1.2.3")
    r2 = services.localizar_por_ip("189.1.2.3")
    assert r1["cidade"] == "Goiânia" and r1["estado"] == "GO"
    assert r2 == r1 and len(chamadas) == 1


def test_por_ip_localhost_e_falha_viram_404(monkeypatch):
    with pytest.raises(services.CepNaoEncontradoError):
        services.localizar_por_ip("127.0.0.1")
    monkeypatch.setattr(services.SessaoEgress, "get", lambda *a, **k: _Resp({"status": "fail"}))
    with pytest.raises(services.CepNaoEncontradoError):
        services.localizar_por_ip("189.1.2.3")


def test_view_por_ip_ok(client, monkeypatch):
    monkeypatch.setattr(
        services, "localizar_por_ip",
        lambda ip: {"cidade": "Goiânia", "estado": "GO", "pais": "Brasil", "fonte": "ip"},
    )
    r = client.get("/api/enderecos/por-ip/", HTTP_X_REAL_IP="189.1.2.3")
    assert r.status_code == 200 and r.json()["cidade"] == "Goiânia"

def test_resolver_uf_sigla_direta():
    assert services.resolver_uf("SP") == "SP"
    assert services.resolver_uf("sp") == "SP"


def test_resolver_uf_sigla_invalida_nao_e_aceita_sem_confirmacao(monkeypatch):
    # "XX" não é UF — cai para geocodificação, que aqui é mockada sem
    # resultado: nunca inventa.
    monkeypatch.setattr(services.SessaoEgress, "get", lambda *a, **k: _Resp([]))
    assert services.resolver_uf("XX") is None


def test_resolver_uf_nome_do_estado_com_e_sem_acento():
    assert services.resolver_uf("Goiás") == "GO"
    assert services.resolver_uf("Goias") == "GO"
    assert services.resolver_uf("são paulo") == "SP"


def test_resolver_uf_cidade_virgula_uf():
    assert services.resolver_uf("Trindade, GO") == "GO"


def test_resolver_uf_nome_de_cidade_via_geocoding(monkeypatch):
    chamadas = []

    def _fake(_self, url, timeout, headers=None):
        chamadas.append(url)
        return _Resp([{"address": {"state_code": "GO", "state": "Goiás"}}])

    monkeypatch.setattr(services.SessaoEgress, "get", _fake)
    assert services.resolver_uf("Trindade") == "GO"
    assert len(chamadas) == 1
    # Resultado cacheado — segunda chamada não bate na rede de novo.
    assert services.resolver_uf("Trindade") == "GO"
    assert len(chamadas) == 1


def test_resolver_uf_nao_resolvivel_devolve_none_nunca_inventa(monkeypatch):
    monkeypatch.setattr(services.SessaoEgress, "get", lambda *a, **k: _Resp([]))
    assert services.resolver_uf("Localidade Que Não Existe De Verdade Nenhuma") is None


def test_resolver_uf_texto_vazio():
    assert services.resolver_uf("") is None
    assert services.resolver_uf(None) is None


def test_resolver_uf_geocoding_falha_vira_none_nao_erro(monkeypatch):
    def _boom(*a, **k):
        raise requests.Timeout("x")

    monkeypatch.setattr(services.SessaoEgress, "get", _boom)
    assert services.resolver_uf("Cidade Qualquer Sem Sigla") is None


def test_resolver_uf_geocoding_bloqueado_por_egress_vira_none(monkeypatch):
    def _boom(*a, **k):
        raise services.EgressBloqueado("destino não permitido")

    monkeypatch.setattr(services.SessaoEgress, "get", _boom)
    assert services.resolver_uf("Cidade Qualquer Bloqueada") is None


def test_resolver_uf_geocoding_http_erro_vira_none(monkeypatch):
    monkeypatch.setattr(services.SessaoEgress, "get", lambda *a, **k: _Resp({}, status=502))
    assert services.resolver_uf("Cidade Qualquer Com Erro Http") is None


def test_resolver_uf_geocoding_json_invalido_vira_none(monkeypatch):
    class _RespQuebrado(_Resp):
        def json(self):
            raise ValueError("corpo não é JSON")

    monkeypatch.setattr(services.SessaoEgress, "get", lambda *a, **k: _RespQuebrado({}))
    assert services.resolver_uf("Cidade Qualquer Com Json Quebrado") is None


def test_resolver_uf_geocoding_sem_state_code_cai_para_nome_do_estado(monkeypatch):
    monkeypatch.setattr(
        services.SessaoEgress, "get",
        lambda *a, **k: _Resp([{"address": {"state": "Goiás"}}]),
    )
    assert services.resolver_uf("Cidade Sem Sigla De Estado") == "GO"


def test_resolver_uf_geocoding_sem_estado_nenhum_vira_none(monkeypatch):
    monkeypatch.setattr(
        services.SessaoEgress, "get",
        lambda *a, **k: _Resp([{"address": {"city": "Lugar Nenhum"}}]),
    )
    assert services.resolver_uf("Cidade Sem Estado Nenhum") is None


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
