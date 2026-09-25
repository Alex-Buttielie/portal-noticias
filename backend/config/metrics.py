"""Métricas técnicas lightweight em formato Prometheus.

A aplicação é multi-process (Gunicorn), portanto este registro é um baseline
por processo.  Em production, o Alloy/agent coletor deve powerhouse os
counters por instância e o Prometheus/Grafana deve somar por `instance`.  Para
métricas que precisam sobreviver a restart, use as tabelas de domínio
(ex.: `RegistroExecucaoIngestao`), o canal durável de job
(`config/job_state.py`) ou um exporter dedicado; este módulo não tenta fingir
persistência distribuída.

Duas proteções de cardinalidade existem porque o input é o tráfego público:
um path 404 por request criaria uma série nova a cada requisição e o
dicionário de counters cresceria para sempre (OOM progressivo, e um
`instance` poluído no Grafana). São três camadas, nesta ordem de importância:

1. **Vocabulário controlado no ponto de entrada** — `record_http` normaliza o
   rótulo `method` contra uma allowlist (achado MAJOR-2: `request.method` é
   texto do cliente e o parser HTTP aceita qualquer token, então cada scanner
   criava duas séries — counter + histograma); o middleware colapsa path não
   resolvido em ``unmatched``.
2. **Teto por família** (``MAX_SERIES_POR_METRICA``) — uma família que estourar
   o teto não pode comer o orçamento inteiro e despejar as métricas de sistema
   (``portal_ready``, profundidade de uma fila nova) do `/metrics`` em silêncio.
3. **Teto global** (``MAX_SERIES``) como rede de segurança, com o descarte
   contado em ``portal_metrics_series_dropped_total`` (contar é obrigatório:
   teto que esconde o próprio estouro é teto que vira armadilha).

Histograma: os buckets são **acumulados na observação**, não recalculados no
scrape. A versão anterior retinha até ``MAX_OBSERVATIONS`` floats por série e
recontava tudo dentro do lock a cada exposição — medido em 200 séries × 10 000
observações: 0,89 s e 33 MB de cópia por scrape, com o lock do registry
segurando o processo inteiro. No teto (5 000 × 10 000) isso são ~1,6 GB de
floats. Acumulando, `observe` custa O(#buckets) e o render só lê contadores já
prontos.
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
# Teto por família de métrica. O global protege o processo; este protege a
# VISIBILIDADE: `portal_http_requests_total` (alta cardinalidade por natureza)
# não pode ser a razão de `portal_ready` sumir do scrape (achado MAJOR-2).
MAX_SERIES_POR_METRICA = 500
# Rótulo `method` de baixo cardinalidade. Fora desta lista vira `other`: o
# cabeçalho da requisição é controlado pelo cliente e o parser HTTP aceita
# qualquer token, então `method` sem allowlist é rótulo escolhido por quem faz
# a requisição (envenenamento de série) e motor de crescimento sem limite.
METODOS_HTTP = ("GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS", "TRACE")
METODO_OUTRO = "other"
# Rótulo `status` normalizado: o valor vem de `response.status_code`, mas um
# chamador de `record_http` pode passar qualquer coisa. Fora de 100..599 vira
# `other` — um status é um número de três dígitos, não um texto livre.
ROTA_OUTRA = "other"
# Métrica que conta o próprio descarte: é a única série que o teto nunca
# recusa (senão o descarte contaria o descarte, recursivamente).
SERIES_DROPPED = "portal_metrics_series_dropped_total"
# Teto de rótulos distintos (`metric=`) dessa métrica. Um nome de métrica é
# código, não entrada de cliente, mas mesmo assim o contador do descarte não
# pode ser o novo lugar onde o teto estoura.
MAX_SERIES_DESCARTE = 200
DESCARTE_OUTRAS = "__outras__"


def normalizar_metodo(valor: object) -> str:
    """`method` contra a allowlist de métodos HTTP (demais → `other`)."""

    texto = str(valor or "").strip().upper()[:16]
    return texto if texto in METODOS_HTTP else METODO_OUTRO


def normalizar_status(valor: object) -> str:
    """`status` como código HTTP de três dígitos (demais → `other`)."""

    try:
        numero = int(valor)
    except (TypeError, ValueError):
        return ROTA_OUTRA
    return str(numero) if 100 <= numero <= 599 else ROTA_OUTRA


def normalizar_rota(valor: object, *, limite: int = 200) -> str:
    """`route` truncado: o vocabulário vem do URLconf (código, não cliente).

    O middleware já colapsa path não resolvido em `ROUTE_UNMATCHED`; aqui só
    resta o teto de tamanho, para que um padrão de URL enorme não gere um
    rótulo gigante (o escape de rótulo existe para o Prometheus não quebrar,
    não como proteção de cardinalidade).
    """

    return str(valor or "unknown")[:limite]


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
        # Histograma = contadores de bucket ACUMULADOS (`counts[i]` = quantas
        # observações ficaram em `limits[i]` ou abaixo), com `total` e `soma`.
        # Nada de lista de observações: o render é O(#buckets) e não há cópia
        # grande dentro do lock.
        self._histograms: dict[
            tuple[str, tuple[tuple[str, str], ...]], dict[str, object]
        ] = {}
        self._gauges: dict[tuple[str, tuple[tuple[str, str], ...]], float] = {}
        self._help: dict[str, str] = {}
        self._types: dict[str, str] = {}
        self._por_familia: dict[str, int] = defaultdict(int)

    def describe(self, name: str, metric_type: str, help_text: str) -> None:
        with self._lock:
            self._help[name] = help_text
            self._types[name] = metric_type

    def _conta_descarte(self, name: str) -> None:
        rotulo = str(name)[:64]
        key = (SERIES_DROPPED, (("metric", rotulo),))
        if key not in self._counters:
            if self._por_familia.get(SERIES_DROPPED, 0) >= MAX_SERIES_DESCARTE:
                # A métrica que conta o descarte não pode crescer sem limite
                # também: senão o teto trocaria "séries demais" por "séries
                # demais" em outra família (e ela ficaria fora do teto, por
                # definição). Acima do limite, tudo cai num rótulo único.
                key = (SERIES_DROPPED, (("metric", DESCARTE_OUTRAS),))
            self._registrou(SERIES_DROPPED)
        self._counters[key] = self._counters.get(key, 0.0) + 1.0

    def _cabe(self, nome: str) -> bool:
        """Diz se uma série nova entra, aplicando teto por família e global.

        Só `SERIES_DROPPED` é imune: é a métrica que conta o próprio descarte
        (ela própria é limitada por `MAX_SERIES_DESCARTE`).
        """

        if nome == SERIES_DROPPED:
            return True
        if self._por_familia[nome] >= MAX_SERIES_POR_METRICA:
            return False
        return len(self._counters) + len(self._histograms) + len(self._gauges) < MAX_SERIES

    def _registrou(self, nome: str) -> None:
        self._por_familia[nome] += 1

    def inc(self, name: str, value: float = 1, **labels: object) -> None:
        with self._lock:
            self._describe_auto(name, "counter", name.replace("_", " "))
            key = (name, _label_key(labels))
            if key not in self._counters:
                if not self._cabe(name):
                    self._conta_descarte(name)
                    return
                self._registrou(name)
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
            stats = self._histograms.get(key)
            if stats is None:
                if not self._cabe(name):
                    self._conta_descarte(name)
                    return
                self._registrou(name)
                stats = self._histograms[key] = {
                    "limits": (),
                    "counts": [],
                    "total": 0,
                    "soma": 0.0,
                }
            limits = stats["limits"]
            if not limits:
                # O recorte de buckets é fixado na primeira observação da série:
                # misturar populações diferentes no mesmo `_count` faria o
                # histograma mentir. No projeto todas as chamadas usam
                # `DEFAULT_BUCKETS`, então isto nunca acontece em produção —
                # é um erro de uso do chamador, não uma reconfiguração.
                limits = stats["limits"] = tuple(sorted({float(b) for b in buckets})) or DEFAULT_BUCKETS
                stats["counts"] = [0] * len(limits)
            counts = stats["counts"]
            for indice, limite in enumerate(limits):
                if numeric <= limite:
                    counts[indice] += 1
            stats["total"] += 1
            stats["soma"] += numeric

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
            if key not in self._gauges:
                if not self._cabe(name):
                    self._conta_descarte(name)
                    return
                self._registrou(name)
            self._gauges[key] = numeric

    def _describe_auto(self, name: str, metric_type: str, help_text: str) -> None:
        self._help.setdefault(name, help_text)
        self._types.setdefault(name, metric_type)

    def snapshot(self) -> dict[str, object]:
        with self._lock:
            return {
                "counters": dict(self._counters),
                "histograms": {key: dict(stats) for key, stats in self._histograms.items()},
                "gauges": dict(self._gauges),
            }

    def clear(self) -> None:
        """Usado somente por testes/isolamento; não é chamado por requests."""

        with self._lock:
            self._counters.clear()
            self._histograms.clear()
            self._gauges.clear()
            self._por_familia.clear()

    def render_prometheus(self) -> str:
        lines: list[str] = []
        # A cópia dentro do lock é pequena (contadores e contadores de bucket,
        # não observações): é o que garante uma exposição coerente sem fazer o
        # trabalho caro — ordenar valores e contar buckets — segurar o lock.
        with self._lock:
            counters = dict(self._counters)
            histograms = {key: dict(stats) for key, stats in self._histograms.items()}
            gauges = dict(self._gauges)
            descriptions = dict(self._help)
            types = dict(self._types)

        names = sorted(
            {name for name, _ in counters}
            | {name for name, _ in histograms}
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
                grouped: dict[tuple[tuple[str, str], ...], dict[str, object]] = {}
                for (metric_name, labels), stats in histograms.items():
                    if metric_name == name:
                        grouped[labels] = stats
                for labels, stats in sorted(grouped.items()):
                    limits = stats["limits"] or DEFAULT_BUCKETS
                    counts = stats["counts"] or [0] * len(limits)
                    for indice, bucket in enumerate(limits):
                        count = counts[indice] if indice < len(counts) else 0
                        lines.append(
                            # `_format_number` (e não `str`): o limite vai como
                            # "1" e não "1.0", como a exposição Prometheus espera.
                            f"{name}_bucket{_render_labels((*labels, ('le', _format_number(bucket))))} {count}"
                        )
                    lines.append(
                        f"{name}_bucket{_render_labels((*labels, ('le', '+Inf')))} {stats['total']}"
                    )
                    lines.append(
                        f"{name}_sum{_render_labels(labels)} {_format_number(stats['soma'])}"
                    )
                    lines.append(f"{name}_count{_render_labels(labels)} {stats['total']}")
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
# Analytics de produto (run 20260925-1020-observabilidade, Bloco A2). Sem estas
# séries, "nenhum evento persistido" e "todo evento descartado por falta de
# consentimento" seriam o mesmo número — um falso verde dentro do falso verde.
METRICS.describe(
    "portal_analytics_consent_rejections_total",
    "counter",
    "Analytics consent tokens or events rejected, by reason and origin",
)
METRICS.describe(
    "portal_analytics_consent_tokens_issued_total",
    "counter",
    "Analytics consent tokens issued by the backend, by category",
)
METRICS.describe(
    "portal_analytics_consent_bypass_total",
    "counter",
    "Analytics events persisted without consent validation (flag off by config)",
)
METRICS.describe(
    "portal_analytics_events_rejected_total",
    "counter",
    "Analytics events not persisted, by technical reason",
)
METRICS.describe(
    "portal_analytics_payload_fields_dropped_total",
    "counter",
    "Analytics payload fields discarded by the allowlist, bucketed by count",
)
METRICS.describe(
    "portal_healthz_legacy_total",
    "counter",
    "Calls to the legacy /healthz endpoint by result (migration signal)",
)
# Telemetria de job pelo canal durável (`config/job_state.py`). São GAUGES com
# valor ABSOLUTO lido do arquivo de estado, não contadores incrementados: o
# produtor é o worker, em outro processo, e somar por `instance` multiplicaria
# o mesmo número. Use `max()`/`last()`, nunca `sum()` nem `rate()`.
METRICS.describe(
    "portal_job_tasks_recorded",
    "gauge",
    "Job executions recorded by the worker so far, by task and result (absolute)",
)
METRICS.describe(
    "portal_job_task_retries_recorded",
    "gauge",
    "Celery retries recorded by the worker so far, by task (absolute)",
)
METRICS.describe(
    "portal_job_task_duration_seconds_sum",
    "gauge",
    "Sum of the durations of the job executions recorded so far, by task (absolute)",
)
METRICS.describe(
    "portal_job_task_duration_seconds_count",
    "gauge",
    "Number of job executions whose duration was recorded, by task (absolute)",
)
METRICS.describe(
    "portal_job_task_idle_seconds",
    "gauge",
    "Seconds since the task last finished successfully: the job lag signal "
    "(-1 means the task never finished successfully yet)",
)
METRICS.describe(
    "portal_job_state_age_seconds",
    "gauge",
    "Age of the durable job state file (freshness of the cross-process channel)",
)
# Check que não tem sinal próprio (sem heartbeat, sem estado de job): o valor 1
# é um ponto cego declarado, que o operador precisa ver como degradação.
METRICS.describe(
    "portal_health_check_not_configured",
    "gauge",
    "1 when a health check has no way to observe its subject (blind spot)",
)
METRICS.describe(
    "portal_sentry_init_failed_total",
    "counter",
    "Sentry initialisation failures swallowed at boot, by exception type",
)
METRICS.describe(
    SERIES_DROPPED,
    "counter",
    "Metric series refused after the per-process cardinality cap, by metric",
)


def record_http(method: str, route: str, status: int, duration: float) -> None:
    """Conta uma requisição HTTP com rótulos de vocabulário controlado.

    `method` e `status` vêm do cliente (o cabeçalho/linha de requisição) e por
    isso passam por allowlist (`normalizar_metodo`/`normalizar_status`); `route`
    vem do URLconf e chega já colapsado em `unmatched` quando não resolveu
    (ver `config.middleware.ROUTE_UNMATCHED`). Sem essa normalização, um scanner
    criava duas séries novas por requisição (counter + histograma) — e, ao
    estourar o teto de séries, derrubava em silêncio séries legítimas como
    `portal_http_requests_total` (achado MAJOR-2).
    """

    labels = {
        "method": normalizar_metodo(method),
        "route": normalizar_rota(route),
        "status": normalizar_status(status),
    }
    METRICS.inc("portal_http_requests_total", **labels)
    METRICS.observe("portal_http_request_duration_seconds", duration, **labels)


def record_dependency(name: str, ok: bool, duration: float) -> None:
    result = "ok" if ok else "error"
    labels = {"dependency": str(name or "unknown")[:64], "result": result}
    METRICS.inc("portal_dependency_checks_total", **labels)
    METRICS.observe("portal_dependency_check_duration_seconds", duration, **labels)


def record_celery(task_name: str, result: str, duration: float) -> None:
    """Métrica de task do PROCESSO que a executou.

    `task` vem do registro de tasks do Celery (código, não cliente) e `result`
    do estado final (vocabulário fechado do Celery), então os dois rótulos são
    de baixa cardinalidade por construção. Estas séries ficam no processo que
    roda a task: quem as publica é o canal durável de `config/job_state.py`
    (o `/metrics` é servido pelo processo web, que não executa task nenhuma).
    """

    labels = {"task": str(task_name or "unknown")[:160], "result": str(result or "unknown")[:32]}
    METRICS.inc("portal_celery_tasks_total", **labels)
    METRICS.observe("portal_celery_task_duration_seconds", duration, **labels)


def record_degradacao(reason: str = "dependency") -> None:
    """Conta resposta servida em estado degradado (Redis/Celery/feed)."""

    METRICS.inc("portal_degraded_responses_total", reason=str(reason or "dependency")[:64])


__all__ = [
    "MAX_SERIES",
    "MAX_SERIES_POR_METRICA",
    "METODOS_HTTP",
    "METRICS",
    "SERIES_DROPPED",
    "MetricsRegistry",
    "normalizar_metodo",
    "normalizar_rota",
    "normalizar_status",
    "record_celery",
    "record_degradacao",
    "record_dependency",
    "record_http",
]
