"""`/healthz` legado: 503/200 útil ao healthcheck sem vazar detalhe de erro.

Critérios 7 e 28 (implementation-contract.md, run 20260925-1020-observabilidade).
O endpoint é o alvo do `HEALTHCHECK` do Docker, do PM2 e do Nginx — logo é
público por definição, e a mensagem de exceção do driver (`could not connect to
server: host=db-interno-portal port=5432`) é exatamente o tipo de dado que não
pode sair dali.

REGRESSÃO: antes desta iteração a resposta era
`{"status": "erro", "detalhe": str(exc)}`. `test_healthz_503_nao_vaza_str_exc` falha
se o `str(exc)` voltar para o corpo, e
`test_healthz_registra_o_detalhe_no_log_tecnico` falha se o detalhe for
simplesmente descartado em vez de ir para o log.

O par canônico de saúde é `/livez` + `/readyz` (`config/observability_views.py`);
migrar o Docker/PM2/Nginx é do bloco de infra. `/healthz` fica por compatibilidade
e por causa do contador `portal_healthz_legacy_total`, que é o sinal para o
operador ver que ainda há consumidor.
"""

from __future__ import annotations

import json
import logging
from unittest import mock

import pytest
from django.db import OperationalError, connection
from django.test import Client

from config import health

pytestmark = pytest.mark.django_db

# Host/nome de banco fictício, no formato que o driver imprime: o teste
# verifica justamente que essa string NÃO aparece na resposta pública.
HOST_INTERNO = "db-interno-portal"
ERRO_DRIVER = (
    "could not connect to server: Connection refused "
    f"host={HOST_INTERNO} port=5432 user=portal password=supersecreta"
)


@pytest.fixture
def banco_fora_do_ar(monkeypatch):
    def _explode(*_args, **_kwargs):
        raise OperationalError(ERRO_DRIVER)

    monkeypatch.setattr(connection, "cursor", _explode)


def _corpo(response) -> dict:
    return json.loads(response.content.decode("utf-8"))


def test_healthz_503_nao_vaza_str_exc(banco_fora_do_ar):
    response = Client().get("/healthz")

    assert response.status_code == 503
    bruto = response.content.decode("utf-8")
    for vazamento in (
        "OperationalError",
        ERRO_DRIVER,
        "could not connect",
        HOST_INTERNO,
        "5432",
        "supersecreta",
        "Traceback",
        "detalhe",
        "SELECT",
    ):
        assert vazamento not in bruto, f"vazou no corpo público: {vazamento!r}"
    # A semântica que o healthcheck externo consome continua a mesma.
    assert _corpo(response) == {"status": "erro"}


def test_healthz_registra_o_detalhe_no_log_tecnico(banco_fora_do_ar, caplog):
    """O detalhe some da resposta pública, não do diagnóstico: quem opera
    precisa da causa, com `request_id` para correlacionar."""

    caplog.set_level(logging.WARNING, logger="config.healthz")

    response = Client().get("/healthz", HTTP_X_REQUEST_ID="id-healthz-1")

    assert response.status_code == 503
    registro = next(r for r in caplog.records if "healthz legado" in r.getMessage())
    texto = registro.getMessage()
    # Causa presente no log (redigida: sem senha, sem traceback)…
    assert "Connection refused" in texto
    assert HOST_INTERNO in texto  # no LOG o host é informação operacional legítima
    assert "supersecreta" not in texto  # … mas a senha não aparece em lugar nenhum
    assert "Traceback" not in texto
    # … e correlacionável pelo request id que o healthcheck pode mandar.
    assert registro.request_id == "id-healthz-1"
    assert registro.environment and registro.service and registro.release


def test_healthz_200_quando_o_banco_responde():
    response = Client().get("/healthz")

    assert response.status_code == 200
    assert _corpo(response) == {"status": "ok"}


def test_healthz_conta_as_chamadas_por_resultado():
    """`portal_healthz_legacy_total` é o sinal de que o endpoint legado ainda
    tem consumidor — é o dado que o bloco de infra usa para migrar."""

    from config.metrics import METRICS

    METRICS.clear()
    Client().get("/healthz")

    assert 'portal_healthz_legacy_total{result="ok"} 1' in METRICS.render_prometheus()


def test_healthz_conta_a_indisponibilidade():
    from config.metrics import METRICS

    METRICS.clear()
    with mock.patch.object(
        health,
        "check_database",
        lambda: health.CheckResult("postgresql", "error", True, 1.0, ERRO_DRIVER),
    ):
        Client().get("/healthz")

    assert 'portal_healthz_legacy_total{result="unavailable"} 1' in METRICS.render_prometheus()


def test_healthz_nao_quebra_quando_a_propria_checagem_explode(caplog):
    """Se `check_database` quebrar (import circular, monkeypatch), a resposta
    precisa continuar sendo 503 genérico — um 500 seria lido pelo orquestrador
    como "saúde desconhecida"."""

    caplog.set_level(logging.ERROR, logger="config.healthz")

    def _explode(*_args, **_kwargs):
        raise RuntimeError("falha inesperada na checagem")

    with mock.patch.object(health, "check_database", _explode):
        response = Client().get("/healthz")

    assert response.status_code == 503
    assert _corpo(response) == {"status": "erro"}
    assert "falha inesperada" not in response.content.decode("utf-8")
    assert "falha inesperada na checagem" in caplog.text


def test_healthz_nao_usa_detalhe_nao_redigido():
    """`/health-detail` é o caminho do detalhe; `/healthz` só precisa do status.

    Mesmo que um check devolvesse uma mensagem com credencial, o que sai daqui é
    o redigido por `config.observability` (`safe_exception`).
    """

    from django.test import RequestFactory

    from config.views import healthz

    with mock.patch.object(
        health,
        "check_database",
        lambda: health.CheckResult(
            "postgresql", "error", True, 1.0, f"login failed for user=portal password={ERRO_DRIVER}"
        ),
    ):
        resposta = healthz(RequestFactory().get("/healthz"))

    assert resposta.status_code == 503
    assert resposta.content.decode("utf-8") == '{"status": "erro"}'
