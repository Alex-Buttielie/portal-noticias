from django.db import models
from django.utils import timezone


class InscricaoListaEspera(models.Model):
    """BRD §26 — cadastro de interesse antes/durante o lançamento."""

    nome = models.CharField(max_length=150)
    email = models.EmailField(unique=True)
    interesses = models.JSONField(default=list, blank=True)
    localidade = models.CharField(max_length=150, blank=True)
    canal_preferido = models.CharField(max_length=20, blank=True)
    consentimento_aceito_em = models.DateTimeField()

    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "inscrição na lista de espera"
        verbose_name_plural = "inscrições na lista de espera"
        ordering = ["criado_em"]

    def __str__(self):
        return f"{self.email} ({self.criado_em:%Y-%m-%d})"

    @classmethod
    def inscrever(cls, *, nome, email, interesses=None, localidade="", canal_preferido="", aceite=False):
        if not aceite:
            raise ValueError("Consentimento de comunicação é obrigatório.")
        obj, criado = cls.objects.get_or_create(
            email=cls.normalizar_email(email),
            defaults={
                "nome": nome,
                "interesses": interesses or [],
                "localidade": localidade,
                "canal_preferido": canal_preferido,
                "consentimento_aceito_em": timezone.now(),
            },
        )
        return obj, criado

    @staticmethod
    def normalizar_email(email: str) -> str:
        return email.strip().lower()
