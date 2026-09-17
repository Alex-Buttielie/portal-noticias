from django.urls import path

from . import views

app_name = "gating"

urlpatterns = [
    path("meus-recursos/", views.MeusRecursosView.as_view(), name="meus-recursos"),
    path("status/", views.StatusSistemaView.as_view(), name="status-sistema"),
]
