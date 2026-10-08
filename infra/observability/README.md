# Observabilidade do portal

Item **P2-01** (Onda 2, consolidação da observabilidade), sobre `develop` =
`1dec732`. Este diretório é a malha de telemetria **técnica** do portal: o que
o time de operação usa para saber se o sistema está de pé, degradado ou
prestes a cair.

## A regra que este diretório inteiro segue

**Um painel que mostra "No data" sem dizer porquê é o mesmo falso verde de um
painel que mostra 0.** Por isso cada painel, cada regra e cada check deste
diretório responde a uma de três perguntas, e nunca a uma quarta:

| Estado | Como aparece | O que significa |
|---|---|---|
| medido | número | o dado existe e está sendo observado |
| **não medido** | painel vermelho `NÃO MEDIDO`, ou alerta `absent()` disparado | o backend **não expõe** este dado; o item de backend que fecha a lacuna está nomeado no painel |
| **não configurado** | exit 3 / `desconhecido` / aviso do gate | não dá para afirmar nada — e isso **não** é "tudo bem" |

O quarto estado proibido é o "verde por ausência": a expressão
`min by (ambiente) (portal_ready) == 0` sobre uma métrica que não existe
devolve vetor vazio, a comparação não casa, e a regra **nunca dispara**. É
silêncio com cara de cobertura. Ver §5.

## Log técnico NÃO é analytics

A separação é deliberada:

| | Log técnico (aqui) | Analytics de produto (`/api/metricas/eventos/`) |
|---|---|---|
| Pergunta | "o sistema está saudável?" | "o produto está sendo usado?" |
| Quem consome | operação, alerta, Sentry | time de produto, BI |
| Base | log do servidor, métricas, checks | eventos de produto com consentimento |
| Retenção | o que o Loki reter | 12 meses, expurgo diário |
| Destination | Grafana Cloud (Loki/Mimir) | banco de dados |

Nunca misture os dois. Um painel de "queda de readership" não é sinal de
incidente; um `5xx/s` não é métrica de negócio.

## O mapa do desenho

```
                    ┌──────────── VPS (uma por ambiente) ────────────┐
  browser ──HTTPS──► Nginx
                        ├──► Next.js (PM2)                    frontend  310x
                        └──► Gunicorn/Django                   api        510x
                                 │  /healthz  /livez  /readyz
                                 │  /health-detail  /metrics   (os 2 últimos
                                 │                          são autenticados)
                                 ├──► PostgreSQL  (obrigatório)
                                 └──► Redis ──► Celery worker / beat

                    Grafana Alloy (uma instância por ambiente)
                      ├── scrape  127.0.0.1:510x/metrics  (Bearer)
                      ├── scrape  a própria telemetria (job="alloy")
                      ├── tail     <log de acesso da borda>   [depende de
                      │                                      item de nginx]
                      ├── tail     ~/.pm2/logs/portal-api-<env>-*.log
                      ├── tail     <saude_filas.jsonl>        [ver §6]
                      ├── journal  units celery-*/nginx (allowlist)
                      └──► Grafana Cloud: Loki (logs) + Mimir (métricas)
                                ▲                    ▲
                    Grafana: painéis + regras    Loki: pesquisa por request_id
                                │
  Better Stack (EXTERNO à VPS) ─┴── checks HTTP/TLS + cron monitors
  Cloudflare R2 (cópia do backup) + lifecycle de 90 dias
```

## Peças, e o que cada uma resolve

| Caminho | O que é |
|---|---|
| `alloy/config.alloy` | coletor: scrape de `/metrics`, tail dos logs, journal, remote-write para Loki e Mimir |
| `alloy/alloy.env.example` | env por ambiente — **placeholders, nenhum segredo** |
| `alloy/verificar-env.sh` | gate fail-closed do coletor (roda no `ExecStartPre` da unit) |
| `grafana/dashboards/*.json` | 4 painéis técnicos importáveis no Grafana |
| `grafana/dashboards/gerar_dashboards.py` | gerador dos painéis: toda `expr` passa por `promtool` |
| `alerts/regras-*.yaml` | 14 regras Prometheus/Mimir com severidade, runbook e dedup |
| `alerts/README.md` | **tabela de correspondência nome a nome**, Contact Points e o que **não** é alerta de métrica |
| `better-stack/checks.json` | checks externos + 2 cron monitors (backup e filas) |
| `r2/lifecycle.json` | política de retenção do bucket de backup (90 dias, piso de 30, MPU órfão) |
| `verificar-correspondencia.py` | verificador: sintaxe PromQL + métrica pedida × exposta |
| `proving/testar-verificar-env.sh` | prova de que o gate do coletor **reprova** quando deve |

## Como validar este diretório (o que roda hoje, sem credencial)

```bash
# 1) Correspondência: toda expr compila e toda métrica pedida existe em develop
python3 infra/observability/verificar-correspondencia.py
#    esperado: "promtool exit: 0 -> TODAS COMPILAM" e
#              "Nenhuma referência quebrada"

# 2) O gate do coletor é capaz de reprovar?
bash infra/observability/proving/testar-verificar-env.sh
#    esperado: 12 de 12 condições quebradas detectadas

# 3) O watchdog de backup é capaz de reprovar?
bash infra/backup/testar-verificar-backup.sh
#    esperado: 14 de 14 cenários com o veredito esperado

# 4) O config do coletor é aceito pelo binário de verdade?
docker run --rm -v "$PWD/infra/observability/alloy:/cfg:ro" \
  grafana/alloy:latest validate /cfg/config.alloy
#    esperado: sem saída, exit 0

# 5) As regras de alerta são aceitas pelo promtool?
docker run --rm --entrypoint promtool -v "$PWD/infra/observability/alerts:/r:ro" \
  prom/prometheus:latest check rules --lint=all /r/regras-disponibilidade.yaml /r/regras-operacao.yaml
#    esperado: "SUCCESS: 6 rules found" e "SUCCESS: 8 rules found"
```

O que **não** é validável aqui, e é template de provisionamento: os Alloys de
dev/homolog/prod, o Grafana Cloud, o Better Stack, o bucket R2 e o Sentry
precisam de credencial e de agente que não existem neste ambiente. Ver §7.

## Como instalar, em ordem

A ordem não é estética: cada passo depende do anterior, e pular um deixa o
sistema meio-configurado — que é pior que não configurado, porque parece
configurado.

1. **Marcadores dos arquivos de nginx.** `__DOMAIN_FRONTEND__` nos site
   confs. Sem substituição, não copie os arquivos.
2. **Conta do Grafana Cloud (Loki e Mimir)**, gerar as API keys e o endereço
   de push. Humanos, MFA, nada por chat.
3. **Uma instância do Alloy por ambiente**, com `/etc/portal/alloy-<env>.env`
   em modo 0640, o arquivo de token em modo 0600 e o usuário do Alloy nos
   grupos `adm` e `systemd-journal`. Rode `verificar-env.sh` **antes** de
   instalar: ele falha se algo estiver faltando, e é exatamente para isso.
4. **O cron de `saude_filas`** que produz `ALLOY_FILAS_JSON_PATH` (§6), e o
   `PORTAL_FILAS_ESTADO_DIR` de `infra/filas/PROVISIONAMENTO.md` §2.2.
5. **Trocar o `runbook_url` `.invalid`** das duas regras pelo endereço interno.
   `verificar-env.sh` reprova enquanto o placeholder estiver lá.
6. **Importar os painéis** (Dashboard → New → Import) e carregar as regras no
   Mimir.
7. **Cadastrar os checks e os cron monitors no Better Stack.**
8. **O watchdog de backup** no cron horário, e o pinger de heartbeat que ele
   ainda não tem (ver §7).

## Como consultar no dia a dia

```logql
# 1. "O usuário colou este código de suporte": ache a requisição inteira.
{servico="portal-api"} | json | request_id="9f2c1b7e-1111-4222-8333-abcdefabcdef"

# 2. Erros do Django no último minuto, por nível.
{servico="portal-api", tipo="aplicacao"} | json | nivel="ERROR"

# 3. Respostas 5xx na borda, com a rota e o tempo. DEPENDE do log_format JSON
#    da borda, que develop ainda não tem (§4).
{servico="portal-edge", tipo="acesso"} | json | status >= "500"

# 4. Estado das filas, pelo relatório oficial (ver §6).
{servico="portal-filas"} | json | estado="degradado"
```

E no Mimir, para o que o Grafana não mostra pronto:

```promql
# Requisições de e-mail por desfecho, nos últimos 15 min.
sum by (destino, situacao) (increase(portal_email_entrega_total[15m]))

# Existe acesso negado ao endpoint privado?
sum by (recurso) (rate(portal_acesso_negado_total[15m]))

# Uptime do processo (único gauge que sobrevive a restart).
max(portal_tempo_de_atividade_segundos)

# Orçamento de cardinalidade: quantas séries portal_* existem?
sum(count by (ambiente, __name__) ({__name__=~"portal_.*"}))
```

## 4. O que `develop` NÃO mede — e quem fecha cada lacuna

Isto é o achado central do item, não uma nota de rodapé. Das **47**
referências de métrica e contrato nos seis documentos de observabilidade do
rascunho, **7 existiam** em `develop` (todas do coletor, nenhuma do backend) e
**40 não**. A tabela completa, com `arquivo:linha` dos dois lados, está em
`alerts/README.md` §1.

O resumo do que falta, e o que fecha cada item:

| Sinal que falta | Fecha com | É o quê |
|---|---|---|
| `portal_http_requests_total` (5xx por `status`, tráfego por rota) | `log_format` JSON na borda **ou** middleware de métricas com `route` de vocabulário fechado | item de nginx **ou** de backend |
| histograma de latência | idem | item de backend |
| `portal_celery_queue_depth`, `portal_celery_tasks_total` | `manage.py saude_filas --json` — **já existe**, e é o que este diretório usa (§6) | já coberto |
| `portal_dependency_checks_total{dependency}` | métrica por dependência no `_Registro` | item de backend |
| `portal_collector_disk_free_ratio` | `node_filesystem_*` do node_exporter, que o projeto não tem | item de infra. **NÃO EXISTE ALERTA DE DISCO NESTE DIRETÓRIO** — a referência foi removida da expressão de `PortalTelemetriaNaoInstrumentada` e o buraco continua aberto (ver `alerts/README.md` §1.3.1 e §7.2) |
| `portal_sentry_events_dropped_total` | Sentry, que `develop` não tem | item de produto |
| `portal_health_check_not_configured` | publicar `Relatorio.nao_verificadas` como métrica | item de backend |
| `portal_metrics_series_dropped_total` | **não se aplica**: `develop` não tem teto de séries. Substituído por `PortalCardinalidadeAcimaDoOrcamento`, que mede | coberto |

## 5. `not_configured`: a lacuna que não pode ser silenciosa

`Relatorio.nao_verificadas` (`backend/config/health.py:302-309`) existe
justamente para que "não verificado" não se pareça com "verificado e ok":
`checar_cache` devolve `None` para `locmem` e `checar_broker` devolve `None`
para `memory://`, em vez de devolver um `ok` falso.

O preço dessa honestidade é que **essa lista é invisível para o
Prometheus**: `develop` não expõe
`portal_health_check_not_configured`. Um ambiente com Postgres verificado e
broker nunca verificado é indistinguível, no alerta, de um ambiente totalmente
verificado.

A correção aplicada aqui **não afrouxa a regra**: em vez de inventar a métrica,
há um **piso** —

* `PortalReadinessNaoSondada` dispara quando `/readyz` não foi sondado no
  ambiente por 15 min, o que cobre o extremo "ninguém está medindo";
* o painel `portal-saude-dependencias` tem um painel de texto que nomeia, check
  por check, o que continua cego;
* `better-stack/checks.json` traz o check de readiness com asserção de
  corpo (`$.status == "pronto"`), que é onde a distinção 1 × 3 de `saude_filas`
  é feita de verdade.

Um painel que dissesse "broker: ok" sem medir seria o oposto disso.

## 6. Filas: reuso de `filas_saude.py`, sem mecanismo duplicado

`develop` mede a saúde das filas com três estados e três códigos de saída
(`backend/config/management/commands/saude_filas.py:10-19`): `ok` (0),
`degradado` (1), `desconhecido` (3). Não existe `portal_celery_queue_depth`
nem `portal_celery_tasks_total`.

Um painel Grafana não executa comando de gerência, e inventar um exportador
Prometheus seria criar um segundo mecanismo de estado de fila. O caminho
adotado:

1. `saude_filas --json` continua sendo a fonte da verdade;
2. o JSON é indexado no **Loki** por `loki.source.file "filas"` em
   `config.alloy`. Só `estado` vira rótulo (três valores); todo o resto fica
   na linha. Um painel `logs` mostra o registro, e sem registro mostra
   `No data` — que é a verdade;
3. o **alerta** é do check externo, não de PromQL — o
   `cron_monitor_filas` de `checks.json`, que é o que
   `infra/filas/PROVISIONAMENTO.md` §2.3 já pede;
4. `verificar-env.sh` exige que `ALLOY_FILAS_JSON_PATH` exista, então a
   instalação sem o cron **reprova** em vez de deixar o painel vazio.

O cron que falta:

```bash
*/5 * * * * cd /home/apps/portal-<env> && \
  .venv/bin/python manage.py saude_filas --json \
  >> /var/lib/portal-noticias/saude_filas.jsonl
```

Detalhe completo, incluindo o buraco conhecido de `filas_saude.py` não medir
se o beat está agendando certo, em `alerts/README.md` §5.

## 7. Limitações e dependências externas (escritas aqui de propósito)

Cada uma destas é um ponto cego real. Nenhuma está escondida num painel que
promete mais do que entrega.

### Limitações do que existe

1. **`/metrics` é por processo.** O Django expõe o registro do processo que
   atendeu o scrape, e a API roda com mais de um worker Gunicorn
   (`health.py:426-436`). Contadores subestimam e zeram a cada restart. Por
   isso **toda** regra deste diretório usa limiar de ocorrência (`> 0`), nunca
   percentual.
2. **Gauge sobrevive a restart; contador não.** Só
   `portal_tempo_de_atividade_segundos` e `portal_readyz_duracao_ms` são
   fiáveis como estado.
3. **O log de borda é JSON, mas depende de o include estar instalado.** O
   `log_format portal_acesso` existe em `infra/nginx/http-cache.conf`
   (contexto `http`), com `escape=json` e todos os valores quotados; o
   `access_log` que o consome está nos três `infra/nginx/portal-*.conf`, em
   `server`, para `/var/log/nginx/portal-<amb>.access.log`. Isto está no
   repositório, **não na VPS**: o `log_format` só vale depois de
   `http-cache.conf` ser instalado dentro do `http {}` e o `nginx -t` passar.
   O `verificar-env.sh` exige o arquivo e avisa se a primeira linha não for
   JSON — é essa dupla verificação que transforma "não instalei o include" em
   aviso em vez de painel de acesso vazio. Um `log_format` que não foi
   instalado devolve o `combined` padrão, que é texto livre: o `stage.json`
   não extrai nada e o painel fica vazio **sem erro em lugar nenhum**.
4. **`/metrics` e `/health-detail` têm duas camadas, mas a de borda ainda não
   está na VPS.** Nos três `infra/nginx/portal-*.conf` há `location =
   /metrics` e `location = /health-detail` com `allow 127.0.0.1; allow ::1;
   deny all;` (o mesmo padrão do `/healthz`), no bloco HTTP e no TLS. A
   aplicação continua sendo a segunda camada e continua valendo: em loopback
   sem token ela devolve 401 (`health.py:414-418`). Isto é configuração no
   repositório: só vale depois do `nginx -t` e do reload na VPS. Medido antes
   da mudança, `/metrics` e `/health-detail` respondiam **404 pelo frontend**
   em HTTPS — barreira real, mas por acidente, dependente de o Next.js não
   ganhar um catch-all. O check `portao-privado-metrics` do Better Stack
   existe para vigir a exposição de fora e não depende do Nginx.
5. **A retenção de 90 dias do R2 é decisão humana**, não ratificada. O número
   está parametrizado, não aprovado.
6. **Uma instância do coletor por ambiente.** Um coletor único misturaria dev,
   homolog e prod. O preço é três unidades para manter.

### O que depende de provisionamento externo (bloqueado)

Nada abaixo pode ser feito por código, e nada aqui contém valor secreto:

- contas com MFA: **Grafana Cloud**, **Better Stack**, **Cloudflare R2**,
  **Sentry** (este último nem existe em `develop`);
- Contact Points do Grafana (`<CP_CRITICO_PRINCIPAL>`, `<CP_CRITICO_SUPLENTE>`,
  `<CP_WARNING>`, `<CP_RUNBOOK>`) e a política de notificação;
- canais: e-mail do responsável principal e do suplente, Telegram/Slack, e a
  lista de contatos;
- **domínios reais** de dev, homolog e prod, e a decisão do domínio canônico —
  os placeholders usam `<DOMINIO_DE_PRODUCAO>` e o TLD reservado `.invalid`,
  que nunca resolve;
- o **endereço interno de runbook** que substitui o placeholder
  `https://runbooks.portal.exemplo.invalid/`;
- a **decisão humana sobre a retenção remota** e a janela de produção para
  testar o restore mensal.

### Dois pingeres que não existem (e por que isso importa)

Os dois cron monitors de `checks.json` — backup e filas — precisam que alguém
faça o ping depois do sucesso verificado. **Nenhum dos dois faz, na topologia
ativa:**

* `infra/backup/pg_backup_pm2.sh` **não** faz ping de heartbeat. Termina em
  `log "backup concluído"` (linha 448) e sai. **Este é o script que a VPS usa.**
* `manage.py saude_filas` não faz ping, e o wrapper de 5 min que o faria
  (e que também anexaria ao JSONL do Loki) não existe.

A variante **Docker/Caddy já tem o pinger**: `infra/backup/pg_backup.sh` faz
`curl --fail` para `$BACKUP_HEARTBEAT_URL` só depois de publicar o dump e a
mídia e, havendo bucket, só depois de `head-object` confirmar os dois
objetos — e **nunca** em caso de falha, porque a ausência de ping é justamente
o sinal que abre o incidente. O comportamento está coberto por
`infra/backup/testar-pg-backup.sh` §10. Como o cron monitor se chama
`backup-diario-pm2` e a VPS é PM2, ele continua precisando do pinger do script
PM2 para funcionar.

Cadastrar esses dois cron monitors sem o pinger é pior do que não cadastrar:
eles ficariam em `desconhecido` desde o primeiro dia, disparando para o canal
de plantão e treinando o time a ignorar o canal. Está registrado em
`checks.json` e aqui para que ninguém os cadastre achando que funcionam. O que
já dá para cadastrar hoje é o watchdog local
`infra/backup/verificar_backup.sh`, que sai com código diferente de zero em
atraso, em ausência de dump e em ausência de cópia remota — e que não depende
de nenhum pinger.

## 8. O que NÃO entrou, e por quê

| Não entrou | Por quê |
|---|---|
| `backend/config/metrics.py` do WIP | `develop` já tem `/metrics` e um registro com cardinalidade **medida** em 33 séries (§`alerts/README.md` §3). O do WIP trazia teto de 5000 séries e um rótulo `route` vindo da URL — 94× pior. Trazer seria duplicar, com cardinalidade pior. |
| `backend/config/observability.py` e `observability_views.py` | `develop` já tem `health.py` + `views.py` com os três contratos separados e o portão de `/metrics` e `/health-detail`. Trazer seria uma segunda implementação do mesmo contrato. |
| `backend/metricas/**` | já existe em `develop` e é analytics de produto, não telemetria técnica. |
| `infra/observability/grafana/validar-infra.sh` e `scripts/observability/**` | não estavam no escopo fechado deste item, e `.github/` não pode ser tocado. O que era verificação de infra virou `verificar-correspondencia.py` + as duas provas em `proving/`, ambos rodáveis localmente. |
| os 6 workflows de CI/CD | fora de escopo por decisão explícita. |
