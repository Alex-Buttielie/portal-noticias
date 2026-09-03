from django.urls import path

from . import views

app_name = "b2b"

urlpatterns = [
    path("criterios/", views.CriteriosView.as_view(), name="criterios"),
    path("itens-monitorados/", views.ItensMonitoradosView.as_view(), name="itens-monitorados"),
    path("resumo-executivo/", views.ResumoExecutivoView.as_view(), name="resumo-executivo"),
    path("membros/", views.MembrosView.as_view(), name="membros"),
]
