# Alertas — como carregar, para onde vão e o que NÃO é alerta de métrica

Run `20260925-1020-observabilidade` (critérios 22, 23, 34, 41).

## O que há aqui

| Arquivo | Grupo | Cobre |
|---|---|---|
| `regras-disponibilidade.yaml` | `portal-disponibilidade` | API inacessível, readiness, taxa de 5xx, latência p95, coletor cego, telemetria ausente |
| `regras-operacao.yaml` | `portal-operacao` | fila Celery, Celery sem execução, task falhando, **atraso de job pelo canal durável, task que nunca conclui, check sem sinal próprio**, dependência crítica/opcional, disco do coletor, Sentry descartando, cardinalidade, acesso privado negado |

Nenhuma regra depende de `.github/`, de Terraform ou de provisionamento
externo para *existir*: são regras Prometheus/Mimir puras, com `expr`,
`for`, `labels` e `annotations`.

## Deduplicação (critério 22)

Deduplicação em Prometheus **não** é um campo: é a identidade do alerta. Uma
instância de alerta é identificada pelo conjunto de rótulos da expressão, e o
Grafana agrupa por esses rótulos. Duas decisões seguem daí e elas são
deliberadas:

1. **Uma regra, uma instância por ambiente.** As expressões usam
   `by (ambiente)` e não filtram `ambiente="..."`. Assim existe UM arquivo,
   não três, e o mesmo sintoma em dev e em prod são dois alertas distintos
   (rótulos diferentes) — o que é o comportamento correto, porque a ação é
   diferente.
2. **Quando o problema É POR ITEM, o item entra na identidade.** Três regras
   (D2) agrupam por `by (ambiente, check)` ou `by (ambiente, task)`:
   `PortalCheckSemSinal`, `PortalJobAtrasado` e `PortalJobNuncaConcluiu`. São
   problemas diferentes com ações diferentes — dois checks cegos, ou duas tasks
   paradas, não são o mesmo incidente — então duas instâncias é o certo, e não
   ruído. Consequência prática: o `mute timing` de 30 min precisa incluir
   `check`/`task` além de `runbook` e `ambiente`, senão o mute de uma task
   silenciaria as outras do mesmo ambiente.
3. **`for:` é a deduplicação temporal.** Sem `for`, cada evaluation que
   satisfaz a condição gera notificação. Os valores estão justificados em
   cada regra e vêm do comportamento real (ingestão a cada 15 min, scrape a
   cada 30 s, `QUEUE_DEPTH_WARN` = 1000).

Além disso, todas as regras carregam `severity` e `runbook_url`, e o Contact
Point do Grafana é quem decide o canal por severidade (tabela abaixo).

## Canais e Contact Points (o que falta provisionar)

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
  por todo mundo. Nas três regras por item (D2), acrescente `check`/`task` ao
  critério do mute, pelo motivo exposto na seção de deduplicação;
* `notification policy` com **continue/repeat** em 4 h para `critical`, porque
  incidente longo precisa lembrar que está em curso;
* agrupamento por `alertname` + `ambiente` (não por `instance`): a instância
  muda a cada restart e agrupar por ela recria o alerta como "novo".

## O que NÃO é alerta de métrica (e onde está)

Três sintomas que a run exige (critérios 23, 33, 34) **não podem** ser alertas
de métrica, porque a métrica morre junto com a falha. Colocá-los no Grafana
seria um painel que promete o que não existe:

| Sintoma | Canal correto | Por quê |
|---|---|---|
| A VPS está no ar / rota HTTPS responde | Better Stack HTTP check em `https://<host>/readyz` | o monitor roda de fora; se a VPS cai, ele ainda avisa |
| Certificado TLS perto de expirar | Better Stack HTTP check (o próprio HTTPS valida a cadeia) | o monitor é externo à VPS |
| Atraso de backup | Better Stack **cron monitor** (ping do `pg_backup_pm2.sh` após sucesso verificado) + `infra/backup/verificar_backup.sh` | um watchdog na própria VPS não avisa quando a VPS morre |

O `runbook_url` de todas as regras aponta para
`https://runbooks.portal.exemplo.invalid/...` — domínio reservado pela RFC 2606,
que nunca resolve. É um placeholder deliberado: um endereço de exemplo
parecido com um real seria pior que um obviously-falso. **Troque pelo endereço
interno antes de carregar as regras**; `scripts/observability/validar-infra.sh`
falha enquanto o `.invalid` estiver no arquivo.

## Como carregar (Grafana Cloud)

```bash
# 1) Subir os arquivos para a stack (o Grafana provisiona por HTTP da API, ou
#    o ruler da stack lê de um bucket). Os comandos exatos dependem do plano
#    contratado (Alerting gerenciado vs Mimir ruler) — decidir com a conta.
# 2) Conferir que o Mimir aceitou:
curl -sS -H "Authorization: Bearer $TOKEN" \
  "$MIMIR_URL/api/v1/rules" | jq '.data.groups[].name'
#    esperado: portal-disponibilidade, portal-operacao
#
# 3) Testar cada regra de alerta (critério 41): disparar, confirmar a entrega
#    nos três canais e depois encerrar/acknowledge. Regra que nunca disparou
#    é regra não testada.
```

## Painéis

`infra/observability/grafana/dashboards/*.json` (4 painéis técnicos). Nenhum
painel cita métrica que o backend não exponha — a validação está em
`scripts/observability/validar-infra.sh`, que também rejeita
`portal_ingestion_executions_total` (nome declarado em `config/metrics.py` que
**nunca é incrementado**, e que por isso viraria painel vazio para sempre).
