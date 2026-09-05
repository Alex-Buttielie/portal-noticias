import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from catalogo_noticias.models import ConfiguracaoRobo, FonteRobo

pytestmark = pytest.mark.django_db
User = get_user_model()


def _admin():
    return User.objects.create_user(email="admin-robos@example.com", password="senha123", papel="admin")


def _free():
    return User.objects.create_user(email="free-robos@example.com", password="senha123", papel="free")


class TestRobosFontes:
    def test_fontes_lista_requer_admin(self):
        free = _free()
        client = APIClient()
        client.force_authenticate(user=free)
        resposta = client.get("/api/admin/robos/fontes/")
        assert resposta.status_code == 403

    def test_fontes_lista_vazia_admin(self):
        admin = _admin()
        client = APIClient()
        client.force_authenticate(user=admin)
        resposta = client.get("/api/admin/robos/fontes/")
        assert resposta.status_code == 200
        assert resposta.data == []

    def test_fontes_criar_admin(self):
        admin = _admin()
        client = APIClient()
        client.force_authenticate(user=admin)
        dados = {"nome": "G1", "url": "https://g1.globo.com/rss/g1/", "ativo": True, "categoria_padrao": ""}
        resposta = client.post("/api/admin/robos/fontes/", dados, format="json")
        assert resposta.status_code == 201
        assert resposta.data["nome"] == "G1"
        assert FonteRobo.objects.filter(nome="G1").exists()

    def test_fontes_atualizar_admin(self):
        admin = _admin()
        fonte = FonteRobo.objects.create(nome="Test", url="https://example.com/rss", ativo=True)
        client = APIClient()
        client.force_authenticate(user=admin)
        resposta = client.patch(f"/api/admin/robos/fontes/{fonte.id}/", {"ativo": False}, format="json")
        assert resposta.status_code == 200
        fonte.refresh_from_db()
        assert fonte.ativo is False

    def test_fontes_remover_admin(self):
        admin = _admin()
        fonte = FonteRobo.objects.create(nome="Test", url="https://example.com/rss", ativo=True)
        fid = fonte.id
        client = APIClient()
        client.force_authenticate(user=admin)
        resposta = client.delete(f"/api/admin/robos/fontes/{fid}/")
        assert resposta.status_code == 204
        assert not FonteRobo.objects.filter(id=fid).exists()


class TestRobosConfig:
    def test_config_get_requer_admin(self):
        free = _free()
        client = APIClient()
        client.force_authenticate(user=free)
        resposta = client.get("/api/admin/robos/config/")
        assert resposta.status_code == 403

    def test_config_get_cria_default(self):
        admin = _admin()
        client = APIClient()
        client.force_authenticate(user=admin)
        resposta = client.get("/api/admin/robos/config/")
        assert resposta.status_code == 200
        assert resposta.data["intervalo_minutos"] == 15
        assert resposta.data["ativo"] is True
        assert ConfiguracaoRobo.objects.filter(pk=1).exists()

    def test_config_patch_admin(self):
        admin = _admin()
        cfg = ConfiguracaoRobo.objects.create(pk=1, intervalo_minutos=15, ativo=True)
        client = APIClient()
        client.force_authenticate(user=admin)
        resposta = client.patch("/api/admin/robos/config/", {"intervalo_minutos": 20, "ativo": False}, format="json")
        assert resposta.status_code == 200
        assert resposta.data["intervalo_minutos"] == 20
        assert resposta.data["ativo"] is False
        cfg.refresh_from_db()
        assert cfg.intervalo_minutos == 20


class TestRobosExecucoes:
    def test_execucoes_lista_requer_admin(self):
        free = _free()
        client = APIClient()
        client.force_authenticate(user=free)
        resposta = client.get("/api/admin/robos/execucoes/")
        assert resposta.status_code == 403

    def test_execucoes_lista_admin(self):
        admin = _admin()
        client = APIClient()
        client.force_authenticate(user=admin)
        resposta = client.get("/api/admin/robos/execucoes/")
        assert resposta.status_code == 200
        assert isinstance(resposta.data, list)
