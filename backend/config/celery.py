"""
Instancia do app Celery do projeto (ARCHITECTURE.md secao 1: Celery + Redis
para jobs assincronos — ingestao periodica de noticias em
`catalogo_noticias/tasks.py`, entre outros usos futuros do projeto). Ver
`config/__init__.py` (garante que o app Celery e carregado junto com o
Django) e `config/settings.py` (`CELERY_*`, `CELERY_BEAT_SCHEDULE`).
"""

import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

app = Celery("brd_portal_noticias")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
