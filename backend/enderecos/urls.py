from django.urls import path

from . import views

app_name = "enderecos"

urlpatterns = [
    path("cep/<str:cep>/", views.CepView.as_view(), name="cep"),
    path("busca/", views.BuscaEnderecoView.as_view(), name="busca"),
    path("estados/", views.EstadosView.as_view(), name="estados"),
    path("estados/<str:uf>/municipios/", views.MunicipiosView.as_view(), name="municipios"),
    path("reverso/", views.ReversoView.as_view(), name="reverso"),
    path("por-ip/", views.PorIpView.as_view(), name="por-ip"),
]
