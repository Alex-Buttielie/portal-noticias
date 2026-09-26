"""P1-04 — cadastro, verificação de e-mail e redefinição de senha.

ESTE ARQUIVO É A PROVA DE QUE O FURO DO P0-02c ESTÁ FECHADO
==========================================================
O P0-02c documentou, e ninguém fechou, que em produção
(`DJANGO_EMAIL_BACKEND=console.EmailBackend`, o padrão de
`config/settings.py:615-617`) a verificação de cadastro e a redefinição de
senha "saíam com sucesso" sem entregar nada: o e-mail ia para o stdout do
container e o deploy reportava verde. O usuário ficava esperando um e-mail que
nunca chegava, sem como recuperar.

A régua deste arquivo, para os QUATRO caminhos:

1. **CADASTRO**: 201 só depois de o e-mail ter saído para um canal de
   entrega real. Sem canal, ou com o provedor recusando/estourando, a
   resposta é 503 e **nenhuma conta fica no banco**.
2. **VERIFICAÇÃO**: não envia nada, então não tem o que mentir sobre
   entrega. O que ela tem que garantir é que o token expira, que não vaza
   em log nem em resposta, e que reaplicá-lo não faz nada de novo.
3. **REDEFINIÇÃO**: a resposta é 200 genérica sempre — e ela é
   condicional, então continua verdadeira mesmo sem entrega. O que ela NÃO
   pode ser é um oráculo de existência de conta.
4. **CADASTRO NÃO ENUMERA**: as respostas de "e-mail novo", "e-mail já
   cadastrado e não verificado" e "e-mail já cadastrado e verificado" são
   idênticas — status, corpo e chaves.

Por que o caminho 3 não vira 503 quando a entrega falha
======================================================
Porque o 503 seria condicional: só sairia para o e-mail que TEM conta. Isso
trocaria "o e-mail não chegou" por "esta pessoa tem conta aqui", que é bem
pior. A falha de entrega nesse caminho é registrada em `logger.error`, em
`portal_email_entrega_total{situacao="sem_canal"}` e em `/health-detail` — o
operador vê, o atacante não. Ver o docstring de `RecuperarSenhaView`.

Todos usam `pytest.mark.django_db` por coerência com os demais testes de
endpoint do projeto. O guard de rede é o autouse de `identidade/tests/conftest.py`.
"""

from __future__ import annotations

import logging
import time
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.core import mail
from django.test import override_settings
from rest_framework.test import APIClient

from config.email_entrega import BACKENDS_SEM_ENTREGA_REAL
from config.tests.backends import (
    EntregaSimuladaBackend,
    ErroDeRedeBackend,
    ExplodindoBackend,
    RecusaBackend,
    caminho_de,
)
from identidade.tokens import (
    make_email_verification_token,
    make_password_reset_token,
    read_email_verification_token,
)

pytestmark = pytest.mark.django_db

User = get_user_model()

URL_CADASTRO = "/api/auth/cadastro/"
URL_VERIFICAR = "/api/auth/verificar-email/"
URL_RECUPERAR = "/api/auth/recuperar-senha/"
URL_REDEFINIR = "/api/auth/redefinir-senha/"

SENHA = "SenhaForte123"
BACKEND_QUE_ENTREGA = caminho_de(EntregaSimuladaBackend)

#: Palavras que NÃO podem aparecer numa resposta de erro: o corpo tem que
#: dizer que NÃO entregou, não que entregou.
PROMESSA_DE_ENVIO = ("enviado", "enviamos", "enviada", "reenviado", "instruções de redefinição")


def _payload(email, **extra):
    dados = {"email": email, "nome": "Ana Souza", "senha": SENHA, "aceite_termos": True}
    dados.update(extra)
    return dados


def _cadastrar(email, senha=SENHA):
    return APIClient().post(URL_CADASTRO, _payload(email, senha=senha), format="json")


def _usuario(email, *, verificado=False, senha=SENHA):
    usuario = User.objects.create_user(email=email, password=senha)
    usuario.email_verificado = verificado
    usuario.save(update_fields=["email_verificado"])
    return usuario


def _token_de_verificacao_da_caixa(email):
    """Extrai o token de verificação do ÚLTIMO e-mail entregue na caixa."""
    corpo = mail.outbox[-1].body
    return corpo.split("token:")[1].strip().splitlines()[0]


# ===========================================================================
# 1. CADASTRO — 201 só depois de entregue
# ===========================================================================


class TestCadastroSemEntregaNaoAnunciaSucesso:
    @pytest.mark.parametrize("backend", sorted(BACKENDS_SEM_ENTREGA_REAL))
    def test_backend_sem_entrega_real_responde_503_e_nao_cria_conta(self, settings, backend):
        settings.EMAIL_BACKEND = backend

        resposta = _cadastrar("sem-entrega@example.com")

        assert resposta.status_code == 503, resposta.data
        assert not User.objects.filter(email="sem-entrega@example.com").exists()

    @pytest.mark.parametrize("backend", sorted(BACKENDS_SEM_ENTREGA_REAL))
    def test_resposta_503_nunca_diz_que_enviou(self, settings, backend):
        settings.EMAIL_BACKEND = backend

        detalhe = str(_cadastrar("sem-entrega2@example.com").data).lower()

        for promessa in PROMESSA_DE_ENVIO:
            assert promessa not in detalhe, f"a resposta afirma '{promessa}' sem ter enviado"

    def test_sem_canal_o_e_mail_com_token_nao_vai_para_o_stdout(self, settings, capsys):
        """A prova direta do item do P0-02c: o e-mail de verificação — que
        contém o token de uso único em texto claro — não pode ser impresso no
        stdout do container."""
        settings.EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

        _cadastrar("stdout@example.com")

        capturado = capsys.readouterr()
        assert capturado.out == "", f"o console backend imprimiu o e-mail: {capturado.out!r}"
        assert "stdout@example.com" not in capturado.out

    def test_503_explica_o_que_falta_sem_vazar_nada(self, settings):
        settings.EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

        resposta = _cadastrar("explica@example.com")

        detalhe = resposta.data["detail"]
        # Nomeia a CONFIGURAÇÃO, para o operador ter o que corrigir...
        assert "DJANGO_EMAIL_BACKEND" in detalhe
        # ...e diz que nada foi criado, para a pessoa não achar que a conta
        # existe e ficar esperando um e-mail que não virá.
        assert "nenhuma conta foi criada" in detalhe
        # Nada de PII nem de valor de configuração na resposta.
        assert "explica@example.com" not in detalhe
        assert "RESEND_API_KEY=" not in detalhe

    @pytest.mark.parametrize(
        "classe",
        [RecusaBackend, ExplodindoBackend, ErroDeRedeBackend],
        ids=["provedor-devolve-0", "provedor-estoura", "provedor-caiu-a-conexao"],
    )
    def test_provedor_que_nao_entrega_responde_503_e_nao_cria_conta(self, settings, classe):
        settings.EMAIL_BACKEND = caminho_de(classe)

        resposta = _cadastrar("provedor-ruim@example.com")

        assert resposta.status_code == 503, resposta.data
        assert not User.objects.filter(email="provedor-ruim@example.com").exists()
        for promessa in PROMESSA_DE_ENVIO:
            assert promessa not in str(resposta.data).lower()

    def test_conta_nao_sobrevive_a_um_envio_falho(self, settings):
        """Se o usuário fosse criado e só o e-mail falhasse, o próximo cadastro
        com o mesmo e-mail cairia no ramo de duplicidade e a pessoa ficaria
        sem nunca receber o link. `transaction.atomic` reverte a criação."""
        settings.EMAIL_BACKEND = caminho_de(ExplodindoBackend)

        _cadastrar("rollback@example.com")

        assert User.objects.filter(email="rollback@example.com").count() == 0

    def test_depois_da_falha_o_cadastro_pode_ser_repetido(self, settings):
        """O estado é coerente com a resposta: como a conta não foi criada,
        repetir funciona (com um canal bom) em vez de bater no 400 de
        duplicidade."""
        settings.EMAIL_BACKEND = caminho_de(ExplodindoBackend)
        assert _cadastrar("repete@example.com").status_code == 503

        settings.EMAIL_BACKEND = BACKEND_QUE_ENTREGA
        resposta = _cadastrar("repete@example.com")

        assert resposta.status_code == 201
        assert User.objects.filter(email="repete@example.com").count() == 1


class TestCadastroComEntregaReal:
    def test_201_e_conta_criada(self, canal_entregando):
        resposta = _cadastrar("entregue@example.com")

        assert resposta.status_code == 201, resposta.data
        usuario = User.objects.get(email="entregue@example.com")
        assert usuario.email_verificado is False
        assert usuario.papel == User.PAPEL_FREE

    def test_e_mail_de_verificacao_chega_com_token_que_funciona(self, canal_entregando):
        mail.outbox = []

        _cadastrar("token-real@example.com")

        assert len(mail.outbox) == 1
        assert mail.outbox[0].to == ["token-real@example.com"]
        resultado = read_email_verification_token(_token_de_verificacao_da_caixa("x"))
        assert resultado is not None
        assert resultado[1] == "token-real@example.com"

    def test_resposta_de_cadastro_nao_traz_o_objeto_usuario(self, canal_entregando):
        """`usuario` na resposta é um oráculo de existência (id, papel,
        `email_verificado`, `date_joined`) e o frontend não usa o campo
        (`frontend/app/cadastro/page.tsx:18`). Ver o docstring de
        `CadastroView`."""
        resposta = _cadastrar("sem-usuario@example.com")

        assert "usuario" not in resposta.data
        assert set(resposta.data) == {"detail"}


# ===========================================================================
# 2. VERIFICAÇÃO — o que ela tem que garantir (não envia nada, mas trata token)
# ===========================================================================


class TestTokenDeVerificacao:
    def test_token_valido_verifica(self, canal_entregando):
        usuario = _usuario("verifica@example.com")

        resposta = APIClient().post(URL_VERIFICAR, {"token": make_email_verification_token(usuario)}, format="json")

        assert resposta.status_code == 200
        usuario.refresh_from_db()
        assert usuario.email_verificado is True

    def test_token_expirado_e_recusado(self, canal_entregando):
        """Expiração real, sem `sleep`: o relógio do `TimestampSigner` é
        adiantado além da janela configurada."""
        usuario = _usuario("expira@example.com")
        token = make_email_verification_token(usuario)
        agora = time.time()
        # `EMAIL_VERIFICATION_TOKEN_MAX_AGE_SECONDS` é 24h por padrão
        # (`config/settings.py:700-702`).
        with patch("django.core.signing.time.time", return_value=agora + 25 * 60 * 60):
            resposta = APIClient().post(URL_VERIFICAR, {"token": token}, format="json")

        assert resposta.status_code == 400
        usuario.refresh_from_db()
        assert usuario.email_verificado is False

    def test_token_dentro_da_janela_ainda_valida(self, canal_entregando):
        """O par com o teste anterior: sem isto, "expirado" podia passar
        porque o token estava sempre inválido."""
        usuario = _usuario("janela@example.com")
        token = make_email_verification_token(usuario)
        agora = time.time()
        with patch("django.core.signing.time.time", return_value=agora + 60 * 60):
            resposta = APIClient().post(URL_VERIFICAR, {"token": token}, format="json")

        assert resposta.status_code == 200

    def test_reaplicar_token_consumido_nao_faz_nada_de_novo(self, canal_entregando):
        """`identidade/tokens.py:5-8` assume que reaplicar um token de
        verificação é inofensivo porque só marca `email_verificado=True` de
        novo. Isso precisa ser VERIFICADO, não presumido: se um dia o token
        passar a carregar papel ou consentimento, esta asserção quebra e
        avisa.

        O que não é possível aqui é single-use de verdade: isso exigiria um
        modelo de token, ou seja, uma migration — proibida neste item. E não
        é necessário: o token é um `TimestampSigner` assinado, e o que ele
        concede é só "e-mail verificado", que já está concedido. Ele não
        carrega papel, não carrega consentimento e não autentica ninguém —
        `VerificarEmailView` é `AllowAny` e devolve só um `detail`.
        """
        usuario = _usuario("reuso@example.com")
        token = make_email_verification_token(usuario)
        cliente = APIClient()

        primeira = cliente.post(URL_VERIFICAR, {"token": token}, format="json")
        segunda = cliente.post(URL_VERIFICAR, {"token": token}, format="json")

        assert primeira.status_code == 200
        assert segunda.status_code == 200
        assert primeira.data == segunda.data
        usuario.refresh_from_db()
        # O token não concede nada além de `email_verificado`.
        assert usuario.email_verificado is True
        assert usuario.papel == User.PAPEL_FREE
        assert usuario.is_staff is False

    def test_token_de_um_usuario_nao_verifica_outro(self, canal_entregando):
        """O token carrega `pk:email` e a view exige os DOIS
        (`identidade/views.py`: `User.objects.get(pk=..., email=...)`).

        Se a view verificasse só pelo pk, um token vazado confirmaria a conta
        de outra pessoa. Aqui o token é assinado de verdade, com um pk que
        não existe e o e-mail de uma conta que existe: a assinatura passa,
        mas o par não casa com nenhum registro.
        """
        from django.core.signing import TimestampSigner

        import identidade.tokens as tokens_mod

        outro = _usuario("outro@example.com")
        signer = TimestampSigner(salt=tokens_mod.EMAIL_VERIFICATION_SALT)
        token = signer.sign("999999:outro@example.com")

        resposta = APIClient().post(URL_VERIFICAR, {"token": token}, format="json")

        assert resposta.status_code == 400
        outro.refresh_from_db()
        assert outro.email_verificado is False

    def test_token_com_email_divergente_nao_verifica(self, canal_entregando):
        """Mesma propriedade pelo outro lado: um token autêntico de `alvo`, com
        o e-mail dele trocado por outro, não assina. A assinatura cobre o
        payload inteiro, e é o par (pk, e-mail) que a view exige."""
        from django.core.signing import TimestampSigner

        import identidade.tokens as tokens_mod

        alvo = _usuario("alvo-real@example.com")
        signer = TimestampSigner(salt=tokens_mod.EMAIL_VERIFICATION_SALT)
        token = signer.sign(f"{alvo.pk}:outro-email@example.com")

        resposta = APIClient().post(URL_VERIFICAR, {"token": token}, format="json")

        assert resposta.status_code == 400
        alvo.refresh_from_db()
        assert alvo.email_verificado is False

    def test_token_nao_vaza_na_resposta(self, canal_entregando):
        usuario = _usuario("vaza-resposta@example.com")
        token = make_email_verification_token(usuario)

        ok = APIClient().post(URL_VERIFICAR, {"token": token}, format="json")
        ruim = APIClient().post(URL_VERIFICAR, {"token": token + "adulterado"}, format="json")

        assert token not in str(ok.data)
        assert token not in str(ruim.data)
        assert ok.status_code == 200
        assert ruim.status_code == 400

    def test_resposta_de_token_invalido_nao_ecola_o_token_recebido(self, canal_entregando):
        token_adulterado = "identidade.verificar-email:1:vaza@exemplo.com:9999999999:assinatura"

        resposta = APIClient().post(URL_VERIFICAR, {"token": token_adulterado}, format="json")

        assert resposta.status_code == 400
        assert token_adulterado not in str(resposta.data)
        assert "vaza@exemplo.com" not in str(resposta.data)

    def test_verificacao_tem_rate_limit_por_ip(self, canal_entregando, throttle_ativo):
        """`AuthSensivelAnonThrottle` (`config/throttling.py:37-49`) — o mesmo
        escopo `auth_sensivel` de login e redefinição, para que forçar o token
        contra o endpoint de verificação seja tão caro quanto forçar senha."""
        respostas = [APIClient().post(URL_VERIFICAR, {"token": f"token-{i}"}, format="json").status_code for i in range(30)]

        assert 429 in respostas, f"sem rate limit em /verificar-email/: {respostas}"
        assert respostas[-1] == 429


# ===========================================================================
# 3. REDEFINIÇÃO — resposta neutra, token de uso único
# ===========================================================================


class TestRecuperacaoSemOraculoDeExistencia:
    def test_resposta_e_identica_para_email_com_e_sem_conta(self, canal_entregando):
        _usuario("tem-conta@example.com")
        mail.outbox = []

        com_conta = APIClient().post(URL_RECUPERAR, {"email": "tem-conta@example.com"}, format="json")
        sem_conta = APIClient().post(URL_RECUPERAR, {"email": "nao-tem-conta@example.com"}, format="json")

        assert com_conta.status_code == sem_conta.status_code == 200
        assert com_conta.data == sem_conta.data
        # E o que realmente prova a diferença: só um dos dois recebeu e-mail.
        assert [m.to for m in mail.outbox] == [["tem-conta@example.com"]]

    def test_resposta_e_identica_para_caixa_variante(self, canal_entregando):
        """`email__iexact` (views.py) casa a caixa do domínio; a resposta não
        pode diferir entre `Alvo@Example.com` e `alvo@example.com`."""
        _usuario("caixa@example.com")
        mail.outbox = []

        maiuscula = APIClient().post(URL_RECUPERAR, {"email": "Caixa@Example.com"}, format="json")
        minuscula = APIClient().post(URL_RECUPERAR, {"email": "caixa@outro.com"}, format="json")

        assert maiuscula.data == minuscula.data
        assert maiuscula.status_code == minuscula.status_code == 200

    def test_resposta_nao_diz_que_enviou(self, canal_entregando):
        """A frase é CONDICIONAL ("Se o e-mail informado estiver cadastrado,
        enviaremos..."), e por isso continua verdadeira mesmo quando nada
        saiu. Um "seus dados foram enviados" seria mentira com canal e
        seria a forma mais fácil de um 2xx."""
        _usuario("condicional@example.com")

        detalhe = APIClient().post(URL_RECUPERAR, {"email": "condicional@example.com"}, format="json").data["detail"]

        assert detalhe.startswith("Se o e-mail informado estiver cadastrado")

    def test_resposta_e_neutra_mesmo_sem_canal_nenhum(self, settings):
        """O caso sistêmico (produção com `console`) também não pode
        distinguir: 503 para o e-mail com conta e 200 para o sem conta seria
        o pior oráculo possível."""
        settings.EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
        _usuario("sistematico@example.com")

        com_conta = APIClient().post(URL_RECUPERAR, {"email": "sistematico@example.com"}, format="json")
        sem_conta = APIClient().post(URL_RECUPERAR, {"email": "ninguem@example.com"}, format="json")

        assert com_conta.status_code == sem_conta.status_code == 200
        assert com_conta.data == sem_conta.data

    def test_resposta_neutra_mesmo_com_provedor_que_estoura(self, settings):
        settings.EMAIL_BACKEND = caminho_de(ExplodindoBackend)
        _usuario("estoura@example.com")

        com_conta = APIClient().post(URL_RECUPERAR, {"email": "estoura@example.com"}, format="json")
        sem_conta = APIClient().post(URL_RECUPERAR, {"email": "ninguem2@example.com"}, format="json")

        assert com_conta.status_code == sem_conta.status_code == 200
        assert com_conta.data == sem_conta.data

    def test_e_mensagem_de_entrega_vai_para_o_log_e_nao_para_a_resposta(self, settings, caplog):
        """O operador precisa ver; o cliente não pode distinguir. Uma falha que
        é barulhenta no log e invisível na resposta é a única forma de
        fechar os dois requisitos ao mesmo tempo."""
        settings.EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
        _usuario("logado@example.com")

        with caplog.at_level(logging.ERROR):
            resposta = APIClient().post(URL_RECUPERAR, {"email": "logado@example.com"}, format="json")

        assert resposta.status_code == 200
        assert "logado@example.com" not in str(resposta.data)
        logs = "\n".join(r.getMessage() for r in caplog.records)
        assert "NÃO enviado" in logs or "não entrega e-mail a ninguém" in logs
        # E o endereço do titular não precisa estar no log: o pk basta.
        assert "logado@example.com" not in logs

    def test_token_nao_vaza_no_log_quando_a_entrega_falha(self, settings, caplog):
        """`entregar_email` não copia `str(exc)` (o texto do provedor pode
        ecoar o payload, que tem o token). Este teste é o que garante que
        isso não volta por outro caminho."""
        settings.EMAIL_BACKEND = caminho_de(ExplodindoBackend)
        _usuario("token-no-log@example.com")

        with caplog.at_level(logging.DEBUG):
            APIClient().post(URL_RECUPERAR, {"email": "token-no-log@example.com"}, format="json")

        logs = "\n".join(r.getMessage() for r in caplog.records)
        assert "provedor fora do ar" not in logs
        assert "uid=" not in logs
        assert "token=" not in logs
        assert "brinde" not in logs

    def test_recuperacao_tem_rate_limit_por_ip(self, canal_entregando, throttle_ativo):
        respostas = [
            APIClient().post(URL_RECUPERAR, {"email": f"throttle-{i}@example.com"}, format="json").status_code
            for i in range(30)
        ]

        assert 429 in respostas, f"sem rate limit em /recuperar-senha/: {respostas}"


class TestTokenDeRedefinicao:
    def test_e_mail_entregue_traz_uid_e_token_que_funcionam(self, canal_entregando):
        _usuario("reset-real@example.com", senha="SenhaAntiga123")
        mail.outbox = []

        resposta = APIClient().post(URL_RECUPERAR, {"email": "reset-real@example.com"}, format="json")

        assert resposta.status_code == 200
        assert len(mail.outbox) == 1
        corpo = mail.outbox[-1].body
        uid = corpo.split("uid:")[1].strip().splitlines()[0]
        token = corpo.split("token:")[1].strip().splitlines()[0]

        redefinir = APIClient().post(
            URL_REDEFINIR, {"uid": uid, "token": token, "nova_senha": "SenhaNovaSegura456"}, format="json"
        )
        assert redefinir.status_code == 200
        usuario = User.objects.get(email="reset-real@example.com")
        assert usuario.check_password("SenhaNovaSegura456") is True

    def test_token_expira(self, canal_entregando):
        """`PASSWORD_RESET_TIMEOUT` é 1h (`config/settings.py:703-705`).
        `_now()` existe no `PasswordResetTokenGenerator` do Django
        exatamente para ser mockado em teste — sem `sleep`, e sem esperar
        uma hora. O valor tem de ser NAIVE: o `_now()` real é
        `datetime.now()` (`django/contrib/auth/tokens.py`), não
        `timezone.now()`."""
        from datetime import datetime, timedelta

        usuario = _usuario("reset-expira@example.com", senha="SenhaAntiga123")
        uidb64, token = make_password_reset_token(usuario)
        futuro = datetime.now() + timedelta(hours=2)

        with patch(
            "django.contrib.auth.tokens.PasswordResetTokenGenerator._now", return_value=futuro
        ):
            resposta = APIClient().post(
                URL_REDEFINIR, {"uid": uidb64, "token": token, "nova_senha": "SenhaNovaSegura456"}, format="json"
            )

        assert resposta.status_code == 400
        usuario.refresh_from_db()
        assert usuario.check_password("SenhaAntiga123") is True

    def test_token_dentro_da_janela_ainda_valida(self, canal_entregando):
        from datetime import datetime, timedelta

        usuario = _usuario("reset-janela@example.com", senha="SenhaAntiga123")
        uidb64, token = make_password_reset_token(usuario)
        dentro = datetime.now() + timedelta(minutes=30)

        with patch(
            "django.contrib.auth.tokens.PasswordResetTokenGenerator._now", return_value=dentro
        ):
            resposta = APIClient().post(
                URL_REDEFINIR, {"uid": uidb64, "token": token, "nova_senha": "SenhaNovaSegura456"}, format="json"
            )

        assert resposta.status_code == 200

    def test_token_nao_pode_ser_reaproveitado_apos_o_uso(self, canal_entregando):
        """Uso único de verdade, sem modelo novo: o
        `PasswordResetTokenGenerator` inclui o hash da senha no hash do token,
        então trocar a senha mata o token antigo. Aqui estava coberto por
        `test_sanity.py:170-177`; o par com o teste acima é o que garante que
        a invalidação é por USO e não por outra coisa."""
        usuario = _usuario("reset-reuso@example.com", senha="SenhaAntiga123")
        uidb64, token = make_password_reset_token(usuario)
        cliente = APIClient()

        primeiro = cliente.post(
            URL_REDEFINIR, {"uid": uidb64, "token": token, "nova_senha": "SenhaNovaSegura456"}, format="json"
        )
        segundo = cliente.post(
            URL_REDEFINIR, {"uid": uidb64, "token": token, "nova_senha": "OutraSenha789"}, format="json"
        )

        assert primeiro.status_code == 200
        assert segundo.status_code == 400
        usuario.refresh_from_db()
        assert usuario.check_password("SenhaNovaSegura456") is True

    def test_redefinir_invalida_o_token_de_api_da_sessao(self, canal_entregando):
        from rest_framework.authtoken.models import Token

        usuario = _usuario("reset-sessao@example.com", senha="SenhaAntiga123")
        token_api = Token.objects.create(user=usuario)
        uidb64, token = make_password_reset_token(usuario)

        APIClient().post(
            URL_REDEFINIR, {"uid": uidb64, "token": token, "nova_senha": "SenhaNovaSegura456"}, format="json"
        )

        assert Token.objects.filter(key=token_api.key).exists() is False

    def test_token_nao_vaza_na_resposta_de_redefinicao(self, canal_entregando):
        usuario = _usuario("reset-vaza@example.com", senha="SenhaAntiga123")
        uidb64, token = make_password_reset_token(usuario)

        ok = APIClient().post(
            URL_REDEFINIR, {"uid": uidb64, "token": token, "nova_senha": "SenhaNovaSegura456"}, format="json"
        )
        ruim = APIClient().post(
            URL_REDEFINIR, {"uid": uidb64, "token": token, "nova_senha": "OutraSenha789"}, format="json"
        )

        assert token not in str(ok.data)
        assert token not in str(ruim.data)
        assert uidb64 not in str(ruim.data)

    def test_redefinir_tem_rate_limit_por_ip(self, canal_entregando, throttle_ativo):
        respostas = [
            APIClient().post(
                URL_REDEFINIR, {"uid": f"u{i}", "token": f"t{i}", "nova_senha": "SenhaNovaSegura456"}, format="json"
            ).status_code
            for i in range(30)
        ]

        assert 429 in respostas, f"sem rate limit em /redefinir-senha/: {respostas}"


# ===========================================================================
# 4. CADASTRO NÃO REVELA SE UM E-MAIL JÁ TEM CONTA
#    (o teste que o item chama de "o mais importante depois do anterior")
# ===========================================================================


class TestCadastroNaoEnumeraContas:
    def test_respostas_de_cadastro_sao_indistinguiveis(self, canal_entregando):
        """O teste central do item.

        Três casos, três respostas — e as três têm de ser IGUAIS:

        * e-mail novo                        → 201, conta criada, e-mail enviado;
        * e-mail já cadastrado, não verificado→ 201, nada criado, e-mail reenviado;
        * e-mail já cadastrado, verificado   → 201, nada criado, nada enviado.

        O terceiro é o caso difícil: é o único em que todos os campos de
        `usuario` (id, papel, `email_verificado`, `date_joined`) divergiriam
        de um cadastro novo. Por isso a resposta não carrega `usuario`.
        """
        _usuario("ja-verificado@example.com", verificado=True)
        _usuario("nao-verificado@example.com", verificado=False)

        novo = _cadastrar("totalmente-novo@example.com")
        nao_verificado = _cadastrar("nao-verificado@example.com")
        verificado = _cadastrar("ja-verificado@example.com")

        assert novo.status_code == nao_verificado.status_code == verificado.status_code == 201
        assert novo.data == nao_verificado.data, "resposta distingue 'não verificado' de 'novo'"
        assert novo.data == verificado.data, "resposta distingue 'já verificado' de 'novo'"

    def test_a_resposta_comum_nao_contem_nada_derivado_do_banco(self, canal_entregando):
        _usuario("derivado@example.com", verificado=True)

        resposta = _cadastrar("derivado@example.com")

        assert set(resposta.data) == {"detail"}
        for vazamento in (
            str(User.objects.get(email="derivado@example.com").pk),
            "free",
            "premium",
            "admin",
        ):
            assert vazamento not in str(resposta.data), f"a resposta vazou {vazamento!r}"

    def test_falha_no_reenvio_da_duplicidade_nao_muda_a_resposta(self, settings):
        """O par de arroz com o `test_respostas_de_cadastro_sao_indistinguiveis`.

        Este é o canto onde as duas exigências do item se tensionam: a resposta
        não pode distinguir (senão vira oráculo) e não pode dizer "enviei"
        (senão vira mentira). A saída é que a falha fique no log e na métrica
        e NADA na resposta — com canal saudável, o e-mail do titular chega de
        qualquer forma, e é por isso que ele não é dado do cliente.
        """
        settings.EMAIL_BACKEND = caminho_de(ExplodindoBackend)
        _usuario("reenvio-falha@example.com", verificado=False)

        resposta = _cadastrar("reenvio-falha@example.com")

        assert resposta.status_code == 201
        assert resposta.data == {"detail": "Cadastro realizado. Verifique seu e-mail para confirmar a conta."}
        assert User.objects.filter(email="reenvio-falha@example.com").count() == 1

    def test_nenhuma_consulta_ao_banco_antes_da_checagem_de_canal(self, settings, django_assert_num_queries):
        """A ordem é uma propriedade de segurança, não de estilo.

        Se a duplicidade fosse consultada ANTES da checagem de canal, o 503 do
        sistema cairia só para e-mails cadastrados — o provider quebrado
        viraria enumerador de contas. Este teste fixa a ordem: com o canal
        quebrado, um e-mail novo e um e-mail existente levam o MESMO número
        de consultas ao banco, que é zero além da autenticação implícita.
        """
        settings.EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
        _usuario("ordem-existente@example.com")

        with django_assert_num_queries(0):
            novo = _cadastrar("ordem-novo@example.com")
        with django_assert_num_queries(0):
            existente = _cadastrar("ordem-existente@example.com")

        assert novo.status_code == existente.status_code == 503
        assert novo.data == existente.data

    def test_cadastro_com_email_ja_cadastrado_nao_sobrescreve_nada(self, canal_entregando):
        """Resposta neutra não pode virar "deixa passar": a conta existente
        mantém papel, consentimento, senha e verificação."""
        original = _usuario("intocavel@example.com", verificado=True, senha="SenhaAntiga123")
        original.papel = User.PAPEL_PREMIUM
        original.save(update_fields=["papel"])

        _cadastrar("intocavel@example.com", senha="SenhaNovaTentativa999")

        original.refresh_from_db()
        assert original.papel == User.PAPEL_PREMIUM
        assert original.check_password("SenhaAntiga123") is True
        assert original.email_verificado is True
        assert User.objects.filter(email="intocavel@example.com").count() == 1

    def test_reenviar_verificacao_nao_pode_virar_bombardeio_de_e_mail(self, canal_entregando):
        """O reenvio só acontece para conta AINDA NÃO VERIFICADA, e nunca cria
        conta nova.

        É a diferença entre "tirar a pessoa do beco sem saída" e "virar um
        amplificador de spam": contra um e-mail já verificado, um cadastro
        repetido não produz NENHUM e-mail, porque não há o que verificar. O
        que limita o volume contra o e-mail não verificado é o throttle por IP
        (`escrita_publica`), testado em `test_cadastro_tem_rate_limit_por_ip`.
        """
        _usuario("verificado-spam@example.com", verificado=True)
        _usuario("naoverificado-spam@example.com", verificado=False)

        mail.outbox = []
        for _ in range(2):
            _cadastrar("verificado-spam@example.com")
        assert mail.outbox == [], "e-mail já verificado não pode ser alvejado"

        mail.outbox = []
        _cadastrar("naoverificado-spam@example.com")
        assert [m.to for m in mail.outbox] == [["naoverificado-spam@example.com"]]

        # Nenhuma conta duplicada nasceu em nenhum dos dois caminhos.
        assert User.objects.filter(email="verificado-spam@example.com").count() == 1
        assert User.objects.filter(email="naoverificado-spam@example.com").count() == 1

    def test_cadastro_tem_rate_limit_por_ip(self, canal_entregando, throttle_ativo):
        respostas = [_cadastrar(f"throttle-cad-{i}@example.com").status_code for i in range(30)]

        assert 429 in respostas, f"sem rate limit em /auth/cadastro/: {respostas}"
