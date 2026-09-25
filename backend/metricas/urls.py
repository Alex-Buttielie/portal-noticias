from django.urls import path

from . import views

app_name = "metricas"

urlpatterns = [
    path("painel/", views.PainelMetricasView.as_view(), name="painel"),
    # FRENTE 6 — Central de Inteligência (ingestão pública + painel admin).
    path("eventos/", views.EventoIngestaoView.as_view(), name="eventos"),
    # Emissão do token de consentimento assinado (run 20260925-1020
    # -observabilidade, Bloco A2). O cliente o chama só depois do gesto de
    # consentimento e o envia no `POST /api/metricas/eventos/` (header
    # `X-Consent-Token` ou campo `consent_token`).
    path("consent/", views.ConsentimentoTokenView.as_view(), name="consent"),
    path("inteligencia/", views.CentralInteligenciaView.as_view(), name="inteligencia"),
]
