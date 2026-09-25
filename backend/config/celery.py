"""
Instancia do app Celery do projeto (ARCHITECTURE.md secao 1: Celery + Redis
para jobs asincronos — ingestao periodica de noticias em
`catalogo_noticias/tasks.py`, entre outros usos futuros do projeto). Ver
`config/__init__.py` (garante que o app Celery e carregado junto com o
Django) e `config/settings.py` (`CELERY_*`, `CELERY_BEAT_SCHEDULE`).
"""

import os
import threading
import time

from celery import Celery
from celery import signals

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

app = Celery("brd_portal_noticias")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()


# ---------------------------------------------------------------------------
# Correlação de log de task (critério de aceite 18: todo log de aplicação
# carrega request/task ID quando aplicável).
#
# Sem isto, `current_task_id()` — lido pelo `RedactingJsonFormatter` — seria
# sempre "-" em qualquer log de task, e um alerta de job travado não conseguiria
# ser ligado ao job. O `task_id` também vira rótulo em
# `portal_celery_tasks_total`, que é o que o painel de jobs consome.
#
# O contexto é POR THREAD: em `prefork` há uma task por processo, mas em pool
# de threads/gevent várias tasks se intercalam na mesma thread e um dict global
# trocaria o task_id entre jobs concorrentes.
# ---------------------------------------------------------------------------
_TASK_CONTEXT = threading.local()


@signals.task_prerun.connect
def _marcar_task_prerun(task_id=None, task=None, **_kwargs):
    from .observability import reset_task_id, set_task_id

    # Um worker atende várias tasks em sequência: o token anterior precisa ser
    # descartado ou o ID vazaria para a task seguinte.
    anterior = getattr(_TASK_CONTEXT, "token", None)
    if anterior is not None:
        reset_task_id(anterior)
    _TASK_CONTEXT.token = set_task_id(task_id)
    _TASK_CONTEXT.task = getattr(task, "name", "-")
    _TASK_CONTEXT.started = time.perf_counter()
    return None


@signals.task_postrun.connect
def _marcar_task_postrun(task_id=None, state=None, **_kwargs):
    from .metrics import record_celery
    from .observability import reset_task_id

    token = getattr(_TASK_CONTEXT, "token", None)
    if token is not None:
        reset_task_id(token)
    started = getattr(_TASK_CONTEXT, "started", None)
    nome = getattr(_TASK_CONTEXT, "task", "-")
    for atributo in ("token", "task", "started"):
        if hasattr(_TASK_CONTEXT, atributo):
            delattr(_TASK_CONTEXT, atributo)
    duracao = (time.perf_counter() - started) if started else 0.0
    try:
        record_celery(nome, state or "unknown", duracao)
    except Exception:  # noqa: BLE001 - métrica nunca derruba o worker
        pass
    # O registry acima é POR PROCESSO e quem serve `/metrics` é o processo web:
    # sem este canal, `portal_celery_tasks_total` não existiria em nenhum scrape
    # (achado MAJOR-4). Ver `config/job_state.py` para o que ele entrega e o
    # que continua cross-process.
    try:
        from .job_state import registrar_task

        registrar_task(nome, state or "unknown", duracao)
    except Exception:  # noqa: BLE001 - telemetria nunca derruba o worker
        pass
    return None


@signals.task_retry.connect
def _contar_task_retry(request=None, **_kwargs):
    """Retry é um dos sinais que o critério 14 exige consultar."""

    try:
        from .job_state import registrar_retry

        registrar_retry(getattr(getattr(request, "task", None), "name", "-"))
    except Exception:  # noqa: BLE001 - telemetria nunca derruba o worker
        pass
    return None
