"""
Backend de e-mail transacional via Resend (https://resend.com), sem SDK
externo — só `requests` (já dependência do projeto).

Uso: `DJANGO_EMAIL_BACKEND=config.email_resend.ResendEmailBackend` +
`RESEND_API_KEY=re_...` no ambiente. Em sandbox/dev sem chave, manter o
default (console). Falha alto quando chamado sem chave — nunca engole envio.
"""

from __future__ import annotations

import logging

from django.core.mail.backends.base import BaseEmailBackend

from config.egress import EgressBloqueado, SessaoEgress

logger = logging.getLogger(__name__)

RESEND_API_URL = "https://api.resend.com/emails"


class ResendEmailBackend(BaseEmailBackend):
    def __init__(self, *args, **kwargs):
        from django.conf import settings

        super().__init__(*args, **kwargs)
        self._api_key = getattr(settings, "RESEND_API_KEY", "") or ""
        if not self._api_key:
            raise ValueError(
                "RESEND_API_KEY não configurado. Gere uma chave em "
                "https://resend.com/api-keys (use domínio verificado como remetente)."
            )

    def send_messages(self, email_messages):
        if not email_messages:
            return 0
        import requests

        enviados = 0
        # `RESEND_API_URL` é constante, mas a sessão com controle de saída
        # é usada mesmo assim: o requisito deste item é que TODO egresso
        # passe pelo módulo único, e um redirecionamento do provedor para
        # rede interna também deve ser barrado.
        sessao = SessaoEgress()
        for mensagem in email_messages:
            corpo: dict = {
                "from": mensagem.from_email,
                "to": list(mensagem.to or []),
                "subject": mensagem.subject,
                "text": mensagem.body or "",
            }
            if mensagem.cc:
                corpo["cc"] = list(mensagem.cc)
            if mensagem.bcc:
                corpo["bcc"] = list(mensagem.bcc)
            if mensagem.reply_to:
                corpo["reply_to"] = list(mensagem.reply_to)
            html = None
            for conteudo, tipo in getattr(mensagem, "alternatives", None) or []:
                if tipo == "text/html":
                    html = conteudo
                    break
            if html:
                corpo["html"] = html
            try:
                resposta = sessao.post(
                    RESEND_API_URL,
                    json=corpo,
                    headers={
                        "Authorization": f"Bearer {self._api_key}",
                        "Content-Type": "application/json",
                    },
                    timeout=20,
                )
            except EgressBloqueado as exc:
                # Nunca engolido: enviar e-mail para a rede interna não é
                # "falha silenciosa", é incidente de configuração.
                logger.error("Resend: destino bloqueado pela política de saída: %s", exc)
                if not self.fail_silently:
                    raise
                continue
            except requests.RequestException as exc:
                if not self.fail_silently:
                    raise
                logger.exception("Resend: falha de rede ao enviar e-mail: %s", exc)
                continue
            if resposta.status_code not in (200, 201):
                if not self.fail_silently:
                    raise ValueError(
                        f"Resend recusou o envio (HTTP {resposta.status_code}): {resposta.text[:300]}"
                    )
                logger.error("Resend recusou o envio (HTTP %s): %s", resposta.status_code, resposta.text[:300])
                continue
            enviados += 1
        sessao.close()
        return enviados
