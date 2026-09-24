# Implementation Contract — 20260923-1230-p1-gunicorn-nginx

## Metadados
- **run_id:** 20260923-1230-p1-gunicorn-nginx
- **Deriva de:** task-plan.md (20260923-1230-p1-gunicorn-nginx)
- **Versão do contrato:** 1

## O que deve ser construído

### Parte A — Gunicorn (P1-3)
1. Criar `backend/gunicorn.conf.py` com config única: `worker_class =
   "gthread"`, `threads` (2–4), `workers` (2 na VPS atual —
   parametrizável via env `GUNICORN_WORKERS` com default),
   `timeout` (30–60s), `bind` via env. Comentários documentando a
   justificativa (API I/O-bound; requisição presa não derruba o
   serviço; `CONN_MAX_AGE=60` já configurado).
2. `backend/Dockerfile` CMD passa a usar o conf file (`gunicorn
   config.wsgi:application --config gunicorn.conf.py` ou equivalente —
   o conf na raiz do backend é lido automaticamente se nomeado
   `gunicorn.conf.py`).
3. `.github/workflows/deploy.yml:186` passa a iniciar o gunicorn com os
   mesmos flags gthread/timeout (ou apenas sem os flags redundantes,
   confiando no conf file — a critério do executor, documentado).
   Atualizar também os comentários do workflow se citarem os flags
   antigos.

### Parte B — Nginx (P1-4)
4. `infra/nginx/portal-{dev,homolog,prod}.conf`: (a) gzip ativo
   (`gzip on` + tipos; brotli como comentário para quando o módulo
   existir); (b) bloco `upstream` por ambiente + `keepalive 32` +
   `proxy_http_version 1.1` + `proxy_set_header Connection ""` nos
   locations `/api/` e `/`; (c) `proxy_cache_path` + `proxy_cache`
   para `/api/feed/` e `/api/radar/tendencias` (TTL 30–60s,
   `proxy_cache_key` sem cookie/Authorization, `proxy_cache_valid`
   200, bypass para requisições autenticadas via `proxy_cache_bypass`
   + `proxy_no_cache` quando header de auth presente); (d)
   `/static/` e `/media/` servidos direto pelo Nginx (alias para os
   paths reais da VPS, a confirmar nos confs existentes/documentação);
   (e) `limit_req` ativo para `POST` público (zona compartilhada,
   taxa alinhada ao throttle do DRF `20/min`); (f)
   `proxy_read_timeout` alinhado ao timeout do Gunicorn.
5. `infra/DEPLOY.md`: seção curta sobre o cache de borda local
   (diretório do proxy_cache_path, como invalidar com reload) e os
   novos flags do gunicorn, se houver mudança de operação.

## Áreas/arquivos esperados
- `backend/gunicorn.conf.py` (novo)
- `backend/Dockerfile`
- `.github/workflows/deploy.yml`
- `infra/nginx/portal-dev.conf`, `infra/nginx/portal-homolog.conf`, `infra/nginx/portal-prod.conf`
- `infra/DEPLOY.md` (só se houver mudança de operação)
- Qualquer mudança fora desta lista deve ser justificada em `implementation-history.md`.

## Interfaces afetadas
- Nenhuma API/contrato/schema muda. Comportamento HTTP observável:
  compressão (Content-Encoding) e headers de cache nas rotas feed/radar
  na topologia Nginx; nada muda na topologia Docker/Caddy (já tem
  `encode zstd gzip`).
- Operação: reload Nginx + restart PM2 na VPS (follow-up humano).

## Critérios de aceite (técnicos, testáveis)
1. `backend/gunicorn.conf.py` define `worker_class gthread`, threads >= 2 e `timeout` <= 60, lendo workers/bind de env com default documentado.
2. `backend/Dockerfile` CMD usa o conf file (sem flags duplicados divergentes).
3. `deploy.yml` inicia gunicorn de forma consistente com o conf (mesmo worker_class/timeout), sem `--workers 2` hardcoded divergente.
4. Os 3 confs nginx têm gzip + upstream/keepalive + proxy_cache feed/radar + static/media direto + limit_req, com `proxy_cache_key` sem cookie.
5. Requisições com header `Authorization`/Cookie não são cacheadas (`proxy_cache_bypass`/`proxy_no_cache` presentes).
6. Sintaxe: `nginx -t` validado se o binário existir neste ambiente; caso contrário, revisão de sintaxe linha a linha registrada no histórico (e follow-up para rodar `nginx -t` na VPS antes do reload).
7. Build da imagem backend continua OK (o CI valida; evidência local via docker build se disponível, senão registro).

## Não-objetivos
- TLS/HTTP2/443 em PROD, Cloudflare, build no CI (run C), React Query (run C), run A (feed/cache/índices), docker-compose.yml, Caddyfile.
- Nova dependência; mudança em settings.py (run A está editando).
- Envio de runbook de deploy na VPS (fica como follow-up do P0-2/P0-3).

## Restrições técnicas
- **Performance:** timeout novo não pode derrubar tarefas longas legítimas — a ingestão síncrona via endpoint não existe (é Celery); 30–60s cobre com folga.
- **Segurança/privacidade:** cache só em rotas públicas; `proxy_cache_key` sem credenciais; limit_req como defesa adicional.
- **Dependências permitidas:** nenhuma nova.
- **Estilo/convenções:** comentários em português no padrão dos confs existentes (o Caddyfile/conf do projeto têm comentários de motivo).
- **Revisão:** `review-triggers.md` consultado — API pública não muda (só headers de infra); sem auth/billing/migração. Diff esperado < 300 linhas. Revisão formal a critério do orchestrator (provável dispensa, mas confs de nginx com proxy_cache merecem atenção do reviewer se houver volume).

## Definição de pronto (Definition of Done)
- [ ] Critérios de aceite implementados
- [ ] Testes escritos e passando (tester — validação de sintaxe/build)
- [ ] Revisão de código aprovada, se exigida (reviewer)
- [ ] Documentação atualizada (documenter)
- [ ] `implementation-history.md` completo e coerente
