import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('catalogo_noticias', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Publicacao',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('titulo', models.CharField(max_length=300)),
                ('conteudo', models.TextField()),
                ('tipo', models.CharField(choices=[('opiniao', 'Opinião'), ('analise', 'Análise')], max_length=20)),
                ('status', models.CharField(choices=[('rascunho', 'Rascunho'), ('enviado', 'Enviado'), ('publicado', 'Publicado')], default='rascunho', max_length=20)),
                ('categoria', models.CharField(blank=True, max_length=100)),
                ('tags', models.JSONField(blank=True, default=list)),
                ('destaque', models.BooleanField(default=False)),
                ('criado_em', models.DateTimeField(auto_now_add=True)),
                ('atualizado_em', models.DateTimeField(auto_now=True)),
                ('publicado_em', models.DateTimeField(blank=True, null=True)),
                ('autor', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='publicacoes', to=settings.AUTH_USER_MODEL)),
                ('news_cluster', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='publicacoes', to='catalogo_noticias.newscluster')),
                ('news_item', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='publicacoes', to='catalogo_noticias.newsitem')),
            ],
            options={
                'verbose_name': 'publicação',
                'verbose_name_plural': 'publicações',
                'ordering': ['-criado_em'],
            },
        ),
        migrations.CreateModel(
            name='Seguidor',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('criado_em', models.DateTimeField(auto_now_add=True)),
                ('autor', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='seguidores', to=settings.AUTH_USER_MODEL)),
                ('seguidor', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='seguindo', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'seguidor',
                'verbose_name_plural': 'seguidores',
                'unique_together': {('seguidor', 'autor')},
            },
        ),
        migrations.CreateModel(
            name='Comentario',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('conteudo', models.TextField()),
                ('criado_em', models.DateTimeField(auto_now_add=True)),
                ('autor', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='comentarios', to=settings.AUTH_USER_MODEL)),
                ('news_item', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='comentarios', to='catalogo_noticias.newsitem')),
                ('publicacao', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='comentarios', to='comunidade.publicacao')),
                ('resposta_de', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='respostas', to='comunidade.comentario')),
            ],
            options={
                'verbose_name': 'comentário',
                'verbose_name_plural': 'comentários',
                'ordering': ['criado_em'],
            },
        ),
        migrations.AddConstraint(
            model_name='comentario',
            constraint=models.CheckConstraint(condition=models.Q(models.Q(('publicacao__isnull', False), ('news_item__isnull', True)), models.Q(('publicacao__isnull', True), ('news_item__isnull', False)), _connector='OR'), name='comentario_exatamente_um_alvo'),
        ),
    ]
