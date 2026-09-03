from django.contrib import admin

from .models import PerfilJornalista, SolicitacaoCredenciamento
from .services import decidir


@admin.register(SolicitacaoCredenciamento)
class SolicitacaoCredenciamentoAdmin(admin.ModelAdmin):
    """Fila administrativa (critério de aceite 2) — ordenada por data (Meta.ordering)."""

    list_display = ("user", "cidade", "uf", "status", "criado_em", "decidido_por")
    list_filter = ("status", "uf")
    search_fields = ("user__email", "cidade")
    readonly_fields = ("user", "criado_em", "decidido_em", "decidido_por")
    actions = ["aprovar_selecionadas", "reprovar_selecionadas"]

    @admin.action(description="Aprovar solicitações selecionadas")
    def aprovar_selecionadas(self, request, queryset):
        for solicitacao in queryset:
            decidir(
                solicitacao,
                request.user,
                SolicitacaoCredenciamento.STATUS_APROVADO,
                motivo="Aprovado via ação em massa do admin.",
            )

    @admin.action(description="Reprovar solicitações selecionadas")
    def reprovar_selecionadas(self, request, queryset):
        for solicitacao in queryset:
            decidir(
                solicitacao,
                request.user,
                SolicitacaoCredenciamento.STATUS_REPROVADO,
                motivo="Reprovado via ação em massa do admin.",
            )


@admin.register(PerfilJornalista)
class PerfilJornalistaAdmin(admin.ModelAdmin):
    list_display = ("user", "selo_ativo", "suspenso", "credenciado_em")
    list_filter = ("selo_ativo", "suspenso")
    search_fields = ("user__email",)
