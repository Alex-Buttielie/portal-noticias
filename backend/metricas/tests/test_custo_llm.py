"""
AC-7 (implementation-contract.md, run 20260903-1211-teto-gasto-diario-llm):
`metricas.services.painel()` devolve `custo_llm_hoje_usd`,
`teto_llm_diario_usd` e `teto_llm_excedido_hoje` consistentes com o estado
atual de `RegistroExecucaoIngestao` e da setting
`CATALOGO_NOTICIAS_LLM_TETO_GASTO_DIARIO_USD` — aditivo, não remove nem
renomeia nenhuma chave já existente do painel (ver
`metricas/tests/test_sanity.py::test_painel_funciona_para_admin_e_retorna_campos_esperados`).
"""

from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from django.test import override_settings
from rest_framework.test import APIClient

from catalogo_noticias.models import RegistroExecucaoIngestao
from metricas import services

pytestmark = pytest.mark.django_db

User = get_user_model()


class TestPainelExpoeCustoLlm:
    def test_painel_traz_as_3_chaves_novas_sem_registro_algum(self):
        resultado = services.painel(dias=30)

        assert resultado["custo_llm_hoje_usd"] == 0.0
        assert resultado["teto_llm_diario_usd"] == 5.0
        assert resultado["teto_llm_excedido_hoje"] is False

    def test_painel_reflete_o_gasto_acumulado_de_hoje(self):
        RegistroExecucaoIngestao.objects.create(custo_estimado_summarization_usd=1.25)
        RegistroExecucaoIngestao.objects.create(custo_estimado_summarization_usd=0.75)
        RegistroExecucaoIngestao.objects.create(custo_estimado_summarization_usd=None)

        resultado = services.painel(dias=30)

        assert resultado["custo_llm_hoje_usd"] == pytest.approx(2.0)
        assert resultado["teto_llm_excedido_hoje"] is False

    @override_settings(CATALOGO_NOTICIAS_LLM_TETO_GASTO_DIARIO_USD=2.0)
    def test_painel_sinaliza_teto_excedido_quando_gasto_atinge_o_teto_configurado(self):
        RegistroExecucaoIngestao.objects.create(custo_estimado_summarization_usd=2.0)

        resultado = services.painel(dias=30)

        assert resultado["custo_llm_hoje_usd"] == pytest.approx(2.0)
        assert resultado["teto_llm_diario_usd"] == 2.0
        assert resultado["teto_llm_excedido_hoje"] is True

    def test_painel_via_endpoint_http_para_admin_inclui_os_3_campos_novos(self):
        admin = User.objects.create_user(email="admin-custo-llm@example.com", password="senha123", papel="admin")
        client = APIClient()
        client.force_authenticate(user=admin)

        resposta = client.get("/api/metricas/painel/?dias=30")

        assert resposta.status_code == 200
        for campo in ("custo_llm_hoje_usd", "teto_llm_diario_usd", "teto_llm_excedido_hoje"):
            assert campo in resposta.data
        # campos existentes continuam presentes (aditivo, nao removeu nada)
        assert "usuarios_cadastrados_total" in resposta.data
