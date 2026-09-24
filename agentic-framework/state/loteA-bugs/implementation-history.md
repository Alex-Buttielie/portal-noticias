# Implementation History — lote A (bugs e pendências)

**Data:** 2026-09-24
**Branch:** `perf/custo-performance-p0-p2`
**Execução:** somente working tree, sem commit e sem criação de branch. Não houve alteração em `ingestao-service/` nem em migrations.

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
- **O que estava errado:** `handle_path /media/*` servia `/srv/media` inteiro. Assim, `media/credenciamento/<user_id>/...` podia ser obtido diretamente pelo edge, sem passar pela `DocumentoView` autenticada.
- **O que mudou:**
  - matcher explícito para `/media/credenciamento` e seus descendentes, com `respond 404`;
  - `handle_path /media/public/*` com raiz isolada `/srv/media/public`;
  - fallback `handle /media*` que fecha `/media/`, a raiz e qualquer subtree desconhecida.
  A ordem foi comparada ao padrão Nginx em `infra/nginx/portal-prod.conf:126-157`.
- **Como foi verificado:**
  - comando solicitado, com placeholders de domínio não definidos, reproduziu o erro esperado de expansão vazia (`header` fora de um site block);
  - validação com cópia temporária substituindo `{$DOMAIN_API}` e `{$DOMAIN_FRONTEND}` por domínios de teste: `Valid configuration`, exit `0`;
  - `caddy adapt` também concluiu com sucesso e mostrou as rotas na ordem privada-negada → pública → fallback.

## Bug 2 — Radar mostra o dia anterior

- **Arquivo:linhas:** `frontend/lib/datas.ts:20-95`; chamada permanece em `frontend/app/radar/RadarClient.tsx:189`.
- **O que estava errado:** `new Date("2026-09-23")` segue a parsing de data-only da ECMAScript e representa midnight UTC. Ao formatar em `America/Sao_Paulo`, o valor virava `22/09/2026`.
- **O que mudou:** strings que casam com `YYYY-MM-DD` são extraídas como uma data civil, validadas e fornecidas ao `Intl` como uma referência de calendário estável. O input civil não é convertido em um instante UTC; instantes normais continuam passando por `new Date(valor)` e pelo fuso editorial `America/Sao_Paulo`.
- **Como foi verificado:**
  - `TZ=UTC node scripts/verificar-datas-tz.mjs`: data civil `23/09/2026`, instante `23/09/2026`, hora `18:30`;
  - `TZ=Asia/Tokyo node scripts/verificar-datas-tz.mjs`: mesmas três saídas;
  - dentro de `node:18-alpine` (v18.20.8) e `node:20-alpine` (v20.20.2), ambos os TZ passaram;
  - `npx tsc --noEmit` e `npm run build` passaram.

## Bug 3 — colisão de `X-Request-ID`

- **Arquivo:linhas:** `backend/config/middleware.py:23-47,89-107`; teste `backend/config/tests/test_request_id.py:20-47`.
- **O que estava errado:** o middleware reutilizava um header arbitrário do cliente, enquanto `EventoBusca.request_id` é `unique=True` e `max_length=64`. A task truncava tarde; dois IDs longos ainda podiam chegar ao mesmo valor gravado.
- **O que mudou:** `normalizar_request_id()` valida antes da propagação: preserva IDs válidos até 64 caracteres, remove espaços nas pontas e gera UUID4 para vazio, sentinel `-`, excessivo ou não imprimível. O valor final é colocado em `request.META`, em `request.request_id`, no ContextVar e no response; a task recebe o mesmo valor, sem uma segunda transformação para esse caso.
- **Como foi verificado:**
  - teste focal `2 passed`;
  - o teste compara `response["X-Request-ID"]`, `request.request_id`, `request.META[...]` e `EventoBusca.request_id`, e executa a task real com o valor propagado;
  - teste de dois IDs longos distintos confirma UUIDs distintos e comprimento dentro de 64;
  - suíte completa: `465 passed`.

## Bug 4 — cache do autocomplete não invalidado ao aprovar/rejeitar

- **Arquivo:linhas:** `backend/painel_admin/services.py:13-41`; `backend/catalogo_noticias/admin.py:82-108`; teste `backend/painel_admin/tests/test_sanity.py:139-169`.
- **O que estava errado:** `decidir_fila()` e as actions do admin alteravam `status_revisao`, mas não limpavam `feed:autocomplete:v2:{categorias,titulos,populares}`. O snapshot de títulos continuava mostrando item pendente/rejeitado até o TTL.
- **O que mudou:** a decisão da API invalida o cache após a escrita; as actions de aprovação/rejeição e a edição direta do status no admin também invalidam. A função existente continua tratando falhas de cache como não fatais.
- **Como foi verificado:** teste focal com cache LocMem semeou as três chaves, aprovou via `/api/admin/fila/<id>/decisao/` e confirmou `cache.get(...) is None` para todas; `2 passed` no conjunto focal e suíte completa verde.

## Bug 5 — marker `.deployed-sha` promovido com web em 3xx

- **Arquivo:linhas:** `.github/workflows/deploy.yml:476-531,533-552`.
- **O que estava errado:** `curl -sf` retorna sucesso para respostas 3xx; um redirect da home podia marcar `WEB_OK=1` e promover o SHA.
- **O que mudou:** ambos os probes capturam `%{http_code}` com `curl -w`, normalizam erro para `000` e só definem `API_OK`/`WEB_OK` quando o código é exatamente `200`. O marker continua condicionado aos dois flags, ao resultado do job de deploy e ao SHA efetivamente verificado.
- **Como foi verificado:** inspeção do shell e `actionlint` confirmaram a removal de `curl -sf`; a lógica de comparação foi validada no workflow e o actionlint passou para todos os workflows. A barreira existente de `DEPLOY_RESULT`/SHA permanece no bloco do marker.

## Bug 6 — script de datas depende de Node 24 experimental

- **Arquivo:linhas:** `frontend/scripts/verificar-datas-tz.mjs:1-68`; CI em `.github/workflows/ci.yml:90-96`.
- **O que estava errado:** o `.mjs` importava diretamente `../lib/datas.ts` e precisava de `node --experimental-strip-types`, que não existe no Node 18/20 suportado pelo projeto. O check também não fazia asserções.
- **O que mudou:** o script continua JavaScript puro, sem a flag experimental. Ele transpila em memória o módulo TypeScript real usando a dependência `typescript` já presente, importa o JavaScript resultante e falha com asserção se a data civil ou o instante com fuso estiverem errados. O job frontend agora executa o script com `TZ=UTC` e `TZ=Asia/Tokyo` antes de `tsc`/build.
- **Como foi verificado:** passou no Node local e em containers Node 18.20.8 e 20.20.2, nos dois TZ; o build frontend também passou.

## Bug 7 — pytest no runtime

- **Arquivo:linhas:** `backend/requirements.txt:55-56`; novo `backend/requirements-dev.txt:1-8`; `backend/requirements-lock.txt:1-14`; `backend/.dockerignore:12`; CI `.github/workflows/ci.yml:65-72`; bootstrap local `scripts/init-local.ps1:117-120`.
- **O que estava errado:** `pytest-django` e `pytest-cov` estavam no arquivo enviado ao Dockerfile/PM2, e o lock compartilhado também carregava `pytest`, `pytest-cov`, `pytest-django` e dependências exclusivas de teste.
- **O que mudou e decisão:** `requirements.txt` agora é runtime puro; `requirements-dev.txt` contém `-r requirements.txt` e as três ferramentas de teste. O lock foi reduzido ao conjunto runtime e documenta que o CI instala o lock runtime e depois o arquivo dev; o `.dockerignore` também exclui o manifesto dev da imagem. O bootstrap local passou a instalar o arquivo dev, enquanto o deploy PM2 continua usando somente `requirements-lock.txt`; portanto nenhum `pytest*` entra na imagem/produção.
- **Como foi verificado:**
  - `pip install --dry-run --ignore-installed -r backend/requirements-lock.txt` resolveu o conjunto runtime sem ferramentas de teste;
  - instalação em diretório isolado com o lock: exit `0`, e a verificação explícita não encontrou `pytest*`/`coverage`;
  - `backend/.venv/bin/python -m pip check`: `No broken requirements found`;
  - CI foi ajustado para instalar `requirements-lock.txt` e `requirements-dev.txt`, incluindo ambos no cache do setup-python.

## Bug 8 — revalidar workflows tocados por duas runs

- **Arquivo:linhas:** `.github/workflows/ci.yml`, `.github/workflows/deploy.yml`, `.github/workflows/deploy-dev.yml`, `.github/workflows/deploy-prod.yml`, `.github/workflows/rollback.yml` (e `deploy-homolog.yml`, que também foi validado).
- **O que estava errado:** as duas runs anteriores tinham deixado validação cruzada pendente; o probe web acceptava 3xx e o lock/runtime ainda estava acoplado.
- **O que mudou:** não foi necessário alterar a topologia de callers. O reusable mantém `verify` (`deploy.yml:113-125`), `concurrency` por ambiente (`108-110`), `tls_enabled` explícito, e `rollback.yml:126-149` reutiliza o mesmo gate com SHA verificado e `strict_validate: true`. A única mudança de workflow neste lote foi o probe explícito e os checks de requirements/data.
- **Como foi verificado:**
  - `actionlint 1.7.12 .github/workflows/*.yml`: exit `0`, sem findings;
  - parser PyYAML com construtor de chaves duplicadas: `OK` para `ci.yml`, `deploy.yml`, `deploy-dev.yml`, `deploy-prod.yml`, `deploy-homolog.yml` e `rollback.yml`;
  - checagem estrutural automatizada confirmou `deploy.needs=verify`, `validate.needs=[verify,deploy]`, grupo `portal-deploy-${{ inputs.environment_name }}`, `cancel-in-progress=false`, `verify_ref` nos callers e `strict_validate=true` no rollback;
  - `git diff --check`: exit `0`.

## Validações finais

- Backend, comando solicitado: `DJANGO_DB_ENGINE=sqlite3 DJANGO_CACHE_BACKEND=locmem .venv/bin/python -m pytest -q -p no:cacheprovider --cov-fail-under=80` → **465 passed**.
- Backend com gate de cobertura do CI: `--cov=. --cov-report=term-missing --cov-fail-under=80` → **465 passed, 87.90%** (limite de 80 atendido).
- Frontend: `npx tsc --noEmit && npm run build` → **exit 0**, 59/59 páginas.
- Caddy: validação com domínios substituídos em arquivo temporário → **Valid configuration**.
- Workflows: actionlint + YAML/duplicatas + coerência de gate/TLS/concurrency/rollback → **exit 0**.
