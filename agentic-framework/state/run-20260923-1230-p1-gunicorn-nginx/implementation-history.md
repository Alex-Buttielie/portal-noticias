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

## Remediação (iteração 1)

Esta seção substitui as decisões de timeout/zonas/mídia registradas antes da
revisão. O endpoint de ingestão e os arquivos de `settings.py`, `feed/` e
`gating/` não foram alterados por esta remediação. Nas referências
`infra/nginx/portal-*.conf`, as linhas indicadas são equivalentes nos três
ambientes (somente mudam upstream, porta e path do alias).

### Finding 1 — blocker — `/media/` expõe documentos de credenciamento

- **Investigação/evidência:** o grep de `FileField`/`upload_to` em
  `backend/credenciamento/models.py:5-6,36,42,89` encontrou somente
  `foto`, `documento` e `foto` de perfil, todos gravados em
  `media/credenciamento/<user_id>/`; `backend/credenciamento/views.py:56-78`
  exige o próprio solicitante ou admin no `DocumentoView`.
- **Correção:** `infra/nginx/portal-dev.conf:78-109`,
  `portal-homolog.conf:78-109` e `portal-prod.conf:78-109` removem o alias
  de `backend/media/` inteiro. A subtree privada é negada por
  `location = /media/credenciamento` e
  `location ^~ /media/credenciamento/` retornam 404; o único alias
  direto é a allowlist `/media/public/`. Não há bloqueio por extensão nem
  caminho Nginx não autenticado para o documento. Como as fotos atuais
  compartilham a árvore privada, a decisão é fail-closed (não as expor
  até uma futura separação de storage); o endpoint Django continua sendo o
  caminho autorizado.
- **Evidência:** os três confs não contêm `alias .../media/` genérico e
  o teste Nginx com todos os sites + include global passou; a proteção do
  `DocumentoView` não foi alterada.

### Finding 2 — blocker — zones ausentes quebram `nginx -t`

- **Correção:** `infra/nginx/http-cache.conf:19-35` versiona os dois
  `map`, as duas `limit_req_zone` e `proxy_cache_path` no contexto correto
  `http {}`. Os snippets `infra/nginx/portal-location-cache.conf:6-20`,
  `portal-location-auth.conf:5-6` e `portal-location-write.conf:6-7`
  versionam as diretivas de location. Os sites referenciam esses snippets
  por includes opcionais (`portal-*.conf:123,137,154,188-189,212`) e não mantêm
  referências ativas a zones; antes da instalação, cache/rate ficam
  deliberadamente desligados e o parser continua válido.
- **Runbook:** `infra/DEPLOY.md:147-208` documenta a ordem include global
  → snippets → site → `nginx -t` → reload, criação/permissão de
  `/var/cache/nginx/feed` e a proibição de instalar snippets antes do
  `http {}`; `CI-CD.md:32-39` aponta o procedimento.
- **Evidência:** `nginx:alpine` 1.31.6 (imagem local) passou em dois
  wrappers: (a) ativação completa com `http-cache.conf` + três snippets +
  os três sites; (b) sites standalone sem zones/snippets. O teste da ordem
  errada (snippet de location sem `http-cache.conf`) reproduziu
  `proxy_cache zone "feed_cache" is unknown`; o script de chaves
  balanceadas passou em todos os sete arquivos `.conf`.

### Finding 3 — major — timeout 45 dependia de 202 não commitado

- **Correção:** `backend/gunicorn.conf.py:54-62` passa a ter default
  seguro `timeout=60` e condiciona qualquer `45` ao commit 202+background
  ser ancestral comprovado do ref implantado. O PM2 em
  `.github/workflows/deploy.yml:191-195` também fixa
  `GUNICORN_TIMEOUT=60`; os três Nginx usam
  `proxy_read_timeout 60s` (`portal-*.conf:128-129,142-143,159-160,
  200-201,217-221`). A pré-condição “commit 202 antes de 45” está também
  no comentário de `gunicorn.conf.py:54-59`, no workflow e no runbook
  `infra/DEPLOY.md:230-240`.
- **Decisão:** 60 é o default seguro para o estado atual; 45 fica como
  follow-up atômico (Gunicorn + três locations), sem tocar no endpoint.
- **Evidência:** `gunicorn --check-config --config gunicorn.conf.py
  config.wsgi:application` passou e `--print-config` reportou
  `workers=2`, `threads=4`, `worker_class=gthread`, `timeout=60`.

### Finding 4 — major — POST `/api/feed/interacoes/` capturado pelo cache

- **Correção:** os três confs têm a location exata
  `location = /api/feed/interacoes/` (`portal-*.conf:150-165`) com o
  snippet de escrita pública, fora do regex; o regex (`portal-*.conf:
  167-206`) é uma allowlist de URIs GET e não inclui `interacoes/` nem
  `busca/historico/`. `http-cache.conf:24-31` e
  `portal-location-cache.conf:6-14` também impedem cache de métodos não
  GET/HEAD. Portanto o POST não pode ser servido/armazenado pelo cache e
  continua sujeito a `limit_req` de 20/min quando os snippets são instalados.
- **Evidência:** grep nos três confs confirmou a location exata e a
  ausência de `feed/interacoes/` no allowlist; a simulação Nginx completa
  passou com o include de escrita ativo.

### Finding 5 — minor — descoberta do conf PM2 dependia do cwd

- **Correção/documentação:** `.github/workflows/deploy.yml:182,186-190,195`
  registra que o `cd "$APP_DIR/backend"` imediatamente anterior faz o
  PM2 herdar `pm_cwd=backend` e passa `--config
  "$APP_DIR/backend/gunicorn.conf.py"` absoluto; `--chdir` continua
  apenas para o caminho de import da aplicação. O mesmo motivo está em
  `backend/gunicorn.conf.py:10-16`.
- **Evidência:** `--print-config` executado de `/tmp/opencode` com
  `--config` absoluto + `--chdir` reportou `gthread/2/4/timeout=60`, sem
  depender da descoberta automática por cwd.

### Finding 6 — minor — keepalive ausente em auth/health

- **Correção:** `proxy_http_version 1.1` e `proxy_set_header Connection ""`
  foram adicionados em `/healthz` (`portal-*.conf:111-118`) e em toda a
  subtree `/api/auth/`, incluindo a location exata de cadastro
  (`portal-*.conf:120-148`), nos três ambientes.
- **Evidência:** verificação estática encontrou as duas diretivas em cada
  um dos três confs; o wrapper Nginx completo passou.

### Finding 7 — minor — cadastro com 10/min em vez de 20/min

- **Correção:** `location = /api/auth/cadastro/` (`portal-*.conf:
  120-134`) inclui `portal-location-write*.conf`, cuja taxa é 20/min
  (`portal-location-write.conf:1-7`). A subtree restante
  `location /api/auth/` (`portal-*.conf:136-148`) inclui
  `portal-location-auth*.conf`, 10/min (`portal-location-auth.conf:1-6`).
  Isso preserva `CadastroView`/DRF 20/min e aplica 10/min a login,
  recuperação e demais endpoints sensíveis.
- **Evidência:** `backend/config/settings.py:369-374` foi somente lido
  (20/min para `escrita_publica`, 10/min para `auth_sensivel`); as duas
  locations e os dois snippets existem de forma idêntica nos três confs.

### Validação da iteração

- `gunicorn --check-config --config gunicorn.conf.py
  config.wsgi:application` (a partir de `backend`, com SQLite/locmem de
  teste) → exit 0.
- `deploy.yml` parseado com `yaml.safe_load` → válido (`guard`, `deploy`,
  `validate`).
- `python3 -m py_compile backend/gunicorn.conf.py` → exit 0;
  `git diff --check` → sem whitespace errors.
- `nginx:alpine` em wrapper com `http-cache.conf` + três snippets + três
  sites → `syntax is ok` / `test is successful`; wrapper standalone sem
  zones/snippets → igualmente `syntax is ok` / `test is successful`.
- Teste de regex/rota: 3/3 `portal-*.conf` não casam
  `/api/feed/interacoes/` nem `busca/historico/`; as locations exatas de
  interação e cadastro estão presentes.
- Leitura manual + script de chaves balanceadas: 7/7 `.conf` válidos;
  os três sites mantêm o mesmo conteúdo estrutural, variando apenas
  ambiente, upstream, porta e alias.

**Veredito da remediação:** 7/7 findings cobertos; pronto para a
revisão do remediator/orchestrator, sem commit realizado nesta etapa.
