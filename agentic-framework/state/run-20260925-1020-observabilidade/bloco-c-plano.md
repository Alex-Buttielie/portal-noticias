<!--
DOCUMENTO DE PLANEJAMENTO (orchestrator)
Base: levantamento somente-leitura do Bloco C (2026-09-25).
Nenhum código de produção foi alterado para produzir este documento.
-->

# Plano do Bloco C — infra, deploy, backup e observabilidade

Run: `20260925-1020-observabilidade`. Contrato: `implementation-contract.md` (critérios 18-19, 21-23, 29-36, 40-41).

## 0. Restrição de ownership que decide o desenho deste bloco

A run `20260925-1433-go-live-producao` (lote P0-1) **já executou** e deixou trabalho **não commitado no mesmo working tree**:

| Caminho | Estado observado |
|---|---|
| `scripts/release/verificar-proveniencia.sh` | criado |
| `agentic-framework/state/run-20260925-1433-go-live-producao/lote-p0-1-evidencias.md` | criado |
| `agentic-framework/state/run-20260925-1433-go-live-producao/implementation-history.md` | criado |
| `CI-CD.md` | modificado |
| `PROD_DECISOES.md` | modificado |
| `infra/DEPLOY.md` | modificado |

Consequências (não negociáveis para o Bloco C):

1. **`.github/workflows/*` está BLOQUEADO neste bloco.** O lote P0-1 declarou `.github/` integralmente proibido, e o `run-state.json` desta run registra que nada em `.github/` pode ser tocado sem acordo entre as duas runs. Como o P0-1 está com diff aberto, tocar `.github/` agora mistura os dois lotes.
2. **`CI-CD.md`, `PROD_DECISOES.md` e `infra/DEPLOY.md` estão BLOQUEADOS neste bloco** (modificados pelo P0-1, não commitados). Reescrever ou "melhorar" seção existente desses arquivos violaria o contrato do P0-1 (`lote-p0-1-proveniencia.md:119`).
3. Os itens de C que dependem desses arquivos ficam registrados em **C2** (adiado), a executar só com as runs reconciliadas.
4. Nenhum arquivo do P0-1 pode ser adicionado a commit desta run, nem revertido.

## 1. Achados que mudam o diagnóstico

O bloco de backend já entregou `config/observability_views.py` (`/livez`, `/readyz`, `/health-detail`, `/metrics`) e `metricas/tasks.py::expurar_analytics`, o que muda três pendências que eram do backend e agora são de borda/infra.

| # | Achado | Evidência | Impacto |
|---|---|---|---|
| B1 | Nginx não expõe `/livez` nem `/readyz`; só existe `location = /healthz` | `infra/nginx/portal-{dev,homolog,prod}.conf:54,159` | check externo do Better Stack não tem rota HTTPS; `/livez` e `/readyz` caem em `location /` (Next) e viram 404 |
| B2 | Nginx **sobrescreve** o `X-Request-ID` do cliente com o `$request_id` nativo | `portal-prod.conf:65,166,182,196,213,254,274,284` (`proxy_set_header X-Request-ID $request_id;`) | quebra o critério 1 (correlação browser → nginx → Django) no primeiro salto |
| B3 | Zero coletor: não existe `infra/observability/`, `infra/systemd/`, Terraform, dashboards, regras de alerta | varredura no repo: 0 arquivos `*.tf`; `infra/` tem só nginx, backup, certbot, logrotate | critérios 21, 22, 40 |
| B4 | **Celery worker e beat não existem na topologia ativa** (nem PM2, nem systemd) | `.github/workflows/deploy.yml:428-447` (só `portal-web-*` e `portal-api-*`) | critérios 13-16; `OBSERVABILITY_BEAT_HEARTBEAT_FILE` do settings fica sem produtor |
| B5 | Frontend no PM2 roda `npm start` (Next normal), não o standalone; sem `HOSTNAME`, sem `static/`/`public` copiados | `deploy.yml:428-429`; o padrão correto já existe em `frontend/Dockerfile:34-42,47` | critério 29 |
| B6 | Deploy é in-place no mesmo diretório, sem `releases/`, sem symlink, sem promoção por smoke | `deploy.yml:259` (`git reset --hard`), `:398-399` (`pm2 delete`+`start`) | critério 30 |
| B7 | Backup **não é fail-closed**: sem `BACKUP_S3_BUCKET` o script termina **exit 0** com 2 avisos | `infra/backup/pg_backup_pm2.sh:444-448` | critério 34: backup "verde" sem cópia externa |
| B8 | **Não existe alerta de atraso de backup** nem restore mensal; `RESTORE.md` só cobre a topologia Docker, não a ativa (PM2) | `infra/backup/`, `infra/RESTORE.md`, `infra/DEPLOY.md:651-667` | critérios 34 e 35 |
| B11 | Healthcheck de `celery-worker` e `celery-beat` **sempre verde**: `... \| grep -q pong \|\| exit 0` | `docker-compose.yml:88-93,120-125` | worker morto continua "healthy" (critérios 14, 16) |
| B12 | SSH por senha, sem chave dedicada e sem `known_hosts` pinado | `deploy.yml:130-135` (secret `VPS_PASSWORD`) | critério 32 |
| B13 | Sem alerta de expiração de TLS; HSTS comentado | `portal-*.conf:96`; `tls_enabled: false` nos 3 callers | critério 33 |
| B14 | Ownership conflitante com a run de go-live | seção 0 acima |.define a divisão C1/C2 |

Achados favoráveis (não reimplementar, apenas referenciar):

- A validação do dump já é forte: `pg_restore --list` + restore em banco descartável + comparação de contagens (`pg_backup_pm2.sh:265-371`).
- `proxy_set_header` de Host/X-Real-IP/X-Forwarded-Proto/Connection e keepalive já estão corretos; gzip e `limit_req` existem.
- Fail-closed de secret no bootstrap já existe via placeholder `troque-aqui` (`deploy.yml:267-301`).
- Rollback manual e smoke pós-deploy já existem (`deploy.yml:497-578`, `rollback.yml`).
- `CI-CD.md:260-323` (§P1-5) **já contém o plano de release atômica** e o gatilho para evoluir a blue-green (`:229-235`): o Bloco C deve executar esse plano, não reescrevê-lo.
- `infra/DEPLOY.md:330-607` (§3A) **já é o runbook TLS**: não duplicar.

## 2. C1 — executável agora (sem `.github/` e sem os três docs)

| ID | Entrega | Arquivos |
|---|---|---|
| C1.1 | Expor `/livez` e `/readyz` no Nginx, com as mesmas regras de allow/deny do `/healthz`; garantir que `/health-detail` e `/metrics` **não** ficam acessíveis por origem (loopback ou `Authorization: Bearer` com token) | `infra/nginx/portal-{dev,homolog,prod}.conf` |
| C1.2 | Aceitar o `X-Request-ID` do cliente quando válido e propagar `X-Release`/`X-Environment`/`X-Operational-State` também em resposta servida do cache | `infra/nginx/portal-*.conf`, `infra/nginx/http-cache.conf` |
| C1.3 | `log_format` de acesso com `$request_id` e `$upstream_http_x_release`, mais logrotate do log de borda | `infra/nginx/http-cache.conf`, `infra/logrotate/` |
| C1.4 | Units systemd do Celery worker e beat, com `After=`/`Requires=` corretos, `Restart=on-failure`, limites de memória/CPU, hardening (`NoNewPrivileges`, `ProtectSystem`) e `EnvironmentFile` com secrets | `infra/systemd/celery-worker.service`, `infra/systemd/celery-beat.service` (diretório novo) |
| C1.5 | Script de execução do Next standalone fora do PM2 (o padrão de `frontend/Dockerfile`), com `HOSTNAME`, `PORT`, cópia de `static/` e `public/`, e smoke antes de promover | `infra/standalone/` ou `scripts/` (novo) |
| C1.6 | Coletor Grafana Alloy: tails do log de borda e dos logs JSON do backend/PM2, scrape de `/metrics` do backend, remote-write para Grafana Cloud (Loki + Mimir), com tudo parametrizado por env e **fail-closed** se o endpoint não estiver definido | `infra/observability/alloy/config.alloy` (novo) |
| C1.7 | Dashboards técnicos versionados em JSON (visibilidade, saúde, filas/Celery, ingestão, dependências) | `infra/observability/grafana/dashboards/*.json` (novo) |
| C1.8 | Regras de alerta com severidade, dedup, `runbook_url` e contato: burn-rate de disponibilidade e latência, fila/ingestão, saúde do beat, atraso de backup, expiração de TLS | `infra/observability/alerts/` (novo) |
| C1.9 | Definição dos checks externos Better Stack em JSON | `infra/observability/better-stack/checks.json` (novo) |
| C1.10 | Política de lifecycle do bucket de backup em JSON, com o bucket privado declarado | `infra/observability/r2/lifecycle.json` (novo) |
| C1.11 | Backup fail-closed: sem destino configurado o script **falha** com código próprio e mensagem clara, em vez de exit 0 silencioso; manter a retenção local suspensa quando não há upload confirmado | `infra/backup/pg_backup_pm2.sh` |
| C1.12 | Watchdog de atraso de backup (>`BACKUP_MAX_AGE_HOURS`, padrão 26 h) com saída alertável, sem depender da VPS estar de pé para o alerta existir | `infra/backup/verificar_backup.sh` (novo) + `infra/backup/RESTORE.md` (runbook da topologia PM2) |
| C1.13 | Corrigir os healthchecks sempre verdes de worker e beat no compose | `docker-compose.yml` |
| C1.14 | Documentar as variáveis novas nos exemplos de ambiente, com placeholders e sem segredo; resolver a divergência de `DJANGO_LOG_JSON` (default `True` no settings vs `false` documentado) | `.env.production.example`, `backend/.env.example`, `.env.localhost.example`, `frontend/.env.local.example` |
| C1.15 | Script de validação de configuração executável fora da CI (`nginx -t` em modo check, `docker compose config`, `systemd-analyze verify`, parse dos JSON de dashboard/alerta, Terraform `validate` se houver) | `scripts/` (novo) |
| C1.16 | `README` do diretório de observabilidade explicando o desenho, o que é log técnico vs analytics, e o que ainda depende de provisionamento externo | `infra/observability/README.md` (novo) |

## 3. C2 — adiado até reconciliar com a run de go-live

| ID | Entrega | Depende de |
|---|---|---|
| C2.1 | Release atômica com `releases/`, symlink `current`, promoção só após smoke e rollback para a release anterior (executando o plano já escrito em `CI-CD.md:260-323`) | `.github/workflows/deploy.yml` |
| C2.2 | PM2 do frontend passando a executar o standalone (C1.5) | `.github/workflows/deploy.yml` |
| C2.3 | Instalação/ativação das units systemd no deploy | `.github/workflows/deploy.yml` |
| C2.4 | Source maps do frontend enviados ao Sentry no build, com `SENTRY_AUTH_TOKEN` como secret | `.github/workflows/ci.yml` |
| C2.5 | Gate de validação de infra na CI, executando o script de C1.15 | `.github/workflows/ci.yml` |
| C2.6 | Migração de SSH de senha para chave dedicada, com `known_hosts` pinado e senha removida só após teste | `.github/workflows/*.yml` + secrets do repositório |
| C2.7 | Segredos de alertamento e Grafana/Alloy no repositório | secrets + `.github/workflows/` |
| C2.8 | Seções de documentação de C em `CI-CD.md`, `infra/DEPLOY.md`, `PROD_DECISOES.md` e `README.md`/`ARCHITECTURE.md` | os três docs estão com diff aberto do P0-1 |

## 4. Dependências externas que permanecem bloqueadas

Nenhuma delas é resolvida por código; cada uma precisa de ação humana e canal seguro (nada de segredo pelo chat):

- contas e MFA: Sentry, Grafana Cloud (região US), Better Stack, Cloudflare R2;
- canais de alerta: Slack, Telegram, e-mail, e os contatos do responsável principal e do suplente;
- URLs reais de dev, homolog e produção, e a decisão do domínio canônico (`.com` × `.com.br`, hoje divergente nos workflows);
- janela de produção e validação dos textos legais de privacidade/consentimento.
