"""REGISTRO DATADO DO CONSENTIMENTO E ANONIMIZAÇÃO NO DESCADASTRO.

⚠️ ESTA MIGRATION FOI ESCRITA E NÃO FOI APLICADA.
=================================================
A regra da casa é NUNCA criar migration sem autorização. O solicitante
autorizou explicitamente este item, então a migration está escrita e versionada
— mas ela **precisa de autorização explícita antes de ser aplicada** em
qualquer banco que não seja o efêmero de teste que o `pytest-django` cria e
destrói a cada sessão. Rodar `manage.py migrate` com isto em produção é uma
decisão separada, de outra pessoa, e este arquivo não a toma.

O QUE ELA FAZ
==============
1. `user` deixa de ser obrigatório: deixa de ser `CASCADE` e passa a ser
   `SET_NULL`, para que o registro do consentimento **sobreviva à conta**. Com
   `CASCADE`, apagar a conta apagaria a prova de que o consentimento existiu e
   foi revogado — o erro oposto ao que este item fecha.
2. Entram `consentimento_aceito_em`, `consentimento_revogado_em` e
   `anonimizado_em`.
3. `referencia_opaca` entra em DUAS etapas (sem `unique`, depois com), porque
   um `default` chamável em campo `unique` dá o MESMO valor para todas as linhas
   já existentes e a criação falha. Ver a nota no `RunPython`.
4. `versao_consentimento` entra com default vazio.

O QUE ELA DEIXA EM BRANCO, E POR QUÊ
=====================================
`consentimento_aceito_em` das inscrições **existentes** fica NULL, e não
backfilled.

Duas opções pareciam possíveis e as duas seriam mentira:

* backfill com `User.consentimento_aceito_em` — dataria o consentimento da
  newsletter com a data do aceite dos **Termos** no cadastro. São finalidades
  diferentes (a LGPD distingue finalidades), e a data ficaria errada;
* backfill com `criado_em` — a data em que a LINHA foi criada, que só é
  aproximadamente a data do consentimento, e para uma inscrição reescrita
  depois é pior que nada.

NULL é a resposta honesta: significa "não registramos quando esta pessoa
consentiu". A partir de uma nova inscrição, o campo é preenchido de verdade
(`services.inscrever_com_status`). Uma coluna com o valor certo a partir de um
corte, e honestamente vazia antes dele, é auditável; uma coluna preenchida com
uma data inventada não é.
"""

import secrets

from django.conf import settings
from django.db import migrations, models

import newsletter.models


def _preencher_referencia_opaca(apps, schema_editor):
    """Gera um valor ALEATÓRIO distinto para cada linha já existente.

    Não é backfill de dado pessoal: a referência é opaca por construção e não
    deriva de nada do titular (ver `newsletter.models.gerar_referencia_opaca`).
    A única coisa que precisa é ser distinta linha a linha, porque o índice é
    `unique` — e é por isso que esta etapa existe antes de a constraint entrar.
    """
    InscricaoNewsletter = apps.get_model("newsletter", "InscricaoNewsletter")
    # Um por linha, em vez de um `default` chamável no `AddField`: o Django
    # chamaria o default UMA vez e todas as linhas nasceriam iguais.
    for inscricao in InscricaoNewsletter.objects.all().order_by("pk").iterator():
        inscricao.referencia_opaca = secrets.token_urlsafe(18)
        inscricao.save(update_fields=["referencia_opaca"])


class Migration(migrations.Migration):

    dependencies = [
        ("newsletter", "0002_inscricaonewsletter_periodo"),
    ]

    operations = [
        # 1. O vínculo deixa de ser obrigatório. `SET_NULL` (e não `CASCADE`)
        #    para o registro do consentimento não morrer com a conta.
        migrations.AlterField(
            model_name="inscricaonewsletter",
            name="user",
            field=models.OneToOneField(
                blank=True,
                help_text=(
                    "NULL após o descadastro: o registro do consentimento é "
                    "preservado, mas já não aponta para uma pessoa identificável."
                ),
                null=True,
                on_delete=models.SET_NULL,
                related_name="inscricao_newsletter",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        # 2. As datas.
        migrations.AddField(
            model_name="inscricaonewsletter",
            name="consentimento_aceito_em",
            field=models.DateTimeField(
                blank=True,
                help_text="Quando o titular concedeu o consentimento da newsletter.",
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="inscricaonewsletter",
            name="consentimento_revogado_em",
            field=models.DateTimeField(
                blank=True,
                help_text="Quando o consentimento foi revogado. NULL = não revogado.",
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="inscricaonewsletter",
            name="anonimizado_em",
            field=models.DateTimeField(
                blank=True,
                help_text="Quando o vínculo com a pessoa foi cortado (vínculo → NULL).",
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="inscricaonewsletter",
            name="versao_consentimento",
            field=models.CharField(
                blank=True,
                default="",
                help_text=(
                    "Versão do texto de consentimento da newsletter. Vazio enquanto "
                    "não houver texto próprio versionado (ver "
                    "NEWSLETTER_VERSAO_CONSENTIMENTO)."
                ),
                max_length=32,
            ),
        ),
        # 3. A referência opaca, em duas etapas — ver a nota do RunPython.
        migrations.AddField(
            model_name="inscricaonewsletter",
            name="referencia_opaca",
            field=models.CharField(
                blank=True,
                default="",
                editable=False,
                help_text="Identificador opaco e aleatório, não derivado do titular.",
                max_length=64,
                null=True,
            ),
        ),
        migrations.RunPython(_preencher_referencia_opaca, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="inscricaonewsletter",
            name="referencia_opaca",
            field=models.CharField(
                default=newsletter.models.gerar_referencia_opaca,
                editable=False,
                help_text="Identificador opaco e aleatório, não derivado do titular.",
                max_length=64,
                unique=True,
            ),
        ),
    ]
