"""DOUBLE OPT-IN: O ESTADO PENDENTE DA CONFIRMAÇÃO DA INSCRIÇÃO.

⚠️ ESTA MIGRATION FOI ESCRITA E NÃO FOI APLICADA.
=================================================
A regra da casa é NUNCA criar migration sem autorização. O solicitante
autorizou a `0003` (retenção/anomização), que também continua **não
aplicada**; esta, a `0004`, é deste item e **não foi autorizada por ninguém**.
Ela está escrita e versionada porque o double opt-in não existe sem schema —
mas ela **precisa de autorização explícita antes de ser aplicada** em
qualquer banco que não seja o efêmero que o `pytest-django` cria e destrói a
cada sessão. Rodar `manage.py migrate` com isto em produção é uma decisão
separada, de outra pessoa, e este arquivo não a toma.

A ORDEM, E POR QUE ESTA CONVIVE COM A `0003` SEM COLIDIR
=======================================================
`0003_retencao_consentimento_e_anonimizacao` faz `user` NULLABLE/SET_NULL e
entra em `consentimento_aceito_em`, `consentimento_revogado_em`,
`anonimizado_em`, `versao_consentimento` e `referencia_opaca`.

Esta declara `dependencies = [("newsletter", "0003_...")]`, e por isso a ordem
é **0001 → 0002 → 0003 → 0004**, aplicada numa sequência só.

Não há colisão de estado porque as duas migrations mexem em colunas
**disjuntas** — nenhuma operação daqui toca em `user`, em
`consentimento_aceito_em` nem em nenhuma das outras da `0003`. E há uma
dependência de VALOR, que é mais interessante que a de coluna:

**`0003` define `consentimento_aceito_em` como "quando o titular concedeu o
consentimento". Com double opt-in, quem concede é o CLIQUE — não o POST.** Por
isso `inscrever_com_status` grava `consentimento_aceito_em=None` e
`confirmar_por_token` grava a data. Aplicar esta migration e depois aplicar a
`0003` daria o mesmo schema, mas com um código de `services.py` que não
corresponde a ele; por isso a dependência é explícita e não apenas tolerada.

A ordem inversa (0004 antes de 0003) é IMPOSSÍVEL por construção: o Django
recusa uma dependência que aponta para o futuro, e `0003` tem
`AddField`/`AlterField` em colunas que `0004` não cria. Mas há uma razão mais
fuerte: `0003` tem um `RunPython` que popula `referencia_opaca` linha a linha,
e rodá-lo sobre uma base cujas linhas já têm `confirmado_em` é seguro — o
oposto, rodar o `RunPython` da `0003` depois de a `0004` ter criado
`token_confirmacao`, também é seguro, porque o `RunPython` só toca
`referencia_opaca`. As duas são ortogonais por construção; a dependência
explícita existe para que a ordem seja uma DECISÃO documentada e não um
acidente do agendamento.

O QUE ESTA MIGRATION FAZ
========================
1. `token_confirmacao` — segredo do par de tokens de confirmação. Coluna
   SEPARADA de `token_descadastro`, e o motivo está em `newsletter/tokens.py`:
   confirmar rotacionaria o segredo que está no link de descadastro do ÚLTIMO
   RESUMO ENTREGUE, e o titular perderia a saída da newsletter no e-mail que
   ele usa para querer sair.
2. `confirmacao_solicitada_em`, `confirmado_em`, `pendencia_expirada_em` — os
   três campos que materializam os três estados.

O QUE ESTA MIGRATION DEIXA EM BRANCO, E POR QUÊ
===============================================
`confirmado_em` das inscrições **existentes** fica NULL, e não backfilled.

As duas alternativas seriam mentira, e as duas foram consideradas:

* backfill com `criado_em` — affirmaria que aquelas pessoas "confirmaram" numa
  data em que nem o termo existia. Ninguém clicou em nada; o fluxo era imediato
  e silêncio era o preço da inscrição. Gravar uma confirmação que não houve é
  fabricar o registro de consentimento mais sensível que existe neste código,
  que é o que diz "a pessoa confirmou, em data X, que quer receber".
* backfill com `consentimento_aceito_em` quando existir — dataria uma
  confirmação com a data de uma OUTRA coisa (o pedido). Continuaria sendo uma
  confirmação que não aconteceu.

NULL é a resposta honesta, e é também a resposta CONSERVADORA: uma inscrição
existente com `confirmado_em=NULL` é uma PENDÊNCIA, e pendência não recebe
(`enviar_newsletters` filtra `confirmado_em__isnull=False`) e não confirma
(`confirmar_por_token` só casa linhas pendentes, e o token do fluxo antigo não
existe). Ou seja: **aplicar esta migration desliga o envio para as inscrições
que já existiam**, até que cada pessoa confirme de novo.

Isso é uma consequência REAL e precisa de decisão de produto, e é o que o
solicitante precisa saber antes de autorizar: a alternativa seria um
`RunPython` de backfill, e ela foi rejeitada aqui porque backfill é a forma
mais fácil de fabricar um registro de consentimento — exatamente o que este
programa passou a existir para não fazer. Se a decisão for manter quem já
recebia recebendo, a decisão precisa ser escrita e datada por quem tem
autoridade para datar um consentimento, não inferida por uma migration.

O QUE NÃO ESTÁ NESTE ARQUIVO, DE PROPÓSITO
==========================================
Não há `AlterField` em `ativa`. O campo continua `BooleanField(default=True)`
no schema, e o double opt-in escreve `ativa=False` na inscrição — o default do
modelo é o valor legado, e usá-lo em código novo daria a uma linha pendente o
`ativa=True` que faria uma tela futura tratá-la como inscrita. Ver
`newsletter/models.py`, no bloco dos três estados.
"""

from django.db import migrations, models

import newsletter.models


class Migration(migrations.Migration):

    dependencies = [
        # Ver o docstring: a ordem 0003 → 0004 é uma decisão documentada, e não
        # um acidente. Ver também a nota sobre `consentimento_aceito_em`.
        ("newsletter", "0003_retencao_consentimento_e_anonimizacao"),
    ]

    operations = [
        # 1. O segredo da confirmação. `editable=False` pelo mesmo motivo de
        #    `token_descadastro` não ter nada contra si: o admin é lido por mais
        #    gente que o necessário, e um segredo que aparece num `change` está
        #    um `print` de distância do log.
        migrations.AddField(
            model_name="inscricaonewsletter",
            name="token_confirmacao",
            field=models.CharField(
                default=newsletter.models.gerar_token,
                editable=False,
                help_text="Segredo do token de confirmação. Nunca sai do banco.",
                max_length=64,
                unique=True,
            ),
        ),
        # 2. Os três campos dos três estados.
        migrations.AddField(
            model_name="inscricaonewsletter",
            name="confirmacao_solicitada_em",
            field=models.DateTimeField(
                blank=True,
                help_text=(
                    "Quando o link de confirmação foi enviado para esta "
                    "inscrição."
                ),
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="inscricaonewsletter",
            name="confirmado_em",
            field=models.DateTimeField(
                blank=True,
                help_text=(
                    "Quando a pessoa confirmou a inscrição pelo link do "
                    "e-mail. NULL = pendente."
                ),
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="inscricaonewsletter",
            name="pendencia_expirada_em",
            field=models.DateTimeField(
                blank=True,
                help_text=(
                    "Quando a pendência expirou sem confirmação. NULL = não "
                    "expirou."
                ),
                null=True,
            ),
        ),
        # 3. Os dois índices dos dois jobs. Sem eles, `enviar_newsletters` faz
        #    seq scan de uma tabela que só cresce, e a varredura de pendências
        #    (que roda sobre `confirmado_em IS NULL AND
        #    pendencia_expirada_em IS NULL`) idem. Os nomes têm ≤ 30 caracteres
        #    porque é o limite do Django (`models.E034`), e `manage.py check` é
        #    exatamente onde esse limite aparece.
        migrations.AddIndex(
            model_name="inscricaonewsletter",
            index=models.Index(
                fields=["ativa", "confirmado_em"],
                name="newsletter_ativa_confi_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="inscricaonewsletter",
            index=models.Index(
                fields=["confirmado_em", "pendencia_expirada_em"],
                name="newsletter_confi_expi_idx",
            ),
        ),
    ]