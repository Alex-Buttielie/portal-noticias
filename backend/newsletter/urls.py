from django.urls import path

from . import views

app_name = "newsletter"

urlpatterns = [
    path("inscrever/", views.InscreverView.as_view(), name="inscrever"),
    path("descadastrar/", views.DescadastrarView.as_view(), name="descadastrar"),
    # Double opt-in. Rota NOVA, e o nome segue o mesmo padrão dos outros dois
    # (`newsletter.<verbo>`). O `config/urls.py:38` monta o app inteiro em
    # `/api/newsletter/`, então o caminho público é `/api/newsletter/confirmar/`
    # — e é esse caminho que `lib/api.ts::confirmarInscricaoNewsletter` chama.
    path("confirmar/", views.ConfirmarView.as_view(), name="confirmar"),
]
