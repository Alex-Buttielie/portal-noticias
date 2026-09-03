from django.conf import settings
from django.db import models


class Organizacao(models.Model):
    PLANO_BASIC = "basic"
    PLANO_PRO = "pro"
    PLANO_ENTERPRISE = "enterprise"
    PLANO_CHOICES = [(PLANO_BASIC, "Basic"), (PLANO_PRO, "Pro"), (PLANO_ENTERPRISE, "Enterprise")]

    nome = models.CharField(max_length=200)
    plano = models.CharField(max_length=20, choices=PLANO_CHOICES, default=PLANO_BASIC)
    ativo = models.BooleanField(default=True)
    # Reaproveita a assinatura já existente (BRD §20) — não duplica cobrança.
    assinatura = models.ForeignKey(
        "assinatura.Subscription", null=True, blank=True, on_delete=models.SET_NULL, related_name="organizacao_b2b"
    )
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "organização"
        verbose_name_plural = "organizações"

    def __str__(self):
        return self.nome


class MembroOrganizacao(models.Model):
    PAPEL_ADMIN = "admin_organizacao"
    PAPEL_MEMBRO = "membro"
    PAPEL_CHOICES = [(PAPEL_ADMIN, "Administrador da organização"), (PAPEL_MEMBRO, "Membro")]

    organizacao = models.ForeignKey(Organizacao, on_delete=models.CASCADE, related_name="membros")
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="membro_b2b")
    papel_na_organizacao = models.CharField(max_length=20, choices=PAPEL_CHOICES, default=PAPEL_MEMBRO)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "membro de organização"
        verbose_name_plural = "membros de organização"

    def __str__(self):
        return f"{self.user_id} em {self.organizacao_id} ({self.papel_na_organizacao})"


class CriterioMonitoramento(models.Model):
    TIPO_EMPRESA = "empresa"
    TIPO_CONCORRENTE = "concorrente"
    TIPO_SETOR = "setor"
    TIPO_PALAVRA_CHAVE = "palavra_chave"
    TIPO_CHOICES = [
        (TIPO_EMPRESA, "Empresa"),
        (TIPO_CONCORRENTE, "Concorrente"),
        (TIPO_SETOR, "Setor"),
        (TIPO_PALAVRA_CHAVE, "Palavra-chave"),
    ]

    organizacao = models.ForeignKey(Organizacao, on_delete=models.CASCADE, related_name="criterios")
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES)
    valor = models.CharField(max_length=200)
    ativo = models.BooleanField(default=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    # BRD §19 — "Alertas" é um item explícito do produto B2B. Gap real
    # encontrado na análise do BRD: nenhum mecanismo de alerta existia —
    # `services.verificar_e_enviar_alertas` usa este campo para só alertar
    # sobre itens ingeridos DEPOIS do último alerta (nunca reenvia o mesmo
    # item duas vezes); `null` significa "nunca alertado", cobre desde a
    # criação do critério.
    ultimo_alerta_em = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "critério de monitoramento"
        verbose_name_plural = "critérios de monitoramento"

    def __str__(self):
        return f"{self.organizacao_id}: {self.tipo}={self.valor}"
