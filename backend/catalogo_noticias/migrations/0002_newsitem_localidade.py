from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('catalogo_noticias', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='newsitem',
            name='pais',
            field=models.CharField(blank=True, max_length=100),
        ),
        migrations.AddField(
            model_name='newsitem',
            name='estado',
            field=models.CharField(blank=True, max_length=100),
        ),
        migrations.AddField(
            model_name='newsitem',
            name='cidade',
            field=models.CharField(blank=True, max_length=150),
        ),
    ]
