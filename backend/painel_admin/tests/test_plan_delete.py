from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from assinatura.models import Plan, Subscription
from painel_admin.models import AuditoriaAdmin

pytestmark = pytest.mark.django_db

User = get_user_model()


def _admin():
    return User.objects.create_user(email="admin-del-plan@example.com", password="senha123", papel="admin")


def _free():
    return User.objects.create_user(email="free-del-plan@example.com", password="senha123", papel="free")


def _plano(nome="Mensal"):
    return Plan.objects.create(nome=nome, preco="29.90", duracao_dias=30, ativo=True)


def test_admin_exclui_plano_sem_assinaturas_e_audita():
    admin = _admin()
    plano = _plano()
    client = APIClient()
    client.force_authenticate(user=admin)
    resposta = client.delete(f"/api/admin/planos/{plano.id}/")
    assert resposta.status_code == 204
    assert not Plan.objects.filter(pk=plano.pk).exists()
    assert AuditoriaAdmin.objects.filter(acao="plan_delete", alvo_id=plano.pk).exists()


def test_plano_com_assinatura_nao_pode_ser_excluido_409():
    admin = _admin()
    plano = _plano("Anual")
    usuario = _free()
    Subscription.objects.create(
        user=usuario, plan=plano, status=Subscription.STATUS_ATIVA,
        preco_cobrado="29.90", duracao_dias_no_momento=30,
    )
    client = APIClient()
    client.force_authenticate(user=admin)
    resposta = client.delete(f"/api/admin/planos/{plano.id}/")
    assert resposta.status_code == 409
    assert Plan.objects.filter(pk=plano.pk).exists()


def test_excluir_plano_anonimo_401_free_404_e_inexistente_404():
    plano = _plano("Trimestral")
    anon = APIClient()
    assert anon.delete(f"/api/admin/planos/{plano.id}/").status_code == 401
    free = _free()
    client = APIClient()
    client.force_authenticate(user=free)
    assert client.delete(f"/api/admin/planos/{plano.id}/").status_code == 404
    admin = _admin()
    client.force_authenticate(user=admin)
    assert client.delete("/api/admin/planos/999999/").status_code == 404
