# Alertas — correspondência com o backend, carregamento e o que NÃO é alerta de métrica

Item **P2-01** (Onda 2, consolidação da observabilidade), sobre `develop` =
`1dec732`. Este arquivo é a parte que decide se a malha funciona: uma regra
que aponta para uma métrica que o backend não expõe não é uma regra, é uma
decoração que parece cobertura.

---

## 1. Tabela de correspondência — o que os painéis e as regras pedem × o que o backend expõe

Método: `GET /metrics` foi executado contra o código de `develop` (Django
5.2.17, `config.settings_test`) e a saída foi comparada, nome a nome, com
toda expressão PromQL dos 4 dashboards e das 2 regras. A coluna "pedido por"
diz **arquivo:linha** do lado do infra; a coluna "exposto em" diz
**arquivo:linha** do lado do backend.

### 1.1 O que `develop` DE FATO expõe (a lista completa, 11 nomes)

Saída literal de `/metrics` de `develop`, depois de exercitar todos os
caminhos de código:

```
# TYPE portal_tempo_de_atividade_segundos gauge
portal_tempo_de_atividade_segundos 0.062
# TYPE portal_acesso_negado_total counter
portal_acesso_negado_total{recurso="metrics"} 1
# TYPE portal_config_insegura_total counter
portal_config_insegura_total{item="email_backend"} 1
# TYPE portal_health_detail_total counter
portal_health_detail_total{situacao="ok"} 1
# TYPE portal_healthz_total counter
portal_healthz_total{situacao="ok"} 1
# TYPE portal_livez_total counter
portal_livez_total{situacao="ok"} 1
# TYPE portal_metrics_total counter
portal_metrics_total 2
# TYPE portal_readyz_duracao_ms gauge
portal_readyz_duracao_ms 1
# TYPE portal_readyz_total counter
portal_readyz_total{situacao="ok"} 1
```

| # | Métrica | Rótulos | Incrementada em | Quando |
|---|---|---|---|---|
| 1 | `portal_tempo_de_atividade_segundos` | — | `backend/config/health.py:459-461` | sempre (gauge, no `render()`) |
| 2 | `portal_healthz_total` | `situacao="ok"` | `backend/config/views.py:83` | `GET /healthz` |
| 3 | `portal_livez_total` | `situacao="ok"` | `backend/config/views.py:97` | `GET /livez` |
| 4 | `portal_readyz_total` | `situacao` ∈ {`ok`,`nao_pronto`} | `backend/config/views.py:116` | `GET /readyz` |
| 5 | `portal_readyz_duracao_ms` | — | `backend/config/views.py:117` | `GET /readyz` (gauge) |
| 6 | `portal_health_detail_total` | `situacao` ∈ {`ok`,`degradado`} | `backend/config/views.py:142` | `GET /health-detail` autorizado |
| 7 | `portal_acesso_negado_total` | `recurso` ∈ {`health_detail`,`metrics`} | `backend/config/views.py:138,215` | negação de token/staff |
| 8 | `portal_config_insegura_total` | `item` ∈ {`media_root`,`email_backend`} | `backend/config/views.py:160,183` | `MEDIA_ROOT` servida / e-mail sem entrega |
| 9 | `portal_metrics_total` | — | `backend/config/views.py:218` | scrape autorizado |
| 10 | `portal_email_entrega_total` | `destino` (5) × `situacao` (3) | `backend/config/email_entrega.py:184-186` | tentativa de entrega |
| 11 | `portal_email_falha_provedor_total` | `destino` (5) × `tipo` (**livre**) | `backend/config/email_entrega.py:210-212` | exceção do provedor |

Mais duas séries que **não** vêm do backend, e sim do coletor, e por isso
existem de fato assim que o Alloy roda:
`up{job="portal-api",ambiente=...}` e `up{job="alloy",ambiente=...}`
(`infra/observability/alloy/config.alloy`, blocos `prometheus.scrape`).

### 1.2 Correspondência completa das referências dos 6 documentos

| Pedido por | Métrica pedida | Existe em `develop`? | Onde está exposta / o que substitui |
|---|---|---|---|
| `regras-disponibilidade.yaml:34` | `up{job="portal-api"}` | **SIM** (coletor) | `config.alloy` `prometheus.scrape "portal_api"` |
| `regras-disponibilidade.yaml:36` | `absent(up{job="portal-api"})` | **SIM** (coletor) | idem |
| `regras-disponibilidade.yaml:58` *(WIP)* | `portal_ready` | **NÃO** | — |
| `regras-disponibilidade.yaml:76` *(nova)* | `portal_readyz_total{situacao="nao_pronto"}` | **SIM** | `backend/config/views.py:116` |
| `regras-disponibilidade.yaml:87` *(nova)* | `absent(portal_readyz_total)` | **SIM** (o `absent` é real) | `backend/config/views.py:116` |
| `regras-disponibilidade.yaml:127` | `up{job="alloy"}` | **SIM** (coletor) | `config.alloy` `prometheus.scrape "alloy"` |
| `regras-disponibilidade.yaml:148` | `absent(up{ambiente="production",...})` | **SIM**, **e foi corrigido** | só funciona porque `config.alloy` posta `ambiente` como rótulo **em banda** via `prometheus.relabel`; com só `external_labels` esta regra é incapaz de disparar |
| `regras-disponibilidade.yaml:267` | `absent(portal_http_requests_total or …)` | **`absent` é real**; as 16 séries ausentes são o que se quer denunciar | ver §1.3 |
| `regras-operacao.yaml:99` *(nova)* | `portal_health_detail_total{situacao="degradado"}` | **SIM** | `backend/config/views.py:142` |
| `regras-operacao.yaml:124` *(nova)* | `absent(up{…}) and absent(portal_config_insegura_total)` | **SIM** | `views.py:142,160,183` |
| `regras-operacao.yaml:172` *(nova)* | `portal_email_entrega_total{situacao="sem_canal"}` | **SIM** | `backend/config/email_entrega.py:184` |
| `regras-operacao.yaml:190` *(nova)* | `portal_email_falha_provedor_total` | **SIM** | `email_entrega.py:210` |
| `regras-operacao.yaml:212` *(nova)* | `portal_config_insegura_total` | **SIM** | `views.py:160,183` |
| `regras-operacao.yaml:229` | `portal_acesso_negado_total{recurso}` | **SIM** *(o WIP pedia `portal_observability_access_denied_total` — **NÃO** existia)* | `views.py:138,215` |
| `regras-operacao.yaml:294` *(nova)* | `count by (__name__) ({__name__=~"portal_.*"})` | **SIM** (auto-referente) | mede a exposição de §1.1 |
| `regras-operacao.yaml:339` *(nova)* | `portal_tempo_de_atividade_segundos` | **SIM** | `health.py:459-461` |
| *(WIP)* `regras-operacao.yaml:26,43` | `portal_celery_queue_depth` | **NÃO** | substituído por `manage.py saude_filas --json` (ver §5) |
| *(WIP)* `regras-operacao.yaml:65,83` | `portal_celery_tasks_total` | **NÃO** | idem |
| *(WIP)* `regras-operacao.yaml:123,153` | `portal_job_task_idle_seconds` | **NÃO** | idem (`filas_estado.py` existe, não é exposto) |
| *(WIP)* `regras-operacao.yaml:187` | `portal_health_check_not_configured` | **NÃO** | substituído por `PortalReadinessNaoSondada` (piso) + leitura de `nao_verificadas` no corpo de `/readyz` |
| *(WIP)* `regras-operacao.yaml:212,229` | `portal_dependency_checks_total` | **NÃO** | substituído por `portal_health_detail_total{situacao="degradado"}` |
| *(WIP)* `regras-operacao.yaml:250` | `portal_collector_disk_free_ratio` | **NÃO** | nenhum componente do Alloy nem do Prometheus a expõe; só `node_filesystem_*` do node_exporter, que o projeto não tem |
| *(WIP)* `regras-operacao.yaml:271` | `portal_sentry_events_dropped_total` | **NÃO** | `develop` não tem Sentry. Substituído por `PortalEmailNaoEntregue`, que é a mesma classe de falha (serviço "verde" que não entrega) com dado real |
| *(WIP)* `regras-operacao.yaml:289` | `portal_metrics_series_dropped_total` | **NÃO** | `develop` **não tem teto de séries**. Substituído por `PortalCardinalidadeAcimaDoOrcamento`, que mede em vez de contar descarte |
| `portal-disponibilidade.json` | `portal_ready` | **NÃO** | painel substituído por `portal_readyz_total` |
| `portal-disponibilidade.json` | `portal_http_requests_total` | **NÃO** | painel "NÃO MEDIDO" + `PortalTelemetriaNaoInstrumentada` |
| `portal-disponibilidade.json` | `portal_http_request_duration_seconds_{bucket,sum,count}` | **NÃO** | idem |
| `portal-disponibilidade.json` | `portal_degraded_responses_total` | **NÃO** | substituído por `portal_health_detail_total{situacao="degradado"}` |
| `portal-disponibilidade.json` | `portal_livez_total` | **SIM** | `views.py:97` |
| `portal-disponibilidade.json` | `portal_readyz_total` | **SIM** | `views.py:116` |
| `portal-disponibilidade.json` | `portal_metrics_scrapes_total` | **NÃO** | substituído por `portal_metrics_total` (`views.py:218`) |
| `portal-filas-celery.json` | `portal_celery_queue_depth` | **NÃO** | `saude_filas --json` (Loki) |
| `portal-filas-celery.json` | `portal_celery_tasks_total` | **NÃO** | idem |
| `portal-filas-celery.json` | `portal_celery_task_duration_seconds_bucket` | **NÃO** | idem |
| `portal-ingestao.json` | `portal_celery_tasks_total{task="catalogo_noticias.tasks.ingerir_noticias"}` | **NÃO** | idem; e o nome da task também não é o de `develop` (§5) |
| `portal-ingestao.json` | `portal_ingestion_executions_total` | **NÃO** | o próprio WIP admitia: declarada e nunca incrementada. **Removida do painel** |
| `portal-ingestao.json` | `portal_http_requests_total{route=~"feed.*"}` | **NÃO** | idem |
| `portal-saude-dependencias.json` | `portal_dependency_checks_total` | **NÃO** | substituído por `portal_health_detail_total` |
| `portal-saude-dependencias.json` | `portal_dependency_check_duration_seconds_bucket` | **NÃO** | substituído por `portal_readyz_duracao_ms` (`views.py:117`) |
| `portal-saude-dependencias.json` | `portal_health_degraded_total` | **NÃO** | substituído por `portal_health_detail_total{situacao="degradado"}` |
| `portal-saude-dependencias.json` | `portal_collector_disk_free_ratio` | **NÃO** | ver acima |
| `portal-saude-dependencias.json` | `portal_sentry_events_dropped_total` | **NÃO** | ver acima |
| `portal-saude-dependencias.json` | `portal_metrics_series_dropped_total` | **NÃO** | ver acima |
| `portal-saude-dependencias.json` | `portal_observability_access_denied_total` | **NÃO** | substituído por `portal_acesso_negado_total{recurso}` |
| `better-stack/checks.json:37` | corpo `"ready": true` de `/readyz` | **NÃO** | `develop` devolve `{"status":"pronto","checagens":{…}}` (`views.py:118-121`). **Corrigido** — ver §6 |

**Placar:** das **47 referências** de métrica/contrato nos 6 documentos do WIP,
**7 existiam** em `develop` (todas do coletor, nenhuma do backend) e **40 não**.
Das 47, **40 foram corrigidas** no artefato: 21 viraram métrica real de
`develop`, 19 viraram "NÃO MEDIDO" declarado + uma regra de ausência.

### 1.3 As 16 séries que `develop` não expõe

Esta lista é literalmente a expressão de
`PortalTelemetriaNaoInstrumentada`
(`regras-disponibilidade.yaml:267`):

`portal_http_requests_total`,
`portal_http_request_duration_seconds_bucket`,
`portal_celery_queue_depth`,
`portal_celery_tasks_total`,
`portal_celery_task_duration_seconds_bucket`,
`portal_job_task_idle_seconds`,
`portal_dependency_checks_total`,
`portal_dependency_check_duration_seconds_bucket`,
`portal_ingestion_executions_total`,
`portal_degraded_responses_total`,
`portal_health_check_not_configured`,
`portal_sentry_events_dropped_total`,
`portal_metrics_series_dropped_total`,
`portal_collector_disk_free_ratio`,
`portal_observability_access_denied_total`,
`portal_metrics_scrapes_total`

Enquanto esta regra estiver de pé, ninguém pode confundir "o painel está vazio"
com "o portal está tranquilo". É a regra que transforma a lacuna em barulho.

---

## 2. O que há aqui

| Arquivo | Grupo | Regras | Cobre |
|---|---|---|---|
| `regras-disponibilidade.yaml` | `portal-disponibilidade` | 6 | API inacessível, readiness falhando, readiness nunca sondada, coletor cego, telemetria de um ambiente ausente, **sinais que develop não instrumenta** |
| `regras-operacao.yaml` | `portal-operacao` | 8 | dependência crítica degradada, filas sem canal de telemetria, **e-mail não entregue**, falha do provedor, configuração insegura, acesso privado negado, **cardinalidade acima do orçamento**, processo reiniciando |

Nenhuma regra depende de `.github/`, de Terraform ou de provisionamento
externo para *existir*: são regras Prometheus/Mimir puras, com `expr`, `for`,
`labels` e `annotations`.

Validação sintática e de template: `promtool check rules --lint=all` nos dois
arquivos (ver §7).

---

## 3. Cardinalidade de rótulo — a medição

`develop` registra em memória, por processo, e **sem teto de séries**
(`backend/config/health.py:438-455`: só um `Lock` e dois dicts; não existe
`MAX_SERIES` nem descarte). A cardinalidade é, portanto, limitada **por
design** — mas isso precisa ser medido, não afirmado.

| Métrica | Rótulos | Combinações | Fechado por design? |
|---|---|---|---|
| `portal_tempo_de_atividade_segundos` | — | 1 | sim |
| `portal_readyz_duracao_ms` | — | 1 | sim |
| `portal_metrics_total` | — | 1 | sim |
| `portal_healthz_total` | `situacao` | 1 (`ok`) | sim — `_registrar` só passa `situacao="ok"` (`views.py:83`) |
| `portal_livez_total` | `situacao` | 1 (`ok`) | sim — `views.py:97` |
| `portal_readyz_total` | `situacao` | 2 | sim — ternário `views.py:116` |
| `portal_health_detail_total` | `situacao` | 2 | sim — ternário `views.py:142` |
| `portal_acesso_negado_total` | `recurso` | 2 | sim — literais `views.py:138,215` |
| `portal_config_insegura_total` | `item` | 2 | sim — literais `views.py:160,183` |
| `portal_email_entrega_total` | `destino` × `situacao` | 5 × 3 = 15 | sim — `DESTINO_*` e os 3 literais de `registrar_evento` |
| `portal_email_falha_provedor_total` | `destino` × `tipo` | 5 × N | **NÃO para `tipo`** |

**Totais medidos**, percorrendo todos os valores alcançáveis e contando a
saída real do `render()`:

* **33 séries** no pior caso com um valor de `tipo` (o piso honesto);
* **53 séries** com cinco classes de exceção diferentes;
* 28 séries se `portal_email_falha_provedor_total` não existisse.

**O único rótulo de valor livre em `develop` é `tipo`**, em
`backend/config/email_entrega.py:211` (`tipo=type(exc).__name__`). A
mitigação já está no código e é real: a entrada é o **nome da classe**, nunca
`str(exc)` nem a mensagem, então a mensagem do provedor (que pode ecoar o
payload de um e-mail de verificação, com o token dentro) não entra no rótulo.
O risco residual é o número de classes de exceção distintas que um ambiente
pode produzir; `PortalCardinalidadeAcimaDoOrcamento` é o que vigia isso
continuamente.

**Comparação com o WIP:** `config/metrics.py` do WIP tinha
`MAX_SERIES = 5_000` e `MAX_SERIES_POR_METRICA = 500` com um rótulo `route`
derivado do path resolvido — ou seja, teto 94× maior e com um rótulo que o
cliente controla. `develop` é melhor aqui, e é por isso que **nada** daquele
módulo foi trazido.

**Os rótulos deste diretório** — `ambiente`, `job`, `instance`, `recurso`,
`item`, `situacao`, `destino`, `servico`, `severity`, `runbook` — são todos de
vocabulário fechado, exceto `instance`, que é o endereço do alvo do scrape
(uma faixa de IP por ambiente, ~1 valor). As regras de alerta agregam
`by (ambiente[, destino|situacao|recurso|item])`, de modo que nem `instance`
nem `__name__` entram na identidade de nenhum alerta.

---

## 4. O que NÃO é alerta de métrica (e onde está)

Cinco sintomas que o item exige **não podem** ser alertas de métrica, porque
a métrica morre junto com a falha. Colocá-los no Grafana seria um painel que
promete o que não existe:

| Sintoma | Canal correto | Por quê |
|---|---|---|
| A VPS está no ar / rota HTTPS responde | Better Stack HTTP check em `https://<host>/readyz` e `/livez` | o monitor roda de fora; se a VPS cai, ele ainda avisa |
| Certificado TLS perto de expirar | Better Stack **TLS check** | o monitor é externo à VPS |
| Atraso de backup | Better Stack **cron monitor** (ping após sucesso verificado) + `infra/backup/verificar_backup.sh` | um watchdog na VPS não avisa quando a VPS morre |
| Profundidade de fila / worker / heartbeat | `manage.py saude_filas --json` + check externo (§5) | o dado existe, mas como JSON e código de saída — não como métrica |
| Início e queda de TLS na borda | idem TLS check | o Collector do Alloy não vê a cadeia pública |

**Sobre o bloqueio de borda:** o WIP afirmava que `infra/nginx/portal-*.conf`
tinha `location ^/(health-detail|metrics)$` bloqueando origem externa.
**Verificado em `develop`: esse location não existe** — `grep -n
'metrics\|health-detail' infra/nginx/portal-prod.conf` devolve apenas
`location = /healthz`. A única proteção de `/metrics` e `/health-detail` hoje é
da aplicação (`backend/config/health.py:414-418`, anônimo = 401, token
comparado com `hmac.compare_digest`). Isso muda a leitura de
`PortalAcessoPrivadoSendoSondado`: uma negação **vista pela aplicação** não
significa camada 2, significa camada 1. Item próprio, não corrigido aqui
porque `infra/nginx/` está fora do escopo deste lote.

O `runbook_url` de todas as regras aponta para
`https://runbooks.portal.exemplo.invalid/...` — domínio reservado pela RFC
2606, que nunca resolve. É um placeholder deliberado: um endereço de exemplo
parecido com um real seria pior que um obviously-falso. **Troque pelo endereço
interno antes de carregar as regras**; `verificar-env.sh` falha enquanto o
`.invalid` estiver no arquivo.

---

## 5. Filas: como `filas_saude.py` foi reutilizado

`develop` já mede a saúde das filas e a publica com **três estados e três
códigos de saída** (`backend/config/management/commands/saude_filas.py:10-19`):

| estado | exit | significado |
|---|---|---|
| `ok` | 0 | tudo verificado e sem problema |
| `degradado` | 1 | medido e com problema |
| `desconhecido` | 3 | **não foi possível verificar** |

O `3` é deliberadamente diferente do `0`: um monitor genérico que trata "não
sei" como sucesso é o falso verde que o P1-03 existe para matar. O painel
`portal-filas-celery` **não** inventou métrica para contornar isso. O caminho
adotado, sem criar um segundo mecanismo de estado de fila:

1. **`saude_filas --json` continua sendo a fonte da verdade.** Os campos
   nomeados que o painel mostra vêm de
   `dependencias.broker.profundidade`,
   `dependencias.workers.idade_da_mais_antiga_s`,
   `dependencias.ultimo_ciclo.estado`.
2. **O JSON é indexado no Loki**, não no Mimir, por
   `loki.source.file "filas"` em `config.alloy` (variável
   `ALLOY_FILAS_JSON_PATH`). Só `estado` vira rótulo — três valores por
   contrato — e todo o resto fica na linha. Um Grafana **logs panel** mostra o
   registro, e um painel sem registro mostra `No data`, que é a verdade.
3. **O alerta é do check externo**, não de PromQL:
   `infra/filas/PROVISIONAMENTO.md` §2.3 já pede exatamente isso
   ("crítico se o processo sai ≠ 0"), e `better-stack/checks.json` traz o
   `cron_monitor` de filas com `expect_period_seconds` e o contrato de
   distingueção entre 1 e 3.
4. **`infra/filas/PROVISIONAMENTO.md:110` já registra que a transformação
   JSON → métrica Prometheus é provisionamento, não código.** Este lote
   concorda e não a faz.

`PortalFilaDeMonitoracaoAusente` cobre a ponta que o Prometheus enxerga: se o
registro some do canal, o painel fica sem dado e alguém é avisado.

**Nomes conferidos, e um que estava certo por acidente.** O painel do WIP
ancorava a execução em `task="catalogo_noticias.tasks.ingerir_noticias"`, e
esse nome EXISTE em `develop` (`backend/config/settings.py:875` e
`backend/catalogo_noticias/tasks.py:65`, intervalo padrão de 15 min em
`settings.py:811-812`). O que não existe é a métrica que contaria essa
execução. Já o painel do WIP afirmava que as tasks do schedule eram "as seis
tasks agendadas" de `feed.tasks`; o que existe em `develop` é
`config.tasks.heartbeat_beat` (`infra/filas/PROVISIONAMENTO.md:18`,
`backend/config/tasks.py:41`) mais as de assinatura e newsletter. Um painel que
narra o schedule errado ensina o operador a procurar o nome errado.

---

## 6. Canais e Contact Points (o que falta provisionar)

O destino **não** está neste repositório: é configuração do Grafana e canal
humano. Nomes abaixo são placeholders e precisam existir antes de carregar as
regras.

| Severidade | Contact Point (a criar) | Canal | Quem |
|---|---|---|---|
| `critical` | `<CP_CRITICO_PRINCIPAL>` | e-mail do responsável principal + Telegram | responsável principal |
| `critical` (fora de janela) | `<CP_CRITICO_SUPLENTE>` | e-mail do suplente | suplente |
| `warning` | `<CP_WARNING>` | Slack/Discord do time | time |
| todo alerta | `<CP_RUNBOOK>` | post no canal com o `runbook_url` | time |

Regras mínimas de Contact Point, para que a tabela acima não seja decorativa:

* `mute timings` de 30 min por `runbook` e `ambiente` — sem isso, um incidente
  que derruba readiness gera uma notificação por minuto e o canal é silenciado
  por todo mundo. As regras por item agregam por `by (ambiente, destino)`,
  `by (ambiente, recurso)` ou `by (ambiente, item)`, então acrescente esses
  rótulos ao critério do mute;
* `notification policy` com **continue/repeat** em 4 h para `critical`, porque
  incidente longo precisa lembrar que está em curso;
* agrupamento por `alertname` + `ambiente` (não por `instance`): a instância
  muda a cada restart e agrupar por ela recria o alerta como "novo";
* `PortalTelemetriaNaoInstrumentada` e
  `PortalCardinalidadeAcimaDoOrcamento` devem ir para um canal de
  **engenharia** e não para o de plantão: elas descrevem dívida de
  instrumentação conhecida, e paging o plantão por elas é o caminho mais curto
  para todo mundo aprender a não olhar alerta.

---

## 7. Como carregar (Grafana Cloud)

```bash
# 1) Subir os arquivos para a stack. Os comandos exatos dependem do plano
#    contratado (Alerting gerenciado vs ruler do Mimir).
# 2) Conferir que o Mimir aceitou:
curl -sS -H "Authorization: Bearer $TOKEN" \
  "$MIMIR_URL/api/v1/rules" | jq '.data.groups[].name'
#    esperado: portal-disponibilidade, portal-operacao
#
# 3) Validar ANTES de subir (o que foi feito neste lote):
docker run --rm --entrypoint promtool -v "$PWD":/r:ro \
  prom/prometheus:latest check rules --lint=all \
  /r/infra/observability/alerts/regras-disponibilidade.yaml \
  /r/infra/observability/alerts/regras-operacao.yaml
#    esperado: "SUCCESS: 6 rules found" e "SUCCESS: 8 rules found", exit 0
#
# 4) Testar cada regra (critério 41): disparar, confirmar a entrega nos três
#    canais e depois encerrar/acknowledge. Regra que nunca disparou é regra
#    não testada. Uma regra que NÃO PODE disparar é pior que uma não testada.
```

`promtool check rules` não é decorativo aqui: durante este lote ele
**reprovou** `regras-operacao.yaml` porque um exemplo de PromQL dentro de
`{{ }}` numa anotação contém `=`, e o parser de template Go rejeita. Sem a
correção, as 8 regras do arquivo não carregavam.

### 7.1 Duas regras que eram incapazes de disparar

O teste unitário de `proving/provar-regras.py` (que exige, para cada uma das
14 regras, que ela **dispare** com o sinal presente e que **resolva** com ele
ausente) encontrou duas regras que passavam em `promtool check rules` e mesmo
assim eram verde para sempre. Nenhuma das duas apareceria em revisão de texto:

1. **`PortalProcessoReiniciando` usava `changes()` num gauge que só sobe.**
   `changes()` conta **qualquer** mudança de valor, e
   `portal_tempo_de_atividade_segundos` é um uptime: ele sobe continuamente.
   `changes(...[30m])` devolvia ~20 num sistema perfeitamente saudável, e a
   condição `>= 3` era sempre verdadeira. A regra seria um alarme fixo — o
   oposto do falso verde, e pior: paging constante que treina o time a
   ignorar o canal. **Corrigido para `resets()`**, que conta quedas. Medido no
   teste: `resets()` de uma série estável = 0; de uma série com 3 quedas = 3.

2. **`PortalFilaDeMonitoracaoAusente` usava `absent(A) and absent(B)`.**
   `absent()` devolve um vetor cujos rótulos são **derivados dos matchers** do
   argumento. Então `absent(up{ambiente="production", job="portal-api"})` vem
   com `{ambiente="production", job="portal-api"}` e
   `absent(portal_config_insegura_total)` vem com `{}`. O operador de
   interseção `and` exige conjuntos de rótulos **idênticos**, então os dois
   lados nunca se cruzam. **Corrigido para `absent(A or B)`**, que é a mesma
   semântica sem a armadilha.

   O mesmo mecanismo feriria qualquer `absent()` usado com `and` neste
   diretório — e vale para quem for escrever regra nova aqui: **nunca
   combine dois `absent()` com `and`.** Use `absent(A or B)`, ou `and on()`
   quando precisar da interseção.

3. Uma terceira armadilha da mesma família, esta na verificação: o
   verificador de correspondência reprovou os 4 painéis na primeira execução
   porque eu tinha escrito `up{${ambiente:raw}, job="portal-api"}`. O Grafana
   renderiza isso como `up{production, job=...}`, que é **sintaxe inválida** —
   todo painel que usasse a variável de ambiente seria um `No data`. A forma
   correta é `up{ambiente=~"${ambiente:raw}"}`, com operador explícito.

---

## 8. Painéis

`infra/observability/grafana/dashboards/*.json` (4 painéis técnicos). Nenhum
painel cita métrica que o backend de `develop` não exponha: onde o dado não
existe, o painel **diz que não está medindo** e nomeia o item de backend que
fecharia a lacuna. Um painel que mostra `No data` sem explicar por quê é o
mesmo falso verde, só com outro formato.
