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
            name='LocalidadeSalva',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('pais', models.CharField(blank=True, max_length=100)),
                ('estado', models.CharField(blank=True, max_length=100)),
                ('cidade', models.CharField(blank=True, max_length=150)),
                ('criado_em', models.DateTimeField(auto_now_add=True)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='localidades_salvas', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'localidade salva',
                'verbose_name_plural': 'localidades salvas',
                'unique_together': {('user', 'pais', 'estado', 'cidade')},
            },
        ),
    ]
