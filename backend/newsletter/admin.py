from django.contrib import admin

from .models import EnvioNewsletter, InscricaoNewsletter


@admin.register(InscricaoNewsletter)
class InscricaoNewsletterAdmin(admin.ModelAdmin):
    list_display = ("user", "tipo", "ativa", "criado_em")
    list_filter = ("tipo", "ativa")


@admin.register(EnvioNewsletter)
class EnvioNewsletterAdmin(admin.ModelAdmin):
    list_display = ("executado_em", "total_inscricoes_processadas", "total_enviados", "total_falhas")

    def has_add_permission(self, request):
        return False
