import credenciamento.models
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
            name='SolicitacaoCredenciamento',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('cidade', models.CharField(blank=True, max_length=150)),
                ('uf', models.CharField(blank=True, max_length=2)),
                ('foto', models.FileField(blank=True, null=True, upload_to=credenciamento.models.caminho_documento)),
                ('mini_bio', models.TextField(blank=True)),
                ('dados_profissionais', models.TextField(blank=True)),
                ('documento', models.FileField(upload_to=credenciamento.models.caminho_documento)),
                ('status', models.CharField(choices=[('pendente', 'Pendente'), ('aprovado', 'Aprovado'), ('reprovado', 'Reprovado'), ('info_solicitada', 'Informação adicional solicitada')], default='pendente', max_length=20)),
                ('criado_em', models.DateTimeField(auto_now_add=True)),
                ('decidido_em', models.DateTimeField(blank=True, null=True)),
                ('motivo_decisao', models.TextField(blank=True)),
                ('decidido_por', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='decisoes_credenciamento', to=settings.AUTH_USER_MODEL)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='solicitacoes_credenciamento', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'solicitação de credenciamento',
                'verbose_name_plural': 'solicitações de credenciamento',
                'ordering': ['criado_em'],
            },
        ),
        migrations.CreateModel(
            name='PerfilJornalista',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('selo_ativo', models.BooleanField(default=True)),
                ('credenciado_em', models.DateTimeField(auto_now_add=True)),
                ('suspenso', models.BooleanField(default=False)),
                ('motivo_suspensao', models.TextField(blank=True)),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='perfil_jornalista', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'perfil de jornalista',
                'verbose_name_plural': 'perfis de jornalista',
            },
        ),
    ]
