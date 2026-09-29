#!/usr/bin/env python3
"""
Gera os 4 painéis de `infra/observability/grafana/dashboards/`.

Por que um gerador e não JSON escrito à mão: cada `targets[].expr` deste
diretório tem que passar pelo `promtool check rules` do Prometheus (a
validação de sintaxe e de template mais rigorosa que existe para PromQL), e o
JSON escrito à mão erra aspas em expressão multilinha mais cedo ou mais
tarde. Aqui cada expressão é uma string Python, e o validador roda sobre o
arquivo GERADO — ou seja, sobre exatamente o que será importado no Grafana.

Todo painel cujo sinal não existe em `develop` é um painel `text` que DIZ que
não está medindo e nomeia o item de backend que fecharia a lacuna. Nenhum
painel aponta para métrica inexistente.

Uso:  python3 gerar_dashboards.py <destino>
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

# `=~` e nao `=`: o template precisa de um OPERADOR de casamento explicito.
# A forma `{${ambiente:raw}}` renderiza `{production}` em PromQL, que e sintaxe
# INVALIDA — e foi exatamente o que o verificador de correspondencia pegou na
# primeira execucao deste arquivo. `:raw` impede que o Grafana embrulhe o valor
# em parenteses de regex.
VALOR_AMBIENTE = '${ambiente:raw}'
ROTULO_AMBIENTE = f'ambiente=~"{VALOR_AMBIENTE}"'
RI = "$__rate_interval"

# ---------------------------------------------------------------------------
# Blocos reutilizados
# ---------------------------------------------------------------------------

def datasource():
    return {"type": "prometheus", "uid": "${DS_PROMETHEUS}"}


def ds_loki():
    return {"type": "loki", "uid": "${DS_LOKI}"}


def target(refid, expr, legend="", instant=True, fmt="time_series"):
    t = {
        "datasource": datasource(),
        "editorMode": "code",
        "expr": expr,
        "legendFormat": legend,
        "range": not instant,
        "instant": instant,
        "format": fmt,
        "refId": refid,
    }
    return t


def target_loki(refid, expr):
    return {
        "datasource": ds_loki(),
        "editorMode": "code",
        "expr": expr,
        "queryType": "range",
        "direction": "backward",
        "refId": refid,
    }


def stat(panel_id, title, grid, desc, targets, unit="short", thresholds=None,
         text_mode="auto", mappings=None, legend_calcs=("lastNotNull",)):
    if thresholds is None:
        thresholds = [
            {"color": "text", "state": None, "value": None},
        ]
    return {
        "id": panel_id,
        "type": "stat",
        "title": title,
        "description": desc,
        "datasource": datasource(),
        "gridPos": grid,
        "fieldConfig": {
            "defaults": {
                "unit": unit,
                "decimals": 2,
                "mappings": mappings or [],
                "thresholds": {"mode": "absolute", "steps": thresholds},
                "color": {"mode": "thresholds"},
            },
            "overrides": [],
        },
        "options": {
            "reduceOptions": {
                "calcs": list(legend_calcs),
                "fields": "",
                "values": False,
            },
            "textMode": text_mode,
            "colorMode": "value",
            "graphMode": "area",
            "justifyMode": "auto",
            "orientation": "auto",
            "wideLayout": True,
        },
        "targets": targets,
    }


def timeseries(panel_id, title, grid, desc, targets, unit="short",
               thresholds=None, stack=False, legend_calcs=("lastNotNull", "max")):
    if thresholds is None:
        thresholds = [{"color": "text", "state": None, "value": None}]
    return {
        "id": panel_id,
        "type": "timeseries",
        "title": title,
        "description": desc,
        "datasource": datasource(),
        "gridPos": grid,
        "fieldConfig": {
            "defaults": {
                "unit": unit,
                "decimals": 2,
                "custom": {
                    "axisBorderShow": False,
                    "axisCenteredZero": False,
                    "axisColorMode": "text",
                    "axisLabel": "",
                    "axisPlacement": "auto",
                    "barAlignment": 0,
                    "drawStyle": "line",
                    "fillOpacity": 10 if stack else 0,
                    "gradientMode": "none",
                    "hideFrom": {"legend": False, "tooltip": False, "viz": False},
                    "insertNulls": False,
                    "lineInterpolation": "linear",
                    "lineWidth": 2,
                    "pointSize": 5,
                    "scaleDistribution": {"type": "linear"},
                    "showPoints": "never",
                    "spanNulls": False,
                    "stacking": {"group": "A", "mode": "normal" if stack else "none"},
                    "thresholdsStyle": {"mode": "off"},
                },
                "mappings": [],
                "thresholds": {"mode": "absolute", "steps": thresholds},
            },
            "overrides": [],
        },
        "options": {
            "legend": {
                "calcs": list(legend_calcs),
                "displayMode": "list",
                "placement": "bottom",
                "showLegend": True,
            },
            "tooltip": {"mode": "multi", "sort": "desc"},
        },
        "targets": targets,
    }


def logs(panel_id, title, grid, desc, targets):
    return {
        "id": panel_id,
        "type": "logs",
        "title": title,
        "description": desc,
        "datasource": ds_loki(),
        "gridPos": grid,
        "options": {
            "dedupStrategy": "none",
            "enableLogDetails": True,
            "prettifyLogMessage": True,
            "showCommonLabels": False,
            "showLabels": False,
            "showTime": True,
            "sortOrder": "Descending",
            "wrapLogMessage": True,
        },
        "targets": targets,
    }


def text(panel_id, title, grid, content):
    return {
        "id": panel_id,
        "type": "text",
        "title": title,
        "description": "",
        "gridPos": grid,
        "options": {"mode": "markdown", "content": content},
    }


def painel(uid, title, tags, description, panels):
    return {
        "__inputs": [
            {
                "name": "DS_PROMETHEUS",
                "label": "Prometheus / Mimir",
                "description": "Data source Prometheus do ambiente (Mimir do Grafana Cloud).",
                "type": "datasource",
                "pluginId": "prometheus",
                "pluginName": "Prometheus",
            },
            {
                "name": "DS_LOKI",
                "label": "Loki",
                "description": "Data source Loki do ambiente.",
                "type": "datasource",
                "pluginId": "loki",
                "pluginName": "Loki",
            },
        ],
        "__requires": [
            {"type": "grafana", "id": "grafana", "name": "Grafana", "version": "11.0.0"},
            {"type": "datasource", "id": "prometheus", "name": "Prometheus", "version": "1.0.0"},
            {"type": "datasource", "id": "loki", "name": "Loki", "version": "1.0.0"},
        ],
        "annotations": {"list": []},
        "description": description,
        "editable": True,
        "fiscalYearStartMonth": 0,
        "graphTooltip": 1,
        "links": [],
        "liveNow": False,
        "panels": panels,
        "preload": False,
        "refresh": "1m",
        "schemaVersion": 39,
        "tags": tags,
        "templating": {
            "list": [
                {
                    "current": {},
                    "hide": 0,
                    "includeAll": False,
                    "label": "Ambiente",
                    "multi": False,
                    "name": "ambiente",
                    "options": [],
                    "query": "label_values(up, ambiente)",
                    "refresh": 1,
                    "regex": "",
                    "sort": 1,
                    "type": "query",
                }
            ]
        },
        "time": {"from": "now-6h", "to": "now"},
        "timepicker": {},
        "timezone": "America/Sao_Paulo",
        "title": title,
        "uid": uid,
        "version": 1,
    }


VERMELHO = [{"color": "text", "state": None, "value": None},
            {"color": "red", "state": "value", "value": 0.000001}]


# ===========================================================================
# 1) DISPONIBILIDADE
# ===========================================================================
def disponibilidade():
    p = []
    p.append(stat(1, "API acessível (scrape)", {"h": 4, "w": 4, "x": 0, "y": 0},
        "`up` do scrape em `/metrics` (vem do COLETOR, não do backend). Zero aqui "
        "significa que o coletor não consegue ler /metrics: API fora do ar, porta "
        "errada em ALLOY_BACKEND_METRICS_ADDR, ou token divergente. Em `develop` "
        "`/metrics` devolve 401 para anônimo "
        "(`backend/config/health.py:414-418`), então token errado É o cenário mais "
        "provável — e produz painel vazio com o portal perfeito para o usuário.",
        [target("A", f'max(up{{{ROTULO_AMBIENTE}, job="portal-api"}})', "up")],
        thresholds=[{"color": "red", "state": None, "value": None},
                    {"color": "green", "state": "value", "value": 1}],
        text_mode="value_and_name"))
    p.append(stat(2, "Readiness: respostas NÃO prontas", {"h": 4, "w": 5, "x": 4, "y": 0},
        "`portal_readyz_total{situacao=\"nao_pronto\"}/s` — incremented em "
        "`backend/config/views.py:116` em TODA chamada de `/readyz`, com `ok` ou "
        "`nao_pronto`. `verificar_prontidao` (`health.py:324-350`) só devolve `ok` "
        "depois de o banco ter sido verificado NESTA chamada. Zero = ninguém recebeu "
        "`nao_pronto` na janela. Lembre: o contador é POR PROCESSO e subestima "
        "(cada worker Gunicorn tem o seu registro em memória).",
        [target("A", f'sum(rate(portal_readyz_total{{{ROTULO_AMBIENTE}, situacao="nao_pronto"}}[{RI}]))', "nao_pronto/s")],
        unit="reqps", text_mode="value"))
    p.append(stat(3, "Saúde degradada (checagem falhou)", {"h": 4, "w": 5, "x": 9, "y": 0},
        "`portal_health_detail_total{situacao=\"degradado\"}` — "
        "`backend/config/views.py:142`. Substitui `portal_health_degraded_total` e "
        "`portal_dependency_checks_total` do WIP, que não existem em `develop`. "
        "ATENÇÃO: `develop` não publica métrica por dependência, então este número "
        "NÃO diz QUAL falhou. O nome está no corpo de `/health-detail` (restrito).",
        [target("A", f'sum(increase(portal_health_detail_total{{{ROTULO_AMBIENTE}, situacao="degradado"}}[$__range]))', "degradadas no período")],
        unit="short", text_mode="value"))
    p.append(stat(4, "LACUNAS DE INSTRUMENTAÇÃO (1 = falta sinal)",
        {"h": 4, "w": 5, "x": 14, "y": 0},
        "`absent()` sobre as 16 séries que `develop` não expõe — é a MESMA expressão "
        "de `PortalTelemetriaNaoInstrumentada`. Valor 1 (vermelho) significa: os "
        "painéis de taxa de erro, latência, fila e ingestão NÃO TÊM DADO. Valor "
        "ausente (cinza) significa que algum dia o backend passou a expor pelo menos "
        "uma delas. Enquanto for 1, os números deste painel são apenas 9 métricas "
        "reais — a lista completa está no painel de texto abaixo.",
        [target("A",
                "absent(\n"
                "  portal_http_requests_total\n"
                "  or portal_http_request_duration_seconds_bucket\n"
                "  or portal_celery_queue_depth\n"
                "  or portal_celery_tasks_total\n"
                "  or portal_celery_task_duration_seconds_bucket\n"
                "  or portal_job_task_idle_seconds\n"
                "  or portal_dependency_checks_total\n"
                "  or portal_dependency_check_duration_seconds_bucket\n"
                "  or portal_ingestion_executions_total\n"
                "  or portal_degraded_responses_total\n"
                "  or portal_health_check_not_configured\n"
                "  or portal_sentry_events_dropped_total\n"
                "  or portal_metrics_series_dropped_total\n"
                "  or portal_collector_disk_free_ratio\n"
                "  or portal_observability_access_denied_total\n"
                "  or portal_metrics_scrapes_total\n"
                ")", "faltando sinal")],
        thresholds=VERMELHO, text_mode="value_and_name",
        mappings=[{"type": "value", "options": {"1": {"text": "NÃO MEDIDO", "color": "red", "index": 0}}}]))

    p.append(timeseries(5, "Sondas de saúde por segundo", {"h": 8, "w": 12, "x": 0, "y": 4},
        "Substitui o painel de `portal_http_requests_total{status}` do WIP, que não "
        "existe em `develop`: não há contagem de requisição por status em lugar "
        "nenhum do backend. O que existe são as sondas dos próprios endpoints de "
        "saúde, e elas são reais (`views.py:83,97,116,218`). Um `healthz/s` que cai "
        "a zero com `up=1` significa que o monitor externo deixou de existir.",
        [target("A", f'sum(rate(portal_healthz_total{{{ROTULO_AMBIENTE}}}[{RI}]))', "healthz/s"),
         target("B", f'sum(rate(portal_livez_total{{{ROTULO_AMBIENTE}}}[{RI}]))', "livez/s"),
         target("C", f'sum(rate(portal_readyz_total{{{ROTULO_AMBIENTE}}}[{RI}]))', "readyz/s"),
         target("D", f'sum(rate(portal_metrics_total{{{ROTULO_AMBIENTE}}}[{RI}]))', "scrapes de /metrics/s")],
        unit="reqps", stack=True))
    p.append(timeseries(6, "Readiness por resultado", {"h": 8, "w": 12, "x": 12, "y": 4},
        "Separação `ok` × `nao_pronto` de `portal_readyz_total`. A separação só "
        "aparece depois que AMBOS os valores ocorreram alguma vez no processo: "
        "`_Registro.render()` (`health.py:468-477`) só emite as combinações de "
        "rótulo que já ocorreram, e não emite zero para as que faltam. "
        "Consequência a saber: uma série `nao_pronto` ausente é \"nunca deu ruim\", "
        "não \"não sei\".",
        [target("A", f'sum by (situacao) (rate(portal_readyz_total{{{ROTULO_AMBIENTE}}}[{RI}]))', "{{situacao}}")],
        unit="reqps", stack=True))
    p.append(timeseries(7, "Duração da checagem de readiness", {"h": 8, "w": 12, "x": 0, "y": 12},
        "`portal_readyz_duracao_ms` (`backend/config/views.py:117`) é a soma das "
        "durações das checagens da chamada, em ms, com "
        "`HEALTH_TIMEOUT_SEGUNDOS` = 2 s por padrão (`health.py:321`). É o ÚNICO "
        "proxy de latência de dependência que `develop` mede, e é um GAUGE: não "
        "zera a cada restart, ao contrário dos contadores. Substitui o histograma "
        "`portal_dependency_check_duration_seconds_bucket` do WIP, que não existe.",
        [target("A", f'max(portal_readyz_duracao_ms{{{ROTULO_AMBIENTE}}})', "ms")],
        unit="ms",
        thresholds=[{"color": "green", "state": None, "value": None},
                    {"color": "yellow", "state": "value", "value": 500},
                    {"color": "red", "state": "value", "value": 1800}]))
    p.append(timeseries(8, "E-mail: desfecho das tentativas", {"h": 8, "w": 12, "x": 12, "y": 12},
        "`portal_email_entrega_total{destino,situacao}` "
        "(`backend/config/email_entrega.py:184-186`). `situacao=\"sem_canal\"` é o "
        "gate de entrega P1-04: o serviço responde sucesso e a mensagem é "
        "DESCARTADA, porque `DJANGO_EMAIL_BACKEND` está num backend que não entrega "
        "a ninguém. Cardinalidade 5 destinos × 3 situações = 15 séries, fechadas por "
        "contrato. Esta série não existia no WIP.",
        [target("A", f'sum by (situacao) (rate(portal_email_entrega_total{{{ROTULO_AMBIENTE}}}[{RI}]))', "{{situacao}}/s")],
        unit="ops", stack=True))
    p.append(stat(9, "Uptime do processo", {"h": 4, "w": 6, "x": 0, "y": 20},
        "`portal_tempo_de_atividade_segundos` (`backend/config/health.py:459-461`). "
        "Único gauge de `develop` que sobrevive a restart — e é exatamente por isso "
        "que ele importa: TODOS os contadores deste painel são em memória, por "
        "worker do Gunicorn, e zeram a cada reinício. Uma queda neste número "
        "explica por que os contadores \"não sobem\".",
        [target("A", f'max(portal_tempo_de_atividade_segundos{{{ROTULO_AMBIENTE}}})', "uptime")],
        unit="s", text_mode="value"))
    p.append(stat(10, "Reinícios na última meia hora", {"h": 4, "w": 6, "x": 6, "y": 20},
        "Quantas vezes o uptime CAIU em 30 min (`resets`, não `changes`: `changes` "
        "conta QUALQUER mudança e o uptime sobe sempre, então devolveria ~20 num "
        "sistema saudável). Três quedas em 10 min já é crash loop, não deploy. É a "
        "mesma expressão de `PortalProcessoReiniciando`.",
        [target("A", f'max(resets(portal_tempo_de_atividade_segundos{{{ROTULO_AMBIENTE}}}[30m]))', "reinícios")],
        unit="short", text_mode="value",
        thresholds=[{"color": "green", "state": None, "value": None},
                    {"color": "red", "state": "value", "value": 3}]))
    p.append(text(11, "O que este painel NÃO mede (e o que fecha cada lacuna)",
                  {"h": 4, "w": 12, "x": 12, "y": 20},
                  """### Três painéis do rascunho foram removidos, não corrigidos

`develop` **não expõe** taxa de erro 5xx, latência de requisição, nem
latência por rota. Não existe `portal_http_requests_total`, nem
`portal_http_request_duration_seconds_*`, nem qualquer histograma, em lugar
nenhum do backend. Três painéis que apontavam para eles foram removidos
deste painel em vez de deixados em `No data`: painel em branco sem
explicação é falso verde com outro formato.

O que fecha cada lacuna — e por que **nada** disso é infraestrutura:

| Sinal que falta | Fecha com | Onde |
|---|---|---|
| taxa de 5xx, por `status` | `log_format` JSON em `infra/nginx/http-cache.conf` (hoje **nenhum** dos 7 arquivos de `infra/nginx/` define `log_format`) | item de nginx |
| taxa de 5xx, por `route` | `portal_http_requests_total{status,route}` com `route` de **vocabulário fechado** | item de backend |
| p50/p90/p95 de requisição | histograma no middleware — `health.py` hoje só mede as checagens de saúde | item de backend |
| ingestões por minuto | hoje só existe `RegistroExecucaoIngestao` no banco (`catalogo_noticias/models.py:288`), que é dado de produto, não de operação | item de backend |

Um rótulo `route` vindo do path resolvido **não** é aceitável: é controlado
pelo cliente e estoura cardinalidade. Ver `alerts/README.md` §3."""))
    p.append(text(12, "Como ler estes números",
                  {"h": 7, "w": 24, "x": 0, "y": 24},
                  """### `/metrics` de `develop` é um registro POR PROCESSO

`backend/config/health.py:426-485` é um registro em memória: um `Lock` e dois
dicts no próprio processo. A API roda com mais de um worker Gunicorn, e o
scrape enxerga **um** deles. Três consequências, todas material:

* **contadores subestimam** o total real — use `rate()` para tendência e
  forma, nunca para contagem;
* **contadores zeram a cada restart** e a cada troca de worker. Os únicos
  gauges fiáveis são `portal_tempo_de_atividade_segundos` e
  `portal_readyz_duracao_ms`;
* **não existe agregação entre processos**. Um alerta de razão
  (divide dois contadores subestimados por um terceiro) não é uma taxa. Por
  isso **todas** as regras deste diretório usam limiar de ocorrência
  (`> 0`), nunca percentual.

Uma consequência prática que costuma morder: a série
`portal_readyz_total{situacao="nao_pronto"}` **não existe** enquanto nada deu
errado, porque `_Registro.render()` só emite combinações de rótulo que já
ocorreram. Ausência dessa série é "nunca deu ruim" — que é o que o alerta
`PortalReadinessFalha` assume, e o que `PortalReadinessNaoSondada` existe para
descobrir quando o pressuposto é falso."""))
    return painel("portal-disponibilidade",
                  "Portal — Disponibilidade e telemetria efetiva (técnico)",
                  ["portal", "tecnico", "disponibilidade"],
                  "Portal — o que `develop` REALMENTE mede, com as lacunas declaradas. "
                  "Item P2-01. Tabela de correspondência em "
                  "infra/observability/alerts/README.md §1.",
                  p)


# ===========================================================================
# 2) FILAS E CELERY
# ===========================================================================
def filas():
    p = []
    p.append(logs(1, "Saúde das filas — registro de `saude_filas --json`",
        {"h": 10, "w": 16, "x": 0, "y": 0},
        "FONTE DA VERDADE: a saída JSON de `manage.py saude_filas --json`, indexada "
        "no Loki por `loki.source.file \"filas\"` em `infra/observability/alloy/"
        "config.alloy` (variável `ALLOY_FILAS_JSON_PATH`). Isto NÃO é uma "
        "aproximação em Grafana: é literalmente o relatório que "
        "`backend/config/filas_saude.py` produz, com os três estados e as "
        "dependências nomeadas. Campos que chegam aqui: `estado`, `verificado`, "
        "`fila`, `modo_execucao`, `profundidade`, `idade_da_mais_antiga_s`, "
        "`idade_s` (heartbeat do beat) e `estado_ciclo` (última execução da task "
        "monitorada). Sem o cron que produz o arquivo, este painel fica vazio — e "
        "vazio aqui significa \"não medido\", não \"fila vazia\".",
        [target_loki("A", '{ambiente="$ambiente", servico="portal-filas"}')]))
    p.append(stat(2, "LACUNA: profundidade de fila no Mimir", {"h": 4, "w": 8, "x": 16, "y": 0},
        "`absent(portal_celery_queue_depth or portal_celery_tasks_total or "
        "portal_celery_task_duration_seconds_bucket)`. 1 (vermelho) = as três séries "
        "do painel do WIP não existem em `develop`, e nada será perdido se alguém "
        "criá-las sem cuidado. É o mesmo一群 série listada em "
        "`PortalTelemetriaNaoInstrumentada`; aqui isolada porque é o buraco mais "
        "grande deste diretório.",
        [target("A",
                "absent(portal_celery_queue_depth or portal_celery_tasks_total or "
                "portal_celery_task_duration_seconds_bucket)", "filas não medidas")],
        thresholds=VERMELHO, text_mode="value_and_name",
        mappings=[{"type": "value", "options": {"1": {"text": "NÃO MEDIDO", "color": "red", "index": 0}}}]))
    p.append(stat(3, "Readiness (as filas podem travar o portal?)", {"h": 4, "w": 8, "x": 16, "y": 4},
        "`portal_readyz_total{situacao=\"nao_pronto\"}/s` (`views.py:116`). Uma fila "
        "acumulada com readiness `ok` é degradação, não queda — e é exatamente o "
        "estado que `saude_filas` classifica como `degradado` (exit 1).",
        [target("A", f'sum(rate(portal_readyz_total{{{ROTULO_AMBIENTE}, situacao="nao_pronto"}}[{RI}]))', "nao_pronto/s")],
        unit="reqps", text_mode="value"))
    p.append(logs(4, "Journal do systemd — worker e beat", {"h": 10, "w": 16, "x": 0, "y": 10},
        "Allowlist de units do `loki.source.journal` (`ALLOY_JOURNAL_UNITS`), com "
        "regex ancorada — valor vazio significa \"não coleta\", nunca \"coleta "
        "tudo\". Em `develop` ainda não foi escolhido entre systemd e PM2 "
        "(`infra/filas/PROVISIONAMENTO.md` §2.1), então o valor tem que bater com as "
        "units que o ambiente realmente tiver. Se este painel estiver vazio, "
        "primeiro verifique `verificar-env.sh` e os grupos `adm`/`systemd-journal`.",
        [target_loki("A", '{ambiente="$ambiente", componente="systemd"} |= "celery"')]))
    p.append(text(5, "Como ler o relatório de filas — e por que este painel não tem gráfico de profundidade",
        {"h": 10, "w": 8, "x": 16, "y": 8},
        """### O dado existe; ele só não é uma métrica

`develop` mede a saúde das filas com **três estados e três códigos de saída**
(`backend/config/management/commands/saude_filas.py:10-19`):

| estado | exit | leitura |
|---|---|---|
| `ok` | 0 | tudo verificado e sem problema |
| `degradado` | 1 | **medido** e com problema |
| `desconhecido` | 3 | **não foi possível verificar** |

O `3` é deliberadamente diferente do `0`. É a razão de `filas_saude.py` existir
(`filas_saude.py:17-22`): um `0` que não foi medido viraria `None` com
`verificado: false`, e é isso que impede o "não consegui medir" de convergir
com o "medi e está tudo bem".

**Nenhum gráfico de profundidade de fila existe neste painel, e a razão é
esta:** `develop` não tem `portal_celery_queue_depth`. Ele tem JSON em stdout.
Um painel Grafana não executa comando de gerência, e inventar um
`exportador` Prometheus seria criar um segundo mecanismo de estado de fila —
exatamente o que este lote foi instruído a não fazer.

O caminho adotado, sem duplicar nada:

1. `saude_filas --json` continua sendo a fonte da verdade;
2. o JSON é indexado no **Loki** (`loki.source.file "filas"`), e só `estado`
   vira rótulo — três valores, cardinalidade 3;
3. o **alerta** é do check externo, não de PromQL:
   `infra/filas/PROVISIONAMENTO.md` §2.3 já pede exatamente isso ("crítico se
   o processo sai ≠ 0"), e `better-stack/checks.json` traz o `cron_monitor`
   correspondente;
4. `infra/filas/PROVISIONAMENTO.md:110` já registra que a transformação
   JSON → métrica Prometheus é **provisionamento, não código**.

### O cron que falta

```bash
*/5 * * * * cd /home/apps/portal-<env> && \\
  .venv/bin/python manage.py saude_filas --json \\
  >> /var/lib/portal-noticias/saude_filas.jsonl
```

Sem ele, o arquivo não existe, `verificar-env.sh` reprova a instalação, e o
painel fica vazio. Vazio é "não medido" — nunca "fila vazia".

### Um buraco conhecido e nomeado

`filas_saude.py` **não** mede se o beat está agendando certo: prova que uma
mensagem do `beat_schedule` chegou a um worker (`filas_saude.py:30-35`). Um
beat com as outras entradas quebradas continua tocando o heartbeat. O sinal
que fecha esse buraco é o `ultimo_ciclo` da task monitorada
(`FILAS_TAREFA_MONITORADA`, `settings.py:799`), que chega aqui como
`estado_ciclo`."""))
    return painel("portal-filas-celery",
                  "Portal — Filas e Celery (técnico, canal JSON)",
                  ["portal", "tecnico", "celery"],
                  "Saúde das filas pelo relatório real de `saude_filas --json` (Loki), "
                  "não por métrica inventada. Item P2-01.",
                  p)


# ===========================================================================
# 3) INGESTÃO
# ===========================================================================
def ingestao():
    p = []
    p.append(text(1, "Este painel NÃO tem gráfico de ingestões — e o motivo está escrito aqui",
        {"h": 6, "w": 24, "x": 0, "y": 0},
        """### `develop` não tem nenhuma métrica de ingestão

O painel do rascunho tinha três séries: `portal_celery_tasks_total{task=…}`,
`portal_celery_task_duration_seconds_bucket{task=…}` e
`portal_ingestion_executions_total`. **Nenhuma das três existe.** A terceira é
o caso mais instructive: o próprio WIP registrava que ela era *declarada em
`config/metrics.py` e nunca incrementada* — ou seja, era um painel vazio por
construção, desde antes de qualquer deploy.

A task existe e está agendada: `catalogo_noticias.tasks.ingerir_noticias`
(`settings.py:875`, `catalogo_noticias/tasks.py:65`), a cada 15 min por padrão
(`settings.py:811-812`). Ela também grava estado durável, que
`saude_filas` lê como `ultimo_ciclo` e que aparece no painel
`portal-filas-celery`.

Portanto, o que este painel mostra é o **resultado** da ingestão (a última
execução, pela via oficial) e os **sinais de falha** que existem de fato. O
que ele não mostra, e por quê, está nos dois painéis de texto abaixo."""))
    p.append(logs(2, "Último ciclo da ingestão (via `saude_filas`, fonte oficial)",
        {"h": 8, "w": 12, "x": 0, "y": 6},
        "Registro JSON de `manage.py saude_filas --json` — campo `ultimo_ciclo`, "
        "que é o `FILAS_TAREFA_MONITORADA` (`catalogo_noticias.tasks."
        "ingerir_noticias`). Este é o sinal de que o agendamento está "
        "acontecendo, e é o mesmo que `saude_filas` usa para classificar "
        "`degradado` (exit 1) — não uma reconstrução dentro do Grafana.",
        [target_loki("A", '{ambiente="$ambiente", servico="portal-filas"} |= "ultimo_ciclo"')]))
    p.append(stat(3, "LACUNAS: séries de ingestão que não existem",
        {"h": 8, "w": 6, "x": 12, "y": 6},
        "1 (vermelho) = `develop` não expõe nenhuma métrica de ingestão nem de "
        "Celery. Enquanto for 1, **este painel não tem como dizer que a ingestão "
        "parou**; o que ele diz é o que o `saude_filas` diz, e o alerta do cron "
        "externo é quem avisa.",
        [target("A",
                "absent(portal_ingestion_executions_total or portal_celery_tasks_total "
                "or portal_celery_task_duration_seconds_bucket or "
                "portal_celery_queue_depth)", "ingestão não medida")],
        thresholds=VERMELHO, text_mode="value_and_name",
        mappings=[{"type": "value", "options": {"1": {"text": "NÃO MEDIDO", "color": "red", "index": 0}}}]))
    p.append(stat(4, "Readiness", {"h": 4, "w": 6, "x": 18, "y": 6},
        "`portal_readyz_total{situacao=\"nao_pronto\"}/s`. A ingestão escreve no "
        "banco; banco fora do ar significa que ela falha em silêncio ou estoura "
        "retry.",
        [target("A", f'sum(rate(portal_readyz_total{{{ROTULO_AMBIENTE}, situacao="nao_pronto"}}[{RI}]))', "nao_pronto/s")],
        unit="reqps", text_mode="value"))
    p.append(timeseries(5, "Checagem de saúde degradada", {"h": 8, "w": 12, "x": 0, "y": 14},
        "`portal_health_detail_total{situacao=\"degradado\"}` (`views.py:142`). "
        "Broker fora do ar (Redis) é exatamente a condição que faz a ingestão "
        "acumular em fila sem gerar erro. Lembre: `develop` não nomeia a "
        "dependência nesta métrica — o nome está no corpo de `/health-detail`.",
        [target("A", f'sum by (ambiente) (rate(portal_health_detail_total{{{ROTULO_AMBIENTE}, situacao="degradado"}}[{RI}]))', "degradado/s")],
        unit="ops"))
    p.append(timeseries(6, "E-mail: a newsletter sai?", {"h": 8, "w": 12, "x": 12, "y": 14},
        "A ingestão de notícias e o envio da newsletter são caminhos separados, e o "
        "da newsletter é o que tem gate de entrega. "
        "`portal_email_entrega_total{destino=\"newsletter\"}` "
        "(`email_entrega.py:184-186`) conta `entregue` / `sem_canal` / `falha`. "
        "Um acúmulo de `sem_canal` aqui significa que o produto \"enviou\" a "
        "newsletter e ninguém recebeu — o alerta "
        "`PortalEmailNaoEntregue` existe exatamente para isso.",
        [target("A", f'sum by (situacao) (rate(portal_email_entrega_total{{{ROTULO_AMBIENTE}, destino="newsletter"}}[{RI}]))', "{{situacao}}/s")],
        unit="ops", stack=True))
    p.append(text(7, "Buracos conhecidos deste painel, escritos aqui em vez de escondidos",
        {"h": 7, "w": 24, "x": 0, "y": 22},
        """### O que este painel não mostra, e o que fecha cada item

| Sinal que falta | Fecha com | Por que não é observabilidade |
|---|---|---|
| ingestões por minuto | métrica em `catalogo_noticias/tasks.py` (ou `log_format` JSON na borda) | é código de aplicação, não de infraestrutura |
| itens ingeridos por execução | `RegistroExecucaoIngestao` já existe no banco (`catalogo_noticias/models.py:288`) | é dado de **produto**, não de operação; Goes para o dashboard de analytics, não para a malha técnica |
| fontes RSS novas / com falha | idem, mais a credencial da fonte | credencial de terceiro não é dado técnico |
| duração por fonte RSS | `config/health.py` mede a *checagem* de dependência, não a latência da fonte | o módulo de ingestão registra resultado, não tempo por fonte |
| backlog da fila de ingestão | `saude_filas --json` → `dependencias.broker.profundidade` | está no painel `portal-filas-celery`, pelo canal JSON oficial |

### Por que a ingestão é difícil de observar, e o que já está feito

`ingerir_noticias` tem `retry_backoff_max=60`, `retry_jitter=True` e
`max_retatives=MAX_TENTATIVAS` (`catalogo_noticias/tasks.py:61-64`): o efeito
é que uma falha de fonte RSS se manifesta como **atraso**, não como erro
visível. É por isso que o sinal de efeito (`ultimo_ciclo` no `saude_filas`) é
mais honesto do que um contador de erro: ele mede a consequência, não a
tentativa."""))
    return painel("portal-ingestao",
                  "Portal — Ingestão de notícias (técnico, canal JSON)",
                  ["portal", "tecnico", "ingestao"],
                  "O que dá para medir de ingestão em `develop` sem inventar métrica. "
                  "Item P2-01.",
                  p)


# ===========================================================================
# 4) SAÚDE DE DEPENDÊNCIAS
# ===========================================================================
def saude():
    p = []
    p.append(timeseries(1, "Sondas de saúde por resultado", {"h": 8, "w": 12, "x": 0, "y": 0},
        "`portal_healthz_total`, `portal_livez_total`, `portal_readyz_total` e "
        "`portal_health_detail_total` separados por `situacao`. São as quatro "
        "sondas reais de `develop` (`views.py:83,97,116,142`). "
        "`degradado` em `health_detail` é o único sinal de **dependência que "
        "falhou** que existe; substitui `portal_dependency_checks_total{dependency,…}` "
        "do WIP, que não existe. Consequência: este gráfico **não nomeia** a "
        "dependência — o nome está no corpo de `/health-detail`.",
        [target("A", f'sum by (situacao) (rate(portal_readyz_total{{{ROTULO_AMBIENTE}}}[{RI}]))', "readyz {{situacao}}/s"),
         target("B", f'sum by (situacao) (rate(portal_health_detail_total{{{ROTULO_AMBIENTE}}}[{RI}]))', "health-detail {{situacao}}/s")],
        unit="ops", stack=True))
    p.append(timeseries(2, "Duração da checagem (proxy de latência de dependência)",
        {"h": 8, "w": 12, "x": 12, "y": 0},
        "`portal_readyz_duracao_ms` (`views.py:117`) — soma das durações das "
        "checagens da chamada. É GAUGE (sobrevive a restart) e é o único proxy de "
        "latência de dependência de `develop`. `HEALTH_TIMEOUT_SEGUNDOS` = 2 s por "
        "padrão (`health.py:321`), então acima de ~1900 ms alguma checagem está no "
        "limite. Substitui `portal_dependency_check_duration_seconds_bucket` do WIP, "
        "que não existe.",
        [target("A", f'max(portal_readyz_duracao_ms{{{ROTULO_AMBIENTE}}})', "ms")],
        unit="ms",
        thresholds=[{"color": "green", "state": None, "value": None},
                    {"color": "yellow", "state": "value", "value": 500},
                    {"color": "red", "state": "value", "value": 1900}]))
    p.append(stat(3, "Configuração insegura ativa", {"h": 4, "w": 6, "x": 0, "y": 8},
        "`portal_config_insegura_total{item}` (`views.py:160,183`). Alerta de "
        "PRESENÇA, não de taxa: `develop` não expõe contador por item. "
        "`media_root` = `MEDIA_ROOT` dentro do que o servidor serve (documento de "
        "credenciamento por URL). `email_backend` = o canal de e-mail não "
        "entrega. Ambos ficam em `avisos` no `/health-detail` e **não** derrubam o "
        "readiness, por decisão de projeto (`views.py:150-154`).",
        [target("A", f'max by (item) (portal_config_insegura_total{{{ROTULO_AMBIENTE}}})', "{{item}}")],
        text_mode="value_and_name",
        thresholds=[{"color": "green", "state": None, "value": None},
                    {"color": "red", "state": "value", "value": 0.5}]))
    p.append(stat(4, "Acessos negados ao endpoint privado", {"h": 4, "w": 6, "x": 6, "y": 8},
        "`portal_acesso_negado_total{recurso}` (`views.py:138,215`) — substitui "
        "`portal_observability_access_denied_total` do WIP, que não existe. "
        "`metrics` alto e inesperado é o coletor com token divergente (e então a "
        "telemetria do ambiente está cega). `metrics` alto vindo de fora é "
        "sondagem — e, ao contrário do que o rascunho afirmava, `develop` **não** "
        "tem bloqueio de borda para `/metrics` em `infra/nginx/portal-*.conf`: a "
        "única barreira é a da aplicação.",
        [target("A", f'sum by (recurso) (rate(portal_acesso_negado_total{{{ROTULO_AMBIENTE}}}[{RI}]))', "{{recurso}}/s")],
        unit="ops", text_mode="value_and_name",
        thresholds=[{"color": "green", "state": None, "value": None},
                    {"color": "red", "state": "value", "value": 0.1}]))
    p.append(stat(5, "Séries `portal_*` neste ambiente", {"h": 4, "w": 6, "x": 12, "y": 8},
        "**A medição contínua do MAJOR-2.** `develop` não tem teto de séries em "
        "código (`health.py:438-455` — só um `Lock` e dois dicts), então a "
        "cardinalidade é limitada por design mas **não é garantida por nada**. "
        "Referência medida: **33 séries** no pior caso (com um valor de `tipo` em "
        "`portal_email_falha_provedor_total`), 28 sem essa métrica, 53 com cinco "
        "classes de exceção. A regra `PortalCardinalidadeAcimaDoOrcamento` dispara "
        "acima de 200. Substitui `portal_metrics_series_dropped_total` do WIP, que "
        "contava descarte de um teto que `develop` não tem.",
        [target("A", f'sum(count by (ambiente, __name__) ({{__name__=~"portal_.*", ambiente=~"{VALOR_AMBIENTE}"}}))', "séries")],
        text_mode="value",
        thresholds=[{"color": "green", "state": None, "value": None},
                    {"color": "yellow", "state": "value", "value": 60},
                    {"color": "red", "state": "value", "value": 200}]))
    p.append(stat(6, "Falha do provedor de e-mail", {"h": 4, "w": 6, "x": 18, "y": 8},
        "`portal_email_falha_provedor_total` (`email_entrega.py:210-212`). Aqui o "
        "rótulo `tipo` é aggregating de fora: a regra agrupa por `ambiente` e o "
        "detalhe fica no log. `tipo` é o **único rótulo de valor livre** de todo o "
        "registro de `develop` (`tipo=type(exc).__name__`), e é o ponto a vigiar no "
        "painel 5.",
        [target("A", f'sum(rate(portal_email_falha_provedor_total{{{ROTULO_AMBIENTE}}}[{RI}]))', "falhas/s")],
        unit="ops", text_mode="value",
        thresholds=[{"color": "green", "state": None, "value": None},
                    {"color": "red", "state": "value", "value": 0.000001}]))
    p.append(timeseries(7, "Desfecho das entregas de e-mail", {"h": 8, "w": 12, "x": 0, "y": 12},
        "`portal_email_entrega_total{destino,situacao}`. `sem_canal` é o gate "
        "P1-04: o serviço responde sucesso e a mensagem é descartada porque "
        "`DJANGO_EMAIL_BACKEND` está num backend que não entrega a ninguém "
        "(`email_entrega.py:198-201`). É o sintoma de \"verde e inútil\" mais "
        "perigoso do produto, e é o único que tem regra "
        "(`PortalEmailNaoEntregue`).",
        [target("A", f'sum by (destino, situacao) (rate(portal_email_entrega_total{{{ROTULO_AMBIENTE}}}[{RI}]))', "{{destino}}/{{situacao}}")],
        unit="ops", stack=True))
    p.append(timeseries(8, "Liveness e métricas por segundo", {"h": 8, "w": 12, "x": 12, "y": 12},
        "`portal_livez_total` e `portal_metrics_total` (`views.py:97,218`). "
        "Substitui `portal_metrics_scrapes_total` do WIP por `portal_metrics_total`, "
        "que é o nome real e **não tem rótulo** (`_registrar` não é chamada; é um "
        "`incrementar` sem rótulo em `views.py:218`). `livez/s` caindo a zero com "
        "`up=1` significa que o check externo deixou de existir.",
        [target("A", f'sum(rate(portal_livez_total{{{ROTULO_AMBIENTE}}}[{RI}]))', "livez/s"),
         target("B", f'sum(rate(portal_metrics_total{{{ROTULO_AMBIENTE}}}[{RI}]))', "scrapes/s"),
         target("C", f'max(resets(portal_tempo_de_atividade_segundos{{{ROTULO_AMBIENTE}}}[30m]))', "reinícios/30m")],
        unit="ops"))
    p.append(text(9, "Dependências: o que existe, o que não existe, e quem mede",
        {"h": 7, "w": 24, "x": 0, "y": 20},
        """### As checagens reais de `develop`

`backend/config/health.py:63-65` define exatamente três nomes de checagem, e o
comportamento de cada um é diferente:

| check | obrigatório | o que quebra quando falha | como se observa |
|---|---|---|---|
| `banco` | **sim** | `/readyz` = 503; nada novo é salvo | `portal_readyz_total{situacao="nao_pronto"}` |
| `cache` | não | toda visita vai ao Postgres | `nao_verificadas` no corpo de `/readyz`, ou a degradação em `portal_health_detail_total` |
| `broker` | não | ingestão e jobs param | idem |

Não existe `celery`, não existe `celery_beat`, não existe `collector_disk` —
os três aparecem no painel do WIP e nenhum é checagem de `develop`. A saúde de
Celery e de filas é medida por outro caminho, já existente e testado:
`backend/config/filas_saude.py`, exposto por `manage.py saude_filas --json`
(ver painel `portal-filas-celery`).

### O caso `not_configured`, que é o ponto dangerous deste painel

`Relatorio.nao_verificadas` (`health.py:302-309`) existe **precisamente** para
que \"não verificado\" não se pareça com \"verificado e ok\": `checar_cache`
devolve `None` para `locmem` (`health.py:206-217`) e `checar_broker` devolve
`None` para `memory://` (`health.py:242-256`) — em vez de devolver um `ok`
falso. Isso é certo, e tem um preço: **essa lista é invisível para o
Prometheus.** `develop` não expõe
`portal_health_check_not_configured` (que o WIP propunha), então um ambiente
com Postgres verificado e broker nunca verificado é indistinguível, no alerta,
de um ambiente totalmente verificado.

A correção aplicada aqui **não afrouxa a regra**: em vez de inventar a métrica,
o painel tem um piso — `PortalReadinessNaoSondada` dispara quando
`/readyz` não foi sondado no ambiente, e o texto abaixo diz o que continua
sendo cego. Um painel que dissesse \"broker: ok\" sem medir seria o oposto
deste."""))
    return painel("portal-saude-dependencias",
                  "Portal — Saúde de dependências (técnico, só o que develop mede)",
                  ["portal", "tecnico", "saude"],
                  "Dependências de `develop` com a lacuna `not_configured` nomeada. "
                  "Item P2-01.",
                  p)


def main():
    destino = Path(sys.argv[1] if len(sys.argv) > 1 else
                   "infra/observability/grafana/dashboards")
    destino.mkdir(parents=True, exist_ok=True)
    for nome, fn in (("portal-disponibilidade.json", disponibilidade),
                     ("portal-filas-celery.json", filas),
                     ("portal-ingestao.json", ingestao),
                     ("portal-saude-dependencias.json", saude)):
        d = fn()
        caminho = destino / nome
        caminho.write_text(json.dumps(d, ensure_ascii=False, indent=2) + "\n",
                           encoding="utf-8")
        n_painel = sum(1 for x in d["panels"] if x["type"] != "text")
        print(f"OK {caminho}  uid={d['uid']}  paineis={len(d['panels'])}  com dado={n_painel}")


if __name__ == "__main__":
    main()
