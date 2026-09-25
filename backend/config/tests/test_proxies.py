"""Identidade do cliente para o balde de rate limit (achado MAJOR-1).

Sem `NUM_PROXIES` configurado, o `SimpleRateThrottle.get_ident` do DRF devolve
o `X-Forwarded-For` CRU: o balde do limite era escolhido pelo próprio cliente e
os nginx versionados não definem esse header (o valor chegava intacto). Estes
testes fixam a regra nova — o header só é lido quando o par é um proxy
declarado/loopback, e só o último elemento conta.
"""

from __future__ import annotations

import pytest
from django.test import RequestFactory, override_settings

from config.proxies import (
    eh_proxy_confiavel,
    endereco_remoto,
    identificar_cliente,
    redes_confiaveis,
)

IP_EXTERNO = "203.0.113.10"  # RFC 5737, nunca roteável
IP_CONTAINER = "172.18.0.5"
IP_CLIENTE = "198.51.100.7"


def _request(xff: str | None = None, remoto: str = IP_EXTERNO, host: str = "portal.invalid"):
    extra = {"REMOTE_ADDR": remoto, "HTTP_HOST": host}
    if xff is not None:
        extra["HTTP_X_FORWARDED_FOR"] = xff
    return RequestFactory().get("/api/metricas/consent/", **extra)


# ---------------------------------------------------------------------------
# O ataque
# ---------------------------------------------------------------------------


def test_xff_forjado_nao_muda_o_balde_de_par_externo():
    """O caso do MAJOR-1: o cliente gira o `X-Forwarded-For` a cada requisição
    para conseguir um balde novo. Sem proxy declarado, o header é ignorado."""

    ids = {identificar_cliente(_request(xff=f"10.0.0.{i}")) for i in range(40)}

    assert ids == {IP_EXTERNO}


def test_xff_forjado_nao_e_autorizacao_nem_balde_com_host_forjado():
    """`Host`/`X-Forwarded-Host` não dizem nada sobre quem é o cliente: um
    `Host: 127.0.0.1` forjado não pode abrir nada."""

    request = _request(
        xff="127.0.0.1", remoto=IP_EXTERNO, host="127.0.0.1"
    )
    request.META["HTTP_X_FORWARDED_HOST"] = "127.0.0.1"

    assert identificar_cliente(request) == IP_EXTERNO
    assert eh_proxy_confiavel(request) is False


def test_xff_vazio_ou_sem_entradas_cai_no_par():
    for xff in ("", "   ", ",", ", ,"):
        assert identificar_cliente(_request(xff=xff)) == IP_EXTERNO


# ---------------------------------------------------------------------------
# Atrás de um proxy declarado (topologia real: Nginx na mesma máquina ou em
# rede de containers declarada)
# ---------------------------------------------------------------------------


def test_proxy_declarado_usa_o_ultimo_elemento_anexado_pelo_proxy():
    """`$proxy_add_x_forwarded_for` (default do Nginx) anexa o cliente real no
    FIM da cadeia; `$remote_addr` sobrescreve. Nos dois casos o último elemento
    é quem o proxy escreveu."""

    with override_settings(OBSERVABILITY_TRUSTED_PROXY_NETWORKS="172.18.0.0/16"):
        request = _request(xff=f"10.9.9.9, {IP_CLIENTE}", remoto=IP_CONTAINER)
        assert identificar_cliente(request) == IP_CLIENTE


def test_proxy_declarado_nao_aceita_header_sem_cliente_anexado():
    with override_settings(OBSERVABILITY_TRUSTED_PROXY_NETWORKS="172.18.0.0/16"):
        assert identificar_cliente(_request(remoto=IP_CONTAINER)) == IP_CONTAINER


def test_loopback_e_proxy_confiavel():
    assert eh_proxy_confiavel(_request(remoto="127.0.0.1")) is True
    assert identificar_cliente(_request(xff="203.0.113.99", remoto="127.0.0.1")) == "203.0.113.99"

    with override_settings(OBSERVABILITY_TRUSTED_PROXY_NETWORKS="172.18.0.0/16"):
        assert eh_proxy_confiavel(_request(remoto=IP_CONTAINER)) is True
    assert eh_proxy_confiavel(_request(remoto=IP_CONTAINER)) is False


def test_clientes_distintos_atras_do_proxy_tem_baldes_distintos():
    with override_settings(OBSERVABILITY_TRUSTED_PROXY_NETWORKS="172.18.0.0/16"):
        ids = {
            identificar_cliente(_request(xff=f"198.51.100.{i}", remoto=IP_CONTAINER))
            for i in (1, 2, 3)
        }

    assert len(ids) == 3


# ---------------------------------------------------------------------------
# Fail-closed de configuração
# ---------------------------------------------------------------------------


def test_rede_invalida_e_ignorada_e_avisa_uma_vez(caplog):
    import logging

    caplog.set_level(logging.WARNING, logger="config.proxies")
    with override_settings(
        OBSERVABILITY_TRUSTED_PROXY_NETWORKS="nao-e-uma-rede, 999.999.0.0/8, 172.18.0.0/16"
    ):
        for _ in range(3):
            redes = redes_confiaveis()
            assert eh_proxy_confiavel(_request(remoto=IP_CONTAINER)) is True

    avisos = [r for r in caplog.records if "valor inválido ignorado" in r.getMessage()]
    # Uma vez por valor inválido, não uma vez por requisição (flood de log).
    assert len(avisos) == 2


def test_lista_vazia_nao_confia_em_nem_um_ip_privado():
    with override_settings(OBSERVABILITY_TRUSTED_PROXY_NETWORKS=""):
        assert redes_confiaveis() == ()
        assert eh_proxy_confiavel(_request(remoto=IP_CONTAINER)) is False


@pytest.mark.parametrize("remoto", ["", "nao-e-ip", "999.999.999.999"])
def test_remoto_inutilizavel_nao_vira_balde_novo_por_requisicao(remoto):
    """Sem endereço utilizável não há balde por IP: um identificador estável
    (e inútil para o atacante) é melhor do que um balde novo por request."""

    ids = {identificar_cliente(_request(remoto=remoto)) for _ in range(5)}

    assert len(ids) == 1
    assert identificar_cliente(_request(remoto=remoto)) != ""


def test_endereco_remoto_de_request_sem_meta():
    class _RequestQuebrado:
        META = None

    assert endereco_remoto(_RequestQuebrado()) is None


# ---------------------------------------------------------------------------
# As throttles do projeto usam esta identidade
# ---------------------------------------------------------------------------


def test_toda_throttle_anonima_do_projeto_ignora_o_xff_de_par_externo(monkeypatch):
    """Prova no nível da classe, com o DRF no seu padrão cru.

    `NUM_PROXIES = 0` em `REST_FRAMEWORK` já faria o DRF usar `REMOTE_ADDR`; o
    mixin `_IdentidadePorParReal` garante que a regra também vale se alguém
    ajustar aquele setting (é a defesa que não depende de um único ponto), e
    cobre a exceção deliberada (proxy declarado). Aqui o `api_settings` do DRF é
    posto em `None` de propósito — sem isso o teste provaria o setting, não a
    classe.
    """

    from rest_framework.settings import api_settings

    from config import throttling

    monkeypatch.setattr(api_settings, "NUM_PROXIES", None, raising=False)

    classes = [
        throttling.EscritaPublicaAnonThrottle,
        throttling.AuthSensivelAnonThrottle,
        throttling.EnderecosAnonThrottle,
        throttling.ConsentimentoAnonThrottle,
    ]
    for classe in classes:
        throttle = classe()
        assert throttle.get_ident(_request(xff="10.0.0.1")) == IP_EXTERNO, classe.__name__
        assert throttle.get_ident(_request(xff="10.0.0.2")) == IP_EXTERNO, classe.__name__

    # `UserRateThrottle` NÃO muda de identidade: lá o balde é o usuário.
    assert (
        throttling.DenunciaUserThrottle.get_ident
        is not throttling._IdentidadePorParReal.get_ident
    )
