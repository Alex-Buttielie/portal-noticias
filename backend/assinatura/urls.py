from django.urls import path

from . import views

app_name = "assinatura"

urlpatterns = [
    path("planos/", views.PlanosListView.as_view(), name="planos"),
    path("assinar/", views.AssinarView.as_view(), name="assinar"),
    path("cancelar/", views.CancelarView.as_view(), name="cancelar"),
    path("minha/", views.MinhaAssinaturaView.as_view(), name="minha"),
    path("historico-pagamentos/", views.HistoricoPagamentosView.as_view(), name="historico-pagamentos"),
]
