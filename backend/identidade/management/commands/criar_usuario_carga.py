"""
Carga de usuário inicial (ex.: dono/admin em produção).

Cria ou atualiza um usuário com senha inicial e `deve_trocar_senha=True`,
forçando a troca no primeiro login (`POST /api/auth/trocar-senha/`).

Uso (na VPS, via compose):
    docker compose --env-file .env.production exec web python manage.py \\
        criar_usuario_carga --email buttielle3@gmail.com --superuser
    # a senha é lida de PROD_SEED_PASSWORD (nunca via argumento/terminal
    # com histórico) ou digitada interativamente.

Variáveis de ambiente:
    PROD_SEED_EMAIL / PROD_SEED_PASSWORD — valores padrão quando os
    argumentos --email/--password não são passados.
"""

from __future__ import annotations

import getpass
import os

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError

User = get_user_model()


class Command(BaseCommand):
    help = "Cria/atualiza usuário de carga com troca de senha obrigatória no primeiro login."

    def add_arguments(self, parser):
        parser.add_argument("--email", default=os.environ.get("PROD_SEED_EMAIL", ""))
        parser.add_argument(
            "--password",
            default=os.environ.get("PROD_SEED_PASSWORD", ""),
            help="Senha inicial (prefira PROD_SEED_PASSWORD; será pedida interativamente se vazia).",
        )
        parser.add_argument("--nome", default="")
        parser.add_argument(
            "--superuser",
            action="store_true",
            help="Torna staff+superuser (acesso ao /admin e à Central).",
        )
        parser.add_argument(
            "--papel",
            default="admin",
            choices=["free", "premium", "admin"],
            help="Papel no portal (default: admin).",
        )

    def handle(self, *args, **options):
        email = (options["email"] or "").strip()
        if not email:
            raise CommandError("Informe --email ou PROD_SEED_EMAIL.")
        email = User.objects.normalize_email(email)
        password = options["password"] or ""
        if not password:
            password = getpass.getpass("Senha inicial: ")
        try:
            validate_password(password)
        except ValidationError as exc:
            raise CommandError(f"Senha inicial inválida: {'; '.join(exc.messages)}")

        user, criado = User.objects.get_or_create(
            email__iexact=email,
            defaults={"email": email},
        )
        user.email = email
        if options["nome"]:
            user.nome = options["nome"]
        user.papel = options["papel"]
        user.is_active = True
        user.email_verificado = True
        user.deve_trocar_senha = True
        if options["superuser"]:
            user.is_staff = True
            user.is_superuser = True
        user.set_password(password)
        user.save()
        # Tokens antigos não valem nada com a senha nova.
        from rest_framework.authtoken.models import Token

        Token.objects.filter(user=user).delete()

        acao = "criado" if criado else "atualizado"
        self.stdout.write(
            self.style.SUCCESS(
                f"Usuário {email} {acao} (papel={user.papel}, "
                f"superuser={user.is_superuser}) — troca de senha exigida no primeiro login."
            )
        )
