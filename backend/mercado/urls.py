from django.urls import path

from . import views

app_name = "mercado"

urlpatterns = [
    path("indices/", views.IndicesView.as_view(), name="indices"),
]
