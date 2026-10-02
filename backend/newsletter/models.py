import secrets

from django.conf import settings
from django.db import models


def gerar_token() -> str:
    return secrets.token_urlsafe(32)


def gerar_referencia_opaca() -> str:
    """Identificador opaco, ALEATÓRIO e não derivado de nada do titular.

    Por que NÃO é um hash do e-mail
    ===============================
    A instrução original deste item pedia "substituir o endereço por um hash
    determinístico com sal, ou por um identificador opaco", e a segunda opção
    é a que existe aqui. A primeira foi **descartada de propósito**, e a razão
    é a mesma que a pessoa que pediu o item nomeou: um hash determinístico de
    um endereço de e-mail é reidentificável.

    E-mail não é segredo de alta entropia: o espaço é enumerável, e quem tem a
    linha e o sal (que moram lado a lado no banco) testa uma lista de candidatos
    e confere. Isso é PSEUDONIMIZAÇÃO, e pseudonimização é o oposto do que a
    LGPD pede aqui. Um identificador **aleatório** não carrega nenhuma
    informação sobre o endereço: não há função do identificador de volta para
    o e-mail, e não há o que testar.

    E o que ele NÃO é: um hash do e-mail com outro nome, nem uma chave de
    pesquisa, nem nada que ligue este registro a alguém.
    """
    return secrets.token_urlsafe(18)


class InscricaoNewsletter(models.Model):
    TIPO_PADRAO = "padrao"
    TIPO_CATEGORIA = "categoria"
    TIPO_PERSONALIZADA = "personalizada"
    TIPO_CHOICES = [
        (TIPO_PADRAO, "Padrão"),
        (TIPO_CATEGORIA, "Por categoria"),
        (TIPO_PERSONALIZADA, "Personalizada (Premium)"),
    ]

    # BRD seção 27 lista "Resumo da manhã" e "Resumo da noite" como opções
    # de newsletter distintas de "por categoria"/"personalizada" — dimensão
    # ORTOGONAL a `tipo` (um usuário escolhe TIPO de conteúdo e PERÍODO de
    # envio independentemente, ex.: "por categoria" + "noite"). Gap real
    # encontrado na análise do BRD: só existia 1 envio agendado a cada 12h
    # (sem horário fixo, sem relação com manhã/noite de verdade), sem opção
    # nenhuma para o usuário escolher.
    PERIODO_MANHA = "manha"
    PERIODO_NOITE = "noite"
    PERIODO_CHOICES = [
        (PERIODO_MANHA, "Manhã"),
        (PERIODO_NOITE, "Noite"),
    ]

    # A RETENÇÃO APÓS O DESCADASTRO (ver `newsletter/services.py`)
    # ===========================================================
    # `user` é NULLABLE e `on_delete=SET_NULL` por um motivo que é o coração
    # deste item: **este modelo nunca guardou o endereço de e-mail.** O que
    # guardava era o VÍNCULO com a linha que o guarda — `identidade.User`,
    # onde `email` é `unique=True` e é o `USERNAME_FIELD`
    # (`identidade/models.py:36,86`). Enquanto o vínculo existe, o endereço é
    # recuperável com um JOIN, e "anonimizar a newsletter" seria uma
    # description que não corresponde a nada.
    #
    # Então a anonimização aqui é CORTAR O VÍNCULO: no descadastro, `user` vira
    # NULL e a linha sobrevive como **prova** do consentimento e da revogação,
    # sem apontar para pessoa nenhuma. Uma nova inscrição é uma NOVA linha, com
    # a sua própria data de concessão — que é o modelo correto: cada ato de
    # consentimento é um registro próprio e imutável, e não uma linha que
    # liga e desliga.
    #
    # `SET_NULL` (e não `CASCADE`) para o registro de consentimento não ser
    # destruído junto com a conta. `CASCADE` apagaria a prova do consentimento
    # e da revogação no momento em que a conta é deletada — que é o erro
    # oposto ao que este item fecha.
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="inscricao_newsletter",
        help_text=(
            "NULL após o descadastro: o registro do consentimento é preservado, "
            "mas já não aponta para uma pessoa identificável."
        ),
    )
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES, default=TIPO_PADRAO)
    periodo = models.CharField(max_length=10, choices=PERIODO_CHOICES, default=PERIODO_MANHA)
    categorias = models.JSONField(default=list, blank=True)
    ativa = models.BooleanField(default=True)
    token_descadastro = models.CharField(max_length=64, unique=True, default=gerar_token)

    # -------------------------------------------------------------------------
    # O ESTADO PENDENTE DA CONFIRMAÇÃO (double opt-in)
    # -------------------------------------------------------------------------
    # `ativa` NÃO pode continuar significando "pode receber". Com o double
    # opt-in, uma inscrição recién-criada é ATIVA e mesmo assim NÃO pode receber
    # nada: está esperando o clique. Colocar `ativa=True` nesse estado e esperar
    # que o filtro de envio cuide disso seria um furo silencioso — o filtro é
    # de LEITURA, e qualquer tela futura que liste `ativa=True` trataria a
    # pessoa como inscrita antes de ela ter confirmado (o mesmo defeito que a
    # Pendência 1 do P1-06 registra em `services.py:5-10`).
    #
    # Por isso a linha nasce `ativa=False` e só fica `ativa=True` no clique.
    # `ativa=False` deixa de ser ambíguo: ou a pessoa revogou, ou a pendência
    # expirou — e as duas coisas continuam datadas em
    # `consentimento_revogado_em`/`pendencia_expirada_em`.
    #
    # `token_confirmacao` é o segredo do par de tokens de CONFIRMAÇÃO. É uma
    # coluna separada de `token_descadastro` pelo mesmo motivo que
    # `newsletter/tokens.py` usa salts diferentes para os dois propósitos: um
    # link não pode abrir o outro. Se compartilhassem o segredo, o link de
    # descadastro do último resumo entregue confirmaria a inscrição — e o
    # contrário também.
    #
    # A rotação é feita NO USO, no mesmo `UPDATE` que confirma, pelo mesmo
    # motivo do descadastro (`services.descadastrar_por_token`): o segredo
    # ANTIGO vai no filtro e o NOVO no `set`, o que torna a operação atômica e
    # o token de uso único.
    token_confirmacao = models.CharField(
        max_length=64,
        unique=True,
        default=gerar_token,
        editable=False,
        help_text="Segredo do token de confirmação. Nunca sai do banco.",
    )
    #: Quando a pendência foi criada. É o que a expiração conta, e não
    #: `criado_em`: `criado_em` é `auto_now_add` e dataria a LINHA, que numa
    #: reinscrição é a mesma de antes.
    confirmacao_solicitada_em = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Quando o link de confirmação foi enviado para esta inscrição.",
    )
    #: Quando a pessoa confirmou. NULL = pendente.
    confirmado_em = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Quando a pessoa confirmou a inscrição pelo link do e-mail. NULL = pendente.",
    )
    #: Quando a pendência EXPIROU sem confirmação. NULL = não expirou.
    #:
    #: Registrado em vez de derivado de `confirmacao_solicitada_em` +
    #: janela, porque a expiração é um FATO que precisa continuar verificável
    #: depois: `criado_em`/`confirmacao_solicitada_em` dizem quando o link saiu,
    #: e a partir do momento em que a pendência expira esse link nunca mais
    #: confirma — que é o mesmo raciocínio de primeira classe que motivou
    #: `consentimento_revogado_em` no P1-06.
    pendencia_expirada_em = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Quando a pendência expirou sem confirmação. NULL = não expirou.",
    )

    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    # -------------------------------------------------------------------------
    # O REGISTRO DATADO DO CONSENTIMENTO (Pendência jurídica do P1-06, 1 e 2)
    # -------------------------------------------------------------------------
    # Antes these campos não existiam, e o que havia era `ativa=False` +
    # `atualizado_em` (auto_now) como PROXY da data da revogação. Proxy se
    # perde: qualquer reescrita posterior da inscrição move `atualizado_em`, e
    # a data em que a pessoa revogou deixa de existir. A LGPD (art. 8º, V e
    # art. 18) exige que a revogação seja registrada de forma que continue
    # verificável depois.
    #
    # `consentimento_aceito_em` e `consentimento_revogado_em` são as duas datas
    # de primeira classe. Juntas com `ativa` e `anonimizado_em`, o registro
    # responde, sozinho e sem nenhum dado pessoal: houve consentimento? quando?
    # foi revogado? quando? o vínculo com a pessoa foi cortado, e quando?
    consentimento_aceito_em = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Quando o titular concedeu o consentimento da newsletter.",
    )
    consentimento_revogado_em = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Quando o consentimento foi revogado. NULL = não revogado.",
    )
    #: Quando o vínculo com a pessoa identificável foi cortado. É a data que um
    #: encarregado de dados pede para provar a minimização.
    anonimizado_em = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Quando o vínculo com a pessoa foi cortado (vínculo → NULL).",
    )
    #: Versão do texto de consentimento DA NEWSLETTER. Distinta de
    #: `User.consentimento_versao_termos`, que data o aceite dos Termos no
    #: cadastro — outra finalidade (ver o docstring de `services.py`).
    #:
    #: O default é VAZIO de propósito: ainda não existe texto de consentimento
    #: próprio da newsletter, e escrever "1.0" aqui seria fabricar um
    #: artefato jurídico. A pendência aberta está registrada em
    #: `newsletter/tests/test_p1_06_bordas_e_pendencia.py`, e o campo já existe
    #: para que a decisão versionada só precise gravar o valor.
    versao_consentimento = models.CharField(
        max_length=32,
        blank=True,
        default="",
        help_text=(
            "Versão do texto de consentimento da newsletter. Vazio enquanto não "
            "houver texto próprio versionado (ver NEWSLETTER_VERSAO_CONSENTIMENTO)."
        ),
    )
    #: Substitui o vínculo com a pessoa depois do descadastro. Ver
    #: `gerar_referencia_opaca` — aleatório, não derivado do endereço.
    referencia_opaca = models.CharField(
        max_length=64,
        unique=True,
        default=gerar_referencia_opaca,
        editable=False,
        help_text="Identificador opaco e aleatório, não derivado do titular.",
    )

    class Meta:
        verbose_name = "inscrição de newsletter"
        verbose_name_plural = "inscrições de newsletter"
        indexes = [
            # Índice do filtro de ENVIO. `enviar_newsletters` roda por job e a
            # consulta é sempre a mesma: `ativa=True AND user IS NOT NULL AND
            # confirmado_em IS NOT NULL`. Com índice, o job não faz seq scan de
            # uma tabela que só cresce — e a ausência de índice aqui não é
            # estética: a lista de pendentes cresce junto com a base.
            models.Index(
                fields=["ativa", "confirmado_em"],
                name="newsletter_ativa_confi_idx",
            ),
            # Índice da VARREDURA DE PENDÊNCIAS: `ativa=False AND
            # confirmado_em IS NULL`. É o que faz a expiração não varrer a
            # tabela inteira a cada execução.
            models.Index(
                fields=["confirmado_em", "pendencia_expirada_em"],
                name="newsletter_confi_expi_idx",
            ),
        ]

    def __str__(self):
        titular = self.user_id if self.user_id is not None else "anonimizada"
        return f"Newsletter de {titular} ({self.tipo}, {self.estado()})"

    # -------------------------------------------------------------------------
    # OS TRÊS ESTADOS, e onde cada um VIVE
    # -------------------------------------------------------------------------
    #
    #   | estado    | ativa | confirmado_em | consentimento_aceito_em | pendencia_expirada_em |
    #   |-----------|-------|---------------|-------------------------|-----------------------|
    #   | PENDENTE  | Falso | NULL          | NULL                    | NULL                  |
    #   | CONFIRMADA| True  | com data      | com data                | NULL                  |
    #   | REJEITADA | Falso | NULL          | NULL                    | com data              |
    #
    # `REJEITADA` cobre os dois motivos pelos quais a linha deixa de poder
    # receber sem ter recebido jamais: revogação (`consentimento_revogado_em`)
    # e expiração da pendência (`pendencia_expirada_em`). Os dois são
    # distinguíveis pelos campos datados, e é essa distinção que um encarregado
    # de dados precisa para responder "por que esta pessoa não recebe mais?".
    #
    # Deliberadamente NÃO há coluna `estado` com `choices`. Um `CharField`
    # permite "pendente" e "confirmada" coexistirem em uma linha sem regra que
    # impeça a combinação impossível (`estado='confirmada'` com
    # `confirmado_em=None`), e essa combinação é exatamente o bug que alguém
    # introduziria daqui a seis meses. Os campos de primeira classe não ficam
    # inconsistentes: cada um responde UMA pergunta factual.
    #
    # Por que `consentimento_aceito_em` é NULL no estado pendente, e não gravado
    # no POST: o P1-06 grava nele "quando o titular CONCEDEU o consentimento".
    # Com double opt-in, no POST a pessoa ainda não concedeu nada — ela pediu.
    # Gravar a data ali seria declarar um consentimento que não aconteceu, e é
    # o mesmo erro que `newsletter/tokens.py` documenta sobre `atualizado_em`:
    # um campo que parece responder a uma pergunta e responde a outra. A data
    # da concessão passa a ser a do clique.
    def estado(self) -> str:
        """`pendente` | `confirmada` | `rejeitada` — derivado, nunca gravado."""
        if self.confirmado_em is not None:
            return "confirmada"
        if self.consentimento_revogado_em is not None or self.pendencia_expirada_em is not None:
            return "rejeitada"
        if self.ativa:
            return "confirmada"
        return "pendente"

    @property
    def pode_receber(self) -> bool:
        """Se esta linha pode entrar no envio — a definição de uma linha.

        Deliberadamente um método derivado dos campos, e não um campo: um
        `BooleanField` calculado pode divergir dos campos de primeira classe e
        ninguém nota. A pergunta tem três partes e as três são verificáveis.
        """
        return bool(
            self.ativa
            and self.confirmado_em is not None
            and self.consentimento_aceito_em is not None
            and self.user_id is not None
        )


class EnvioNewsletter(models.Model):
    """Log de execuções da task periódica (auditoria/observabilidade, mesmo padrão de RegistroExecucaoIngestao)."""

    executado_em = models.DateTimeField(auto_now_add=True)
    total_inscricoes_processadas = models.PositiveIntegerField(default=0)
    total_enviados = models.PositiveIntegerField(default=0)
    total_falhas = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = "envio de newsletter"
        verbose_name_plural = "envios de newsletter"
        ordering = ["-executado_em"]

    def __str__(self):
        return f"Envio {self.executado_em:%Y-%m-%d %H:%M} — {self.total_enviados} enviados"
