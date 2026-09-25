"""Middleware de correlação, resposta segura e métricas HTTP."""

from __future__ import annotations

import contextvars
import logging
import time
import uuid
from typing import Any

from .health import degraded_state
from .metrics import record_degradacao, record_http
from .observability import (
    configure_sentry_tags,
    environment,
    release,
    reset_technical_consent,
    safe_path,
    service,
    set_technical_consent,
)

# ContextVar: isolado por task/thread (gunicorn gthread = thread por request;
# asyncio = task). Default "-" para logs fora de requisição (migrate, shell,
# celery beat sem HTTP).
_request_id_ctx: contextvars.ContextVar[str] = contextvars.ContextVar(
    "request_id", default="-"
)

# `EventoBusca.request_id` é um CharField unique com max_length=64. O valor
# precisa ter esse limite já no middleware, antes de entrar em qualquer
# view/task; limitar apenas na gravação permitiria colisões entre IDs distintos.
MAX_REQUEST_ID_LENGTH = 64

# Rótulo de rota para path NÃO resolvido pelo URLconf. Sem isso, cada 404 com
# path aleatório (`/wp-admin`, scanner, probe) criaria uma série nova em
# `portal_http_requests_total` — cardinalidade sem limite alimentada por
# tráfego público.
ROUTE_UNMATCHED = "unmatched"


def normalizar_request_id(valor: object | None) -> str:
    """Retorna um ID seguro para header, logs e banco.

    IDs até 64 caracteres são propagados sem alteração (apenas sem espaços
    ASCII nas pontas). A imprimibilidade é verificada no valor bruto: tab e
    qualquer outro controle continuam inválidos mesmo quando ``strip()`` os
    removeria das bordas. O sentinel "-" e valores vazios também viram UUID,
    pois a task trata o sentinel como ausência. Para um valor excessivo ou com
    caracteres de controle, geramos um UUID4 em vez de truncar: truncar poderia
    fazer dois requests distintos colidirem no índice unique.
    """
    if valor is None:
        return str(uuid.uuid4())

    request_id_bruto = str(valor)
    if not request_id_bruto.isprintable():
        return str(uuid.uuid4())

    # Somente espaço ASCII é OWS aceitável depois da validação bruta. Tab,
    # newline, NBSP e C1 (incluindo U+0085) já foram rejeitados acima.
    request_id = request_id_bruto.strip(" ")
    if not request_id or request_id == "-":
        return str(uuid.uuid4())
    if len(request_id) > MAX_REQUEST_ID_LENGTH:
        return str(uuid.uuid4())
    return request_id


def get_current_request_id() -> str:
    """Usado por LOGGING filter e por código que queira o id corrente."""
    return _request_id_ctx.get()


class RequestIdLogFilter(logging.Filter):
    """Filtro de logging: injeta campos de correlação e contexto da task.

    O fallback para ``record.request`` cobre logs emitidos pelo Django depois
    do unwind do middleware (por exemplo, ``django.request`` em 404/5xx).
    """

    def filter(self, record: logging.LogRecord) -> bool:  # noqa: D102
        if not hasattr(record, "request_id"):
            rid = _request_id_ctx.get()
            if rid == "-" or not rid:
                req = getattr(record, "request", None)
                if req is not None:
                    rid = (
                        getattr(req, "request_id", None)
                        or req.META.get("HTTP_X_REQUEST_ID")
                        or "-"
                    )
            record.request_id = rid
        from .observability import current_task_id

        record.service = getattr(record, "service", service())
        record.environment = getattr(record, "environment", environment())
        record.release = getattr(record, "release", release())
        record.task_id = getattr(record, "task_id", current_task_id())
        return True


def _header_consent_tecnico(request: Any) -> bool:
    value = request.headers.get("X-Technical-Consent", "")
    return value.strip().lower() in {"1", "true", "yes", "on"}


def mark_degraded(request: Any, reason: str = "dependency") -> None:
    """Marca a resposta corrente como degradada sem expor causa ao cliente."""

    request.observability_degraded = True
    request.observability_degraded_reason = safe_path(reason, limit=120)


def _marcar_degradacao_por_dependencia(request: Any) -> None:
    """Consulta o estado das dependências opcionais (memoizado) e marca a
    resposta quando cache/Celery estão fora do ar.

    Silenciosamente degradado é o falso verde que esta instrumentação existe
    para evitar: o header `X-Operational-State: degraded` + a métrica
    `portal_degraded_responses_total` tornam o estado visível para o proxy, o
    alerta externo e o Grafana, sem derrubar a request nem vazar a causa.
    """

    try:
        estado = degraded_state()
    except Exception:  # noqa: BLE001 - observabilidade não pode derrubar requisição
        return
    if estado.get("status") == "degraded":
        mark_degraded(request, "optional-dependency")


class RequestIdMiddleware:
    """Propaga X-Request-ID, mede a request e adiciona headers de release."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        started = time.perf_counter()
        request_id = normalizar_request_id(request.META.get("HTTP_X_REQUEST_ID"))
        request.META["HTTP_X_REQUEST_ID"] = request_id
        request.request_id = request_id
        request.observability_degraded = False
        request.observability_degraded_reason = ""
        _marcar_degradacao_por_dependencia(request)

        request_token = _request_id_ctx.set(request_id)
        technical_token = set_technical_consent(
            _header_consent_tecnico(request)
            or str(getattr(request, "technical_consent", "")).lower() in {"1", "true", "yes", "on"}
        )
        configure_sentry_tags(
            request_id=request_id,
            service=service(),
            environment=environment(),
            release=release(),
        )
        status = 500
        try:
            response = self.get_response(request)
            status = int(getattr(response, "status_code", 0) or 0)
            self._add_response_headers(request, response)
            return response
        except Exception:
            # Não mascaramos a exceção: o handler Django continua responsável
            # porconvertê-la em 4xx/5xx. A métrica ainda registra a falha.
            raise
        finally:
            elapsed = time.perf_counter() - started
            resolver_match = getattr(request, "resolver_match", None)
            route = (
                safe_path(getattr(resolver_match, "route", None), limit=200)
                if getattr(resolver_match, "route", None)
                else ROUTE_UNMATCHED
            )
            record_http(request.method, route, status, elapsed)
            if getattr(request, "observability_degraded", False):
                record_degradacao(getattr(request, "observability_degraded_reason", "") or "dependency")
            reset_technical_consent(technical_token)
            _request_id_ctx.reset(request_token)

    def process_exception(self, request, exception):
        """Anexa os headers de correlação à resposta de erro 500.

        Numa exception não tratada a resposta é montada pelo handler do Django
        ACIMA deste middleware: sem este hook, o 500 saía sem `X-Request-ID` e
        sem `X-Operational-State` — justamente a resposta que o usuário cola
        como código de suporte e que o operador usa para correlacionar o log.

        Devolver uma resposta aqui SUPLANTE `response_for_exception`, então os
        dois efeitos padrão do Django precisam ser refeitos explicitamente:
        o sinal `got_request_exception` (é por ele que o Sentry e o
        `django.request` ERROR são emitidos) e o log de 5xx. Sem eles, esta
        troca trocaria um header faltando por um erro invisível — pior que o
        defeito original.
        """
        from django.conf import settings
        from django.core.exceptions import PermissionDenied
        from django.core.signals import got_request_exception
        from django.http import Http404, JsonResponse

        try:  # Django >= 5.1: erro de multipart tem resposta própria (400)
            from django.http.request import MultiPartParserError
        except ImportError:  # pragma: no cover
            MultiPartParserError = ()  # type: ignore[assignment]

        # `DEBUG_PROPAGATE_EXCEPTIONS` (pytest/debug) manda a exception
        # subir: nesse modo quem responde é o traceback do Django.
        if getattr(settings, "DEBUG_PROPAGATE_EXCEPTIONS", False):
            return None

        # Exceção de protocolo HTTP NÃO é erro interno: `Http404`,
        # `PermissionDenied` e `MultiPartParserError` têm conversão própria no
        # Django (`get_exception_response`) e interceptá-las aqui
        # transformaria um 404 legítimo — `comunidade/views.py` e
        # `credenciamento/views.py` levantam `Http404` — em 500.
        if isinstance(exception, (Http404, PermissionDenied, MultiPartParserError)):
            return None

        got_request_exception.send(sender=None, request=request)
        logging.getLogger("django.request").error(
            "Internal Server Error: %s", request.path, exc_info=exception
        )
        response = JsonResponse(
            {
                "detail": "Erro interno.",
                "request_id": getattr(request, "request_id", None) or "-",
            },
            status=500,
        )
        self._add_response_headers(request, response)
        return response

    def _add_response_headers(self, request, response) -> None:
        request_id = getattr(request, "request_id", None)
        if request_id:
            response["X-Request-ID"] = request_id
        response["X-Service"] = service()
        response["X-Environment"] = environment()
        response["X-Release"] = release()
        if getattr(request, "observability_degraded", False):
            response["X-Operational-State"] = "degraded"
        else:
            response["X-Operational-State"] = "ok"

    # Mantido como método público para testes e para integrações que usem o
    # middleware diretamente; o caminho normal já o chama no ``__call__``.
    def process_response(self, request, response):
        self._add_response_headers(request, response)
        return response


__all__ = [
    "MAX_REQUEST_ID_LENGTH",
    "ROUTE_UNMATCHED",
    "RequestIdLogFilter",
    "RequestIdMiddleware",
    "get_current_request_id",
    "mark_degraded",
    "normalizar_request_id",
]
