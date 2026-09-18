from django.apps import AppConfig


class EnderecosConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "enderecos"
    verbose_name = "Endereços inteligentes (proxy ViaCEP/IBGE)"
