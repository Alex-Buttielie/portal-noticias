from django.contrib import admin

from .models import InscricaoListaEspera


@admin.register(InscricaoListaEspera)
class InscricaoListaEsperaAdmin(admin.ModelAdmin):
    """Critério de aceite 3 — segmentação via filtro/busca do próprio admin."""

    list_display = ("email", "nome", "localidade", "criado_em")
    search_fields = ("email", "nome", "localidade")
    list_filter = ("localidade",)
