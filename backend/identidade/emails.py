"""
Envio de e-mails transacionais do módulo identidade/ (verificação de cadastro
e redefinição de senha).

O QUE MUDOU NESTE ITEM (P1-04) E POR QUÊ
========================================
Antes deste item, estes dois helpers faziam `send_mail(...)` e devolviam o
token, sem olhar para o que a resposta do `send_mail` significava. Com
`DJANGO_EMAIL_BACKEND=console.EmailBackend` (o padrão de
`config/settings.py:615-617`), `send_mail` **devolve 1 e imprime a mensagem no
stdout**: o helper "entregava", `CadastroView` respondia 201 "Verifique seu
e-mail" e `RecuperarSenhaView` respondia 200 "enviaremos instruções" — sem
nada ter saído. O usuário ficava esperando um e-mail que nunca chegava e não
tinha como recuperar. É o furo que o P0-02c documentou e que ninguém fechou.

Agora os dois passam por `config.email_entrega.entregar_email`, que:
  1. recusa ANTES de qualquer trabalho um backend que não entrega a ninguém
     (console/locmem/dummy/filebased/vazio) — nada de token gerado, nada
     impresso, nada no log;
  2. exige que o provedor tenha devolvido ≥ 1 depois do envio;
  3. levanta `CanalIndisponivel` ou `FalhaDeEntrega` caso contrário.

A ORDEM IMPORTA: a checagem de canal vem ANTES de `make_*_token`. Um token de
uso único que foi gerado e descartado é lixo que quase vaza — e o de
verificação é um `TimestampSigner` assinado (não cifrado) cujo payload é
`pk:email` (`identidade/tokens.py:28-31`), ou seja, o endereço do titular fica
legível dentro dele. Gerar só quando vai mesmo enviar é o que impede o token
de aparecer em log, em traceback e em memória morta.

Nenhum log deste módulo recebe o token, o uid nem o endereço do titular: só o
pk, que não é PII e serve para o operador correlacionar.
"""

from __future__ import annotations

import logging

from django.conf import settings
from django.core.mail import EmailMessage

from config.email_entrega import (
    CanalIndisponivel,
    FalhaDeEntrega,
    entregar_email,
    registrar_evento,
    verificar_canal_email,
)

from .tokens import make_email_verification_token, make_password_reset_token

logger = logging.getLogger(__name__)

#: Rótulos da métrica `portal_email_entrega_total`. São rótulos, não dados:
#: nenhum endereço de usuário entra neles.
DESTINO_VERIFICACAO = "verificacao"
DESTINO_REDEFINICAO = "redefinicao"

ASSUNTO_VERIFICACAO = "Confirme seu e-mail — Portal de Notícias"
ASSUNTO_REDEFINICAO = "Redefinição de senha — Portal de Notícias"


def _cobrar_canal_antes_de_gerar_token(destino: str) -> None:
    """Recusa o backend que não entrega ANTES de existir token.

    `entregar_email` faz esta checagem de novo (é a defesa completa, e é o que
    protege os outros chamadores). Aqui ela aparece antes da geração do token
    por um motivo específico deste módulo: o token não deve sequer existir
    quando não há para quem mandá-lo.
    """
    canal = verificar_canal_email()
    if canal.disponivel:
        return
    registrar_evento(destino, "sem_canal")
    logger.error(
        "email: canal de entrega indisponível, nada foi enviado (destino=%s motivo=%s)",
        destino,
        "; ".join(canal.motivos),
    )
    raise CanalIndisponivel(canal.motivos)


def _email_para(usuario, assunto: str, corpo: str) -> EmailMessage:
    """Monta o e-mail como `EmailMessage` text/plain.

    Sem alternativa HTML: a versão em texto é a que funciona em cliente de
    e-mail em modo texto. Nenhum dado do titular entra em header além do `to`
    (que vem do cadastro validado) e o assunto é constante — não há superfície
    de injeção de header.
    """
    return EmailMessage(
        subject=assunto,
        body=corpo,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[usuario.email],
    )


def enviar_email_verificacao(usuario) -> str:
    """Entrega o e-mail de verificação. Retorna o token SÓ se entregou.

    Levanta `CanalIndisponivel`/`FalhaDeEntrega` (de `config.email_entrega`)
    quando nada saiu — o chamador trata.
    """
    _cobrar_canal_antes_de_gerar_token(DESTINO_VERIFICACAO)

    token = make_email_verification_token(usuario)
    link = f"{settings.FRONTEND_BASE_URL}/verificar-email?token={token}"
    mensagem = _email_para(
        usuario,
        ASSUNTO_VERIFICACAO,
        (
            "Olá!\n\n"
            "Confirme seu cadastro clicando no link abaixo (ou envie o token "
            "para POST /api/auth/verificar-email/):\n\n"
            f"{link}\n\n"
            f"token: {token}\n\n"
            "Se você não fez este cadastro, ignore este e-mail."
        ),
    )
    try:
        entregar_email(mensagem, destino=DESTINO_VERIFICACAO)
    except (CanalIndisponivel, FalhaDeEntrega):
        # `logger.error` de propósito (não `warning`): é um ERROR de entrega,
        # do mesmo peso do ERROR de boot do P0-02c. Sem token, sem uid e sem
        # endereço — só o pk, que não é PII.
        logger.error(
            "identidade: e-mail de verificação do usuário pk=%s NÃO foi entregue",
            usuario.pk,
        )
        raise
    return token


def enviar_email_redefinicao_senha(usuario) -> tuple[str, str]:
    """Entrega o e-mail de redefinição. Retorna `(uid, token)` só se entregou."""
    _cobrar_canal_antes_de_gerar_token(DESTINO_REDEFINICAO)

    uidb64, token = make_password_reset_token(usuario)
    link = f"{settings.FRONTEND_BASE_URL}/redefinir-senha?uid={uidb64}&token={token}"
    mensagem = _email_para(
        usuario,
        ASSUNTO_REDEFINICAO,
        (
            "Recebemos um pedido de redefinição de senha para esta conta.\n\n"
            f"{link}\n\n"
            f"uid: {uidb64}\ntoken: {token}\n\n"
            "Se você não pediu isso, ignore este e-mail — sua senha continua a mesma."
        ),
    )
    try:
        entregar_email(mensagem, destino=DESTINO_REDEFINICAO)
    except (CanalIndisponivel, FalhaDeEntrega):
        # Mesmo cuidado do de verificação. O token de redefinição é um hash
        # (não carrega dado), mas o par (uid, token) é o que abre a redefinição.
        logger.error(
            "identidade: e-mail de redefinição de senha do usuário pk=%s NÃO foi entregue",
            usuario.pk,
        )
        raise
    return uidb64, token
