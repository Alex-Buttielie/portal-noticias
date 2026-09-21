"""Middleware X-Request-ID — observabilidade P0 item 10.

Gera/propaga X-Request-ID (uuid4 se não vier na requisição) e ecoa no
response header. Também expõe em request.META para logs e injeta em um
ContextVar para que o LOGGING filter inclua request_id em todo log da
requisição (correlação nginx ↔ Django ↔ Sentry sem grep manual).
"""

from __future__ import annotations

import contextvars
import logging
import uuid

# ContextVar: isolado por task/thread (gunicorn sync worker = thread por
# request; asyncio = task). Default "-" para logs fora de requisição
# (migrate, shell, celery beat sem HTTP).
_request_id_ctx: contextvars.ContextVar[str] = contextvars.ContextVar(
    "request_id", default="-"
)


def get_current_request_id() -> str:
    """Usado por LOGGING filter e por código que queira o id corrente."""
    return _request_id_ctx.get()


class RequestIdLogFilter(logging.Filter):
    """Filtro de logging: injeta `record.request_id` a partir do ContextVar.

    Referenciado em LOGGING.filters.request_id (config/settings.py).
    """

    def filter(self, record: logging.LogRecord) -> bool:  # noqa: D102
        # Não sobrescreve se algo já setou manualmente
        if not hasattr(record, "request_id"):
            record.request_id = _request_id_ctx.get()  # type: ignore[attr-defined]
        return True


class RequestIdMiddleware:
    """Propaga X-Request-ID: reaproveita se cliente/nginx já enviou, senão gera."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request_id = request.META.get("HTTP_X_REQUEST_ID") or str(uuid.uuid4())
        # Normaliza: garante que request.META tenha o valor final
        request.META["HTTP_X_REQUEST_ID"] = request_id
        # Opcional: expõe como atributo direto
        request.request_id = request_id  # type: ignore[attr-defined]
        # Expõe para o logging de toda a cadeia da requisição
        token = _request_id_ctx.set(request_id)
        try:
            response = self.get_response(request)
        finally:
            _request_id_ctx.reset(token)
        response["X-Request-ID"] = request_id
        return response
