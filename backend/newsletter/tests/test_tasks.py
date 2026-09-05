"""
Tasks Celery de newsletter — wrappers finos sobre `services` (antes 0% de
cobertura: nunca executadas porque o Beat não roda na suíte).

Chamar a task diretamente (`*_task()`) executa `run()` em processo, sem
broker. Os testes com serviço dublado verificam o roteamento de `periodo`;
o teste com banco vazio exercita o caminho real sem enviar nenhum e-mail.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

import pytest

from newsletter import tasks
from newsletter.models import EnvioNewsletter, InscricaoNewsletter


def _envio_falso(id=7):
    return SimpleNamespace(
        id=id,
        total_enviados=1,
        total_falhas=0,
        total_inscricoes_processadas=1,
    )


def test_task_sem_periodo_envia_para_todas_as_inscricoes():
    with patch.object(tasks, "enviar_newsletters", return_value=_envio_falso()) as mock:
        assert tasks.enviar_newsletters_task() == 7

    mock.assert_called_once_with(periodo=None)


def test_task_manha_envia_so_periodo_manha():
    with patch.object(tasks, "enviar_newsletters", return_value=_envio_falso()) as mock:
        tasks.enviar_newsletters_manha_task()

    mock.assert_called_once_with(periodo=InscricaoNewsletter.PERIODO_MANHA)


def test_task_noite_envia_so_periodo_noite():
    with patch.object(tasks, "enviar_newsletters", return_value=_envio_falso()) as mock:
        tasks.enviar_newsletters_noite_task()

    mock.assert_called_once_with(periodo=InscricaoNewsletter.PERIODO_NOITE)


@pytest.mark.django_db
def test_task_manha_sem_inscricoes_cria_envio_zerado():
    envio_id = tasks.enviar_newsletters_manha_task()

    envio = EnvioNewsletter.objects.get(pk=envio_id)
    assert envio.total_inscricoes_processadas == 0
    assert envio.total_enviados == 0
    assert envio.total_falhas == 0
