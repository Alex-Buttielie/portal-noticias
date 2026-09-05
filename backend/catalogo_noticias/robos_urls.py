from django.urls import path

from . import robos_views

urlpatterns = [
    path("fontes/", robos_views.FontesRoboView.as_view(), name="robos-fontes"),
    path("fontes/<int:pk>/", robos_views.FonteRoboDetailView.as_view(), name="robos-fonte-detail"),
    path("config/", robos_views.ConfigRoboView.as_view(), name="robos-config"),
    path("execucoes/", robos_views.ExecucoesRoboView.as_view(), name="robos-execucoes"),
    path("executar/", robos_views.ExecutarRoboView.as_view(), name="robos-executar"),
]
