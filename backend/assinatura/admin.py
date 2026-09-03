from django.contrib import admin

from .models import (
    AssinaturaMudancaEstadoLog,
    ConfiguracaoAssinatura,
    HistoricoPagamento,
    Plan,
    Subscription,
)


@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    """Critério de aceite 1: preço e duração editáveis aqui, sem alteração de código."""

    list_display = ("nome", "preco", "duracao_dias", "ativo", "atualizado_em")
    list_filter = ("ativo",)
    search_fields = ("nome",)


class HistoricoPagamentoInline(admin.TabularInline):
    model = HistoricoPagamento
    extra = 0
    can_delete = False
    readonly_fields = [f.name for f in HistoricoPagamento._meta.fields]

    def has_add_permission(self, request, obj=None):
        return False


class AssinaturaMudancaEstadoLogInline(admin.TabularInline):
    """Auditoria (critério de aceite 9) — visível na tela da assinatura, somente leitura."""

    model = AssinaturaMudancaEstadoLog
    extra = 0
    can_delete = False
    readonly_fields = [f.name for f in AssinaturaMudancaEstadoLog._meta.fields]

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ("user", "plan", "status", "inicio", "vencimento", "renovacao_automatica")
    list_filter = ("status", "plan")
    search_fields = ("user__email",)
    inlines = [HistoricoPagamentoInline, AssinaturaMudancaEstadoLogInline]
    # preco_cobrado/duracao_dias_no_momento são um "congelamento" histórico
    # (Restrições técnicas do implementation-contract.md) — não editáveis
    # depois de criados, para não distorcer o registro do que foi
    # efetivamente cobrado.
    readonly_fields = ("preco_cobrado", "duracao_dias_no_momento", "gateway_referencia")


@admin.register(ConfiguracaoAssinatura)
class ConfiguracaoAssinaturaAdmin(admin.ModelAdmin):
    """Singleton (critério de aceite 6/10 — grace period e período de teste editáveis)."""

    list_display = ("grace_period_dias", "periodo_teste_ativo", "periodo_teste_dias", "atualizado_em")

    def has_add_permission(self, request):
        return not ConfiguracaoAssinatura.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False
