"""Middleware de correlação, resposta segura e métricas HTTP."""

from __future__ import annotations

import contextvars
import logging
import time
import uuid
from typing import Any

from .metrics import record_http
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
            route = safe_path(
                getattr(resolver_match, "route", None) or request.path,
                limit=200,
            )
            record_http(request.method, route, status, elapsed)
            reset_technical_consent(technical_token)
            _request_id_ctx.reset(request_token)

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
    "RequestIdLogFilter",
    "RequestIdMiddleware",
    "get_current_request_id",
    "mark_degraded",
    "normalizar_request_id",
]
