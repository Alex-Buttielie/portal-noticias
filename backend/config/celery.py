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

# `config` não é uma app do Django, então `autodiscover_tasks()` — que varre
# só as apps instaladas — não encontra `config/tasks.py` (a task de heartbeat
# do beat, P1-03). O import explícito abaixo é o que a registra. Ele roda
# durante o import de `config` (via `config/__init__.py`), antes do fim de
# `django.setup()`; por isso `config/tasks.py` não pode importar models nem
# ler settings no nível do módulo.
from . import tasks as _tasks_do_projeto  # noqa: E402,F401 — registro por efeito colateral
