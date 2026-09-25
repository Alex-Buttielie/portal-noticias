"""Métricas técnicas lightweight em formato Prometheus.

A aplicação é multi-process (Gunicorn), portanto este registro é um baseline
por processo.  Em production, o Alloy/agent coletor deve powerhouse os
counters por instância e o Prometheus/Grafana deve somar por `instance`.  Para
métricas que precisam sobreviver a restart, use as tabelas de domínio
(ex.: `RegistroExecucaoIngestao`) ou um exporter dedicado; este módulo não
tenta fingir persistência distribuída.
"""

from __future__ import annotations

import math
import threading
import time
from collections import defaultdict
from typing import Iterable, Mapping

DEFAULT_BUCKETS = (0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, 30, 60, 120)


def _label_key(labels: Mapping[str, object]) -> tuple[tuple[str, str], ...]:
    return tuple(sorted((str(k), str(v)) for k, v in labels.items() if v is not None))


def _escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace("\n", "\\n").replace('"', '\\"')


def _format_number(value: float) -> str:
    if math.isnan(value) or math.isinf(value):
        return "0"
    return f"{value:.12g}"


class MetricsRegistry:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._counters: dict[tuple[str, tuple[tuple[str, str], ...]], float] = defaultdict(float)
        self._observations: dict[
            tuple[str, tuple[tuple[str, str], ...]], list[float]
        ] = defaultdict(list)
        self._help: dict[str, str] = {}
        self._types: dict[str, str] = {}

    def describe(self, name: str, metric_type: str, help_text: str) -> None:
        with self._lock:
            self._help[name] = help_text
            self._types[name] = metric_type

    def inc(self, name: str, value: float = 1, **labels: object) -> None:
        with self._lock:
            self._describe_auto(name, "counter", name.replace("_", " "))
            self._counters[(name, _label_key(labels))] += max(0.0, float(value))

    def observe(
        self,
        name: str,
        value: float,
        *,
        buckets: Iterable[float] = DEFAULT_BUCKETS,
        **labels: object,
    ) -> None:
        numeric = float(value)
        if not math.isfinite(numeric):
            return
        with self._lock:
            self._describe_auto(name, "histogram", name.replace("_", " "))
            # bounded list keeps accidental per-request paths from growing the
            # process forever; a real exporter can aggregate counters instead.
            values = self._observations[(name, _label_key(labels))]
            values.append(numeric)
            if len(values) > 10_000:
                del values[:-10_000]

    def timer(self, name: str, **labels: object):
        return _Timer(self, name, labels)

    def _describe_auto(self, name: str, metric_type: str, help_text: str) -> None:
        self._help.setdefault(name, help_text)
        self._types.setdefault(name, metric_type)

    def snapshot(self) -> dict[str, object]:
        with self._lock:
            return {
                "counters": dict(self._counters),
                "observations": {key: list(values) for key, values in self._observations.items()},
            }

    def clear(self) -> None:
        """Usado somente por testes/isolamento; não é chamado por requests."""

        with self._lock:
            self._counters.clear()
            self._observations.clear()

    def render_prometheus(self) -> str:
        lines: list[str] = []
        with self._lock:
            counters = dict(self._counters)
            observations = {key: list(values) for key, values in self._observations.items()}
            descriptions = dict(self._help)
            types = dict(self._types)

        names = sorted({name for name, _ in counters} | {name for name, _ in observations})
        for name in names:
            metric_type = types.get(name, "untyped")
            help_text = descriptions.get(name, name.replace("_", " "))
            lines.append(f"# HELP {name} {_escape(help_text)}")
            lines.append(f"# TYPE {name} {metric_type}")
            if metric_type == "counter":
                for (metric_name, labels), value in sorted(
                    ((key[0], key[1]), value) for key, value in counters.items() if key[0] == name
                ):
                    lines.append(f"{metric_name}{_render_labels(labels)} {_format_number(value)}")
            elif metric_type == "histogram":
                grouped: dict[tuple[tuple[str, str], ...], list[float]] = defaultdict(list)
                for (metric_name, labels), values in observations.items():
                    if metric_name == name:
                        grouped[labels].extend(values)
                for labels, values in sorted(grouped.items()):
                    ordered = sorted(values)
                    for bucket in DEFAULT_BUCKETS:
                        count = sum(1 for value in ordered if value <= bucket)
                        bucket_labels = dict(labels)
                        bucket_labels["le"] = str(bucket)
                        lines.append(
                            f"{name}_bucket{_render_labels(bucket_labels)} {count}"
                        )
                    inf_labels = dict(labels)
                    inf_labels["le"] = "+Inf"
                    lines.append(
                        f"{name}_bucket{_render_labels(inf_labels)} {len(ordered)}"
                    )
                    lines.append(f"{name}_sum{_render_labels(labels)} {_format_number(sum(ordered))}")
                    lines.append(f"{name}_count{_render_labels(labels)} {len(ordered)}")
            else:
                for (metric_name, labels), value in sorted(
                    ((key[0], key[1]), value) for key, value in counters.items() if key[0] == name
                ):
                    lines.append(f"{metric_name}{_render_labels(labels)} {_format_number(value)}")
        return "\n".join(lines) + "\n"


def _render_labels(labels: tuple[tuple[str, str], ...]) -> str:
    if not labels:
        return ""
    body = ",".join(f'{key}="{_escape(value)}"' for key, value in labels)
    return "{" + body + "}"


class _Timer:
    def __init__(self, registry: MetricsRegistry, name: str, labels: Mapping[str, object]):
        self.registry = registry
        self.name = name
        self.labels = dict(labels)
        self.started = 0.0

    def __enter__(self):
        self.started = time.perf_counter()
        return self

    def __exit__(self, exc_type, exc, tb):
        self.registry.observe(self.name, time.perf_counter() - self.started, **self.labels)
        return False


# Singleton is process-local by design; import once from middleware/health.
METRICS = MetricsRegistry()
METRICS.describe(
    "portal_http_requests_total",
    "counter",
    "HTTP requests processed by the Django process",
)
METRICS.describe(
    "portal_http_request_duration_seconds",
    "histogram",
    "Django HTTP request duration in seconds",
)
METRICS.describe(
    "portal_dependency_checks_total",
    "counter",
    "Dependency checks by dependency and result",
)
METRICS.describe(
    "portal_dependency_check_duration_seconds",
    "histogram",
    "Dependency check duration in seconds",
)
METRICS.describe(
    "portal_celery_tasks_total",
    "counter",
    "Celery task executions by task name and result",
)
METRICS.describe(
    "portal_celery_task_duration_seconds",
    "histogram",
    "Celery task duration in seconds",
)
METRICS.describe(
    "portal_ingestion_executions_total",
    "counter",
    "Durable ingestion executions by result",
)


def record_http(method: str, route: str, status: int, duration: float) -> None:
    labels = {
        "method": str(method or "UNKNOWN")[:16],
        "route": str(route or "unknown")[:200],
        "status": str(status or 0)[:8],
    }
    METRICS.inc("portal_http_requests_total", **labels)
    METRICS.observe("portal_http_request_duration_seconds", duration, **labels)


def record_dependency(name: str, ok: bool, duration: float) -> None:
    result = "ok" if ok else "error"
    labels = {"dependency": str(name or "unknown")[:64], "result": result}
    METRICS.inc("portal_dependency_checks_total", **labels)
    METRICS.observe("portal_dependency_check_duration_seconds", duration, **labels)


def record_celery(task_name: str, result: str, duration: float) -> None:
    labels = {"task": str(task_name or "unknown")[:160], "result": str(result or "unknown")[:32]}
    METRICS.inc("portal_celery_tasks_total", **labels)
    METRICS.observe("portal_celery_task_duration_seconds", duration, **labels)


__all__ = [
    "METRICS",
    "MetricsRegistry",
    "record_celery",
    "record_dependency",
    "record_http",
]
