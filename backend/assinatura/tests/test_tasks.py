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
    # P1-07: o dicionário cresceu com os contadores de renovação que
    # distinguem "renovado" de "cobrança criada aguardando o provedor" e
    # de "já havia cobrança em aberto" (a guarda anti-cobrança-dupla).
    # P1-08: e com `erros`, porque a varredura passou a isolar a falha de cada
    # assinatura — uma renovação que levanta exceção não pode mais abortar o
    # laço inteiro, e o contador é o que torna isso observável.
    assert tasks.processar_vencimentos() == {
        "expiradas": 0,
        "encerradas": 0,
        "renovadas": 0,
        "renovacoes_aguardando": 0,
        "renovacoes_ja_em_aberto": 0,
        "renovacoes_recusadas": 0,
        "erros": 0,
    }
