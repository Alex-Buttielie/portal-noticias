"""Backends de e-mail usados SÓ pelos testes — o lado "provedor" da fiction.

Nenhum deles é usado em runtime, e nenhum está em `BACKENDS_SEM_ENTREGA_REAL`
(`config/email_entrega.py`) — o ponto é justamente simular um provedor que
ACEITA ENTREGAR, para que o caminho de sucesso dos fluxos de e-mail seja
exercitado de verdade, e simular provedores que recusam, para provar que recusa
vira erro e não 2xx.

O QUE MUDOU NO P1-04 E POR QUÊ
==============================
Até aqui a suíte rodava com o `locmem.EmailBackend` que o `pytest-django`
injeta, e era isso que `mail.outbox` enchia. O `locmem` está na lista de
backends que NÃO entregam (`config/email_entrega.py`), porque é isso que ele
é: um buffer em memória. Com o P1-04, `identidade/` e `newsletter/` passaram a
recusar um backend sem entrega real — e `locmem` é justamente um deles. Os
testes desses fluxos rodam agora sobre `EntregaSimuladaBackend`, que representa
o provedor que aceita e entrega.

`EntregaSimuladaBackend` herda de `locmem.EmailBackend` de propósito: assim ela
**entrega de verdade** no sentido do que os testes conseguem observar — a
mensagem é materializada em MIME e guardada, em `entregues` e em `mail.outbox` —
enquanto fica, para o gate, num caminho pontilhado diferente do `locmem` do
Django. A distinção não é um truque para enganar o gate: ela representa a
fato de que existe um provedor na frente que aceita a mensagem, coisa que o
`locmem` puro não tem.

`caminho_de` existe para que os testes escrevam o caminho pontilhado a partir
da classe, e não à mão: se o nome da classe mudasse, o teste passaria a falhar
na importação — em vez de "entregar" para um backend inexistente e cair no
`except` genérico, que devolveria erro e faria o teste passar pelo motivo
errado.
"""

from __future__ import annotations

from django.core.mail.backends.locmem import EmailBackend as LocmemEmailBackend


def caminho_de(classe: type) -> str:
    """Caminho pontilhado de um backend, para `settings.EMAIL_BACKEND`."""
    return f"{classe.__module__}.{classe.__qualname__}"


class EntregaSimuladaBackend(LocmemEmailBackend):
    """Provedor que aceita a mensagem e a entrega (devolve ≥ 1, como um SMTP)."""

    #: mensagens entregues nesta execução da suíte (reiniciada por teste)
    entregues: list = []

    def send_messages(self, email_messages):
        if not email_messages:
            return 0
        for mensagem in email_messages:
            # `.message()` materializa a MIME: é o que prova, no teste, o
            # que foi entregue (remetente, destinatário, corpo, assunto).
            self.entregues.append(mensagem.message())
        return super().send_messages(email_messages)


class RecusaBackend(LocmemEmailBackend):
    """Provedor que aceita a conexão mas não entrega nada (devolve 0)."""

    def send_messages(self, email_messages):
        return 0


class ExplodindoBackend(LocmemEmailBackend):
    """Provedor que estoura — simula timeout/erro de rede do provedor."""

    def send_messages(self, email_messages):
        raise RuntimeError("provedor fora do ar")


class ErroDeRedeBackend(LocmemEmailBackend):
    """Provedor que estoura com o tipo de exceção que `requests` usa.

    `config/email_resend.py:83` trata `requests.RequestException` (rede) e
    qualquer outra coisa sobe. Um provedor que derruba a conexão não é um
    `RuntimeError` genérico: é o caso que o item pede explicitamente
    (500/timeout/`ConnectionError`).
    """

    def send_messages(self, email_messages):
        import requests

        raise requests.ConnectionError("conexão com o provedor caiu")
