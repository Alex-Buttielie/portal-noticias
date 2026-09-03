import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('assinatura', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Organizacao',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nome', models.CharField(max_length=200)),
                ('plano', models.CharField(choices=[('basic', 'Basic'), ('pro', 'Pro'), ('enterprise', 'Enterprise')], default='basic', max_length=20)),
                ('ativo', models.BooleanField(default=True)),
                ('criado_em', models.DateTimeField(auto_now_add=True)),
                ('assinatura', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='organizacao_b2b', to='assinatura.subscription')),
            ],
            options={
                'verbose_name': 'organização',
                'verbose_name_plural': 'organizações',
            },
        ),
        migrations.CreateModel(
            name='CriterioMonitoramento',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('tipo', models.CharField(choices=[('empresa', 'Empresa'), ('concorrente', 'Concorrente'), ('setor', 'Setor'), ('palavra_chave', 'Palavra-chave')], max_length=20)),
                ('valor', models.CharField(max_length=200)),
                ('ativo', models.BooleanField(default=True)),
                ('criado_em', models.DateTimeField(auto_now_add=True)),
                ('organizacao', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='criterios', to='b2b.organizacao')),
            ],
            options={
                'verbose_name': 'critério de monitoramento',
                'verbose_name_plural': 'critérios de monitoramento',
            },
        ),
        migrations.CreateModel(
            name='MembroOrganizacao',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('papel_na_organizacao', models.CharField(choices=[('admin_organizacao', 'Administrador da organização'), ('membro', 'Membro')], default='membro', max_length=20)),
                ('criado_em', models.DateTimeField(auto_now_add=True)),
                ('organizacao', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='membros', to='b2b.organizacao')),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='membro_b2b', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'membro de organização',
                'verbose_name_plural': 'membros de organização',
            },
        ),
    ]
