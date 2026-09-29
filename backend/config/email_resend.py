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
                # "falha silenciosa", é incidente de configuração. O log leva
                # o motivo do BLOQUEIO (que vem do módulo de egresso, é
                # controlado por nós), não o payload.
                logger.error("Resend: destino bloqueado pela política de saída: %s", exc)
                if not self.fail_silently:
                    raise
                continue
            except requests.RequestException as exc:
                if not self.fail_silently:
                    raise
                # Só o TIPO da exceção no log. `str(exc)` de um erro de rede
                # pode conter a URL com a query string; e o traceback que
                # `logger.exception` anexa é o que costuma ecoar o payload,
                # e o payload do e-mail de verificação CONTÉM o token de uso
                # único em texto claro. `config.email_entrega.entregar_email`
                # trata o `except` genérico que sobra e registra o tipo,
                # nunca o texto.
                logger.error(
                    "Resend: falha de rede ao enviar e-mail (tipo=%s)", type(exc).__name__
                )
                continue
            if resposta.status_code not in (200, 201):
                # `resposta.text` é o CORPO DE ERRO DO PROVEDOR, e um
                # provedor real pode ecoar o payload que recebeu — que aqui é
                # o e-mail de verificação/redefinição, com o token dentro.
                # P1-04: log e exceção levam o STATUS e nada mais. O
                # operador precisa do código HTTP para agir; o corpo do erro
                # do fornecedor não é seguro reproduzir.
                status = resposta.status_code
                if not self.fail_silently:
                    raise ValueError(f"Resend recusou o envio (HTTP {status})")
                logger.error("Resend recusou o envio (HTTP %s)", status)
                continue
            enviados += 1
        sessao.close()
        return enviados
