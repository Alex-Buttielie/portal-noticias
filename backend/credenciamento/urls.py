from django.urls import path

from . import views

app_name = "credenciamento"

urlpatterns = [
    path("solicitar/", views.SolicitarCredenciamentoView.as_view(), name="solicitar"),
    path("minha-solicitacao/", views.MinhaSolicitacaoView.as_view(), name="minha-solicitacao"),
    path(
        "solicitacoes/<int:solicitacao_id>/documento/",
        views.DocumentoView.as_view(),
        name="documento",
    ),
    path("meu-perfil/", views.MeuPerfilView.as_view(), name="meu-perfil"),
]
