"""Primitivas de observabilidade do backend.

Este módulo é deliberadamente pequeno e sem dependências de UI.  Ele fornece:

* contexto de correlação (request/task) propagado por middleware e sinais
  Celery;
* redaction defensiva para logs e eventos Sentry;
* metadados de ambiente/release usados por todos os serviços;
* uma Before-Send do Sentry que nunca envia cookies, Authorization, query
  strings ou payloads de usuário.

As funções não initializam integrations externas.  Assim podem ser importadas
pelo formatter de logging, por commands de management e por testes sem DSN,
Redis ou Sentry configurados.
"""

from __future__ import annotations

import copy
import os
import re
from contextvars import ContextVar
from typing import Any
from urllib.parse import urlsplit, urlunsplit

try:  # python-json-logger é runtime, mas não é necessário para importar o módulo.
    from pythonjsonlogger.jsonlogger import JsonFormatter
except ImportError:  # pragma: no cover - fallback para ambientes mínimos
    JsonFormatter = None  # type: ignore[assignment,misc]

SERVICE_NAME = os.environ.get("OTEL_SERVICE_NAME", "portal-api").strip() or "portal-api"
ENVIRONMENT = (
    os.environ.get("SENTRY_ENVIRONMENT")
    or os.environ.get("DJANGO_ENVIRONMENT")
    or os.environ.get("APP_ENV")
    or "development"
).strip() or "development"
RELEASE = (
    os.environ.get("SENTRY_RELEASE")
    or os.environ.get("GIT_SHA")
    or os.environ.get("RELEASE_SHA")
    or "local"
).strip() or "local"

REDACTED = "[REDACTED]"
MAX_LOG_TEXT = 4_000
MAX_REDACT_DEPTH = 6
MAX_REDACT_ITEMS = 100

_task_id_ctx: ContextVar[str] = ContextVar("observability_task_id", default="-")
_technical_consent_ctx: ContextVar[bool] = ContextVar(
    "observability_technical_consent", default=False
)

# Nomes que nunca devem aparecer em telemetria. A comparação é feita sem
# diferenciar maiúsculas/minúsculas e também cobre as formas com hífen.
_SENSITIVE_KEY = re.compile(
    r"(authorization|cookie|set-cookie|password|passwd|secret|token|api[-_]?key|"
    r"access[-_]?key|private[-_]?key|credential|session|csrf|xsrf|email|e-mail|"
    r"telefone|phone|documento|document|endereco|address|ip|user[-_]?agent|"
    r"cookieConsent|query)",
    re.IGNORECASE,
)
_EMAIL = re.compile(r"(?<![\w.+-])[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}(?![\w.-])")
_BEARER = re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]+", re.IGNORECASE)
_SECRET_ASSIGNMENT = re.compile(
    r"(?i)\b(api[_-]?key|access[_-]?token|refresh[_-]?token|password|secret)\s*[:=]\s*[^\s,;]+"
)
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def current_task_id() -> str:
    """ID da task Celery corrente ou ``-`` fora de uma task."""

    return _task_id_ctx.get()


def set_task_id(task_id: object | None):
    """Define o contexto de task e devolve o token para ``reset``."""

    value = str(task_id or "-").strip() or "-"
    return _task_id_ctx.set(value[:128])


def reset_task_id(token) -> None:
    _task_id_ctx.reset(token)


def set_technical_consent(value: bool):
    """ContextVar de consentimento técnico para filtros Sentry/logs."""

    return _technical_consent_ctx.set(bool(value))


def reset_technical_consent(token) -> None:
    _technical_consent_ctx.reset(token)


def technical_consent() -> bool:
    return _technical_consent_ctx.get()


def release() -> str:
    """Release efetiva, sem aceitar-control/injection do ambiente."""

    value = RELEASE
    value = _CONTROL.sub("", value)
    return value[:200] or "local"


def environment() -> str:
    value = ENVIRONMENT
    value = _CONTROL.sub("", value)
    return value[:80] or "development"


def service() -> str:
    value = SERVICE_NAME
    value = _CONTROL.sub("", value)
    return value[:80] or "portal-api"


def is_sensitive_key(key: object) -> bool:
    return bool(_SENSITIVE_KEY.search(str(key)))


def redact_text(value: object, *, limit: int = MAX_LOG_TEXT) -> str:
    """Reduz texto a uma forma segura para log/Sentry.

    A função é conservadora: mesmo um valor que não seja um segredo pode ser
    mascarado.  False positives são aceitáveis para telemetria; vazar um token
    ou query string não é.
    """

    text = "" if value is None else str(value)
    text = _CONTROL.sub("", text)
    text = _BEARER.sub(f"Bearer {REDACTED}", text)
    text = _EMAIL.sub("[REDACTED_EMAIL]", text)
    text = _SECRET_ASSIGNMENT.sub(lambda m: f"{m.group(1)}={REDACTED}", text)
    # Não preservar query strings em URLs que apareçam em mensagens de log.
    text = re.sub(
        r"(https?://[^\s?]+)\?[^\s#]+",
        lambda m: f"{m.group(1)}?{REDACTED}",
        text,
    )
    if len(text) > max(0, limit):
        return text[: max(0, limit - 1)] + "…"
    return text


def safe_path(value: object, *, limit: int = 500) -> str:
    """Path sem query/fragment, preservando apenas o que é útil no diagnóstico."""

    raw = "" if value is None else str(value)
    try:
        parts = urlsplit(raw)
        if parts.scheme or parts.netloc:
            return redact_text(urlunsplit((parts.scheme, parts.netloc, parts.path, "", "")), limit=limit)
        # urlsplit treats an ordinary path as a path; query/fragment are removed.
        return redact_text(parts.path or raw, limit=limit)
    except Exception:
        return redact_text(raw.split("?", 1)[0].split("#", 1)[0], limit=limit)


def redact_payload(value: Any, *, _depth: int = 0, _key: object | None = None) -> Any:
    """Reduz estruturas recursivamente, com limites de CPU/tamanho.

    Listas e dicionários são limitados para que um payload de erro malicioso não
    vire um log gigante.  unknown objects viram apenas seu tipo/nome seguro.
    """

    if _key is not None and is_sensitive_key(_key):
        return REDACTED
    if _depth >= MAX_REDACT_DEPTH:
        return "[TRUNCATED_DEPTH]"
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        return redact_text(value)
    if isinstance(value, bytes):
        return f"[BYTES:{len(value)}]"
    if isinstance(value, dict):
        output: dict[str, Any] = {}
        for index, (key, item) in enumerate(value.items()):
            if index >= MAX_REDACT_ITEMS:
                output["_truncated"] = True
                break
            key_text = redact_text(key, limit=120)
            output[key_text] = redact_payload(item, _depth=_depth + 1, _key=key)
        return output
    if isinstance(value, (list, tuple, set)):
        items = list(value)[:MAX_REDACT_ITEMS]
        result = [redact_payload(item, _depth=_depth + 1) for item in items]
        if len(value) > MAX_REDACT_ITEMS:
            result.append("[TRUNCATED_ITEMS]")
        return result
    return f"[{type(value).__name__}]"


def safe_exception(exc: BaseException | None) -> str:
    """Mensagem de exceção sem traceback, credenciais ou payload."""

    if exc is None:
        return ""
    return redact_text(f"{type(exc).__name__}: {exc}")


def sentry_before_send(event: dict, hint: dict | None = None) -> dict | None:
    """Filtro Sentry fail-closed para PII e segredos.

    ``before_send`` também é o ponto de controle para o consentimento técnico
    quando o SDK está em contexto de browser/servidor.  O servidor pode
    configurar ``SENTRY_TECHNICAL_CONSENT_DEFAULT=true`` para eventos
    operacionais; o padrão é não enviar eventos quando não há contexto de
    consentimento.  O pipeline de produto continua separado.
    """

    if not bool(os.environ.get("SENTRY_TECHNICAL_CONSENT_DEFAULT", "false").lower() in {"1", "true", "yes", "on"}) and not technical_consent():
        return None
    if not isinstance(event, dict):
        return None
    safe = redact_payload(copy.deepcopy(event))
    if not isinstance(safe, dict):
        return None
    safe["environment"] = environment()
    safe["release"] = release()
    tags = safe.setdefault("tags", {})
    if isinstance(tags, dict):
        tags.setdefault("service", service())
        tags.setdefault("environment", environment())
        tags.setdefault("release", release())
        task_id = current_task_id()
        if task_id != "-":
            tags.setdefault("task_id", task_id)
    # Sentry integrations podem colocar estes campos no event mesmo com
    # send_default_pii=False. Removê-los é uma segunda barreira explícita.
    safe.pop("user", None)
    request_data = safe.get("request")
    if isinstance(request_data, dict):
        request_data.pop("cookies", None)
        request_data.pop("headers", None)
        request_data.pop("query_string", None)
        request_data.pop("data", None)
        if "url" in request_data:
            request_data["url"] = safe_path(request_data["url"], limit=1_000)
    extra = safe.get("extra")
    if isinstance(extra, dict):
        safe["extra"] = redact_payload(extra)
    return safe


def sentry_before_send_transaction(event: dict, hint: dict | None = None) -> dict | None:
    """Aplica o mesmo controle de consentimento a transações."""

    return sentry_before_send(event, hint)


def configure_sentry_tags(**values: object) -> None:
    """Define tags sem transformar a inicialização do Sentry em dependência."""

    try:
        import sentry_sdk
    except ImportError:
        return
    for key, value in values.items():
        if value not in (None, "", "-"):
            try:
                sentry_sdk.set_tag(str(key), str(value)[:200])
            except Exception:
                return


class RedactingJsonFormatter(JsonFormatter if JsonFormatter is not None else object):  # type: ignore[misc]
    """JSON logger que aplica os mesmos limites do redactor do Sentry."""

    def format(self, record):  # noqa: D102
        # Não mutamos o LogRecord original: outros handlers podem precisar do
        # traceback original dentro do mesmo processo.
        local = copy.copy(record)
        local.msg = redact_text(getattr(local, "msg", ""))
        args = getattr(local, "args", None)
        if args:
            local.args = tuple(redact_payload(arg) for arg in args)
        local.request_id = getattr(local, "request_id", "-")
        local.service = getattr(local, "service", service())
        local.environment = getattr(local, "environment", environment())
        local.release = getattr(local, "release", release())
        local.task_id = getattr(local, "task_id", current_task_id())
        return super().format(local)

    def formatException(self, ei):  # noqa: N802,D102
        return redact_text(super().formatException(ei))


__all__ = [
    "ENVIRONMENT",
    "RELEASE",
    "SERVICE_NAME",
    "RedactingJsonFormatter",
    "configure_sentry_tags",
    "current_task_id",
    "environment",
    "is_sensitive_key",
    "redact_payload",
    "redact_text",
    "release",
    "reset_task_id",
    "reset_technical_consent",
    "safe_exception",
    "safe_path",
    "sentry_before_send",
    "sentry_before_send_transaction",
    "service",
    "set_task_id",
    "set_technical_consent",
    "technical_consent",
]
