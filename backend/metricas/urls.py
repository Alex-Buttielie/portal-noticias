from django.urls import path

from . import views

app_name = "metricas"

urlpatterns = [
    path("painel/", views.PainelMetricasView.as_view(), name="painel"),
    # FRENTE 6 — Central de Inteligência (ingestão pública + painel admin).
    path("eventos/", views.EventoIngestaoView.as_view(), name="eventos"),
    path("inteligencia/", views.CentralInteligenciaView.as_view(), name="inteligencia"),
]
