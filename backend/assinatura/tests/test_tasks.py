"""
Tasks Celery de assinatura — wrappers finos sobre `services` (antes 0% de
cobertura: nunca executados porque o Beat não roda na suíte).

Chamar a task diretamente (`processar_vencimentos()`) executa `run()` em
processo, sem broker — padrão padrão para testar wrapper sem Celery de
verdade.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from assinatura import tasks

pytestmark = pytest.mark.django_db


def test_processar_vencimentos_delega_para_o_servico_e_retorna_resultado():
    esperado = {"expiradas": 1, "encerradas": 0, "renovadas": 2}

    with patch.object(tasks, "processar_vencimentos_e_grace_periods", return_value=esperado) as mock:
        resultado = tasks.processar_vencimentos()

    mock.assert_called_once_with()
    assert resultado == esperado


def test_processar_vencimentos_sem_nada_a_processar_retorna_zeros():
    assert tasks.processar_vencimentos() == {"expiradas": 0, "encerradas": 0, "renovadas": 0}
