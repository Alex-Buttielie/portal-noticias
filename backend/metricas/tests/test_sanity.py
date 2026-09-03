from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

pytestmark = pytest.mark.django_db

User = get_user_model()


def test_painel_recusa_usuario_nao_admin():
    usuario = User.objects.create_user(email="free-metricas@example.com", password="senha123", papel="free")
    client = APIClient()
    client.force_authenticate(user=usuario)

    resposta = client.get("/api/metricas/painel/")

    assert resposta.status_code == 403


def test_painel_funciona_para_admin_e_retorna_campos_esperados():
    admin = User.objects.create_user(email="admin-metricas@example.com", password="senha123", papel="admin")
    client = APIClient()
    client.force_authenticate(user=admin)

    resposta = client.get("/api/metricas/painel/?dias=30")

    assert resposta.status_code == 200
    for campo in (
        "usuarios_cadastrados_total",
        "assinaturas_ativas",
        "conversao_free_premium",
        "receita_recorrente_periodo",
        "churn_periodo",
        "organizacoes_b2b_ativas",
        "usuarios_ativos_diarios",
        "usuarios_ativos_mensais",
        "retencao_periodo",
        "receita_media_por_assinante",
        "taxa_renovacao_periodo",
    ):
        assert campo in resposta.data


# ---------------------------------------------------------------------------
# BRD §21 — métricas de negócio que o painel ainda não cobria (usuários
# ativos, retenção, taxa de renovação, receita média por assinante). Gap
# real encontrado na análise do BRD.
# ---------------------------------------------------------------------------


def test_usuarios_ativos_diarios_conta_so_login_recente():
    from datetime import timedelta

    from django.utils import timezone

    from metricas import services

    ativo_hoje = User.objects.create_user(email="ativo-hoje@example.com", password="senha123", papel="free")
    ativo_hoje.last_login = timezone.now()
    ativo_hoje.save(update_fields=["last_login"])

    inativo_ha_muito = User.objects.create_user(email="inativo@example.com", password="senha123", papel="free")
    inativo_ha_muito.last_login = timezone.now() - timedelta(days=10)
    inativo_ha_muito.save(update_fields=["last_login"])

    resultado = services.painel(dias=30)

    assert resultado["usuarios_ativos_diarios"] == 1
    assert resultado["usuarios_ativos_mensais"] == 2


def test_login_por_senha_atualiza_last_login():
    """Regressão do gap: o fluxo de login por token nunca gravava last_login."""
    User.objects.create_user(email="login-tracking@example.com", password="senha123", papel="free")
    client = APIClient()

    resposta = client.post(
        "/api/auth/login/", {"email": "login-tracking@example.com", "senha": "senha123"}, format="json"
    )

    assert resposta.status_code == 200
    usuario = User.objects.get(email="login-tracking@example.com")
    assert usuario.last_login is not None
