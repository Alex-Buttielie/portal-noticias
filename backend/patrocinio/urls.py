from django.urls import path

from . import views

app_name = "patrocinio"

urlpatterns = [
    path("ativo/", views.PatrocinioAtivoView.as_view(), name="ativo"),
]
