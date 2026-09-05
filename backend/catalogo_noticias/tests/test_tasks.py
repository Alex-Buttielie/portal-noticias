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


def test_ingerir_noticias_task_retorna_id_do_registro():
    registro = SimpleNamespace(id=42, total_itens_ingeridos=5, erros_por_fonte={})

    with patch.object(tasks, "executar_ingestao", return_value=registro) as mock:
        resultado = tasks.ingerir_noticias()

    mock.assert_called_once_with()
    assert resultado == 42
