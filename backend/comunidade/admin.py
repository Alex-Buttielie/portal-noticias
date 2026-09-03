from django.contrib import admin

from .models import Comentario, Publicacao, Seguidor


@admin.register(Publicacao)
class PublicacaoAdmin(admin.ModelAdmin):
    list_display = ("titulo", "autor", "tipo", "status", "destaque", "publicado_em")
    list_filter = ("tipo", "status", "destaque")
    search_fields = ("titulo", "autor__email")


@admin.register(Comentario)
class ComentarioAdmin(admin.ModelAdmin):
    list_display = ("autor", "publicacao", "news_item", "resposta_de", "criado_em")
    search_fields = ("autor__email",)


@admin.register(Seguidor)
class SeguidorAdmin(admin.ModelAdmin):
    list_display = ("seguidor", "autor", "criado_em")
