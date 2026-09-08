from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from b2b import services
from b2b.models import CriterioMonitoramento

pytestmark = pytest.mark.django_db

User = get_user_model()


def _usuario(email):
    return User.objects.create_user(email=email, password="senha123", papel="free")


def _org_com_membro(nome="Empresa Del", admin_email="admin-del-org@example.com"):
    admin = _usuario(admin_email)
    organizacao = services.criar_organizacao_com_admin(nome, admin)
    return organizacao, admin


def test_membro_exclui_criterio_da_propria_org():
    organizacao, admin = _org_com_membro()
    criterio = services.criar_criterio(organizacao, "palavra_chave", "django")
    client = APIClient()
    client.force_authenticate(user=admin)
    resposta = client.delete(f"/api/b2b/criterios/{criterio.id}/")
    assert resposta.status_code == 204
    assert not CriterioMonitoramento.objects.filter(pk=criterio.pk).exists()


def test_membro_nao_exclui_criterio_de_outra_org():
    org_a, admin_a = _org_com_membro("Org A", "a-del@example.com")
    org_b, admin_b = _org_com_membro("Org B", "b-del@example.com")
    criterio_b = services.criar_criterio(org_b, "setor", "tech")
    client = APIClient()
    client.force_authenticate(user=admin_a)
    resposta = client.delete(f"/api/b2b/criterios/{criterio_b.id}/")
    assert resposta.status_code == 404
    assert CriterioMonitoramento.objects.filter(pk=criterio_b.pk).exists()


def test_sem_org_403_anonimo_401_e_inexistente_404():
    sem_org = _usuario("sem-org@example.com")
    client = APIClient()
    client.force_authenticate(user=sem_org)
    assert client.delete("/api/b2b/criterios/1/").status_code == 403
    anon = APIClient()
    assert anon.delete("/api/b2b/criterios/1/").status_code == 401
    _, admin = _org_com_membro("Org C", "c-del@example.com")
    client.force_authenticate(user=admin)
    assert client.delete("/api/b2b/criterios/999999/").status_code == 404
