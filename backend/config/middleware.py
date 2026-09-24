"""Middleware X-Request-ID — observabilidade P0 item 10.

Gera/propaga X-Request-ID (uuid4 se não vier, ou se o valor recebido for
inválido/excessivo) e ecoa no response header. Também expõe em request.META
para logs e injeta em um ContextVar para que o LOGGING filter inclua
request_id em todo log da requisição (correlação nginx ↔ Django ↔ Sentry sem
grep manual).
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
    fazer dois requests distintos colidirem no índice unique de
    ``EventoBusca``.
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
    """Filtro de logging: injeta `record.request_id` a partir do ContextVar.

    Referenciado em LOGGING.filters.request_id (config/settings.py).

    Fallback para `record.request` (usado por `django.request` /
    `django.security` em `BaseHandler.log_response`): esse log é emitido
    *após* o `RequestIdMiddleware.__call__` já ter feito `reset()` do
    ContextVar, então `_request_id_ctx` já vale "-" nessa altura. Nesse
    caso o `LogRecord` traz `record.request` (ver `handlers/base.py`),
    de onde recuperamos `HTTP_X_REQUEST_ID`/`request_id` para não perder
    correlação nginx → Django → Sentry em 4xx/5xx.
    """

    def filter(self, record: logging.LogRecord) -> bool:  # noqa: D102
        # Não sobrescreve se algo já setou manualmente
        if hasattr(record, "request_id"):
            return True
        rid = _request_id_ctx.get()
        if rid == "-" or not rid:
            # Fallback: log emitido fora do Contexto do middleware (ex.:
            # `django.request` Not Found 404 logado em BaseHandler após
            # unwinding do middleware). Tenta extrair do request do record.
            req = getattr(record, "request", None)
            if req is not None:
                rid = (
                    getattr(req, "request_id", None)
                    or req.META.get("HTTP_X_REQUEST_ID")
                    or "-"
                )
        record.request_id = rid  # type: ignore[attr-defined]
        return True


class RequestIdMiddleware:
    """Propaga X-Request-ID: reaproveita se cliente/nginx já enviou, senão gera."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request_id = normalizar_request_id(request.META.get("HTTP_X_REQUEST_ID"))
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
