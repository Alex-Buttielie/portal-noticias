from django.contrib import admin

from .models import CriterioMonitoramento, MembroOrganizacao, Organizacao


class MembroOrganizacaoInline(admin.TabularInline):
    model = MembroOrganizacao
    extra = 0


class CriterioMonitoramentoInline(admin.TabularInline):
    model = CriterioMonitoramento
    extra = 0


@admin.register(Organizacao)
class OrganizacaoAdmin(admin.ModelAdmin):
    list_display = ("nome", "plano", "ativo", "criado_em")
    list_filter = ("plano", "ativo")
    inlines = [MembroOrganizacaoInline, CriterioMonitoramentoInline]


@admin.register(MembroOrganizacao)
class MembroOrganizacaoAdmin(admin.ModelAdmin):
    list_display = ("user", "organizacao", "papel_na_organizacao")
