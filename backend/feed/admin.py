from django.contrib import admin

from .models import DestaqueEditorial, EventoBusca, InteracaoNoticia


@admin.register(EventoBusca)
class EventoBuscaAdmin(admin.ModelAdmin):
    list_display = ("query", "resultados", "user", "criado_em")
    list_filter = ("criado_em",)
    search_fields = ("query", "query_normalizada")
    readonly_fields = ("criado_em",)


@admin.register(InteracaoNoticia)
class InteracaoNoticiaAdmin(admin.ModelAdmin):
    list_display = ("tipo", "entry_tipo", "cluster", "item", "categoria", "criado_em")
    list_filter = ("tipo", "entry_tipo", "criado_em")
    readonly_fields = ("criado_em",)


@admin.register(DestaqueEditorial)
class DestaqueEditorialAdmin(admin.ModelAdmin):
    list_display = ("tipo", "entry_tipo", "cluster", "item", "posicao", "ativo", "inicio", "fim")
    list_filter = ("tipo", "ativo")
    ordering = ("posicao", "-criado_em")
