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
# - GUNICORN_THREADS (default 4), GUNICORN_TIMEOUT (default 60 no estado
#   atual; reduzir para 45 somente depois do commit do endpoint 202).
import os


def _int_env(nome, padrao, minimo=1, maximo=None):
    """Lê inteiro do env com clamp.

    O clamp importa: `threads` e `timeout` alimentam invariantes que outros
    arquivos assumem (`gthread` com threads >= 2 e o `proxy_read_timeout 60s`
    do Nginx). Um override solto como `GUNICORN_TIMEOUT=180` desalinharia o
    par servidor/proxy sem que ninguém perceba, e `GUNICORN_THREADS=1`
    trocaria o benefício do gthread (uma requisição presa mata o worker).
    """
    try:
        valor = int(os.environ.get(nome, padrao))
    except (TypeError, ValueError):
        valor = padrao
    valor = max(minimo, valor)
    if maximo is not None:
        valor = min(maximo, valor)
    return valor


# 2 na VPS atual (pouca RAM); parametrizável sem editar arquivo.
workers = _int_env("GUNICORN_WORKERS", 2)
# 4 threads/worker: 2 x 4 = 8 concorrentes; I/O-bound escala bem aqui.
# Mínimo 2: com 1 thread o worker fica bloqueado por requisição.
threads = _int_env("GUNICORN_THREADS", 4, minimo=2, maximo=32)
worker_class = "gthread"
# 60s é o default seguro enquanto o ref implantado ainda puder ter o
# endpoint síncrono. O 202+background de /api/admin/robos/executar/ está
# em uma alteração de trabalho ainda não commitada: só ative
# `GUNICORN_TIMEOUT=45` (e `proxy_read_timeout 45s` nos três confs) depois
# que esse commit for ancestral comprovado do ref implantado. Não reduzir o
# timeout antes disso; a ingestão síncrona pode passar de 45s.
# Nginx usa proxy_read_timeout 60s para casar (infra/nginx/portal-*.conf):
# o teto de 60s mantém o par servidor/proxy dentro do contrato documentado.
timeout = _int_env("GUNICORN_TIMEOUT", 60, minimo=10, maximo=60)
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
