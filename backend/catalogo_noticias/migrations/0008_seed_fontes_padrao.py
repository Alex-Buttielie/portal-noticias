"""
Seed das fontes padrão de ingestão (lista do dono em settings).

Aplica `settings.CATALOGO_NOTICIAS_FONTES_RSS` em `FonteRobo` — mesma regra
do comando `sincronizar_fontes_padrao`, sem desativar órfãs:
- cria a linha quando o nome (case-insensitive) não existe;
- atualiza url/UF e reativa quando existe com dados divergentes.

Idempotente: roda em todo `migrate` (local, dev, homolog, prod) sem duplicar
nem apagar curadoria manual. Reverso sem efeito (nunca remove fontes).
"""

from django.conf import settings
from django.db import migrations


def aplicar_fontes_padrao(apps, schema_editor):
    FonteRobo = apps.get_model("catalogo_noticias", "FonteRobo")
    existentes = {f.nome.strip().lower(): f for f in FonteRobo.objects.all()}
    for fonte in settings.CATALOGO_NOTICIAS_FONTES_RSS:
        nome = (fonte.get("nome") or "").strip()
        url = (fonte.get("url") or "").strip()
        uf = (fonte.get("uf") or "").strip().upper()
        if not nome or not url:
            continue
        atual = existentes.get(nome.lower())
        if atual is None:
            FonteRobo.objects.create(
                nome=nome, url=url, ativo=True, estado_padrao=uf
            )
        else:
            mudou = False
            if atual.url != url:
                atual.url = url
                mudou = True
            if (atual.estado_padrao or "") != uf:
                atual.estado_padrao = uf
                mudou = True
            if not atual.ativo:
                atual.ativo = True
                mudou = True
            if mudou:
                atual.save(
                    update_fields=["url", "estado_padrao", "ativo"]
                )


def reverso_sem_efeito(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("catalogo_noticias", "0007_fonterobo_estado_padrao"),
    ]

    operations = [
        migrations.RunPython(aplicar_fontes_padrao, reverso_sem_efeito),
    ]
