from django.contrib import admin

from .models import LocalidadeSalva


@admin.register(LocalidadeSalva)
class LocalidadeSalvaAdmin(admin.ModelAdmin):
    list_display = ("user", "pais", "estado", "cidade", "criado_em")
