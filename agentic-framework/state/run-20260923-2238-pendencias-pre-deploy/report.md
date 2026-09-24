# Report — 20260923-2238-pendencias-pre-deploy

## Metadados
- **run_id:** 20260923-2238-pendencias-pre-deploy
- **Tarefa:** validação pré-deploy da ingestão 202+background e do serving P1-3/P1-4
- **Resultado final:** veredito técnico 8/8 passed; **release bloqueado por credencial** (PAT sem escopo `workflow`) e por ação humana na VPS (zonas globais do Nginx)

## Veredito por critério

| Critério | Veredito | Evidência |
|---|---|---|
| 1 — POST 202, corpo e execução posterior | **passed** | `test_robos_background.py`; `1 passed`. O mock fica bloqueado até a resposta, grava `RegistroExecucaoIngestao` e o teste encontra o registro via GET. |
| 2 — thread não pendurada/sem flake | **passed** | mesmo teste usa `Event.wait(timeout=10)`, polling com deadline e espera a thread `ingestao-manual-*` terminar; 3 execuções consecutivas passaram. |
| 3 — Gunicorn | **passed** | `gunicorn --check-config ...` → exit 0; valores default: `gthread`, `threads=4`, `timeout=45`, `workers=2`, `max_requests=1000`, jitter `100`. |
| 4 — tipagem frontend | **passed** | `npx tsc --noEmit` → exit 0. |
| 5 — sintaxe Nginx | **passed (revisão estática)** | `which nginx` → ausente; parser local: 3/3 com chaves balanceadas, 8 `location` e 1 `upstream`; `nginx -t` real fica pendente na VPS. |
| 6 — cache sem credenciais | **passed** | 3/3: `proxy_cache_key "$scheme$request_method$host$request_uri"`, sem `$cookie_*`/`$http_authorization`; `proxy_cache_bypass` e `proxy_no_cache` presentes. |
| 7 — timeout | **passed** | grep nos 3 confs: somente `proxy_read_timeout 45s`; nenhuma ocorrência de `180s`. |
| 8 — suíte/cobertura | **passed** | `435 passed`, cobertura `87.89%` (gate 80%, exit 0). |

## Correções aplicadas após a validação (remediation do orchestrator)

1. **Vazamento de histórico de busca entre visitantes (corrigido).** O regex
   `^/api/(feed/|radar/tendencias/)` capturava também `feed/busca/historico/`,
   cujo payload é por usuário/sessão (`feed/views.py:365-372`); a chave de
   cache é `$scheme$request_method$host$request_uri`, sem componente de
   usuário — a resposta de um visitante seria servida a outro. Substituído
   por allowlist explícita das 9 rotas GET públicas que não variam por
   usuário. Regex validado com 15 casos (9 match, 6 no-match), incluindo
   `busca/historico/`, `interacoes/`, `cobertura/`, `cluster/`, `item/`.
2. **`POST /api/feed/interacoes/` escapava do rate limit (corrigido).** Como
   `location` regex tem precedência sobre prefix location, o POST público de
   interações caía no bloco de cache e não herdava o `limit_req zone=escrita_publica`
   de `location /api/`; a view é `AllowAny` e não tem throttle DRF. Fora da
   allowlist, volta a ser tratado por `location /api/`.
3. **Overrides do Gunicorn podiam violar os limites (corrigido).** `_int_env`
   agora recebe `minimo`/`maximo`: `GUNICORN_THREADS=1` → 2 (gthread com 1
   thread perde o benefício) e `GUNICORN_TIMEOUT=180` → 60 (mantém o par
   servidor/`proxy_read_timeout` alinhado). Verificado por execução.
4. **Runbook de VPS (corrigido).** `infra/DEPLOY.md` agora traz a seção
   "Nginx na VPS: zonas globais obrigatórias (P1-4)" com o bloco exato a
   inserir no `http {}` de `/etc/nginx/nginx.conf`, o gate `nginx -t` antes
   do reload, como invalidar o cache e o que a allowlist cobre/não cobre.
5. **Docstring que prometia mais do que o código faz (corrigido).** O
   docstring de `_executar_ingestao_em_background` afirmava que a falha
   também fica no banco; `executar_ingestao()` só grava o registro ao
   concluir. Documentado que a falha vai para o log com `request_id` e que
   persistir a falha é backlog.
6. **Comentário obsoleto nos confs (corrigido).** As três portas
   `proxy_read_timeout 45s` citavam um stash pelo nome; agora referenciam
   `catalogo_noticias/robos_views.py`.

Revalidação após as correções: **435 passed, cobertura 87.89%**, `tsc --noEmit`
exit 0, `gunicorn --check-config` exit 0, 3/3 confs com chaves balanceadas,
0 ocorrências de `proxy_read_timeout 180s`.

## Teste adicionado

- `backend/catalogo_noticias/tests/test_robos_background.py`: cobre o POST real com `executar_ingestao` mockado, segura a thread para provar que o 202 retorna antes do trabalho, grava um registro no banco, faz polling autenticado do endpoint de execuções e verifica que a thread termina. Nenhuma ingestão/rede real é disparada.

## Bloqueadores de release (pendentes de ação humana)

1. **Push bloqueado por credencial.** O PAT embutido na URL do remote
   (`https://<token>@github.com/...`) não tem escopo `workflow`; o GitHub
   recusa qualquer push que toque `.github/workflows/deploy.yml`. Como o
   commit `93b919d` altera esse arquivo, ele não sobe. Requer token com
   escopo `workflow` (ou push manual).
2. **Ação na VPS antes do reload.** Adicionar as zonas globais
   (`proxy_cache_path` + 2 `limit_req_zone`) no `http {}` de
   `/etc/nginx/nginx.conf` e rodar `nginx -t` — conforme o runbook em
   `infra/DEPLOY.md`. Sem isso o reload falha e o ambiente fica sem cache.
3. **Validação real do Nginx não executada.** O binário não existe neste
   ambiente; a revisão de sintaxe passou, mas `nginx -t` real só na VPS.

## Melhorias / riscos não bloqueantes

- Threads daemon podem ser encerradas em restart do PM2 durante uma ingestão e
  não há lock contra execuções manuais simultâneas. Mitigação de curto prazo:
  documentado no docstring. Correção real: migrar a ingestão manual para Celery.
- A suíte emitiu 185 warnings (inclui `ResourceWarning` de SQLite e diretório
  `staticfiles` ausente), sem impacto no gate.

## Artefatos
- `task-plan.md`
- `implementation-contract.md`
- `report.md`
- `backend/catalogo_noticias/tests/test_robos_background.py`
