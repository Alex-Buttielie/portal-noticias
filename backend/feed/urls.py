from django.urls import path

from . import views

app_name = "feed"

urlpatterns = [
    path("", views.FeedListView.as_view(), name="feed-list"),
    path("urgentes/", views.UrgentesView.as_view(), name="feed-urgentes"),
    path("mais-lidas/", views.MaisLidasView.as_view(), name="feed-mais-lidas"),
    path("cluster/<int:cluster_id>/", views.ClusterDetailView.as_view(), name="feed-cluster-detail"),
    path("item/<int:item_id>/", views.ItemDetailView.as_view(), name="feed-item-detail"),
]
