"""Validação do formulário de contato (P1-15b).

Os limites NÃO são arbitrários: cada um espelha o `maxLength`/`minLength` que
`frontend/app/contato/ContatoForm.tsx` já aplica no navegador (branch
`p1-15-rotas-formularios`, `ContatoForm.tsx:110-190`) OU um limite de protocolo
de e-mail. Aceitar no servidor mais do que a UI envia esconderia erro; aceitar
menos quebraria envio legítimo.

| campo      | limite aqui | de onde vem                                        |
|------------|-------------|----------------------------------------------------|
| `nome`     | 150         | `maxLength={150}` do `<Input>` (ContatoForm.tsx:139) e a checagem `nomeLimpo.length > 150` (ContatoForm.tsx:93) |
| `email`    | 254         | `maxLength={254}` do `<Input>` (ContatoForm.tsx:162) + RFC 5321 §4.5.3.1.3 (tamanho máximo de endereço) |
| `mensagem` | 4000        | `maxLength={4000}` do `<Textarea>` (ContatoForm.tsx:184); abaixo do teto prático de corpo de e-mail e do line-length (998) do RFC 5322, então o servidor nunca precisa quebrar o texto do usuário |
| `mensagem` | mín. 10     | "Descreva sua mensagem com pelo menos 10 caracteres." (ContatoForm.tsx:107) |

Sobre HTML/`<script>` no corpo: a decisão é NEUTRALIZAR, não rejeitar. Um
usuário legítimo pode precisar escrever "meu <div> não abre". Recusar a mensagem
por isso seria um beco sem saída sem ganho real de segurança, porque o corpo já
é entregue como `text/plain` (`contato/services.py:_montar_mensagem_email` nunca
anexa alternativa `text/html`) — o HTML viaja como dado inerte, nunca como
markup interpretável. O que É removido é o que realmente tem risco: caracteres
de controle (que quebram o layout do texto euxiliary/plain e, em campos que
viram header, permitiriam injeção de header) e quebras de linha em `nome`, que
é campo de linha única.
"""

from __future__ import annotations

import re

from rest_framework import serializers

LIMITE_NOME = 150
LIMITE_EMAIL = 254
MINIMO_MENSAGEM = 10
LIMITE_MENSAGEM = 4000

# Campo-armadilha (honeypot). Ver a justificativa em `contato/views.py`.
CAMPO_HONEYPOT = "website"
MENSAGEM_HONEYPOT = "Requisição rejeitada."

# Caracteres de controle C0 + DEL, exceto TAB (0x09) e LF (0x0A), que são
# legítimos em texto. Removidos porque são invisíveis para quem lê a mensagem e
# é com eles que se faz injeção de header/quebra de visualização em campos que
# viram header de e-mail.
_CARACTERES_DE_CONTROLE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def remover_controles(valor: str) -> str:
    """Remove controles invisíveis, preservando TAB/LF e o texto puro."""
    return _CARACTERES_DE_CONTROLE.sub("", valor)


def normalizar_nome(valor: str) -> str:
    """Nome é campo de linha única: qualquer quebra vira espaço."""
    return remover_controles(valor).replace("\n", " ").replace("\r", " ")


class MensagemContatoSerializer(serializers.Serializer):
    """Contrato de entrada de `POST /api/contato/` (`contato/views.py`)."""

    nome = serializers.CharField(max_length=LIMITE_NOME, allow_blank=False)
    email = serializers.EmailField(max_length=LIMITE_EMAIL)
    mensagem = serializers.CharField(
        max_length=LIMITE_MENSAGEM, min_length=MINIMO_MENSAGEM, allow_blank=False
    )
    # Honeypot: ausente/vazio = humano; preenchido = bot. `required=False`
    # para o payload honesto (que nunca envia o campo) continuar válido.
    website = serializers.CharField(
        required=False, allow_blank=True, max_length=200, write_only=True
    )

    def validate_nome(self, value: str) -> str:
        return normalizar_nome(value)

    def validate_mensagem(self, value: str) -> str:
        return remover_controles(value)

    def validate(self, attrs: dict) -> dict:
        if attrs.get(CAMPO_HONEYPOT):
            # Erro de campo não nomeado (`non_field_errors`): a resposta não
            # pode denunciar a armadilha, senão o bot aprende o nome do campo.
            # Também NÃO é 2xx: nada foi entregue, e um 200 seria mentira.
            raise serializers.ValidationError(MENSAGEM_HONEYPOT)
        # O honeypot é removido do resultado: `validated_data` carrega
        # exatamente os três campos que vão para o e-mail.
        attrs.pop(CAMPO_HONEYPOT, None)
        return attrs
