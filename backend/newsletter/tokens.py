"""
Token de descadastro da newsletter — P1-06.

O que este módulo resolve
========================
Até `d225791` o link de descadastro carregava o **segredo do banco cru**
(`InscricaoNewsletter.token_descadastro`, `newsletter/models.py:40`), e o
endpoint aceitava esse valor cru. Três consequências, todas medidas:

1. **Não expirava.** O campo é um `CharField` permanente: um link de descadastro
   impresso num e-mail de 2026 valia para sempre, e o valor sobrevive a logs de
   proxy, a "histórico do navegador" e a forwarded messages.
2. **Não era de uso único.** `descadastrar_por_token` só fazia
   `.update(ativa=False)`; o token continuava válido e replayável (3 POSTs = 3
   × 200, medido). Replay não é perigoso por si (a ação é idempotente), mas
   significa que o token **nunca expira na prática**, porque nada o inutiliza.
3. **Vazava o segredo.** O valor cru é o mesmo que fica no banco; colocá-lo na
   URL expõe o segredo de estado, não só um handle.

O desenho
=========
`TimestampSigner` (o mesmo par usado por `identidade/tokens.py:29` para
verificação de e-mail) sobre o **SHA-256** do segredo do banco:

    payload  = sha256(inscricao.token_descadastro).hexdigest()
    wire     = TimestampSigner(salt=...).sign(payload)   # "payload:timestamp:signature"

| propriedade           | como é garantida                                              |
|-----------------------|---------------------------------------------------------------|
| expira                | `unsign(max_age=...)` — `SignatureExpired` quando envelhece     |
| uso único             | o segredo do banco é **rotacionado** no uso (ver `services.descadastrar_por_token`), então o hash do token já usado não bate mais |
| não vaza o segredo    | só o SHA-256 vai no link; o segredo nunca sai do banco        |
| irrecuperável sem o banco | `TimestampSigner` assina, não cifra: quem tiver o link consegue ler o hash — e não consegue nada com ele, porque o hash não é o segredo e a comparison é feita no banco |

Por que `TimestampSigner` e não um token opaco novo em tabela: exigiria
migration, e este item não pode criar schema. A alternativa (campo de
expiração + campo de "usado em") tem o mesmo custo. O par
secret-no-banco + hash assinado entrega as duas propriedades sem tocar em
migration — e reaproveita o padrão que o projeto já provou em `identidade/`.

O que este módulo NÃO faz (e é Pendência jurídica, não bug)
============================================================
Não há registro datado da **revogação** do consentimento. O que existe é
`InscricaoNewsletter.ativa=False` + `atualizado_em` (auto_now), que é um
proxy — se algo reescrever a inscrição depois, a data da revogação se perde.
Um `consentimento_revogado_em` de verdade exige migration; ver o relatório do
P1-06.
"""

from __future__ import annotations

import hashlib

from django.conf import settings
from django.core import signing
from django.core.signing import BadSignature, SignatureExpired

# Salt próprio. Um token de descadastro de newsletter não pode ser aceito por
# `identidade/tokens.py` (nem o contrário): são PURPOSOS diferentes, e
# reaproveitar o mesmo token entre verificação de e-mail e descadastro daria ao
# dono de um link de verificação o direito de cancelar a newsletter — e o
# contrário.
DESCADASTRO_SALT = "newsletter.descadastrar"


def _assinante() -> signing.TimestampSigner:
    return signing.TimestampSigner(salt=DESCADASTRO_SALT)


def hash_do_segredo(segredo: str) -> str:
    """SHA-256 hexadecimal do segredo do banco. O segredo não sai daqui.

    Público porque `services._localizar_por_hash` precisa reproduzir o hash a
    partir de uma inscrição para comparar com o que veio no link — é a única
    forma de localizar a linha sem guardar o hash em coluna (que exigiria
    migration) nem expor o segredo.
    """
    return hashlib.sha256(segredo.encode("utf-8")).hexdigest()


def gerar_token_descadastro(inscricao) -> str:
    """Token que vai na URL do e-mail. Não expõe o segredo do banco."""
    return _assinante().sign(hash_do_segredo(inscricao.token_descadastro))


def ler_hash_do_token(token: str) -> str | None:
    """Devolve o hash assinado, ou `None` se o token for inválido/expirado.

    `None` é indistinguível de "token que não casa com nenhuma inscrição" para
    quem chama — é essa indistinguibilidade que impede o endpoint de virar
    oráculo de cadastro (ver `newsletter/views.DescadastrarView`).
    """
    if not token or not isinstance(token, str):
        return None
    max_age = getattr(
        settings, "NEWSLETTER_TOKEN_DESCADASTRO_MAX_AGE_SECONDS", 30 * 24 * 60 * 60
    )
    try:
        payload = _assinante().unsign(token.strip(), max_age=max_age)
    except (BadSignature, SignatureExpired):
        return None
    return payload or None
