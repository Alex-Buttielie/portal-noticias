"""
Backend Resend (`config/email_resend.py`): mapeamento Django -> API e
falhas altas — tudo com `requests` mockado, sem rede.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from django.core.mail import EmailMessage, EmailMultiAlternatives
from django.test import override_settings

from config.email_resend import ResendEmailBackend


def _resposta(status_code=200, corpo=None):
    mock = MagicMock()
    mock.status_code = status_code
    mock.text = str(corpo)
    return mock


@override_settings(RESEND_API_KEY="re_test_dummy")
def test_envia_texto_com_auth_e_remetente():
    mensagem = EmailMessage(
        subject="Verifique seu e-mail",
        body="Clique no link.",
        from_email="no-reply@portal-noticias.com.br",
        to=["leitor@example.com"],
    )

    with patch("config.email_resend.SessaoEgress.post", return_value=_resposta(200, {"id": "abc"})) as post:
        enviados = ResendEmailBackend().send_messages([mensagem])

    assert enviados == 1
    chamada = post.call_args
    assert chamada.args[0] == "https://api.resend.com/emails"
    assert chamada.kwargs["headers"]["Authorization"] == "Bearer re_test_dummy"
    corpo = chamada.kwargs["json"]
    assert corpo["from"] == "no-reply@portal-noticias.com.br"
    assert corpo["to"] == ["leitor@example.com"]
    assert corpo["subject"] == "Verifique seu e-mail"
    assert corpo["text"] == "Clique no link."


@override_settings(RESEND_API_KEY="re_test_dummy")
def test_envia_alternativa_html_quando_existe():
    mensagem = EmailMultiAlternatives(
        subject="Resumo", body="texto", from_email="a@x.com", to=["b@x.com"]
    )
    mensagem.attach_alternative("<p>html</p>", "text/html")

    with patch("config.email_resend.SessaoEgress.post", return_value=_resposta(200, {"id": "abc"})) as post:
        assert ResendEmailBackend().send_messages([mensagem]) == 1

    assert post.call_args.kwargs["json"]["html"] == "<p>html</p>"


@override_settings(RESEND_API_KEY="re_test_dummy")
def test_erro_http_levanta_quando_nao_silencioso():
    mensagem = EmailMessage(subject="s", body="b", from_email="a@x.com", to=["b@x.com"])

    with patch("config.email_resend.SessaoEgress.post", return_value=_resposta(422, {"message": "bad"})):
        with pytest.raises(ValueError, match="Resend recusou"):
            ResendEmailBackend().send_messages([mensagem])


@override_settings(RESEND_API_KEY="")
def test_sem_chave_falha_alto_na_inicializacao():
    with pytest.raises(ValueError, match="RESEND_API_KEY"):
        ResendEmailBackend()
