<!--
CONTRACT: implementation-contract
DONO: tester (subagente independente)
RUN: 20260925-1020-observabilidade
PAPEL: VERIFICAÇÃO. Nenhum arquivo do projeto foi editado, criado ou commitado.
-->

# Test Report — 20260925-1020-observabilidade

**Testador:** subagente independente (verificação, não correção)
**Branch:** `observability-20260925-1020` · **Diff:** `7715dae..HEAD` (10 commits, 148 arquivos, +39 333/−2 777)
**Data:** 2026-09-25
**Veredito final:** **`passed_with_blocked_criteria`**
**Contagem:** 42 critérios → **21 passou** · **9 falhou** · **12 não verificáveis neste ambiente**

---

## 0. Como este relatório deve ser lido

O tema declarado da run é **falso verde**. A regra que apliquei ao meu próprio
trabalho foi: *nenhum veredito se apoia em "deve funcionar", em leitura de
código, nem no que `run-state.json` e os relatórios de bloco afirmam.* Onde a
afirmação dos relatórios divergiu do comportamento observado, o relatório
aponta a divergência.

Duas armadilhas do ambiente foram tratadas explicitamente:

1. **WIP alheio na mesma árvore.** `git status` no início e no fim mostrou 23
   entradas modificadas/não rastreadas. **Nenhuma delas pertence a esta run.**
   As 4 modificações em `.github/workflows/deploy*.yml` (gate `usuarios_teste`),
   `subir-localhost.sh`, `backend/feed/views.py`,
   `backend/catalogo_noticias/services/deduplicacao.py`,
   `backend/catalogo_noticias/management/commands/agendar_ingestao.py`,
   `backend/identidade/management/commands/criar_usuario_carga.py` e
   `scripts/release/` são das runs `20260924-2136`, `20260925-1836` e do lote
   P0-1 de `20260925-1433`.
   **Consequência metodológica real:** o parse dos 6 workflows e o `actionlint`
   rodados sobre a árvore de trabalho mediram arquivos **contaminados**. Por isso
   repeti os dois **sobre o conteúdo commitado** (`git show HEAD:<file>`, extraído
   para fora do repositório) e são esses os resultados que valem (§3.4).
   Nenhuma falha alheia é reportada como falha desta run; onde o WIP alheio
   impediu a verificação, o critério está marcado como **não verificável por
   contenção**.
2. **Worktree em `/tmp/opencode/p01-wt`** (branch `lote-p0-1-proveniencia`): não
   foi tocado, lido nem montado.

**Nenhum arquivo do projeto foi modificado.** As duas mutações que fiz para
provar que a guarda de conteúdo fictício morde (seção 2.4) foram restauradas e
confirmadas por `git status` **e** por `sha256sum` antes/depois. O `git status`
final é byte a byte o do início.

### Ambiente montado por mim

| componente | como subiu | evidência |
|---|---|---|
| PostgreSQL 16 | `docker run` em `localhost:5432`, base `brd_portal_noticias` | `pg_isready` OK, `migrate` completo |
| Redis 7 | `docker run` em `localhost:6379` | `redis-cli ping` implícito pelo `check_cache` = `ok` |
| Django | `manage.py runserver 0.0.0.0:8011` (run 1 e run 2, com `OBSERVABILITY_JOB_STATE_FILE` e `OBSERVABILITY_BEAT_HEARTBEAT_FILE`) | `/livez` 200 |
| Celery worker | `.venv/bin/celery -A config worker --concurrency=1` | 4 tasks executadas com `SUCCESS` |
| Frontend | `next build` + `next start` em 3 portas (3001→backend real, 3002→porta morta 9999, 3003→upstream lento 9998 com `API_PROXY_TIMEOUT_MS=2000`) | Home 200 nos três |
| Upstream lento | servidor Node que nunca responde, em `127.0.0.1:9998` | ver §2.5 |
| nginx / promtool / actionlint / alloy | **imagens oficiais em container** (§3) | ver §3 |
| Browser | **indisponível** — `browser.disconnected`, nenhuma aba conectada | §2.6 |

Tokens usados (valores inventados por mim, só neste ambiente):
`OBSERVABILITY_HEALTH_TOKEN=TOK_HEALTH_abc123ZZZ`,
`OBSERVABILITY_METRICS_TOKEN=TOK_METRICS_xyz789QQQ`,
`ANALYTICS_CONSENT_SIGNING_KEY=chave-de-teste-para-verificacao-independente-0001`.
Nenhum deles aparece em log, banco, métrica ou telemetria (§4).

---

## 1. Backend — comandos da CI, saída real

### 1.1 `manage.py check`

```
$ cd backend && DJANGO_DB_ENGINE=postgresql ... .venv/bin/python manage.py check
System check identified no issues (0 silenced).
CHECK_EXIT=0
```

### 1.2 `makemigrations --check --dry-run`

```
$ cd backend && ... .venv/bin/python manage.py makemigrations --check --dry-run
No changes detected
MAKEMIG_EXIT=0
```

### 1.3 Suíte completa — **o comando exato da CI**

Extraí o comando de `.github/workflows/ci.yml` (job `backend-tests`, passo
final) e rodei com as mesmas variáveis de ambiente do serviço `postgres` do
workflow (Postgres 16, `DJANGO_DEBUG=true`, sem `DJANGO_CACHE_BACKEND=locmem`):

```
$ python -m pytest -q --cov=. --cov-report=term-missing --cov-fail-under=80
...
Required test coverage of 80% reached. Total coverage: 91.08%
834 passed, 298 warnings in 148.41s (0:02:28)
PYTEST_EXIT=0
```

**Cobertura: 91,08 %** (gate 80 %). Cobertura dos módulos que a run criou ou
tocou:

| arquivo | cobertura | linhas não cobertas |
|---|---|---|
| `config/health.py` | **96 %** | 189-190, 192, **201**, 290, 328, 346, 485 |
| `config/middleware.py` | **96 %** | 166-169, 212, 258-259 |
| `config/observability.py` | 88 % | 29 linhas |
| `config/observability_views.py` | 94 % | 72, 104-107, 202-203 |
| `config/metrics.py` | 94 % | 15 linhas |
| `config/job_state.py` | 89 % | 14 linhas |
| `config/proxies.py` | 89 % | 7 linhas |
| `metricas/consent.py` | 92 % | 23 linhas |
| `metricas/tasks.py` | 96 % | 112-118 |

> A linha **`health.py:201`** é a única do `check_celery` não coberta, e é
> exatamente a linha do defeito do §4.1. O próprio relatório de cobertura é
> evidência de que o caminho de produção nunca foi exercitado.

---

## 2. Comportamento — o que vale mais que o acima

### 2.1 `/livez` e `/readyz` se comportam diferente com o banco fora

Servidor real, Postgres **derrubado** (`docker stop obs-pg`):

```
ANTES:  livez=200  readyz=200
DEPOIS (banco fora):
  GET /livez   -> HTTP/1.1 200 OK
                  X-Operational-State: degraded
                  {"status": "alive"}
  GET /readyz  -> HTTP/1.1 503 Service Unavailable
                  X-Operational-State: degraded
                  {"status": "unavailable", "ready": false}
```

O `/readyz` **não expõe `str(exc)`**: o corpo tem 2 chaves, sem host, sem nome de
check, sem traceback. A causa fica no privado, como projetado:

```
  GET /health-detail (token certo) -> HTTP 503
    postgresql  -> error | OperationalError: connection to server at "localhost" (127.0.0.1), port 5432 failed: Connection refused
    migrations  -> error | (idem)
    redis       -> ok
```

O `/healthz` legado também foi fechado (critério 28): `{"status":"erro"}` + 503
com o banco fora, sem detalhe.

### 2.2 `/health-detail` e `/metrics` **não** vazam para quem não tem token

Origem **não-loopback** (LAN `192.168.1.64`, o próprio IP da máquina), para não
cair no atalho de loopback:

| requisição | `/health-detail` | `/metrics` |
|---|---|---|
| **sem token** | `404` `{"detail": "Not found."}` | `404` `{"detail": "Not found."}` |
| **token errado** (`TOK_HEALTH_ERRADO_zzz`) | `404` | `404` |
| **token certo** | `200` + payload completo | `200`, 15 736 bytes |

Antiblob de 500 (o `before_send` do revisor e o `try/except` do remediator
sustentam):

```
Authorization: Basic ZGV2OnNlcmV0YQ==   -> 404   (não 500)
Authorization: Bearer çéé                -> 404   (não 500)
Authorization: BearerTOK_METRICS_...    -> 404   (sem espaço)
```

`/metrics` com o banco fora **não vaza** host, porta, nome do banco nem DSN:

```
  'localhost' 0 | '5432' 0 | 'brd_portal_noticias' 0 | 'Connection refused' 0
  'OperationalError' 0 | 'TOK_METRICS' 0 | '127.0.0.1' 0
  ('postgres' -> 37, todas em dependency="postgresql", que é o NOME do check)
```

### 2.3 Fluxo de consentimento — os quatro casos exigidos

`POST /api/metricas/consent/` emite; `POST /api/metricas/eventos/` consome.

| caso | resposta | persistiu? |
|---|---|---|
| **sem token** | `202 {"registrado":false,"motivo":"consent_ausente"}` | não |
| **token válido** (header `X-Consent-Token`) | `201 {"registrado":true}` | **sim** |
| **token adulterado** (1 caractere da assinatura trocado) | `202 ... "consent_assinatura_invalida"` | não |
| token de outra sessão | `202 ... "consent_sujeito_invalido"` | não |
| token expirado (iat/exp no passado, HMAC válido) | `202 ... "consent_expirado"` | não |
| tipo desconhecido + campo excessivo | `400 {"detail":"Tipo de evento desconhecido.","motivo":"tipo_desconhecido"}` | não |

Contagem no banco antes e depois: **1 evento persistido, o do token válido, e
nenhum outro**. A linha persistida prova a sanitização:

```
sessao=sessao-teste-001  tipo=page_view  path=/politica
extra={"ok": "valor", "email": "[REDACTED]", "token": "[REDACTED]"}
```

O `path` enviado era `/politica?token=SEGREDO123` → a query string foi removida.
O `extra` enviado trazia `hacker@evil.example` e `token: abc` → ambos redigidos.

Além disso, rodei os **7 testes de integração opt-in contra o backend real** (os
que a CI pula de propósito):

```
$ B2_INTEGRACAO=1 B2_API_BASE=http://127.0.0.1:8011 \
  NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8011 npx vitest run testes/integracao-backend.test.ts
  ✓ o cliente aceita o envelope que o emissor real devolve
  ✓ SEM token o backend recusa e nao persiste (criterio 26)
  ✓ COM token o backend persiste o evento (criterios 25 e 26)
  ✓ token de outra sessao e recusado (o token nao e bem publico)
  ✓ token adulterado e recusado (a assinatura e verificada no servidor)
  ✓ o track() do analytics ANEXA o token ao evento (o caminho real do portal)
  ✓ o evento com token e aceito de verdade pelo backend
  Tests  7 passed (7)
```

### 2.4 Correlação ponta a ponta

**(a) ID conhecido, via o proxy real (Next 3001 → Django 8011):**

```
enviado:  e2e-correlacao-1790373413
resposta: x-request-id: e2e-correlacao-1790373413     <- IGUAL
          x-service: portal-api | x-environment: development | x-release: local
          x-operational-state: degraded
```

Com uma requisição que **gera log** (404), o mesmo id aparece no log JSON do
Django:

```
$ curl -H "X-Request-ID: e2e-404-correlacao-1790373423" .../api/feed/nao-existe/
x-request-id: e2e-404-correlacao-1790373423
$ grep -c 'e2e-404-correlacao-1790373423' backend2.log     -> 1
{"...","request_id": "e2e-404-correlacao-1790373423", "task_id": "-", "message": "Not Found: /api/feed/nao-existe/"}
```

> Nota honesta: num **200** o id não aparece no log — não há linha de log para
> requisição de sucesso, por desenho (o run diz que log por request seria custo
> sem valor). O critério 18 fala em "quando aplicável".

**(b) ID inválido, longo, com controle, e ausente:**

| entrada | `X-Request-ID` na resposta |
|---|---|
| ausente | `48151ce1-ed01-4054-8777-531861f31a7f` (UUID v4) |
| `abc<TAB>def` (controle) | `fdbe4381-187d-4eb7-ab72-00dc97c817cd` (UUID) |
| 65 caracteres | `da3bf1c8-dfbf-4ead-9c61-f0b669bbd42b` (UUID) |
| 64 caracteres (limite) | `yyyy…` preservado |
| via proxy, com controle | `b2f55f3a-5e18-4376-809e-00c61636ed49` (UUID) |
| via proxy, ausente | `3af29e33-e0f9-4f64-b1cf-8beb379147bc` (UUID) |

Não há truncamento, logo não há colisão no índice unique.

**(c) O `ApiError` do cliente, em runtime** — exercitei `lib/api.ts` real contra
o backend real, com config de vitest temporária **fora do repositório**
(`/tmp/opencode/obs-test/`):

```
PROVA_404  status=404 requestId=cfc59039-80ce-49f2-901b-0c627cbe7212 operacional=degraded motivo=http
PROVA_400  status=400 requestId=0625820b-d56b-4060-8d7e-f6c420ee4efd detail={"detail":"Token de verificação inválido ou expirado."}
PROVA_UUID_GERADO requestId=98fcb487-dff8-4bba-b2f0-68a377555811
```

E o `0625820b-…` **está no log do Django** com o mesmo valor
(`Bad Request: /api/auth/verificar-email/`). Note que o 400 **não** tem
`request_id` no corpo: o código de suporte vem do header, como o contrato exige.

**(d) O código de suporte realmente aparece na tela.** Com o feed fora do ar
(Next 3002 → upstream morto), a Home renderizada contém:

> "Sem notícias no momento · Não conseguimos falar com a base de notícias.
> **Não exibimos conteúdo de exemplo** — volte em instantes ou confira o arquivo.
> · **código de suporte: 07c50d34-fac9-438c-bb32-9abf8e49a734** · Nenhuma notícia
> real disponível para exibir agora. Preferimos mostrar isto a mostrar conteúdo
> inventado."

Verificado por extração de texto do HTML: `MOCK` ausente, "dados de exemplo"
ausente, "conteúdo de exemplo" presente **só** na frase honesta "Não exibimos
conteúdo de exemplo".

### 2.5 O proxy do frontend: teto de body, 504 vs 502

`next start` de produção em três portas, cada uma com um `API_INTERNAL_URL`
diferente:

| cenário | resultado |
|---|---|
| body de **17 825 792 bytes** (> 16 MB) com `content-length` | **`413`** + `{"detail":"Arquivo ou formulário maior que o limite aceito (16 MB)…","request_id":"6196d5ca-…"}` |
| o **mesmo** corpo em `Transfer-Encoding: chunked`, **sem** `content-length` | **`413`** + `request_id: dd2f124a-…` |
| body de 1 000 bytes | passa ao Django (`202 {"registrado":false,…}`) |
| upstream **lento** (nunca responde), `API_PROXY_TIMEOUT_MS=2000` | **`504`** em `time_total=2.008s` — "O servidor demorou demais para responder" |
| upstream **fora do ar** (nada escutando em 9999) | **`502`** em `time_total=0.009s` — "Não foi possível conectar ao servidor" |

Não houve estouro de tempo indefinido em nenhum caso. O log do Next registra o
desfecho com `requestId`, `metodo`, `rota` **sem query string**, `status` e
`motivo` (`timeout` / `conexao`), e o `X-Request-ID` do header bate com o
`request_id` do corpo em todos os quatro.

### 2.6 O que **não** deu para provar em browser

`tools.browser.tabs.open` respondeu `browser.disconnected` — **não há browser
conectado a esta sessão**. Não pude exercitar em navegador: o error boundary do
App Router capturando uma exceção real, a tela de recuperação com `reset()`, o
`reset()` aparecendo depois de um erro de chunk, e o evento de Web Vitals. Isso
está registrado como **não verificável** no critério 4 (e qualificado no 5 e 27,
onde a parte de runtime que importa — o `before_send` do Sentry no backend — foi
provada em runtime).

---

## 3. Frontend, infra e CI

### 3.1 `npm run verificar`

```
NPM_VERIFICAR_EXIT=0
  lint        -> "✔ No ESLint warnings or errors"      (--max-warnings 0)
  typecheck   -> tsc --noEmit, sem saída
  test        -> Test Files 6 passed | 1 skipped (7)
                 Tests  82 passed | 7 skipped (89)
  test:conteudo-ficticio -> todos [OK], 18 páginas + 67 arquivos em app/ + 41 em lib/
  test:query-client     -> 8 [OK]
  test:datas-tz         -> 1 [OK]
```

### 3.2 Cada `verificar-*.mjs` individualmente

```
node scripts/verificar-conteudo-ficticio.mjs   EXIT=0
node scripts/verificar-query-client.mjs        EXIT=0
node scripts/verificar-datas-tz.mjs            EXIT=0
TZ=Asia/Tokyo node scripts/verificar-datas-tz.mjs  EXIT=0
TZ=UTC        node scripts/verificar-datas-tz.mjs  EXIT=0
```

### 3.3 A guarda de conteúdo fictício **realmente falha** com um MOCK

**Mutação 1 — reinseri um array `MOCK` em `frontend/app/page.tsx`:**

```
$ npm run test:conteudo-ficticio
[VIOLAÇÃO] frontend/app/**: sem array/objeto/texto de demonstração — 1 achado(s):
      - app/page.tsx:227 — array de demonstração (MOCK*) ("MOCK_PUBS")
1 verificação(ões) em VIOLAÇÃO da política de conteúdo real.
EXIT=1
```

**Mutação 2 — recoloquei o `catch` que engole falha dentro de `carregarHome`
(`lib/recomendacao.ts`):**

```
[VIOLAÇÃO] lib/recomendacao.ts: carregarHome existe e propaga falha — carregarHome
tem `catch` devolvendo seção/lista vazia — todo tratamento de erro das páginas que
a consomem vira código morto e o fallback fictício volta
EXIT=1
```

**Restauração (duas vezes), com prova por hash e por `git status`:**

```
antes da mutação 1: 01c4b21552a27f6cc188e471ff16ed416fc2e8268a5a1c1e804be523e1899fe1  app/page.tsx
depois da mutação : 9411ba449dae514af8b42700aef58d96e41d916db4df880ee668155b8fe60e6b
após restaurar   : 01c4b21552a27f6cc188e471ff16ed416fc2e8268a5a1c1e804be523e1899fe1  ✔
git status --porcelain app/page.tsx                -> (vazio)  ✔
npm run test:conteudo-ficticio                     -> EXIT=0   ✔

antes da mutação 2: 5201da44ea82cb16cab73de96c205ee64f09151f2658ee891584f4087a579a40  lib/recomendacao.ts
após restaurar   : 5201da44ea82cb16cab73de96c205ee64f09151f2658ee891584f4087a579a40  ✔
git status --porcelain lib/recomendacao.ts         -> (vazio)  ✔
npm run test:conteudo-ficticio                     -> EXIT=0   ✔
```

A guarda morde nos dois formatos e o repositório voltou ao estado inicial.

### 3.4 `npm run build`

**Primeira execução: exit 1**, com `Error: Cannot find module './8838.js'`.
**Atribuição honesta: a falha foi minha**, não da run — eu estava mutando
`app/page.tsx` e `lib/recomendacao.ts` *enquanto* o build rodava, o que
inconsistente o grafo de chunks. Reiniciei limpo, sem mutação concorrente:

```
$ rm -rf .next
$ NEXT_PUBLIC_API_BASE_URL=http://localhost:8000 NEXT_PUBLIC_SITE_URL=http://localhost:3000 npm run build
  ✓ Compiled successfully
  ✓ Generating static pages (56/56)
  ... 56 rotas
BUILD_EXIT=0
```

**254 arquivos `.map`** em `.next` e `node_modules/.bin/sentry-cli` presente —
as duas condições que o gate de source map da CI exige.

> Observação de efeito colateral, não de falha: durante a geração das páginas
> estáticas o SSR tentou chamar a API (que eu havia apontado para a porta 8000,
> sem serviço) e registrou `motivo: 'conexao'` em ~10 rotas — **sem quebrar o
> build**. Isso confirma que a falha de API no SSG não é convertida em erro de
> build nem em conteúdo fictício.

### 3.5 `scripts/observability/validar-infra.sh --estrito`

```
VALIDAR_INFRA_EXIT=0
  57 OK, 0 AVISO, 1 PENDENTE DECLARADA, 1 PULADO, 0 FALHOU
  Pendência: runbook-url-placeholder  (runbook_url em domínio RFC 2606 .invalid)
  PULADO: shellcheck não instalado
```

Cobertura do gate: `bash -n` + bit de executável em 6 scripts · 6 JSON
(parse + "importável" em 4 dashboards, checks Better Stack, lifecycle R2) ·
61 queries de painel/alerta extraídas · 2 YAMLs de alerta (6 + 13 regras, todas
com `severity`, `runbook_url`, `description`, sem nome duplicado) · **nginx -t**
· 4 units systemd via `systemd-analyze verify` + 4 asserções de hardening por
unidade · `docker compose config` + 4 validações de healthcheck ·
`alloy validate` · varredura de segredo.

### 3.6 `nginx -t` (em container, método declarado)

Não há binário `nginx` no host. **Método:** imagem oficial `nginx:alpine`,
renderizando os três site confs com os marcadores de domínio substituídos
(teste Automatic + chaves auto-assinadas) e um `nginx.conf` mínimo que inclui
`http-cache.conf` + os três sites, exatamente como o gate faz:

```
nginx: the configuration file /etc/nginx/nginx.conf syntax is ok
nginx: configuration file /etc/nginx/nginx.conf test is successful
NGINX_T_EXIT=0
```

O valor de `X-Forwarded-For` confere **13/13 upstreams em cada um dos três
ambientes**, e é `$proxy_add_x_forwarded_for` (anexa) nos 39 — que é a condição
de que depende a correção do MAJOR-1 do throttle (ver §4.3).

### 3.7 `promtool`

```
$ docker run --rm --entrypoint promtool -v .../alerts:/alerts:ro prom/prometheus check rules ...
Checking /alerts/regras-disponibilidade.yaml
  SUCCESS: 6 rules found
Checking /alerts/regras-operacao.yaml
  SUCCESS: 13 rules found
PROMTOOL_CHECK_EXIT=0
```

**`promtool test rules` NÃO PODE RODAR: não existe nenhum arquivo de teste de
regras no repositório** (`find infra -name '*test*'` → vazio). As 19 regras não
têm teste unitário de expressão. Nenhum `promtool test` foi executado, e nenhum
resultado deve ser lido como "as regras foram testadas". Isso é uma lacuna
concreta do critério 22 (o alerta é validado **estruturalmente**, nunca
**comportamentalmente**).

### 3.8 Os 6 workflows — **sobre o conteúdo commitado**

`ci.yml` e `rollback.yml` estão limpos na árvore; os outros 4 têm WIP alheio.
Extraí os 6 de `HEAD` para fora do repositório e validei:

```
PARSEOK  ci.yml           jobs= ['backend-tests', 'frontend-build', 'infra-validate']
PARSEOK  deploy-dev.yml   jobs= ['deploy-dev']
PARSEOK  deploy-homolog.yml jobs= ['deploy-homolog']
PARSEOK  deploy-prod.yml  jobs= ['pre', 'deploy-prod', 'release']
PARSEOK  deploy.yml       jobs= ['verify', 'deploy', 'validate']
PARSEOK  rollback.yml     jobs= ['prepare', 'rollback']
YAML_COMMITADO_EXIT=0
```

### 3.9 `actionlint`

Não há binário local; usei a imagem oficial `rhysd/actionlint:1.7.7` com o repo
commitado montado (o primeiro uso, sobre a árvore de trabalho, falhou com
`no project was found` — o `--entrypoint`/mount errados; e sobre a árvore
contaminada o resultado seria irrelevante).

```
$ docker run --rm -v <repo-commitado>:/repo:ro -w /repo rhysd/actionlint:1.7.7
.github/workflows/ci.yml:248:9: shellcheck reported issue in this script:
  SC2153:info:14:10: Possible misspelling: SENTRY_ORG may not be assigned.
  Did you mean SENTRY_URL?  [shellcheck]
ACTIONLINT_EXIT=1
```

**Um único achado, e é falso positivo:** `SENTRY_ORG` é atribuído no bloco
`env:` do próprio passo, que o shellcheck embutido do actionlint não enxerga.
Nenhum erro real de workflow. Vale registrar, porém, que o
`validar-infra.sh` marca `shellcheck` como **PULADO** (não instalado): se o
shellcheck estivesse disponível no CI, ele produziria esse mesmo aviso e o gate
continuaria verde — o que é o comportamento correto para um `info`, mas mostra
que a análise estática de shell da run **não roda no CI**.

### 3.10 `alloy validate`

```
$ docker run --rm -v .../alloy:/etc/alloy:ro grafana/alloy:latest validate /etc/alloy/config.alloy
EXIT=0   (0 bytes de saída — o validate é silencioso no sucesso)
```

### 3.11 Terraform

**Não há nenhum `.tf` no repositório** — o gate reporta
`PULADO: nenhum arquivo .tf no repositório (nada que validar)`. O critério 40
inclui Terraform na lista; não há Terraform para validar, e nenhum
`backend/`+`provider` foi provisionado.

---

## 4. O que eu tentei quebrar

### 4.1 `check_celery` **nunca pode dizer "ok"** — achado novo, com prova de runtime

`backend/config/health.py:195-204` (commit `5e7fe90`):

```python
respostas = app.control.inspect(timeout=timeout).ping() or []
# `ping()` devolve uma LISTA de dicts {nome_do_worker: {"ok": "pong"}}.
if not isinstance(respostas, (list, tuple, set)):
    respostas = []
if not respostas:
    return "degraded", "no Celery worker replied", {"workers": 0}
return "ok", "", {"workers": len(respostas)}
```

O comentário está errado para a versão pinada. Com um worker real no ar
(Redis 7 + Celery 5.6.0, o mesmo `celery==5.6.0` de `requirements-lock.txt`):

```
$ celery -A config worker --concurrency=1 &   # no ar, respondendo
$ python -c "... app.control.inspect(timeout=3.0).ping() ..."
  inspect().ping() devolveu : {'celery@alex-buttielie-Latitude-5450': {'ok': 'pong'}}
  type(r)                  : dict -> isinstance list/tuple/set = False
  health.check_celery()    : status=degraded detail='no Celery worker replied' meta={'workers': 0}
```

O `ping()` respondeu **pong**, e o check disse **degraded, 0 workers**. Confirmei
que é a API da biblioteca, não o ambiente:

- docstring do `celery.app.control.Inspect.ping` na 5.6.0, instalada:
  `Returns: Dict: Dictionary {HOSTNAME: {'ok': 'pong'}}`;
- a mesma coisa em três timeouts (0,35 s / 1,0 s / 3,0 s) — não é timeout;
- o `inspect().getsource(Inspect.ping)` no ambiente devolve `dict`.

**E o teste que deveria pegar isso prova o contrário.** Em
`backend/config/tests/test_health_checks.py:281-296`
(`test_celery_com_worker_responde_conta_sem_vazar_nome`), o mock devolve
`[{"celery@host-interno-da-vps": {"ok": "pong"}}]` — **uma lista**, forma que a
biblioteca nunca produz. O teste passa verde (`assert resultado.status == "ok"`)
numa forma impossível. E a cobertura confirma: **`health.py:201`
(`respostas = []`) é a única linha do bloco não coberta** da suíte inteira.

**Consequência operacional, nos dois sentidos:**

- `check_celery` **jamais** retorna `ok` → o agregado fica `degraded`
  permanentemente → **toda** resposta carrega `X-Operational-State: degraded` e
  `portal_degraded_responses_total{reason="optional-dependency"}` conta tráfego
  normal como degradação (medido: 38 no meu teste, com tudo saudável exceto o
  worker);
- a regra `PortalDependenciaOpcionalIndisponivel` (warning) fica **sempre** acima
  do limiar, o que é o caminho natural para alguém silenciá-la — e aí uma queda
  real de Celery passa sem alerta.

**Não estava em nenhum dos dois relatórios de revisão.** Varri
`code-review-backend.md`, `code-review-contract.md` e
`remediacao-backend.md` por `ping`/`check_celery`/`no Celery worker replied`: a
única ocorrência é `check_celery_jobs`, sem relação. O próprio
`remediacao-backend.md:446` registra `degraded_state → {'status': 'degraded',
'reasons': ('celery:degraded', …)}` como se fosse o estado correto — o
remediator não tinha worker no ar, então "celery:degraded" era indistinguível de
um bug. **Só se vê com um worker real respondendo.**

**Corroboração de que a intenção era outra:** o `docker-compose.yml` faz o mesmo
ping e usa `len(resp)`, que funciona para `dict`:

```python
resp = app.control.inspect(timeout=5).ping() or {};
sys.exit(0 if resp else 1)
```

Ou seja: o healthcheck do compose diria "healthy" com o worker vivo, enquanto
`/health-detail` diria "degraded" para o mesmo worker. Duas leituras do mesmo
`ping`, uma certa e uma errada.

### 4.2 Dois painéis e **duas regras de alerta** cites métricas que não existem em scrape nenhum

Com um worker real que executou 4 tasks com `SUCCESS` (gravadas no arquivo
durável), o `/metrics` do processo web expôs **11 séries** de job:

```
portal_job_state_age_seconds                       40.0
portal_job_task_duration_seconds_count{task="metricas.tasks.expurar_analytics"} 1
portal_job_task_duration_seconds_sum{task="…"}     0.368
portal_job_task_idle_seconds{task="…"}             40.0
portal_job_task_retries_recorded{task="…"}         0
portal_job_tasks_recorded{result="SUCCESS",task="…"} 1
```

E **zero** das métricas que os painéis e as regras usam:

```
$ grep -c 'portal_celery_tasks_total' metrics-com-worker2.txt    -> 0
```

Cross-check com o inventário declarado no código: as 6 séries
`portal_celery_*` / `portal_ingestion_executions_total` /
`portal_job_task_idle_seconds` citadas por alertas/painéis **existem todas no
registro do backend** — o que faz o gate passar. O `validar-infra.sh` extrai o
inventário com `grep -ho '"portal_[a-z_]*"' backend/config/metrics.py
…` — ou seja, **confere o NOME declarado no fonte, nunca a exposição em runtime**,
e imprime `[OK] métricas usadas em painel/alerta conferidas contra o inventário do
backend`. Esse OK afirma mais do que verifica.

Afetados: `PortalCelerySemExecucao` (critical),
`PortalCeleryTaskFalha` (warning), e 6 queries em
`portal-filas-celery.json` + `portal-ingestao.json`. Em
`sum(...)` sobre vetor vazio, `== 0` também é vetor vazio: **a regra não
dispara**. Sem painel vermelho e sem sintoma.

*Justiça:* o run **sabia**. O comentário de `regras-operacao.yaml:100-110` (do
commit D2) diz que `portal_celery_tasks_total` "não aparece em nenhum scrape" e
migra `PortalJobAtrasado`/`PortalJobNuncaConcluiu` para `portal_job_task_idle_seconds`,
que funciona. O defeito é que as duas regras antigas ficaram no arquivo com
anotação descrevendo comportamento, e o gate verde cobre a inconsistência. O
`README` de `infra/observability/` chega a dizer que "o proxy honesto é a task de
ingestão em `portal_celery_tasks_total`" — o que também é falso pelo mesmo
motivo. (O revisor completo tratou isto como MAJOR-1 dele; eu acrescento a
medição com worker real e o caso do `check_celery`.)

### 4.3 "Backup verde sem destino" — o watchdog fecha com verde quando o objeto sumiu do bucket

`pg_backup_pm2.sh` (o **produtor**) é fail-closed de verdade: exit 20 sem
`BACKUP_S3_BUCKET`, exit 19 se `head-object` do S3 falhar ou divergir de tamanho,
exit 21 se o heartbeat do Better Stack não responder, e o marcador
`.ultimo-backup-ok` é escrito **depois** da verificação remota. O problema está no
**consumidor**, `verificar_backup.sh`, que é quem detecta a deriva no dia
seguinte. Rodei os 9 estados; 7 fecham corretamente:

| estado | `status` | exit |
|---|---|---|
| sem marcador e sem dump | `nunca-executou` | 2 |
| dump local sem marcador de sucesso | `atrasado` | 1 |
| marcador com `remoto=ausente` | `sem-destino` | 1 |
| marcador atual, `remoto=confirmado` | `ok` | 0 |
| marcador de 30 h (limite 26 h) | `atrasado` | 1 |
| `BACKUP_MAX_AGE_HOURS=abc` | `indisponivel` | 3 |
| bucket declarado sem AWS CLI | `indisponivel` | 3 |
| **marcador diz `remoto=confirmado`, objeto AUSENTE no bucket (head-object 404)** | **`ok`** | **0** |
| marcador ok mas **dump local apagado** | `ok` (com `"dump": null`) | 0 |

Estado 8, na íntegra (com um stub de `aws` que devolve 404, fora do repositório):

```
[backup-watchdog] ERRO: head-object em s3://meu-bucket-r2/db/pm2-db-20260925.dump falhou:
                  o último backup CONFIRMADO não está mais no bucket
[backup-watchdog] OK: backup dentro do prazo
{"status":"ok", "idade_horas":0, "motivo":"backup dentro do prazo",
 "remoto_confirmado":false, "max_age_horas":26, …}
EXIT=0
```

O `stderr` diz a verdade; a **última linha em JSON — que o cabeçalho do próprio
script declara ser a saída para consumo por máquina — diz `ok`, e o exit code é
0**. O bloco de veredito consulta `REMOTO_CONFIGURADO == "ausente"` e nunca
consulta `REMOTO_CONFIRMADO`. A intenção de falhar fechado está demonstrada no
caso 7 (AWS CLI ausente → exit 3); falta o mesmo tratamento para o objeto
inexistente. O comentário do próprio script afirma o oposto do que o código faz
("um marcador com dump apagado embaixo é motivo para desconfiar, não motivo
para ficar tranquilo"). Isto é literalmente o tema da run.

### 4.4 Garantias de privacidade que segurei

Payload com e-mail, token, `Authorization` e query string sensível, ponta a
ponta:

```
enviado:  path=/politica?token=SEGREDO123
          extra={"email":"hacker@evil.example","token":"abc"}
          header Authorization: Token 0123456789abcdef0123456789abcdef01234567
          cookie sessao=1 ; query_string=token=SEGREDO
```

| superfície | varredura | resultado |
|---|---|---|
| `pg_dump` do banco inteiro (59 282 bytes) | `hacker@evil.example`, `SEGREDO123`, `TOK_HEALTH_abc123ZZZ`, `TOK_METRICS_xyz789QQQ`, `chave-de-teste…`, `eyJjYXRlZ29yaWE` (prefixo do token) | **0 ocorrências cada** |
| log JSON do backend (41 linhas reais) | os mesmos 6 + `Authorization` + `consent_` | **0 ocorrências cada** |
| `/metrics` (15 736 bytes) | id do consentimento, `Bearer abc.def.ghi`, `sessao=1`, `hunter2`, `203.0.113.9` | **0** |
| evento do Sentry depois de `before_send` | `SEGREDO`, `hacker@evil.example`, `Bearer abc.def.ghi`, `sessao=1`, `hunter2`, token DRF de 40 hex, `203.0.113.9` | **todos ausentes**; `user`, `headers`, `cookies`, `query_string`, `data` removidos; sobraram `environment`, `release` e `tags{service,environment,release}` |
| `ApiError` no cliente | token de teste no `message`/`detail`/`stack` | **ausente** |

`redact_text` em runtime, 6 casos:

```
'analytics: token de consentimento NÃO emitido (motivo=%s)' -> 'analytics: token [REDACTED] consentimento NÃO emitido (…)'
'GET /x?token=SEGREDO&email=a@b.com Authorization: Bearer abc.def.ghi'
      -> 'GET /x?token=[REDACTED]&email=[REDACTED_EMAIL] Authorization=[REDACTED]'
'Cookie: sessao=abc123; csrf=def456'   -> 'Cookie=[REDACTED]'
'Authorization: Basic ZGV2OnNlcmV0YQ=='-> 'Authorization=[REDACTED]'
'senha: hunter2 email da pessoa exemplo@dominio.com.br'
      -> 'senha=[REDACTED] email da pessoa [REDACTED_EMAIL]'
'/api/x?redirect=https://evil.example/?t=abc' -> '/api/x?redirect=https://evil.example/?[REDACTED]'
```

**Seguraram.** Um falso positivo cosmético, que registro como nit e não como
vazamento: o regex `_AUTH_SCHEME` casa `token de` (o `de` casa
`[A-Za-z0-9._~+/=-]{2,}` com IGNORECASE), então a própria mensagem de WARNING da
run vira `analytics: token [REDACTED] consentimento NÃO emitido`. O operador lê
"um token foi redigido" num log onde nenhum token estava. Redigir demais é
preferível a vazar, mas aqui degrada a legibilidade de um diagnóstico.

### 4.5 MAJOR-1 (throttle furado por `X-Forwarded-For`): **corrigido, e confirmei por execução**

40 POSTs no emissor de token de consentimento, `X-Forwarded-For` girando a cada
requisição, em dois cenários:

```
A) peer NÃO-loopback (203.0.113.10), XFF girando        -> {400: 30, 429: 10}
B) peer loopback, XFF no formato que o Nginx produz
   depois de anexar ("<spoof>, <real>")                   -> {400: 30, 429: 10}
```

O limite age a partir da 31ª em ambos. (Os 400 são do meu `sessao` curto demais,
`MIN_SUB_LEN=6` — irrelevante para o throttle, que conta antes da validação.) E o
Nginx **anexa** (`$proxy_add_x_forwarded_for`) em 39/39 upstreams, que é a
premissa da correção. **Segurou.**

### 4.6 MAJOR-2 (cardinalidade de rótulo): **corrigido, e confirmei por execução**

60 requisições com 60 paths distintos e não resolvidos:

```
séries de portal_http_requests_total  antes=12   depois=12
rotulos de route gerados: api/feed/, api/metricas/consent/, livez, metrics,
                           health-detail, api/feed/cluster/<int:cluster_id>/, …
```

Zero séries novas, zero perda de série legítima, e `ROUTE_UNMATCHED` colapsa o
lixo de scanner. **Segurou.**

### 4.7 Batimento do beat: três estados, três vereditos

| estado do beat | `celery_beat` | agregado |
|---|---|---|
| arquivo de heartbeat **inexistente** | `error` "beat heartbeat file unreadable" | `degraded` |
| heartbeat **recente** | `ok` | `degraded` (por causa do `celery`, §4.1) |
| heartbeat com **3 601 s** (> limite 900 s) | **`degraded`** "beat heartbeat stale" `{"age_seconds": 3601.0}` | `degraded` |

O beat parado **aparece** como falha, e o endpoint privado detalha a causa —
critério 16 no ponto mais difícil. `portal_health_check_not_configured` distingue
`not_configured` (ponto cego) de `error`/`degraded` (sinal), que era o MAJOR-3
do backend. O beat também roda de verdade: o worker executou
`metricas.tasks.expurar_analytics` com `retencao_dias=365` vindo do schedule.

### 4.8 Expurgo de analytics: idempotente e auditável (critério 24)

```
antes:   metricas_eventosite=1  feed_eventobusca=3  feed_interacaonoticia=0
1ª execução (dias=0): removidos={'metricas.EventoSite': 1, 'feed.InteracaoNoticia': 0, 'feed.EventoBusca': 3}
                      total_removido=4  lotes={…: 1, …: 0, …: 1}  duracao_s=0.185
2ª execução (dias=0): removidos={…: 0, …: 0, …: 0}  total_removido=0  duracao_s=0.017
depois:  metricas_eventosite=0  feed_eventobusca=0  feed_interacaonoticia=0
```

Log de auditoria (JSON, com ambiente/release/request_id/task_id, **sem** path,
sessão ou usuário):

```
"expurgo de analytics concluido: corte=2026-09-25T21:55:31.335618+00:00
 retencao_dias=0 removidos={…} lotes={…} total_removido=4 duracao_s=0.185"
```

### 4.9 Bootstrap fail-closed (critério 31)

```
DEBUG=False + SECRET_KEY de fallback  -> ImproperlyConfigured  EXIT=1
DEBUG=False + DJANGO_DB_ENGINE=sqlite3 -> ImproperlyConfigured  EXIT=1
```

Mensagem segura: nome da variável e o que fazer, sem valor de segredo.

### 4.10 `run-standalone.sh`: o smoke falha de verdade

```
prepare sem .next/static   -> EXIT=64   (ERRO_AO_USAR)
smoke sem nenhum .js       -> EXIT=69   (FALHA_SMOKE)
smoke com a release real   -> EXIT=0
   GET /robots.txt -> 200
   GET /_next/static/chunks/13-9e3e520d88a77c9b.js -> 200
   GET / -> 200
```

O `.next/static` é copiado; o `public/` ausente produz aviso explícito e pasta
vazia (mesmo comportamento do `frontend/Dockerfile`). Não é rubber stamp.

### 4.11 Segredos em commit

Varri o diff inteiro (2 040 993 bytes) por padrões de credencial e por DSN/URL
com senha embutida:

```
AKIA… / sk-… / sk_live / glpat- / xox?- / ghp_ / github_pat_ / -----BEGIN … PRIVATE KEY-----
  -> 0 ocorrências
DSN Sentry real (https://<chave>@<org>.ingest.sentry.io/…)  -> 0
amqp://…:senha@ / postgres://…:senha@ / redis://:senha@    -> 0
```

O que casou é placeholder obviamente falso, e nenhum `.env` real está
versionado (`git ls-files | grep .env` → 4 arquivos `.example`; `backend/.env` e
`.env.localhost` são ignorados):

```
DJANGO_SECRET_KEY=troque-por-uma-chave-secreta-gerada
OBSERVABILITY_HEALTH_TOKEN=troque-aqui-por-um-valor-aleatorio-longo
ALLOY_LOKI_TOKEN=cole-aqui-o-token-de-escrita-do-loki
password="senha-de-teste-123"                      (fixture de teste)
const TOKEN = "a1b2c3d4e5f60718293a4b5c6d7e8f9012345678"  (valor sintético)
SENTRY_DSN=                                        (vazio)
```

**Nenhum segredo, DSN real, token ou credencial entrou nesta run.**

### 4.12 Coerência de `docker-compose.yml` / `subir-localhost.sh`

- `docker-compose.yml` **não está contaminado** (idêntico a `HEAD`) e é coerente
  com o entregue: os dois healthchecks que a run corrigiu (achado B11) não têm
  mais `|| exit 0`; o do worker usa `len(resp)` sobre o dict, que é a leitura
  correta; o do beat confere `/proc/1/cmdline` e a idade do schedule, com o
  comentário honesto de que isso prova o processo e não o agendamento.
- `subir-localhost.sh` **tem WIP alheio** e não foi tocado por esta run; o
  `git show HEAD:subir-localhost.sh` não referencia `celery`/`agendador`/
  observabilidade, ou seja, o bootstrap local **não** sobe worker/beat e não
  exercita o canal durável nem o heartbeat. Isso é uma lacuna de paridade entre
  o que a run promete e o que o atalho local entrega — mas o arquivo está sob
  WIP de outra run, então **não é falha desta run**; registro como observação.

---

## 5. Tabela dos 42 critérios

`passou` = comprovado por execução. `falhou` = comprovado que não atende.
`não verificável` = exige ambiente/credencial/tempo que este agente não tem.

| # | critério (resumo) | veredito | evidência |
|---|---|---|---|
| 1 | sem `X-Request-ID` → UUID seguro gerado, enviado, aceito | **passou** | `48151ce1-…` (curl) e `3af29e33-…` (via proxy) volta no header |
| 2 | ID válido no header, no `ApiError` e como código de suporte | **passou** | `e2e-correlacao-1790373413` idêntico no header e no log; `PROVA_404 requestId=cfc59039-…`; Home exibe "código de suporte: 07c50d34-…" |
| 3 | ID inválido/longo/com controle → UUID sem colisão | **passou** | tab→UUID, 65→UUID, 64 preservado, nos dois lados; 14 testes vitest |
| 4 | erro de renderização → Sentry + `reset()` | **não verificável** | `browser.disconnected`; código existe e passa tsc/lint, sem execução em browser |
| 5 | evento técnico sem consentimento → nenhum envio | **passou** | `before_send` devolve `None` sem consentimento; 32 testes de redação/Sentry verdes. *Caminho de browser não exercitado* |
| 6 | com consentimento: ambiente/release, sem token/e-mail/IP/URL sensível | **passou** | evento final com `environment`, `release`, `tags`; 7 segredos testados, 0 no payload |
| 7 | `/livez` vive, `/readyz` indisponível sem `str(exc)` | **passou** | banco derrubado: livez 200, readyz 503 `{"status":"unavailable","ready":false}` |
| 8 | `/readyz` 200 genérico com tudo disponível | **passou** | `{"status":"ready","ready":true}` |
| 9 | Redis/Celery fora → degradação registrada, metricada, alertada, detalhada | **falhou** | o lado "indisponível" funciona (`degraded_responses_total`, header, causa no privado), **mas `check_celery` nunca diz `ok`**: com worker real respondendo `pong` devolve `degraded`/`workers:0` (§4.1). O alerta fica permanentemente acima do limiar |
| 10 | cache real ≤5 min → conteúdo real + degradação, sem fictício | **não verificável (contenção)** | `backend/feed/views.py` é WIP da run `20260924-2136`; a run declara o header de idade/`cached_at` como follow-up com essa outra run |
| 11 | sem cache válido → **503** e nunca `MOCK` | **falhou** | "nunca MOCK" passa (Home honesta + guarda com mutação). O **503 não vem**: HTML sai **200**. A run declara isso impossível em Server Component; o 503 do backend depende do WIP alheio |
| 12 | nenhuma página com fallback fictício silencioso | **passou** | guarda barra MOCK e `catch` que engole; Home e Radar dizem "Não exibimos…"; 0 MOCK em 67+41 arquivos |
| 13 | disparo manual de ingestão com `queued/running/succeeded/failed`, task ID, request ID, duração, retries, erro | **falhou** | não existe tal registro. `POST /api/admin/robos/executar/` sobe uma **thread** e devolve 202; `RegistroExecucaoIngestao` só tem `executado_em` + contadores; **nenhuma migration nesta run**; nenhum literal `queued`/`running` no código. O `code-review-backend.md:463` já marca "não verificado" |
| 14 | métricas de fila, atraso, retry, falha e duração consultáveis no Grafana | **falhou** | com worker real e 4 tasks `SUCCESS`: 11 séries `portal_job_*` expostas, **0** de `portal_celery_tasks_total`/`portal_celery_task_duration_seconds*` — que são as 6 queries dos 2 painéis e 2 regras (§4.2) |
| 15 | segunda tentativa concorrente rejeitada/agrupada | **falhou** | nenhum mecanismo de lock no código commitado (`FileLock`/`fcntl`/flag de execução: 0 ocorrências) e a run não tocou `backend/catalogo_noticias` |
| 16 | worker/beat parados → falha/degradação + alerta | **passou** | beat sem arquivo → `error`; heartbeat de 3 601 s → `degraded "beat heartbeat stale"`; `not_configured` separado de `error` no gauge. *Ressalva: o ramo "celery" é coberto por §4.1* |
| 17 | dependência externa real → status/duração/resultado/erro sanitizado | **falhou** | `record_dependency(` é chamado **só** de `health.py:97`; Resend, ViaCEP/IBGE e fetch de feed não são instrumentados. A própria remediação classifica como MINOR-12 "não corrigido" |
| 18 | log com ambiente, serviço, release, request/task ID | **passou** | log JSON real: `environment`, `service`, `release`, `request_id`, `task_id`, `levelname` |
| 19 | Sentry backend: ambiente/release corretos, PII desabilitada | **passou** | `send_default_pii=False` em `settings.py:1160`; `before_send` fixa env/release e remove `user` |
| 20 | source maps enviados no CI, release = SHA | **não verificável** | o build gera **254 `.map`** e o `sentry-cli` existe (gate satisfeito); o **upload** exige conta Sentry real |
| 21 | logs JSON pesquisáveis no Grafana por request ID/release/serviço/nível | **não verificável** | os 4 campos existem no JSON (provado) e `alloy validate` passa; a ingestão no Loki exige Grafana Cloud provisioned |
| 22 | alerta deduplicado, com severidade, runbook e **destino e-p definido** | **falhou** | severidade + `for:` + `description` + `primeiro_passo` em 19/19 regras e `promtool` OK — mas **não há teste de expressão** (`promtool test rules` sem arquivos) e **não há destino**: `runbook_url` em domínio `.invalid` que nunca resolve (pendência declarada) e Contact Points são `<CP_CRITICO_PRINCIPAL>`/`<CP_CRITICO_SUPLENTE>`/`<CP_WARNING>` |
| 23 | Better Stack aciona sem depender da VPS | **não verificável** | `checks.json` com 7 checks + cron monitor do backup, validado e importável; URL é `https://<DOMINIO_DE_PRODUCAO>/…` |
| 24 | retenção 12 meses: expurgo idempotente e auditável | **passou** | 2 execuções: 4 linhas removidas, depois 0; log com corte/contagens/lotes/duração; worker executou com `retencao_dias=365` |
| 25 | payload com tipo desconhecido/campo a mais/token → recusado ou redigido, com sinal | **passou** | `400 tipo_desconhecido`; query string removida; `extra` redigido; 7/7 testes de integração com o backend real |
| 26 | token ausente/inválido/expirado → não persiste | **passou** | `consent_ausente` / `consent_assinatura_invalida` / `consent_expirado` / `consent_sujeito_invalido`; 1 linha no banco, a do token válido |
| 27 | consentimento técnico recusado → nenhum envio externo | **passou** | `before_send` → `None` sem consentimento (runtime). *Browser não exercitado* |
| 28 | query string sensível / Authorization / PII mascarados no log | **passou** | 6 casos de `redact_text`, 0 ocorrência de 6 segredos no log e no `pg_dump`, evento Sentry limpo, `ApiError` limpo |
| 29 | standalone com `HOSTNAME`, `PORT`, static e public | **passou** | `prepare`+`smoke` reais: `/robots.txt`, chunk de `.next/static` e `/` em 200; exit 64/69/0 corretos. *PM2 em si não instalado aqui*; a run registra pendência de decisão sobre o critério |
| 30 | smoke falha → symlink não muda, release anterior disponível | **não verificável** | a lógica está no `deploy.yml` commitado (smoke **antes** de qualquer troca; `ln -s`+`mv -T` atômico; `releases/previous`); o smoke é fail-closed (exit 69), mas "symlink não muda" exige deploy real |
| 31 | placeholder de secret → bootstrap falha com mensagem segura | **passou** | `ImproperlyConfigured` + exit 1 em ambos os casos |
| 32 | SSH por chave, senha removida após fallback documentado | **não verificável** | exige acesso à VPS; a run registra C2.6 como pendente de acesso |
| 33 | TLS validado externamente, renovação e alerta de expiração | **não verificável** | check `tls-producao` declarado no Better Stack; nenhum domínio real |
| 34 | backup diário no R2, **exit 0 só após validação**, alerta de atraso | **falhou** | produtor fail-closed de verdade; mas o **watchdog devolve `ok`/exit 0 com o objeto ausente do bucket** e com o dump local apagado (§4.3) |
| 35 | restore mensal verificado em ambiente isolado | **não verificável** | `infra/backup/RESTORE.md` existe (111 linhas); não executado |
| 36 | migration em produção com backup, homologação, smoke e rollback prévios | **não verificável** | a run **não adicionou migration nenhuma** — o critério fica sem objeto para este diff; a política está no `deploy.yml` |
| 37 | runbook com diagnóstico, consulta, recuperação, owner e escalonamento | **falhou** | **não existe arquivo de runbook no repositório**; os 19 `runbook_url` apontam para `runbooks.portal.exemplo.invalid` (RFC 2606, nunca resolve). Diagnóstico/consulta/recuperação existem **dentro** das annotations e a tabela severidade→canal→quem está no `alerts/README.md`, mas `owner`/escalonamento são só placeholders |
| 38 | CI de backend: testes, integração, migration check, coverage gate | **passou** | `check` 0 issues; `makemigrations --check` "No changes detected"; comando exato da CI → 834 passed, **91,08 %** ≥ 80 |
| 39 | CI de frontend: typecheck, lint, build, testes de erro/consentimento | **passou** | `npm run verificar` exit 0 (0 warnings de lint, tsc limpo, 82+7) e `npm run build` exit 0; 7/7 de integração com o backend real |
| 40 | CI de observabilidade valida Nginx/systemd/Compose/Terraform | **passou** | `validar-infra.sh --estrito` exit 0: `nginx -t` (imagem oficial), 4 units com `systemd-analyze verify`, `docker compose config`, `alloy validate`, 6 JSON, 2 YAML de alerta, `promtool check rules` 19 regras. *2 itens PULADO: `shellcheck` ausente e nenhum `.tf` no repositório* |
| 41 | entrega nos 3 canais confirmada e encerrada | **não verificável** | exige Sentry, Grafana Cloud e Better Stack |
| 42 | soak de 48 h sem incidente/regressão de SLO | **não verificável** | exige produção e 48 h |

### Resumo

- **passou: 21** — 1, 2, 3, 5, 6, 7, 8, 12, 16, 18, 19, 24, 25, 26, 27, 28, 29, 31, 38, 39, 40
- **falhou: 9** — 9, 11, 13, 14, 15, 17, 22, 34, 37
- **não verificável: 12** — 4, 10, 20, 21, 23, 30, 32, 33, 35, 36, 41, 42

---

## 6. O que só ambiente real prova, e não foi provado

Nada abaixo é falha da implementação. É o que impede declarar a run **entregue**.

1. **Primeiro deploy real** em dev/homolog/prod — nenhum dos 4 workflows de
   deploy foi executado; precisam de VPS, chaves e secrets.
2. **Release atômica com rollback real** — a lógica está no `deploy.yml`
   commitado e o smoke é fail-closed, mas a troca de symlink e o retorno à
   `releases/previous` nunca ocorreram.
3. **Celery sob systemd** — as 4 units passam no `systemd-analyze verify` e
   existem `NoNewPrivileges`/`ProtectSystem`/`Restart=on-failure`/`MemoryMax`; o
   `ExecStartPre` fail-closed não foi exercitado; o beat prove o processo, não o
   agendamento (a própria unit do heartbeat é que consulta a unit do beat).
4. **Entrega dos 3 alertas nos canais** (Sentry, Grafana, Better Stack) — e o
   encerramento/acknowledged do teste.
5. **TLS** — validação externa, renovação e alerta de expiração.
6. **SSH por chave** — conexão real e a remoção da senha só depois do
   fallback/rollback documentado.
7. **Backup em R2 e restore mensal** — sem bucket, sem objeto, sem restore; só a
   lógica fail-closed, exercitada com stub.
8. **Soak de 48 h** — precisa de produção e de tempo.

Some-se a isso o que o próprio contrato coloca fora do alcance de um agente:
**validação humana dos textos de consentimento e privacidade** ("código não
deve fingir aprovação jurídica") e a **decisão de orçamento** antes de passar de
~R$300/mês.

**Enquanto 32 dos 42 critérios dependem de execução real ou de conta externa
(12 não verificáveis + o que está no item 20/21/23/30 acima), a run não pode ser
declarada entregue** — por mais que o código esteja, no meu veredito, em boa
forma onde eu consegui exercitá-lo.

---

## 7. Achados que exigem decisão do dono do run

Priorizados por consequência observável. Os três primeiros são da família
"falso verde" que a run existe para eliminar, e os três **sobreviveram a dois
ciclos de revisão**.

| # | severidade | achado | onde | efeito |
|---|---|---|---|---|
| F1 | **major** | `check_celery` nunca retorna `ok`: `ping()` devolve `dict` na Celery 5.6.0 pinada, o código exige `list` | `backend/config/health.py:195-204`; teste que prova o oposto em `tests/test_health_checks.py:281-296`; `health.py:201` é a única linha do bloco não coberta | `X-Operational-State: degraded` em **toda** resposta; `PortalDependenciaOpcionalIndisponivel` sempre acima do limiar → somebody silences it → queda real de Celery passa sem alerta |
| F2 | **major** | 2 regras de alerta (1 critical) e 6 queries de painel usam `portal_celery_tasks_total`/`…_duration_seconds*`, que **não aparecem em nenhum scrape** | `regras-operacao.yaml:65,83`; `portal-filas-celery.json`; `portal-ingestao.json` | alertas que **nunca disparam**; 2 painéis que **abrem vazios** sem erro |
| F3 | **major** | o gate de métricas confere **nomes no fonte**, não exposição, e imprime `[OK]` | `scripts/observability/validar-infra.sh:277-307` | verde que cobre exatamente a classe de defeito que F2 é |
| F4 | **major** | watchdog de backup devolve `ok`/exit 0 com o objeto **ausente do R2** e com o dump local apagado | `infra/backup/verificar_backup.sh` (bloco de veredito) | "backup verde sem destino" — o tema da run, dentro da run |
| F5 | **major** | 9 critérios falham, 3 deles (13, 15, 17) **nunca foram implementados** nesta run e nenhum relatório de bloco os declara como pendência | 13, 15, 17, 34, 37 | DoD "todos os critérios implementados ou bloqueados **explicitamente**" não se cumpre para 13 e 15 |
| F6 | **minor** | nenhuma regra de alerta tem teste de expressão: `promtool test rules` não tem o que rodar | `infra/observability/alerts/` | alerta validado só estruturalmente |
| F7 | **minor** | `shellcheck` marcado PULADO no gate; o `actionlint` do repo emite SC2153 (falso positivo) que passaria se o shellcheck estivesse no CI | `validar-infra.sh:13` | análise estática de shell não roda no gate |
| F8 | **nit** | falso positivo de redação: a própria mensagem da run vira `analytics: token [REDACTED] consentimento NÃO emitido` | `metricas/consent.py` + `_AUTH_SCHEME` | diagnóstico enganoso num WARNING |
| F9 | **nit** | `subir-localhost.sh` (commitado) não sobe worker/beat, então o atalho local não exercita o canal durável nem o heartbeat | `git show HEAD:subir-localhost.sh` | paridade entre o prometido e o atalho — arquivo sob WIP de outra run, **não é falha desta** |

**Uma assimetria que merece nota:** a correção de F1 é de uma linha
(`isinstance(respostas, dict)` → `list(respostas)`) **e** exige corrigir o mock do
teste, que hoje codifica a forma errada como se fosse a real. É a demonstração
mais barata de que teste com mock de biblioteca pode afirmar o inverso do
comportamento — que é o mesmo tema da run.

---

## 8. Veredito final

# `passed_with_blocked_criteria`

**21 passou · 9 falhou · 12 não verificáveis.**

O que sustenta o veredito:

- **A espinha dorsal da run funciona, e por execução, não por leitura.**
  Correlação ponta a ponta (header = `ApiError` = log = código de suporte na
  tela), `/livez` vs `/readyz` com o banco derrubado, gating fail-closed de
  `/health-detail` e `/metrics` (404 sem token, token errado e não-ASCII, todos
  sem virar 500), consentimento assinado nos cinco modos de recusa, teto de body
  do proxy com e sem `content-length`, 504 vs 502 com tempo medido, redação de
  PII em log/banco/métrica/telemetria, expurgo idempotente, backup watchdog
  fail-closed em 7 de 9 estados, smoke do standalone com exit codes reais.
- **A suíte é verde de verdade:** 834 testes, 91,08 % de cobertura com o comando
  exato da CI e Postgres 16, e o `npm run verificar` + `npm run build` limpos.
- **Nenhum segredo real** entrou em nenhum dos 10 commits.
- **9 critérios falham, e 3 deles (13, 15, 17) nunca foram implementados** — não
  são defeitos, são ausência, e nenhum relatório de bloco os declara como
  bloqueio. Os outros 6 são reais e verificáveis, **3 deles da família "falso
  verde" que esta run existe para eliminar** (F1, F2, F4), dois dos quais
  sobreviveram a dois ciclos de revisão porque a evidência exigia um worker real
  no ar e um bucket com o objeto faltando.
- **12 critérios são genuinamente não verificáveis aqui** e nenhum deles é por
  defeito: 10 dependem de conta externa, VPS ou 48 h; 2 (4 e 10) dependem de
  browser conectado e de um arquivo sob WIP de outra run.

**Por que não `failed`:** nenhum caminho de corrupção de dados, vazamento de PII
ou indisponibilidade de produção foi encontrado, e a maior parte do contrato está
comprovadamente em pé. **Por que não `passed`:** o DoD exige que todos os
critérios estejam implementados **ou bloqueados explicitamente**, e há 9 que
não são nem um nem outro; há 2 gates que reportam `[OK]` para verificações que
não verificam o que prometem; e 12 critérios dependem de evidência que só um
ambiente real produz.

**Recomendação:** tratar F1–F4 antes de qualquer promoção para homologação, e
exigir no fechamento da run que os critérios 13, 15 e 17 apareçam na
`run-state.json` como pendências declaradas, com dono — hoje eles não aparecem.
O soak de 48 h e as validações externas continuam pendentes e são, sozinhos,
suficientes para impedir a declaração de "entregue".

---

*Relatório escrito pelo subagente tester. Único arquivo criado. Nenhum arquivo
do projeto foi editado. `run-state.json` não foi tocado. As duas mutações de
prova foram restauradas e confirmadas por `git status` e `sha256sum`; o
`git status` final é idêntico ao inicial.*
