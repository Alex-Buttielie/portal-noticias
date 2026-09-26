"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
"""
from django.contrib import admin
from django.urls import include, path

from config.views import healthz

urlpatterns = [
    path("healthz", healthz, name="healthz"),
    path("admin/", admin.site.urls),
    path("api/", include("identidade.urls")),
    path("api/feed/", include("feed.urls")),
    path("api/gating/", include("gating.urls")),
    path("api/assinatura/", include("assinatura.urls")),
    path("api/credenciamento/", include("credenciamento.urls")),
    path("api/comunidade/", include("comunidade.urls")),
    path("api/moderacao/", include("moderacao.urls")),
    path("api/radar/", include("radar.urls")),
    path("api/enderecos/", include("enderecos.urls")),
    path("api/newsletter/", include("newsletter.urls")),
    path("api/landing/", include("landing.urls")),
    # P1-15b — `POST /api/contato/`: entrega a mensagem do formulário de
    # contato por e-mail. Sem persistência e sem migration (justificativa em
    # `contato/services.py`); responde 503, nunca 2xx, enquanto o canal de
    # entrega real não estiver configurado.
    path("api/contato/", include("contato.urls")),
    path("api/b2b/", include("b2b.urls")),
    path("api/metricas/", include("metricas.urls")),
    path("api/admin/", include("painel_admin.urls")),
    path("api/admin/robos/", include("catalogo_noticias.robos_urls")),
]
