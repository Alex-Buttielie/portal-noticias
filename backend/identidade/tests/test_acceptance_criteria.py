"""
Suite formal do `tester` — cobre explicitamente cada um dos 11 critérios de
aceite de `implementation-contract.md`
(run-20260901-2135-cadastro-auth). Cada teste referencia o número do
critério ("AC-N") no nome e/ou docstring, para rastreabilidade.

Esta suíte é independente de `identidade/tests/test_sanity.py` (escrita pelo
executor apenas para autovalidação) — reaproveita o mesmo mecanismo de
execução (pytest-django, override `DJANGO_DB_ENGINE=sqlite3` por falta de
PostgreSQL no ambiente), mas adiciona casos de borda que a suíte de sanidade
não cobre (token expirado, usuário Google já existente, ausência de
mensagem 500 real via client Django, senha "unusable" de conta social,
gap de consentimento no fluxo Google).
"""

import time
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.core import mail
from django.test import RequestFactory, override_settings
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from identidade.tokens import (
    make_email_verification_token,
    make_password_reset_token,
    read_email_verification_token,
)

User = get_user_model()

pytestmark = pytest.mark.django_db


def _cadastro_payload(**overrides):
    payload = {
        "email": "novo.usuario@example.com",
        "nome": "Novo Usuario",
        "senha": "SenhaForte123",
        "aceite_termos": True,
    }
    payload.update(overrides)
    return payload


def _google_sociallogin(email="social.novo@example.com", uid="google-uid-001", nome="Social Novo"):
    """Constrói um SocialLogin "fake" do allauth para mockar verify_token."""
    from allauth.socialaccount.models import EmailAddress, SocialAccount, SocialLogin
    from allauth.socialaccount.providers.google.views import GoogleOAuth2Adapter

    request = RequestFactory().post("/api/auth/google/")
    provider = GoogleOAuth2Adapter(request).get_provider()
    return SocialLogin(
        user=User(email=email, nome=nome),
        account=SocialAccount(provider="google", uid=uid),
        email_addresses=[EmailAddress(email=email, verified=True, primary=True)],
        provider=provider,
    )


# ---------------------------------------------------------------------------
# AC-1: cadastro cria conta papel=free, email_verificado=False, mecanismo de
# e-mail/token existe.
# ---------------------------------------------------------------------------

class TestAC1CadastroEmailSenha:
    def test_cadastro_valido_cria_usuario_free_nao_verificado(self):
        client = APIClient()
        resp = client.post("/api/auth/cadastro/", _cadastro_payload(), format="json")

        assert resp.status_code == 201, resp.data
        user = User.objects.get(email="novo.usuario@example.com")
        assert user.papel == User.PAPEL_FREE
        assert user.email_verificado is False

    def test_cadastro_gera_email_com_token_de_verificacao_valido(self):
        mail.outbox = []
        client = APIClient()
        resp = client.post("/api/auth/cadastro/", _cadastro_payload(email="comtoken@example.com"), format="json")
        assert resp.status_code == 201

        # O mecanismo de token não é só "existe um e-mail" — o e-mail
        # enviado precisa conter um token que de fato decodifica para o
        # usuário criado (não um valor decorativo).
        assert len(mail.outbox) == 1
        body = mail.outbox[0].body
        assert "token:" in body
        token = body.split("token:")[1].strip().splitlines()[0]
        resultado = read_email_verification_token(token)
        assert resultado is not None
        user_pk, email = resultado
        user = User.objects.get(email="comtoken@example.com")
        assert str(user.pk) == user_pk
        assert email == "comtoken@example.com"

    def test_cadastro_com_email_ja_cadastrado_e_rejeitado(self):
        User.objects.create_user(email="duplicado@example.com", password="SenhaForte123")
        client = APIClient()
        resp = client.post(
            "/api/auth/cadastro/", _cadastro_payload(email="duplicado@example.com"), format="json"
        )
        assert resp.status_code == 400
        assert User.objects.filter(email="duplicado@example.com").count() == 1


# ---------------------------------------------------------------------------
# AC-2: token de verificação válido -> email_verificado=True (+ borda: token
# expirado / inválido não deve marcar como verificado).
# ---------------------------------------------------------------------------

class TestAC2VerificacaoEmail:
    def test_token_valido_marca_email_verificado(self):
        user = User.objects.create_user(email="verificar@example.com", password="SenhaForte123")
        token = make_email_verification_token(user)

        client = APIClient()
        resp = client.post("/api/auth/verificar-email/", {"token": token}, format="json")
        assert resp.status_code == 200

        user.refresh_from_db()
        assert user.email_verificado is True

    def test_token_invalido_nao_marca_email_verificado(self):
        user = User.objects.create_user(email="tokeninvalido@example.com", password="SenhaForte123")
        client = APIClient()
        resp = client.post("/api/auth/verificar-email/", {"token": "token-adulterado"}, format="json")
        assert resp.status_code == 400

        user.refresh_from_db()
        assert user.email_verificado is False

    @override_settings(EMAIL_VERIFICATION_TOKEN_MAX_AGE_SECONDS=0)
    def test_token_expirado_e_rejeitado(self):
        user = User.objects.create_user(email="expirado@example.com", password="SenhaForte123")
        token = make_email_verification_token(user)
        time.sleep(1.1)  # garante que o token, com max_age=0s, já expirou

        client = APIClient()
        resp = client.post("/api/auth/verificar-email/", {"token": token}, format="json")
        assert resp.status_code == 400

        user.refresh_from_db()
        assert user.email_verificado is False


# ---------------------------------------------------------------------------
# AC-3: usuário com e-mail não verificado tem acesso negado (não 500) a
# funcionalidade que exige identidade confirmada. No escopo implementado, o
# único endpoint protegido dessa forma é /api/onboarding/ (interpretação do
# executor documentada em implementation-history.md — questão de escopo para
# o reviewer, não bloqueante para o tester).
# ---------------------------------------------------------------------------

class TestAC3BloqueioSemEmailVerificado:
    def test_get_onboarding_sem_email_verificado_retorna_403_com_mensagem_clara(self):
        user = User.objects.create_user(email="pendente.ac3@example.com", password="SenhaForte123")
        client = APIClient()
        client.force_authenticate(user=user)

        resp = client.get("/api/onboarding/")
        assert resp.status_code == 403
        # Não pode ser um 500 genérico nem corpo vazio — precisa haver uma
        # mensagem inteligível para o cliente da API.
        assert resp.status_code != 500
        assert "detail" in resp.data or "message" in str(resp.data).lower() or resp.data

    def test_patch_onboarding_sem_email_verificado_tambem_e_bloqueado(self):
        user = User.objects.create_user(email="pendente.patch@example.com", password="SenhaForte123")
        client = APIClient()
        client.force_authenticate(user=user)

        resp = client.patch("/api/onboarding/", {"localidade": "SP"}, format="json")
        assert resp.status_code == 403

    def test_usuario_verificado_acessa_onboarding_normalmente(self):
        user = User.objects.create_user(email="verificado.ac3@example.com", password="SenhaForte123")
        user.email_verificado = True
        user.save()
        client = APIClient()
        client.force_authenticate(user=user)

        resp = client.get("/api/onboarding/")
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# AC-4: fluxo OAuth do Google (mockado) cria ou associa um User; papel=free
# se for novo.
# ---------------------------------------------------------------------------

class TestAC4LoginSocialGoogle:
    def test_google_login_usuario_novo_cria_com_papel_free(self):
        fake_sociallogin = _google_sociallogin(email="novo.social@example.com", uid="uid-novo")

        with patch(
            "allauth.socialaccount.providers.google.provider.GoogleProvider.verify_token",
            return_value=fake_sociallogin,
        ):
            client = APIClient()
            resp = client.post(
                "/api/auth/google/", {"id_token": "fake", "aceite_termos": True}, format="json"
            )

        assert resp.status_code == 200, resp.data
        assert resp.data["criado_agora"] is True
        user = User.objects.get(email="novo.social@example.com")
        assert user.papel == User.PAPEL_FREE
        assert "token" in resp.data

    def test_google_login_usuario_existente_associa_sem_duplicar(self):
        from allauth.socialaccount.models import SocialAccount

        user = User.objects.create_user(email="ja.existe@example.com", password=None)
        user.papel = User.PAPEL_PREMIUM  # marca deliberadamente diferente de "free"
        user.email_verificado = True
        user.save()
        SocialAccount.objects.create(user=user, provider="google", uid="uid-existente")

        fake_sociallogin = _google_sociallogin(email="ja.existe@example.com", uid="uid-existente")
        with patch(
            "allauth.socialaccount.providers.google.provider.GoogleProvider.verify_token",
            return_value=fake_sociallogin,
        ):
            client = APIClient()
            resp = client.post("/api/auth/google/", {"id_token": "fake"}, format="json")

        assert resp.status_code == 200, resp.data
        assert resp.data["criado_agora"] is False
        assert User.objects.filter(email="ja.existe@example.com").count() == 1
        user.refresh_from_db()
        # Usuário pré-existente não deve ter seu papel sobrescrito por login social.
        assert user.papel == User.PAPEL_PREMIUM

    def test_google_login_com_token_invalido_nao_cria_usuario(self):
        with patch(
            "allauth.socialaccount.providers.google.provider.GoogleProvider.verify_token",
            side_effect=Exception("token inválido"),
        ):
            client = APIClient()
            resp = client.post("/api/auth/google/", {"id_token": "lixo"}, format="json")

        assert resp.status_code == 400
        assert resp.status_code != 500
        # Nenhum usuário/conta social foi criado por causa de um token inválido.
        from allauth.socialaccount.models import SocialAccount
        assert not SocialAccount.objects.filter(uid="uid-invalido").exists()
        assert not User.objects.filter(email="novo.social.invalido@example.com").exists()

    def test_google_login_com_email_ja_cadastrado_por_senha_associa_sem_crashar(self):
        """
        Regressão para code-review-contract.md Finding 1 (blocker):
        usuário que já se cadastrou por e-mail/senha (`POST
        /api/auth/cadastro/`) tenta "Entrar com Google" pela primeira vez
        usando o mesmo e-mail. Antes da correção, `sociallogin.lookup()` não
        encontrava nenhum `SocialAccount` nem (por `_lookup_by_email` estar
        desabilitado neste projeto) o `User` existente, então o código
        tratava como "usuário novo" e tentava criar um segundo `User` com o
        mesmo e-mail — violando a constraint `unique=True` e estourando
        `IntegrityError` (HTTP 500 não tratado).

        Depois da correção, a view deve reconhecer o `User` existente pelo
        e-mail e apenas associar o `SocialAccount` a ele — nunca duplicar,
        nunca 500.
        """
        from allauth.socialaccount.models import SocialAccount

        senha_original = "SenhaForte123"
        user = User.objects.create_user(email="alice.dupla@example.com", password=senha_original)
        user.email_verificado = True
        user.papel = User.PAPEL_PREMIUM  # marca deliberadamente diferente de "free"
        user.save()
        assert not SocialAccount.objects.filter(user=user).exists()

        fake_sociallogin = _google_sociallogin(email="alice.dupla@example.com", uid="uid-alice-google")
        with patch(
            "allauth.socialaccount.providers.google.provider.GoogleProvider.verify_token",
            return_value=fake_sociallogin,
        ):
            client = APIClient()
            resp = client.post("/api/auth/google/", {"id_token": "fake"}, format="json")

        assert resp.status_code == 200, resp.data
        assert resp.status_code != 500
        assert resp.data["criado_agora"] is False

        # Nenhum User duplicado foi criado — continua existindo exatamente 1
        # com este e-mail.
        assert User.objects.filter(email__iexact="alice.dupla@example.com").count() == 1
        user.refresh_from_db()
        # Papel e senha por e-mail/senha pré-existentes não são sobrescritos
        # pela associação da conta Google.
        assert user.papel == User.PAPEL_PREMIUM
        assert user.check_password(senha_original)
        # A conta Google agora está associada a este mesmo usuário.
        assert SocialAccount.objects.filter(user=user, provider="google", uid="uid-alice-google").exists()

        # A associação funciona de fato como login: retorna um token válido
        # para o usuário existente.
        token = Token.objects.get(user=user)
        assert resp.data["token"] == token.key

    def test_google_login_sem_aceite_termos_e_rejeitado_para_usuario_novo(self):
        """
        Regressão para code-review-contract.md Finding 2 (blocker):
        cadastro via Google (usuário verdadeiramente novo, sem User nem
        SocialAccount pré-existentes) sem `aceite_termos=true` no payload
        deve ser rejeitado — não pode criar a conta sem consentimento LGPD
        auditável (critério de aceite 11).
        """
        fake_sociallogin = _google_sociallogin(
            email="semaceite.social@example.com", uid="uid-semaceite-social"
        )
        with patch(
            "allauth.socialaccount.providers.google.provider.GoogleProvider.verify_token",
            return_value=fake_sociallogin,
        ):
            client = APIClient()
            resp = client.post("/api/auth/google/", {"id_token": "fake"}, format="json")

        assert resp.status_code == 400
        assert resp.status_code != 500
        assert not User.objects.filter(email="semaceite.social@example.com").exists()
        from allauth.socialaccount.models import SocialAccount

        assert not SocialAccount.objects.filter(uid="uid-semaceite-social").exists()


# ---------------------------------------------------------------------------
# AC-5: login correto retorna token válido; login errado retorna erro sem
# revelar se o e-mail existe (mitigação de user enumeration).
# ---------------------------------------------------------------------------

class TestAC5Login:
    def test_login_credenciais_corretas_retorna_token_valido(self):
        User.objects.create_user(email="loginok@example.com", password="SenhaForte123")
        client = APIClient()
        resp = client.post(
            "/api/auth/login/", {"email": "loginok@example.com", "senha": "SenhaForte123"}, format="json"
        )
        assert resp.status_code == 200
        assert resp.data["token"]
        assert Token.objects.filter(key=resp.data["token"]).exists()

    def test_login_email_existente_senha_errada_mensagem_generica(self):
        User.objects.create_user(email="existeesenhaerra@example.com", password="SenhaForte123")
        client = APIClient()
        resp = client.post(
            "/api/auth/login/", {"email": "existeesenhaerra@example.com", "senha": "errada"}, format="json"
        )
        assert resp.status_code == 401
        mensagem_email_existente = resp.data["detail"]

        resp2 = client.post(
            "/api/auth/login/", {"email": "naoexisteemabsoluto@example.com", "senha": "qualquer"}, format="json"
        )
        assert resp2.status_code == 401
        mensagem_email_inexistente = resp2.data["detail"]

        # A mensagem precisa ser idêntica nos dois casos — se diferir, o
        # atacante consegue inferir se o e-mail está cadastrado.
        assert mensagem_email_existente == mensagem_email_inexistente

    def test_login_conta_inativa_nao_autentica(self):
        user = User.objects.create_user(email="inativo@example.com", password="SenhaForte123")
        user.is_active = False
        user.save()
        client = APIClient()
        resp = client.post(
            "/api/auth/login/", {"email": "inativo@example.com", "senha": "SenhaForte123"}, format="json"
        )
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# AC-6: logout invalida a sessão/token.
# ---------------------------------------------------------------------------

class TestAC6Logout:
    def test_logout_invalida_token_e_impede_reuso(self):
        user = User.objects.create_user(email="logoutac6@example.com", password="SenhaForte123")
        token = Token.objects.create(user=user)

        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
        resp = client.post("/api/auth/logout/")
        assert resp.status_code == 200
        assert not Token.objects.filter(key=token.key).exists()

        # O mesmo token não pode mais ser usado após o logout.
        client2 = APIClient()
        client2.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
        resp2 = client2.post("/api/auth/logout/")
        assert resp2.status_code == 401

    def test_logout_sem_autenticacao_e_rejeitado(self):
        client = APIClient()
        resp = client.post("/api/auth/logout/")
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# AC-7: recuperar-senha gera token; redefinir-senha com token válido altera
# a senha e o hash antigo deixa de autenticar.
# ---------------------------------------------------------------------------

class TestAC7RecuperacaoSenha:
    def test_fluxo_completo_recupera_e_redefine_senha(self):
        user = User.objects.create_user(email="recupera.ac7@example.com", password="SenhaAntiga123")
        senha_hash_antiga = user.password

        client = APIClient()
        resp = client.post("/api/auth/recuperar-senha/", {"email": "recupera.ac7@example.com"}, format="json")
        assert resp.status_code == 200

        uidb64, token = make_password_reset_token(user)
        resp = client.post(
            "/api/auth/redefinir-senha/",
            {"uid": uidb64, "token": token, "nova_senha": "SenhaNovaSegura456"},
            format="json",
        )
        assert resp.status_code == 200

        user.refresh_from_db()
        assert user.password != senha_hash_antiga
        assert user.check_password("SenhaAntiga123") is False
        assert user.check_password("SenhaNovaSegura456") is True

        # Login com a senha antiga deve falhar; com a nova, funcionar.
        resp_login_antiga = client.post(
            "/api/auth/login/",
            {"email": "recupera.ac7@example.com", "senha": "SenhaAntiga123"},
            format="json",
        )
        assert resp_login_antiga.status_code == 401

        resp_login_nova = client.post(
            "/api/auth/login/",
            {"email": "recupera.ac7@example.com", "senha": "SenhaNovaSegura456"},
            format="json",
        )
        assert resp_login_nova.status_code == 200

    def test_redefinir_senha_com_token_invalido_e_rejeitado(self):
        user = User.objects.create_user(email="tokenruim@example.com", password="SenhaAntiga123")
        client = APIClient()
        resp = client.post(
            "/api/auth/redefinir-senha/",
            {"uid": "uid-invalido", "token": "token-invalido", "nova_senha": "OutraSenha789"},
            format="json",
        )
        assert resp.status_code == 400
        user.refresh_from_db()
        assert user.check_password("SenhaAntiga123") is True

    def test_recuperar_senha_email_inexistente_nao_revela_e_nao_envia(self):
        mail.outbox = []
        client = APIClient()
        resp = client.post(
            "/api/auth/recuperar-senha/", {"email": "naoexiste.ac7@example.com"}, format="json"
        )
        # Mesma resposta HTTP de sucesso genérico, e-mail existindo ou não.
        assert resp.status_code == 200
        assert len(mail.outbox) == 0


# ---------------------------------------------------------------------------
# AC-8: GET /api/onboarding/ retorna estado atual (não preenchido, para
# usuário recém-cadastrado); PATCH salva interesses/localidade/canal.
# ---------------------------------------------------------------------------

class TestAC8Onboarding:
    def _usuario_verificado(self, email="onboarding.ac8@example.com"):
        user = User.objects.create_user(email=email, password="SenhaForte123")
        user.email_verificado = True
        user.save()
        return user

    def test_get_onboarding_usuario_recem_cadastrado_estado_nao_preenchido(self):
        user = self._usuario_verificado()
        client = APIClient()
        client.force_authenticate(user=user)

        resp = client.get("/api/onboarding/")
        assert resp.status_code == 200
        assert resp.data["interesses"] == []
        assert resp.data["localidade"] == ""
        assert resp.data["canal_preferido"] == ""
        assert resp.data["onboarding_concluido"] is False

    def test_patch_onboarding_salva_interesses_localidade_canal(self):
        user = self._usuario_verificado(email="patch.ac8@example.com")
        client = APIClient()
        client.force_authenticate(user=user)

        resp = client.patch(
            "/api/onboarding/",
            {"interesses": ["economia", "esportes"], "localidade": "São Paulo, SP", "canal_preferido": "email"},
            format="json",
        )
        assert resp.status_code == 200

        user.refresh_from_db()
        assert user.interesses == ["economia", "esportes"]
        assert user.localidade == "São Paulo, SP"
        assert user.canal_preferido == "email"
        assert user.onboarding_concluido is True


# ---------------------------------------------------------------------------
# AC-9: pular onboarding registra que foi pulado, mantém a informação de que
# deve ser reapresentado, e não bloqueia o uso da conta.
# ---------------------------------------------------------------------------

class TestAC9PularOnboarding:
    def test_pular_onboarding_registra_pulado_sem_marcar_concluido(self):
        user = User.objects.create_user(email="pular.ac9@example.com", password="SenhaForte123")
        user.email_verificado = True
        user.save()
        client = APIClient()
        client.force_authenticate(user=user)

        resp = client.patch("/api/onboarding/", {"pular": True}, format="json")
        assert resp.status_code == 200

        user.refresh_from_db()
        assert user.onboarding_pulado is True
        # "não perde a informação de que deve ser reapresentado depois":
        # o modelo expõe isso via onboarding_concluido=False (e a property
        # onboarding_pendente correspondente).
        assert user.onboarding_concluido is False
        assert user.onboarding_pendente is True

    def test_pular_onboarding_nao_bloqueia_uso_da_conta(self):
        user = User.objects.create_user(email="pularusaconta.ac9@example.com", password="SenhaForte123")
        user.email_verificado = True
        user.save()
        client = APIClient()
        client.force_authenticate(user=user)

        resp = client.patch("/api/onboarding/", {"pular": True}, format="json")
        assert resp.status_code == 200

        # Conta continua utilizável: login funciona e onboarding continua
        # acessível (não passa a retornar 403/423 por ter sido pulado).
        login_client = APIClient()
        resp_login = login_client.post(
            "/api/auth/login/",
            {"email": "pularusaconta.ac9@example.com", "senha": "SenhaForte123"},
            format="json",
        )
        assert resp_login.status_code == 200

        resp_get = client.get("/api/onboarding/")
        assert resp_get.status_code == 200


# ---------------------------------------------------------------------------
# AC-10: nenhuma senha é persistida em texto plano.
# ---------------------------------------------------------------------------

class TestAC10SenhaNuncaEmTextoPlano:
    def test_senha_do_cadastro_por_email_esta_hasheada_no_banco(self):
        client = APIClient()
        senha_plana = "SenhaForte123"
        resp = client.post(
            "/api/auth/cadastro/",
            _cadastro_payload(email="hash.ac10@example.com", senha=senha_plana),
            format="json",
        )
        assert resp.status_code == 201

        # Inspeciona o valor persistido diretamente via query crua ao banco
        # (não via `user.check_password`, que sempre re-hasheia) — evidência
        # de que o valor armazenado de fato não é a senha em claro.
        from django.db import connection

        with connection.cursor() as cursor:
            cursor.execute("SELECT password FROM identidade_user WHERE email = %s", ["hash.ac10@example.com"])
            (password_no_banco,) = cursor.fetchone()

        assert password_no_banco != senha_plana
        assert senha_plana not in password_no_banco
        assert password_no_banco.startswith("pbkdf2_")

    def test_usuario_criado_via_google_nao_tem_senha_utilizavel_nem_plana(self):
        fake_sociallogin = _google_sociallogin(email="semhash.ac10@example.com", uid="uid-semhash")
        with patch(
            "allauth.socialaccount.providers.google.provider.GoogleProvider.verify_token",
            return_value=fake_sociallogin,
        ):
            client = APIClient()
            resp = client.post(
                "/api/auth/google/", {"id_token": "fake", "aceite_termos": True}, format="json"
            )
        assert resp.status_code == 200

        user = User.objects.get(email="semhash.ac10@example.com")
        assert user.has_usable_password() is False
        assert user.password  # ainda é uma string "unusable" gerenciada pelo Django, não vazio/plaintext


# ---------------------------------------------------------------------------
# AC-11: aceite de consentimento LGPD no cadastro é persistido com timestamp
# e identificação do que foi aceito.
# ---------------------------------------------------------------------------

class TestAC11ConsentimentoLGPD:
    def test_cadastro_email_senha_persiste_consentimento_com_timestamp_e_versao(self):
        client = APIClient()
        resp = client.post(
            "/api/auth/cadastro/", _cadastro_payload(email="consentimento.ac11@example.com"), format="json"
        )
        assert resp.status_code == 201

        user = User.objects.get(email="consentimento.ac11@example.com")
        assert user.consentimento_aceito_em is not None
        assert user.consentimento_versao_termos  # identificação do que foi aceito (versão dos termos)

    def test_cadastro_sem_aceite_explicito_de_termos_e_rejeitado(self):
        client = APIClient()
        resp = client.post(
            "/api/auth/cadastro/",
            _cadastro_payload(email="semaceite.ac11@example.com", aceite_termos=False),
            format="json",
        )
        assert resp.status_code == 400
        assert not User.objects.filter(email="semaceite.ac11@example.com").exists()

    def test_cadastro_via_google_com_aceite_termos_persiste_consentimento(self):
        """
        AC-11 exige que "o aceite de consentimento LGPD no cadastro" seja
        persistido com timestamp e identificação do que foi aceito. O
        critério não restringe isso ao fluxo e-mail/senha — fala em
        "cadastro" de forma genérica, e o cadastro via Google (AC-4) também é
        uma forma de cadastro (usuário novo, `criado_agora=True`).

        Corrigido no remediator (code-review-contract.md Finding 2,
        run-20260901-2135-cadastro-auth): `POST /api/auth/google/` agora
        exige `aceite_termos=true` no payload para criar um usuário novo, e
        persiste `consentimento_aceito_em`/`consentimento_versao_termos`
        nesse momento — análogo ao cadastro por e-mail/senha. Este teste
        substitui `test_cadastro_via_google_TAMBEM_deveria_persistir_consentimento`
        (que documentava o gap antes da correção); ver também
        `TestAC4LoginSocialGoogle.test_google_login_sem_aceite_termos_e_rejeitado_para_usuario_novo`
        para o caso de rejeição sem aceite.
        """
        fake_sociallogin = _google_sociallogin(email="consentimento.google.ac11@example.com", uid="uid-consent")
        with patch(
            "allauth.socialaccount.providers.google.provider.GoogleProvider.verify_token",
            return_value=fake_sociallogin,
        ):
            client = APIClient()
            resp = client.post(
                "/api/auth/google/",
                {"id_token": "fake", "aceite_termos": True},
                format="json",
            )

        assert resp.status_code == 200, resp.data
        assert resp.data["criado_agora"] is True

        user = User.objects.get(email="consentimento.google.ac11@example.com")
        assert user.consentimento_aceito_em is not None
        assert user.consentimento_versao_termos  # identificação do que foi aceito (versão dos termos)
