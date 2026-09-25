"""Semântica de liveness/readiness e gating dos endpoints de observabilidade.

Cobre os critérios 7, 8, 9, 16, 17 e 21 (implementation-contract.md):
processo vivo com banco fora do ar continua `live`; `/readyz` não vaza
`str(exc)`, traceback nem host; `/health-detail` e `/metrics` só respondem a
loopback, proxy declarado ou bearer token — e negam com 404 sem confirmar a
existência do diagnóstico.
"""

from __future__ import annotations

import json

import pytest
from django.db import OperationalError, connection
from django.test import Client, override_settings

from config import health

pytestmark = pytest.mark.django_db

IP_EXTERNO = "203.0.113.10"  # faixa de documentação (RFC 5737), nunca roteável
IP_CONTAINER = "172.18.0.5"
TOKEN_SAUDE = "token-de-teste-saude-nao-usar"
TOKEN_METRICAS = "token-de-teste-metricas-nao-usar"


@pytest.fixture(autouse=True)
def _isola_memoria_de_degradacao():
    """O memoizador de degradação é por processo: cada teste começa limpo."""

    health.reset_degraded_cache()
    yield
    health.reset_degraded_cache()


@pytest.fixture(autouse=True)
def _broker_em_memoria(monkeypatch):
    """Pin do broker para o transporte em memória durante a suíte.

    `Settings.broker_url` do Celery prefere `os.environ` ao setting Django, e
    `backend/.env` (carregado no boot) exporta `redis://localhost:6379/0`. Sem
    este pin, o check de fila tentaria o Redis real e o teste dependeria de uma
    porta aberta na máquina — exatamente a dependência que a suíte não deve ter.
    """

    monkeypatch.setenv("CELERY_BROKER_URL", "memory://")
    monkeypatch.setenv("CELERY_BROKER_WRITE_URL", "memory://")
    health.reset_degraded_cache()
    yield


def _body(response) -> dict:
    return json.loads(response.content.decode("utf-8"))


def _banco_fora_do_ar(monkeypatch):
    def _explode(*_args, **_kwargs):
        raise OperationalError(
            "could not connect to server: Connection refused "
            "host=db-interno-portal port=5432"
        )

    monkeypatch.setattr(connection, "cursor", _explode)


# ---------------------------------------------------------------------------
# Liveness
# ---------------------------------------------------------------------------


def test_livez_responde_mesmo_com_banco_fora_do_ar(monkeypatch):
    _banco_fora_do_ar(monkeypatch)

    response = Client().get("/livez")

    assert response.status_code == 200
    # Payload mínimo: liveness não é lugar para detalhe de dependência.
    assert _body(response) == {"status": "alive"}


def test_livez_tem_headers_de_correlacao_e_nao_e_cacheavel():
    response = Client().get("/livez", HTTP_X_REQUEST_ID="id-livez-1")

    assert response["X-Request-ID"] == "id-livez-1"
    assert response["X-Service"]
    assert response["X-Environment"]
    assert response["X-Release"]
    assert response["X-Operational-State"] in {"ok", "degraded"}
    assert "no-store" in response["Cache-Control"]


# ---------------------------------------------------------------------------
# Readiness
# ---------------------------------------------------------------------------


def test_readyz_200_com_resposta_publica_generica():
    response = Client().get("/readyz")

    assert response.status_code == 200
    corpo = _body(response)
    assert corpo == {"status": "ready", "ready": True}


def test_readyz_503_sem_expor_excecao_traceback_ou_host(monkeypatch):
    _banco_fora_do_ar(monkeypatch)

    response = Client().get("/readyz")

    assert response.status_code == 503
    bruto = response.content.decode("utf-8")
    corpo = _body(response)
    assert corpo == {"status": "unavailable", "ready": False}
    for vazamento in (
        "OperationalError",
        "could not connect",
        "db-interno-portal",
        "Traceback",
        "SELECT",
    ):
        assert vazamento not in bruto
    # A causa fica no log técnico, que tem request_id — não no corpo público.
    assert "checks" not in corpo and "detail" not in corpo


def test_readyz_503_quando_ha_migration_pendente(monkeypatch):
    class _ExecutorFalso:
        def __init__(self, _connection):
            self.loader = type("Loader", (), {"graph": type("Graph", (), {"leaf_nodes": staticmethod(lambda: [("x", "y")])})()})()

        def migration_plan(self, _targets):
            return [("catalogo_noticias", "0009_qualquer")]

    monkeypatch.setattr(
        "django.db.migrations.executor.MigrationExecutor", _ExecutorFalso, raising=True
    )

    response = Client().get("/readyz")

    assert response.status_code == 503
    assert _body(response)["ready"] is False


def test_readyz_nao_e_afetado_por_dependencia_opcional(monkeypatch):
    """Redis/Celery fora do ar é degradação, não indisponibilidade."""

    monkeypatch.setattr(
        health, "check_cache", lambda: health.CheckResult("redis", "error", False, 1.0, "cache round-trip failed")
    )

    response = Client().get("/readyz")

    assert response.status_code == 200
    assert _body(response) == {"status": "ready", "ready": True}


# ---------------------------------------------------------------------------
# /health-detail — privado
# ---------------------------------------------------------------------------


def test_health_detail_negado_para_origem_externa_sem_token():
    response = Client().get("/health-detail", REMOTE_ADDR=IP_EXTERNO)

    assert response.status_code == 404
    # 404, não 403: resposta idêntica à de uma rota inexistente.
    assert _body(response) == {"detail": "Not found."}


def test_health_detail_negado_nao_vaza_o_diagnostico():
    response = Client().get("/health-detail", REMOTE_ADDR=IP_EXTERNO)

    bruto = response.content.decode("utf-8")
    for vazamento in ("postgresql", "redis", "celery", "workers", "queues", "collector"):
        assert vazamento not in bruto


@override_settings(OBSERVABILITY_HEALTH_TOKEN=TOKEN_SAUDE)
def test_health_detail_com_bearer_token():
    response = Client().get(
        "/health-detail",
        REMOTE_ADDR=IP_EXTERNO,
        HTTP_AUTHORIZATION=f"Bearer {TOKEN_SAUDE}",
    )

    assert response.status_code == 200
    corpo = _body(response)
    assert corpo["ready"] is True
    assert set(corpo["checks"]) >= {"postgresql", "migrations", "redis", "celery"}
    assert corpo["collector"]["service"]


@override_settings(OBSERVABILITY_HEALTH_TOKEN=TOKEN_SAUDE)
def test_health_detail_com_token_errado_ou_de_outro_endpoint():
    errado = Client().get(
        "/health-detail",
        REMOTE_ADDR=IP_EXTERNO,
        HTTP_AUTHORIZATION=f"Bearer {TOKEN_METRICAS}",
    )
    sem_bearer = Client().get(
        "/health-detail", REMOTE_ADDR=IP_EXTERNO, HTTP_AUTHORIZATION=TOKEN_SAUDE
    )

    assert errado.status_code == 404
    assert sem_bearer.status_code == 404


def test_health_detail_aceita_loopback():
    response = Client().get("/health-detail", REMOTE_ADDR="127.0.0.1")

    assert response.status_code == 200
    assert _body(response)["ready"] is True


def test_health_detail_aceita_staff_autenticado_de_origem_externa():
    from django.contrib.auth import get_user_model

    User = get_user_model()
    user = User.objects.create_user(
        email="operacao@example.invalid",
        password="senha-de-teste-123",
        papel=User.PAPEL_ADMIN,
        is_staff=True,
    )
    client = Client()
    client.force_login(user)

    response = client.get("/health-detail", REMOTE_ADDR=IP_EXTERNO)

    assert response.status_code == 200


def test_health_detail_ip_privado_so_passa_com_proxy_declarado():
    """Atrás de Docker o tráfego público chega com IP privado: sem lista
    explícita de proxy confiável, isso NÃO pode virar acesso liberado."""

    sem_declaracao = Client().get("/health-detail", REMOTE_ADDR=IP_CONTAINER)
    assert sem_declaracao.status_code == 404

    with override_settings(OBSERVABILITY_TRUSTED_PROXY_NETWORKS="172.18.0.0/16"):
        declarado = Client().get("/health-detail", REMOTE_ADDR=IP_CONTAINER)
        outra_rede = Client().get("/health-detail", REMOTE_ADDR="10.9.9.9")

    assert declarado.status_code == 200
    assert outra_rede.status_code == 404


def test_health_detail_ignora_x_forwarded_for_como_autorizacao():
    """O header é controlado pelo cliente final: usá-lo seria autenticação
    por `curl -H`."""

    response = Client().get(
        "/health-detail",
        REMOTE_ADDR=IP_EXTERNO,
        HTTP_X_FORWARDED_FOR="127.0.0.1",
    )

    assert response.status_code == 404


# ---------------------------------------------------------------------------
# /metrics — loopback ou token
# ---------------------------------------------------------------------------


def test_metrics_negado_para_origem_externa():
    response = Client().get("/metrics", REMOTE_ADDR=IP_EXTERNO)

    assert response.status_code == 404


def test_metrics_loopback_expoe_prometheus():
    Client().get("/readyz")
    response = Client().get("/metrics", REMOTE_ADDR="127.0.0.1")

    assert response.status_code == 200
    assert response["Content-Type"].startswith("text/plain; version=0.0.4")
    corpo = response.content.decode("utf-8")
    assert "portal_http_requests_total" in corpo
    assert "portal_ready" in corpo


@override_settings(OBSERVABILITY_METRICS_TOKEN=TOKEN_METRICAS)
def test_metrics_com_bearer_token():
    response = Client().get(
        "/metrics",
        REMOTE_ADDR=IP_EXTERNO,
        HTTP_AUTHORIZATION=f"Bearer {TOKEN_METRICAS}",
    )

    assert response.status_code == 200
    assert "# TYPE portal_http_requests_total counter" in response.content.decode("utf-8")


@override_settings(OBSERVABILITY_METRICS_TOKEN=TOKEN_METRICAS)
def test_metrics_nao_aceita_staff_nem_token_de_saude():
    """`/metrics` é superfície de leitura de métricas técnicas: o gating é
    loopback/token, não sessão de staff (a instrução do contrato é explícita)."""

    from django.contrib.auth import get_user_model

    User = get_user_model()
    user = User.objects.create_user(
        email="operacao2@example.invalid",
        password="senha-de-teste-123",
        papel=User.PAPEL_ADMIN,
        is_staff=True,
    )
    client = Client()
    client.force_login(user)

    assert client.get("/metrics", REMOTE_ADDR=IP_EXTERNO).status_code == 404
    assert client.get(
        "/metrics", REMOTE_ADDR=IP_EXTERNO, HTTP_AUTHORIZATION=f"Bearer {TOKEN_SAUDE}"
    ).status_code == 404


# ---------------------------------------------------------------------------
# Detalhe privado: sem nome de host/worker no payload
# ---------------------------------------------------------------------------


def test_health_detail_nao_expoe_nome_de_worker_nem_host(monkeypatch):
    monkeypatch.setattr(
        health,
        "check_celery",
        lambda: health.CheckResult("celery", "ok", False, 1.0, "", {"workers": 2}),
    )

    corpo = _body(Client().get("/health-detail", REMOTE_ADDR="127.0.0.1"))

    bruto = json.dumps(corpo)
    assert "celery@" not in bruto
    assert "worker_names" not in bruto
    assert corpo["checks"]["celery"]["meta"]["workers"] == 2
