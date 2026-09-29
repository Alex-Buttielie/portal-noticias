"""
Dublês de teste do `newsletter/` — P1-06.

POR QUE ESTE ARQUIVO EXISTE
==========================
O `newsletter/services.py` só conta um e-mail como entregue (`total_enviados`)
quando o `EMAIL_BACKEND` configurado **entrega de verdade** — a mesma regra de
`contato/` (P0-02c, furo 3). Isso cria um problema de teste que não existia
antes: `django.test.utils.setup_test_environment()` **sobrescreve**
`settings.EMAIL_BACKEND` com `locmem` no início de toda sessão de teste
(`django/test/utils.py:146-147`), e `locmem` está na lista de backends que não
entregam. Portanto **nenhum teste deste projeto**, por padrão, roda contra um
backend que entrega.

Isso é bom — é o comportamento honesto aparecendo em todo lugar — mas deixa
sem cobertura o caminho de "entregou de verdade". Para exercitá-lo sem rede e
sem credencial, este arquivo declara um backend de e-mail que:

  * faz **zero I/O** (não abre socket, não escreve arquivo, não imprime);
  * guarda o que "entregou" numa lista em memória (`mail.outbox`, a mesma
    convenção do `locmem`), para o teste poder afirmar QUANTO e PARA QUEM;
  * **não finge ser um provedor real**: o nome diz que é dublê e o módulo diz o
    que ele é. Ele existe para provar que a contagem de entrega acontece quando
    existe canal, não para provar que Resend funciona.

Credencial Resend real é Pendência: `RESEND_API_KEY` chega depois do
solicitante (ver `PROD_DECISOES.md`, item 2). Nada aqui a usa.
"""

from __future__ import annotations

from django.core.mail.backends.base import BaseEmailBackend

# Caminhos importáveis dos dublês, para uso em `override_settings`.
CAMINHO_ENTREGA = "newsletter.tests.doubles.EntregaRegistradaBackend"
CAMINHO_RECUSA = "newsletter.tests.doubles.BackendQueRecusa"
CAMINHO_EXPLODE = "newsletter.tests.doubles.BackendQueExplode"


class EntregaRegistradaBackend(BaseEmailBackend):
    """Backend que registra o que enviaria, sem I/O. NÃO é um provedor real."""

    def send_messages(self, email_messages):
        if not email_messages:
            return 0
        from django.core import mail

        mail.outbox.extend(email_messages)
        return len(email_messages)


class BackendQueRecusa(BaseEmailBackend):
    """Backend que sempre recusa o envio, como um provedor que devolvê 4xx."""

    def send_messages(self, email_messages):
        return 0


class BackendQueExplode(BaseEmailBackend):
    """Backend que levanta exceção com o destinatário no texto do erro.

    Reproduz o caso que motiva a regra de log mínimo: a mensagem de erro de um
    backend real costuma ecoar o endereço (`SMTPServerDisconnected: ... b'
    fulano@exemplo.com' ...`). O teste que usa este dublê afirma que esse
    endereço **não** aparece no log.
    """

    def send_messages(self, email_messages):
        raise OSError(
            "falha de rede: b'550 recipient fulano-de-exemplo@exemplo.com "
            "rejected (endereco-secreto-nao-deve-ir-para-o-log)'"
        )
