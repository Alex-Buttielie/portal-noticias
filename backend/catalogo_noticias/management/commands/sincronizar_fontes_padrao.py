"""Aplica as fontes padrão (`settings.CATALOGO_NOTICIAS_FONTES_RSS`) no banco.

Uso:
    python manage.py sincronizar_fontes_padrao [--desativar-orfas]

- Para cada fonte padrão: cria a linha `FonteRobo` ou atualiza url/uf de
  linha existente com o MESMO nome (case-insensitive); sempre ativa.
- Sem flags, linhas do banco fora do padrão são apenas LISTADAS (órfãs) —
  nada é desativado sem `--desativar-orfas`.
- Corrige o incidente 2026-09-18 (homepages cadastradas como feed).

Idempotente: pode rodar a cada deploy.
"""

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction

from catalogo_noticias.models import FonteRobo


class Command(BaseCommand):
    help = "Sincroniza FonteRobo com as fontes padrão dos settings."

    def add_arguments(self, parser):
        parser.add_argument(
            "--desativar-orfas",
            action="store_true",
            help="Desativa linhas FonteRobo fora da lista padrão.",
        )

    def handle(self, *args, **opcoes):
        padrao = settings.CATALOGO_NOTICIAS_FONTES_RSS
        existentes = {f.nome.strip().lower(): f for f in FonteRobo.objects.all()}
        criadas, atualizadas = 0, 0

        with transaction.atomic():
            for fonte in padrao:
                nome = (fonte["nome"] or "").strip()
                url = (fonte["url"] or "").strip()
                uf = (fonte.get("uf") or "").strip().upper()
                if not nome or not url:
                    continue
                atual = existentes.pop(nome.lower(), None)
                if atual is None:
                    FonteRobo.objects.create(nome=nome, url=url, ativo=True, estado_padrao=uf)
                    criadas += 1
                    self.stdout.write(f"[nova] {nome} ({uf or 'nacional'})")
                else:
                    mudou = False
                    if atual.url != url:
                        atual.url = url
                        # Validators HTTP são específicos do recurso antigo;
                        # trocar a URL precisa forçar um download completo.
                        atual.etag = ""
                        atual.last_modified = ""
                        atual.ultima_revalidacao_completa = None
                        mudou = True
                    if (atual.estado_padrao or "") != uf:
                        atual.estado_padrao = uf
                        mudou = True
                    if not atual.ativo:
                        atual.ativo = True
                        mudou = True
                    if mudou:
                        atual.save()
                        atualizadas += 1
                        self.stdout.write(f"[atualizada] {nome} -> {url} ({uf or 'nacional'})")

            if opcoes["desativar_orfas"]:
                for nome_norm, f in existentes.items():
                    if f.ativo:
                        f.ativo = False
                        f.save()
                        self.stdout.write(f"[desativada] {f.nome}")
            elif existentes:
                self.stdout.write("Órfãs (fora do padrão, mantidas):")
                for f in existentes.values():
                    self.stdout.write(f"  - {f.nome} [{f.url}] ativo={f.ativo}")

        self.stdout.write(
            self.style.SUCCESS(f"OK: {criadas} criadas, {atualizadas} atualizadas, {len(padrao)} no padrão.")
        )
