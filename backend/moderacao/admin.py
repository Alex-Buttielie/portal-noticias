from django.contrib import admin

from .models import (
    AcaoModeracao,
    Denuncia,
    PaginaEditorial,
    RecursoModeracao,
    Reputacao,
    ReputacaoEventoLog,
)


@admin.register(Denuncia)
class DenunciaAdmin(admin.ModelAdmin):
    list_display = ("id", "denunciante", "motivo", "status", "content_type", "object_id", "criado_em")
    list_filter = ("status", "motivo")


@admin.register(AcaoModeracao)
class AcaoModeracaoAdmin(admin.ModelAdmin):
    list_display = ("usuario_alvo", "tipo", "aplicado_por", "ativo_ate", "criado_em")
    list_filter = ("tipo",)


@admin.register(RecursoModeracao)
class RecursoModeracaoAdmin(admin.ModelAdmin):
    list_display = ("usuario", "acao", "status", "criado_em")
    list_filter = ("status",)


@admin.register(Reputacao)
class ReputacaoAdmin(admin.ModelAdmin):
    list_display = ("user", "pontuacao", "nivel", "atualizado_em")


@admin.register(ReputacaoEventoLog)
class ReputacaoEventoLogAdmin(admin.ModelAdmin):
    list_display = ("user", "delta", "motivo", "criado_em")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(PaginaEditorial)
class PaginaEditorialAdmin(admin.ModelAdmin):
    list_display = ("slug", "titulo", "atualizado_em")
