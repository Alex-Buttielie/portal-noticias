from django.conf import settings
from django.db import models


class Plan(models.Model):
    """
    Plano de assinatura (BRD §6; implementation-contract.md run
    20260902-1426-assinatura-premium, critério de aceite 1) — preço e
    duração totalmente editáveis pelo admin, nunca hardcoded em código de
    negócio. `duracao_dias` (não um enum fechado "semestral"/"anual") para
    permitir qualquer periodicidade sem alteração de código.
    """

    nome = models.CharField(max_length=100)
    preco = models.DecimalField(max_digits=10, decimal_places=2)
    duracao_dias = models.PositiveIntegerField()
    ativo = models.BooleanField(default=True)

    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "plano"
        verbose_name_plural = "planos"
        ordering = ["preco"]

    def __str__(self):
        return f"{self.nome} (R${self.preco} / {self.duracao_dias} dias)"


class Subscription(models.Model):
    """
    Assinatura de um usuário (ARCHITECTURE.md seção 3; BRD §9 — os 7 estados
    abaixo são exatamente os do BRD, nenhum estado adicional deve ser
    introduzido). `plan` usa `on_delete=PROTECT`: um `Plan` com assinaturas
    associadas não pode ser apagado (só desativado via `ativo=False`) — evita
    perder o vínculo histórico de qual plano um usuário assinou.

    `preco_cobrado`/`duracao_dias_no_momento` CONGELAM o valor do `Plan` no
    momento da assinatura (critério de aceite técnico, "Restrições
    técnicas") — mudar o preço do `Plan` depois não retroage sobre
    assinaturas já criadas.
    """

    STATUS_TESTE = "teste"
    STATUS_ATIVA = "ativa"
    STATUS_PAGAMENTO_PENDENTE = "pagamento_pendente"
    STATUS_INADIMPLENTE = "inadimplente"
    STATUS_CANCELADA = "cancelada"
    STATUS_EXPIRADA = "expirada"
    STATUS_ENCERRADA = "encerrada"
    STATUS_CHOICES = [
        (STATUS_TESTE, "Teste"),
        (STATUS_ATIVA, "Ativa"),
        (STATUS_PAGAMENTO_PENDENTE, "Pagamento pendente"),
        (STATUS_INADIMPLENTE, "Inadimplente"),
        (STATUS_CANCELADA, "Cancelada"),
        (STATUS_EXPIRADA, "Expirada"),
        (STATUS_ENCERRADA, "Encerrada"),
    ]

    # Estados em que o usuário deve ter acesso Premium (User.papel=premium)
    # — ver services._sincronizar_papel_usuario e a property
    # `deveria_ter_acesso_premium` abaixo. `cancelada` continua aqui
    # deliberadamente: o usuário já pagou o período corrente e mantém acesso
    # até `vencimento` (task-plan.md, "Suposições assumidas" — não é uma
    # prática de retenção abusiva, é o oposto: não cortar o que já foi pago).
    #
    # `inadimplente` (grace period) NÃO entra neste conjunto simples — ver
    # `deveria_ter_acesso_premium`, que trata esse caso à parte. Bugs reais
    # encontrados por execução de teste real, dois cenários que pareciam a
    # mesma regra mas são opostos:
    # 1. `test_pagamento_recusado_nao_derruba_acesso_premium_ja_ativo`:
    #    assinatura JÁ ATIVA (pagamento aprovado antes) cujo pagamento de
    #    RENOVAÇÃO é recusado depois — critério de aceite 4, grace period,
    #    acesso Premium NÃO cai na hora.
    # 2. `test_assinar_com_gateway_recusando_nao_promove_usuario_mas_inicia_grace_period`:
    #    assinatura NOVA cujo PRIMEIRO pagamento já é recusado (nunca esteve
    #    ativa) — o usuário nunca teve acesso Premium de verdade, então não
    #    pode "manter" um acesso que nunca existiu, mesmo caindo em
    #    `inadimplente` com um grace period.
    # Incluir `inadimplente` incondicionalmente aqui resolvia o cenário 1 mas
    # quebrava o 2 (usuário ganhava Premium de graça só por o primeiro
    # pagamento cair em grace period). O sinal que distingue os dois casos é
    # `inicio`: só é preenchido por `processar_confirmacao_pagamento` — uma
    # assinatura que nunca foi aprovada tem `inicio=None`.
    STATUS_COM_ACESSO_PREMIUM = {STATUS_TESTE, STATUS_ATIVA, STATUS_CANCELADA}

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="assinaturas"
    )
    plan = models.ForeignKey(Plan, on_delete=models.PROTECT, related_name="assinaturas")

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PAGAMENTO_PENDENTE)

    preco_cobrado = models.DecimalField(max_digits=10, decimal_places=2)
    duracao_dias_no_momento = models.PositiveIntegerField()

    inicio = models.DateTimeField(null=True, blank=True)
    vencimento = models.DateTimeField(null=True, blank=True)

    renovacao_automatica = models.BooleanField(default=True)
    grace_period_termina_em = models.DateTimeField(null=True, blank=True)

    gateway_referencia = models.CharField(max_length=200, blank=True)

    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "assinatura"
        verbose_name_plural = "assinaturas"
        ordering = ["-criado_em"]
        constraints = [
            # Achado de revisão de segurança (major): a checagem de
            # "usuário já tem assinatura em andamento" em
            # services.assinar_plano era check-then-act sem lock nem
            # constraint de banco — com um gateway de pagamento real
            # (confirmação assíncrona/com latência de rede, ao contrário do
            # ManualPaymentGatewayProvider atual), duas requisições quase
            # simultâneas (duplo clique, replay de rede) podiam passar pela
            # checagem antes de qualquer uma criar sua Subscription,
            # resultando em duas assinaturas ativas e duas cobranças para o
            # mesmo usuário. Esta constraint garante a regra no nível do
            # banco, não só na aplicação — a única defesa que não depende de
            # nenhuma janela de tempo entre checar e agir. Valores literais
            # (não as constantes STATUS_*) porque `Meta` é uma classe aninhada
            # e não enxerga o namespace de `Subscription` por nome simples.
            models.UniqueConstraint(
                fields=["user"],
                condition=models.Q(status__in=["teste", "ativa", "pagamento_pendente"]),
                name="assinatura_uma_em_andamento_por_usuario",
            ),
        ]

    def __str__(self):
        return f"Assinatura de {self.user} — {self.plan.nome} ({self.status})"

    @property
    def deveria_ter_acesso_premium(self) -> bool:
        if self.status in self.STATUS_COM_ACESSO_PREMIUM:
            return True
        if self.status == self.STATUS_INADIMPLENTE:
            # Grace period: só preserva acesso Premium se a assinatura JÁ
            # esteve ativa antes (tinha algo a preservar) — ver comentário
            # detalhado acima de STATUS_COM_ACESSO_PREMIUM.
            return self.inicio is not None
        return False


class HistoricoPagamento(models.Model):
    """Histórico de pagamentos visível ao usuário (spec, requisito funcional 9)."""

    STATUS_APROVADO = "aprovado"
    STATUS_RECUSADO = "recusado"
    STATUS_PENDENTE = "pendente"
    STATUS_ESTORNADO = "estornado"
    STATUS_CHOICES = [
        (STATUS_APROVADO, "Aprovado"),
        (STATUS_RECUSADO, "Recusado"),
        (STATUS_PENDENTE, "Pendente"),
        (STATUS_ESTORNADO, "Estornado"),
    ]

    subscription = models.ForeignKey(Subscription, on_delete=models.CASCADE, related_name="pagamentos")
    valor = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    referencia_gateway = models.CharField(max_length=200, blank=True)

    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "pagamento"
        verbose_name_plural = "histórico de pagamentos"
        ordering = ["-criado_em"]

    def __str__(self):
        return f"Pagamento {self.status} — R${self.valor} ({self.subscription})"


class AssinaturaMudancaEstadoLog(models.Model):
    """
    Auditoria de TODA transição de estado de `Subscription` (spec, requisito
    não-funcional: "decisões financeiras não podem ser silenciosas") — ver
    `services._registrar_mudanca_estado`, chamado em toda transição.
    """

    subscription = models.ForeignKey(
        Subscription, on_delete=models.CASCADE, related_name="mudancas_de_estado"
    )
    estado_anterior = models.CharField(max_length=20, blank=True)
    estado_novo = models.CharField(max_length=20)
    motivo = models.CharField(max_length=300)

    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "log de mudança de estado de assinatura"
        verbose_name_plural = "logs de mudança de estado de assinatura"
        ordering = ["-criado_em"]

    def __str__(self):
        return f"{self.subscription_id}: {self.estado_anterior} -> {self.estado_novo}"


class ConfiguracaoAssinatura(models.Model):
    """
    Configuração administrativa global do módulo (spec, requisito funcional
    6 e 10) — singleton (sempre `pk=1`, ver `services.obter_configuracao`).
    Grace period e período de teste editáveis pelo admin, sem alteração de
    código/deploy.
    """

    grace_period_dias = models.PositiveIntegerField(default=7)
    periodo_teste_dias = models.PositiveIntegerField(default=0)
    periodo_teste_ativo = models.BooleanField(default=False)

    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "configuração de assinatura"
        verbose_name_plural = "configuração de assinatura"

    def __str__(self):
        return "Configuração de Assinatura"

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)
