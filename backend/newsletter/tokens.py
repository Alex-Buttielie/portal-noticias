"""
Tokens da newsletter: descadastro (P1-06) e confirmação (double opt-in).

Dois PROPÓSITOS, um MESMO PAR. Ver a seção do double opt-in no fim deste
docstring.

O que este módulo resolve (descadastro)
=======================================
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

O que este módulo NÃO faz (e o que mudou)
========================================
Este módulo continua sem token próprio em tabela: o par segredo-no-banco +
hash assinado entrega expiração e uso único sem tocar em schema, e é o desenho
que o projeto já provou em `identidade/`.

O que mudou é uma CORREÇÃO DE UMA AFIRMAÇÃO QUE ESTAVA FALSA AQUI. A versão
anterior deste docstring dizia que "`atualizado_em` (auto_now) recebe o instante
da revogação" e que a data da revogação existia "como um proxy".

Não recebia, e não existia. O descadastro é feito com
`InscricaoNewsletter.objects.filter(...).update(...)`, e `auto_now` é aplicado
por `Model.save()`, não por update de queryset
(`django/db/models/fields/__init__.py`: `DateTimeField.pre_save` só é chamado
no caminho do `save()`). Medido nesta suíte: `atualizado_em` é byte a byte o
mesmo antes e depois do descadastro. Duas docstrings do projeto afirmavam o
contrário, e nenhum teste perguntava.

Hoje existe `InscricaoNewsletter.consentimento_revogado_em`, gravado no mesmo
`UPDATE`: de primeira classe, e sobrevive a qualquer reescrita posterior da
linha. A prova de que o `atualizado_em` nunca serviu está em
`newsletter/tests/test_p1_06_bordas_e_pendencia.py::test_a_data_da_revogacao_sobrevive_a_uma_reescrita_da_linha`.

Continua pendente, e é decisão de produto/jurídico: a versão do texto de
consentimento da newsletter (a coluna `versao_consentimento` existe, mas
`NEWSLETTER_VERSAO_CONSENTIMENTO` é vazio por padrão).

O DOUBLE OPT-IN (2026-10-02) — o MESMO PAR, UM PROPÓSITO NOVO
=============================================================
O token de confirmação NÃO é um segundo mecanismo: é o MESMO par
(segredo no banco + SHA-256 assinado com `TimestampSigner`), com um salt
próprio. A escolha é deliberada e tem dois motivos:

1. **Reuso, não reinvenção.** Um token opaco novo em tabela exigiria uma
   migration e um segundo lugar onde "o token já foi usado?" mora. Este módulo
   já provou, com teste, que o par entrega as três propriedades — expira
   (`unsign(max_age=...)`), é de uso único (o segredo é rotacionado no uso) e
   não vaza o segredo do banco (só o SHA-256 vai no link).
2. **Salt separado, e não FIELD separado só porque sim.** `CONFIRMACAO_SALT`
   é diferente de `DESCADASTRO_SALT` pelo mesmo motivo documentado acima: são
   PROPÓSITOS diferentes, e um link que abre um abre o outro é um link que dá
   ao dono de um deles um poder que não deveria ter. Quem tem o link de
   confirmação não pode cancelar a newsletter, e quem tem o de descadastro não
   pode confirmar uma inscrição.

As duas colunas (`token_descadastro` e `token_confirmacao`) também são
separadas, e por uma consequência prática do mesmo motivo: a rotação de um não
pode invalidar o outro. Se compartilhassem o segredo, confirmar a inscrição
rotacionaria o segredo que está no link de descadastro do ÚLTIMO RESUMO
ENTREGUE — e o titular perderia a saída da newsletter justamente no e-mail que
ela usa para querer sair. Seriam dois poderes num segredo só, e o segundo
perderia sem querer.
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
#: Salt do token de CONFIRMAÇÃO da inscrição (double opt-in). Deliberadamente
#: diferente do de descadastrar: são poderes diferentes, e um link que abre um
#: teria de abrir o outro. Ver o docstring do módulo.
CONFIRMACAO_SALT = "newsletter.confirmar"


def _assinante(salt: str = DESCADASTRO_SALT) -> signing.TimestampSigner:
    return signing.TimestampSigner(salt=salt)


def _assinante_confirmacao() -> signing.TimestampSigner:
    return signing.TimestampSigner(salt=CONFIRMACAO_SALT)


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


# ---------------------------------------------------------------------------
# CONFIRMAÇÃO DA INSCRIÇÃO (double opt-in) — o MESMO par, outro propósito
# ---------------------------------------------------------------------------


def gerar_token_confirmacao(inscricao) -> str:
    """Token que vai na URL do e-mail de confirmação. Não expõe o segredo.

    Assina `sha256(inscricao.token_confirmacao)` com o salt de CONFIRMAÇÃO. É
    a mesma construção de `gerar_token_descadastro`, com duas diferenças que
    são o ponto do desenho: outro segredo (outra coluna) e outro salt (outro
    poder). Rodar os dois tokens pelo MESMO par impede que alguém empurre um
    para o outro por engano depois.
    """
    return _assinante_confirmacao().sign(hash_do_segredo(inscricao.token_confirmacao))


def ler_hash_do_token_de_confirmacao(token: str) -> str | None:
    """Devolve o hash assinado da confirmação, ou `None` (inválido/expirado).

    O `None` é a mesma indistinguibilidade do descadastro, e por um motivo
    AGORA MAIS FORTE: a confirmação é um endpoint público e anônimo, e o
    `DescadastrarView` já estabeleceu que a resposta não pode distinguir
    "token válido" de "token que não casa com nada". Um atacante que consiga
    distinguir os dois confirma, para si mesmo, que um endereço está na base do
    portal — o vazamento que a LGPD e o art. 8º, V tratam como direito do
    titular, não como informação do portal.

    `None` cobre token malformado, assinatura inválida, expirado e token cujo
    segredo já foi rotacionado pelo uso. Os quatro são a mesma resposta, e é
    isso que o chamador precisa: um booleano "posso confirmar ou não".
    """
    if not token or not isinstance(token, str):
        return None
    max_age = getattr(
        settings, "NEWSLETTER_TOKEN_CONFIRMACAO_MAX_AGE_SECONDS", 7 * 24 * 60 * 60
    )
    try:
        payload = _assinante_confirmacao().unsign(token.strip(), max_age=max_age)
    except (BadSignature, SignatureExpired):
        return None
    return payload or None
