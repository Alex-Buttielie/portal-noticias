from django.conf import settings
from django.db import models


class AuditoriaAdmin(models.Model):
    acao = models.CharField(max_length=100)
    alvo_tipo = models.CharField(max_length=100)
    alvo_id = models.CharField(max_length=100)
    detalhe = models.JSONField(default=dict, blank=True)
    alterado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "auditoria admin"
        verbose_name_plural = "auditorias admin"
        ordering = ["-criado_em"]

    def __str__(self):
        return f"{self.acao} {self.alvo_tipo}#{self.alvo_id}"
