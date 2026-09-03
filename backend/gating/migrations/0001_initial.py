import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='FeatureLimit',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('chave', models.CharField(max_length=100)),
                ('plano', models.CharField(choices=[('free', 'Free'), ('premium', 'Premium')], max_length=20)),
                ('valor', models.CharField(max_length=200)),
                ('descricao', models.TextField(blank=True)),
                ('atualizado_em', models.DateTimeField(auto_now=True)),
                ('atualizado_por', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'limite de recurso (Free x Premium)',
                'verbose_name_plural': 'limites de recurso (Free x Premium)',
                'ordering': ['chave', 'plano'],
                'unique_together': {('chave', 'plano')},
            },
        ),
        migrations.CreateModel(
            name='FeatureLimitAlteracaoLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('feature_limit_chave', models.CharField(max_length=100)),
                ('plano', models.CharField(max_length=20)),
                ('valor_anterior', models.CharField(blank=True, max_length=200)),
                ('valor_novo', models.CharField(max_length=200)),
                ('alterado_em', models.DateTimeField(auto_now_add=True)),
                ('alterado_por', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'log de alteração de limite de recurso',
                'verbose_name_plural': 'logs de alteração de limite de recurso',
                'ordering': ['-alterado_em'],
            },
        ),
    ]
