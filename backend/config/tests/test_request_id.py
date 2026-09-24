from __future__ import annotations

import logging
import uuid

import pytest
from django.http import HttpResponse
from django.test import RequestFactory, override_settings
from rest_framework.test import APIClient

from config.middleware import (
    MAX_REQUEST_ID_LENGTH,
    RequestIdLogFilter,
    RequestIdMiddleware,
    get_current_request_id,
    normalizar_request_id,
)
from feed.models import EventoBusca
from feed.tasks import registrar_evento_busca

pytestmark = pytest.mark.django_db


def test_request_id_longo_e_normalizado_antes_de_propagacao_e_gravacao():
    factory = RequestFactory()
    request = factory.get("/", HTTP_X_REQUEST_ID="prefixo-" + ("x" * 80))
    resposta_esperada = HttpResponse("ok")
    middleware = RequestIdMiddleware(lambda _request: resposta_esperada)

    resposta = middleware(request)
    request_id = resposta["X-Request-ID"]

    assert request_id == request.request_id
    assert request_id == request.META["HTTP_X_REQUEST_ID"]
    assert len(request_id) <= MAX_REQUEST_ID_LENGTH
    assert request_id != "prefixo-" + ("x" * 80)
    uuid.UUID(request_id)

    # Simula o worker: o valor que chega à task é exatamente o valor que o
    # middleware colocou no request e no response, sem um segundo truncamento.
    registrar_evento_busca.run("busca", 0, request_id=request_id)
    assert EventoBusca.objects.get().request_id == request_id


def test_ids_longos_distintos_nao_colidem_apos_sanitizacao():
    primeiro = normalizar_request_id("a" * 64 + "1")
    segundo = normalizar_request_id("a" * 64 + "2")

    assert primeiro != segundo
    assert len(primeiro) <= MAX_REQUEST_ID_LENGTH
    assert len(segundo) <= MAX_REQUEST_ID_LENGTH


def test_request_id_invalido_gera_uuid4_v4():
    for valor in (
        "",
        "   ",
        "-",
        "x" * 65,
        "id\ncom-controle",
        "\x1b[31m",
        "\tid-com-tab",
        "\x85trusted-id\x85",
    ):
        request_id = normalizar_request_id(valor)

        assert len(request_id) <= MAX_REQUEST_ID_LENGTH
        assert uuid.UUID(request_id).version == 4


def test_controle_c1_nas_bordas_gera_uuid4_e_nao_vaza_no_response():
    request = RequestFactory().get("/", HTTP_X_REQUEST_ID="\x85trusted-id\x85")
    middleware = RequestIdMiddleware(lambda _request: HttpResponse("ok"))

    response = middleware(request)
    request_id = response["X-Request-ID"]

    assert request_id != "trusted-id"
    assert uuid.UUID(request_id).version == 4
    assert request_id.isprintable()
    assert "\x85" not in request_id
    assert request.request_id == request_id
    assert request.META["HTTP_X_REQUEST_ID"] == request_id


@pytest.mark.parametrize(
    "valor_bruto",
    [
        "\x85trusted-id\x85",
        "trusted\x85id",
        "trusted\nid",
        "\ttrusted-id",
    ],
)
def test_controle_invalido_nao_propaga_para_header_request_log_ou_db(valor_bruto):
    request = RequestFactory().get("/", HTTP_X_REQUEST_ID=valor_bruto)
    ids_do_log = []

    def view(req):
        record = logging.LogRecord(
            "test.request_id", logging.INFO, __file__, 1, "request", (), None
        )
        assert RequestIdLogFilter().filter(record)
        ids_do_log.append(record.request_id)
        registrar_evento_busca.run("busca-invalida", 0, request_id=req.request_id)
        return HttpResponse("ok")

    response = RequestIdMiddleware(view)(request)
    request_id = response["X-Request-ID"]
    evento = EventoBusca.objects.get()

    assert uuid.UUID(request_id).version == 4
    assert request_id.isprintable()
    assert request_id == request.request_id
    assert request_id == request.META["HTTP_X_REQUEST_ID"]
    assert ids_do_log == [request_id]
    assert evento.request_id == request_id
    assert all(ord(char) >= 32 for char in request_id)


def test_ows_ascii_valido_nas_bordas_e_preservado_sem_colidir():
    esperados = ("request-ows-1", "request-ows-2")
    ids_normalizados = []

    for valor, esperado in zip((" request-ows-1 ", " request-ows-2 "), esperados):
        request = RequestFactory().get("/", HTTP_X_REQUEST_ID=valor)
        response = RequestIdMiddleware(lambda _request: HttpResponse("ok"))(request)

        assert response["X-Request-ID"] == esperado
        assert request.request_id == esperado
        assert request.META["HTTP_X_REQUEST_ID"] == esperado
        ids_normalizados.append(response["X-Request-ID"])

    assert ids_normalizados == list(esperados)
    assert len(set(ids_normalizados)) == 2


def test_middleware_preserva_id_valido_e_propaga_o_mesmo_valor_ao_contexto():
    prefixo = "id-valido-"
    valor_valido = prefixo + "á" * (MAX_REQUEST_ID_LENGTH - len(prefixo))
    assert len(valor_valido) == MAX_REQUEST_ID_LENGTH
    request = RequestFactory().get("/", HTTP_X_REQUEST_ID=valor_valido)
    contexto_visto = {}

    def view(req):
        contexto_visto["id"] = get_current_request_id()
        return HttpResponse("ok")

    resposta = RequestIdMiddleware(view)(request)

    assert resposta["X-Request-ID"] == valor_valido
    assert request.request_id == valor_valido
    assert request.META["HTTP_X_REQUEST_ID"] == valor_valido
    assert contexto_visto["id"] == valor_valido


def test_busca_persiste_o_id_igual_ao_header_e_ao_request():
    request = RequestFactory().get("/api/feed/busca/", HTTP_X_REQUEST_ID="request-igual-123")
    request_id_visto = {}

    def view(req):
        request_id_visto["value"] = req.request_id
        registrar_evento_busca.run("termo", 0, request_id=req.request_id)
        return HttpResponse("ok")

    resposta = RequestIdMiddleware(view)(request)
    evento = EventoBusca.objects.get()

    assert resposta["X-Request-ID"] == request_id_visto["value"]
    assert request.META["HTTP_X_REQUEST_ID"] == request_id_visto["value"]
    assert evento.request_id == request_id_visto["value"]


def test_ids_longos_distintos_sao_persistidos_distintos():
    primeiro = normalizar_request_id("a" * 64 + "1")
    segundo = normalizar_request_id("a" * 64 + "2")

    registrar_evento_busca.run("primeira", 0, request_id=primeiro)
    registrar_evento_busca.run("segunda", 0, request_id=segundo)

    assert set(EventoBusca.objects.values_list("request_id", flat=True)) == {
        primeiro,
        segundo,
    }


@override_settings(CELERY_TASK_ALWAYS_EAGER=True)
def test_busca_http_persiste_o_header_normalizado_no_evento():
    request_id = "api-header-id-123"
    response = APIClient().get(
        "/api/feed/busca/",
        {"q": "termo"},
        HTTP_X_REQUEST_ID=request_id,
    )

    assert response.status_code == 200
    assert response["X-Request-ID"] == request_id
    assert EventoBusca.objects.get().request_id == request_id
