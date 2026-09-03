from django.urls import path

from . import views

app_name = "identidade"

urlpatterns = [
    path("auth/cadastro/", views.CadastroView.as_view(), name="cadastro"),
    path("auth/verificar-email/", views.VerificarEmailView.as_view(), name="verificar-email"),
    path("auth/google/", views.GoogleLoginView.as_view(), name="google-login"),
    path("auth/login/", views.LoginView.as_view(), name="login"),
    path("auth/logout/", views.LogoutView.as_view(), name="logout"),
    path("auth/recuperar-senha/", views.RecuperarSenhaView.as_view(), name="recuperar-senha"),
    path("auth/redefinir-senha/", views.RedefinirSenhaView.as_view(), name="redefinir-senha"),
    path("onboarding/", views.OnboardingView.as_view(), name="onboarding"),
    path("preferencias-cookies/", views.PreferenciasCookiesView.as_view(), name="preferencias-cookies"),
]
