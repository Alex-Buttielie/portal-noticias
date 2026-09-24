# Task Plan — 20260923-2238-pendencias-pre-deploy

## Metadados
- **run_id:** 20260923-2238-pendencias-pre-deploy
- **Data de abertura:** 2026-09-23
- **Solicitado por:** Alex (humano) — "preciso resolver as pendências"
- **Spec de origem:** `ANALISE_CUSTO_PERFORMANCE.md` (seção 7: P1-3/P1-4/P1-5/P1-6) + pendências apontadas na verificação pré-deploy

## Objetivo
Fechar as pendências que ficaram abertas no ciclo de deploy anterior: (a) a mudança de ingestão 202+background que sustenta o timeout curto; (b) a pré-condição de VPS para o cache de borda do Nginx; (c) os follow-ups do reviewer que só pedem documentação/ajuste; e (d) destravar o push da develop (escopo do PAT).

## Escopo
### Dentro do escopo
- Validar a mudança `POST /api/admin/robos/executar/` → 202 + thread daemon (WIP não verificado, commit `93b919d` já assume que ela existe).
- Consolidar P1-3 (`backend/gunicorn.conf.py` + Dockerfile + deploy.yml) e P1-4 (gzip/proxy_cache/limit_req/keepalive nos 3 confs) em um único release, já que são acoplados pelo timeout de 45s.
- Registrar em `infra/DEPLOY.md` o runbook de VPS: zonas globais no `nginx.conf` (`proxy_cache_path`, `limit_req_zone`) obrigatórias para o reload, e o comportamento de proxy_cache_bypass.
- Documentar TTL 45s do gating como invalidação oficial (follow-up 5 do reviewer) e a necessidade de backfill/recompute de `numero_fontes_distintas` ao editar item no admin (follow-up 1).
- Resolver o bloqueio de push (PAT sem escopo `workflow`) com o usuário.

### Fora do escopo (explicitamente)
- TLS/HTTP2 em PROD e backup (P0-2/P0-3) — exigem decisão/credencial na VPS.
- P1-5 (build no CI, concurrency) e P1-6 (React Query) — runs próprias.
- Reescrever a ingestão em Celery (o WIP usa thread daemon; migração para Celery vira backlog).
- Coluna de produção com default 0.15 e o default repetido em `ingestao-service/` (follow-ups herdados do P0).

## Suposições assumidas
- O deploy de PROD pode ser feito com o `migrate` em janela fria, conforme nota já publicada em `infra/DEPLOY.md` para o índice GIN. — motivo: a migração 0011 já foi aplicada com sucesso no deploy v1.0.27.
- O usuário consegue conceder escopo `workflow` ao PAT (ou fazer o push manualmente). — motivo: não há como contornar a recusa do GitHub sem mudar credencial.

## Restrições
- P1-3 e P1-4 não podem ir para produção sem a mudança 202: o timeout 45s cortaria a ingestão síncrona de ~90 feeds + LLM, reintroduzindo o bug do PR #23.
- O reload do Nginx na VPS só é válido depois que `proxy_cache_path` e as duas `limit_req_zone` estiverem no `http {}` global — caso contrário `nginx -t` falha e o ambiente fica sem reload.
- Nenhuma dependência nova; nenhuma mudança de contrato de API fora do 202 já preparado no frontend.

## Divisão de trabalho
| Etapa | Agente responsável | Entrada esperada | Saída esperada |
|---|---|---|---|
| 1 | tester | implementation-contract.md | veredito passed/failed/blocked |
| 2 | reviewer (obrigatório: API pública + serving) | diff | code-review-contract.md |
| 3 | orchestrator | veredito + revisão | decisão de release e runbook de VPS |

## Critérios de aceite (nível de negócio/produto)
1. `POST /api/admin/robos/executar/` responde 202 imediatamente e a ingestão conclui registrado em `RegistroExecucaoIngestao`.
2. Nenhuma requisição legítima da API é cortada em 45s pelo Gunicorn com a mudança 202 aplicada.
3. Feed e radar respondem do cache de borda em requisições repetidas, sem exigir credencial.
4. Os três ambientes recebem o mesmo conjunto de mudanças de serving, sem divergência de config.
5. O runbook de VPS necessário para o reload do Nginx está documentado e é executável por humano.

## Riscos identificados
| Risco | Impacto | Mitigação |
|---|---|---|
| Push bloqueado pelo escopo do PAT | alto | resolver credencial com o usuário antes de qualquer tag |
| `nginx -t` falhar na VPS por zonas globais ausentes | alto | runbook explícito em `infra/DEPLOY.md`; não recarregar sem validar |
| Thread daemon morrer em restart do PM2 durante ingestão | médio | aceito e documentado;正解 é migrar para Celery (backlog) |
| `proxy_cache` servindo resposta variando por usuário | médio | chave sem cookie + `proxy_cache_bypass`/`proxy_no_cache` em auth |

## Dependências
- Credencial com escopo `workflow` (bloqueia push e, portanto, a tag).
- Ação humana na VPS para as zonas globais do Nginx antes do reload.
