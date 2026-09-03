from django.urls import path

from . import views

app_name = "newsletter"

urlpatterns = [
    path("inscrever/", views.InscreverView.as_view(), name="inscrever"),
    path("descadastrar/", views.DescadastrarView.as_view(), name="descadastrar"),
]
