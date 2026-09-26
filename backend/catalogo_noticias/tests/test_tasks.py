"""
Task Celery de ingestão — wrapper fino sobre `services.ingestao` (antes 0%
de cobertura: nunca executada porque o Beat não roda na suíte).

O serviço real NÃO é chamado aqui de propósito: sem argumentos ele leria as
fontes RSS de `settings` e faria HTTP de verdade. O teste cobre o wrapper
(task → serviço → id do registro) com o serviço dublado — o pipeline real
já é coberto por `test_sanity.py`/`test_acceptance_criteria.py`.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from catalogo_noticias import tasks


def test_ingerir_noticias_task_retorna_id_do_registro(diretorio_estado):
    registro = SimpleNamespace(
        id=42,
        total_itens_ingeridos=5,
        total_grupos_formados=2,
        erros_por_fonte={},
    )

    with patch.object(tasks, "executar_ingestao", return_value=registro) as mock:
        resultado = tasks.ingerir_noticias()

    mock.assert_called_once_with()
    assert resultado == 42


def test_ingerir_noticias_grava_o_ciclo_no_estado_duravel(diretorio_estado):
    """
    P1-03: o wrapper nao e so um delegate. O que rodou fica consultavel em
    disco, com o id do registro e os contadores -- e e dai que
    `manage.py saude_filas` le para dizer que a ingestao rodou de fato.
    """
    from config import filas_estado

    registro = SimpleNamespace(
        id=77,
        total_itens_ingeridos=11,
        total_grupos_formados=4,
        erros_por_fonte={"Fonte X": "timeout"},
    )

    with patch.object(tasks, "executar_ingestao", return_value=registro):
        tasks.ingerir_noticias()

    ciclo = filas_estado.ler_estado()["ciclos"][tasks.TASK_INGESTAO]
    assert ciclo["estado"] == "sucesso"
    assert ciclo["tentativas_observadas"] == 1
    assert ciclo["detalhe"]["registro_id"] == 77
    assert ciclo["detalhe"]["erros_por_fonte"] == 1
