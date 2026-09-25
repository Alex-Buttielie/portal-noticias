"""Health/readiness e checks de dependências.

Liveness não toca dependências: um banco indisponível não deve fazer o
orquestrador reiniciar um processo Python que está vivo.  Readiness verifica o
banco e migrations; Redis/Celery são degradação observável (o feed pode
continuar sem cache, mas a fila não pode desaparecer em silêncio).
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from django.conf import settings
from django.core.cache import cache
from django.db import connection

from .metrics import record_dependency
from .observability import redact_text, safe_exception


@dataclass
class CheckResult:
    name: str
    status: str
    required: bool = False
    duration_ms: float = 0.0
    detail: str = ""
    meta: dict[str, Any] = field(default_factory=dict)

    def as_dict(self, detailed: bool = False) -> dict[str, Any]:
        result: dict[str, Any] = {
            "name": self.name,
            "status": self.status,
            "required": self.required,
            "duration_ms": round(self.duration_ms, 2),
        }
        if detailed:
            result["detail"] = self.detail
            if self.meta:
                result["meta"] = self.meta
        return result


def _timed(name: str, required: bool, fn) -> CheckResult:
    started = time.perf_counter()
    try:
        status, detail, meta = fn()
    except Exception as exc:  # noqa: BLE001 - health check must report any failure
        status, detail, meta = "error", safe_exception(exc), {}
    result = CheckResult(
        name=name,
        status=status,
        required=required,
        duration_ms=(time.perf_counter() - started) * 1000,
        detail=detail,
        meta=meta,
    )
    record_dependency(name, result.status == "ok", result.duration_ms / 1000)
    return result


def check_database() -> CheckResult:
    def probe():
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        return "ok", "", {"vendor": connection.vendor}

    return _timed("postgresql", True, probe)


def check_migrations() -> CheckResult:
    def probe():
        from django.db.migrations.executor import MigrationExecutor

        executor = MigrationExecutor(connection)
        plan = executor.migration_plan(executor.loader.graph.leaf_nodes())
        if plan:
            return (
                "error",
                "pending migrations",
                {"pending_count": len(plan)},
            )
        return "ok", "", {"applied": True}

    return _timed("migrations", True, probe)


def check_cache() -> CheckResult:
    def probe():
        backend = settings.CACHES.get("default", {}).get("BACKEND", "")
        if "dummy" in backend.lower() or "locmem" in backend.lower():
            return (
                "not_configured",
                "cache local/sem persistência",
                {"backend": backend.rsplit(".", 1)[-1]},
            )
        key = f"observability:health:{id(cache)}"
        cache.set(key, "ok", timeout=5)
        if cache.get(key) != "ok":
            return "error", "cache round-trip failed", {"backend": backend.rsplit(".", 1)[-1]}
        return "ok", "", {"backend": backend.rsplit(".", 1)[-1]}

    return _timed("redis", False, probe)


def check_celery() -> CheckResult:
    def probe():
        if not getattr(settings, "OBSERVABILITY_CHECK_CELERY", True):
            return "disabled", "check disabled by configuration", {}
        from config.celery import app

        inspector = app.control.inspect(timeout=float(getattr(settings, "OBSERVABILITY_CELERY_PING_TIMEOUT", 0.35)))
        replies = inspector.ping() or {}
        workers = sorted(str(name)[:120] for name in replies)
        if not workers:
            return "degraded", "no Celery worker replied", {"workers": 0}
        return "ok", "", {"workers": len(workers), "worker_names": workers}

    return _timed("celery", False, probe)


def snapshot(*, include_optional: bool = True) -> dict[str, Any]:
    """Executa checks e devolve estado agregável.

    ``ready`` significa que as dependências obrigatórias estão disponíveis.
    ``degraded`` é um estado distinto, com HTTP ainda potencialmente 200 para
    readiness: o cache é otimizável e a ausência de worker precisa aparecer no
    header/log/métrica, não ser escondida nem tirar o portal do ar.
    """

    results = [check_database(), check_migrations()]
    if include_optional:
        results.extend([check_cache(), check_celery()])
    by_name = {result.name: result for result in results}
    required_ok = all(result.status == "ok" for result in results if result.required)
    optional_bad = [result for result in results if not result.required and result.status not in {"ok", "disabled", "not_configured"}]
    if not required_ok:
        status = "error"
    elif optional_bad:
        status = "degraded"
    else:
        status = "ok"
    return {
        "status": status,
        "ready": required_ok,
        "degraded": status == "degraded",
        "checks": {name: result.as_dict(detailed=True) for name, result in by_name.items()},
        "version": {
            "service": "portal-api",
            "environment": getattr(settings, "OBSERVABILITY_ENVIRONMENT", "development"),
            "release": getattr(settings, "OBSERVABILITY_RELEASE", "local"),
        },
    }


def public_snapshot() -> dict[str, Any]:
    """Forma segura para endpoints públicos: sem mensagens de exceção."""

    data = snapshot()
    return {
        "status": data["status"],
        "ready": data["ready"],
        "degraded": data["degraded"],
        "checks": {
            name: {"status": value["status"], "required": value["required"]}
            for name, value in data["checks"].items()
        },
        "version": data["version"],
    }


def detail_text(result: CheckResult) -> str:
    return redact_text(result.detail or result.status, limit=300)


__all__ = [
    "CheckResult",
    "check_cache",
    "check_celery",
    "check_database",
    "check_migrations",
    "detail_text",
    "public_snapshot",
    "snapshot",
]
