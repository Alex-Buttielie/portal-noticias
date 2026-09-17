from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('catalogo_noticias', '0003_configuracaorobo_fonterobo'),
    ]

    operations = [
        migrations.AddField(
            model_name='newsitem',
            name='imagem_url',
            field=models.URLField(blank=True, help_text='URL da imagem extraída do RSS/enclosure — opcional, best-effort', max_length=1000),
        ),
    ]
