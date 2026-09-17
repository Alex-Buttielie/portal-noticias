"""FRENTE 6 — migration da `RegraCuradoria` (controles editoriais amplos)."""

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("painel_admin", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="RegraCuradoria",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "tipo",
                    models.CharField(
                        choices=[
                            ("boost_entrada", "Boost de entrada"),
                            ("bloqueio_entrada", "Bloqueio de entrada"),
                            ("boost_categoria", "Boost de categoria"),
                            ("bloqueio_categoria", "Bloqueio de categoria"),
                            ("ordem_categorias", "Ordem fixa de categorias"),
                            ("colunista_destaque", "Colunista em destaque"),
                            ("selo_forcado", "Selo forçado"),
                            ("urgente_forcado", "Urgente forçado"),
                            ("exclusivo_forcado", "Exclusivo forçado"),
                        ],
                        db_index=True,
                        max_length=30,
                    ),
                ),
                ("entry_tipo", models.CharField(blank=True, help_text="'cluster' ou 'item' (só tipos por entrada)", max_length=10)),
                ("entry_id", models.PositiveIntegerField(blank=True, null=True)),
                ("alvo", models.CharField(blank=True, help_text="Categoria, autor, selo ou lista de categorias", max_length=300)),
                ("ordem", models.PositiveIntegerField(default=0, help_text="Menor primeiro (boosts/manchetes extras)")),
                ("ativo", models.BooleanField(db_index=True, default=True)),
                ("inicio", models.DateTimeField(blank=True, null=True)),
                ("fim", models.DateTimeField(blank=True, null=True)),
                ("motivo", models.CharField(blank=True, max_length=300)),
                ("criado_em", models.DateTimeField(auto_now_add=True)),
                ("atualizado_em", models.DateTimeField(auto_now=True)),
                (
                    "criado_por",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="+",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "regra de curadoria",
                "verbose_name_plural": "regras de curadoria",
                "ordering": ["ordem", "-criado_em"],
            },
        ),
    ]
