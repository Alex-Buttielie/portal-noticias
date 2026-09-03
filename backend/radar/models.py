from django.conf import settings
from django.db import models


class LocalidadeSalva(models.Model):
    """Critério de aceite 5 — salvar/seguir localidade."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="localidades_salvas")
    pais = models.CharField(max_length=100, blank=True)
    estado = models.CharField(max_length=100, blank=True)
    cidade = models.CharField(max_length=150, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "localidade salva"
        verbose_name_plural = "localidades salvas"
        unique_together = [("user", "pais", "estado", "cidade")]

    def __str__(self):
        return f"{self.user_id}: {self.cidade or self.estado or self.pais or 'nacional'}"
