# Task Plan — 20260923-1230-p1-gunicorn-nginx (atualizado pós-reconciliação)

## Metadados
- **run_id:** 20260923-1230-p1-gunicorn-nginx
- **Data de abertura:** 2026-09-23 (revisão reconciliada em 2026-09-23 14h)
- **Solicitado por:** Alex (humano)
- **Spec de origem:** `ANALISE_CUSTO_PERFORMANCE.md` §7 — P1-3 e P1-4

## Objetivo
Servir o tráfego sem que uma requisição lenta derrube a API (gthread + timeout curto) e reduzir CPU por pageview (compressão, cache de borda local, estático/mídia fora do Gunicorn), sem introduzir vazamento de dados privados nem config que derrube o reload do Nginx.

## Escopo
### Dentro do escopo
- P1-3: `backend/gunicorn.conf.py` (gthread, 2w×4t, timeout 45) + `backend/Dockerfile` + `.github/workflows/deploy.yml` coerentes.
- P1-4: `infra/nginx/portal-{dev,homolog,prod}.conf` com gzip, upstream+keepalive, cache de feed/radar, `/static/` e `/media/` servidos localmente, `limit_req` na escrita pública.

### Fora do escopo
- TLS/443 (P0-3, runbook à parte), Cloudflare, build no CI (P1-5), React Query (P1-6), ETag dos RSS, busca FTS, P2.

## Suposições assumidas
- `proxy_cache_path` e `limit_req_zone` serão declarados no `http{}` global da VPS (passo manual humano), com os blocos comentados nos server confs — o reload falha sem isso, então a validação de produção depende do runbook de ativação.
- O endpoint de ingestão manual em background (mudança não commitada em `robos_views.py`, 202) é pré-requisito do timeout curto: enquanto não for commitado junto, o timeout 45s estoura.

## Restrições
- `/media/` servido pelo Nginx precisa preservar a restrição de acesso do `DocumentoView` (credenciamento) — serving direto só é aceitável para mídia pública.
- Nenhuma mudança em `backend/config/settings.py`, `backend/feed`, `backend/gating`, `backend/catalogo_noticias` (fora do arquivo já alterado para 202).
- `nginx -t` precisa passar na VPS antes do reload.

## Divisão de trabalho
| Etapa | Agente | Entrada | Saída |
|---|---|---|---|
| 1 | executor | implementation-contract.md | config + implementation-history.md |
| 2 | tester | implementation-contract.md | veredito |
| 3 | reviewer (reconciliado) | commit 93b919d | code-review-contract.md |
| 4 | remediator | code-review-contract.md | correções dos 7 findings |
| 5 | reviewer (re-revisão) | diff da remediação | veredito final |
| 6 | documenter/historian | tudo acima | documentation-update.md + report.md + HISTORY |

## Critérios de aceite
1. Nenhuma requisição presa ocupa um worker de forma que derrube a API.
2. Requisições repetidas de feed/radar dentro do TTL não atingem o Gunicorn.
3. Estático e mídia **pública** não passam pelo Gunicorn; **documentos privados continuam atrás de autenticação**.
4. Escrita pública tem rate limit no edge.
5. `nginx -t` passa na VPS e o reload preserva as 3 Portrait (dev/homolog/prod) funcionando.

## Riscos identificados
| Risco | Impacto | Mitigação |
|---|---|---|
| `/media/` público vaza documentos de credenciamento | blocker | reproduzir a verificação do reviewer; servir via Django apenas o que é privado |
| zones ausentes quebram o reload | blocker | runbook de ativação + validação `nginx -t` na VPS antes do reload |
| timeout curto sem endpoint async | major | commit do 202 junto ou timeout provisório maior até o merge |
| regex de cache capturando POST de interação | major | ancorar o regex a `/api/feed/` + método GET/HEAD |

## Dependências
- Commit do endpoint 202 (`robos_views.py` + frontend) antes de ativar o timeout 45 em produção.
- Passo manual na VPS para `http{}` global (zonas) + `nginx -t` + reload + restart PM2.
