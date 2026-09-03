from django.urls import path

from . import views

app_name = "metricas"

urlpatterns = [
    path("painel/", views.PainelMetricasView.as_view(), name="painel"),
]
