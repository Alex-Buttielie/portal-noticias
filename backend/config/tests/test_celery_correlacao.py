"""Correlação de log e métrica por task Celery.

Critério 18 (todo log carrega task ID quando aplicável) e 14 (métricas de job).
Sem os sinais `task_prerun`/`task_postrun` em `config/celery.py`, o
`current_task_id()` lido pelo `RedactingJsonFormatter` seria sempre `-` e um
alerta de job travado não poderia ser ligado ao job.
"""

from __future__ import annotations

import logging

import pytest
from django.test import override_settings

from config.metrics import METRICS
from config.observability import current_task_id, set_task_id

pytestmark = pytest.mark.django_db


def test_task_eager_publica_task_id_no_log_e_na_metrica(caplog):
    from feed.tasks import registrar_evento_busca

    METRICS.clear()
    caplog.set_level(logging.INFO)

    registrar_evento_busca.apply(args=("termo correlacionado", 3))

    registros = [r for r in caplog.records if getattr(r, "task_id", "-") != "-"]
    assert registros, "nenhum log de task carregou task_id"
    assert any("registrar_evento_busca" in r.getMessage() for r in registros)
    assert 'result="SUCCESS",task="feed.tasks.registrar_evento_busca"' in METRICS.render_prometheus()


def test_task_id_nao_vaza_para_depois_do_fim_da_task():
    from feed.tasks import registrar_evento_busca

    registrar_evento_busca.apply(args=("termo", 1))

    assert current_task_id() == "-"


def test_task_id_da_task_anterior_e_descartado_entre_execucoes():
    """Um worker atende várias tasks em sequência: sem `reset`, o log da
    segunda task mostraria o ID da primeira (correlação errada é pior que
    nenhuma)."""

    from celery import signals

    class _TaskFalsa:
        name = "app.tasks.falsa"

    sinais = []
    original = logging.getLogger("config.celery")
    for indice, estado in enumerate(("a", "b"), start=1):
        signals.task_prerun.send(
            sender=None, task_id=f"task-{indice}", task=_TaskFalsa, args=(), kwargs={}
        )
        sinais.append(current_task_id())
        signals.task_postrun.send(sender=None, task_id=f"task-{indice}", state=estado)

    assert sinais == ["task-1", "task-2"]
    assert current_task_id() == "-"
    assert original is logging.getLogger("config.celery")


def test_metrica_de_task_registra_resultado_nao_ok():
    from celery import signals

    METRICS.clear()

    class _TaskFalsa:
        name = "app.tasks.falha"

    signals.task_prerun.send(sender=None, task_id="task-x", task=_TaskFalsa, args=(), kwargs={})
    signals.task_postrun.send(sender=None, task_id="task-x", state="FAILURE")

    assert 'result="FAILURE",task="app.tasks.falha"' in METRICS.render_prometheus()


def test_sinal_de_prerun_nao_sobrescreve_token_externo(caplog):
    """Um `set_task_id` feito pelo chamador (ex.: task que processa um job com
    id próprio) não pode ser destruído pelo sinal, ou o log de aplicação
    perderia a correlação do job."""

    from celery import signals

    class _TaskFalsa:
        name = "app.tasks.falsa"

    token = set_task_id("job-de-dominio")
    try:
        signals.task_prerun.send(sender=None, task_id="task-y", task=_TaskFalsa, args=(), kwargs={})
        assert current_task_id() == "task-y"

        signals.task_postrun.send(sender=None, task_id="task-y", state="SUCCESS")

        # O `reset` do postrun devolve o contexto que estava antes do sinal.
        assert current_task_id() == "job-de-dominio"
    finally:
        from config.observability import reset_task_id

        reset_task_id(token)

    assert current_task_id() == "-"
