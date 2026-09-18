"""FRENTE 3 — tabelas de sinais (busca/interações) + overrides editoriais.

Nenhum dado de negócio duplicado aqui: métricas são agregações sobre
InteracaoNoticia/EventoBusca, calculadas em feed/recomendacao.py.
"""

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("catalogo_noticias", "0006_newsitem_autoria_tags"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="EventoBusca",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("query", models.CharField(max_length=300)),
                ("query_normalizada", models.CharField(db_index=True, max_length=300)),
                ("session_key", models.CharField(blank=True, max_length=64)),
                ("resultados", models.PositiveIntegerField(default=0)),
                ("filtros", models.JSONField(blank=True, default=dict)),
                ("criado_em", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("user", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="buscas", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "verbose_name": "evento de busca",
                "verbose_name_plural": "eventos de busca",
                "ordering": ["-criado_em"],
                "indexes": [models.Index(fields=["query_normalizada", "-criado_em"], name="feed_evento_query_n_8f7c1a_idx")],
            },
        ),
        migrations.CreateModel(
            name="InteracaoNoticia",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("session_key", models.CharField(blank=True, max_length=64)),
                ("tipo", models.CharField(choices=[("view", "Visualização"), ("click", "Clique"), ("read", "Leitura com tempo"), ("save", "Salvo"), ("unsave", "Removido dos salvos"), ("share", "Compartilhado"), ("search_click", "Clique em resultado de busca")], db_index=True, max_length=20)),
                ("entry_tipo", models.CharField(help_text="'cluster' ou 'item'", max_length=10)),
                ("categoria", models.CharField(blank=True, db_index=True, max_length=100)),
                ("tempo_leitura_seg", models.PositiveIntegerField(default=0)),
                ("query", models.CharField(blank=True, help_text="Query de origem quando tipo=search_click", max_length=300)),
                ("criado_em", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("cluster", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="interacoes", to="catalogo_noticias.newscluster")),
                ("item", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="interacoes", to="catalogo_noticias.newsitem")),
                ("user", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="interacoes_noticia", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "verbose_name": "interação com notícia",
                "verbose_name_plural": "interações com notícias",
                "ordering": ["-criado_em"],
                "indexes": [
                    models.Index(fields=["entry_tipo", "cluster", "-criado_em"], name="feed_inter_entry__c2c1f9_idx"),
                    models.Index(fields=["entry_tipo", "item", "-criado_em"], name="feed_inter_entry__9a4b2e_idx"),
                    models.Index(fields=["tipo", "-criado_em"], name="feed_inter_tipo_6d3a2f_idx"),
                ],
            },
        ),
        migrations.CreateModel(
            name="DestaqueEditorial",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("tipo", models.CharField(choices=[("destaque", "Destaque do Dia (override manual)"), ("manchete", "Manchete fixa no topo"), ("bloqueio", "Bloqueio (não exibir)")], db_index=True, max_length=20)),
                ("entry_tipo", models.CharField(help_text="'cluster' ou 'item'", max_length=10)),
                ("posicao", models.PositiveIntegerField(default=0, help_text="Ordena manchetes entre si (menor primeiro)")),
                ("ativo", models.BooleanField(db_index=True, default=True)),
                ("inicio", models.DateTimeField(blank=True, null=True)),
                ("fim", models.DateTimeField(blank=True, null=True)),
                ("motivo", models.CharField(blank=True, max_length=300)),
                ("criado_em", models.DateTimeField(auto_now_add=True)),
                ("cluster", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="destaques_editoriais", to="catalogo_noticias.newscluster")),
                ("item", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="destaques_editoriais", to="catalogo_noticias.newsitem")),
            ],
            options={
                "verbose_name": "override editorial",
                "verbose_name_plural": "overrides editoriais",
                "ordering": ["posicao", "-criado_em"],
            },
        ),
    ]
