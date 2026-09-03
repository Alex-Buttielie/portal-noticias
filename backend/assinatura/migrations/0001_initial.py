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
            name='Plan',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nome', models.CharField(max_length=100)),
                ('preco', models.DecimalField(decimal_places=2, max_digits=10)),
                ('duracao_dias', models.PositiveIntegerField()),
                ('ativo', models.BooleanField(default=True)),
                ('criado_em', models.DateTimeField(auto_now_add=True)),
                ('atualizado_em', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'plano',
                'verbose_name_plural': 'planos',
                'ordering': ['preco'],
            },
        ),
        migrations.CreateModel(
            name='ConfiguracaoAssinatura',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('grace_period_dias', models.PositiveIntegerField(default=7)),
                ('periodo_teste_dias', models.PositiveIntegerField(default=0)),
                ('periodo_teste_ativo', models.BooleanField(default=False)),
                ('atualizado_em', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'configuração de assinatura',
                'verbose_name_plural': 'configuração de assinatura',
            },
        ),
        migrations.CreateModel(
            name='Subscription',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('status', models.CharField(choices=[('teste', 'Teste'), ('ativa', 'Ativa'), ('pagamento_pendente', 'Pagamento pendente'), ('inadimplente', 'Inadimplente'), ('cancelada', 'Cancelada'), ('expirada', 'Expirada'), ('encerrada', 'Encerrada')], default='pagamento_pendente', max_length=20)),
                ('preco_cobrado', models.DecimalField(decimal_places=2, max_digits=10)),
                ('duracao_dias_no_momento', models.PositiveIntegerField()),
                ('inicio', models.DateTimeField(blank=True, null=True)),
                ('vencimento', models.DateTimeField(blank=True, null=True)),
                ('renovacao_automatica', models.BooleanField(default=True)),
                ('grace_period_termina_em', models.DateTimeField(blank=True, null=True)),
                ('gateway_referencia', models.CharField(blank=True, max_length=200)),
                ('criado_em', models.DateTimeField(auto_now_add=True)),
                ('atualizado_em', models.DateTimeField(auto_now=True)),
                ('plan', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='assinaturas', to='assinatura.plan')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='assinaturas', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'assinatura',
                'verbose_name_plural': 'assinaturas',
                'ordering': ['-criado_em'],
            },
        ),
        migrations.CreateModel(
            name='HistoricoPagamento',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('valor', models.DecimalField(decimal_places=2, max_digits=10)),
                ('status', models.CharField(choices=[('aprovado', 'Aprovado'), ('recusado', 'Recusado'), ('pendente', 'Pendente'), ('estornado', 'Estornado')], max_length=20)),
                ('referencia_gateway', models.CharField(blank=True, max_length=200)),
                ('criado_em', models.DateTimeField(auto_now_add=True)),
                ('subscription', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='pagamentos', to='assinatura.subscription')),
            ],
            options={
                'verbose_name': 'pagamento',
                'verbose_name_plural': 'histórico de pagamentos',
                'ordering': ['-criado_em'],
            },
        ),
        migrations.CreateModel(
            name='AssinaturaMudancaEstadoLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('estado_anterior', models.CharField(blank=True, max_length=20)),
                ('estado_novo', models.CharField(max_length=20)),
                ('motivo', models.CharField(max_length=300)),
                ('criado_em', models.DateTimeField(auto_now_add=True)),
                ('subscription', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='mudancas_de_estado', to='assinatura.subscription')),
            ],
            options={
                'verbose_name': 'log de mudança de estado de assinatura',
                'verbose_name_plural': 'logs de mudança de estado de assinatura',
                'ordering': ['-criado_em'],
            },
        ),
    ]
