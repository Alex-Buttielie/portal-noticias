from django.contrib import admin

from .models import Patrocinio


@admin.register(Patrocinio)
class PatrocinioAdmin(admin.ModelAdmin):
    """Cadastro do patrocínio: anunciante, criativo, URL, posição, período, ativo."""

    list_display = ("anunciante", "posicao", "data_inicio", "data_fim", "ativo", "atualizado_em")
    list_filter = ("ativo", "posicao")
    search_fields = ("anunciante", "posicao")
    date_hierarchy = "data_inicio"
