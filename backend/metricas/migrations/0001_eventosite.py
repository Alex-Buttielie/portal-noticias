"""FRENTE 6 — migration inicial do app `metricas` (modelo `EventoSite`)."""

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="EventoSite",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("sessao", models.CharField(blank=True, db_index=True, max_length=64)),
                (
                    "tipo",
                    models.CharField(
                        choices=[
                            ("page_view", "Visualização de página"),
                            ("category_view", "Visualização de categoria/editoria"),
                            ("category_click", "Clique em categoria/editoria"),
                            ("author_view", "Visualização de autor"),
                            ("columnist_view", "Visualização de colunista"),
                            ("radar_view", "Visualização do radar"),
                            ("location_permission", "Permissão de localização"),
                            ("location_selected", "Região selecionada"),
                            ("home_section_view", "Visualização de seção da Home"),
                            ("home_section_click", "Clique em seção da Home"),
                            ("community_view", "Visualização da comunidade"),
                            ("community_interaction", "Interação na comunidade"),
                        ],
                        db_index=True,
                        max_length=30,
                    ),
                ),
                ("path", models.CharField(blank=True, max_length=500)),
                ("categoria", models.CharField(blank=True, db_index=True, max_length=100)),
                ("autor_ref", models.CharField(blank=True, max_length=200)),
                ("secao_home", models.CharField(blank=True, db_index=True, max_length=60)),
                (
                    "origem",
                    models.CharField(
                        blank=True,
                        choices=[
                            ("busca", "Busca"),
                            ("social", "Social"),
                            ("direto", "Direto"),
                            ("referencia", "Referência"),
                            ("campanha", "Campanha"),
                        ],
                        db_index=True,
                        max_length=20,
                    ),
                ),
                ("dispositivo", models.CharField(blank=True, db_index=True, max_length=20)),
                ("pais", models.CharField(blank=True, max_length=100)),
                ("estado", models.CharField(blank=True, max_length=100)),
                ("cidade", models.CharField(blank=True, max_length=150)),
                ("regiao", models.CharField(blank=True, max_length=150)),
                ("tempo_permanencia_seg", models.PositiveIntegerField(default=0)),
                ("scroll_max_pct", models.PositiveIntegerField(default=0)),
                ("extra", models.JSONField(blank=True, default=dict)),
                ("criado_em", models.DateTimeField(auto_now_add=True, db_index=True)),
                (
                    "user",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="eventos_site",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "evento do site",
                "verbose_name_plural": "eventos do site",
                "ordering": ["-criado_em"],
                "indexes": [
                    models.Index(fields=["tipo", "-criado_em"], name="metricas_ev_tipo_criado_idx"),
                    models.Index(fields=["sessao", "-criado_em"], name="metricas_ev_sessao_criado_idx"),
                    models.Index(fields=["categoria", "-criado_em"], name="metricas_ev_categ_criado_idx"),
                ],
            },
        ),
    ]
