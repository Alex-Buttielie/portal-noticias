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
    path("api/newsletter/", include("newsletter.urls")),
    path("api/landing/", include("landing.urls")),
    path("api/b2b/", include("b2b.urls")),
    path("api/metricas/", include("metricas.urls")),
]
