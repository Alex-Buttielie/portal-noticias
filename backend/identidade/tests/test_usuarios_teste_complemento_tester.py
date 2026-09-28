"""
Complemento de verificação do tester (run 20260925-1836-usuarios-teste-dev-homolog).

`test_usuarios_teste.py` (executor) cobre bem o caminho feliz. Estes testes
pegam buracos que aquela suíte NÃO pega — cada um existe porque a leitura do
`handle()` mostrou um estado ou uma invocação sem asserção:

1. **`deve_trocar_senha` no ramo "preservou a senha".** A suíte do executor só
   verifica a flag no estado JÁ CONCLUÍDO (`deve_trocar_senha is False` depois
   do redeploy). Ela não verifica o estado INTERMEDIÁRIO — pessoa recuperou a
   senha mas ainda não logou — onde a flag tem que continuar `True`. Uma
   mutação que pusesse `deve_trocar_senha = False` no ramo que preserva a senha
   PASSA em `test_redeploy_preserva_a_senha_que_a_pessoa_definiu_na_recuperacao`
   (que já espera `False`) e em `test_redeploy_preserva_ate_o_token_de_quem_ja_
   estava_logado` (que nem olha a flag). Ou seja: hoje a suíte não trava a
   regra "o primeiro acesso continua pendente" — que é o que o critério 8
   promete do ponto de vista do produto. Aqui ela é travada nos DOIS estados.

2. **Redeploy repetido.** O gate roda a cada push, não uma vez. A suíte do
   executor prova 1 redeploy. Aqui são 3, com recuperação no meio, e o
   `deve_trocar_senha` que estava `True` na 2ª execução tem que continuar
   `True` na 3ª (a preservação não pode virar uma concessão implícita).

3. **`getpass` jamais no caminho `--sem-senha`.** É a razão de o gate poder ser
   automatizado: no deploy não há terminal, e um `getpass` ali travaria o job
   para sempre. Nenhum teste da suíte do executor afirma isso; eu conferi por
   leitura (`if not sem_senha:` em volta do prompt), mas leitura não é prova.

4. **Regressão do `default` de `--password` (critério 4).** A mudança de
   `default=os.environ.get("PROD_SEED_PASSWORD", "")` para `default=None` só é
   segura se o caminho legado continuar pedindo a senha no `getpass` quando não
   há argumento E não há variável de ambiente. A suíte do executor cobre
   "sem argumento + variável presente" (que nem é o caminho do
   `subir-localhost.sh`, que passa `--password`) e "com argumento". Nenhum
   teste cobre "sem argumento + sem variável", que é o caminho do
   `docker compose ... criar_usuario_carga --email X --superuser` documentado
   no docstring.
"""

from __future__ import annotations

import io

import pytest
from django.contrib.auth import get_user_model
from django.core import mail
from django.core.management import call_command
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

pytestmark = pytest.mark.django_db

User = get_user_model()

SENHA_RECUPERADA = "RecuperadaTeste123"
SENHA_TROCADA = "TrocadaTeste456"

ENDPOINT_RECUPERAR = "/api/auth/recuperar-senha/"
ENDPOINT_REDEFINIR = "/api/auth/redefinir-senha/"
ENDPOINT_TROCAR = "/api/auth/trocar-senha/"
ENDPOINT_LOGIN = "/api/auth/login/"


def _carga(**kwargs) -> str:
    saida = io.StringIO()
    call_command("criar_usuario_carga", stdout=saida, **kwargs)
    return saida.getvalue()


def _login(email: str, senha: str):
    return APIClient().post(ENDPOINT_LOGIN, {"email": email, "senha": senha}, format="json")


def _recuperar_e_redefinir(email: str, nova_senha: str = SENHA_RECUPERADA):
    """Percorre o endpoint REAL de recuperação e o de redefinição, lendo o
    token do e-mail (mesmo caminho da pessoa, nenhum atalho)."""
    import re

    mail.outbox = []
    resposta = APIClient().post(ENDPOINT_RECUPERAR, {"email": email}, format="json")
    assert resposta.status_code == 200, resposta.data
    assert len(mail.outbox) == 1
    corpo = mail.outbox[0].body
    uid = re.search(r"^uid: (\S+)$", corpo, flags=re.MULTILINE)
    token = re.search(r"^token: (\S+)$", corpo, flags=re.MULTILINE)
    assert uid and token, f"e-mail sem uid/token recuperáveis:\n{corpo}"
    redefinir = APIClient().post(
        ENDPOINT_REDEFINIR,
        {"uid": uid.group(1), "token": token.group(1), "nova_senha": nova_senha},
        format="json",
    )
    assert redefinir.status_code == 200, redefinir.data


# ---------------------------------------------------------------------------
# Critério 2 — a flag do primeiro acesso sobrevive ao redeploy, nos DOIS estados
# ---------------------------------------------------------------------------


def test_redeploy_apos_recuperar_mas_antes_do_login_mantem_a_troca_pendente(canal_entregando):
    """Estado intermediário que a suíte do executor não cobre: a pessoa passou
    pela recuperação/redefinição, mas ainda NÃO logou nem trocou a senha.

    Aqui não existe Token nenhum. O redeploy tem que preservar a senha que ela
    acabou de definir E deixar `deve_trocar_senha=True` de pé — se a flag
    caísse para `False`, o primeiro acesso inteiro (critério 8) seria pulado em
    silêncio e a pessoa entraria direto no portal, sem a troca que o login
    exige de todo mundo no primeiro acesso.
    """
    email = "teste-free@dev.portal-noticias.com.br"
    _carga(email=email, sem_senha=True, papel="free")
    _recuperar_e_redefinir(email)

    antes = User.objects.get(email=email)
    assert antes.has_usable_password() is True
    assert antes.deve_trocar_senha is True
    assert Token.objects.filter(user=antes).exists() is False

    saida = _carga(email=email, sem_senha=True, papel="free")

    depois = User.objects.get(email=email)
    assert depois.check_password(SENHA_RECUPERADA) is True
    assert depois.deve_trocar_senha is True, (
        "o redeploy limpou a troca de senha de quem ainda NÃO concluiu o "
        "primeiro acesso — o primeiro acesso inteiro seria pulado"
    )
    assert "preservada" in saida
    # E o primeiro acesso segue funcionando de verdade: login → troca.
    login = _login(email, SENHA_RECUPERADA)
    assert login.status_code == 200
    assert login.data["usuario"]["deve_trocar_senha"] is True


def test_redeploy_nao_reimpoe_a_troca_nem_apaga_a_senha_apos_o_primeiro_acesso(canal_entregando):
    """O outro estado: primeiro acesso CONCLUÍDO (login + troca). O redeploy
    tem de preservar senha nova E `deve_trocar_senha=False` — se reimpusesse
    `True`, a pessoa seria obrigada a trocar a senha a cada push."""
    email = "teste-admin@homolog.portal-noticias.com.br"
    _carga(email=email, sem_senha=True, papel="admin", superuser=True)
    _recuperar_e_redefinir(email)
    login = _login(email, SENHA_RECUPERADA)
    assert login.status_code == 200
    cliente = APIClient()
    cliente.credentials(HTTP_AUTHORIZATION=f"Token {login.data['token']}")
    troca = cliente.post(
        ENDPOINT_TROCAR,
        {"senha_atual": SENHA_RECUPERADA, "nova_senha": SENHA_TROCADA},
        format="json",
    )
    assert troca.status_code == 200, troca.data
    assert User.objects.get(email=email).deve_trocar_senha is False

    _carga(email=email, sem_senha=True, papel="admin", superuser=True)

    depois = User.objects.get(email=email)
    assert depois.deve_trocar_senha is False, (
        "o redeploy reimpôs a troca de senha de quem já concluiu o primeiro acesso"
    )
    assert depois.check_password(SENHA_TROCADA) is True
    assert _login(email, SENHA_TROCADA).data["usuario"]["deve_trocar_senha"] is False


def test_tres_redeploysseguidos_preservam_a_senha_e_nao_reimpoem_a_troca(canal_entregando):
    """O gate roda a cada push. A idempotência tem de valer para 2º, 3º, 4º
    deploy — não só para o primeiro."""
    email = "teste-premium@homolog.portal-noticias.com.br"
    _carga(email=email, sem_senha=True, papel="premium")  # 1º deploy: conta nova
    assert User.objects.get(email=email).has_usable_password() is False

    _recuperar_e_redefinir(email)  # pessoa entrou
    assert User.objects.get(email=email).deve_trocar_senha is True

    for numero in (2, 3, 4):
        _carga(email=email, sem_senha=True, papel="premium")
        user = User.objects.get(email=email)
        assert user.has_usable_password() is True, f"{numero}º deploy apagou a senha"
        assert user.check_password(SENHA_RECUPERADA) is True, f"{numero}º deploy trocou a senha"
        assert user.deve_trocar_senha is True, f"{numero}º deploy limpou a troca pendente"
        assert user.papel == "premium"
        assert user.email_verificado is True
        assert user.is_active is True

    # Nenhum desses 3 deploys inventou Token para conta que nunca logou.
    assert Token.objects.filter(user__email=email).exists() is False
    # E o acesso continua valendo.
    assert _login(email, SENHA_RECUPERADA).status_code == 200


# ---------------------------------------------------------------------------
# Critério 11 / D3 — o prompt de senha jamais pode rodar no gate
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("com_variavel_no_ambiente", [False, True])
def test_sem_senha_nunca_chama_getpass(monkeypatch, com_variavel_no_ambiente):
    """No deploy não há terminal: um `getpass` ali travaria o job para sempre.
    O caminho `--sem-senha` tem que passar por cima dele — e passar por cima
    mesmo com `PROD_SEED_PASSWORD` no ambiente, que é o caso em que o
    `password` resolvido não fica vazio e o `if not password:` é justamente
    o que dispararia o prompt."""
    import getpass as getpass_mod

    def explodir(*_args, **_kwargs):  # pragma: no cover - só roda se o gate travar
        raise AssertionError("getpass foi chamado no caminho --sem-senha (o job de deploy travaria)")

    monkeypatch.setattr(getpass_mod, "getpass", explodir)
    if com_variavel_no_ambiente:
        monkeypatch.setenv("PROD_SEED_PASSWORD", "SeedDoAmbiente123")

    _carga(email="teste-free@dev.portal-noticias.com.br", sem_senha=True, papel="free")

    user = User.objects.get(email="teste-free@dev.portal-noticias.com.br")
    assert user.has_usable_password() is False
    assert user.deve_trocar_senha is True


# ---------------------------------------------------------------------------
# Critério 4 — regressão do caminho legado, incluindo o prompt
# ---------------------------------------------------------------------------


def test_caminho_legado_sem_password_e_sem_variavel_ainda_pede_a_senha(monkeypatch):
    """`subir-localhost.sh` passa `--password`; o docstring do comando
    documenta o uso sem ele. A mudança do `default` de `--password` (de
    `PROD_SEED_PASSWORD` para `None`) não pode engolir esse prompt: sem
    argumento e sem variável, a senha tem de ser pedida interativamente como
    sempre foi."""
    import getpass as getpass_mod

    monkeypatch.delenv("PROD_SEED_PASSWORD", raising=False)
    pedidos = []

    def getpass_falso(prompt=""):
        pedidos.append(prompt)
        return "SenhaDigitada123"

    monkeypatch.setattr(getpass_mod, "getpass", getpass_falso)

    _carga(email="dono@example.com", papel="admin", superuser=True)

    assert pedidos, "o prompt de senha deixou de acontecer sem --password e sem PROD_SEED_PASSWORD"
    user = User.objects.get(email="dono@example.com")
    assert user.check_password("SenhaDigitada123") is True
    assert user.has_usable_password() is True
    assert user.deve_trocar_senha is True
    assert user.is_superuser is True


def test_caminho_legado_com_password_vazio_no_argumento_ainda_pede_a_senha(monkeypatch):
    """`--password ""` explícito é o mesmo "sem senha" e, antes da mudança,
    caía no prompt (`options["password"] or ""`). A distinção nova
    (`is not None`) não pode ter quebrado esse caso de borda."""
    import getpass as getpass_mod

    monkeypatch.delenv("PROD_SEED_PASSWORD", raising=False)
    pedidos = []

    def getpass_falso(prompt=""):
        pedidos.append(prompt)
        return "SenhaDigitada123"

    monkeypatch.setattr(getpass_mod, "getpass", getpass_falso)

    _carga(email="dono2@example.com", password="", papel="admin")

    assert pedidos, "--password vazio deixou de cair no prompt"
    assert User.objects.get(email="dono2@example.com").check_password("SenhaDigitada123") is True
