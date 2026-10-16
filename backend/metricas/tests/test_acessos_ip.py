from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from metricas.models import AcessoIP, mascarar_ip

pytestmark = pytest.mark.django_db

User = get_user_model()


def test_mascarar_ip_ipv4_mantem_so_os_dois_primeiros_octetos():
    assert mascarar_ip("203.0.113.42") == "203.0.xxx.xxx"


def test_mascarar_ip_ipv6_mantem_so_os_dois_primeiros_grupos():
    assert mascarar_ip("2001:db8:85a3:0:0:8a2e:370:7334") == "2001:db8:xxxx:xxxx"


def test_mascarar_ip_entrada_invalida_ou_vazia_nao_mascara_nada():
    assert mascarar_ip("") == ""
    assert mascarar_ip("isso-nao-e-ip") == ""


def test_page_view_grava_acesso_ip_mascarado_e_nunca_o_ip_completo():
    client = APIClient()

    resposta = client.post(
        "/api/metricas/eventos/",
        {"tipo": "page_view", "path": "/"},
        format="json",
        REMOTE_ADDR="203.0.113.42",
    )

    assert resposta.status_code == 201
    acesso = AcessoIP.objects.get()
    assert acesso.ip_mascarado == "203.0.xxx.xxx"
    assert "113.42" not in acesso.ip_mascarado


def test_outros_tipos_de_evento_nao_geram_acesso_ip():
    client = APIClient()

    resposta = client.post(
        "/api/metricas/eventos/",
        {"tipo": "category_view", "categoria": "esportes"},
        format="json",
        REMOTE_ADDR="203.0.113.42",
    )

    assert resposta.status_code == 201
    assert AcessoIP.objects.count() == 0


def test_acessos_ip_recusa_usuario_nao_admin():
    usuario = User.objects.create_user(email="free-acessos-ip@example.com", password="senha123", papel="free")
    client = APIClient()
    client.force_authenticate(user=usuario)

    resposta = client.get("/api/metricas/acessos-ip/")

    assert resposta.status_code == 403


def test_acessos_ip_agrega_por_ip_mascarado_do_mais_para_o_menos_frequente():
    AcessoIP.objects.bulk_create(
        [AcessoIP(ip_mascarado="203.0.xxx.xxx")] * 3
        + [AcessoIP(ip_mascarado="198.51.xxx.xxx")] * 1
    )
    admin = User.objects.create_user(email="admin-acessos-ip@example.com", password="senha123", papel="admin")
    client = APIClient()
    client.force_authenticate(user=admin)

    resposta = client.get("/api/metricas/acessos-ip/")

    assert resposta.status_code == 200
    assert resposta.data["acessos_total"] == 4
    assert resposta.data["ips_distintos"] == 2
    itens = resposta.data["itens"]
    assert itens[0] == {"ip_mascarado": "203.0.xxx.xxx", "total": 3}
    assert itens[1] == {"ip_mascarado": "198.51.xxx.xxx", "total": 1}
