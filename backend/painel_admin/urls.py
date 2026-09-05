from django.urls import path

from . import views

urlpatterns = [
    path("usuarios/", views.UsuarioListView.as_view(), name="admin-usuarios-list"),
    path("usuarios/<int:user_id>/", views.UsuarioDetailView.as_view(), name="admin-usuarios-detail"),
    path("fila/", views.FilaListView.as_view(), name="admin-fila-list"),
    path("fila/<int:item_id>/decisao/", views.FilaDecisaoView.as_view(), name="admin-fila-decisao"),
    path("planos/", views.PlanListCreateView.as_view(), name="admin-planos-list"),
    path("planos/<int:plan_id>/", views.PlanDetailView.as_view(), name="admin-planos-detail"),
    path("limites/", views.LimiteListView.as_view(), name="admin-limites-list"),
    path("limites/<int:limite_id>/", views.LimiteDetailView.as_view(), name="admin-limites-detail"),
    path("assinaturas/", views.AssinaturaListView.as_view(), name="admin-assinaturas-list"),
    path("assinaturas/<int:assinatura_id>/", views.AssinaturaDetailView.as_view(), name="admin-assinaturas-detail"),
    path("moderacao/denuncias/", views.DenunciaListView.as_view(), name="admin-denuncias-list"),
    path("moderacao/denuncias/<int:denuncia_id>/acao/", views.DenunciaAcaoView.as_view(), name="admin-denuncias-acao"),
]
