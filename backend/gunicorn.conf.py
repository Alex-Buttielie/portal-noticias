# Gunicorn — config única (run 20260923-1230 P1-3).
#
# API é I/O-bound (Postgres + cache + upstream HTTP): `gthread` permite que
# uma requisição presa (ex.: ingestão em thread background, endpoint lento)
# não derrube o serviço — outras threads do worker continuam servindo.
# `CONN_MAX_AGE=60` já configurado (config/settings.py: o Django mantém a
# conexão por 60s, compatível com workers/threads de longa vida; pgbouncer
# fica como follow-up se o pool saturar).
#
# Lido automaticamente pelos dois caminhos de serving (Docker e PM2 na VPS):
# - Docker: `CMD gunicorn config.wsgi:application` (o conf na raiz do
#   backend, nomeado `gunicorn.conf.py`, é carregado por padrão).
# - PM2/VPS: o workflow (.github/workflows/deploy.yml) não passa flags de
#   worker/timeout — tudo vem daqui (bind/porta continuam via env/args).
#
# Env vars (override sem editar arquivo):
# - GUNICORN_WORKERS (default 2: VPS atual tem pouca RAM; 2 workers x 4
#   threads = 8 requisições concorrentes, folga para o tráfego atual).
# - GUNICORN_BIND (default "0.0.0.0:8000"; na VPS o deploy passa
#   --bind "0.0.0.0:$API_PORT" por cima).
# - GUNICORN_THREADS (default 4), GUNICORN_TIMEOUT (default 45).
import os


def _int_env(nome, padrao):
    try:
        return max(1, int(os.environ.get(nome, padrao)))
    except (TypeError, ValueError):
        return padrao


# 2 na VPS atual (pouca RAM); parametrizável sem editar arquivo.
workers = _int_env("GUNICORN_WORKERS", 2)
# 4 threads/worker: 2 x 4 = 8 concorrentes; I/O-bound escala bem aqui.
threads = _int_env("GUNICORN_THREADS", 4)
worker_class = "gthread"
# 45s: nenhum caminho HTTP legítimo precisa de mais — POST
# /api/admin/robos/executar/ responde 202 imediato (thread background,
# stash "ingestao-background-202" no develop, a commitar pela run dona;
# ver implementation-history.md); ingestão longa roda em Celery
# (catalogo_noticias/tasks.py:ingerir_noticias).
# Nginx usa proxy_read_timeout 45s para casar (infra/nginx/portal-*.conf).
timeout = _int_env("GUNICORN_TIMEOUT", 45)
graceful_timeout = 30
keepalive = 5
bind = os.environ.get("GUNICORN_BIND", "0.0.0.0:8000")
# Não matar workers sob carga transitória de CPU (ex.: collectstatic
# concorrente, GC): reinicia só em leak real de memória.
max_requests = 1000
max_requests_jitter = 100
# Logs no formato do request_id do projeto (ver config/settings.py LOGGING):
# o access log inclui X-Request-ID quando o Nginx o repassa.
accesslog = "-"
errorlog = "-"
loglevel = os.environ.get("GUNICORN_LOG_LEVEL", "info")
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" req=%({x-request-id}i)s %(D)sus'
preload_app = False
