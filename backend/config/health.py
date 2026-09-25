"""Health/readiness e checks de dependências.

Liveness não toca dependências: um banco indisponível não deve fazer o
orquestrador reiniciar um processo Python que está vivo.  Readiness verifica o
banco e migrations; Redis/Celery são degradação observável (o feed pode
continuar sem cache, mas a fila não pode desaparecer em silêncio).

Três níveis, deliberadamente separados:

* ``/livez``       — o processo responde. Sem banco, sem cache, sem Celery.
* ``/readyz``      — banco + migrations (dependências obrigatórias). Público e
                     genérico: nunca devolve ``str(exc)``, traceback nem host.
* ``/health-detail``— tudo, incluindo Redis, worker Celery, filas e disco do
                     collector. Privado (loopback, staff ou bearer token).

Nenhum check expõe nome de host/worker: a topologia da VPS não é informação
pública e nem é necessária para decidir ação (o operador tem ``celery inspect``
e o Grafana para isso). O que o endpoint privado devolve é a CAUSA, redigida.
"""

from __future__ import annotations

import shutil
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from django.conf import settings
from django.core.cache import cache
from django.db import connection

from .metrics import METRICS, record_dependency
from .observability import redact_text, safe_exception, service

# Estado degradado agregado, memoizado por processo: o middleware consulta isso
# em toda requisição e um `celery inspect` custa centenas de ms (mais o tempo
# de espera pelo broker). Sem memoização, uma queda do broker transformaria
# TODA requisição em uma checagem bloqueante — o próprio sintoma que estamos
# tentando observar viraria a causa de indisponibilidade.
_degrade_lock = threading.Lock()
_degrade_cache: dict[str, Any] = {"status": "unknown", "checked_at": 0.0, "reasons": ()}


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
        vendor = backend.rsplit(".", 1)[-1]
        if "dummy" in backend.lower() or "locmem" in backend.lower():
            return (
                "not_configured",
                "cache local/sem persistência",
                {"backend": vendor},
            )
        # Chave estável (não derivada de `id()`): o probe precisa ser
        # repetível entre chamadas e é o que o operador consegue inspecionar
        # no Redis quando o cache está suspeito.
        key = "observability:health:ping"
        cache.set(key, "ok", timeout=5)
        if cache.get(key) != "ok":
            # Com `IGNORE_EXCEPTIONS=True` (produção) o erro do Redis é
            # engolido pelo backend: é exatamente aqui que a queda deixa de
            # ser silenciosa.
            return "error", "cache round-trip failed", {"backend": vendor}
        return "ok", "", {"backend": vendor}

    return _timed("redis", False, probe)


def check_celery() -> CheckResult:
    def probe():
        if not getattr(settings, "OBSERVABILITY_CHECK_CELERY", True):
            return "disabled", "check disabled by configuration", {}
        from config.celery import app

        timeout = float(getattr(settings, "OBSERVABILITY_CELERY_PING_TIMEOUT", 0.35))
        # 1) Portão barato: sem broker não há worker, e o `inspect().ping()` a
        #    caminho com broker fora do ar leva ~6 s (retries do kombu) numa
        #    thread que atende requisição. `max_retries=0` + connect_timeout
        #    transformam isso em ~20 ms.
        conexao = None
        try:
            conexao = app.connection_for_write(
                connect_timeout=timeout,
                transport_options={
                    "max_retries": 0,
                    "socket_connect_timeout": timeout,
                    "retry_on_timeout": False,
                },
            )
            viva = conexao.ensure_connection(max_retries=0, timeout=timeout)
        except Exception as exc:  # noqa: BLE001
            return "degraded", f"broker unreachable ({safe_exception(exc)})", {"workers": 0}
        finally:
            if conexao is not None:
                try:
                    conexao.release()
                except Exception:  # noqa: BLE001
                    pass
        if not viva:
            return "degraded", "broker unreachable", {"workers": 0}

        # 2) Só com broker de pé vale contar worker.
        respostas = app.control.inspect(timeout=timeout).ping() or []
        # `ping()` devolve uma LISTA de dicts {nome_do_worker: {"ok": "pong"}}.
        # Iterar essa lista diretamente (o que o código fazia) serializava o
        # dict inteiro como "nome do nó": contagem certa, dado errado e nome de
        # host vazando no payload. Aqui só a quantidade interessa.
        if not isinstance(respostas, (list, tuple, set)):
            respostas = []
        if not respostas:
            return "degraded", "no Celery worker replied", {"workers": 0}
        return "ok", "", {"workers": len(respostas)}

    return _timed("celery", False, probe)


def check_celery_beat() -> CheckResult:
    """Batimento do beat, via arquivo de heartbeat escrito pelo operador.

    Não existe introspection confiável de "o beat está vivo" pelo broker: o
    beat não tem identidade de worker e nada no broker prova que ele disparou
    o agendamento. Inventar um "ok" aqui seria exatamente o falso verde que
    esta run existe para eliminar. Sem `OBSERVABILITY_BEAT_HEARTBEAT_FILE`
    configurado o check é `not_configured` (visível, não verde); com ele, a
    idade do arquivo diz se o beat parou de escrever.
    """

    def probe():
        caminho = str(getattr(settings, "OBSERVABILITY_BEAT_HEARTBEAT_FILE", "") or "")
        if not caminho:
            return (
                "not_configured",
                "defina OBSERVABILITY_BEAT_HEARTBEAT_FILE para monitorar o beat",
                {},
            )
        try:
            Path(caminho).stat()
        except OSError as exc:
            return "error", "beat heartbeat file unreadable", {"errno": getattr(exc, "errno", None)}
        idade = max(0.0, time.time() - Path(caminho).stat().st_mtime)
        limite = float(getattr(settings, "OBSERVABILITY_BEAT_MAX_AGE_SECONDS", 900))
        if idade > limite:
            return "degraded", "beat heartbeat stale", {"age_seconds": round(idade, 1)}
        return "ok", "", {"age_seconds": round(idade, 1)}

    return _timed("celery_beat", False, probe)


def check_filas() -> CheckResult:
    """Profundidade das filas do broker (fila acumulada é falha em formação).

    Usa `queue_declare(passive=True)`: no Redis do projeto isso equivale a um
    `LLEN`, ou seja, número de mensagens prontas — não um palpite. A
    profundidade também vira métrica (`portal_celery_queue_depth`) para o
    alerta de acúmulo não depender de alguém abrir o endpoint.
    """

    def probe():
        from config.celery import app

        nomes = _nomes_de_filas()
        if not nomes:
            return "not_configured", "no queue configured", {}
        timeout = float(getattr(settings, "OBSERVABILITY_CELERY_PING_TIMEOUT", 0.35))
        try:
            # `connect_timeout` limita a espera: um `/health-detail` não pode
            # pendurar por conta de broker fora do ar.
            with app.connection_for_write(connect_timeout=timeout) as conexao:
                channel = conexao.default_channel
                profundidades: dict[str, int | None] = {}
                for nome in nomes:
                    try:
                        _fila, mensagens, _consumidores = channel.queue_declare(
                            queue=nome, passive=True
                        )
                        profundidades[nome] = int(mensagens or 0)
                    except Exception:  # noqa: BLE001 - fila inexistente não é erro
                        profundidades[nome] = None
        except Exception as exc:  # noqa: BLE001
            return "error", safe_exception(exc), {}
        for nome, profundidade in profundidades.items():
            METRICS.gauge("portal_celery_queue_depth", float(profundidade or 0), queue=nome)
        conhecidas = {n: p for n, p in profundidades.items() if p is not None}
        if not conhecidas:
            # Sem nenhuma leitura possível não há como afirmar "fila ok":
            # declarar passivamente falha tanto para fila ainda não criada
            # quanto para broker que não responde. `degraded` (e não `ok`)
            # porque é um ponto cego, não um sinal de saúde.
            return (
                "degraded",
                "queue depth unavailable (filas ainda não declaradas?)",
                {},
            )
        limite = int(getattr(settings, "OBSERVABILITY_QUEUE_DEPTH_WARN", 1000))
        if any((p or 0) > limite for p in conhecidas.values()):
            return (
                "degraded",
                "queue depth above threshold",
                {"limite": limite, "filas": conhecidas},
            )
        return "ok", "", {"filas": conhecidas}

    return _timed("celery_queues", False, probe)


def check_filesystem() -> CheckResult:
    """Espaço em disco do path do collector de telemetria/log.

    Sem espaço, o coletor para de escrever e a ausência de alerta deixa de ser
    observável — a falha se torna invisível exatamente quando mais importa.
    """

    def probe():
        caminho = str(
            getattr(settings, "OBSERVABILITY_COLLECTOR_PATH", "")
            or getattr(settings, "BASE_DIR", "")
        )
        if not caminho:
            return "not_configured", "no collector path configured", {}
        try:
            uso = shutil.disk_usage(caminho)
        except OSError as exc:
            return "error", "collector path unreadable", {"errno": getattr(exc, "errno", None)}
        livre = uso.free / uso.total if uso.total else 0.0
        METRICS.gauge("portal_collector_disk_free_ratio", livre)
        minimo = float(getattr(settings, "OBSERVABILITY_DISK_MIN_FREE_RATIO", 0.05))
        meta = {
            "path": caminho,
            "free_bytes": uso.free,
            "total_bytes": uso.total,
            "free_ratio": round(livre, 4),
        }
        if livre < minimo:
            return "degraded", "collector filesystem low on space", meta
        return "ok", "", meta

    return _timed("collector_disk", False, probe)


def _nomes_de_filas() -> list[str]:
    nomes = [
        str(getattr(settings, "CELERY_TASK_DEFAULT_QUEUE", "") or "").strip(),
        "celery",
    ]
    vistos: list[str] = []
    for nome in nomes:
        if nome and nome not in vistos:
            vistos.append(nome)
    return vistos


def snapshot(*, include_optional: bool = True, include_queues: bool = False) -> dict[str, Any]:
    """Executa checks e devolve estado agregável.

    ``ready`` significa que as dependências obrigatórias estão disponíveis.
    ``degraded`` é um estado distinto, com HTTP ainda potencialmente 200 para
    readiness: o cache é otimizável e a ausência de worker precisa aparecer no
    header/log/métrica, não ser escondida nem tirar o portal do ar.
    """

    results = [check_database(), check_migrations()]
    if include_optional:
        # `check_filas` fica de fora do caminho de requisição (custa uma
        # conexão ao broker): ele aparece no detalhe privado e vira métrica de
        # profundidade, que é o que o alerta de acúmulo consome.
        results.extend(
            [check_cache(), check_celery(), check_celery_beat(), check_filesystem()]
        )
    if include_queues:
        results.append(check_filas())
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
            "service": service(),
            "environment": getattr(settings, "OBSERVABILITY_ENVIRONMENT", "development"),
            "release": getattr(settings, "OBSERVABILITY_RELEASE", "local"),
        },
    }


def public_snapshot() -> dict[str, Any]:
    """Forma segura para o endpoint público de readiness.

    Só dependências obrigatórias e NENHUM detalhe: o nome do check que falhou,
    a mensagem da exceção e o host do banco são informação de operação que
    não pode sair para a internet (a causa fica em `/health-detail`, privado).
    """

    data = snapshot(include_optional=False)
    return {
        "status": "ready" if data["ready"] else "unavailable",
        "ready": data["ready"],
    }


def reset_degraded_cache() -> None:
    """Limita a memoização (usado por testes/isolamento)."""

    with _degrade_lock:
        _degrade_cache.update({"status": "unknown", "checked_at": 0.0, "reasons": ()})


def degraded_state(*, force: bool = False) -> dict[str, Any]:
    """Estado das dependências OTICIONAIS, memoizado por processo.

    Devolve ``{"status": "ok"|"degraded"|"unknown", "reasons": (...), ...}``.
    ``unknown`` é o estado inicial (antes do primeiro check) e NÃO deve ser
    tratado como degradado: sem isso, todo deploy começaria degradado.
    """

    intervalo = float(getattr(settings, "OBSERVABILITY_DEGRADED_PROBE_INTERVAL_SECONDS", 15))
    agora = time.monotonic()
    with _degrade_lock:
        if not force and (agora - float(_degrade_cache["checked_at"])) < max(0.0, intervalo):
            return dict(_degrade_cache)
        resultados = [check_cache(), check_celery(), check_celery_beat(), check_filesystem()]
        reasons = tuple(
            f"{r.name}:{r.status}" for r in resultados
            if r.status not in {"ok", "disabled", "not_configured"}
        )
        estado = {
            "status": "degraded" if reasons else "ok",
            "checked_at": agora,
            "reasons": reasons,
        }
        _degrade_cache.update(estado)
        return dict(estado)


def detail_text(result: CheckResult) -> str:
    return redact_text(result.detail or result.status, limit=300)


__all__ = [
    "CheckResult",
    "check_cache",
    "check_celery",
    "check_celery_beat",
    "check_database",
    "check_filesystem",
    "check_filas",
    "check_migrations",
    "degraded_state",
    "detail_text",
    "public_snapshot",
    "reset_degraded_cache",
    "snapshot",
]
