# Implementation History — 20260924-1330-bugs-pendencias

**Data:** 2026-09-24
**Branch:** `perf/custo-performance-p0-p2`
**Execução:** working tree, sem commit. A implementação foi delegada a um subagente executor; o prompt detalhado cobriu os mesmos oito itens materializados no implementation-contract.md.

> Observação de provenance: a execução começou com o histórico em `agentic-framework/state/loteA-bugs/implementation-history.md`; o conteúdo abaixo é a cópia auditável para a run canônica, sem alteração das evidências do executor.

## Resumo

| Bug | Status | Resultado |
|---|---|---|
| 1 — Caddy expõe credenciamento | **corrigido** | Caddy nega a subtree privada e serve somente `/media/public/`. |
| 2 — Radar mostra dia anterior | **corrigido** | Datas civis ISO não passam pela semântica UTC do construtor `Date`; instantes com fuso permanecem corretos. |
| 3 — colisão de `X-Request-ID` | **corrigido** | IDs são saneados no middleware e o valor persistido é o mesmo valor propagado. |
| 4 — cache de autocomplete não invalidado | **corrigido** | Aprovação/rejeição pelo painel e pelo admin nativo invalidam as três chaves do snapshot. |
| 5 — marker promovido com HTTP 3xx | **corrigido** | API e web exigem código HTTP exatamente `200` antes da promoção. |
| 6 — script de datas depende de Node experimental | **corrigido** | Check `.mjs` roda em Node 18/20 sem flag experimental e está no CI. |
| 7 — pytest no runtime | **corrigido** | Dependências de teste foram separadas; o lock de runtime não contém ferramentas de teste. |
| 8 — revalidação cruzada dos workflows | **corrigido** | Actionlint, parser de chaves duplicadas e checagem de coerência passaram. |

## Bug 1 — Caddyfile expõe documentos de credenciamento
- **Arquivo:linhas:** `Caddyfile:42-61`.
- **Problema:** `handle_path /media/*` servia `/srv/media` inteiro, permitindo obter `media/credenciamento/<user_id>/...` sem a visão autenticada.
- **Correção:** matcher de `/media/credenciamento` com 404; `/media/public/*` com raiz `/srv/media/public`; fallback fecha `/media*` e subtrees desconhecidos. Ordem comparada ao Nginx.
- **Verificação:** placeholders substituídos em cópia temporária; `Valid configuration`, exit 0; `caddy adapt` confirmou a ordem privada-negada → pública → fallback.

## Bug 2 — Radar mostra dia anterior
- **Arquivo:linhas:** `frontend/lib/datas.ts:20-95`; uso em `frontend/app/radar/RadarClient.tsx:189`.
- **Problema:** `new Date("2026-09-23")` representa midnight UTC e virava `22/09/2026` em America/Sao_Paulo.
- **Correção:** strings `YYYY-MM-DD` seguem semântica civil; instantes com fuso continuam por `new Date(valor)` e `America/Sao_Paulo`.
- **Verificação:** `23/09/2026` para a data civil e `23/09/2026`/`18:30` para `2026-09-23T21:30:00Z`, em TZ UTC e Asia/Tokyo; tsc e build passaram.

## Bug 3 — colisão de X-Request-ID
- **Arquivo:linhas:** `backend/config/middleware.py:23-47,89-107`; `backend/config/tests/test_request_id.py:20-47`.
- **Problema:** header externo arbitrário era reutilizado, enquanto `EventoBusca.request_id` é unique e limitado a 64 caracteres; truncamento tardio podia colidir.
- **Correção:** `normalizar_request_id()` preserva IDs válidos, remove espaços e gera UUID4 para entradas vazias, sentinel, longas ou não imprimíveis. O mesmo valor final alimenta request, logs, resposta e persistência.
- **Verificação:** teste focal 2 passed; comparou header/request/DB e confirmou UUIDs distintos para dois IDs longos; suíte completa 465 passed.

## Bug 4 — cache de autocomplete não invalidado
- **Arquivo:linhas:** `backend/painel_admin/services.py:13-41`; `backend/catalogo_noticias/admin.py:82-108`; `backend/painel_admin/tests/test_sanity.py:139-169`.
- **Problema:** mudar `status_revisao` não limpava as três chaves do autocomplete; título pendente/rejeitado permanecia até o TTL.
- **Correção:** decisão da API, approve/reject e edição de status no admin invalidam as três chaves; falha de cache continua não fatal.
- **Verificação:** teste semeou as três chaves, aprovou via `/api/admin/fila/<id>/decisao/` e confirmou `cache.get(...) is None`; 2 passed no conjunto focal e suíte completa verde.

## Bug 5 — marker `.deployed-sha` promovido com HTTP 3xx
- **Arquivo:linhas:** `.github/workflows/deploy.yml:476-552`.
- **Problema:** `curl -sf` retorna sucesso em 3xx; redirect da home podia promover o SHA.
- **Correção:** ambos os probes capturam `%{http_code}`, normalizam erro para `000` e só marcam OK em 200. Permanecem as condições de resultado do job e SHA verificado.
- **Verificação:** inspeção do shell, comparação dos casos e actionlint nos seis workflows.

## Bug 6 — script de datas dependia de Node experimental
- **Arquivo:linhas:** `frontend/scripts/verificar-datas-tz.mjs:1-68`; `.github/workflows/ci.yml:90-96`.
- **Problema:** importava TypeScript diretamente e exigia `--experimental-strip-types`, ausente em Node 18/20; não fazia asserções nem rodava no CI.
- **Correção:** JavaScript puro usa o compilador TypeScript já presente para carregar o módulo real em memória e faz asserções. O CI executa com TZ UTC e Asia/Tokyo.
- **Verificação:** Node 18.20.8 e 20.20.2, ambos os fusos, além de build do frontend.

## Bug 7 — pytest no runtime
- **Arquivo:linhas:** `backend/requirements.txt:55-56`; novo `backend/requirements-dev.txt:1-8`; `backend/requirements-lock.txt:1-14`; `backend/.dockerignore:12`; `.github/workflows/ci.yml:65-72`; `scripts/init-local.ps1:117-120`.
- **Problema:** `pytest-django` e `pytest-cov` eram instalados no runtime e o lock compartilhado carregava ferramentas de teste.
- **Correção:** `requirements.txt` e lock são runtime puro; `requirements-dev.txt` contém `-r requirements.txt` e ferramentas de teste. CI instala lock + dev; deploy PM2 instala apenas lock; bootstrap local instala dev.
- **Verificação:** dry-run e instalação em diretório isolado sem pytest/coverage; `pip check` sem quebras; lock e dev resolvem com exit 0.

## Bug 8 — revalidação dos workflows
- **Arquivo:linhas:** `.github/workflows/{ci,deploy,deploy-dev,deploy-prod,deploy-homolog,rollback}.yml`.
- **Problema:** as runs de ops e TLS tinham deixado validação cruzada pendente.
- **Correção:** nenhuma quebra de topologia; verificou-se `verify`, `concurrency`, `tls_enabled` e rollback estrito, além de probe e requirements.
- **Verificação:** actionlint 1.7.12 sem findings; PyYAML com detecção de duplicatas OK; checagem estrutural confirmou `deploy.needs=verify`, `validate.needs=[verify,deploy]`, `cancel-in-progress=false`, callers com `verify_ref` e rollback com `strict_validate=true`; `git diff --check` passou.

## Validações finais do executor
- Backend com gate de cobertura: **465 passed, 87.90%**, exit 0.
- Frontend: `tsc --noEmit` e build **59/59 páginas**, exit 0.
- Datas: Node 18 e 20, TZ UTC e Asia/Tokyo, ambos passaram.
- Caddy: `Valid configuration` com placeholders substituídos.
- Workflows: actionlint, YAML/duplicatas, coerência estrutural e `git diff --check`, exit 0.

## Ressalvas do executor
- Não houve execução em GitHub Actions/VPS; workflows foram validados estaticamente.
- PowerShell não estava disponível para executar `scripts/init-local.ps1`; a mudança foi revisada estaticamente.
- A criação de venv isolado via `ensurepip` falhou no host; a validação do lock usou `pip --target`.
- `agentic-framework/state/run-20260924-1400-tls-ingestao/run-state.json` foi modificado por outra sessão e preservado fora deste lote.

## Verificação final independente do tester — 2026-09-24

**Veredito:** `passed`.

**Branch:** `perf/custo-performance-p0-p2`. **Engine usada na suíte final:** PostgreSQL real 16 em container `postgres:16-alpine` efêmero; a suíte final não usou o banco local e nenhum pacote foi instalado no host. O tester não alterou código de produção, migrations, `ingestao-service/`, dependências de produto, workflows, `run-state.json` da run TLS nem `agentic-framework/state/loteA-bugs/`, e não fez commit.

### Matriz dos 12 critérios

| # | Critério | Resultado | Evidência independente |
|---|---|---|---|
| 1 | Caddy nega `/media/credenciamento` e descendentes sem fallback para `/srv/media` | `passed` | Caddy `v2.11.4` em `caddy:2-alpine`; `caddy validate` e `caddy adapt` com placeholders substituídos, exit 0. Em roteamento HTTP real, arquivo privado existente respondeu **404**, corpo vazio e não continha `PRIVATE-SECRET`; rota desconhecida sob `/media` também respondeu 404. |
| 2 | Caddy serve `/media/public/<arquivo>` da raiz correta | `passed` | No mesmo servidor Caddy real, `/media/public/photo.txt` respondeu **200** e corpo `PUBLIC-OK`; `handle_path` foi aplicado a `/srv/media/public` sem remover o nome do arquivo. |
| 3 | Data civil e instante com fuso permanecem corretos | `passed` | `node:18-alpine` (Node 18.20.8) e `node:20-alpine` (Node 20.20.2), em `TZ=UTC` e `TZ=Asia/Tokyo`: `2026-09-23` → `23/09/2026`; `2026-09-23T21:30:00Z` → data `23/09/2026` e hora `18:30`. |
| 4 | Check de datas é executável e não é frouxo | `passed` | As quatro combinações Node 18/20 × UTC/Tokyo terminaram exit 0. Em cópia temporária do check, adulterar a saída esperada para `24/09/2026` fez as quatro execuções falharem com exit 1 e `data civil incorreta`; portanto a asserção realmente detecta divergência. |
| 5 | Saneamento de `X-Request-ID` | `passed` | Focal `config/tests/test_request_id.py`: **7 passed**. Cobre ID válido no limite exato de 64 caracteres, vazio/espaços, sentinel `-`, excesso, controle ANSI/quebra de linha, UUID4 v4 e limite de tamanho. O middleware também foi exercitado com request/header/ContextVar. |
| 6 | Header, request e `EventoBusca.request_id` são byte a byte iguais; IDs longos distintos persistem | `passed` | Teste focal com `APIClient` e Celery eager: resposta `200`, header, `request.request_id` e linha `EventoBusca` iguais. Teste com dois IDs longos distintos confirmou dois UUIDs distintos e duas linhas persistidas distintas. |
| 7 | Invalidação das três chaves após decisão editorial | `passed` | Focal do painel/admin: **34 passed** no conjunto request-ID + sanity. Foram exercitados approve/reject do painel, approve/reject do admin nativo, `save_model` e o formulário real `admin:catalogo_noticias_newsitem_change`; `feed:autocomplete:v2:{categorias,titulos,populares}` ficou vazio em todos os casos. Cache indisponível durante decisão continuou retornando 200, sem erro fatal. |
| 8 | `.deployed-sha` promove somente API=200 e web=200, preservando barreiras | `passed` | Extraí o corpo real de `jobs.validate.steps[0].with.script` de `deploy.yml` e o executei com `curl`/`git`/`pm2` simulados. A matriz completa **6×6** (200, 301, 302, 404, 500, 000) cobriu 36 casos: somente 200/200 substituiu o marker; os demais preservaram `OLD-SHA`. `DEPLOY_RESULT!=success`, `STRICT=true` com probe não-200 e SHA de checkout divergente também preservaram o marker. |
| 9 | Lock runtime, manifesto dev, `pip check` e caminho de deploy | `passed` | Parse dos pins: `pytest`, `pytest-django`, `pytest-cov` e `coverage` ausentes do lock. Em `python:3.12-slim` com venv efêmero, `pip install -r requirements-lock.txt` instalou runtime e os quatro pacotes ficaram `ABSENT`; `pip check` passou. `pip install -r requirements-dev.txt` instalou `pytest 9.1.1` e `pip check` continuou passando. O caminho PM2 ativo em `deploy.yml` tem uma única instalação: `pip install -r requirements-lock.txt`. A variante Docker alternativa usa `requirements.txt` runtime-only e `.dockerignore` exclui o manifesto dev; não contém ferramentas de teste. |
| 10 | Job frontend executa o check antes de `tsc`/build nos fusos definidos | `passed` | Parser estrutural confirmou a ordem `npm ci` → check de datas → `npx tsc --noEmit` → `npm run build`, com `TZ=UTC` e `TZ=Asia/Tokyo`. O mesmo check foi executado de fato em Node 18 e 20. |
| 11 | Seis workflows: actionlint, YAML sem duplicatas e relações estruturais | `passed` | `rhysd/actionlint:1.7.12` executado nos seis arquivos, exit 0 e sem findings. Parser PyYAML com detector de chaves duplicadas processou os seis; controle negativo rejeitou uma chave duplicada. Estrutura confirmada: `deploy.needs=verify`, `validate.needs=[verify,deploy]`, `cancel-in-progress=false`, `tls_enabled` no reusable/callers, `verify_ref` nos callers e rollback com `strict_validate=true`. |
| 12 | Run-state concorrente e escopo preservados | `passed` | SHA-256 do run-state TLS antes/depois: `7c57ea9bfe8ebe2920247f94aa9d73b9b1efd152a3286b226a8ab20954f5dc4f` (sem alteração). `git status` continua mostrando-o como `M` por causa da outra sessão, mas o tester não o editou; `loteA-bugs/` não foi tocado e não há diff em migrations ou `ingestao-service/`. |

### Testes acrescentados/ajustados pelo tester

- `backend/config/tests/test_request_id.py`: limite válido de 64 caracteres, saneamento de entradas inválidas, UUID4 v4, igualdade via ContextVar, persistência byte a byte, integração HTTP com Celery eager e persistência de dois IDs longos distintos.
- `backend/painel_admin/tests/test_sanity.py`: approve/reject parametrizados no painel, approve/reject do admin nativo, edição via `save_model`, formulário real do Django admin e decisão com cache indisponível. Somente testes foram acrescentados; nenhum arquivo de produção foi corrigido.

### Comandos e resultados consolidados

- **Caddy:** `docker run --rm -v <Caddyfile-substituído>:/etc/caddy/Caddyfile:ro caddy:2-alpine caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile` e `caddy adapt` — exit 0; servidor real com `caddy run` — status privado/desconhecido 404, público 200.
- **Datas:** `docker run ... node:18-alpine node scripts/verificar-datas-tz.mjs` e o equivalente Node 20, com `TZ=UTC`/`TZ=Asia/Tokyo` — 4/4 exit 0; mutação — 4/4 exit 1 como esperado.
- **Backend completo (gate CI):** `DJANGO_DEBUG=true DJANGO_DB_ENGINE=postgresql ... .venv/bin/python -m pytest -q --cov=. --cov-report=term-missing --cov-fail-under=80` — **476 passed, 0 failed, 211 warnings, cobertura total 88.60%, exit 0**, PostgreSQL 16 real. `python manage.py check` também retornou “System check identified no issues”, exit 0.
- **Frontend:** `npx tsc --noEmit` — exit 0; `npm run build` — exit 0, Next.js gerou **59/59** páginas.
- **Requirements:** instalação isolada em `python:3.12-slim` — runtime sem pytest/coverage, dev com pytest, dois `pip check` sem quebras, exit 0.
- **Workflows:** actionlint, parser YAML/duplicatas (incluindo controle negativo) e checagem estrutural — todos exit 0; `git diff --check` — exit 0.

### Findings e limitações

- **Finding funcional:** nenhum; os 12 critérios passaram.
- Não houve execução em GitHub Actions, VPS, DNS ou TLS real, conforme não-objetivos do contrato; a validação de workflows foi estática.
- `pwsh` não está disponível no host, portanto `scripts/init-local.ps1` foi conferido estaticamente; a instalação efetiva de `requirements-dev.txt` foi executada em container efêmero. Isso não bloqueou os critérios testáveis.
- As imagens `caddy:2-alpine`, `node:18-alpine`, `node:20-alpine`, `rhysd/actionlint:1.7.12` e `postgres:16-alpine` estavam disponíveis; portanto não houve critério `blocked`.

## Remediação — iteração 1

**Data:** 2026-09-24

**Branch:** `perf/custo-performance-p0-p2`

**Execução:** remediação dos seis findings da revisão da iteração 1, sem commit e sem alteração de `run-state.json` ou `code-review-contract.md`.

| Finding | Status | Resultado |
|---|---|---|
| 1 — probe de deploy mascarava rc do curl | **resolved** | API/web exigem simultaneamente `curl rc=0` e HTTP exatamente `200`. |
| 2 — cache invalidado antes do commit | **resolved** | Admin e ingestão usam `on_commit`; painel foi auditado e mantido por não estar em transação atômica. |
| 3 — controle nas bordas preservava ID do cliente | **resolved** | `isprintable()` é avaliado no bruto antes de remover somente espaço ASCII. |
| 4 — anos civis 0000–0099 perdiam identidade | **resolved** | A parte `year` é reconstruída com `formatToParts`; civil impossível retorna vazio. |
| 5 — asserts do check de datas eram frouxos | **resolved** | Todas as funções declaradas e os limites civis agora têm expectativa exata. |
| 6 — docs declaravam Python 3.13 | **resolved** | README e bootstrap local foram alinhados ao Python 3.12 coberto por CI/Docker. |

### Finding 1 — resolved

- **Arquivos/linhas:** `.github/workflows/deploy.yml:476-574`.
- **Mudança:** o job `validate` inicializa e captura separadamente `API_CURL_RC`/`WEB_CURL_RC` e `API_HTTP_CODE`/`WEB_HTTP_CODE`. O helper local `probe_http` mantém `curl -sS` dentro de um `if`, portanto captura o rc sem `|| true` e sem desligar `set -e`. `API_OK`/`WEB_OK` só tornam-se 1 quando rc é zero e o código é exatamente `200`; stderr, rc e código aparecem no diagnóstico. Em `STRICT=true`, a transferência incompleta falha; em modo warn, o marker anterior é preservado.
- **Teste/resultado:** servidor HTTP local com `Content-Length: 100` e corpo parcial produziu `http_code=200` com `curl rc=18`. O script real extraído do YAML foi executado com `curl/git/pm2` simulados: matriz 6×6 (`200/301/302/404/500/000`) em `strict=false` e `strict=true`, 72 execuções; somente 200/200 promoveu o marker. O caso API 200/rc 18 + web 200 retornou 1 em strict, preservou `OLD-SHA` e emitiu `api FAIL curl_rc=18 http_code=200`. `bash -n` do script renderizado passou.

### Finding 2 — resolved

- **Arquivos/linhas:** `backend/catalogo_noticias/admin.py:83-113`; `backend/painel_admin/services.py:28-35`; `backend/catalogo_noticias/services/ingestao.py:449-457`; `backend/painel_admin/tests/test_sanity.py:185-399`; `backend/catalogo_noticias/tests/test_p2_ingestao_performance.py:617-640`.
- **Mudança:** `save_model`, approve e reject do admin nativo agendam `invalidar_cache_autocomplete` por `django.db.transaction.on_commit`, cobrindo o `transaction.atomic` interno de `changeform_view`/`response_action`. A auditoria de `painel_admin/services.py` confirmou uma única chamada em `FilaDecisaoView`, sem `transaction.atomic` no serviço/view e sem `ATOMIC_REQUESTS`; a invalidação imediata foi mantida e a evidência foi documentada no código. A ingestão também foi corrigida: `_persistir_news_items_em_lote` é chamada dentro de `_persistir_grupo` e `_persistir_grupo_mesclado`, ambos atômicos, e agora registra `on_commit`. O helper continua best-effort e nenhum cache é apagado em rollback.
- **Teste/resultado:** testes transacionais cobriram `save_model` e uma action: dentro de `atomic`, o mock não era chamado e as três chaves (`categorias`, `titulos`, `populares`) permaneceram; somente após o commit o mock foi chamado uma vez e as três sumiram. O rollback de `save_model` descartou o callback, preservou status e as três chaves. Fluxos reais de approve/reject, formulário nativo e a invalidação da ingestão passaram. Focal: **40 passed**; suíte Python 3.12: **481 passed**, cobertura **88.67%**.

### Finding 3 — resolved

- **Arquivos/linhas:** `backend/config/middleware.py:29-55`; `backend/config/tests/test_request_id.py:52-100`.
- **Mudança:** o valor bruto é convertido para string e validado com `isprintable()` antes de qualquer normalização. Depois, remove-se somente espaço ASCII das bordas; tab, newline, NBSP e C1, inclusive U+0085, não chegam ao `strip`. Sentinel, vazio e núcleo maior que 64 continuam gerando UUID4; espaço ASCII normal continua sendo removido.
- **Teste/resultado:** teste unitário do middleware com `\x85trusted-id\x85` confirmou UUID4, request/META/response iguais e nenhum U+0085 na resposta. O teste de OWS confirmou preservação de dois IDs distintos com espaço nas bordas; tab e C1 entraram na matriz de UUID4. Focal e suíte completa passaram.

### Finding 4 — resolved

- **Arquivos/linhas:** `frontend/lib/datas.ts:79-105`.
- **Mudança:** para data civil válida 0000–0099, o formatador usa `formatToParts` e substitui apenas a parte `year` por `String(ano).padStart(4, "0")`, preservando os demais componentes, a referência civil em UTC e o timezone dos instantes normais. A alteração atende curto, extenso, mês/ano, ano e `dateStyle` por ficar no helper central.
- **Teste/resultado:** `0000-01-01` produziu `01/01/0000`/`0000`, `0001-01-01` produziu `01/01/0001`/`0001` e `0096-02-29` produziu `29/02/0096`/`0096`; 0000 e 0001 permaneceram distintos. `0095-02-29` retornou string vazia em todos os formatadores com ano, sem normalização para 1º de março. Node **18.20.8** e **20.20.2**, em `TZ=UTC` e `TZ=Asia/Tokyo`, passaram nas quatro combinações.

### Finding 5 — resolved

- **Arquivos/linhas:** `frontend/scripts/verificar-datas-tz.mjs:22-141`.
- **Mudança:** as 12 saídas listadas — data civil, data sem ano, hora, data/hora, completa, compacta, extenso, data/hora por extenso, hora com segundos, mês/ano, ano e número — agora comparam com valores exatos. O check continua transpilando/importando `frontend/lib/datas.ts`; os casos 0000, 0001, ano bissexto 0096 e impossível 0095 cobrem todos os formatadores que pedem ano. As expectativas são estáveis no ICU dos Node 18/20 testados, portanto não foi necessário aceitar saída variável.
- **Teste/resultado:** as quatro combinações Node 18/20 × UTC/Tokyo passaram com o módulo real; `npx tsc --noEmit` e `npm run build` também passaram.

### Finding 6 — resolved

- **Arquivos/linhas:** `README.md:54`; `scripts/init-local.ps1:87`. Evidência: `.github/workflows/ci.yml:61-64` usa Python 3.12; `backend/Dockerfile:1` usa `python:3.12-slim`.
- **Mudança:** somente as duas afirmações locais incompatíveis passaram de 3.13 para 3.12. Manifestos, dependências e fluxo de instalação não foram alterados nesta remediação.
- **Teste/resultado:** grep em README, CI-CD, scripts, workflows, infra, Dockerfiles/compose e bootstrap não encontrou outra afirmação ativa de 3.13; as ocorrências restantes estão apenas em históricos de runs. A suíte completa e `manage.py check` executaram no container oficial `python:3.12-slim` e passaram. O parser PowerShell ficou **blocked** porque `pwsh` não está instalado; a alteração do bootstrap é apenas texto de diagnóstico.

### Validações consolidadas da remediação

- **Backend focal:** PostgreSQL 16 real; `40 passed`, exit 0.
- **Backend Python 3.12.14:** `manage.py check` sem issues; suíte com `--cov-fail-under=80`: **481 passed**, **88.67%**, exit 0.
- **Datas:** Node 18.20.8 e 20.20.2 × `UTC`/`Asia/Tokyo`: **4/4 exit 0**.
- **Frontend:** `npx tsc --noEmit` exit 0; `npm run build` gerou **59/59** páginas, exit 0.
- **Workflows:** matriz de probe + caso truncado real; `actionlint 1.7.12` nos seis workflows, exit 0.
- **Integridade:** `git diff --check` exit 0; nenhum diff em migrations; SHA-256 do run-state TLS preservado em `7c57ea9bfe8ebe2920247f94aa9d73b9b1efd152a3286b226a8ab20954f5dc4f`; `agentic-framework/state/loteA-bugs/` não foi editado.

### Riscos residuais

- Não houve GitHub Actions, VPS, DNS ou TLS reais; a promoção foi validada com o script real do workflow e dependências locais simuladas.
- O parser do PowerShell ficou blocked por ausência de `pwsh`; README/bootstrap foram conferidos estaticamente e o runtime Python 3.12 foi executado.
- Redis não foi exercitado como backend real nesta remediação; o contrato best-effort permanece coberto por teste de indisponibilidade e o cache de teste usa LocMem.
- Nenhum commit foi criado.

## Reteste independente pós-remediação — 2026-09-24

**Veredito do novo reteste:** `passed`.

Esta seção é append-only e não substitui a evidência da remediação nem a verificação anterior. O tester releu os seis findings do `code-review-contract.md`, executou o código real renderizado do workflow e rodou a suíte final em Python 3.12.14 + PostgreSQL 16 real. Não corrigi código de produção, não alterei `run-state.json` nem `code-review-contract.md`, não toquei `agentic-framework/state/loteA-bugs/` e não fiz commit.

### Matriz finding → evidência independente

| Finding | Resultado | Evidência executada pelo tester |
|---|---|---|
| 1 — probe de deploy mascarava rc do `curl` | `passed` | Extraí o script real de `deploy.yml`, substituí apenas entradas de teste e rodei `bash -n` (exit 0). Servidor HTTP local real respondeu headers `200` + `Content-Length: 100`, enviou corpo parcial e produziu `curl` com `http_code=200`, rc 18. O script registrou `curl_rc=18 http_code=200`, preservou `OLD-SHA`; com `STRICT=false` terminou 0, com `STRICT=true` terminou 1. A matriz simulada 6×6 (200/301/302/404/500/000), nos dois modos strict, totalizou 72 casos; somente API=200 + web=200 + rc=0 promoveu marker. Actionlint 1.7.12 nos seis workflows: exit 0. |
| 2 — invalidação antes do commit | `passed` | Focal real: **21 passed** no conjunto request/cache/ingestão. Os testes transacionais cobriram `save_model` e action: callback não ocorreu dentro de `atomic`, ocorreu uma vez após commit e as três chaves foram limpas; no rollback o status permaneceu anterior, as chaves permaneceram e o callback não ocorreu. Acrescentei teste de rollback para `_persistir_grupo`/ingestão. Auditoria independente: `decidir_fila` tem um único caller (`FilaDecisaoView`), não há `ATOMIC_REQUESTS` nem `transaction.atomic` no serviço/view; a invalidação imediata do painel é imediata por desenho. Ingestão usa `on_commit` dentro de `_persistir_grupo`/`_persistir_grupo_mesclado`, ambos atômicos. |
| 3 — `strip()` antes da validação do request ID | `passed` | `config/tests/test_request_id.py` agora tem **13 passed**. Testei U+0085 nas bordas, U+0085 interno, newline e tab: todos geraram UUID4 imprimível, não propagaram controle para header/request e o `RequestIdLogFilter` gravou o mesmo ID. O teste compara header, `request.request_id`, `request.META`, log e `EventoBusca.request_id`; OWS ASCII (`' id '`) foi preservado como núcleo válido e dois IDs distintos não colidiram; dois IDs longos distintos foram persistidos separadamente. |
| 4 — anos civis 0000–0099 | `passed` | Script real em Node 18.20.8 e 20.20.2 × UTC/Tokyo: 4/4 exit 0. Executei também harness independente com todos os 12 formatadores e expectativas exatas para `0000-01-01`, `0001-01-01`, `0096-02-29`, `2026-09-23` e `0095-02-29`; os três primeiros preservaram ano com quatro dígitos, o último retornou vazio em todos os formatadores temporais. A adulteração de `dataPorExtenso` no check falhou com exit 1 nos quatro ambientes. |
| 5 — asserts do check de datas | `passed` | O check real compara valores exatos para as 12 saídas e para os limites civis; a mutação negativa explícita falhou 4/4. `npx tsc --noEmit` e `npm run build` (59/59 páginas) passaram. |
| 6 — Python 3.13 versus 3.12 | `passed` | Grep em README, CI-CD, scripts, workflows, infra, Dockerfiles e compose não encontrou afirmação ativa de 3.13; README, `init-local.ps1`, CI e Dockerfile apontam para 3.12. `python:3.12-slim` executou `pip check`, `manage.py check` e a suíte. PowerShell não foi executado por ausência de `pwsh`; a limitação está registrada abaixo. |

### Testes acrescentados/ajustados neste reteste

- `backend/config/tests/test_request_id.py`: matriz end-to-end de U+0085 nas bordas, controles internos, igualdade header/request/log/DB e segurança de resposta; OWS ASCII com igualdade no request.
- `backend/catalogo_noticias/tests/test_p2_ingestao_performance.py`: rollback real da ingestão com `transaction.atomic`, confirmando ausência de callback, preservação das três chaves e ausência do item persistido.

### Comandos e métricas finais

- **Probe:** matriz simulada **72/72** com resultados esperados; caso real de transferência parcial `200/rc=18`; `bash -n` do script renderizado e actionlint 1.7.12 — exit 0.
- **Datas:** script real 4/4; harness de todos os formatadores 8/8; mutação negativa 4/4 (exit 1 esperado em cada caso) — conforme esperado.
- **Cache/request/ingestão focal:** `21 passed`, 0 failed, exit 0; request ID isolado: `13 passed`, exit 0.
- **Suíte completa em Python 3.12.14 + PostgreSQL 16:** `python -m pytest -q -o cache_dir=/tmp/pytest-cache --cov=. --cov-report=term-missing --cov-fail-under=80` — **486 passed, 0 failed, 184 warnings, cobertura 88.71%, exit 0**; `pip check` e `manage.py check` também passaram. A primeira tentativa com o repositório read-only falhou somente porque testes de credenciamento tentaram criar `backend/media`; repeti com `media` em tmpfs gravável, sem alterar o código, e a suíte completa passou.
- **Frontend:** `npx tsc --noEmit` exit 0; `npm run build` exit 0, **59/59** páginas.
- **Workflows:** actionlint, parser YAML com duplicatas e relações `verify`/`tls_enabled`/`concurrency`/rollback — exit 0.
- **Caddy:** `caddy validate`/`adapt` com placeholders, e roteamento HTTP real privado=404, público=200, desconhecido=404 — pass.
- **Integridade:** `git diff --check` exit 0; sem diff em migrations ou `ingestao-service/`; SHA-256 do run-state TLS antes/depois: `7c57ea9bfe8ebe2920247f94aa9d73b9b1efd152a3286b226a8ab20954f5dc4f`; `loteA-bugs/` não foi editado.

### Findings e limitações do reteste

- **Finding funcional/regressão:** nenhum; os seis findings foram reproduzidos ou testados e passaram.
- Não houve GitHub Actions, VPS, DNS ou TLS reais; o probe foi executado contra o corpo real do workflow e servidores HTTP locais, conforme o escopo do contrato.
- `pwsh` não está instalado; o bootstrap foi validado estaticamente e o runtime Python 3.12 foi executado em container.
- Redis real não foi exercitado; o cache de teste usa LocMem e o comportamento best-effort foi coberto por indisponibilidade. Não houve critério `blocked`.

## Remediação — iteração 2 (nits finais)

**Data:** 2026-09-24

**Branch:** `perf/custo-performance-p0-p2`

**Execução:** fechamento dos dois nits da revisão final, sem commit e sem alteração de `run-state.json` ou `code-review-contract.md`.

| Nit | Status | Resultado |
|---|---|---|
| 1 — comentário afirmava atomic indevido no Django 5.2 | **resolved** | Comentário corrigido para refletir autocommit e a manutenção de `on_commit` como API correta/forward-safe. |
| 2 — actions invalidavam cache sem mudança efetiva | **resolved** | Approve/reject restringem o update a itens diferentes do destino e invalidam apenas quando o retorno é maior que zero. |

### NIT 1 — resolved

- **Arquivo/linhas:** `backend/catalogo_noticias/admin.py:100-112`.
- **Mudança:** o comentário anterior, que atribuía `transaction.atomic` ao `response_action` do Django 5.2, foi removido. O novo comentário registra que esse caminho é autocommit e explica que `transaction.on_commit` continua correto: em autocommit executa após o update e, se uma versão futura ou um caller envolver a action em transação atômica, adia a invalidação até o commit.
- **Teste/resultado:** `manage.py check`, suíte completa e inspeções estáticas passaram; nenhuma afirmação de atomic no `response_action` permanece no arquivo.

### NIT 2 — resolved

- **Arquivos/linhas:** `backend/catalogo_noticias/admin.py:101-123`; `backend/painel_admin/tests/test_sanity.py:225-353`.
- **Mudança:** approve e reject agora aplicam `queryset.exclude(status_revisao=<destino>).update(...)`. O retorno `atualizados` identifica a quantidade efetivamente alterada; `transaction.on_commit(invalidar_cache_autocomplete)` só é registrado quando `atualizados > 0`. As actions continuam retornando `None`, e seleções mistas atualizam todos os itens diferentes do destino.
- **Teste/resultado:** testes parametrizados cobriram approve e reject. Com dois itens já no destino, o mock do callback não foi chamado e `categorias`, `titulos` e `populares` permaneceram. Com seleção mista contendo um item já no destino, um pendente e um no outro status, o callback não ocorreu dentro de `atomic`, ocorreu exatamente uma vez após o commit e as três chaves foram limpas; todos os itens terminaram no destino e ambas as actions mantiveram retorno `None`.

### Validações da iteração 2

- **Focal PostgreSQL 16:** `pytest -q painel_admin/tests/test_sanity.py` — **34 passed**, exit 0.
- **Suíte Python 3.12.14 + PostgreSQL 16 real:** `pytest -q --cov=. --cov-report=term-missing --cov-fail-under=80` — **490 passed**, 0 failed, **88.74%** de cobertura, gate 80% atendido, exit 0.
- **Django:** `manage.py check` — `System check identified no issues`, exit 0.
- **Frontend:** `npx tsc --noEmit` — exit 0; `npm run build` — exit 0, **59/59** páginas.
- **Workflows:** `actionlint 1.7.12` nos seis workflows — exit 0.
- **Integridade:** `git diff --check` — exit 0; nenhum diff em migrations ou `ingestao-service/`; SHA-256 do run-state TLS preservado em `7c57ea9bfe8ebe2920247f94aa9d73b9b1efd152a3286b226a8ab20954f5dc4f`; `agentic-framework/state/loteA-bugs/` não foi editado; nenhum commit criado.

### Riscos residuais da iteração 2

- Nenhum risco funcional novo identificado; a proteção contra rollback e a semântica forward-safe permanecem cobertas pelos testes transacionais existentes.
- Não houve GitHub Actions real; `actionlint` e a suíte local foram as validações executáveis estáticas/de comportamento disponíveis.

## Reteste final — iteração 3

**Veredito:** `passed`.

Esta seção é append-only e preserva as seções de implementação, remediação e reteste anteriores. O tester validou independentemente os dois nits finais e repetiu os gates habituais. Não alterei código de produção, `run-state.json`, `code-review-contract.md` ou `agentic-framework/state/loteA-bugs/`, e não fiz commit.

### Matriz dos 2 nits

| Nit | Resultado | Evidência independente |
|---|---|---|
| 1 — comentário sobre `response_action`/`on_commit` | `passed` | O comentário atual contém explicitamente Django 5.2, `response_action`, `autocommit`, `on_commit` e o cenário futuro com `atomic`. O teste no-op confirmou `connection.in_atomic_block=False` no caminho da action; o teste de seleção mista repetiu a action dentro de `transaction.atomic` e confirmou que o mesmo `on_commit` fica deferred até o commit. A asserção é forward-safe e a descrição corresponde ao comportamento real. |
| 2 — actions idempotentes e seleção mista | `passed` | Focal final: **4 passed** (approve/reject × no-op/misto). No-op: `QuerySet.update` retornou `[0]`, nenhum callback foi chamado, as três chaves permaneceram e a action retornou `None`. Misto: exatamente uma instrução `UPDATE` com exclusão do status destino, apenas os itens diferentes mudaram, o callback não ocorreu antes do commit e ocorreu uma única vez depois; `categorias`, `titulos` e `populares` foram limpas, e approve/reject retornaram `None`. |

### Testes ajustados

Apenas `backend/painel_admin/tests/test_sanity.py` foi reforçado pelo tester para medir o retorno efetivo de `QuerySet.update` e o caminho autocommit. A primeira tentativa de inferir “nenhum update” pela ausência de SQL foi descartada porque o Django pode emitir um `UPDATE` zero-row; a verificação final usa o retorno efetivo `0`, que é o contrato relevante. Nenhum arquivo de produção foi editado.

### Gates e métricas finais

- **Focal dos nits:** `pytest -q painel_admin/tests/test_sanity.py -k 'action_sem_mudanca or action_mista'` — **4 passed**, 0 failed, exit 0.
- **Suíte completa:** Python 3.12.14 + PostgreSQL 16 real, `pytest -q -o cache_dir=/tmp/pytest-cache --cov=. --cov-report=term-missing --cov-fail-under=80` — **490 passed**, 0 failed, **88.75%** de cobertura, gate 80% atendido, 184 warnings, exit 0.
- **Python:** `pip check` sem quebras; `manage.py check` — `System check identified no issues`, exit 0.
- **Datas:** script real em Node 18.20.8 e 20.20.2 × `TZ=UTC`/`Asia/Tokyo` — **4/4 exit 0**.
- **Frontend:** `npx tsc --noEmit` exit 0; `npm run build` exit 0, **59/59** páginas.
- **Workflows:** actionlint 1.7.12 nos seis arquivos, exit 0; parser YAML sem chaves duplicadas e relações `verify`/`tls_enabled`/`concurrency`/rollback, exit 0.
- **Integridade:** `git diff --check` exit 0; nenhum diff em `migrations/` ou `ingestao-service/`; SHA-256 do run-state TLS preservado em `7c57ea9bfe8ebe2920247f94aa9d73b9b1efd152a3286b226a8ab20954f5dc4f`; `loteA-bugs/` não foi editado.

### Findings e limitações

- **Finding/regressão funcional:** nenhum; os dois nits passaram e a suíte completa permaneceu verde.
- Não houve GitHub Actions, VPS, DNS ou TLS reais; Redis real e `pwsh` também não foram exercitados. Essas limitações não bloquearam os nits nem os gates executáveis.
- Nenhum commit foi criado.

## Síntese cronológica e referências do fechamento

Esta seção foi acrescentada pelo `historian` ao encerrar a execução; todas as evidências anteriores, inclusive as rodadas de teste independentes e as duas remediações, permanecem preservadas acima.

1. **2026-09-24 — executor / implementação inicial:** o lote A foi materializado no working tree, sem commit, e corrigiu os oito itens do contrato. A implementação canônica e auditável está em `agentic-framework/state/run-20260924-1330-bugs-pendencias/`; `agentic-framework/state/loteA-bugs/` foi mantido apenas como artefato temporário de provenance criado pelo executor.
2. **2026-09-24 — tester / verificação inicial:** a matriz independente dos 12 critérios passou; a primeira suíte completa registrada foi 476 testes em PostgreSQL 16, com 88,60% de cobertura.
3. **2026-09-24 — reviewer / iteração 1:** veredito `changes_requested`, com seis findings acumulados (quatro major e dois minor).
4. **2026-09-24 — remediator / iteração 1:** os seis findings foram resolvidos e o reteste independente passou com 486 testes e 88,71% de cobertura.
5. **2026-09-24 — reviewer / iteração 2:** veredito `approve_with_comments`, com os seis findings anteriores confirmados como resolvidos e dois nits residuais registrados.
6. **2026-09-24 — remediator / iteração 2:** os dois nits finais foram resolvidos; o commentário transacional e as actions idempotentes foram alinhados ao comportamento real.
7. **2026-09-24 — tester / reteste final:** veredito `passed`, com 490 testes em PostgreSQL 16, 88,75% de cobertura, datas 4/4, build 59/59 e actionlint limpo.
8. **2026-09-24 — reviewer / reconciliação final:** veredito `approve`, 0 blocker, 0 major, 0 minor e 0 nit; os oito findings acumulados ficaram resolvidos.
9. **2026-09-24 — documenter:** `README.md`, `CI-CD.md` e `infra/DEPLOY.md` foram alinhados ao comportamento validado; o registro detalhado está em `documentation-update.md`.
10. **2026-09-24 — historian:** `report.md` foi consolidado, a linha append-only foi acrescentada ao ledger e o `run-state.json` foi finalizado como `closed`/`done`.

### Referências auditáveis

- Contratos e decisões: `task-plan.md`, `implementation-contract.md` e `code-review-contract.md` nesta pasta.
- Evidências de execução, testes e limitações: `implementation-history.md` e `documentation-update.md` nesta pasta.
- Documentação conferida: `README.md`, `CI-CD.md` e `infra/DEPLOY.md`; o diff real também confirmou que não houve alteração em migrations ou `ingestao-service/`.
- O run-state concorrente `agentic-framework/state/run-20260924-1400-tls-ingestao/run-state.json` foi preservado fora do escopo; o SHA-256 registrado nas evidências permaneceu `7c57ea9bfe8ebe2920247f94aa9d73b9b1efd152a3286b226a8ab20954f5dc4f`.
- `agentic-framework/state/loteA-bugs/implementation-history.md` permaneceu intacto, com SHA-256 `16d394a4816725b4edfa95f5a1f052395ffee21a17faa027e265bb0fb0f28889`; não foi removido sem autorização.

