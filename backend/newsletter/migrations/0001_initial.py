import django.db.models.deletion
import newsletter.models
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='EnvioNewsletter',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('executado_em', models.DateTimeField(auto_now_add=True)),
                ('total_inscricoes_processadas', models.PositiveIntegerField(default=0)),
                ('total_enviados', models.PositiveIntegerField(default=0)),
                ('total_falhas', models.PositiveIntegerField(default=0)),
            ],
            options={
                'verbose_name': 'envio de newsletter',
                'verbose_name_plural': 'envios de newsletter',
                'ordering': ['-executado_em'],
            },
        ),
        migrations.CreateModel(
            name='InscricaoNewsletter',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('tipo', models.CharField(choices=[('padrao', 'Padrão'), ('categoria', 'Por categoria'), ('personalizada', 'Personalizada (Premium)')], default='padrao', max_length=20)),
                ('categorias', models.JSONField(blank=True, default=list)),
                ('ativa', models.BooleanField(default=True)),
                ('token_descadastro', models.CharField(default=newsletter.models.gerar_token, max_length=64, unique=True)),
                ('criado_em', models.DateTimeField(auto_now_add=True)),
                ('atualizado_em', models.DateTimeField(auto_now=True)),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='inscricao_newsletter', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'inscrição de newsletter',
                'verbose_name_plural': 'inscrições de newsletter',
            },
        ),
    ]
