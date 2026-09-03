"""
Envio de e-mails transacionais do módulo identidade/.

Usa `django.core.mail.send_mail` com o `EMAIL_BACKEND` configurado em
`settings.py` (console em dev/teste por padrão). A integração com um
provedor real (SendGrid, SES, etc.) é uma decisão em aberto — ver
`implementation-contract.md`, seção "Não-objetivos", e
`implementation-history.md`.
"""

from django.conf import settings
from django.core.mail import send_mail

from .tokens import make_email_verification_token, make_password_reset_token


def enviar_email_verificacao(user):
    token = make_email_verification_token(user)
    link = f"{settings.FRONTEND_BASE_URL}/verificar-email?token={token}"
    send_mail(
        subject="Confirme seu e-mail — Portal de Notícias",
        message=(
            "Olá!\n\n"
            "Confirme seu cadastro clicando no link abaixo (ou envie o token "
            "para POST /api/auth/verificar-email/):\n\n"
            f"{link}\n\n"
            f"token: {token}\n\n"
            "Se você não fez este cadastro, ignore este e-mail."
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
        fail_silently=False,
    )
    return token


def enviar_email_redefinicao_senha(user):
    uidb64, token = make_password_reset_token(user)
    link = f"{settings.FRONTEND_BASE_URL}/redefinir-senha?uid={uidb64}&token={token}"
    send_mail(
        subject="Redefinição de senha — Portal de Notícias",
        message=(
            "Recebemos um pedido de redefinição de senha para esta conta.\n\n"
            f"{link}\n\n"
            f"uid: {uidb64}\ntoken: {token}\n\n"
            "Se você não pediu isso, ignore este e-mail — sua senha continua a mesma."
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
        fail_silently=False,
    )
    return uidb64, token
