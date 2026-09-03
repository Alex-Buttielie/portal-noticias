from django.urls import path

from . import views

app_name = "comunidade"

urlpatterns = [
    path("publicacoes/", views.PublicacoesListCreateView.as_view(), name="publicacoes"),
    path("publicacoes/<int:publicacao_id>/", views.PublicacaoDetailView.as_view(), name="publicacao-detail"),
    path(
        "publicacoes/<int:publicacao_id>/enviar/",
        views.EnviarPublicacaoView.as_view(),
        name="publicacao-enviar",
    ),
    path("comentarios/", views.ComentariosListCreateView.as_view(), name="comentarios"),
    path("autores/<int:autor_id>/seguir/", views.SeguirAutorView.as_view(), name="seguir-autor"),
    path("autores/<int:autor_id>/perfil/", views.PerfilAutorPublicoView.as_view(), name="perfil-autor"),
    path("denunciar/", views.DenunciarView.as_view(), name="denunciar"),
]
