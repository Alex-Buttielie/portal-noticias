"""Backends de e-mail usados SÓ pelos testes de `contato/`.

Nenhum deles é usado em runtime, e nenhum está em `BACKENDS_SEM_ENTREGA_REAL`
(`contato/services.py`) — o ponto é justamente simular um provedor que ACEITA
ENTREGAR, para que o caminho de 2xx da view seja exercitado de verdade, e
simular provedores que recusam, para provar que recusas viram 503.

O "console" de verdade continua fora daqui: é o backend real do projeto e é
usado nos testes como está (`EMAIL_BACKEND` default), justamente para provar que
o endpoint recusa um backend que apenas imprime.
"""

from __future__ import annotations

from django.core.mail.backends.base import BaseEmailBackend


def caminho_de(classe: type) -> str:
    """Caminho pontilhado de um backend, para `settings.EMAIL_BACKEND`.

    Os testes usam isto em vez de escrever o caminho à mão: se o nome da classe
    mudasse, o teste passaria a falhar na importação — em vez de "entregar"
    para um backend inexistente e cair no `except` genérico, que devolveria 503
    e faria o teste passar pelo motivo errado.
    """
    return f"{classe.__module__}.{classe.__qualname__}"


class EntregaSimuladaBackend(BaseEmailBackend):
    """Provedor que aceita a mensagem e devolve 1 (como um SMTP real aceito)."""

    #: mensagens entregues nesta execução da suíte (reiniciada por teste)
    entregues: list = []

    def send_messages(self, email_messages):
        if not email_messages:
            return 0
        for mensagem in email_messages:
            # `.message()` materializa a MIME: é o que prova, no teste, que a
            # mensagem entregue é text/plain e não tem alternativa HTML.
            self.entregues.append(mensagem.message())
        return len(email_messages)


class RecusaBackend(BaseEmailBackend):
    """Provedor que aceita a conexão mas não entrega nada (devolve 0)."""

    def send_messages(self, email_messages):
        return 0


class ExplodindoBackend(BaseEmailBackend):
    """Provedor que estoura — simula timeout/erro de rede do provedor."""

    def send_messages(self, email_messages):
        raise RuntimeError("provedor fora do ar")
