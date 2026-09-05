"""
Comando `manage.py ingerir_noticias` — atalho manual do pipeline (antes 0%
de cobertura).

O serviço real NÃO é chamado de propósito (faria HTTP nos feeds RSS); um
registro dublado exercita todos os ramos de impressão do comando: resumo
normal, fontes com erro e dia sem novidades.
"""

from __future__ import annotations

from io import StringIO
from types import SimpleNamespace
from unittest.mock import patch

from django.core.management import call_command

_PATCH_TARGET = "catalogo_noticias.management.commands.ingerir_noticias.executar_ingestao"


def _registro(**sobrescritas):
    base = {
        "id": 99,
        "total_itens_ingeridos": 3,
        "total_grupos_formados": 1,
        "total_duplicatas_agrupadas": 0,
        "chamadas_summarization_provider": 1,
        "itens_por_fonte": {"G1": 3},
        "erros_por_fonte": {},
    }
    base.update(sobrescritas)
    return SimpleNamespace(**base)


def _rodar(registro) -> str:
    saida = StringIO()
    with patch(_PATCH_TARGET, return_value=registro):
        call_command("ingerir_noticias", stdout=saida)
    return saida.getvalue()


def test_comando_imprime_resumo_da_execucao():
    saida = _rodar(_registro())

    assert "Execucao concluida (registro_id=99)" in saida
    assert "Itens novos ingeridos: 3" in saida
    assert "Grupos/acontecimentos formados: 1" in saida
    assert "G1: 3" in saida


def test_comando_lista_fontes_com_erro():
    saida = _rodar(_registro(erros_por_fonte={"UOL": "timeout simulado"}))

    assert "Fontes com erro nesta execucao:" in saida
    assert "UOL: timeout simulado" in saida


def test_comando_sem_novidades_avisa_que_esta_em_dia():
    saida = _rodar(
        _registro(total_itens_ingeridos=0, total_grupos_formados=0, itens_por_fonte={}),
    )

    assert "Nenhum item novo" in saida
