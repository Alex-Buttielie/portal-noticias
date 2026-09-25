"""Toda entrada do `CELERY_BEAT_SCHEDULE` precisa apontar para uma task
REGISTRADA no app Celery.

O `settings.py` agendava `metricas.tasks.expurar_analytics` enquanto
`metricas/tasks.py` não existia: o beat publicava um nome que ninguém
registrou, o worker logava `Received unregistered task of type ...` e a
retenção de 12 meses simplesmente nunca acontecia — sem erro visível, sem
alerta, sem ninguém percebendo. Este teste falha no CI em vez de produção.
"""

from __future__ import annotations

import pytest
from django.conf import settings


@pytest.fixture(scope="module")
def _app_com_tasks_importadas():
    """Força o mesmo caminho do worker (`celery -A config` → autodiscover)."""

    from config.celery import app

    app.loader.import_default_modules()
    return app


def test_celery_beat_schedule_tem_entradas():
    assert settings.CELERY_BEAT_SCHEDULE, "CELERY_BEAT_SCHEDULE vazio"


def test_varredura_completa_do_beat_no_momento_do_teste(_app_com_tasks_importadas):
    """Cobre também entradas adicionadas depois da coleta de parâmetros."""

    nao_registradas = [
        entrada["task"]
        for entrada in settings.CELERY_BEAT_SCHEDULE.values()
        if entrada["task"] not in _app_com_tasks_importadas.tasks
    ]

    assert nao_registradas == [], (
        f"tasks agendadas e não registradas no app Celery: {nao_registradas}"
    )


@pytest.mark.parametrize("nome_agendamento", sorted(settings.CELERY_BEAT_SCHEDULE))
def test_task_do_beat_esta_registrada(nome_agendamento, _app_com_tasks_importadas):
    entrada = settings.CELERY_BEAT_SCHEDULE[nome_agendamento]
    nome_task = entrada["task"]

    assert isinstance(nome_task, str) and "." in nome_task
    assert nome_task in _app_com_tasks_importadas.tasks, (
        f"'{nome_agendamento}' agenda '{nome_task}', que não está registrado no app "
        f"Celery. O beat publica esse nome, o worker não conhece a task e o job "
        f"nunca roda (falha silenciosa)."
    )
    assert "schedule" in entrada and entrada["schedule"] is not None


def test_task_de_expurgo_de_analytics_esta_registrada(_app_com_tasks_importadas):
    from metricas.tasks import expurar_analytics

    nome = settings.CELERY_BEAT_SCHEDULE["metricas-expurar-analytics"]["task"]

    assert nome == "metricas.tasks.expurar_analytics"
    assert expurar_analytics.name == nome
    assert nome in _app_com_tasks_importadas.tasks


def test_todas_as_tasks_do_app_tem_nome_explicito(_app_com_tasks_importadas):
    """Nome implícito `module.task` impede o beat de referenciar a task por um
    nome estável (e quebra ao mover o módulo)."""

    sem_nome = [
        nome
        for nome, task in _app_com_tasks_importadas.tasks.items()
        if not nome.startswith("celery.") and " " in nome
    ]

    assert sem_nome == []
