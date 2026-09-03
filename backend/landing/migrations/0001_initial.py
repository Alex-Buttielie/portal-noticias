from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name='InscricaoListaEspera',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nome', models.CharField(max_length=150)),
                ('email', models.EmailField(max_length=254, unique=True)),
                ('interesses', models.JSONField(blank=True, default=list)),
                ('localidade', models.CharField(blank=True, max_length=150)),
                ('canal_preferido', models.CharField(blank=True, max_length=20)),
                ('consentimento_aceito_em', models.DateTimeField()),
                ('criado_em', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'verbose_name': 'inscrição na lista de espera',
                'verbose_name_plural': 'inscrições na lista de espera',
                'ordering': ['criado_em'],
            },
        ),
    ]
