"""
C-05 (implementation-contract.md run 20261013-1048-home-radar-central-ux,
Bloco C): uma execução de ingestão que lança exceção não isolada deixa de
ser silenciosa — fica registrada em `RegistroExecucaoIngestao` com
`falhou=True`. Chama `_executar_ingestao_em_background` diretamente
(sem thread) para manter o teste rápido e determinístico.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from catalogo_noticias import robos_views
from catalogo_noticias.models import RegistroExecucaoIngestao

pytestmark = pytest.mark.django_db


def test_falha_na_ingestao_cria_registro_falhou_true():
    assert RegistroExecucaoIngestao.objects.count() == 0

    with patch.object(robos_views, "executar_ingestao", side_effect=RuntimeError("boom de infra")):
        robos_views._executar_ingestao_em_background("req-teste-falha")

    assert RegistroExecucaoIngestao.objects.count() == 1
    registro = RegistroExecucaoIngestao.objects.get()
    assert registro.falhou is True
    assert "boom de infra" in registro.erro_falha
    assert "req-teste-falha" in registro.erro_falha
    # Campos numéricos ficam nos defaults — não é uma execução de verdade.
    assert registro.total_itens_ingeridos == 0


def test_sucesso_na_ingestao_nao_marca_falhou():
    registro_sucesso = RegistroExecucaoIngestao(
        itens_por_fonte={"G1": 2}, total_itens_ingeridos=2, total_grupos_formados=2
    )
    registro_sucesso.save()

    with patch.object(robos_views, "executar_ingestao", return_value=registro_sucesso):
        robos_views._executar_ingestao_em_background("req-teste-sucesso")

    assert RegistroExecucaoIngestao.objects.count() == 1
    registro = RegistroExecucaoIngestao.objects.get()
    assert registro.falhou is False
    assert registro.erro_falha == ""


def test_erro_falha_e_truncado_para_nao_crescer_sem_limite():
    mensagem_gigante = "x" * 10_000
    with patch.object(robos_views, "executar_ingestao", side_effect=RuntimeError(mensagem_gigante)):
        robos_views._executar_ingestao_em_background("req-teste-truncamento")

    registro = RegistroExecucaoIngestao.objects.get()
    assert len(registro.erro_falha) <= 4000
