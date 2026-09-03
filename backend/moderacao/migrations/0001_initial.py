import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('contenttypes', '0002_remove_content_type_name'),
    ]

    operations = [
        migrations.CreateModel(
            name='Denuncia',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('motivo', models.CharField(choices=[('ameaca', 'Ameaça'), ('assedio', 'Assédio'), ('dado_pessoal', 'Divulgação indevida de dado pessoal'), ('spam', 'Spam'), ('outro', 'Outro')], default='outro', max_length=20)),
                ('detalhe', models.TextField(blank=True)),
                ('object_id', models.PositiveIntegerField()),
                ('status', models.CharField(choices=[('pendente', 'Pendente'), ('procedente', 'Procedente'), ('improcedente', 'Improcedente')], default='pendente', max_length=20)),
                ('criado_em', models.DateTimeField(auto_now_add=True)),
                ('resolvido_em', models.DateTimeField(blank=True, null=True)),
                ('resolucao_motivo', models.TextField(blank=True)),
                ('content_type', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='contenttypes.contenttype')),
                ('denunciante', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='denuncias_feitas', to=settings.AUTH_USER_MODEL)),
                ('resolvido_por', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='denuncias_resolvidas', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'denúncia',
                'verbose_name_plural': 'denúncias',
                'ordering': ['-criado_em'],
            },
        ),
        migrations.CreateModel(
            name='AcaoModeracao',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('tipo', models.CharField(choices=[('aviso', 'Aviso'), ('remocao_conteudo', 'Remoção de conteúdo'), ('bloqueio_temporario', 'Bloqueio temporário'), ('bloqueio_permanente', 'Bloqueio permanente')], max_length=30)),
                ('motivo', models.TextField()),
                ('ativo_ate', models.DateTimeField(blank=True, null=True)),
                ('criado_em', models.DateTimeField(auto_now_add=True)),
                ('aplicado_por', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='acoes_moderacao_aplicadas', to=settings.AUTH_USER_MODEL)),
                ('denuncia_relacionada', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='acoes', to='moderacao.denuncia')),
                ('usuario_alvo', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='acoes_moderacao_recebidas', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'ação de moderação',
                'verbose_name_plural': 'ações de moderação',
                'ordering': ['-criado_em'],
            },
        ),
        migrations.CreateModel(
            name='RecursoModeracao',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('texto', models.TextField()),
                ('status', models.CharField(choices=[('aberto', 'Aberto'), ('analisado', 'Analisado')], default='aberto', max_length=20)),
                ('criado_em', models.DateTimeField(auto_now_add=True)),
                ('acao', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='recursos', to='moderacao.acaomoderacao')),
                ('usuario', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='recursos_moderacao', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'recurso de moderação',
                'verbose_name_plural': 'recursos de moderação',
                'ordering': ['-criado_em'],
            },
        ),
        migrations.CreateModel(
            name='Reputacao',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('pontuacao', models.IntegerField(default=100)),
                ('atualizado_em', models.DateTimeField(auto_now=True)),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='reputacao', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'reputação',
                'verbose_name_plural': 'reputações',
            },
        ),
        migrations.CreateModel(
            name='ReputacaoEventoLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('delta', models.IntegerField()),
                ('motivo', models.CharField(max_length=300)),
                ('criado_em', models.DateTimeField(auto_now_add=True)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='eventos_reputacao', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'evento de reputação',
                'verbose_name_plural': 'eventos de reputação',
                'ordering': ['-criado_em'],
            },
        ),
        migrations.CreateModel(
            name='PaginaEditorial',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('slug', models.SlugField(unique=True)),
                ('titulo', models.CharField(max_length=200)),
                ('conteudo', models.TextField()),
                ('atualizado_em', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'página editorial',
                'verbose_name_plural': 'páginas editoriais',
            },
        ),
    ]
