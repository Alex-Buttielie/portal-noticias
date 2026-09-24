# Documentation Update — 20260923-1230-p1-gunicorn-nginx

## Escopo

Documentação e registro histórico da run `20260923-1230-p1-gunicorn-nginx`.
Nenhum arquivo de código-fonte foi alterado pelo documenter/historian.

## Verificações

- `backend/gunicorn.conf.py:47-65` — confirmado o default operacional
  `worker_class = "gthread"`, 2 workers × 4 threads, `timeout = 60`, keepalive
  e parametrização por `GUNICORN_*`.
- `.github/workflows/deploy.yml:182-196` — confirmado que o PM2 recebe
  `--config "$APP_DIR/backend/gunicorn.conf.py"`, `GUNICORN_TIMEOUT=60` e
  apenas o bind/porta como override; o Dockerfile também usa a mesma
  configuração sem duplicar flags de worker/timeout.
- `infra/nginx/http-cache.conf:1-35` e
  `infra/nginx/portal-location-{cache,auth,write}.conf:1-20` — confirmados os
  includes em seus contextos, as zones, o cache público GET/HEAD, o bypass de
  credenciais e os limites de escrita/auth.
- `infra/nginx/portal-{dev,homolog,prod}.conf:78-109` — confirmado que o edge
  expõe apenas `/media/public/` e mantém `media/credenciamento` fora do alias,
  com acesso pelo `DocumentoView` autenticado.
- `Caddyfile:41-44` — confirmado que a variante Docker/Caddy ainda entrega
  `/media/*` inteiro sem autenticação. O arquivo não foi modificado; o risco
  foi explicitado no runbook para impedir uso da topologia com credenciamento
  antes da separação de storage.

## Alterações de documentação (arquivo:linha, antes → depois)

| Arquivo:linha | Antes | Depois |
|---|---|---|
| `infra/DEPLOY.md:147-164` | O runbook explicava include global, snippets, site, `nginx -t` e reload em blocos dispersos, sem lista única que incluísse o restart do PM2. | Acrescentado checklist explícito: include `http-cache.conf` uma vez no `http {}` → snippets/site → `nginx -t` → reload → restart da API PM2; esclarecer que os snippets são opcionais para validade do parser, mas necessários para ativar cache/rate. |
| `infra/DEPLOY.md:166-218` | Os comandos existiam, mas a ordem segura dependia de texto e repetição. | Mantidos e explicitados o contexto `http {}`, a ordem dos includes, a proibição de instalar snippets antes do global e o bloqueio do reload se `nginx -t` falhar. |
| `infra/DEPLOY.md:226-242` | Não havia seção de restart/verificação do PM2. | Acrescentados `pm2 restart portal-api-*`, `pm2 save`, health check por porta eorientação para o caso de deploy pelo workflow. |
| `infra/DEPLOY.md:244-267` | A seção explicava a proteção Nginx, mas não alertava que o Caddyfile ainda expõe toda a mídia. | Acrescentado aviso de segurança explícito: `Caddyfile:41-44` pode expor documentos de credenciamento; é proibido usar Caddy com credenciamento antes de servir somente `/media/public/*` e manter o caminho privado somente na `DocumentoView`. |
| `infra/DEPLOY.md:269-280` | O runbook já registrava o default 60 s e a pré-condição do 45 s. | Mantido e ligado ao checklist operacional; nenhuma redução automática de timeout foi documentada. |
| `CI-CD.md:32-41` | A sequência P1-4 terminava em reload do Nginx. | Incluído o restart da API correspondente no PM2 após reload, além da referência ao runbook e à proteção fail-closed de `media/credenciamento`. |
| `README.md:16-35` | Não havia seção de deploy/infra; o README não resumia Gunicorn nem a política de mídia. | Criada a seção “Deploy e infraestrutura” com `gthread`, 2 workers × 4 threads, timeout 60, sequência de ativação, separação `/media/public/` versus `/media/credenciamento/` e link para o aviso do Caddy. |

## Resultado

O operador da VPS tem agora uma sequência única e verificável para instalar
o include no contexto global correto, ativar os snippets/sites, validar o
Nginx, recarregar e reiniciar o PM2. O risco residual da topologia Caddy
alternativa está destacado e não deve ser tratado como coberto pela correção
aplicada aos sites Nginx.
