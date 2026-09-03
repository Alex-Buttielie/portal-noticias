from django.contrib import admin

from .models import FeatureLimit, FeatureLimitAlteracaoLog


@admin.register(FeatureLimit)
class FeatureLimitAdmin(admin.ModelAdmin):
    list_display = ("chave", "plano", "valor", "atualizado_em", "atualizado_por")
    list_filter = ("plano",)
    search_fields = ("chave", "descricao")

    def save_model(self, request, obj, form, change):
        """
        Critério de aceite 2/6 (implementation-contract.md run
        20260902-1420-gating-free-premium): toda alteração de `FeatureLimit`
        pelo admin gera um `FeatureLimitAlteracaoLog` com quem alterou,
        quando, e o valor antes/depois — captura o valor ANTERIOR do banco
        (não do form) antes de salvar, para não confiar em nenhum estado em
        memória que possa estar desatualizado.
        """
        valor_anterior = ""
        if change:
            try:
                valor_anterior = FeatureLimit.objects.get(pk=obj.pk).valor
            except FeatureLimit.DoesNotExist:
                valor_anterior = ""

        obj.atualizado_por = request.user
        super().save_model(request, obj, form, change)

        FeatureLimitAlteracaoLog.objects.create(
            feature_limit_chave=obj.chave,
            plano=obj.plano,
            valor_anterior=valor_anterior,
            valor_novo=obj.valor,
            alterado_por=request.user,
        )


@admin.register(FeatureLimitAlteracaoLog)
class FeatureLimitAlteracaoLogAdmin(admin.ModelAdmin):
    """
    Somente leitura por definição (é um log de auditoria, não um dado
    operacional comum) — sem permissão de adicionar/editar/apagar via admin;
    só é criado programaticamente por `FeatureLimitAdmin.save_model`.
    """

    list_display = ("feature_limit_chave", "plano", "valor_anterior", "valor_novo", "alterado_em", "alterado_por")
    list_filter = ("plano",)
    search_fields = ("feature_limit_chave",)
    readonly_fields = [f.name for f in FeatureLimitAlteracaoLog._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
