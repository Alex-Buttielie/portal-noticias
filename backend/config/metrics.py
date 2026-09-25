"""Métricas técnicas lightweight em formato Prometheus.

A aplicação é multi-process (Gunicorn), portanto este registro é um baseline
por processo.  Em production, o Alloy/agent coletor deve powerhouse os
counters por instância e o Prometheus/Grafana deve somar por `instance`.  Para
métricas que precisam sobreviver a restart, use as tabelas de domínio
(ex.: `RegistroExecucaoIngestao`) ou um exporter dedicado; este módulo não
tenta fingir persistência distribuída.

Duas proteções de cardinalidade existem porque o input é o tráfego público:
um path 404 por request criaria uma série nova a cada requisição e o
dicionário de counters cresceria para sempre (OOM progressivo, e um
`instance` poluído no Grafana). Por isso: (1) quem chama deve passar uma rota
de baixa cardinalidade (o middleware colapsa path não resolvido em
``unmatched``) e (2) o registry recusa séries novas acima de ``MAX_SERIES``,
contando o descarte em ``portal_metrics_series_dropped_total`` em vez de
crescer sem limite.
"""

from __future__ import annotations

import math
import threading
import time
from collections import defaultdict
from typing import Iterable, Mapping

DEFAULT_BUCKETS = (0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, 30, 60, 120)

# Teto de séries por processo. Dimensionado para o vocabulário real de rotas do
# portal (ordem de centenas) com folga larga; o exceeded é visível em /metrics.
MAX_SERIES = 5_000
# Observações retidas por série de histograma (bucket é recalculado no render).
MAX_OBSERVATIONS = 10_000
# Métrica que conta o próprio descarte: é a única série que o teto nunca
# recusa (senão o descarte contaria o descarte, recursivamente).
SERIES_DROPPED = "portal_metrics_series_dropped_total"


def _label_key(labels: Mapping[str, object]) -> tuple[tuple[str, str], ...]:
    return tuple(sorted((str(k), str(v)) for k, v in labels.items() if v is not None))


def _escape(value: str) -> str:
    return (
        value.replace("\\", "\\\\")
        .replace("\n", "\\n")
        .replace("\r", "\\r")
        .replace('"', '\\"')
    )


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
        self._gauges: dict[tuple[str, tuple[tuple[str, str], ...]], float] = {}
        self._buckets: dict[
            tuple[str, tuple[tuple[str, str], ...]], tuple[float, ...]
        ] = {}
        self._help: dict[str, str] = {}
        self._types: dict[str, str] = {}

    def describe(self, name: str, metric_type: str, help_text: str) -> None:
        with self._lock:
            self._help[name] = help_text
            self._types[name] = metric_type

    def _conta_descarte(self) -> None:
        key = (SERIES_DROPPED, ())
        self._counters[key] = self._counters.get(key, 0.0) + 1.0

    def inc(self, name: str, value: float = 1, **labels: object) -> None:
        with self._lock:
            self._describe_auto(name, "counter", name.replace("_", " "))
            key = (name, _label_key(labels))
            if (
                key not in self._counters
                and name != SERIES_DROPPED
                and len(self._counters) >= MAX_SERIES
            ):
                self._conta_descarte()
                return
            self._counters[key] += max(0.0, float(value))

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
            key = (name, _label_key(labels))
            if (
                key not in self._observations
                and name != SERIES_DROPPED
                and len(self._observations) >= MAX_SERIES
            ):
                self._conta_descarte()
                return
            # bounded list keeps accidental per-request paths from growing the
            # process forever; a real exporter can aggregate counters instead.
            values = self._observations[key]
            values.append(numeric)
            if len(values) > MAX_OBSERVATIONS:
                del values[:-MAX_OBSERVATIONS]
            # Os buckets são guardados por série: renderizar sempre com
            # DEFAULT_BUCKETS mentiria para quem pediu um recorte diferente.
            limites = tuple(sorted({float(b) for b in buckets}))
            self._buckets[key] = limites or DEFAULT_BUCKETS

    def timer(self, name: str, **labels: object):
        return _Timer(self, name, labels)

    def gauge(self, name: str, value: float, **labels: object) -> None:
        """Guarda o ÚLTIMO valor da série (estado instantâneo).

        Gauge e histograma não são intercambiáveis: um gauge de profundidade de
        fila registrado como histograma seria agregado em buckets e perderia o
        valor que o alerta de acúmulo precisa ler.
        """

        numeric = float(value)
        if not math.isfinite(numeric):
            return
        with self._lock:
            self._describe_auto(name, "gauge", name.replace("_", " "))
            key = (name, _label_key(labels))
            if (
                key not in self._gauges
                and name != SERIES_DROPPED
                and len(self._gauges) >= MAX_SERIES
            ):
                self._conta_descarte()
                return
            self._gauges[key] = numeric

    def _describe_auto(self, name: str, metric_type: str, help_text: str) -> None:
        self._help.setdefault(name, help_text)
        self._types.setdefault(name, metric_type)

    def snapshot(self) -> dict[str, object]:
        with self._lock:
            return {
                "counters": dict(self._counters),
                "observations": {key: list(values) for key, values in self._observations.items()},
                "gauges": dict(self._gauges),
            }

    def clear(self) -> None:
        """Usado somente por testes/isolamento; não é chamado por requests."""

        with self._lock:
            self._counters.clear()
            self._observations.clear()
            self._buckets.clear()
            self._gauges.clear()

    def render_prometheus(self) -> str:
        lines: list[str] = []
        with self._lock:
            counters = dict(self._counters)
            observations = {key: list(values) for key, values in self._observations.items()}
            buckets = dict(self._buckets)
            gauges = dict(self._gauges)
            descriptions = dict(self._help)
            types = dict(self._types)

        names = sorted(
            {name for name, _ in counters}
            | {name for name, _ in observations}
            | {name for name, _ in gauges}
        )
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
            elif metric_type == "gauge":
                for (metric_name, labels), value in sorted(
                    ((key[0], key[1]), value) for key, value in gauges.items() if key[0] == name
                ):
                    lines.append(f"{metric_name}{_render_labels(labels)} {_format_number(value)}")
            elif metric_type == "histogram":
                grouped: dict[tuple[tuple[str, str], ...], list[float]] = defaultdict(list)
                for (metric_name, labels), values in observations.items():
                    if metric_name == name:
                        grouped[labels].extend(values)
                for labels, values in sorted(grouped.items()):
                    ordered = sorted(values)
                    limites = buckets.get((name, labels), DEFAULT_BUCKETS)
                    for bucket in limites:
                        count = sum(1 for value in ordered if value <= bucket)
                        lines.append(
                            # `_format_number` (e não `str`): o limite vai como
                            # "1" e não "1.0", como a exposição Prometheus espera.
                            f"{name}_bucket{_render_labels((*labels, ('le', _format_number(bucket))))} {count}"
                        )
                    lines.append(
                        f"{name}_bucket{_render_labels((*labels, ('le', '+Inf')))} {len(ordered)}"
                    )
                    lines.append(f"{name}_sum{_render_labels(labels)} {_format_number(sum(ordered))}")
                    lines.append(f"{name}_count{_render_labels(labels)} {len(ordered)}")
            else:
                for (metric_name, labels), value in sorted(
                    ((key[0], key[1]), value) for key, value in counters.items() if key[0] == name
                ):
                    lines.append(f"{metric_name}{_render_labels(labels)} {_format_number(value)}")
        if not lines:
            return ""
        return "\n".join(lines) + "\n"


def _render_labels(labels) -> str:
    """Serializa rótulos para a exposição Prometheus.

    Aceita tanto a tupla de pares (chave canônica do registry) quanto um
    mapping: passar um `dict` para cá NÃO funciona, porque iterar um dict
    devolve as CHAVES e um rótulo de 2 letras ("le") desempacota silenciosamente
    como par — o bug produzia `l="e"` ou um `ValueError` mais adiante.
    """

    pares = labels.items() if hasattr(labels, "items") else labels
    pares = sorted((str(key), str(value)) for key, value in pares)
    if not pares:
        return ""
    body = ",".join(f'{key}="{_escape(value)}"' for key, value in pares)
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
METRICS.describe(
    "portal_celery_queue_depth",
    "gauge",
    "Ready messages per Celery queue at the last queue check",
)
METRICS.describe(
    "portal_collector_disk_free_ratio",
    "gauge",
    "Free space ratio of the telemetry collector filesystem",
)
METRICS.describe(
    "portal_degraded_responses_total",
    "counter",
    "Responses served while an optional dependency was degraded",
)
METRICS.describe(
    "portal_sentry_events_dropped_total",
    "counter",
    "Sentry events discarded locally before sending (no technical consent)",
)
METRICS.describe(
    SERIES_DROPPED,
    "counter",
    "Metric series refused after the per-process cardinality cap",
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


def record_degradacao(reason: str = "dependency") -> None:
    """Conta resposta servida em estado degradado (Redis/Celery/feed)."""

    METRICS.inc("portal_degraded_responses_total", reason=str(reason or "dependency")[:64])


__all__ = [
    "MAX_OBSERVATIONS",
    "MAX_SERIES",
    "METRICS",
    "SERIES_DROPPED",
    "MetricsRegistry",
    "record_celery",
    "record_degradacao",
    "record_dependency",
    "record_http",
]
