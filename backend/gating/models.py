from django.conf import settings
from django.db import models


def _invalidar_gating_best_effort():
    # Import tardio: `gating.services` importa este módulo.
    try:
        from .services import invalidar_cache_gating

        invalidar_cache_gating()
    except Exception:
        pass


class ConfiguracaoSistemaQuerySet(models.QuerySet):
    def delete(self):
        # `QuerySet.delete()` em lote NÃO chama `Model.delete()` — sem este
        # override, `filter(pk=1).delete()` deixaria o cache stale até o TTL.
        resultado = super().delete()
        _invalidar_gating_best_effort()
        return resultado


class FeatureLimit(models.Model):
    """
    Camada central e parametrizavel de controle de acesso Free x Premium
    (BRD secao 7; implementation-contract.md run
    20260902-1420-gating-free-premium). Cada linha define o valor de UM
    recurso para UM plano - editavel via Django admin, nunca hardcoded em
    codigo de negocio de outros modulos (ver `services.has_feature`).

    `valor` e armazenado como string livre, interpretado pelo chamador
    (booleano "true"/"false", numero, etc.) - flexibilidade deliberada para
    nao precisar de um schema por tipo de recurso.
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

    def _invalidar_cache_gating(self):
        # Import tardio: `gating.services` importa este módulo.
        try:
            from .services import invalidar_cache_gating

            invalidar_cache_gating()
        except Exception:
            pass

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self._invalidar_cache_gating()

    def delete(self, *args, **kwargs):
        super().delete(*args, **kwargs)
        self._invalidar_cache_gating()


class ConfiguracaoSistema(models.Model):
    """
    Chave geral do produto (singleton pk=1, ver `save()`): enquanto
    `premium_ativo` estiver DESMARCADO, todas as funcionalidades Premium ficam
    liberadas para todos os usuários e as assinaturas ficam pausadas — o
    produto opera como se todo mundo fosse Premium, sem cobrar ninguém
    (ver `gating/services.premium_liberado_geral`). Editável SOMENTE pela
    Central (`/admin/configuracoes`), nunca por endpoint público.
    """

    premium_ativo = models.BooleanField(
        default=False,
        help_text="Quando marcado, os planos Premium passam a valer e as funcionalidades voltam a ser limitadas por plano. Quando desmarcado, tudo fica liberado e assinar é pausado.",
    )
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "configuração do sistema"
        verbose_name_plural = "configuração do sistema"

    def __str__(self):
        return f"ConfiguracaoSistema (premium_ativo={self.premium_ativo})"

    objects = ConfiguracaoSistemaQuerySet.as_manager()

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)
        try:
            from .services import invalidar_cache_gating

            invalidar_cache_gating()
        except Exception:
            pass

    def delete(self, *args, **kwargs):
        super().delete(*args, **kwargs)
        try:
            from .services import invalidar_cache_gating

            invalidar_cache_gating()
        except Exception:
            pass


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
