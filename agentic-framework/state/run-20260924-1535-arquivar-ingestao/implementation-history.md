<!--
CONTRACT: implementation-history
DONO: executor (cria e adiciona entradas) / tester, remediator, historian (adicionam entradas)
QUANDO É CRIADO: junto com a primeira ação do executor sobre o implementation-contract.md.
PARA ONDE VAI A INSTÂNCIA: agentic-framework/state/run-20260924-1535-arquivar-ingestao/
NATUREZA: append-only durante a execução — cada entrada é uma iteração, nunca se edita uma entrada anterior.
-->

# Implementation History — 20260924-1535-arquivar-ingestao

## Iteração 1 — 2026-09-24T15:45:49-03:00 — executor (implementação inicial e validação)

**O que foi feito:**

- Antes da remoção, `git status --short ingestao-service` retornou vazio. Não
  havia alteração local não relacionada no diretório que pudesse ser
  sobrescrita.
- Inventário removido: 33 arquivos versionados de `ingestao-service/`,
  contendo 43 funções de teste (`18` em `test_api.py`, `23` em
  `test_pipeline.py`, `2` em `test_smoke.py`), além de
  `backend/feed/microservice_client.py` e
  `backend/feed/tests/test_microservice_client.py` (13 funções de teste). Da
  suíte de cache local também foi removido somente o fake/classe de remediação
  do caminho remoto (1 função). Não foi mantido stub nem cópia em
  `docs/archive`.
- O feed Django ficou sem imports, classe de erro, branches
  `servico_ativo()` e fallbacks remotos. Services, serializers, curadoria,
  cache, paginação, gating, busca e os mesmos endpoints públicos foram
  preservados. O arquivo inteiro foi relido após a edição.
- Robôs deixou de importar/sincronizar fontes remotamente. O CRUD local de
  fontes/config e o endpoint de execução em background com resposta 202 foram
  preservados.
- As duas settings e os comentários/variáveis correspondentes de
  `backend/.env.example` foram removidos. `backend/.env`, arquivos de
  secrets/produção e `.env.production` não foram editados.
- `.gitignore` recebeu apenas a atualização do comentário que dependia do
  diretório removido. Nenhuma regra de runtime foi alterada.
- Documentos vivos registram a decisão humana de arquivamento definitivo,
  Django/PostgreSQL/Celery como fonte única e o procedimento humano para
  desligar, inspecionar e possivelmente remover serviços e volumes externos
  somente após backup, sem afirmar apagamento de dados. `infra/DEPLOY.md` teve
  uma única referência operacional residual a MongoDB substituída por
  PostgreSQL/Redis, para não deixar runbook apontando para a topologia
  removida.
- As remoções foram añadidas ao índice com `git add -u` somente para que
  `git ls-files ingestao-service` retornasse vazio, como exige o contrato.
  Não houve commit, criação de branch nem push.

**Por quê:**

A decisão explícita do solicitante foi remoção completa, não desativação de
um segundo pipeline. Isso elimina duas fontes de verdade, o painel sem
autenticação, a exposição anterior do Mongo e a duplicação de pipeline/testes
fora do CI, mantendo o backend Django como caminho local já validado.

**Arquivos removidos (35):**

```text
ingestao-service/.env.example
ingestao-service/Dockerfile
ingestao-service/README.md
ingestao-service/app/__init__.py
ingestao-service/app/collectors/__init__.py
ingestao-service/app/collectors/rss.py
ingestao-service/app/config.py
ingestao-service/app/db.py
ingestao-service/app/deps.py
ingestao-service/app/main.py
ingestao-service/app/observability.py
ingestao-service/app/pipeline/__init__.py
ingestao-service/app/pipeline/curadoria.py
ingestao-service/app/pipeline/dedup.py
ingestao-service/app/pipeline/execucao.py
ingestao-service/app/pipeline/summarizer.py
ingestao-service/app/pipeline/texto.py
ingestao-service/app/routers/__init__.py
ingestao-service/app/routers/_comum.py
ingestao-service/app/routers/config_router.py
ingestao-service/app/routers/feed.py
ingestao-service/app/routers/fila.py
ingestao-service/app/routers/fontes.py
ingestao-service/app/routers/ingestao.py
ingestao-service/app/routers/painel.py
ingestao-service/app/routers/system.py
ingestao-service/app/schemas.py
ingestao-service/docker-compose.yml
ingestao-service/requirements.txt
ingestao-service/tests/__init__.py
ingestao-service/tests/test_api.py
ingestao-service/tests/test_pipeline.py
ingestao-service/tests/test_smoke.py
backend/feed/microservice_client.py
backend/feed/tests/test_microservice_client.py
```

**Arquivos modificados (11):**

- `backend/feed/views.py` — removido exclusivamente o caminho remoto;
  comportamento local/contratos preservados.
- `backend/catalogo_noticias/robos_views.py` — removida sincronização remota;
  CRUD e resposta 202 preservados.
- `backend/feed/tests/test_p1_feed_cache_indices.py` — removidos somente
  `RespostaRemotaFake` e `TestUrgentesMicroservicoRemediacao`; testes locais
  de feed/cache mantidos.
- `backend/config/settings.py` — removidas as duas settings do adaptador.
- `backend/.env.example` — removidos comentários/variáveis do adaptador.
- `.gitignore` — atualizado somente o comentário dependente do serviço.
- `PROD_DECISOES.md` — decisão datada, remoção, fonte única e runbook humano.
- `ARCHITECTURE.md` — fonte única de verdade declarada.
- `ANALISE_CUSTO_PERFORMANCE.md` — achado histórico marcado como resolvido,
  sem apagar o diagnóstico anterior.
- `infra/DEPLOY.md` — removida uma instrução operacional residual sobre
  MongoDB (mudança fora da lista nominal, necessária ao grep operacional).
- `agentic-framework/state/run-20260924-1535-arquivar-ingestao/implementation-history.md`
  — este registro.

**Comandos executados / evidência:**

```text
git status --short ingestao-service
→ vazio antes da remoção.

git ls-files ingestao-service | wc -l
→ 0
find: ingestao-service ausente do filesystem.

python3 -m py_compile backend/feed/views.py \
  backend/catalogo_noticias/robos_views.py \
  backend/feed/tests/test_p1_feed_cache_indices.py \
  backend/config/settings.py
→ exit 0.

DJANGO_DEBUG=true .venv/bin/python manage.py check
→ System check identified no issues (0 silenced).

PostgreSQL real 16.15 (container efêmero postgres:16-alpine, porta host 32768):
pytest feed/test_p1 + test_robos_admin + test_robos_background
→ 25 passed, 18 warnings.

pytest -q --cov=. --cov-report=term-missing --cov-fail-under=80
→ 476 passed, 208 warnings, cobertura total 88.84%, gate 80% atendido,
  exit 0, PostgreSQL 16 real.

imports/settings check
→ imports/settings: ok; as duas settings removidas não existem.

manage.py makemigrations --check --dry-run
→ No changes detected.

npx tsc --noEmit
→ exit 0.

npm run build
→ Next.js 14.2.15 compilado; 59 páginas estáticas geradas; exit 0.

docker compose config --quiet
→ exit 0.
docker compose config --services
→ db, redis, web, frontend, caddy, celery-beat, celery-worker
  (nenhum serviço do segundo pipeline).

docker stop portal-arquivar-ingestao-1535-pg
→ container PostgreSQL efêmero removido após os testes.

git grep -n -E \
  'microservice_client|MICROSERVICO_INGESTAO_URL|INGESTAO_API_TOKEN|ingestao-service' \
  -- . ':!agentic-framework/state/**'
→ somente ANALISE_CUSTO_PERFORMANCE.md:309 e PROD_DECISOES.md:70, ambos
  explicitamente marcados como estado histórico/arquivado.

grep de filesystem em backend/frontend/infra/scripts/.github e manifests,
excluindo .venv/.pytest_cache/node_modules/.next
→ somente backend/.env:130-132. Arquivo local ignorado preservado
  deliberadamente por instrução; as flags são inertes após a remoção das
  settings.

git diff --check; git diff --cached --check; git diff HEAD --check
→ exit 0 nos três comandos.
```

**Preservação de estado concorrente/histórico:**

- `agentic-framework/state/run-20260924-1400-tls-ingestao/run-state.json`:
  SHA-256 antes/depois
  `7c57ea9bfe8ebe2920247f94aa9d73b9b1efd152a3286b226a8ab20954f5dc4f`.
- `agentic-framework/state/loteA-bugs/` (hash agregado dos arquivos):
  `8fd8604942458cc6ff720c68fab4c13f814734e0099a777deeec3cea7313b05d`
  antes/depois.
- Migrations (hash agregado): antes/depois
  `d796f446e0976321894a07efca858f474b7775055d815ba5ad57842722e1936c`;
  `git status --short -- backend/*/migrations` permaneceu vazio.
- `run-state.json` desta run e relatórios/run-states anteriores não foram
  editados pelo executor. Nenhuma migration/modelo foi alterada.
- Durante a execução, outra sessão fez commit e trocou o worktree de
  `perf/custo-performance-p0-p2` para `develop` às 15:39:34. O executor não
  fez essa troca nem commit; no momento do registro, ambos os refs apontavam
  para o mesmo commit `6e61a97`, e as mudanças desta run permanecem apenas na
  working tree/index deste diretório compartilhado.

**Resultado:**

Sucesso da implementação e das validações do executor. Métrica do diff desta
run, antes deste arquivo de histórico: 47 linhas adicionadas e 4.294 removidas
em 10 arquivos modificados + 35 arquivos removidos. `requests` foi mantido no
backend porque continua usado por provedores, pagamentos, e-mail e endereços.
Nenhum comando foi executado em VPS e nenhum dado/volume Mongo real foi
apagado. A aprovação formal e o veredito de encerramento continuam com
`tester`/`reviewer`/`historian`.

**Notas fora do escopo (se houver):**

- Limpeza operacional de flags em arquivos `.env` preexistentes e
  desligamento/remoção de containers/volumes Mongo em VPS são ações humanas
  posteriores, orientadas na documentação, fora deste repositório.
- A branch nominal mudou externamente durante a execução, conforme evidência
  acima; os refs `develop` e `perf/custo-performance-p0-p2` estavam no mesmo
  commit ao final da implementação.

---

## Iteração 2 — 2026-09-24T15:59:37-03:00 — tester (verificação independente do Lote B)

**Escopo e estado preservado:**

- Li `implementation-contract.md`, `task-plan.md`, este histórico e o diff real
  `git diff HEAD --` (staged + unstaged). O diff contém 45 caminhos, 47
  linhas adicionadas e 4.294 removidas; as deleções de `ingestao-service/` e
  do cliente continuam staged, sem reset/unstage.
- A validação rodou em `develop`, `HEAD=6e61a97d634dc0d2e9cad564a342d4992a9d2375`
  (o commit do Lote A). O diff do Lote B foi tratado separadamente; não houve
  commit, troca de branch, reset, unstaging ou correção de produção. O único
  artefato alterado por este tester foi esta nova entrada append-only. O smoke
  adicional foi temporário em `/tmp/opencode/test_archive_local_smoke.py` e
  não foi adicionado ao repositório.

**Matriz dos critérios de aceite:**

| # | Veredito | Evidência executada |
|---|---|---|
| 1 | **passed** | `git ls-files ingestao-service` retornou vazio (exit 0); `find` confirmou diretório ausente; nenhum arquivo de runtime/compose do serviço permaneceu no filesystem ou no índice. |
| 2 | **passed** | `git grep` fora de `agentic-framework/state/` retornou somente `ANALISE_CUSTO_PERFORMANCE.md:309` e `PROD_DECISOES.md:70`, ambos em seções explicitamente marcadas como achado/contexto/decisão histórica. O grep de filesystem, excluindo state/vendor/cache/generated, retornou somente esses dois documentos e `backend/.env:130-132`; esse `.env` local foi preservado deliberadamente, e suas flags são inertes. Com as duas flags não vazias, `manage.py check` passou e `hasattr(settings, ...)` foi `False` para ambas. Nenhum match operacional em código, config ou manifests. |
| 3 | **passed** | `DJANGO_DEBUG=true ... manage.py check` e também check com `DEBUG=false`, secret forte e flags antigas: `System check identified no issues (0 silenced)`. `compileall` de `feed`, `catalogo_noticias` e `config` saiu 0; AST/`tokenize.open` percorreu 277 arquivos sem imports do cliente/serviço removidos. `makemigrations --check --dry-run`: `No changes detected`. |
| 4 | **passed** | `pytest -q feed catalogo_noticias/tests/test_robos_admin.py catalogo_noticias/tests/test_robos_background.py` (SQLite local) → **58 passed, 36 warnings in 13.62s**, exit 0. Isso cobriu feed, urgentes, cache, detalhes, CRUD de fontes/config e o endpoint 202/background. O smoke temporário com flags apontando para `127.0.0.1:1`, `requests.sessions.Session.request` substituído por falha explícita e dados criados no banco local → **1 passed, 1 warning in 8.27s**, exit 0; exercitou `/api/feed/`, `/api/feed/urgentes/`, detalhe de cluster/item, segundo GET em cache e POST/PATCH/DELETE local sem rede real. |
| 5 | **passed** | Scan preciso de `backend/feed`, `backend/catalogo_noticias/robos_views.py` e `robos_urls.py` não encontrou `requests`, `microservice`, `servico_ativo`, funções do cliente, flags ou imports removidos. `requests` permanece somente nos providers/serviços de ingestão e testes, fora do caminho feed/robôs. `robos_views.py:151-160` mantém thread daemon e `HTTP_202_ACCEPTED`; o teste de background passou. |
| 6 | **passed** | `docker compose config --quiet` para `docker-compose.yml`, override localhost e override homolog: **exit 0** nos três. Serviços resolvidos: `db, redis, web, frontend, caddy, celery-beat, celery-worker`; volumes: `postgres_data, redis_data, media_data, static_data, caddy_data, caddy_config`. A configuração resolvida não contém `ingestao`, `microservice`, `mongo` ou `27017`. |
| 7 | **passed** | `docker run --rm postgres:16-alpine postgres --version` → `postgres (PostgreSQL) 16.15`. Suíte completa em container PostgreSQL real 16 efêmero (porta host 32769) com `--cov=. --cov-report=term-missing --cov-fail-under=80` → **476 passed, 208 warnings, cobertura total 88.84%, gate 80% atendido, exit 0, 116.90s**; container removido ao final. `npx tsc --noEmit` → exit 0. `npm run build` → Next.js 14.2.15, compilação e 59/59 páginas estáticas, exit 0. `git diff --check`, `git diff --cached --check` e `git diff HEAD --check` → exit 0 nos três. |
| 8 | **passed** | `makemigrations --check --dry-run` sem alterações; nenhum caminho de migration aparece no status/diff. Hashes de antes/depois permaneceram iguais: `backend/.env` `5560bcd29e4df3dde972207f6180f45cd7e2c38f9c258fcd1d79f297ae3a0a5a`; `run-20260924-1400-tls-ingestao/run-state.json` `7c57ea9bfe8ebe2920247f94aa9d73b9b1efd152a3286b226a8ab20954f5dc4f`; `loteA-bugs/` agregado `8fd8604942458cc6ff720c68fab4c13f814734e0099a777deeec3cea7313b05d`; migrations agregado `2877a483a570b5c1de62d950fac49a8bcb77be9b488b1e0ecfb4c24716ae7432`. O diff não toca `run-state.json` anterior, `loteA-bugs/`, `backend/.env` ou migrations; `6e61a97` foi identificado apenas como Lote A, não como Lote B. |
| 9 | **passed** | `PROD_DECISOES.md:69-89` registra a decisão humana de arquivamento, Django/PostgreSQL/Celery como fonte única e a ação humana em VPS; afirma explicitamente que a run não acessou a VPS, não desligou a instância e não diz que Mongo/volumes foram apagados. `ARCHITECTURE.md:21-25` e `ANALISE_CUSTO_PERFORMANCE.md:308-315` repetem a fonte única e a necessidade de desligamento/remoção manual só após backup. A documentação não afirma apagamento de dados externos. |

**Warnings observados:** 36 na suíte focada, 1 no smoke temporário e 208 na suíte
completa. Incluem o aviso de `staticfiles/` ausente, deprecations do
`feedparser` e `RemovedInDjango60Warning` de `URLField`; não houve warning
convertido em erro nem falha de gate.

**Veredito independente:** **passed** — 9/9 critérios de aceite atendidos.
Nenhum bug foi encontrado; não há arquivo:linha/situação `failed` a reportar.
A limpeza de flags em `.env` preexistentes e o desligamento/remoção de
containers/volumes Mongo externos continuam follow-up humano, como a
documentação corretamente declara.

## Iteração 3 — 2026-09-24T16:01:02-03:00 — tester (evento concorrente observado)

**Estado do worktree durante a validação:**

- Durante a execução, outra sessão criou o commit
  `5dc842d86238f7924c72b4f559bea1801bb21fa0`
  (`refactor(ingestao): arquiva o microservico de ingestao e sua integracao`)
  às 15:56:59. O `reflog` confirma que o commit ocorreu depois de
  `6e61a97`; **este tester não fez commit, reset, unstaging ou alteração
  desse conteúdo**. O commit externo tornou a árvore do Lote B igual ao diff
  que fora validado; não tentarei desfazer o commit porque isso violaria a
  preservação pedida.
- `6e61a97` continua sendo explicitamente o commit do Lote A;
  `5dc842d` é o commit posterior do Lote B. A comparação
  `git diff 6e61a97 5dc842d --` reproduz os 45 caminhos de produção
  (10 modificados e 35 removidos) que o tester examinou. No estado atual,
  `git diff 5dc842d --` contém somente a entrada append-only deste histórico;
  não há diff de produção pending, e o status mostra somente
  `M implementation-history.md`.
- Revalidação pós-commit: `manage.py check` sem issues, `compileall` exit 0,
  suíte focada **58 passed, 36 warnings in 6.69s** (exit 0), `docker compose
  config --quiet` exit 0 e nenhuma referência de Mongo/ingestão no compose.
  `git diff 5dc842d --check` e `git diff --cached --check` também passaram.
- Os hashes protegidos continuam iguais aos registrados na Iteração 2:
  `backend/.env` `5560bcd29e4df3dde972207f6180f45cd7e2c38f9c258fcd1d79f297ae3a0a5a`,
  run-state TLS `7c57ea9bfe8ebe2920247f94aa9d73b9b1efd152a3286b226a8ab20954f5dc4f`,
  `loteA-bugs/` `8fd8604942458cc6ff720c68fab4c13f814734e0099a777deeec3cea7313b05d`
  e migrations `2877a483a570b5c1de62d950fac49a8bcb77be9b488b1e0ecfb4c24716ae7432`.

**Impacto no veredito:** o comportamento e os 9 critérios continuam
**passed**. A única diferença é de estado Git externo: o Lote B não está mais
staged/unstaged porque outra sessão o commitou durante a rodada. O orquestrador
deve registrar esse commit concorrente antes da revisão formal; não há bug de
produção nem ação corretiva a tomar por este tester.

---

## Remediação — iteração 1 — 2026-09-24T16:28:51-03:00 — remediator

**Finding tratado:** `code-review-contract.md`, Finding 1 (minor) — o cutover
para a fonte local reutilizava `feed:v1` e podia servir payload remoto antigo
durante o TTL de 45 s.

**Correção aplicada:**

- `backend/feed/views.py` agora define `CACHE_NAMESPACE_LISTAGENS = "feed:v2"`
  e usa essa constante em `_chave_cache_listagem`. A sufixação existente
  (`prefixo`, usuário e querystring normalizada) foi preservada; assim, nenhuma
  chave `feed:v1` é lida pelas listagens, mas todos os endpoints que já usavam
  o helper continuamowego.
- O comentário do cutover registra que `v2` é a versão do contrato local e que
  a troca de namespace dispensa varrer Redis: as entradas antigas ficam
  inacessíveis para leitura e expiram pelo TTL.
- `backend/feed/tests/test_p1_feed_cache_indices.py` ganhou regressão com
  backend LocMem real: semeia `feed:v1:lista:uanon:categoria=cidades&page_size=20`
  com payload remoto falso, cria uma notícia no Postgres local e faz um GET real
  em `/api/feed/`. A resposta contém o ID/título locais, a chave antiga continua
  intacta, `feed:v2` recebe a resposta e a chamada usa TTL 45 s. O spy envolve o
  cache real somente para registrar o timeout; não substitui o banco nem o
  cache.

**Validação da remediação:**

- `pytest -q feed/tests/test_p1_feed_cache_indices.py -k cutover` → **1 passed**.
- `pytest -q feed/tests/test_p1_feed_cache_indices.py` → **15 passed**, 8
  warnings.
- `DJANGO_DEBUG=true .venv/bin/python manage.py check` → **0 issues**.
- `DJANGO_DEBUG=true .venv/bin/python manage.py makemigrations --check --dry-run`
  → **No changes detected**.
- `npx tsc --noEmit` → **exit 0**.
- `npm run build` → Next.js 14.2.15 compilado; **59/59 páginas estáticas**,
  exit 0.
- `docker compose --env-file .env.production.example config --quiet`,
  `docker compose -f docker-compose.yml -f docker-compose.localhost.yml
  --env-file .env.localhost config --quiet` e a combinação com
  `docker-compose.homolog.yml` usando `.env.production.example` → **exit 0**
  nos três.
- Suíte completa em PostgreSQL real 16 (container efêmero, porta host 32770):
  `pytest -q --cov=. --cov-report=term-missing --cov-fail-under=80` → **477
  passed**, 209 warnings, cobertura total **88,86%**, gate 80% atendido, exit
  0, 165,75 s; o container foi removido ao final.
- Reexecução final da suíte após a asserção explícita de não leitura de
  `feed:v1` (PostgreSQL 16 efêmero, porta host 32771) → **477 passed**, 209
  warnings, cobertura **88,86%**, gate 80% atendido, exit 0, 142,01 s; o
  container foi removido ao final.
- `git diff --check`, `git diff --cached --check` e `git diff HEAD --check` →
  exit 0.

**Estado preservado:** `HEAD` continua no commit externo `5dc842d`; não houve
commit, troca de branch, reset ou unstaging. Não editei `run-state.json` nem
`code-review-contract.md`; a única alteração desta remediação fora de
produção/teste é esta entrada append-only. Migrations, documentação viva e os
demais findings não foram tocados.

## Iteração 4 — 2026-09-24T16:48:32-03:00 — tester (revalidação independente do Finding 1)

**Escopo e estado concorrente:**

- Li o Finding 1 do `code-review-contract.md`, a remediação e o diff real. A
  validação começou com `HEAD=5dc842d`; não usei o relatório do remediator
  como substituto de execução própria.
- Durante a rodada, outra sessão fez o commit externo
  `f8d8db68692157ef340dcb1a198cbcce509572a2` (parent `5dc842d`) às
  `16:42:57`: `fix(deploy): restart_or_start passa a aplicar os args novos
  (delete+start)`. Ele alterou `.github/workflows/deploy.yml:373-423` com
  23 adições/20 remoções, fora do cache. O `reflog` e o commit confirmam que
  não foi feito por este tester; não fiz reset, unstaging, commit nem correção.
- Assim, `git diff 5dc842d` **não** contém apenas cache/teste/histórico: também
  contém o commit externo de workflow. `git diff HEAD` contém somente os quatro
  artefatos/ramificações de remediação já presentes (histórico, run-state,
  teste e `views.py`), enquanto `code-review-contract.md` segue untracked e
  não foi editado. Portanto o critério literal de escopo posterior a
  `5dc842d` fica **blocked**, embora o finding de cache esteja corrigido.

**Finding 1 — validaçãoOwn:**

| Verificação | Veredito | Evidência |
|---|---|---|
| Namespace e chaves | **passed** | `backend/feed/views.py:30-51` define `CACHE_NAMESPACE_LISTAGENS = "feed:v2"`; `_chave_cache_listagem` continua ordenando a query, usando `usuario = pk ou "anon"` e preservando `prefixo`. Chamadas nos cinco prefixes: `lista` (77), `urgentes` (148), `mais-lidas` (163), `home` (210), `destaques` (233). AST confirmou que não há literal runtime `feed:v1`; o TTL continua em `_ttl_feed()` (22-25) e nos cinco `cache.set`. |
| Cutover existente | **passed** | `pytest -q feed/tests/test_p1_feed_cache_indices.py -k cutover` → **1 passed, 1 warning in 8.40s**, exit 0. O teste semeia `feed:v1:lista:uanon:categoria=cidades&page_size=20` com payload falso, obtém resposta local, confirma que `feed:v1` não foi lido, que `feed:v2` recebe a resposta e que o TTL é 45 s. O arquivo completo → **15 passed, 8 warnings in 9.27s**, exit 0. |
| Todos os endpoints de listagem | **passed** | Smoke independente temporário em `/tmp/opencode/test_feed_v2_all_listings.py` cobriu `lista`, `urgentes`, `mais-lidas`, `home` e `destaques`, com payload legado semeado em cada `feed:v1`; verificou resposta local, ausência de leitura v1, escrita v2, TTL 45 e uma chave autenticada `u<pk>`. Resultado final → **1 passed, 1 warning in 19.62s**, exit 0. A primeira versão do smoke temporário falhou porque a auxiliar de teste montou `uuanon`; corrigi apenas esse arquivo fora do repositório e repeti. Não houve alteração de produção ou teste versionado. |
| Search/autocomplete/gating | **passed** | `pytest -q feed/tests/test_algoritmos_busca.py feed/tests/test_sanity.py gating/tests/test_sanity.py` → **42 passed, 20 warnings in 43.82s**, exit 0. |
| Smoke offline | **passed** | Smoke temporário com flags antigas apontando para porta inalcançável e `requests.sessions.Session.request` substituído por falha explícita → **1 passed, 1 warning in 16.49s**, exit 0; feed/robôs locais continuaram sem rede. |

**Validações gerais:**

- `manage.py check` → `System check identified no issues (0 silenced)`;
  `compileall` → exit 0; `makemigrations --check --dry-run` →
  `No changes detected`.
- Suíte focada `pytest -q feed` → **48 passed, 26 warnings in 14.65s**, exit 0.
- Suíte completa independente em PostgreSQL real `16.15` (container efêmero,
  porta host 32772) com `--cov=. --cov-report=term-missing
  --cov-fail-under=80` → **477 passed, 209 warnings, cobertura total 88.86%**,
  gate 80% atendido, exit 0, **396.42s**. O container foi removido ao final.
- `npx tsc --noEmit` → exit 0; `npm run build` → Next.js 14.2.15,
  **59/59** páginas, exit 0. `docker compose config --quiet` passou para
  base, localhost e homolog; serviços resolvidos sem Mongo/ingestão:
  `db, redis, web, frontend, caddy, celery-beat, celery-worker`.
  `actionlint:1.7.12` no workflow externo → exit 0.
- `git diff --check`, `git diff --cached --check` e `git diff HEAD --check` →
  exit 0 nos três.

**Preservação:**

- `backend/.env` permanece com SHA-256
  `5560bcd29e4df3dde972207f6180f45cd7e2c38f9c258fcd1d79f297ae3a0a5a`.
- `run-20260924-1400-tls-ingestao/run-state.json` permanece
  `7c57ea9bfe8ebe2920247f94aa9d73b9b1efd152a3286b226a8ab20954f5dc4f`;
  `loteA-bugs/` permanece `8fd8604942458cc6ff720c68fab4c13f814734e0099a777deeec3cea7313b05d`;
  migrations permanecem `2877a483a570b5c1de62d950fac49a8bcb77be9b488b1e0ecfb4c24716ae7432`.
  O `run-state.json` desta run, que já estava modificado pelo ciclo de
  remediação, teve SHA-256 `72b212a5ef2d07f5a910b62b3085c5caf4545ec229e6ffc954b1c78a459784b3`
  durante as verificações; este tester não o editou. Nenhum desses caminhos
  aparece no diff de produção.

**Veredito:** a **remediação do Finding 1 é passed** e não há bug de cache
encontrado. O veredito solicitado para a run como um todo é **blocked**, não
`passed`, porque a outro commit `f8d8db6` alterou
`.github/workflows/deploy.yml:373-423` depois de `5dc842d`, contrariando a
condição literal de que apenas cache/teste/histórico foram alterados. O
orquestrador deve reconciliar esse commit externo antes de fechar a run; este
tester não o reverteu.

## Iteração 5 — 2026-09-24T16:51:57-03:00 — tester (reconciliação do baseline f8d8db6)

**Reconciliação de escopo:**

- Baseline desta rodada: `HEAD=f8d8db68692157ef340dcb1a198cbcce509572a2`,
  parent `5dc842d`. `git show` confirma que o commit externo contém somente
  `.github/workflows/deploy.yml` (SHA-256 do arquivo no commit e no
  filesystem: `7c8427d5efc8d961dafcfb5b63b3d5108fc119d3d7f9fd30538c6c086fc1c1d1`).
  O commit permanece intocado; não foi resetado, revertido, reatribuído à run
  nem tratado como finding.
- `git diff --name-only f8d8db6` retornou exatamente:
  `agentic-framework/state/run-20260924-1535-arquivar-ingestao/implementation-history.md`,
  `agentic-framework/state/run-20260924-1535-arquivar-ingestao/run-state.json`,
  `backend/feed/tests/test_p1_feed_cache_indices.py` e
  `backend/feed/views.py`. Não houve `.github/workflows/deploy.yml` no diff.
  `code-review-contract.md` continua sendo artefato untracked, não editado.
- Os quatro paths estão dentro do escopo desta run; nenhum arquivo de produção
  foi alterado por este tester. A suíte completa anterior (**477 passed,
  209 warnings, 88.86%**, PostgreSQL real 16) foi usada como contexto; a
  baseline nova foi reconfirmada diretamente pelos testes focados abaixo.

**Validação direta do cache contra a nova baseline:**

| Verificação | Veredito | Evidência |
|---|---|---|
| Cutover v1→v2 | **passed** | `pytest -q feed/tests/test_p1_feed_cache_indices.py -k cutover` → **1 passed, 1 warning in 4.99s**, exit 0. A resposta foi local, `feed:v1` não foi lido, `feed:v2` foi escrito e o TTL foi 45 s. |
| Prefixes, TTL, usuário e query | **passed** | Smoke temporário independente em `/tmp/opencode/test_feed_v2_all_listings.py` → **1 passed, 1 warning in 6.06s**, exit 0. Cobriu `lista`, `urgentes`, `mais-lidas`, `home` e `destaques`, com query normalizada, TTL 45, chave anonima e chave autenticada `u<pk>`, sem leitura v1. |
| Arquivo de cache | **passed** | `pytest -q feed/tests/test_p1_feed_cache_indices.py` → **15 passed, 8 warnings in 6.30s**, exit 0. |
| Suíte focal de feed | **passed** | `pytest -q feed` → **48 passed, 26 warnings in 8.91s**, exit 0; inclui busca e autocomplete. |
| Gating | **passed** | `pytest -q gating/tests/test_sanity.py` → **14 passed, 3 warnings in 7.23s**, exit 0. |
| Smoke offline | **passed** | Smoke temporário com flags antigas e `requests` bloqueado → **1 passed, 1 warning in 6.87s**, exit 0. |

**Boot e integridade:**

- `manage.py check` → `System check identified no issues (0 silenced)`;
  `makemigrations --check --dry-run` → `No changes detected`; `compileall` →
  exit 0.
- `git diff --check`, `git diff --cached --check` e
  `git diff f8d8db6 --check` → exit 0.
- `backend/.env` preservado (`5560bcd29e4df3dde972207f6180f45cd7e2c38f9c258fcd1d79f297ae3a0a5a`);
  run-state TLS preservado (`7c57ea9bfe8ebe2920247f94aa9d73b9b1efd152a3286b226a8ab20954f5dc4f`);
  `loteA-bugs/` preservado (`8fd8604942458cc6ff720c68fab4c13f814734e0099a777deeec3cea7313b05d`);
  migrations preservadas (`2877a483a570b5c1de62d950fac49a8bcb77be9b488b1e0ecfb4c24716ae7432`).
  O `run-state.json` desta run, já modificado pelo ciclo de remediação, teve
  hash `72b212a5ef2d07f5a910b62b3085c5caf4545ec229e6ffc954b1c78a459784b3`
  durante esta rodada; não foi editado por este tester.

**Veredito desta reconciliação: passed.** O commit externo `f8d8db6` é
`out-of-scope/existing concurrent commit`, não finding. O escopo relativo à
baseline está limpo, o cutover foi reexecutado diretamente e nenhum problema
real foi encontrado nos paths desta run.

## Iteração 6 — 2026-09-24T17:09:22-03:00 — historian (síntese cronológica e fechamento)

**O que foi feito:**

- A execução começou com planejamento e contrato às 15:30–15:35 e a
  implementação da remoção às 15:35–15:46. O inventário canônico do Lote B
  removeu 33 arquivos de `ingestao-service/` e 2 paths do adaptador/teste do
  cliente (`microservice_client.py` e seu teste), além de 10 modificações de
  código/configuração/documentação.
- O teste inicial independente executou-se sobre `6e61a97` (Lote A) e validou
  476 testes em PostgreSQL 16. A rodada de remediação às 16:28–16:48 recebeu o
  Finding 1 (minor) e corrigiu o namespace das cinco listagens de `feed:v1` para
  `feed:v2`, com teste de regressão para payload remoto legado.
- A reconciliação do tester, às 16:48–16:55, usou `HEAD=f8d8db6` (parent
  `5dc842d`) como baseline explícita. A suíte final independente ficou em
  477 testes, PostgreSQL 16, cobertura 88,86%, smoke offline e cutover v1→v2
  aprovados.
- A re-revisão de 16:56–17:00 aprovou o escopo com 0 findings residuais; a
  documentação de 17:00–17:05 consolidou fonte única, cutover de cache e
  limpeza manual de infraestrutura externa. O fechamento do historian produziu
  o relatório, o estado `closed/done` e uma única entrada append-only no
  ledger.

**Por quê:**

A remoção definitiva elimina a segunda fonte de verdade e o caminho remoto do
portal, preservando Django/PostgreSQL/Celery e seus contratos locais. A troca de
namespace é necessária para que uma chave remota antiga não seja servida como
resposta local durante o TTL; o teste de cutover prova que a entrada `feed:v1`
permanece inacessível à leitura, enquanto a resposta local é gravada em
`feed:v2`.

**Commits e concorrência:**

- `6e61a97` é o commit do Lote A, usado como baseline inicial.
- `5dc842d` é o Lote B, criado por outra sessão e preservado como autoridade
  do conteúdo arquivado; não foi realizado commit nem atribuído a esta execução.
- `f8d8db6` é uma correção independente de PM2, posterior e com parent
  `5dc842d`, alterando somente `.github/workflows/deploy.yml`. Foi preservado
  como baseline da retestagem, registrado como follow-up externo e não é bug nem
  finding desta execução.

**Integridade e resultado:**

- Não houve commit, reset, troca de branch ou push desta execução. Não houve acesso
  a VPS, desligamento de Mongo real, edição de `.env` existente ou remoção de
  dados/volumes externos.
- O finding minor foi resolvido; findings finais: 0 blocker, 0 major, 0 minor,
  0 nit, com 1 resolvido. O run foi encerrado como entregue após validação
  do JSON contra `agentic-framework/schemas/run-state.schema.json`.

## Iteração 7 — 2026-09-24T17:15:08-03:00 — historian (reconciliação de concorrência externa final)

**O que foi feito:**

- A verificação final do Git Detectou que, às 17:09:03, outra sessão criou
  `d1e0456` (parent `f8d8db6`), um commit externo de documentação que altera
  somente `infra/DEPLOY.md` com o estado HTTP-only/drift da VPS. O commit foi
  observado depois da retestagem de comportamento e não foi resetado, revertido,
  editado ou atribuído a esta execução.
- A baseline usada pela retestagem permanece explicitamente `f8d8db6`; `d1e0456`
  é um estado documental posterior e concorrente, não uma mudança do código de
  arquivamento validado por esta execução.
- A árvore final está em `d1e0456`; os paths protegidos, migrations e o prefixo
  anterior do ledger continuam preservados. Não houve novo commit, reset ou
  push durante esta reconciliação.

**Resultado:** concorrência externa registrada sem atribuição indevida e sem
classificar `d1e0456` como bug ou finding desta execução. O veredito final permanece
`approve`, com 0 findings residuais e 1 finding resolvido.
