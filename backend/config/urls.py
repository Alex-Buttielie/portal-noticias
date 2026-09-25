"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
"""
from django.contrib import admin
from django.urls import include, path

from config.observability_views import health_detail, livez, metrics_view, readyz
from config.views import healthz

urlpatterns = [
    # --- Observabilidade (run 20260925-1020-observabilidade) -----------------
    # Rotas na raiz (sem barra final) porque é assim que o Docker HEALTHCHECK,
    # o Nginx, o Alloy e o Better Stack chamam; o `APPEND_SLASH` do
    # CommonMiddleware redireciona `/livez/` -> `/livez` para quem digitar a
    # barra. `healthz` (abaixo) é o endpoint legado e foi mantido: o
    # `HEALTHCHECK` do docker-compose e o monitor externo já apontam para ele.
    path("livez", livez, name="livez"),
    path("readyz", readyz, name="readyz"),
    path("health-detail", health_detail, name="health-detail"),
    path("metrics", metrics_view, name="metrics"),
    # -----------------------------------------------------------------------
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
    path("api/b2b/", include("b2b.urls")),
    path("api/metricas/", include("metricas.urls")),
    path("api/admin/", include("painel_admin.urls")),
    path("api/admin/robos/", include("catalogo_noticias.robos_urls")),
]
