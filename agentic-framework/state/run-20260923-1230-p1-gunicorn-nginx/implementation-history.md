# Implementation History — 20260923-1230-p1-gunicorn-nginx

## O que mudou (arquivo:linha)

- `backend/gunicorn.conf.py` (novo, 55 linhas): `worker_class="gthread"`,
  `workers=2` (env `GUNICORN_WORKERS`), `threads=4` (env `GUNICORN_THREADS`),
  `timeout=45` (env `GUNICORN_TIMEOUT`), `bind` via env `GUNICORN_BIND`
  (default `0.0.0.0:8000`); `graceful_timeout=30`, `keepalive=5`,
  `max_requests=1000` (+jitter 100), access log com `X-Request-ID`.
- `backend/Dockerfile:37-41`: CMD reduzido para
  `gunicorn config.wsgi:application --bind 0.0.0.0:8000` (conf auto-carregado;
  removidos `--workers 3 --timeout 180`).
- `.github/workflows/deploy.yml:186-191`: removido `--workers 2`, adicionado
  `--chdir "$APP_DIR/backend"` (gunicorn precisa achar `gunicorn.conf.py` +
  `config.wsgi` após o `cd frontend` do passo web) + comentário de motivo.
- `infra/nginx/portal-dev.conf` (187 linhas), `portal-homolog.conf`,
  `portal-prod.conf` (idênticos salvo cabeçalho/server_name/portas/alias):
  gzip on (+tipos JSON/CSS/JS; brotli comentado); `upstream portal_api_*`
  + keepalive 32 + `proxy_http_version 1.1` + `Connection ""` nos 4 proxys
  `/api/`; `location ~ ^/api/(feed/|radar/tendencias/)` com proxy_cache
  (zona `feed_cache`, TTL 45s, chave `$scheme$request_method$host$request_uri`
  sem cookie/Authorization, bypass+no_cache em
  `$http_authorization$cookie_sessionid$cookie_csrftoken`, cache_lock,
  use_stale, `X-Cache-Status`); `/static/` + `/media/` via alias
  (`/home/apps/portal-{dev,homolog,prod}/backend/{staticfiles,media}`) com
  security headers repetidos (pegadinha `add_header` do Nginx) e
  Cache-Control (`static`: max-age 30d immutable; `media`: max-age 7d sem
  immutable); `limit_req` (`escrita_publica` 20r/m burst 20 em `/api/`,
  `auth` 10r/m burst 10 em `/api/auth/`, `limit_req_status 429`);
  `proxy_read_timeout 45s` em tudo; zonas `limit_req_zone`/`proxy_cache_path`
  + `map $request_method $limit_post` como bloco COMENTADO no topo (vão no
  `http {}` global da VPS, uma vez). Bloco `= /api/admin/robos/executar/`
  com timeout 180 REMOVIDO (sem caminho HTTP longo restante).
- `infra/DEPLOY.md`: NÃO alterado — arquivo documenta a variante Docker/Caddy
  (não-operada); operação PM2+Nginx vive em `CI-CD.md` + cabeçalhos dos confs.
  Desvio do contrato registrado de propósito (diff menor, sem doc órfã).

## Decisões (motivo)

- Timeout 45s (não 30 nem 60): grep em `robos_views.py` (main + develop + stash)
  confirma que NENHUM caminho HTTP precisa de timeout longo — ingestão roda em
  Celery (`catalogo_noticias/tasks.py:ingerir_noticias`) e o POST manual vira
  202+thread (stash `ingestao-background-202`, ainda não commitado — ver
  pendências). 45s = mesmo TTL do cache de app P1-A
  (`FEED_CACHE_TTL_SEGUNDOS=45`, settings.py:884) → Nginx e app falam a mesma
  língua. `proxy_read_timeout 45s` casa com `timeout 45` (Nginx nunca corta antes).
- Workers 2 x threads 4 (= 8 concorrentes): VPS com pouca RAM; API I/O-bound
  (Postgres+cache+HTTP) escala em thread. `CONN_MAX_AGE=60` (settings.py:218)
  compatível com workers longevos.
- Cache regex `^/api/(feed/|radar/tendencias/)` (não prefixo `/api/feed/`):
  cobre `GET /api/feed/...` + `GET /api/radar/tendencias/...` com OU sem query
  string — chave inclui `$request_uri` (query normalizada pelo cliente). Rotas
  vizinhas (`/api/radar/evolucao/` autenticada, `/api/gating/status`,
  `/api/feed/interacoes/` POST) passam ao largo: caem no `/api/` geral, sem cache.
  `TendenciasView` e todo `feed/views.py` são `AllowAny` sem `exibir_publicidade`
  (P1-A removeu) → 100% público-cacheável; `EvolucoView`/`LocalidadesSalvasView`
  exigem auth e nunca casam o regex.
- `limit_req` em `/api/` INTEIRO (não só POST): Nginx sem módulo Lua não filtra
  por método em `limit_req`; o `map $request_method $limit_post` no bloco http
  faz a chave ser vazia em GET (sem limite) e IP em POST (20r/m). GET de leitura
  (feed/radar) nunca toma 503; POST anônimo (cadastro, lista-espera, comunidade)
  limitado igual ao DRF `escrita_publica` 20/min (settings.py:370). Zona `auth`
  10r/m casa com DRF `auth_sensivel` 10/min (settings.py:374).
- `alias` (não `root`) para /static/ e /media/: paths reais confirmados —
  VPS `/home/apps/portal-{dev,homolog,prod}` (CI-CD.md:23-25, deploy.yml app_dir),
  `staticfiles` = `STATIC_ROOT` (settings.py:285), `media` = `MEDIA_ROOT`
  (settings.py:306). WhiteNoise continua como fallback (não removido).
  `/media/` com `return 404` para `.py/.sh/.php/.pl/.cgi`: documentos de
  credenciamento servem SÓ via FileResponse autenticado (credenciamento/views.py:78),
  nunca via URL pública — bloco é cinto duplo.
- `proxy_cache_use_stale error timeout updating ...` + `proxy_cache_lock on`:
  upstream lento/errado serve stale em vez de 500; herd não derruba Gunicorn.
- `--chdir` no deploy PM2: passo anterior faz `cd frontend` (build web); sem
  `--chdir backend`, gunicorn não acha `config.wsgi` nem `gunicorn.conf.py`.
- `DEPLOY.md` intacto: contrato pedia seção de operação, mas o arquivo descreve
  stack Docker/Caddy desativada; operação canônica está em `CI-CD.md` + cabeçalho
  dos confs (comandos `cp/nginx -t/reload` + diretivas http{}). Adicionar seção
  lá seria doc órfã — orchestrator/documenter decidem se move para CI-CD.md.

## Evidências (validação)

- `gunicorn --check-config --config gunicorn.conf.py config.wsgi:application` → ok
  (venv, DJANGO_DEBUG=true/sqlite3/locmem).
- `python -m py_compile gunicorn.conf.py` → ok; asserts
  (`worker_class==gthread`, `threads>=2`, `timeout<=60`) → ok.
- `docker build -f backend/Dockerfile ./backend` → ok (imagem monta, migrations +
  collectstatic rodam no entrypoint); dentro da imagem, `gunicorn.conf.py` resolve
  `gthread 2w x 4t timeout 45`; CMD = `["gunicorn","config.wsgi:application",
  "--bind","0.0.0.0:8000"]` (sem flags divergentes). Imagem de teste removida.
- Endpoints resolvidos localmente (Client Django, sqlite/locmem):
  `GET /api/feed/` 200, `/api/feed/?categoria=esportes` 200,
  `/api/radar/tendencias/` 200, `GET /api/comunidade/publicacoes/` 200,
  `GET /api/landing/lista-espera/` 405 (POST-only, correto).
- `deploy.yml` parseado via `yaml.safe_load` → ok; grep confirma zero
  `--timeout/--workers/180s` restante em Dockerfile/deploy/nginx/Caddy/compose
  (só o `--timeout=5s` do HEALTHCHECK Docker, irrelevante).
- `nginx -t`: BINÁRIO AUSENTE neste ambiente (`which nginx` vazio) — validação
  substituída por revisão de sintaxe automatizada (script Python: braces
  balanceados nos 3 confs; presença de todas as diretivas exigidas; ausência de
  `180s`/`limit_req_zone`/`proxy_cache_path` em contexto ativo; chave de cache
  sem cookie/Authorization; bypass com os 3 sinais; drift dev↔homolog↔prod =
  só cabeçalho/upstream/portas/alias). 3/3 ok (187 linhas cada).
- `tsc`/pytest: NÃO afetados (só config/infra; nenhum `.py` de app tocado —
  `git status` mostra só Dockerfile/deploy/nginx + `gunicorn.conf.py` novo).

## Pendências / follow-ups (exigem humano ou outra run)

1. **Rodar `nginx -t` + reload NA VPS antes de ativar** (binário inexistente aqui;
   critério 6 do contrato atendido via revisão registrada, não via `nginx -t`).
2. **Adicionar UMA vez no `http {}` global da VPS** (`/etc/nginx/nginx.conf`):
   `map`, 2× `limit_req_zone`, `proxy_cache_path` (bloco comentado no topo dos
   confs); criar `/var/cache/nginx/feed` (Nginx cria sozinho com `use_temp_path=off`,
   mas checar permissão do usuário `www-data`); depois `cp` dos 3 confs + reload.
3. **Reload Nginx + restart PM2 na VPS exige acesso humano** (sem SSH neste
   ambiente; deploy sai pela esteira `deploy-{dev,homolog,prod}.yml` ou manual).
   PM2 pega `gunicorn.conf.py` automaticamente via `--chdir backend` (sem flag
   extra); confirmar com `pm2 logs portal-api-*` que workers sobem como gthread.
4. **Stash `ingestao-background-202` (POST /executar/ → 202) ainda NÃO commitado**
   (`git stash list`): timeout 45s desta run PRESSUPÕE ele. Se a run dona não
   commitar, o endpoint síncrono (~90 feeds) estoura 45s → 502/504 no Nginx +
   worker morto no Gunicorn. Ordem segura: commitar o stash ANTES de ativar estes
   confs na VPS (ou manter `--timeout 180` temporário no PM2).
5. Cache Nginx é opaco ao `Cache-Control` do app por default (`proxy_cache_valid
   200 45s` manda): se a run P1-A mudar `FEED_CACHE_TTL_SEGUNDOS`, alinhar o `45s`
   dos confs junto (documenter pode mover para CI-CD.md).
6. `limit_req` 503→429 via `limit_req_status 429`: frontend deve tratar 429 como
   retry-mais-tarde (hoje trata como erro genérico) — follow-up frontend, sem
   urgência (burst 20 absorve uso legítimo).
