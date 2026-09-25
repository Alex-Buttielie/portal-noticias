<!--
CONTRACT: implementation-history
DONO: executor (cria e adiciona entradas) / tester, remediator, historian (adicionam entradas)
QUANDO É CRIADO: junto com a primeira ação do executor sobre o implementation-contract.md.
PARA ONDE VAI A INSTÂNCIA: agentic-framework/state/run-20260925-1020-observabilidade/
NATUREZA: append-only durante a execução — cada entrada é uma iteração, nunca se edita uma entrada anterior.
-->

# Implementation History — 20260925-1020-observabilidade

## Iteração 1 — Bloco A (backend) — 2026-09-25 — executor (subagente delegado)

Escopo desta iteração: **somente o backend** (`backend/config`, `backend/metricas`).
Frontend, infra, CI/CD e documentação não foram tocados — ver "Fora do escopo".

### Ponto de partida

O commit `672ffba` ("wip(observabilidade): baseline de telemetria do backend")
entregou `config/observability.py`, `config/health.py`, `config/metrics.py` e
as mudanças em `config/middleware.py`/`config/settings.py` **sem nenhum teste**.
A revisão encontrou defeitos reais (não cosméticos) — a lista abaixo é o
inventário do que foi corrigido, e ela é a razão de os testes existirem.

### Bugs reais encontrados no WIP recebido e corrigidos

1. **`render_prometheus` levantava `ValueError` em qualquer histograma**
   (`config/metrics.py`). O branch de histograma montava os rótulos de bucket
   com `dict(labels)` e passava o dict para um renderer que esperava tupla de
   pares: iterar um dict devolve as CHAVES, e o rótulo de 2 letras `le`
   desempacava silenciosamente como par (`l="e"`). Na prática, o primeiro
   `/metrics` com uma observação de duração quebrava com 500. Corrigido com
   `_render_labels` normalizando qualquer iterable de pares.
2. **Nomes de worker do Celely serializados como dict inteiro**
   (`config/health.py`). `inspect().ping()` devolve uma **lista** de dicts
   `{nome: {"ok": "pong"}}`; o código iterava a lista e fazia
   `str(name)[:120]`, produzindo `"{'celery@host': {'ok': 'pong'}}"` — contagem
   certa, dado errado e **nome de host** no payload. Agora só a contagem sai.
3. **Cardinalidade sem limite no registro de métricas.** `MetricsRegistry`
   guardava um counter por combinação de labels para sempre, e o middleware
   rotulava a rota com `request.path` quando não havia `resolver_match`: cada
   404 de scanner criava uma série nova (OOM progressivo e `instance` inútil no
   Grafana). Corrigido em duas camadas: `ROUTE_UNMATCHED` no middleware e teto
   `MAX_SERIES` (5 000) com contagem de descarte visível em
   `portal_metrics_series_dropped_total`.
4. **`X-Environment` mentia em produção.** `config/observability.py` derivava
   ambiente/release **só do ambiente**, enquanto `config/settings.py` (que o
   middleware e o Sentry usam) cai em `"production"` quando `DEBUG=False`. Sem
   `SENTRY_ENVIRONMENT`/`DJANGO_ENVIRONMENT`, o header dizia `development` em
   produção — o oposto do critério 9. Agora `release()/environment()/service()`
   leem o setting do Django quando ele está configurado, com o valor do
   ambiente como fallback (o módulo continua importável sem Django pronto).
5. **`record.args` como dict quebrava o log.** `logger.info("%(k)s", {...})`
   guarda um **dict** em `record.args` (o `logging` desembrulha o dict); o
   formatter fazia `tuple(redact_payload(a) for a in args)`, iterando as CHAVES e
   produzindo `TypeError` no `msg % args` na saída. Corrigido com tratamento
   explícito de `dict`.
6. **Header injection em `X-Release`/`X-Environment`.** O saneamento removia
   caracteres de controle exceto `\n`/`\r` (necessários em log), e esses mesmos
   valores vão para header. Um `GIT_SHA` mal configurado viraria um segundo
   header. Agora identidade usa uma regex sem nenhum caractere de controle/espaço.
7. **404 legítimo viraria 500.** O `process_exception` (novo, ver abaixo)
   intercepta exceções **antes** da conversão do Django; sem guarda explícita,
   o `Http404` levantado por `comunidade/views.py:256` e
   `credenciamento/views.py:69,77` seria convertido em 500. Há teste de
   regressão que falha se a guarda for removida.
8. **`check_celery` travava a thread de requisição por ~6 s com o broker
   fora do ar** (retries do kombu no `inspect().ping()`). Agora há um portão
   `ensure_connection(max_retries=0, connect_timeout=...)` (~20 ms medido) antes
   do ping, e o estado é `degraded` (o portal serve tráfego sem worker), não
   `error`.
9. **Redação por sub-string** redigia campos inocentes: `description` contém
   "ip", `clip` contém "ip", `principal` contém "ip". Agora a comparação é por
   token, com compostos de IP explícitos; e foram adicionados `senha`, `chave`,
   `segredo`, `cpf`, `cnpj`, `sessionid`, `authorization` e JWT sem rótulo, que
   vazavam em texto livre (`cpf=...` num log não era redigido).
10. **Campos de `extra=` e do evento Sentry saíam crus.** O
    `python-json-logger` copia qualquer atributo do `LogRecord` para o JSON;
    o redactor só cobria `msg`/`args`. Agora `add_fields` redige o registro
    montado (e `redact_payload` preserva `datetime`/`Decimal` em vez de
    degenerar tudo para `[datetime]`).
11. **Rótulo de rota corrompido** por `safe_path`: um path como `api:feed/x`
    era remontado como URL. `safe_path` só trata como URL absoluta o que é
    http(s).

### O que foi implementado (não existia no baseline)

- **Endpoints** em `config/urls.py` + `config/observability_views.py`:
  - `/livez` — liveness do processo, público, payload mínimo `{"status":"alive"}`,
    **sem tocar banco/cache/Celery** (teste com `connection.cursor` levantando
    `OperationalError` prova que continua 200).
  - `/readyz` — banco + migrations, público, corpo `{"status","ready"}` e nada
    mais; 503 sem `str(exc)`, traceback, nome de check ou host (teste
    explicitamente procurando cada um desses vazamentos).
  - `/health-detail` — privado (loopback **ou** proxy declarado **ou** staff/admin
    **ou** `Authorization: Bearer $OBSERVABILITY_HEALTH_TOKEN`). Detalha Redis,
    worker Celery, beat, filas e filesystem do collector. Negação responde
    **404** (idêntico a rota inexistente) para não confirmar a existência do
    diagnóstico.
  - `/metrics` — exposição Prometheus `text/plain; version=0.0.4`, restrita a
    loopback/proxy declarado **ou** `OBSERVABILITY_METRICS_TOKEN` (staff **não**
    passa: é superfície de leitura técnica, conforme instruído).
- **Gating que funciona atrás de Nginx/Docker**: `X-Forwarded-For` **não** é
  usado para autorizar (é controlado pelo cliente final); o default é
  loopback real, e redes de proxy precisam ser declaradas em
  `OBSERVABILITY_TRUSTED_PROXY_NETWORKS`. O teste prova que um IP privado de
  container **não** passa sem declaração — porque atrás de Docker o tráfego
  público também chega com IP privado.
- **`process_exception` no middleware**: o 500 agora sai com `X-Request-ID`,
  `X-Service`, `X-Environment`, `X-Release` e `X-Operational-State`, com o
  `request_id` no corpo (código de suporte para o usuário). Como devolver
  resposta aqui suplanta `response_for_exception`, o sinal
  `got_request_exception` (Sentry) e o log `django.request` ERROR são
  republicados explicitamente — sem eles a troca seria header por erro
  invisível.
- **Estado degradado visível**: `health.degraded_state()` memoizado por processo
  (15 s) é consultado pelo middleware; quando Redis/Celery/beat/disco estão fora,
  a resposta ganha `X-Operational-State: degraded` e a métrica
  `portal_degraded_responses_total`. O primeiro estado é `unknown` e **não**
  marca degradação (todo deploy nasceria degradado).
- **Correlação de task Celery** (`config/celery.py`): sinais `task_prerun`/
  `task_postrun` alimentam o `ContextVar` de `task_id` (por thread) e registram
  `portal_celery_tasks_total`/`portal_celery_task_duration_seconds`. Antes,
  `current_task_id()` era sempre `-` em qualquer log de task.
- **Task de expurgo ausente** — `metricas/tasks.py::expurar_analytics` (o beat
  agendava um nome que ninguém registrava: falha silenciosa):
  retenção de `ANALYTICS_RETENTION_DAYS` (365), expurgo de **eventos brutos**
  (`EventoSite`, `InteracaoNoticia`, `EventoBusca`) e **agregados** (invalida o
  snapshot em cache `feed:autocomplete:v2:*`, único agregado materializado
  daqui), idempotente, em lotes (`ANALYTICS_EXPURGO_LOTE`, default 1000, com
  `MAX_LOTES` anti-laço), log técnico auditável (corte, retenção, contagem por
  modelo, lotes, duração) **sem** query buscada, path, sessão, usuário ou
  e-mail, e métricas do próprio expurgo.
- **Guarda de fail-fast no CI**: `config/tests/test_celery_beat_schedule.py`
  prova que **toda** entrada de `CELERY_BEAT_SCHEDULE` aponta para uma task
  registrada no app Celery (parâmetro + varredura em tempo de teste).
- **Descarte de evento Sentry contável**: `portal_sentry_events_dropped_total`
  — sem ele, um `SENTRY_TECHNICAL_CONSENT_DEFAULT` mal configurado seria
  indistinguível de "não houve erro" (falso verde dentro do falso verde).

### Arquivos tocados

Modificados:

```text
backend/config/celery.py
backend/config/health.py
backend/config/metrics.py
backend/config/middleware.py
backend/config/observability.py
backend/config/settings.py
backend/config/settings_test.py
backend/config/urls.py
```

Novos:

```text
backend/config/observability_views.py
backend/config/tests/test_celery_beat_schedule.py
backend/config/tests/test_celery_correlacao.py
backend/config/tests/test_health_checks.py
backend/config/tests/test_health_endpoints.py
backend/config/tests/test_metrics_registry.py
backend/config/tests/test_observability_contexto.py
backend/config/tests/test_observability_middleware.py
backend/config/tests/test_observability_redaction.py
backend/metricas/tasks.py
backend/metricas/tests/test_tasks_expurgo.py
agentic-framework/state/run-20260925-1020-observabilidade/implementation-history.md
```

Settings novas (todas por variável de ambiente, nenhuma com valor inventado):
`OBSERVABILITY_TRUSTED_PROXY_NETWORKS`, `OBSERVABILITY_DEGRADED_PROBE_INTERVAL_SECONDS`
(15), `OBSERVABILITY_BEAT_HEARTBEAT_FILE` (vazio), `OBSERVABILITY_BEAT_MAX_AGE_SECONDS`
(900), `OBSERVABILITY_QUEUE_DEPTH_WARN` (1000), `OBSERVABILITY_COLLECTOR_PATH`
(vazio = `BASE_DIR`), `OBSERVABILITY_DISK_MIN_FREE_RATIO` (0.05),
`ANALYTICS_EXPURGO_LOTE` (1000). `config/settings_test.py` recebeu
`OBSERVABILITY_CHECK_CELERY = False` e
`OBSERVABILITY_DEGRADED_PROBE_INTERVAL_SECONDS = 0.0` (a suíte não sobe worker
nem broker; sem isso todo teste que olha `X-Operational-State` dependeria de um
Redis local).

Nenhuma dependência nova: só `requirements-lock.txt` existente
(`sentry-sdk`, `python-json-logger`, `celery`, `django-redis`).

### Decisões e trade-offs

- **404 em vez de 403 na negação dos endpoints privados.** Um 403 confirma a
  existência do diagnóstico, que é justamente o que não pode vazar. O corpo é
  idêntico ao de uma rota inexistente. Trade-off: um monitor externo não
  distingue "não existe" de "sem permissão" — aceito, porque o próximo passo
  dele é o mesmo (pedir token ao operador).
- **Não confiar em IP privado.** "Qualquer RFC1918 é confiável" publicaria o
  diagnóstico para a internet atrás de Docker/Nginx (o `REMOTE_ADDR` do tráfego
  público é o IP privado do gateway). Custo: em Docker o operador precisa
  declarar `OBSERVABILITY_TRUSTED_PROXY_NETWORKS` ou usar token.
- **Probe de degradação memoizado por processo (15 s).** Sem memoização, cada
  requisição pagaria um `celery inspect`. Custo aceito: até 15 s de atraso para
  o header refletir uma queda nova. O `/health-detail` (chamado por humano ou
  monitor) sempre força checagem completa.
- **`/readyz` só checa dependências obrigatórias.** Redis/Celery são degradação,
  não indisponibilidade: tirar o portal do ar porque o cache caiu seria
  transformar otimização em dependência dura. A degradação continua visível no
  header e na métrica.
- **Beat sem introspection inventada.** Não existe forma confiável de provar
  "o beat está vivo" pelo broker. Sem `OBSERVABILITY_BEAT_HEARTBEAT_FILE`, o
  check é `not_configured` (visível, **nunca** verde por omissão). Escrever o
  heartbeat é pendência do bloco de infra (systemd/Alloy).
- **Profundidade de fila como `degraded`, não `ok`, quando ilegível.** Declarar
  passivamente falha tanto para fila ainda não criada quanto para broker sem
  resposta; afirmar "ok" seria inventar saúde.
- **`/metrics` sem bypass de staff.** Instrução explícita do bloco; o coletor
  scrapeia com token ou de loopback. Sessão Django no `curl` do Prometheus seria
  outra superfície.
- **Nenhum nome de host/worker em payload HTTP**, nem no privado. A topologia da
  VPS não é necessária para decidir ação (o operador tem `celery inspect` e o
  Grafana), e é o tipo de dado que vaza por descuido quando alguém copia a
  resposta para um ticket.
- **`config/views.py::healthz` legado ficou intacto.** Ele ainda devolve
  `str(exc)` no corpo público (`{"status": "erro", "detalhe": ...}`) e é
  justamente o endpoint apontado pelo `HEALTHCHECK` do Docker, pelo PM2/Nginx e
  pelo `subir-localhost.sh`. Alterar o contrato ali é decisão do bloco de infra
  (migrar as checagens para `/livez` + `/readyz` e remover `detalhe`), não deste
  bloco — ver "Riscos".
- **Consentimento técnico continua fail-closed.** `SENTRY_TECHNICAL_CONSENT_DEFAULT`
  false (default) significa que **todo** evento Sentry do backend é descartado
  (a menos que a requisição traga `X-Technical-Consent: 1`). É o comportamento
  exigido pelo contrato ("ausência de consentimento não pode gerar envio"), mas
  é um risco operacional real: quem ativar `SENTRY_DSN` sem ligar o default
  terá um Sentry silenciosamente vazio. Mitigação implementada: o descarte é
  contável em `/metrics`.

### Testes: comandos e saída real

Ambiente: `backend/.venv/bin/python` (Python 3.14.4), `DJANGO_SETTINGS_MODULE=config.settings_test`,
`DJANGO_DB_ENGINE=sqlite3` (o `.env` local não define engine; o sandbox usa
SQLite via `DJANGO_DB_ENGINE`), `DJANGO_SECRET_KEY` de teste via `settings_test.py`.

```console
$ backend/.venv/bin/python manage.py check
System check identified no issues (0 silenced).
```

```console
$ cd backend && .venv/bin/python -m pytest config metricas -q
186 passed, 42 warnings in 7.02s
```

```console
$ cd backend && .venv/bin/python -m pytest -q
7 failed, 629 passed, 230 warnings in 61.82s (0:01:01)
```

As 7 falhas são **externas** (WIP de outra run), em arquivo não rastreado do
outro agente:

```text
FAILED catalogo_noticias/tests/test_command_agendar_ingestao.py::test_primeira_rodada_imediata_chama_executar_ingestao_uma_vez
FAILED catalogo_noticias/tests/test_command_agendar_ingestao.py::test_falha_na_primeira_rodada_nao_mata_o_loop
FAILED catalogo_noticias/tests/test_command_agendar_ingestao.py::test_intervalo_configurado_respeitado_segunda_rodada_apos_o_intervalo
FAILED catalogo_noticias/tests/test_command_agendar_ingestao.py::test_intervalo_configurado_chega_ao_mecanismo_de_espera
FAILED catalogo_noticias/tests/test_command_agendar_ingestao.py::test_intervalo_default_vem_da_setting_de_minutos
FAILED catalogo_noticias/tests/test_command_agendar_ingestao.py::test_sigterm_durante_o_loop_para_de_agendar_graciosamente
FAILED catalogo_noticias/tests/test_command_agendar_ingestao.py::test_sigint_durante_o_loop_para_de_agendar_graciosamente
RuntimeError: Database access not allowed, use the "django_db" mark, or the "db" or "transactional_db" fixtures to enable it.
```

Prova de que é externo (nenhum arquivo meu participa dessas execuções):

```console
$ cd backend && .venv/bin/python -m pytest catalogo_noticias -q
7 failed, 156 passed, 38 warnings in 11.40s
$ cd backend && .venv/bin/python -m pytest -q --ignore=catalogo_noticias/tests/test_command_agendar_ingestao.py
620 passed, 230 warnings in 63.14s (0:01:03)
```

**Owner: run `20260924-2136-ingestao-noticias`** (arquivo `?? catalogo_noticias/tests/test_command_agendar_ingestao.py`
+ `?? catalogo_noticias/management/commands/agendar_ingestao.py`, ainda em
edição durante esta execução). Não foi "con-certado" revertendo nada do outro
agente.

Cobertura (mesmo comando do CI):

```console
$ cd backend && .venv/bin/python -m pytest -q --cov=config --cov=metricas --cov-report=term --cov-fail-under=80
config/celery.py                       38    3   92%
config/health.py                      195    8   96%
config/metrics.py                     171   14   92%
config/middleware.py                  114    5   96%
config/observability.py               212   27   87%
config/observability_views.py          99    7   93%
config/urls.py                          5    0  100%
metricas/tasks.py                      50    2   96%
TOTAL                               3270  291   91%
Required test coverage of 80% reached. Total coverage: 91.10%
```

(Sujeito às mesmas 7 falhas externas; o gate de 80% passa.)

O que os 186 testes de `config` + `metricas` cobrem, por requisito do bloco:
semântica `/livez` vs `/readyz` (inclusive banco indisponível sem vazar erro);
gating de `/health-detail` e `/metrics` (loopback, proxy declarado, staff, token,
token errado, negação, `X-Forwarded-For` ignorado); redaction de payload com
e-mail/`Authorization`/token/cookie/query string/JWT/CPF no log **e** no evento
do Sentry (incluindo `extra=`, traceback e evento original não mutado);
normalização de `X-Request-ID` (válido, vazio, `-`, longo, controle, tab) e
headers de resposta (`X-Request-ID`, `X-Service`, `X-Environment`, `X-Release`,
`X-Operational-State`); marcação de degradação (header + métrica, e degradação
não quebra a requisição); `record_http`/métricas (buckets, gauge, escape de
labels, teto de cardinalidade); consentimento técnico via header (8 casos) e
fail-closed do Sentry; registro de toda task de `CELERY_BEAT_SCHEDULE`.

### Fora do escopo (não tocado)

- **Frontend** (`frontend/`): Sentry, `X-Request-ID` no `ApiError`, error
  boundaries, consentimento técnico no tracker (critérios 1-6, 20).
- **Infra** (`infra/`, `docker-compose*`, `subir-localhost.sh`, `.env*`):
  Nginx (allowlist de `/livez`, `/readyz`, negação de `/health-detail` e
  `/metrics` por origem), Grafana Alloy, Loki/Mimir, systemd (worker/beat e o
  **heartbeat do beat** que `OBSERVABILITY_BEAT_HEARTBEAT_FILE` espera), R2,
  TLS/SSH/secrets (critérios 21-23, 29-37).
- **CI/CD** (`.github/`): upload de source maps, checks de secrets, validação de
  config de infra (critérios 20, 40).
- **Documentação**: ARCHITECTURE, PROD_DECISOES, PRIVACIDADE, runbooks, SLOs e
  dashboards (critérios 17, 37) — o bloco de documentação.
- **Analytics de produto**: validação do token de consentimento assinado no
  endpoint público (`POST /api/metricas/eventos/`) e redaction do payload de
  produto (critérios 25 e 26). Os settings
  (`ANALYTICS_CONSENT_SIGNING_KEY`, `ANALYTICS_REQUIRE_CONSENT_TOKEN`,
  `ANALYTICS_CONSENT_TTL_SECONDS`) existem, mas **nada os valida** ainda — o
  endpoint hoje persiste evento sem conferir token. Não foi implementado aqui
  porque é a semântica de produto (e não de telemetria técnica) e mexe em
  `metricas/views.py`; está registrado como pendência explícita abaixo.
- **Migrations**: nenhuma criada/alterada.
- `backend/feed/views.py`, `backend/catalogo_noticias/services/deduplicacao.py`,
  `backend/feed/tests/test_p1_feed_cache_indices.py` (WIP da run 2136) e
  `CI-CD.md`, `PROD_DECISOES.md`, `infra/DEPLOY.md` (WIP da run 1433) não foram
  tocados.

### Riscos, bloqueios e pendências

1. **CONSENTIMENTO DE ANALYTICS NÃO APLICADO (bloqueio para os critérios 25/26).**
   `POST /api/metricas/eventos/` segue persistindo sem exigir o token HMAC de
   consentimento, apesar de `ANALYTICS_REQUIRE_CONSENT_TOKEN=True` no default.
   O expurgo que criei reduz a exposição no tempo, mas não impede a coleta.
   Precisa de um bloco próprio (a view é de produto, com rate limit e resposta
   202 para não quebrar tracking).
2. **`/healthz` legado ainda vaza `str(exc)`** em resposta pública. Não toquei
   porque é o alvo do `HEALTHCHECK` do Docker/PM2/Nginx; migrar para
   `/livez`+`/readyz` é decisão do bloco de infra, e o `detalhe` deve sair do
   corpo.
3. **Sentry pode nascer vazio em produção.** `SENTRY_TECHNICAL_CONSENT_DEFAULT`
   default `false` + fail-closed = todo evento descartado. Contável em
   `portal_sentry_events_dropped_total`, mas o operador precisa LIGAR a flag ao
   provisionar o DSN. Documentar no runbook.
4. **Heartbeat do beat não existe ainda.** `check_celery_beat` fica
   `not_configured` até o bloco de infra criar o arquivo e a escrita periódica.
   Critério 16 (worker/beat paradoxos aparecendo como falha) fica parcialmente
   coberto: worker é checado de verdade; beat precisa do heartbeat.
5. **Métricas são por processo.** `/metrics` é baseline em memória por worker
   Gunicorn (2 workers × 4 threads). O agregado por `instance` depende do
   Alloy/Prometheus (bloco de infra); com 2 workers os counters somam certo, mas
   um restart zera a série (aceito e documentado no docstring de `metrics.py`).
6. **`/livez` não tem atalho de middleware.** A cadeia inteira roda antes da
   view; `SessionMiddleware`/`AuthenticationMiddleware` são preguiçosos, então
   hoje `/livez` não toca o banco. Se algum dia um middleware novo for
   eagerness de sessão, o liveness pode cair com o banco — daí o teste que
   faz patch em `connection.cursor` e exige 200.
7. **Prova de regressão do 404** depende do comportamento interno do Django
   (`process_exception_by_middleware` roda antes de `get_exception_response`);
   se um upgrade do Django mudar essa ordem, o teste `test_404_continua_404...`
   acusa.
8. **Nenhuma métrica de gauge sobrevive a restart** e o teto de 5 000 séries é
   por processo: com `MAX_SERIES` atingido, métricas novas são descartadas
   (visíveis em `portal_metrics_series_dropped_total`) — alarme para ajustar
   `MAX_SERIES` se o vocabulário de rotas crescer.
9. **Regressão de content-type do 500.** O `process_exception` responde JSON
   onde antes podia vir a página técnica do Django (`DEBUG=True` é preservado
   via `DEBUG_PROPAGATE_EXCEPTIONS`). Nenhum teste existente dependia do HTML de
   500, mas é uma mudança observável para quem chama a API.
10. **Validação em homologação/produção, Sentry, Alloy, Better Stack, R2, soak
    de 48 h** — fora do alcance deste bloco; exige acesso e janela coordenada.
