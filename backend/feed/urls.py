from django.urls import path

from . import views

app_name = "feed"

urlpatterns = [
    path("", views.FeedListView.as_view(), name="feed-list"),
    path("urgentes/", views.UrgentesView.as_view(), name="feed-urgentes"),
    path("mais-lidas/", views.MaisLidasView.as_view(), name="feed-mais-lidas"),
    path("sitemap/", views.SitemapView.as_view(), name="feed-sitemap"),
    # FRENTE 3 — recomendação / destaques / busca / cobertura / interações.
    path("home/", views.HomeSecoesView.as_view(), name="feed-home"),
    path("destaques/", views.DestaquesDiaView.as_view(), name="feed-destaques"),
    path("busca/", views.BuscaView.as_view(), name="feed-busca"),
    path("busca/autocomplete/", views.BuscaAutocompleteView.as_view(), name="feed-busca-autocomplete"),
    path("busca/populares/", views.BuscaPopularesView.as_view(), name="feed-busca-populares"),
    path("busca/historico/", views.BuscaHistoricoView.as_view(), name="feed-busca-historico"),
    path("cobertura/<str:tipo>/<int:entrada_id>/", views.CoberturaCompletaView.as_view(), name="feed-cobertura"),
    path("interacoes/", views.InteracaoView.as_view(), name="feed-interacoes"),
    path("afinidade/", views.AfinidadeView.as_view(), name="feed-afinidade"),
    path("fontes-seguidas/", views.FontesSeguidasView.as_view(), name="feed-fontes-seguidas"),
    path("cluster/<int:cluster_id>/", views.ClusterDetailView.as_view(), name="feed-cluster-detail"),
    path("item/<int:item_id>/", views.ItemDetailView.as_view(), name="feed-item-detail"),
]
