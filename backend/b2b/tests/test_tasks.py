"""
Task Celery de alertas B2B — wrapper fino sobre `services` (antes 0% de
cobertura: nunca executada porque o Beat não roda na suíte).

Chamar a task diretamente (`verificar_alertas_task()`) executa `run()` em
processo, sem broker.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from b2b import tasks

pytestmark = pytest.mark.django_db

_ZERADO = {
    "total_criterios_verificados": 0,
    "total_alertas_enviados": 0,
    "total_falhas": 0,
}


def test_verificar_alertas_task_delega_para_o_servico_e_retorna_resultado():
    esperado = {
        "total_criterios_verificados": 2,
        "total_alertas_enviados": 1,
        "total_falhas": 0,
    }

    with patch.object(tasks, "verificar_e_enviar_alertas", return_value=esperado) as mock:
        resultado = tasks.verificar_alertas_task()

    mock.assert_called_once_with()
    assert resultado == esperado


def test_verificar_alertas_task_sem_criterios_retorna_zeros():
    assert tasks.verificar_alertas_task() == _ZERADO
