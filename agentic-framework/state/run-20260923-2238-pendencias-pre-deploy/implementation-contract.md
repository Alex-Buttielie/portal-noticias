# Implementation Contract — 20260923-2238-pendencias-pre-deploy

## Metadados
- **run_id:** 20260923-2238-pendencias-pre-deploy
- **Deriva de:** task-plan.md (20260923-2238-pendencias-pre-deploy)
- **Versão do contrato:** 1

## O que deve ser validado/ajustado

### Parte A — ingestão 202+background (WIP não verificado)
1. `backend/catalogo_noticias/robos_views.py`: `POST /api/admin/robos/executar/` devolve `202` com `{detail, request_id}` e executa `executar_ingestao()` em thread daemon, com `close_old_connections()` no início e no `finally`, log de sucesso/falha com `request_id` e sem traceback vazio.
2. `frontend/lib/api.ts` + `frontend/lib/queries.ts` + `frontend/app/admin/robos/page.tsx`: tipagem da resposta 202 e UI que informa "acompanhe na lista de execuções" em vez de esperar o corpo completo.

### Parte B — serving (já implementado, entra no mesmo release)
3. `backend/gunicorn.conf.py`: `gthread`, `threads >= 2`, `timeout <= 60` (45), workers/bind por env, `max_requests` com jitter, log de access com `X-Request-ID`.
4. `backend/Dockerfile` e `.github/workflows/deploy.yml`: sem flags de worker/timeout duplicadas; o conf é a fonte única.
5. `infra/nginx/portal-{dev,homolog,prod}.conf`: gzip, `upstream` + `keepalive`, `proxy_cache` em `/api/feed/` e `/api/radar/tendencias/` com TTL 45s e chave sem cookie, `/static/` e `/media/` servidos por alias, `limit_req` para escrita pública, `proxy_read_timeout 45s`.

### Parte C — documentação de operação (follow-ups do reviewer)
6. `infra/DEPLOY.md`: runbook do reload com as zonas globais obrigatórias no `nginx.conf` da VPS (`proxy_cache_path`, `limit_req_zone`), como invalidar o cache e o que fazer se `nginx -t` falhar.
7. Registrar no artefato da run que o TTL de 45s do gating é o mecanismo oficial de invalidação e que `numero_fontes_distintas` só é recalculado pela ingestão e por `save_related` do admin de cluster (editar item isolado pelo admin não recalcula).

## Áreas/arquivos esperados
- `backend/catalogo_noticias/robos_views.py`
- `backend/gunicorn.conf.py`, `backend/Dockerfile`, `.github/workflows/deploy.yml`
- `infra/nginx/portal-dev.conf`, `infra/nginx/portal-homolog.conf`, `infra/nginx/portal-prod.conf`
- `infra/DEPLOY.md`
- testes de `backend/catalogo_noticias/tests/` para o 202
- `agentic-framework/state/run-20260923-2238-pendencias-pre-deploy/` (artefatos)

## Interfaces afetadas
- **API pública:** `POST /api/admin/robos/executar/` deixa de devolver `201` com o registro e passa a devolver `202` com `{detail, request_id}`. O registro continua disponível em `GET /api/admin/robos/execucoes/`. Frontend migrado na mesma mudança.
- Comportamento observável de infra: compressão gzip, `X-Cache-Status`, estático/mídia servidos pelo Nginx.

## Critérios de aceite (técnicos, testáveis)
1. Existe teste que faz `POST /api/admin/robos/executar/` e prova `202` + corpo `{detail, request_id}`, e que a execução aparece em `/execucoes/` depois.
2. O teste não deixa a ingestão pendurada: a thread é aguardada ou o estado é verificado por polling com timeout, sem flake.
3. `backend/gunicorn.conf.py` é carregável pelo gunicorn (`gunicorn --check-config` ou import direto) e declara `gthread`, `threads >= 2`, `timeout <= 60`.
4. `tsc --noEmit` passa com a mudança de tipagem do 202.
5. `nginx -t` passa nos 3 confs se o binário existir; se não existir, a revisão de sintaxe confere diretivas balanceadas (chaves, `location`, `upstream`) e o relatório registra a limitação.
6. `proxy_cache_key` não contém `$cookie_*` nem `$http_authorization`, e existem `proxy_cache_bypass`/`proxy_no_cache` para sessão.
7. Nenhum `proxy_read_timeout` continua em 180s nos locations tocados (alineado a 45s).
8. Suíte completa passa com o gate de cobertura de 80.

## Não-objetivos
- Celery para a ingestão; TLS/HTTP2; P1-5/P1-6; mudança do default de preço em `ingestao-service/`.

## Restrições técnicas
- O par 202 + timeout 45s é atômico: não mergear um sem o outro.
- Comentários em português no padrão do projeto.

## Definição de pronto (Definition of Done)
- [ ] Critérios de aceite validados
- [ ] Suíte + tsc verdes
- [ ] Revisão feita
- [ ] `infra/DEPLOY.md` com o runbook de VPS
- [ ] `implementation-history.md` coerente
