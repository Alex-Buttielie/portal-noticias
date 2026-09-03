"""
Teste mínimo de sanidade escrito pelo executor apenas para validar o próprio
código durante o desenvolvimento — a suíte de testes formal, cobrindo todos
os critérios de aceite do implementation-contract.md, é responsabilidade do
`tester` (próximo agente do pipeline).
"""

from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.core import mail
from rest_framework.test import APIClient

from identidade.tokens import make_email_verification_token, make_password_reset_token

User = get_user_model()

pytestmark = pytest.mark.django_db


def test_cadastro_cria_usuario_free_com_senha_hasheada():
    client = APIClient()
    resp = client.post(
        "/api/auth/cadastro/",
        {
            "email": "visitante@example.com",
            "nome": "Visitante Teste",
            "senha": "SenhaForte123",
            "aceite_termos": True,
        },
        format="json",
    )
    assert resp.status_code == 201, resp.data

    user = User.objects.get(email="visitante@example.com")
    assert user.papel == User.PAPEL_FREE
    assert user.email_verificado is False
    assert user.consentimento_aceito_em is not None
    # Senha não pode estar em texto plano no banco.
    assert user.password != "SenhaForte123"
    assert user.password.startswith("pbkdf2_")


def test_cadastro_sem_aceite_termos_e_rejeitado():
    client = APIClient()
    resp = client.post(
        "/api/auth/cadastro/",
        {"email": "semaceite@example.com", "senha": "SenhaForte123", "aceite_termos": False},
        format="json",
    )
    assert resp.status_code == 400
    assert not User.objects.filter(email="semaceite@example.com").exists()


def test_cadastro_envia_email_de_verificacao():
    mail.outbox = []
    client = APIClient()
    resp = client.post(
        "/api/auth/cadastro/",
        {"email": "recebeemail@example.com", "senha": "SenhaForte123", "aceite_termos": True},
        format="json",
    )
    assert resp.status_code == 201
    assert len(mail.outbox) == 1
    assert mail.outbox[0].to == ["recebeemail@example.com"]


def test_logout_invalida_token():
    from rest_framework.authtoken.models import Token

    user = User.objects.create_user(email="logout@example.com", password="SenhaForte123")
    token = Token.objects.create(user=user)

    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
    resp = client.post("/api/auth/logout/")
    assert resp.status_code == 200
    assert not Token.objects.filter(user=user).exists()


def test_login_com_senha_errada_retorna_mensagem_generica():
    User.objects.create_user(email="alguem@example.com", password="SenhaForte123")
    client = APIClient()
    resp = client.post(
        "/api/auth/login/",
        {"email": "alguem@example.com", "senha": "errada"},
        format="json",
    )
    assert resp.status_code == 401
    assert resp.data["detail"] == "E-mail ou senha inválidos."


def test_login_com_credenciais_corretas_retorna_token():
    User.objects.create_user(email="logincerto@example.com", password="SenhaForte123")
    client = APIClient()
    resp = client.post(
        "/api/auth/login/",
        {"email": "logincerto@example.com", "senha": "SenhaForte123"},
        format="json",
    )
    assert resp.status_code == 200
    assert resp.data["token"]


def test_onboarding_bloqueado_sem_email_verificado():
    user = User.objects.create_user(email="pendente@example.com", password="SenhaForte123")
    client = APIClient()
    client.force_authenticate(user=user)
    resp = client.get("/api/onboarding/")
    assert resp.status_code == 403


def test_onboarding_funciona_apos_verificacao_e_suporta_pular():
    user = User.objects.create_user(email="verificado@example.com", password="SenhaForte123")
    user.email_verificado = True
    user.save()

    client = APIClient()
    client.force_authenticate(user=user)

    resp = client.get("/api/onboarding/")
    assert resp.status_code == 200
    assert resp.data["onboarding_concluido"] is False

    resp = client.patch("/api/onboarding/", {"pular": True}, format="json")
    assert resp.status_code == 200
    user.refresh_from_db()
    assert user.onboarding_pulado is True
    assert user.onboarding_concluido is False


def test_verificar_email_com_token_valido():
    user = User.objects.create_user(email="naoverificado@example.com", password="SenhaForte123")
    token = make_email_verification_token(user)

    client = APIClient()
    resp = client.post("/api/auth/verificar-email/", {"token": token}, format="json")
    assert resp.status_code == 200

    user.refresh_from_db()
    assert user.email_verificado is True


def test_verificar_email_com_token_invalido():
    client = APIClient()
    resp = client.post("/api/auth/verificar-email/", {"token": "lixo"}, format="json")
    assert resp.status_code == 400


def test_fluxo_completo_recuperar_e_redefinir_senha_invalida_hash_antigo():
    user = User.objects.create_user(email="esqueceu@example.com", password="SenhaAntiga123")

    client = APIClient()
    resp = client.post("/api/auth/recuperar-senha/", {"email": "esqueceu@example.com"}, format="json")
    assert resp.status_code == 200

    uidb64, token = make_password_reset_token(user)
    resp = client.post(
        "/api/auth/redefinir-senha/",
        {"uid": uidb64, "token": token, "nova_senha": "SenhaNovaSegura456"},
        format="json",
    )
    assert resp.status_code == 200

    user.refresh_from_db()
    assert user.check_password("SenhaAntiga123") is False
    assert user.check_password("SenhaNovaSegura456") is True

    # O mesmo token não pode ser reaproveitado após a troca de senha —
    # PasswordResetTokenGenerator invalida automaticamente (critério 7).
    resp = client.post(
        "/api/auth/redefinir-senha/",
        {"uid": uidb64, "token": token, "nova_senha": "OutraSenha789"},
        format="json",
    )
    assert resp.status_code == 400


def test_recuperar_senha_com_email_inexistente_retorna_mensagem_generica_e_nao_envia_email():
    mail.outbox = []
    client = APIClient()
    resp = client.post("/api/auth/recuperar-senha/", {"email": "naoexiste@example.com"}, format="json")
    assert resp.status_code == 200
    assert len(mail.outbox) == 0


def test_google_login_cria_usuario_novo_free_com_email_verificado():
    from django.test import RequestFactory

    from allauth.socialaccount.models import EmailAddress, SocialAccount, SocialLogin
    from allauth.socialaccount.providers.google.views import GoogleOAuth2Adapter

    request = RequestFactory().post("/api/auth/google/")
    provider = GoogleOAuth2Adapter(request).get_provider()

    fake_sociallogin = SocialLogin(
        user=User(email="social@example.com", nome="Social Teste"),
        account=SocialAccount(provider="google", uid="12345"),
        email_addresses=[EmailAddress(email="social@example.com", verified=True, primary=True)],
        provider=provider,
    )

    with patch(
        "allauth.socialaccount.providers.google.provider.GoogleProvider.verify_token",
        return_value=fake_sociallogin,
    ):
        client = APIClient()
        resp = client.post(
            "/api/auth/google/",
            {"id_token": "token-fake-de-teste", "aceite_termos": True},
            format="json",
        )

    assert resp.status_code == 200, resp.data
    assert resp.data["criado_agora"] is True
    user = User.objects.get(email="social@example.com")
    assert user.papel == User.PAPEL_FREE
    assert user.email_verificado is True
    assert "token" in resp.data
