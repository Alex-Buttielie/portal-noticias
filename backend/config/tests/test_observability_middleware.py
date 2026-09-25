"""Middleware de correlação: headers, degradação, 500 e consentimento técnico.

Critérios 1, 2, 3, 9, 18 e 27 (implementation-contract.md).
"""

from __future__ import annotations

import logging
import uuid

import pytest
from django.core.signals import got_request_exception
from django.http import Http404, HttpResponse
from django.test import Client, RequestFactory, override_settings
from django.urls import path

from config import health
from config.metrics import METRICS, record_http
from config.middleware import (
    ROUTE_UNMATCHED,
    RequestIdMiddleware,
    mark_degraded,
    normalizar_request_id,
)
from config.observability import technical_consent

pytestmark = pytest.mark.django_db


def _view_que_quebra(_request):
    raise RuntimeError("falha interna simulada")


def _view_que_nao_encontrou(_request):
    raise Http404("conteudo inexistente")


# URLconf local: exercita o pipeline REAL de middleware (o `process_exception`
# só é invocado pelo handler do Django, não por uma chamada direta).
urlpatterns = [
    path("boom", _view_que_quebra),
    path("ausente", _view_que_nao_encontrou),
]


@pytest.fixture(autouse=True)
def _isola_memoria_de_degradacao():
    health.reset_degraded_cache()
    yield
    health.reset_degraded_cache()


# ---------------------------------------------------------------------------
# Headers de resposta
# ---------------------------------------------------------------------------


def test_headers_de_correlacao_e_release_na_resposta():
    request = RequestFactory().get("/", HTTP_X_REQUEST_ID="req-headers-1")
    response = RequestIdMiddleware(lambda _r: HttpResponse("ok"))(request)

    assert response["X-Request-ID"] == "req-headers-1"
    assert response["X-Service"] == "portal-api"
    assert response["X-Environment"]
    assert response["X-Release"]
    assert response["X-Operational-State"] == "ok"


@override_settings(
    OBSERVABILITY_SERVICE_NAME="portal-api-teste",
    OBSERVABILITY_ENVIRONMENT="homolog",
    OBSERVABILITY_RELEASE="sha-abc1234",
)
def test_headers_refletem_o_ambiente_da_release_configurados():
    """Ambiente/release vêm do settings: o mesmo valor que o painel do
    Grafana e o evento do Sentry usam (antes vinham só do ambiente, e em
    produção sem SENTRY_ENVIRONMENT o header dizia `development`)."""

    response = RequestIdMiddleware(lambda _r: HttpResponse("ok"))(RequestFactory().get("/"))

    assert response["X-Service"] == "portal-api-teste"
    assert response["X-Environment"] == "homolog"
    assert response["X-Release"] == "sha-abc1234"


@pytest.mark.parametrize(
    "bruto",
    [None, "", "-", "x" * 200, "id\ncom-controle", "\x1b[31m", "\tid-com-tab"],
)
def test_request_id_invalido_ainda_gera_header_de_correlacao_util(bruto):
    response = RequestIdMiddleware(lambda _r: HttpResponse("ok"))(
        RequestFactory().get("/", HTTP_X_REQUEST_ID=bruto)
    )

    request_id = response["X-Request-ID"]
    assert uuid.UUID(request_id).version == 4
    assert request_id.isprintable()


@override_settings(ROOT_URLCONF="config.tests.test_observability_middleware")
def test_erro_500_carrega_request_id_e_preserva_sinal_e_log(caplog):
    """Pipeline completo: a resposta de erro é montada ACIMA do middleware, e
    sem o `process_exception` o 500 saía sem código de suporte."""

    caplog.set_level(logging.ERROR, logger="django.request")
    recebidos = []

    def _receiver(sender, **kwargs):
        recebidos.append(kwargs.get("request"))

    got_request_exception.connect(_receiver)
    try:
        client = Client(raise_request_exception=False)
        response = client.get("/boom", HTTP_X_REQUEST_ID="req-erro-500")
    finally:
        got_request_exception.disconnect(_receiver)

    assert response.status_code == 500
    assert response["X-Request-ID"] == "req-erro-500"
    assert response["X-Operational-State"] in {"ok", "degraded"}
    assert b"req-erro-500" in response.content
    # Os efeitos padrão do Django precisam ser republicados: sem o sinal, o
    # Sentry e o log de 5xx nunca ocorreriam.
    assert len(recebidos) == 1
    assert any(r.name == "django.request" and r.levelno == logging.ERROR for r in caplog.records)


@override_settings(ROOT_URLCONF="config.tests.test_observability_middleware")
def test_404_continua_404_e_ganha_os_headers_de_correlacao():
    """`Http404` tem conversão própria no Django: se o `process_exception` a
    interceptasse, um 404 legítimo viraria 500 (e `comunidade`/`credenciamento`
    levantam `Http404` de verdade)."""

    response = Client().get("/ausente", HTTP_X_REQUEST_ID="req-404-1")

    assert response.status_code == 404
    assert response["X-Request-ID"] == "req-404-1"


def test_process_exception_anexa_headers_e_dispara_sinal_e_log(caplog):
    from django.core.signals import got_request_exception

    caplog.set_level(logging.ERROR, logger="django.request")
    recebidos = []

    def _receiver(sender, **kwargs):
        recebidos.append(kwargs.get("request"))

    got_request_exception.connect(_receiver)

    try:
        request = RequestFactory().get("/", HTTP_X_REQUEST_ID="req-erro-500")
        middleware = RequestIdMiddleware(lambda _r: HttpResponse("ok"))
        middleware(request)  # popula request.request_id/estado
        mark_degraded(request, "redis")
        response = middleware.process_exception(request, RuntimeError("boom"))
    finally:
        got_request_exception.disconnect(_receiver)

    assert response.status_code == 500
    assert response["X-Request-ID"] == "req-erro-500"
    assert response["X-Operational-State"] == "degraded"
    assert b"req-erro-500" in response.content
    # O efeito colateral padrão do Django precisa ser republicado: sem o sinal,
    # o Sentry e o log de 5xx nunca ocorreriam.
    assert len(recebidos) == 1
    assert any(r.name == "django.request" and r.levelno == logging.ERROR for r in caplog.records)


# ---------------------------------------------------------------------------
# Degradação
# ---------------------------------------------------------------------------


def test_resposta_degradada_quando_dependencia_opcional_cai(monkeypatch):
    monkeypatch.setattr(
        "config.middleware.degraded_state",
        lambda *a, **k: {"status": "degraded", "reasons": ("redis:error",)},
    )
    METRICS.clear()

    response = RequestIdMiddleware(lambda _r: HttpResponse("ok"))(RequestFactory().get("/"))

    assert response["X-Operational-State"] == "degraded"
    exposicao = METRICS.render_prometheus()
    assert "portal_degraded_responses_total" in exposicao


def test_probe_de_dependencia_quebrado_nao_derruba_a_requisicao(monkeypatch):
    def _explode(*_a, **_k):
        raise RuntimeError("probe morreu")

    monkeypatch.setattr("config.middleware.degraded_state", _explode)

    response = RequestIdMiddleware(lambda _r: HttpResponse("ok"))(RequestFactory().get("/"))

    assert response.status_code == 200
    assert response["X-Operational-State"] == "ok"


def test_mark_degraded_nao_expoe_a_causa_ao_cliente(monkeypatch):
    monkeypatch.setattr(
        "config.middleware.degraded_state",
        lambda *a, **k: {"status": "ok", "reasons": ()},
    )

    def view(request):
        mark_degraded(request, "/api/feed/?token=segredo-123")
        return HttpResponse("ok")

    request = RequestFactory().get("/")
    response = RequestIdMiddleware(view)(request)

    assert response["X-Operational-State"] == "degraded"
    assert "segredo" not in response.get("X-Operational-State", "")


# ---------------------------------------------------------------------------
# Consentimento técnico por header
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "header, esperado",
    [
        (None, False),
        ("1", True),
        ("true", True),
        ("TRUE", True),
        ("on", True),
        ("0", False),
        ("nao", False),
        ("", False),
    ],
)
def test_consentimento_tecnico_vem_do_header(header, esperado):
    kwargs = {"HTTP_X_TECHNICAL_CONSENT": header} if header is not None else {}
    visto = {}

    def view(_request):
        visto["consent"] = technical_consent()
        return HttpResponse("ok")

    RequestIdMiddleware(view)(RequestFactory().get("/", **kwargs))

    assert visto["consent"] is esperado


def test_consentimento_tecnico_nao_vaza_para_a_proxima_requisicao():
    vistos = []

    def view(_request):
        vistos.append(technical_consent())
        return HttpResponse("ok")

    middleware = RequestIdMiddleware(view)
    middleware(RequestFactory().get("/", HTTP_X_TECHNICAL_CONSENT="1"))
    middleware(RequestFactory().get("/"))

    assert vistos == [True, False]


# ---------------------------------------------------------------------------
# Cardinalidade das métricas HTTP
# ---------------------------------------------------------------------------


def test_path_nao_resolvido_vira_rotulo_debaixa_cardinalidade():
    METRICS.clear()
    request = RequestFactory().get("/qualquer/rota/que-nao-existe-12345")
    request.resolver_match = None
    RequestIdMiddleware(lambda _r: HttpResponse("ok", status=404))(request)

    exposicao = METRICS.render_prometheus()

    assert f'route="{ROUTE_UNMATCHED}"' in exposicao
    assert "qualquer/rota/que-nao-existe-12345" not in exposicao


def test_rota_resolvida_usa_o_padrao_da_url():
    METRICS.clear()
    from django.urls import resolve

    match = resolve("/api/feed/")
    request = RequestFactory().get("/api/feed/")
    request.resolver_match = match
    RequestIdMiddleware(lambda _r: HttpResponse("ok"))(request)

    assert 'route="api/feed/"' in METRICS.render_prometheus()


def test_record_http_normaliza_labels():
    METRICS.clear()
    record_http("get", "/api/x/" + "y" * 500, 200, 0.01)
    record_http("get", "/api/x/" + "y" * 500, 500, 0.02)

    exposicao = METRICS.render_prometheus()
    assert "y" * 200 not in exposicao
    assert 'status="200"' in exposicao and 'status="500"' in exposicao
    assert "portal_http_request_duration_seconds_count" in exposicao


def test_request_id_invalido_nao_derruba_o_normalizador():
    assert normalizar_request_id(None)
    assert normalizar_request_id(12345) == "12345"
