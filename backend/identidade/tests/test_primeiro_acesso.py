"""
Primeiro acesso com troca obrigatória de senha (conta de carga + cadastro).
"""

from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

pytestmark = pytest.mark.django_db

User = get_user_model()


def _cadastro(email="primeiro@example.com", senha="SenhaForte123"):
    client = APIClient()
    resposta = client.post(
        "/api/auth/cadastro/",
        {"email": email, "nome": "Primeiro", "senha": senha, "aceite_termos": True},
        format="json",
    )
    assert resposta.status_code == 201
    return resposta


def _login(email, senha):
    client = APIClient()
    resposta = client.post("/api/auth/login/", {"email": email, "senha": senha}, format="json")
    return resposta


def test_cadastro_marca_troca_obrigatoria_e_login_avisa():
    _cadastro()

    user = User.objects.get(email="primeiro@example.com")
    assert user.deve_trocar_senha is True

    resposta = _login("primeiro@example.com", "SenhaForte123")

    assert resposta.status_code == 200
    assert resposta.data["usuario"]["deve_trocar_senha"] is True


def test_trocar_senha_exige_atual_limpa_flag_e_troca_token():
    _cadastro(email="troca@example.com")
    token_antigo = _login("troca@example.com", "SenhaForte123").data["token"]

    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Token {token_antigo}")

    ruim = client.post(
        "/api/auth/trocar-senha/", {"senha_atual": "Errada123", "nova_senha": "NovaSenha456"}, format="json"
    )
    assert ruim.status_code == 400

    ok = client.post(
        "/api/auth/trocar-senha/", {"senha_atual": "SenhaForte123", "nova_senha": "NovaSenha456"}, format="json"
    )
    assert ok.status_code == 200
    assert ok.data["token"] != token_antigo

    user = User.objects.get(email="troca@example.com")
    assert user.deve_trocar_senha is False
    assert user.check_password("NovaSenha456") is True

    # Token antigo morreu; login com a nova senha não pede mais troca.
    assert Token.objects.filter(key=token_antigo).exists() is False
    assert _login("troca@example.com", "NovaSenha456").data["usuario"]["deve_trocar_senha"] is False


def test_trocar_senha_exige_autenticacao():
    resposta = APIClient().post(
        "/api/auth/trocar-senha/", {"senha_atual": "x", "nova_senha": "NovaSenha456"}, format="json"
    )

    assert resposta.status_code in (401, 403)


def test_comando_carga_cria_admin_com_troca_obrigatoria():
    call_command(
        "criar_usuario_carga",
        email="carga@example.com",
        password="CargaForte123",
        superuser=True,
        papel="admin",
    )

    user = User.objects.get(email="carga@example.com")
    assert user.is_superuser is True
    assert user.papel == "admin"
    assert user.deve_trocar_senha is True
    assert user.check_password("CargaForte123") is True

    resposta = _login("carga@example.com", "CargaForte123")
    assert resposta.status_code == 200
    assert resposta.data["usuario"]["deve_trocar_senha"] is True


def test_comando_carga_rejeita_senha_fraca():
    from django.core.management.base import CommandError

    with pytest.raises(CommandError):
        call_command("criar_usuario_carga", email="fraca@example.com", password="123")
