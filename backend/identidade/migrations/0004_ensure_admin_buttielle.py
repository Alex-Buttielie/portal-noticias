"""
Garante o administrador principal (dono) em todos os ambientes.

- Se buttielle3@gmail.com existir: promove a papel=admin, staff, superuser,
  ativo e e-mail verificado — SEM TOCAR na senha nem em deve_trocar_senha.
- Se não existir (banco novo de dev/homolog): cria com senha inutilizável
  (login só após `criar_usuario_carga` definir senha).

Idempotente e reversível sem efeito (nunca rebaixa ninguém no rollback).
"""

from django.db import migrations


def garantir_admin(apps, schema_editor):
    User = apps.get_model("identidade", "User")
    try:
        user = User.objects.get(email__iexact="buttielle3@gmail.com")
        user.papel = "admin"
        user.is_staff = True
        user.is_superuser = True
        user.is_active = True
        user.email_verificado = True
        user.save(
            update_fields=[
                "papel",
                "is_staff",
                "is_superuser",
                "is_active",
                "email_verificado",
            ]
        )
    except User.DoesNotExist:
        from django.contrib.auth.hashers import make_password

        user = User(
            email="buttielle3@gmail.com",
            # Senha inutilizável (model histórico não tem set_unusable_password):
            # login só após `criar_usuario_carga` definir senha real.
            password=make_password(None),
            papel="admin",
            is_staff=True,
            is_superuser=True,
            is_active=True,
            email_verificado=True,
        )
        user.save()


def reverso_sem_efeito(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("identidade", "0003_user_deve_trocar_senha"),
    ]

    operations = [
        migrations.RunPython(garantir_admin, reverso_sem_efeito),
    ]
