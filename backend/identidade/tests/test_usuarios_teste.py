"""
Conta de teste de DEV/HOMOLOG — o caminho `--sem-senha` do
`criar_usuario_carga` (run 20260925-1836-usuarios-teste-dev-homolog).

O que estes testes travam, e por quê:

- a senha da conta de teste NÃO EXISTE (critérios 1, 7 e 11): o primeiro acesso
  só é possível pela senha que a própria pessoa definiu;
- o redeploy é IDEMPOTENTE (critério 2): o gate roda a cada push, então um
  `set_unusable_password()` cego a cada deploy trancaria fora de novo quem já
  passou pela recuperação — o critério mais fácil de errar e o mais grave em
  termos de uso;
- `--sem-senha` + `--password` é recusado, nunca resolvido por precedência
  silenciosa (critério 3);
- o caminho COM senha continua byte a byte igual ao de antes (critério 4),
  porque é o que `subir-localhost.sh`, `subir-localhost.bat` e o dono de
  PROD dependem;
- o fluxo de primeiro acesso é o que o produto já tinha
  (recuperação → redefinição → login → troca), sem nenhuma peça nova.
"""

from __future__ import annotations

import io
import re

import pytest
from django.contrib.auth import get_user_model
from django.core import mail
from django.core.management import call_command
from django.core.management.base import CommandError
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

pytestmark = pytest.mark.django_db

User = get_user_model()

# Senhas usadas só dentro dos testes. `validate_password` roda em
# redefinição/troca, e o e-mail de recuperação NUNCA as carrega.
SENHA_RECUPERADA = "RecuperadaTeste123"
SENHA_TROCADA = "TrocadaTeste456"


def _carga(**kwargs) -> str:
    """Roda o comando devolvendo a saída (sem vazar para a saída do pytest)."""
    saida = io.StringIO()
    call_command("criar_usuario_carga", stdout=saida, **kwargs)
    return saida.getvalue()


def _sem_ansi(texto: str) -> str:
    """Tira as cores do `self.style` — o texto do log precisa ser conferível."""
    return re.sub(r"\x1b\[[0-9;]*m", "", texto)


def _login(email: str, senha: str):
    return APIClient().post("/api/auth/login/", {"email": email, "senha": senha}, format="json")


def _recuperar(email: str) -> tuple[str, str]:
    """Percorre `/recuperar-senha` e devolve (uid, token) lidos do E-MAIL.

    Lê o token do e-mail de propósito: é o mesmo caminho que a pessoa percorre,
    e não uma atalho de teste que poderia passar mesmo com o e-mail quebrado.
    """
    mail.outbox = []
    resposta = APIClient().post("/api/auth/recuperar-senha/", {"email": email}, format="json")
    assert resposta.status_code == 200, resposta.data
    assert len(mail.outbox) == 1
    assert mail.outbox[0].to == [email]

    corpo = mail.outbox[0].body
    uid = re.search(r"^uid: (\S+)$", corpo, flags=re.MULTILINE)
    token = re.search(r"^token: (\S+)$", corpo, flags=re.MULTILINE)
    assert uid and token, f"e-mail sem uid/token recuperáveis:\n{corpo}"
    return uid.group(1), token.group(1)


def _redefinir(email: str, nova_senha: str = SENHA_RECUPERADA):
    uid, token = _recuperar(email)
    return APIClient().post(
        "/api/auth/redefinir-senha/",
        {"uid": uid, "token": token, "nova_senha": nova_senha},
        format="json",
    )


# ---------------------------------------------------------------------------
# Critério 1 — a conta nasce sem senha utilizável e em estado de primeiro acesso
# ---------------------------------------------------------------------------


def test_comando_sem_senha_cria_conta_sem_senha_utilizavel_em_primeiro_acesso():
    saida = _carga(email="teste-free@dev.portal-noticias.com.br", sem_senha=True, papel="free")

    user = User.objects.get(email="teste-free@dev.portal-noticias.com.br")
    assert user.has_usable_password() is False
    assert user.deve_trocar_senha is True
    assert user.is_active is True
    assert user.email_verificado is True
    assert user.papel == "free"
    # `email_verificado=True` é o que dá acesso ao /admin e à Central, mas
    # `is_staff`/`is_superuser` SÓ vêm com `--superuser`: o gate passa a flag
    # apenas no perfil admin, para não existirem três contas de staff.
    assert user.is_staff is False
    assert user.is_superuser is False
    # Nenhuma senha em texto puro sobrou no banco.
    assert user.password.startswith("!")
    # Critério 11 (parte do log): a linha do comando tem que ser EXATAMENTE esta
    # — e-mail, papel, flag de superuser e o caminho de entrada. Se uma senha
    # aparecesse aqui, esta asserção quebraria.
    assert _sem_ansi(saida) == (
        "Usuário teste-free@dev.portal-noticias.com.br criado (papel=free, superuser=False)"
        " — sem senha utilizável; o primeiro acesso é por /recuperar-senha com este e-mail.\n"
    )


def test_sem_senha_com_papel_admin_e_superuser_so_no_admin():
    _carga(email="teste-admin@dev.portal-noticias.com.br", sem_senha=True, papel="admin", superuser=True)
    _carga(email="teste-premium@dev.portal-noticias.com.br", sem_senha=True, papel="premium")

    admin = User.objects.get(email="teste-admin@dev.portal-noticias.com.br")
    premium = User.objects.get(email="teste-premium@dev.portal-noticias.com.br")
    assert (admin.is_staff, admin.is_superuser) == (True, True)
    assert (premium.is_staff, premium.is_superuser) == (False, False)
    assert admin.papel == "admin" and premium.papel == "premium"
    assert admin.has_usable_password() is False
    assert premium.has_usable_password() is False


# ---------------------------------------------------------------------------
# Critério 2 — idempotência do redeploy
# ---------------------------------------------------------------------------


def test_redeploy_preserva_a_senha_que_a_pessoa_definiu_na_recuperacao(canal_entregando):
    """O gate roda a cada push: a 2ª execução não pode apagar o acesso de quem
    já passou pela recuperação, redefinition e troca de senha."""
    email = "teste-admin@homolog.portal-noticias.com.br"
    _carga(email=email, sem_senha=True, papel="admin", superuser=True)
    assert User.objects.get(email=email).has_usable_password() is False

    assert _redefinir(email).status_code == 200
    login = _login(email, SENHA_RECUPERADA)
    assert login.status_code == 200
    cliente = APIClient()
    cliente.credentials(HTTP_AUTHORIZATION=f"Token {login.data['token']}")
    troca = cliente.post(
        "/api/auth/trocar-senha/",
        {"senha_atual": SENHA_RECUPERADA, "nova_senha": SENHA_TROCADA},
        format="json",
    )
    assert troca.status_code == 200, troca.data
    token_da_pessoa = User.objects.get(email=email)
    assert token_da_pessoa.check_password(SENHA_TROCADA) is True
    assert token_da_pessoa.deve_trocar_senha is False

    # --- 2º deploy -------------------------------------------------------
    saida = _carga(email=email, sem_senha=True, papel="admin", superuser=True)

    depois = User.objects.get(email=email)
    assert depois.has_usable_password() is True
    assert depois.check_password(SENHA_TROCADA) is True
    assert depois.check_password(SENHA_RECUPERADA) is False
    # A troca do primeiro acesso NÃO é reimposta: quem já terminou o fluxo não
    # pode ser obrigado a trocar a senha a cada push.
    assert depois.deve_trocar_senha is False
    # Campos administrativos continuam normalizados.
    assert depois.is_active is True
    assert depois.email_verificado is True
    assert depois.papel == "admin"
    assert depois.is_superuser is True
    # O login segue funcionando depois do deploy.
    assert _login(email, SENHA_TROCADA).status_code == 200
    assert "preservada" in saida


def test_redeploy_preserva_ate_o_token_de_quem_ja_estava_logado(canal_entregando):
    """Como a credencial continua valendo, derrubar o `Token` só deslogaria
    quem está usando o ambiente de teste — sem ganho de segurança nenhum."""
    email = "teste-free@dev.portal-noticias.com.br"
    _carga(email=email, sem_senha=True, papel="free")
    assert _redefinir(email).status_code == 200
    login = _login(email, SENHA_RECUPERADA)
    assert login.status_code == 200
    token = Token.objects.get(user__email=email)
    assert token.key == login.data["token"]

    _carga(email=email, sem_senha=True, papel="free")

    assert Token.objects.filter(user__email=email).exists() is True
    cliente = APIClient()
    cliente.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
    assert cliente.get("/api/preferencias-cookies/").status_code == 200


def test_redeploy_reaplica_sem_senha_na_conta_que_ainda_nao_tem_senha():
    """Idempotência no outro extremo: rodar duas vezes seguidas, sem ninguém
    ter acessado, continua deixando a conta sem senha utilizável."""
    email = "teste-premium@dev.portal-noticias.com.br"
    primeira = _carga(email=email, sem_senha=True, papel="premium")
    segunda = _carga(email=email, sem_senha=True, papel="premium")

    user = User.objects.get(email=email)
    assert user.has_usable_password() is False
    assert user.deve_trocar_senha is True
    assert "criado" in primeira
    assert "atualizado" in segunda
    assert User.objects.filter(email=email).count() == 1


def test_sem_senha_normaliza_campos_administrativos_sem_destruir_senha():
    user = User.objects.create_user(
        email="teste-admin@dev.portal-noticias.com.br", password="ExistenteDesdeAntes123"
    )
    user.papel = "free"
    user.is_active = False
    user.email_verificado = False
    user.save()

    _carga(email=user.email, sem_senha=True, papel="admin", superuser=True)

    user.refresh_from_db()
    assert user.papel == "admin"
    assert user.is_active is True
    assert user.email_verificado is True
    assert user.is_superuser is True
    # Senha que já existia continua valendo: o gate não tranca fora quem já
    # tinha acesso, mesmo se a conta nasceu por outro caminho (cadastro, etc.).
    assert user.has_usable_password() is True
    assert user.check_password("ExistenteDesdeAntes123") is True


# ---------------------------------------------------------------------------
# Critério 3 — ambiguidade recusada, nunca resolvida em silêncio
# ---------------------------------------------------------------------------


def test_sem_senha_com_password_falha_sem_criar_nada():
    saida = io.StringIO()
    with pytest.raises(CommandError) as erro:
        call_command(
            "criar_usuario_carga",
            email="ambiguo@example.com",
            sem_senha=True,
            password="QualquerSenha123",
            stdout=saida,
        )

    assert "mutuamente exclusivos" in str(erro.value)
    # Falha ANTES de qualquer escrita: nem conta, nem token, nem metade do
    # estado de primeiro acesso.
    assert not User.objects.filter(email="ambiguo@example.com").exists()
    assert Token.objects.count() == 0


def test_sem_senha_com_prod_seed_password_no_ambiente_avisa_e_nao_imprime_a_senha(monkeypatch):
    """`PROD_SEED_PASSWORD` no ambiente não é ambiguidade (quem chamou pediu
    `--sem-senha` explicitamente), mas também não pode virar senha nem ser
    silenciosamente engolida."""
    monkeypatch.setenv("PROD_SEED_PASSWORD", "SeedDoAmbiente123")

    saida = _carga(email="teste-free@dev.portal-noticias.com.br", sem_senha=True, papel="free")

    assert "IGNORADA" in saida
    assert "SeedDoAmbiente123" not in saida
    user = User.objects.get(email="teste-free@dev.portal-noticias.com.br")
    assert user.has_usable_password() is False
    assert user.deve_trocar_senha is True


# ---------------------------------------------------------------------------
# Critério 4 — regressão: sem a flag, o comportamento é o de sempre
# ---------------------------------------------------------------------------


def test_caminho_com_senha_inalterado_troca_a_senha_e_mata_o_token_anterior():
    user = User.objects.create_user(email="carga@example.com", password="SenhaAntiga123")
    token_antigo = Token.objects.create(user=user)
    user.deve_trocar_senha = False
    user.save()

    saida = _carga(email="carga@example.com", password="NovaCargaForte123", superuser=True, papel="admin")

    user.refresh_from_db()
    assert user.has_usable_password() is True
    assert user.check_password("NovaCargaForte123") is True
    assert user.check_password("SenhaAntiga123") is False
    assert user.deve_trocar_senha is True
    assert user.is_superuser is True
    assert user.papel == "admin"
    assert user.is_active is True
    assert user.email_verificado is True
    # Regressão do comentário "Tokens antigos não valem nada com a senha nova".
    assert Token.objects.filter(user=user).exists() is False
    assert Token.objects.filter(key=token_antigo.key).exists() is False
    # A mensagem do caminho legado é a mesma de antes.
    assert "troca de senha exigida no primeiro login" in saida
    assert "sem senha utilizável" not in saida


def test_caminho_com_senha_continua_lendo_prod_seed_password_do_ambiente(monkeypatch):
    """A refatoração do `default` de `--password` (para distinguir explícito de
    herdado do ambiente) não pode quebrar o uso documentado de
    `PROD_SEED_PASSWORD`."""
    monkeypatch.setenv("PROD_SEED_PASSWORD", "SeedAmbienteForte123")

    saida = _carga(email="dono@example.com", papel="admin")

    user = User.objects.get(email="dono@example.com")
    assert user.check_password("SeedAmbienteForte123") is True
    assert user.deve_trocar_senha is True
    assert user.has_usable_password() is True
    assert "sem senha utilizável" not in saida


def test_caminho_com_senha_rejeita_senha_fraca_e_nao_cria_conta():
    with pytest.raises(CommandError):
        call_command(
            "criar_usuario_carga",
            email="fraca@example.com",
            password="123",
            stdout=io.StringIO(),
        )
    assert not User.objects.filter(email="fraca@example.com").exists()


# ---------------------------------------------------------------------------
# Critério 7 — nenhuma senha, nenhuma entrada
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "senha",
    ["LocalAdmin123", "teste", "qualquer-coisa-123", "!", SENHA_RECUPERADA],
)
def test_login_com_qualquer_senha_na_conta_sem_senha_utilizavel_falha(senha):
    email = "teste-free@dev.portal-noticias.com.br"
    _carga(email=email, sem_senha=True, papel="free")

    resposta = _login(email, senha)

    assert resposta.status_code == 401
    assert resposta.data["detail"] == "E-mail ou senha inválidos."
    assert "token" not in resposta.data
    assert Token.objects.filter(user__email=email).exists() is False


# ---------------------------------------------------------------------------
# Critério 8 — fluxo completo: recuperação → login → troca → uso
# ---------------------------------------------------------------------------


def test_fluxo_completo_de_primeiro_acesso_da_conta_de_teste(canal_entregando):
    email = "teste-premium@homolog.portal-noticias.com.br"
    _carga(email=email, sem_senha=True, papel="premium")

    # 0. Antes de definir senha, o login é impossível.
    assert _login(email, "Qualquer123").status_code == 401

    # 1. POST /api/auth/recuperar-senha/ → e-mail com uid + token.
    uid, token = _recuperar(email)
    assert uid and token

    # 2. POST /api/auth/redefinir-senha/ → a pessoa define a senha dela.
    redefinir = APIClient().post(
        "/api/auth/redefinir-senha/",
        {"uid": uid, "token": token, "nova_senha": SENHA_RECUPERADA},
        format="json",
    )
    assert redefinir.status_code == 200, redefinir.data
    user = User.objects.get(email=email)
    assert user.has_usable_password() is True
    assert user.check_password(SENHA_RECUPERADA) is True
    # `RedefinirSenhaView` grava SÓ `password`: a troca do primeiro acesso
    # continua de pé, que é o que faz o login redirecionar para /trocar-senha.
    assert user.deve_trocar_senha is True

    # 3. Login → deve_trocar_senha: true.
    login = _login(email, SENHA_RECUPERADA)
    assert login.status_code == 200
    assert login.data["usuario"]["deve_trocar_senha"] is True

    # 4. POST /api/auth/trocar-senha/ → flag limpa e token novo.
    cliente = APIClient()
    cliente.credentials(HTTP_AUTHORIZATION=f"Token {login.data['token']}")
    troca = cliente.post(
        "/api/auth/trocar-senha/",
        {"senha_atual": SENHA_RECUPERADA, "nova_senha": SENHA_TROCADA},
        format="json",
    )
    assert troca.status_code == 200, troca.data
    assert troca.data["token"] != login.data["token"]
    assert Token.objects.filter(key=login.data["token"]).exists() is False

    user.refresh_from_db()
    assert user.deve_trocar_senha is False

    # 5. Login normal, e a senha intermediária morreu.
    final = _login(email, SENHA_TROCADA)
    assert final.status_code == 200
    assert final.data["usuario"]["deve_trocar_senha"] is False
    assert final.data["usuario"]["papel"] == "premium"
    assert _login(email, SENHA_RECUPERADA).status_code == 401
