from django.urls import path

from . import views

app_name = "moderacao"

urlpatterns = [
    path("fila/", views.FilaModeracaoView.as_view(), name="fila"),
    path("denuncias/<int:denuncia_id>/resolver/", views.ResolverDenunciaView.as_view(), name="resolver-denuncia"),
    path("acoes/", views.AplicarAcaoView.as_view(), name="aplicar-acao"),
    path("acoes/<int:acao_id>/recurso/", views.CriarRecursoView.as_view(), name="criar-recurso"),
    path("paginas/<slug:slug>/", views.PaginaEditorialView.as_view(), name="pagina-editorial"),
    path("minha-reputacao/", views.MinhaReputacaoView.as_view(), name="minha-reputacao"),
]
