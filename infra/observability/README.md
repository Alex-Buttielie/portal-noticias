# Observabilidade do portal

Run `20260925-1020-observabilidade`. Este diretório é a malha de telemetria
**técnica** do portal: o que o time de operação usa para saber se o sistema
está de pé, degradado ou prestes a cair.

## Log técnico é NÃO é analytics

A separação é deliberada e é o critério 6/21 da run:

| | Log técnico (aqui) | Analytics de produto (`/api/metricas/eventos/`) |
|---|---|---|
| Pergunta | "o sistema está saudável?" | "o produto está sendo usado?" |
| Quem consome | operação, alerta, Sentry | time de produto, BI |
| Base | log do servidor, métricas, checks | eventos de produto com consentimento |
| Consentimento | técnicos, com `SENTRY_TECHNICAL_CONSENT_DEFAULT` | **exige consentimento assinado** (HMAC) |
| Retenção | 30 dias no disco, o que o Loki reter | 12 meses, expurgo diário |
| Destination | Grafana Cloud (Loki/Mimir) | banco de dados |

Nunca misture os dois. Um painel de "queda de readership" não é sinal de
incidente; um `5xx/s` não é métrica de negócio. O dashboard de business
intelligence que já existia continua sendo o lugar do segundo, e esta malha é o
lugar do primeiro.

## O mapa do desenho

```
                    ┌──────────────── VPS (uma por ambiente) ────────────────┐
  browser ──HTTPS──► Nginx  ──► Next.js (PM2)          frontend  310x
                        │
                        └──► Gunicorn/Django            api        510x
                                 │  /livez  /readyz  /health-detail  /metrics
                                 ├──► PostgreSQL  (obrigatório)
                                 └──► Redis ──► Celery worker / beat (systemd)

                    Grafana Alloy (uma instância por ambiente, systemd)
                      ├── scrape  127.0.0.1:510x/metrics  (Bearer)
                      ├── tail     /var/log/nginx/portal-<env>.access.log (JSON)
                      ├── tail     ~/.pm2/logs/portal-api-<env>-*.log (JSON)
                      ├── journal  units celery-*/nginx (allowlist)
                      └──► Grafana Cloud: Loki (logs) + Mimir (métricas)
                                ▲                    ▲
                    Grafana: painéis + regras    Loki: pesquisa por request_id
                                │
  Better Stack (EXTERNO à VPS) ─┴── checks HTTP/TLS + cron monitor de backup
  Sentry (erros, com consentimento técnico)
  Cloudflare R2 (cópia do backup) + lifecycle de 90 dias
```

## Peças, e o que cada uma resolve

| Caminho | O que é |
|---|---|
| `alloy/config.alloy` | coletor: scrape de `/metrics`, tail dos logs, journal, remote-write para Loki e Mimir |
| `alloy/alloy.env.example` | env por ambiente (endpoints, tokens, globs) — **placeholders, nenhum segredo** |
| `alloy/verificar-env.sh` | gate fail-closed do coletor (roda no `ExecStartPre` e na validação de infra) |
| `grafana/dashboards/*.json` | 4 painéis técnicos importáveis no Grafana |
| `alerts/regras-*.yaml` | 16 regras Prometheus/Mimir com severidade, runbook e dedup |
| `alerts/README.md` | Contact Points, política de notificação e o que **não** é alerta de métrica |
| `better-stack/checks.json` | checks externos (readiness, liveness, home, feed, TLS) + cron monitor de backup |
| `r2/lifecycle.json` | política de retenção do bucket de backup (90 dias, piso de 30, MPU órfão) |

## Como instalar, em ordem

A ordem não é estética: cada passo depende do anterior, e pular um deixa o
sistema meio-configurado (que é pior que não configurado, porque parece
configurado).

1. **`http-cache.conf` ANTES dos site confs.** A partir desta run os sites
   referenciam `$portal_request_id`, `$observability_acesso` e o `log_format`
   `portal_acesso`, todos definidos naquele arquivo. Sem ele, `nginx -t` falha
   com "unknown variable" e o deploy-hook de certificado **não recarrega** —
   falha ruidosa, na configuração certa.
2. **Marcadores dos arquivos de nginx.** `__DOMAIN_FRONTEND__` (e
   `__DOMAIN_FRONTEND_WWW__` em prod) nos site confs;
   `__OBS_TOKEN_ESPERADO__` no `http-cache.conf`, com o MESMO valor de
   `OBSERVABILITY_METRICS_TOKEN` no ambiente da aplicação. Enquanto o marcador
   estiver lá, nenhum `Authorization: Bearer` autoriza nada — a instalação sem
   substituição fecha o acesso em vez de abri-lo com uma credencial de exemplo.
3. **Criar a conta do Grafana Cloud (US), Loki e Mimir**, gerar as API keys e
   o endereço de push. Humanos, MFA, nada por chat.
4. **Uma instância do Alloy por ambiente**, com `/etc/portal/alloy-<env>.env`
   em modo 0640, o arquivo de token em modo 0600 e o usuário do Alloy nos
   grupos `adm` e `systemd-journal`. Rode `verificar-env.sh` antes: ele falha
   se algo estiver faltando, e é exatamente para isso.
5. **Importar os painéis** (Dashboard → New → Import, apontando para o arquivo
   JSON) e carregar as regras de alerta no Mimir.
6. **Cadastrar os checks no Better Stack** e o cron monitor de backup;
   colocar a URL de heartbeat em `BACKUP_HEARTBEAT_URL`.
7. **Instalar as units systemd** do Celery (`infra/systemd/`) e o
   watchdog de backup no cron. Detalhes e ajustes obrigatórios no cabeçalho de
   cada unit.
8. **Rodar a validação** (`scripts/observability/validar-infra.sh`) na VPS
   depois de instalar: ela é a mesma que roda no CI.

## Como consultar no dia a dia

O que o time vai mais fazer, em ordem de frequência:

```logql
# 1. "O usuário colou este código de suporte": ache a requisição inteira.
{servico="portal-api"} | json | request_id="9f2c1b7e-1111-4222-8333-abcdefabcdef"

# 2. Erros do Django no último minuto, por mensagem.
{servico="portal-api", tipo="aplicacao"} | json | nivel="ERROR"

# 3. Respostas 5xx na borda, com a rota e o tempo.
{servico="portal-edge", tipo="acesso"} | json | status >= "500" | line_format "{{.uri}} {{.status}} {{.tempo}}s"

# 4. Uma release específica teve regressão? (o release é label no log e no Mimir)
{servico="portal-api", release="$release"} | json | nivel="ERROR"

# 5. O que o Nginx respondeu quando o app degradou?
{servico="portal-edge"} | json | estado="degraded"
```

E no Mimir, para o que o Grafana não mostra pronto:

```promql
# Rota mais lenta agora (o rótulo de rota é de baixa cardinalidade por contrato).
topk(5, sum by (route) (rate(portal_http_request_duration_seconds_sum[5m]))
  / sum by (route) (rate(portal_http_request_duration_seconds_count[5m])))

# Falhas de check por dependência, novas no intervalo.
sum by (dependency) (increase(portal_dependency_checks_total{result="error"}[15m]))
```

## Limitações conhecidas (escritas aqui de propósito)

Cada uma destas é um ponto cego real. Nenhuma delas está escondida num painel
que promete mais do que entrega.

1. **`/metrics` é por processo.** O Django expõe o registro do processo que
   atendeu o scrape, e a API roda com mais de um worker Gunicorn. Contadores
   subestimam o total e zeram a cada restart. Os painéis usam `rate()` para
   tendência, nunca para contagem, e o dashboard de disponibilidade tem um
   painel de texto explicando isso.
2. **Gauge sobrevive a restart; contador não.** `portal_ready`,
   `portal_celery_queue_depth` e `portal_collector_disk_free_ratio` são estado
   instantâneo e são confiáveis. Contadores servem para taxa.
3. **O heartbeat do beat prova o processo, não o agendamento.** Um beat travado
   com processo vivo continua produzindo heartbeat. O sinal que fecha o
   diagnóstico é `PortalCelerySemExecucao` (nenhuma task em 45 min).
4. **Não existe métrica de ingestão.** `portal_ingestion_executions_total` é
   DECLARADA em `backend/config/metrics.py` e nunca incrementada; por isso
   nenhum painel a usa. O proxy honesto é a task de ingestão em
   `portal_celery_tasks_total`. Fechar isso é pendência do bloco de backend.
5. **Atraso de backup e expiração de TLS não são métrica.** Nenhum dos dois
   sobrevive à queda da VPS, então nenhum dos dois pode ser painel de Grafana:
   são o cron monitor e o check externo do Better Stack. Ver
   `alerts/README.md`.
6. **O `loki.source.journal` só coleta com `adm` + `systemd-journal`.** Sem os
   dois grupos o componente "inicia sem erro e não coleta nada" — por isso o
   gate de ambiente do coletor verifica os grupos.
7. **Uma instância do coletor por ambiente.** Um coletor único misturaria dev,
   homolog e prod, e uma falha em dev poderia "explicar" um painel de prod. O
   preço é três unidades para manter.

## O que depende de provisionamento externo (bloqueado nesta run)

Nada abaixo pode ser feito por código, e nada aqui contém valor secreto:

- contas com MFA: **Grafana Cloud (US)**, **Better Stack**, **Cloudflare R2**,
  **Sentry**;
- Contact Points do Grafana (`<CP_CRITICO_PRINCIPAL>`, `<CP_CRITICO_SUPLENTE>`,
  `<CP_WARNING>`) e a política de notificação;
- canais: e-mail do responsável principal e do suplente, Telegram/Slack, e a
  lista de contatos;
- **domínios reais** de dev, homolog e prod, e a decisão do domínio canônico —
  hoje há divergência entre os workflows, e nenhum endereço real foi inventado
  aqui (os placeholders usam `<DOMINIO_DE_PRODUCAO>` e o TLD reservado
  `.invalid`, que nunca resolve);
- o **endereço interno de runbook** que substitui o placeholder
  `https://runbooks.portal.exemplo.invalid/`;
- a **decisão humana sobre a retenção remota** (90 dias propostos aqui) e a
  janela de produção para testar o restore mensal.

## O que foi adiado para o Bloco C2 (e por quê)

O plano do Bloco C (`../bloco-c-plano.md`, seção 3) adia para C2 tudo que
depende de `.github/workflows/`, porque a run de go-live tem diff aberto em
`.github/` e misturar os dois lotes contamina o histórico:

- release atômica com `releases/` + symlink (executa o plano já escrito em
  `CI-CD.md` §P1-5, sem reescrever);
- o PM2 do frontend passando a executar o standalone (`infra/standalone/`);
- instalação das units systemd durante o deploy;
- gate de validação de infra na CI (executando `scripts/observability/validar-infra.sh`);
- SSH por chave dedicada e segredos de alerta/Grafana no repositório;
- as seções de documentação de C em `CI-CD.md`, `infra/DEPLOY.md` e
  `PROD_DECISOES.md`.
