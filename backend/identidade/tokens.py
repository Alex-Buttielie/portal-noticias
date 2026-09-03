"""
Tokens de verificação de e-mail e de redefinição de senha.

- Verificação de e-mail: `TimestampSigner` (django.core.signing) com salt
  próprio e expiração configurável (`EMAIL_VERIFICATION_TOKEN_MAX_AGE_SECONDS`).
  Reaplicar um token já usado é inofensivo (idempotente — só marca
  `email_verificado=True` de novo), então não há necessidade de um modelo de
  token de uso único para satisfazer os critérios de aceite deste contrato.

- Redefinição de senha: `PasswordResetTokenGenerator` padrão do Django, que
  já incorpora o hash da senha atual e o `last_login` no hash do token — ou
  seja, assim que a senha é trocada, qualquer token antigo emitido para
  aquele usuário deixa de ser válido automaticamente (critério de aceite 7).
"""

from django.conf import settings
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.core import signing
from django.core.signing import BadSignature, SignatureExpired
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from django.utils.encoding import force_bytes, force_str

EMAIL_VERIFICATION_SALT = "identidade.verificar-email"

password_reset_token_generator = PasswordResetTokenGenerator()


def make_email_verification_token(user):
    signer = signing.TimestampSigner(salt=EMAIL_VERIFICATION_SALT)
    payload = f"{user.pk}:{user.email}"
    return signer.sign(payload)


def read_email_verification_token(token):
    """Retorna o `pk` (str) do usuário se o token for válido e não expirado, senão None."""
    signer = signing.TimestampSigner(salt=EMAIL_VERIFICATION_SALT)
    max_age = settings.EMAIL_VERIFICATION_TOKEN_MAX_AGE_SECONDS
    try:
        payload = signer.unsign(token, max_age=max_age)
    except (BadSignature, SignatureExpired):
        return None
    user_pk, _, email = payload.partition(":")
    return user_pk, email


def make_password_reset_token(user):
    uidb64 = urlsafe_base64_encode(force_bytes(user.pk))
    token = password_reset_token_generator.make_token(user)
    return uidb64, token


def decode_uidb64(uidb64):
    try:
        return force_str(urlsafe_base64_decode(uidb64))
    except (TypeError, ValueError, OverflowError):
        return None
