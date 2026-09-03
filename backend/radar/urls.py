from django.urls import path

from . import views

app_name = "radar"

urlpatterns = [
    path("tendencias/", views.TendenciasView.as_view(), name="tendencias"),
    path("evolucao/", views.EvolucaoView.as_view(), name="evolucao"),
    path("localidades-salvas/", views.LocalidadesSalvasView.as_view(), name="localidades-salvas"),
]
