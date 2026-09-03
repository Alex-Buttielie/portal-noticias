from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .models import User


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    ordering = ["email"]
    list_display = ["email", "nome", "papel", "email_verificado", "is_staff", "is_active"]
    list_filter = ["papel", "email_verificado", "is_staff", "is_active"]
    search_fields = ["email", "nome"]
    filter_horizontal = ("groups", "user_permissions")

    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Informações pessoais", {"fields": ("nome",)}),
        ("Papel e identidade", {"fields": ("papel", "email_verificado")}),
        (
            "Onboarding",
            {
                "fields": (
                    "interesses",
                    "localidade",
                    "canal_preferido",
                    "onboarding_concluido",
                    "onboarding_pulado",
                    "onboarding_atualizado_em",
                )
            },
        ),
        (
            "Consentimento (LGPD)",
            {"fields": ("consentimento_aceito_em", "consentimento_versao_termos")},
        ),
        (
            "Permissões",
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                )
            },
        ),
        ("Datas", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("email", "nome", "password1", "password2"),
            },
        ),
    )
    readonly_fields = ["date_joined", "onboarding_atualizado_em"]
