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
