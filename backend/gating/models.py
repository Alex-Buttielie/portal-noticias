from django.conf import settings
from django.db import models


class FeatureLimit(models.Model):
    """
    Camada central e parametrizável de controle de acesso Free x Premium
    (BRD seção 7; implementation-contract.md run
    20260902-1420-gating-free-premium). Cada linha define o valor de UM
    recurso para UM plano — editável via Django admin, nunca hardcoded em
    código de negócio de outros módulos (ver `services.has_feature`).

    `valor` é armazenado como string livre, interpretado pelo chamador
    (booleano "true"/"false", número, etc.) — flexibilidade deliberada para
    não precisar de um schema por tipo de recurso.
    """

    PLANO_FREE = "free"
    PLANO_PREMIUM = "premium"
    PLANO_CHOICES = [
        (PLANO_FREE, "Free"),
        (PLANO_PREMIUM, "Premium"),
    ]

    chave = models.CharField(max_length=100)
    plano = models.CharField(max_length=20, choices=PLANO_CHOICES)
    valor = models.CharField(max_length=200)
    descricao = models.TextField(blank=True)

    atualizado_em = models.DateTimeField(auto_now=True)
    atualizado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )

    class Meta:
        verbose_name = "limite de recurso (Free x Premium)"
        verbose_name_plural = "limites de recurso (Free x Premium)"
        unique_together = [("chave", "plano")]
        ordering = ["chave", "plano"]

    def __str__(self):
        return f"{self.chave} ({self.plano}) = {self.valor}"


class FeatureLimitAlteracaoLog(models.Model):
    """
    Auditoria (BRD seção 17; implementation-contract.md, critério de aceite
    6) de toda alteração de `FeatureLimit` — append-only, nunca editado/
    apagado via admin (ver `admin.py`). Não usa FK para `FeatureLimit`
    propositalmente: o log deve sobreviver mesmo que a linha de
    `FeatureLimit` original seja apagada no futuro.
    """

    feature_limit_chave = models.CharField(max_length=100)
    plano = models.CharField(max_length=20)
    valor_anterior = models.CharField(max_length=200, blank=True)
    valor_novo = models.CharField(max_length=200)

    alterado_em = models.DateTimeField(auto_now_add=True)
    alterado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )

    class Meta:
        verbose_name = "log de alteração de limite de recurso"
        verbose_name_plural = "logs de alteração de limite de recurso"
        ordering = ["-alterado_em"]

    def __str__(self):
        return f"{self.feature_limit_chave} ({self.plano}): {self.valor_anterior!r} -> {self.valor_novo!r}"
