"""P1-04 — `identidade/emails.py` testado direto, sem passar pela view.

A SUÍTE `test_p1_04_entrega_email.py` prova o comportamento pelos endpoints.
Este arquivo cobre o que só existe no nível do serviço, e que os endpoints
nunca exercitam — o que é perigoso, porque defenses não cobertas são defenses
que quebram em silêncio:

1. **`_cobrar_canal_antes_de_gerar_token`** (`identidade/emails.py:61-78`).
   `CadastroView` e `RecuperarSenhaView` checam o canal ANTES de chamar estes
   helpers, então a checagem interna nunca dispara por eles. Ela existe para o
   próximo chamador que alguém vão adicionar daqui a seis meses. Um teste que
   ela levanta `CanalIndisponivel` é o que garante que ela ainda levanta
   alguma coisa.

2. **O token não é gerado quando não há canal.** O token de verificação é um
   `TimestampSigner` assinado cujo payload é `pk:email`
   (`identidade/tokens.py:28-31`) — o e-mail do titular está legível dentro
   dele. Gerar e descartar é como um token passa a vazar: num log de
   exceção, num traceback, num `print` de depuração futures. Aqui o teste
   patcha `make_*_token` para explodir se ela for chamada.

3. **O log da falha não leva o endereço do titular.** Só o pk, que não é PII
   e serve para o operador correlacionar.
"""

from __future__ import annotations

import logging

import pytest
from django.contrib.auth import get_user_model
from django.core import mail

from config.email_entrega import BACKENDS_SEM_ENTREGA_REAL, CanalIndisponivel, FalhaDeEntrega
from config.tests.backends import (
    EntregaSimuladaBackend,
    ExplodindoBackend,
    RecusaBackend,
    caminho_de,
)
from identidade import emails

pytestmark = pytest.mark.django_db

User = get_user_model()

BACKEND_QUE_ENTREGA = caminho_de(EntregaSimuladaBackend)


def _usuario(email):
    return User.objects.create_user(email=email, password="SenhaForte123")


def _token_nunca_deve_ser_gerado(nome):
    def explodir(*args, **kwargs):
        raise AssertionError(f"{nome} foi chamado mesmo sem canal de entrega")

    return explodir


class TestRecusaAntesDeGerarToken:
    @pytest.mark.parametrize("backend", sorted(BACKENDS_SEM_ENTREGA_REAL))
    def test_verificacao_recusa_sem_gerar_token(self, settings, backend, monkeypatch):
        settings.EMAIL_BACKEND = backend
        usuario = _usuario("sem-entrega@example.com")
        monkeypatch.setattr(
            emails, "make_email_verification_token", _token_nunca_deve_ser_gerado("make_email_verification_token")
        )

        with pytest.raises(CanalIndisponivel):
            emails.enviar_email_verificacao(usuario)

    @pytest.mark.parametrize("backend", sorted(BACKENDS_SEM_ENTREGA_REAL))
    def test_redefinicao_recusa_sem_gerar_token(self, settings, backend, monkeypatch):
        settings.EMAIL_BACKEND = backend
        usuario = _usuario("sem-entrega2@example.com")
        monkeypatch.setattr(
            emails, "make_password_reset_token", _token_nunca_deve_ser_gerado("make_password_reset_token")
        )

        with pytest.raises(CanalIndisponivel):
            emails.enviar_email_redefinicao_senha(usuario)

    def test_console_nao_imprime_o_token_no_stdout(self, settings, capsys):
        settings.EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
        usuario = _usuario("imprimido@example.com")

        with pytest.raises(CanalIndisponivel):
            emails.enviar_email_verificacao(usuario)

        capturado = capsys.readouterr()
        assert capturado.out == ""
        assert "imprimido@example.com" not in capturado.out

    def test_locmem_nao_enche_o_outbox(self, settings):
        settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
        usuario = _usuario("outbox@example.com")
        mail.outbox = []

        with pytest.raises(CanalIndisponivel):
            emails.enviar_email_verificacao(usuario)

        assert mail.outbox == []


class TestFalhaNaRecusaDeEntrega:
    @pytest.mark.parametrize(
        "classe", [RecusaBackend, ExplodindoBackend], ids=["devolve-0", "estoura"]
    )
    def test_falha_do_provedor_propaga_como_falha_de_entrega(self, settings, classe):
        settings.EMAIL_BACKEND = caminho_de(classe)
        usuario = _usuario("falhou@example.com")

        with pytest.raises(FalhaDeEntrega):
            emails.enviar_email_verificacao(usuario)

        with pytest.raises(FalhaDeEntrega):
            emails.enviar_email_redefinicao_senha(usuario)

    def test_log_da_falha_nao_traz_o_endereco_do_titular(self, settings, caplog):
        settings.EMAIL_BACKEND = caminho_de(ExplodindoBackend)
        usuario = _usuario("privado@example.com")

        with caplog.at_level(logging.DEBUG), pytest.raises(FalhaDeEntrega):
            emails.enviar_email_verificacao(usuario)

        logs = "\n".join(r.getMessage() for r in caplog.records)
        assert "privado@example.com" not in logs
        assert "provedor fora do ar" not in logs
        # O pk entra: não é PII e é o que o operador usa para correlacionar.
        assert str(usuario.pk) in logs


class TestCaminhoFelizDoServico:
    def test_verificacao_devolve_o_token_e_a_caixa_registra(self, settings):
        settings.EMAIL_BACKEND = BACKEND_QUE_ENTREGA
        usuario = _usuario("feliz@example.com")
        mail.outbox = []
        EntregaSimuladaBackend.entregues.clear()

        token = emails.enviar_email_verificacao(usuario)

        from identidade.tokens import read_email_verification_token

        resultado = read_email_verification_token(token)
        assert resultado is not None
        assert resultado[0] == str(usuario.pk)
        assert resultado[1] == "feliz@example.com"
        assert mail.outbox[0].to == ["feliz@example.com"]

    def test_redefinicao_devolve_uid_e_token(self, settings):
        settings.EMAIL_BACKEND = BACKEND_QUE_ENTREGA
        usuario = _usuario("feliz2@example.com")
        mail.outbox = []
        EntregaSimuladaBackend.entregues.clear()

        uidb64, token = emails.enviar_email_redefinicao_senha(usuario)

        from identidade.tokens import decode_uidb64, password_reset_token_generator

        assert decode_uidb64(uidb64) == str(usuario.pk)
        assert password_reset_token_generator.check_token(usuario, token) is True

    def test_e_mail_de_verificacao_tem_assunto_e_remetente_constantes(self, settings):
        """Nada do titular entra em header: o assunto é constante e o `to` vem da
        conta validada. É o que neutraliza injeção de header."""
        settings.EMAIL_BACKEND = BACKEND_QUE_ENTREGA
        usuario = _usuario("headers@example.com")
        mail.outbox = []

        emails.enviar_email_verificacao(usuario)

        mensagem = mail.outbox[0]
        assert mensagem.subject == emails.ASSUNTO_VERIFICACAO
        assert mensagem.reply_to == []
        assert mensagem.to == ["headers@example.com"]
        # `EmailMessage` puro (e não `EmailMultiAlternatives`): não existe
        # atributo `alternatives`, o que é exatamente a prova de que nenhuma
        # parte HTML foi anexada. O e-mail de verificação/redefinição é o
        # gancho de isca de phishing com o nome do portal, e um espelho HTML
        # só daria mais superfície para isso.
        assert not hasattr(mensagem, "alternatives")
