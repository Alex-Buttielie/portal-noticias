"""
Backend Resend (`config/email_resend.py`): mapeamento Django -> API e
falhas altas — tudo com `requests` mockado, sem rede.

O dublê tem que estar em `config.email_resend.SessaoEgress.post`, e não em
`requests.post`: o P0-10 (eixo SSRF) trocou a chamada direta pela sessão de
egresso, e um dublê no lugar errado não falha — ele sai para
`api.resend.com` de verdade (já aconteceu nesta run do P1-15b: um 401 real no
lugar do 201 simulado).
"""

from __future__ import annotations

import logging
from unittest.mock import MagicMock, patch

import pytest
import requests
from django.core.mail import EmailMessage, EmailMultiAlternatives
from django.test import override_settings

from config.egress import EgressBloqueado
from config.email_resend import ResendEmailBackend

#: Marcador único: se ele aparecer num log ou numa exceção, o texto do
#: provedor (que pode ecoar o payload — e o payload do e-mail de verificação
#: tem o token dentro) vazou.
TEXTO_DO_PROVEDOR_QUE_NAO_PODE_VAZAR = "to: nao-recebe@exemplo.invalido, subject: token=abc123"


def _resposta(status_code=200, corpo=None):
    mock = MagicMock()
    mock.status_code = status_code
    mock.text = str(corpo)
    return mock


def _mensagem(**extra):
    base = dict(
        subject="Verifique seu e-mail",
        body="Clique no link.",
        from_email="no-reply@portal-noticias.com.br",
        to=["leitor@example.com"],
    )
    base.update(extra)
    return EmailMessage(**base)


def _rede_proibida(*args, **kwargs):
    raise AssertionError("este teste tentou sair para a rede real; o dublê tem que estar em SessaoEgress.post")


@pytest.fixture(autouse=True)
def _nenhum_teste_sai_para_a_rede(monkeypatch):
    monkeypatch.setattr("requests.post", _rede_proibida)
    monkeypatch.setattr("requests.get", _rede_proibida)
    monkeypatch.setattr("urllib.request.urlopen", _rede_proibida)


@override_settings(RESEND_API_KEY="re_test_dummy")
def test_envia_texto_com_auth_e_remetente():
    mensagem = _mensagem()

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
    with patch("config.email_resend.SessaoEgress.post", return_value=_resposta(422, {"message": "bad"})):
        with pytest.raises(ValueError, match="Resend recusou"):
            ResendEmailBackend().send_messages([_mensagem()])


@override_settings(RESEND_API_KEY="")
def test_sem_chave_falha_alto_na_inicializacao():
    with pytest.raises(ValueError, match="RESEND_API_KEY"):
        ResendEmailBackend()


# ---------------------------------------------------------------------------
# P1-04: o texto do provedor não pode vazar para log nem para exceção
# ---------------------------------------------------------------------------


@override_settings(RESEND_API_KEY="re_test_dummy")
def test_texto_do_provedor_nao_vaza_na_excecao(caplog):
    """Um provedor real pode ecoar no corpo do erro o payload que recebeu, e o
    payload do e-mail de verificação CONTÉM o token de uso único em texto
    claro. A exceção leva o código HTTP — que é o que o operador precisa para
    agir — e nada do corpo."""
    resposta = _resposta(422, TEXTO_DO_PROVEDOR_QUE_NAO_PODE_VAZAR)

    with caplog.at_level(logging.DEBUG), patch(
        "config.email_resend.SessaoEgress.post", return_value=resposta
    ), pytest.raises(ValueError) as info:
        ResendEmailBackend().send_messages([_mensagem()])

    assert "422" in str(info.value)
    assert TEXTO_DO_PROVEDOR_QUE_NAO_PODE_VAZAR not in str(info.value)
    assert TEXTO_DO_PROVEDOR_QUE_NAO_PODE_VAZAR not in caplog.text


@override_settings(RESEND_API_KEY="re_test_dummy")
def test_erro_http_com_fail_silently_conta_zero_e_nao_vaza(caplog):
    resposta = _resposta(500, TEXTO_DO_PROVEDOR_QUE_NAO_PODE_VAZAR)

    with caplog.at_level(logging.DEBUG), patch(
        "config.email_resend.SessaoEgress.post", return_value=resposta
    ):
        enviados = ResendEmailBackend(fail_silently=True).send_messages([_mensagem()])

    assert enviados == 0
    assert "500" in caplog.text
    assert TEXTO_DO_PROVEDOR_QUE_NAO_PODE_VAZAR not in caplog.text


# ---------------------------------------------------------------------------
# P1-04: ramos deCc/Bcc/reply_to e de falha de rede
# ---------------------------------------------------------------------------


@override_settings(RESEND_API_KEY="re_test_dummy")
def test_mapeia_cc_bcc_e_reply_to():
    mensagem = _mensagem()
    mensagem.cc = ["copia@example.com"]
    mensagem.bcc = ["oculto@example.com"]
    mensagem.reply_to = ["responder@example.com"]

    with patch("config.email_resend.SessaoEgress.post", return_value=_resposta(200)) as post:
        assert ResendEmailBackend().send_messages([mensagem]) == 1

    corpo = post.call_args.kwargs["json"]
    assert corpo["cc"] == ["copia@example.com"]
    assert corpo["bcc"] == ["oculto@example.com"]
    assert corpo["reply_to"] == ["responder@example.com"]


@override_settings(RESEND_API_KEY="re_test_dummy")
def test_sem_cc_bcc_ou_reply_to_nao_manda_campos_vazios():
    """A API do Resend rejeita `cc: []`. Só enviar o campo quando existe."""
    with patch("config.email_resend.SessaoEgress.post", return_value=_resposta(200)) as post:
        ResendEmailBackend().send_messages([_mensagem()])

    corpo = post.call_args.kwargs["json"]
    for campo in ("cc", "bcc", "reply_to", "html"):
        assert campo not in corpo


@override_settings(RESEND_API_KEY="re_test_dummy")
def test_201_tambem_e_aceito():
    """A API do Resend responde 200 ou 201 dependendo da versão; tratar só um
    deles seria uma falha silenciosa de entrega."""
    with patch("config.email_resend.SessaoEgress.post", return_value=_resposta(201)):
        assert ResendEmailBackend().send_messages([_mensagem()]) == 1


@override_settings(RESEND_API_KEY="re_test_dummy")
def test_lista_vazia_devolve_zero_sem_chamar_a_rede():
    with patch("config.email_resend.SessaoEgress.post", side_effect=_rede_proibida):
        assert ResendEmailBackend().send_messages([]) == 0


@override_settings(RESEND_API_KEY="re_test_dummy")
def test_falha_de_rede_propaga_quando_nao_silencioso():
    with patch(
        "config.email_resend.SessaoEgress.post",
        side_effect=requests.ConnectionError("conexão caiu"),
    ), pytest.raises(requests.ConnectionError):
        ResendEmailBackend().send_messages([_mensagem()])


@override_settings(RESEND_API_KEY="re_test_dummy")
def test_falha_de_rede_com_fail_silently_conta_zero_e_nao_vaza(caplog):
    with caplog.at_level(logging.DEBUG), patch(
        "config.email_resend.SessaoEgress.post",
        side_effect=requests.ConnectionError("conexão caiu"),
    ):
        enviados = ResendEmailBackend(fail_silently=True).send_messages([_mensagem()])

    assert enviados == 0
    assert "ConnectionError" in caplog.text
    assert "conexão caiu" not in caplog.text, "o log copiou str(exc) do provedor"


@override_settings(RESEND_API_KEY="re_test_dummy")
def test_timeout_e_de_verdade_uma_tentativa_e_nao_um_lacre():
    """A chamada declara `timeout=20` (`email_resend.py:74`). Sem isso, um
    provedor que aceita a conexão e nunca responde travaria a thread do
    worker, e o pedido de redefinição de senha (síncrono, no request) travaria
    junto."""
    with patch("config.email_resend.SessaoEgress.post", return_value=_resposta(200)) as post:
        ResendEmailBackend().send_messages([_mensagem()])

    assert post.call_args.kwargs["timeout"] == 20


@override_settings(RESEND_API_KEY="re_test_dummy")
def test_egress_bloqueado_propaga_e_nao_vaza_o_payload(caplog):
    """Enviar e-mail para a rede interna é incidente de configuração, não
    "falha silenciosa": propaga, e o log diz o motivo do bloqueio (que é
    nosso), não o conteúdo da mensagem."""
    with caplog.at_level(logging.ERROR), patch(
        "config.email_resend.SessaoEgress.post",
        side_effect=EgressBloqueado("host forbidden", host="10.0.0.1"),
    ), pytest.raises(EgressBloqueado):
        ResendEmailBackend().send_messages([_mensagem()])

    assert "host forbidden" in caplog.text
    assert "Clique no link" not in caplog.text


@override_settings(RESEND_API_KEY="re_test_dummy")
def test_egress_bloqueado_com_fail_silently_conta_zero():
    with patch(
        "config.email_resend.SessaoEgress.post",
        side_effect=EgressBloqueado("host forbidden", host="10.0.0.1"),
    ):
        assert ResendEmailBackend(fail_silently=True).send_messages([_mensagem()]) == 0


@override_settings(RESEND_API_KEY="re_test_dummy")
def test_uma_falha_no_meio_nao_impede_as_demais_da_lote():
    """O `send_messages` itera e conta um a um: uma mensagem recusada no meio
    do lote não pode fazer as anteriores deixarem de contar (elas saíram)."""
    respostas = [_resposta(200), _resposta(422), _resposta(201)]

    with patch("config.email_resend.SessaoEgress.post", side_effect=respostas):
        enviados = ResendEmailBackend(fail_silently=True).send_messages(
            [_mensagem(), _mensagem(), _mensagem()]
        )

    assert enviados == 2
