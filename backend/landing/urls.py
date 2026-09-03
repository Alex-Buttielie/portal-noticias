from django.urls import path

from . import views

app_name = "landing"

urlpatterns = [
    path("lista-espera/", views.ListaEsperaView.as_view(), name="lista-espera"),
]
