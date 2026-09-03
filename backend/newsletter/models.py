import secrets

from django.conf import settings
from django.db import models


def gerar_token() -> str:
    return secrets.token_urlsafe(32)


class InscricaoNewsletter(models.Model):
    TIPO_PADRAO = "padrao"
    TIPO_CATEGORIA = "categoria"
    TIPO_PERSONALIZADA = "personalizada"
    TIPO_CHOICES = [
        (TIPO_PADRAO, "Padrão"),
        (TIPO_CATEGORIA, "Por categoria"),
        (TIPO_PERSONALIZADA, "Personalizada (Premium)"),
    ]

    # BRD seção 27 lista "Resumo da manhã" e "Resumo da noite" como opções
    # de newsletter distintas de "por categoria"/"personalizada" — dimensão
    # ORTOGONAL a `tipo` (um usuário escolhe TIPO de conteúdo e PERÍODO de
    # envio independentemente, ex.: "por categoria" + "noite"). Gap real
    # encontrado na análise do BRD: só existia 1 envio agendado a cada 12h
    # (sem horário fixo, sem relação com manhã/noite de verdade), sem opção
    # nenhuma para o usuário escolher.
    PERIODO_MANHA = "manha"
    PERIODO_NOITE = "noite"
    PERIODO_CHOICES = [
        (PERIODO_MANHA, "Manhã"),
        (PERIODO_NOITE, "Noite"),
    ]

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="inscricao_newsletter")
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES, default=TIPO_PADRAO)
    periodo = models.CharField(max_length=10, choices=PERIODO_CHOICES, default=PERIODO_MANHA)
    categorias = models.JSONField(default=list, blank=True)
    ativa = models.BooleanField(default=True)
    token_descadastro = models.CharField(max_length=64, unique=True, default=gerar_token)

    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "inscrição de newsletter"
        verbose_name_plural = "inscrições de newsletter"

    def __str__(self):
        return f"Newsletter de {self.user_id} ({self.tipo}, {'ativa' if self.ativa else 'inativa'})"


class EnvioNewsletter(models.Model):
    """Log de execuções da task periódica (auditoria/observabilidade, mesmo padrão de RegistroExecucaoIngestao)."""

    executado_em = models.DateTimeField(auto_now_add=True)
    total_inscricoes_processadas = models.PositiveIntegerField(default=0)
    total_enviados = models.PositiveIntegerField(default=0)
    total_falhas = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = "envio de newsletter"
        verbose_name_plural = "envios de newsletter"
        ordering = ["-executado_em"]

    def __str__(self):
        return f"Envio {self.executado_em:%Y-%m-%d %H:%M} — {self.total_enviados} enviados"
