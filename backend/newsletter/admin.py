from django.contrib import admin

from .models import EnvioNewsletter, InscricaoNewsletter


@admin.register(InscricaoNewsletter)
class InscricaoNewsletterAdmin(admin.ModelAdmin):
    list_display = ("user", "tipo", "estado", "criado_em")
    list_filter = ("tipo", "ativa")

    @admin.display(description="estado")
    def estado(self, obj):
        # `estado()` é derivado e nunca gravado — ver `newsletter/models.py`. O
        # admin mostra o estado porque é a pergunta que o operador faz ("por que
        # esta pessoa não recebe?"), e as três respostas são distinguíveis por
        # três colunas datadas diferentes.
        return obj.estado()


@admin.register(EnvioNewsletter)
class EnvioNewsletterAdmin(admin.ModelAdmin):
    list_display = ("executado_em", "total_inscricoes_processadas", "total_enviados", "total_falhas")

    def has_add_permission(self, request):
        return False
