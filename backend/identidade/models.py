from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.db import models
from django.utils import timezone

from .managers import UserManager


class User(AbstractBaseUser, PermissionsMixin):
    """
    Usuário do Portal de Notícias (módulo identidade/).

    Campos macro definidos em ARCHITECTURE.md seção 3 (`User`) e seção 4
    (papéis/permissões). Este recorte (`implementation-contract.md` desta
    execução) só implementa o comportamento do papel `free`; `premium` e
    `admin` existem como valores possíveis do campo `papel` (compartilhado
    por módulos futuros: assinatura/gating), mas nenhuma lógica de permissão
    para eles é construída aqui.
    """

    PAPEL_FREE = "free"
    PAPEL_PREMIUM = "premium"
    PAPEL_ADMIN = "admin"
    PAPEL_CHOICES = [
        (PAPEL_FREE, "Free"),
        (PAPEL_PREMIUM, "Premium"),
        (PAPEL_ADMIN, "Admin"),
    ]

    CANAL_EMAIL = "email"
    CANAL_PUSH = "push"
    CANAL_CHOICES = [
        (CANAL_EMAIL, "E-mail"),
        (CANAL_PUSH, "Push"),
    ]

    email = models.EmailField(unique=True)
    nome = models.CharField(max_length=150, blank=True)

    papel = models.CharField(max_length=20, choices=PAPEL_CHOICES, default=PAPEL_FREE)

    email_verificado = models.BooleanField(default=False)

    # Onboarding (ARCHITECTURE.md seção 3: "preferências de onboarding —
    # interesses, localidade, canal preferido"). Persistido diretamente no
    # User por ser um conjunto pequeno e 1:1 com o usuário; ver
    # implementation-history.md para o racional dessa escolha.
    interesses = models.JSONField(default=list, blank=True)
    localidade = models.CharField(max_length=150, blank=True)
    canal_preferido = models.CharField(max_length=20, choices=CANAL_CHOICES, blank=True)
    onboarding_concluido = models.BooleanField(default=False)
    onboarding_pulado = models.BooleanField(default=False)
    onboarding_atualizado_em = models.DateTimeField(null=True, blank=True)

    # Consentimento LGPD — auditável (BRD/ARCHITECTURE.md seção 7).
    consentimento_aceito_em = models.DateTimeField(null=True, blank=True)
    consentimento_versao_termos = models.CharField(max_length=20, blank=True)

    # Preferências de cookies (implementation-contract.md run
    # 20260903-1134-seo-lgpd-design-system, escopo B — LGPD). Categoria
    # "essenciais" não é armazenada aqui porque nunca é opcional (sempre
    # ativa, não é uma escolha do usuário). Persistido apenas para usuário
    # AUTENTICADO — visitante anônimo usa só localStorage no frontend (ver
    # `frontend/lib/cookie-consent.ts`); isto aqui é o espelho server-side
    # usado quando o usuário está logado (ex.: para manter a preferência ao
    # trocar de dispositivo). Lacuna de backend encontrada e corrigida nesta
    # run: não existia nenhum campo/endpoint para isso antes.
    preferencias_cookies = models.JSONField(
        default=dict,
        blank=True,
        help_text="Ex.: {'analytics': false, 'personalizacao': false}. Chave 'essenciais' nunca é armazenada aqui (sempre ativa).",
    )
    preferencias_cookies_atualizado_em = models.DateTimeField(null=True, blank=True)

    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(default=timezone.now)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    class Meta:
        verbose_name = "usuário"
        verbose_name_plural = "usuários"

    def __str__(self):
        return self.email

    @property
    def onboarding_pendente(self):
        """
        True quando o onboarding ainda não foi concluído nem pulado, ou
        quando foi pulado e deve ser reapresentado (critério de aceite 9 do
        implementation-contract.md: pular não perde a informação de que o
        onboarding deve ser reapresentado depois).
        """
        return not self.onboarding_concluido
