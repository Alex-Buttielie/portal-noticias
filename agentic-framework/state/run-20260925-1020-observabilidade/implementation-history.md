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

## Iteração 2 — Bloco A2 (backend, lacunas remanescentes) — 2026-09-25 — executor (subagente delegado)

Escopo desta iteração: **exatamente as duas lacunas** que o Bloco A registrou
como pendências próprias (iteração 1, "Riscos, bloqueios e pendências" 1 e 2) —
a validação real do consentimento assinado de analytics e o fim do vazamento de
`str(exc)` no `/healthz` legado. Commit: `ca3ae4d`. Frontend, infra, CI/CD e
documentação continuam intocados (ver "Fora do escopo").

### 1. Consentimento assinado de analytics, de fato validado (critérios 25-27)

**O defeito.** `ANALYTICS_REQUIRE_CONSENT_TOKEN` (default `True`),
`ANALYTICS_CONSENT_SIGNING_KEY` e `ANALYTICS_CONSENT_TTL_SECONDS` existiam, e
**nada os validava**: `EventoIngestaoView.post` sanitizava o payload e gravava
`EventoSite`/`InteracaoNoticia`/`EventoBusca` direto no banco. Era fail-open —
o controle de privacidade era decorativo, e o critério 26 ("o evento não é
persistido como dado de produto autorizado") era impossível de atender.

**O que foi implementado**

- `backend/metricas/consent.py` (novo, 767 linhas com docstrings): formato do
  token, emissão, verificação, allowlist do payload e sinal técnico das recusas.
  Não duplica nada do Bloco A — reaproveita `redact_text`, `redact_payload`,
  `safe_path` e `METRICS` de `config/`.
- Verificação fail-closed com sete barreiras, nesta ordem: envelope de 3 partes
  e base64url canônico → assinatura HMAC-SHA256 em `hmac.compare_digest`
  (contra a chave ativa **e** as anteriores) → claims com conjunto e tipos
  exatos → `categoria == "analytics"` → `exp > agora` e
  `exp - iat <= ANALYTICS_CONSENT_TTL_SECONDS` → `iat <= agora + 60 s` →
  `sub` igual ao sujeito do evento. Qualquer uma reprova.
- **Emissor no servidor**: `POST /api/metricas/consent/`. Sem ele a validação
  seria inaplicável — o navegador não pode ter a chave HMAC, e um token "assinado
  pelo cliente" seria control decorativo de novo. O emissor não grava nada, não
  vê IP e é rate limitado (escopo novo `consentimento`, `30/min`).
- **Allowlist de payload** (`CAMPOS_ACEITOS`): campo fora da lista é descartado
  e contabilizado em `portal_analytics_payload_fields_dropped_total`; texto livre
  passa por `redact_text`; `path` passa por `safe_path` (perde query string e
  fragment — o frontend mandava `pathname + search`); `extra`/`filtros` têm teto
  de 20 chaves e 512 bytes já redigidos; payload acima de 4 KB é recusado antes
  do banco; corpo com mais de 200 campos é recusado.
- **Recusa sem 500 e sem oráculo**: toda recusa de consentimento responde
  `202 {"registrado": false, "motivo": "consent_<motivo>"}`. O motivo completo vai
  para o log técnico (motivo + tipo redigido; **nunca** o token, o path, a query
  ou o e-mail) e para `portal_analytics_consent_rejections_total` /
  `portal_analytics_events_rejected_total`.
- **Flag desligado visível**: com `ANALYTICS_REQUIRE_CONSENT_TOKEN=false` o
  caminho legado continua funcionando, mas cada evento incrementa
  `portal_analytics_consent_bypass_total` e dispara aviso técnico (amostrado a
  cada 300 s — o contador é a verdade, o log não pode virar flood de endpoint
  público). A allowlist continua valendo com a flag desligada.

**Mudanças de comportamento que o cliente precisa saber** (documentadas aqui e
no contrato abaixo): campo `id` saiu da allowlist (alias informal de `entry_id`);
o tipo desconhecido deixou de ser ecoado na resposta (`{"detail": "Tipo de evento
desconhecido.", "motivo": "tipo_desconhecido"}`); `path` não carrega mais query
string; termo de busca e filtros também passam pela redação.

### Contrato do token de consentimento

> Seção normativa para o Bloco B (frontend). O cliente **não assina** nada: ele
> obtém o token no endpoint de emissão e o apresenta no evento.

**Formato**

```text
v1.<payload_base64url>.<assinatura_base64url>
```

- `v1` — versão do envelope e das claims.
- `payload_base64url` — JSON canônico **UTF-8, chaves em ordem alfabética, sem
  espaços, base64url sem padding `=`**. Exemplo (linha única, sem quebra):

  ```text
  {"categoria":"analytics","exp":1758086400,"iat":1758000000,"sub":"m1x2k3-8hj3kd2","v":1}
  ```

- `assinatura_base64url` — `HMAC-SHA256(chave, "v1." + payload_base64url)`,
  base64url sem padding (32 bytes de digest).

**Claims obrigatórias** (conjunto exato — claim a mais ou a menos é recusado):
`v` (int, 1), `categoria` (str, `"analytics"`), `iat` (int, epoch s),
`exp` (int, epoch s), `sub` (str pseudônimo do visitante, 6 a 64 caracteres em
`[A-Za-z0-9._-]`).

**Exemplo real gerado pelo código** (chave de exemplo, `iat=1758000000`,
TTL 86400) — serve de golden para o cliente:

```text
token: v1.eyJjYXRlZ29yaWEiOiJhbmFseXRpY3MiLCJleHAiOjE3NTgwODY0MDAsImlhdCI6MTc1ODAwMDAwMCwic3ViIjoibTF4MmszLThoajNrZDIiLCJ2IjoxfQ.ENaqNwsnheFezVGHgcb3enBzRnWHAqU84M0Tvo-k4tA
payload decodificado: {"categoria":"analytics","exp":1758086400,"iat":1758000000,"sub":"m1x2k3-8hj3kd2","v":1}
verificar_consentimento(token, sub_esperado="m1x2k3-8hj3kd2") -> Verificacao(ok=True)
```

**Geração (servidor — `metricas/consent.py`)**

```python
from metricas import consent

token, claims = consent.emitir_consentimento(
    categoria="analytics",   # só "analytics" é emitido aqui
    sub="m1x2k3-8hj3kd2",   # = sessionStorage do tracker
    # ttl_seconds=None -> ANALYTICS_CONSENT_TTL_SECONDS (86400), sempre limitado
)                            # por essa configuração, nunca pelo chamador
```

Ou, sem materializar claims: `consent.gerar_token_consent(sub=...)` → `str`.

**Verificação (servidor — o único verificador)**

```python
verificacao = consent.verificar_consentimento(token, sub_esperado=sessao)
if not verificacao.ok:                      # motivo em verificacao.motivo
    ...
```

`emitir_consentimento` devolve as claims de propósito: um "decodifique sem
verificar" no meio do caminho é o atalho que um dia vira bypass de assinatura.

**Endpoints**

| Endpoint | Quem chama | O que faz |
| --- | --- | --- |
| `POST /api/metricas/consent/` | cliente, **só depois** do gesto de consentimento e quando o `exp` atual passou | emite o token; resposta `201 {token, categoria, sub, exp, ttl_segundos}`; `400` se `sessao`/categoria inválidas; `503` se não há chave configurada; `429` além de `THROTTLE_CONSENTIMENTO_RATE` |
| `POST /api/metricas/eventos/` | cliente, sempre | persiste o evento **só** com token válido; o token vai no header `X-Consent-Token` (preferido) **ou** no campo `consent_token` do corpo (necessário para `navigator.sendBeacon`, que não envia header) |

**Códigos de recusa** (o prefixo `consent_` só aparece na resposta HTTP; log e
métrica usam o código cru)

| `motivo` (resposta: `consent_<motivo>`) | Significado | Ação do cliente |
| --- | --- | --- |
| `ausente` | nenhum token | pedir token e reenviar |
| `malformado` | envelope/base64/claims fora do formato | pedir token novo |
| `assinatura_invalida` | assinatura não bate (ou chave rotacionada) | pedir token novo |
| `expirado` | `exp` passou | pedir token novo (renovação normal) |
| `categoria_invalida` | token de outra categoria | bug de integração |
| `sujeito_invalido` | `sub` ≠ sessão do evento | reemitir com a sessão atual |
| `ttl_invalido` | validade maior que a configurada | bug/config |
| `emissao_invalida` | `iat` no futuro além do skew | relógio do cliente |
| `token_grande` | token acima de 2 048 bytes | bug de integração |
| `sem_chave` | servidor sem chave de assinatura | operação: 503 no emissor |
| `payload_grande` / `campo_excedente` / `tipo_desconhecido` | rejeição de payload (não de consentimento) | revisar payload |

**Flags / settings**

| Setting | Default | Efeito |
| --- | --- | --- |
| `ANALYTICS_REQUIRE_CONSENT_TOKEN` | `True` | `false` só para uso local; passa a contar `portal_analytics_consent_bypass_total` e a avisar em log |
| `ANALYTICS_CONSENT_SIGNING_KEY` | vazio → cai na `SECRET_KEY` | chave que assina; vazia nas duas = `sem_chave` (fail-closed) |
| `ANALYTICS_CONSENT_SIGNING_KEY_PREVIOUS` | vazio | chaves antigas (vírgula) que ainda validam — janela de rotação |
| `ANALYTICS_CONSENT_TTL_SECONDS` | `86400` | teto de validade; o emissor não consegue ultrapassar |
| `THROTTLE_CONSENTIMENTO_RATE` | `30/min` | teto do emissor |
| `X-Consent-Token` no `CORS_ALLOW_HEADERS` | adicionado | sem isso o navegador nem consegue enviar o header |

**Rotação de chave** (revogação real): `ANALYTICS_CONSENT_SIGNING_KEY` = chave
nova (assina) e `ANALYTICS_CONSENT_SIGNING_KEY_PREVIOUS` = chave antiga (ainda
valida). Depois de um TTL sem emissão, remover a antiga da lista invalida todos
os tokens pendentes. É o mecanismo de revogação de que a run precisa: um
incidente de privacidade não depende de deploy.

**O que a assinatura prova e o que não prova**: prova que o payload foi emitido
por este backend, que é da categoria correta, que não expirou, que pertence a
um sujeito, e que pode ser revogado. **Não** prova que um humano leu os termos —
o gesto é do cliente (`frontend/lib/cookie-consent.ts`) e é inevitavelmente do
lado do navegador; o emissor é público, rate limitado e não guarda nada, então ele
não é (e não pode ser) um registro de consentimento.

### 2. `/healthz` legado sem detalhe de erro (critérios 7 e 28)

`config/views.py` devolvia `{"status": "erro", "detalhe": str(exc)}` — e
`/healthz` é o alvo do `HEALTHCHECK` do Docker, do PM2 e do Nginx, logo público
por definição. A mensagem do driver carrega host, porta, usuário e, em alguns
casos, credencial.

- Resposta pública agora genérica: `200 {"status": "ok"}` /
  `503 {"status": "erro"}`. Sem `str(exc)`, sem traceback, sem host, sem chave
  `detalhe` (que agora nem existe).
- O detalhe foi para o **log técnico**, já redigido por
  `config.observability.safe_exception` (`health._timed` aplica a redação), com
  `request_id` para correlação e apontando `/health-detail` como o caminho do
  diagnóstico completo.
- A checagem passou a usar `health.check_database()` (o mesmo do par canônico, e
  o que já gera `portal_dependency_checks_total`) em vez do `SELECT 1` solto,
  e o 503 é garantido mesmo se a própria checagem explodir — um 500 ali seria
  lido pelo orquestrador como "saúde desconhecida".
- `portal_healthz_legacy_total{result=ok|unavailable}`: é o sinal de que ainda há
  consumidor do legado, ou seja, a evidência que o bloco de infra precisa para
  migrar Docker/PM2/Nginx/Better Stack para `/livez` + `/readyz`. O par
  canônico está documentado no docstring da view; a migração é do bloco de infra
  (`docker-compose.yml`, `infra/`, `.github/` não foram tocados).

### Arquivos tocados

Novos:

```text
backend/metricas/consent.py
backend/metricas/tests/test_consent_token.py
backend/metricas/tests/test_consent_ingestao.py
backend/config/tests/test_healthz_legado.py
```

Modificados:

```text
backend/metricas/views.py          (fail-closed + allowlist + emissor)
backend/metricas/urls.py           (rota /api/metricas/consent/)
backend/metricas/tests/test_inteligencia.py   (5 testes de ingestão agora postam token válido)
backend/config/views.py            (/healthz genérico + log)
backend/config/settings.py         (chave anterior, taxa de throttle, CORS header)
backend/config/throttling.py       (ConsentimentoAnonThrottle)
backend/config/metrics.py          (describe das 6 séries novas)
```

Nenhuma migration (`manage.py makemigrations --check --dry-run` → "No changes
detected"), nenhuma dependência nova (só stdlib: `hmac`, `hashlib`, `base64`,
`json`, `re`, `threading`).

### Testes: comandos e saída real

Ambiente: `backend/.venv/bin/python` (Python 3.14.4), `DJANGO_SETTINGS_MODULE=config.settings_test`.

```console
$ backend/.venv/bin/python manage.py check
System check identified no issues (0 silenced).

$ backend/.venv/bin/python manage.py makemigrations --check --dry-run
No changes detected
```

```console
$ cd backend && .venv/bin/python -m pytest config metricas -q
287 passed, 94 warnings in 13.02s
```

```console
$ cd backend && .venv/bin/python -m pytest metricas -q
124 passed, 63 warnings in 6.61s
```

```console
$ cd backend && .venv/bin/python -m pytest -q
7 failed, 730 passed, 282 warnings in 85.67s (0:01:25)
```

As 7 falhas são **externas**, o mesmo WIP da run `20260924-2136-ingestao-noticias`
(`?? catalogo_noticias/tests/test_command_agendar_ingestao.py` +
`?? catalogo_noticias/management/commands/agendar_ingestao.py`), com
`RuntimeError: Database access not allowed` — idênticas às 7 do Bloco A, e nenhum
arquivo meu participa delas:

```console
$ cd backend && .venv/bin/python -m pytest catalogo_noticias -q
7 failed, 156 passed, 38 warnings in 21.14s
$ cd backend && .venv/bin/python -m pytest -q --ignore=catalogo_noticias/tests/test_command_agendar_ingestao.py
721 passed, 282 warnings in 82.69s (0:01:22)
```

Cobertura (mesmo comando do CI):

```console
$ cd backend && .venv/bin/python -m pytest config metricas -q --cov=config --cov=metricas --cov-report=term --cov-fail-under=80
config/views.py                          19      0  100%
config/throttling.py                     11      0  100%
metricas/consent.py                     291     23   92%
metricas/views.py                       145     19   87%
TOTAL                                  4159    308   93%
Required test coverage of 80% reached. Total coverage: 92.59%
```

**101 testes novos**: 48 no contrato do token, 46 na ingestão fail-closed, 7 no
`/healthz`.

**Prova de regressão (o teste falha sem o fix)** — verificado desativando o bloco
de consentimento e reintroduzindo o `str(exc)` no corpo, e restaurando em seguida:

```console
# views.py com a verificação substituída por um Verificacao(True) fixo
22 failed, 23 passed          # test_consent_ingestao.py

# config/views.py com {"status": "erro", "detalhe": <detalhe>} de volta
2 failed, 5 passed            # test_healthz_legado.py
```

O que os testes cobrem: formato canônico e assinatura cobrindo a versão; claims
com tipo/forma errados (`"1758000000"`, `1.5`, `true`); claim a mais (inclusive
uma com e-mail) e a menos; base64url não canônico, versão errada, token não
ASCII (que viraria `UnicodeEncodeError` → 500), token gigante; assinatura
trocada, payload adulterado com re-assinatura por chave errada, token de
categoria técnica, token de outra sessão, token expirado, token de validade
acima do TTL, `iat` no futuro, skew pequeno aceito; rotação (válido na janela,
revogado depois) e ausência de chave; emissão por HTTP (201/400/503/429) e token
emitido sendo aceito pelo endpoint; evento persistido só com token válido (por
header e por corpo, para o `sendBeacon`), token ausente/malformado/expirado/
adulterado/errado/ausente de `sessao` não persistindo; tipo desconhecido (400,
sem eco do input); campo em excesso, e-mail/token/cpf em `extra`, query string
no `path`, e-mail no termo de busca e nos filtros; payload grande e corpo com
muitos campos; corpo não-dict sem 500; evento roteado para `feed.*` também
exigindo consentimento; sinal técnico de recusa em log (sem token, sem PII) e
nas duas métricas; flag desligada mantendo o caminho legado **e** visível, e
ainda redigindo; `/healthz` 503 genérico (nenhum dos 9 termos que o vazariam),
detalhe no log com `request_id`/`environment`/`release` e sem senha, 200 com
banco de pé, contador por resultado, e os dois caminhos de exceção.

### Decisões e trade-offs

- **Emissor público e sem registro.** Poderia exigir autenticação ou gravar um
  recibo de consentimento, mas nenhum dos dois é melhor aqui: exigir login
  quebraria o consentimento de visitante anônimo (que é a maioria), e gravar
  recibo exigiria migration + dado pessoal novo, o que contraria o espírito de
  reduzir dado. O emissor entrega prova de que o backend autorizou, não um
  registro de que alguém aceitou. O recibo no servidor fica como pendência.
- **Assinatura não substitui o gesto do cliente.** Deixar isso explícito no
  docstring evita o pior uso futuro: alguém "corrigir" o cliente colocando a
  chave HMAC no browser (o que torna tudo decorativo de novo).
- **Rejeitar payload é melhor que truncar silenciosamente.** Campo fora da
  allowlist é descartado e o evento segue; `payload_grande` recusa o evento
  inteiro (um corpo de megabytes é abuso, não evento). Redigir valor sensível
  dentro de campo legítimo é o caminho intermediário.
- **Alegação de sessão descartada em favor do token.** Se o `sessao` do payload
  não é um sujeito válido, quem manda é o `sub` assinado. Um cliente descuidado
  não perde o evento, e um token de uma sessão não consegue poluir outra.
- **Amostragem do log de bypass.** Contador por evento + no máximo um WARNING a
  cada 300 s. Contador sozinho não é visível no momento do incidente; log por
  evento inundaria o Loki e esconderia o resto.
- **202 para recusa de consentimento, 400 para tipo desconhecido.** O 202 é o
  "nada persistido, tudo bem" que o tracking já espera e não vira erro no
  console do visitante; o 400 é bug de integração do cliente, que precisa ver.
  O `motivo` é um código fechado e curto, não um diagnóstico do visitante.
- **`/healthz` não foi removido.** Remover derrubaria o orquestrador inteiro
  (Docker/PM2/Nginx ainda apontam para lá). Migrar os consumidores é do bloco de
  infra; aqui o vazamento fecha e nasce o contador que mede a migração.

### Fora do escopo (não tocado)

- **`frontend/`** — Bloco B: obter o token em `POST /api/metricas/consent/` só
  depois do gesto de consentimento, guardar (`sessionStorage`/`localStorage`),
  renovar quando `exp` passar, anexar em `X-Consent-Token` (ou `consent_token`
  no corpo, se mantiver `sendBeacon`) e renovar ao receber
  `motivo: consent_expirado`/`consent_ausente`. O contrato está na seção acima.
- **Infra/CI/CD** — `docker-compose.yml`, `Dockerfile`, `infra/`, `.github/`,
  `subir-localhost.sh`: migrar healthcheck para `/livez` + `/readyz` (usando
  `portal_healthz_legacy_total` como sinal do que ainda sobra) e expor as duas
  rotas no Nginx.
- **Documentação** — `ARCHITECTURE.md` (linha do healthcheck), `infra/DEPLOY.md`
  (que ainda descreve `/healthz` como checagem de conectividade e cita
  `400`/códigos em smoke tests), textos de consentimento/privacidade e runbooks
  de analytics: bloco de documentação.
- **Migrations**: nenhuma criada/alterada.
- Não tocados por serem WIP de outra run: `backend/feed/views.py`,
  `backend/catalogo_noticias/services/deduplicacao.py`,
  `backend/feed/tests/test_p1_feed_cache_indices.py`, `subir-localhost.sh`,
  `CI-CD.md`, `PROD_DECISOES.md`, `infra/DEPLOY.md`, `run-state.json` desta e de
  outras runs.

### Riscos, pendências e o que continua aberto

1. **Analytics de produto para de coletar até o Bloco B publicar o cliente.**
   O backend agora é fail-closed, e o `frontend/lib/analytics.ts` atual NÃO
   envia token — logo todo evento sai com `consent_ausente` até o Bloco B. É o
   comportamento correto (é o que os critérios 25/26 exigem), mas é uma perda de
   dado de produto de verdade no intervalo entre os dois blocos. Sinais para
   acompanhar: `portal_analytics_consent_rejections_total{reason="ausente"}` e
   `portal_analytics_events_rejected_total`. Mitigação de operação, se o
   Bloco B atrasar: `ANALYTICS_REQUIRE_CONSENT_TOKEN=false` com
   `ANALYTICS_CONSENT_SIGNING_KEY` preenchida (deixa o bypass visível em
   métrica e log, e a allowlist continua valendo).
2. **Não há recibo de consentimento no servidor.** O emissor é público e não
   persiste nada; a auditoria de "quem consentiu, quando" continua sendo do
   cliente (localStorage) mais log/métrica. Persistir exigiria model +
   migration + política de retenção própria — decisão de produto/jurídica, não
   deste bloco.
3. **Reuso/replay de token dentro do TTL.** A assinatura liga o token à sessão e
   à janela, mas não impede o mesmo token de ser reenviado dentro dela. O único
   freio é o throttle do emissor (não o da ingestão). **Não** throttlei a
   ingestão de propósito: `page_view` em rajada é uso legítimo e um limite por IP
   quebraria o tracking de navegação real. O freio correto seria por sujeito
   (`sub`), não por IP — pendência para o Bloco B/infra.
4. **Inflação de BI por coleta automatizada.** Um bot pode pedir token ( throttle
   de 30/min) e enviar eventos. Reduzir exigiria consentimento autenticado ou
   prova de interação humana; está registrado, não resolvido.
5. **Termo de busca agora é redigido.** `EventoBusca.query` é produto
   ("termos populares"), e um termo com formato de e-mail/CPF/token passa a ser
   mascarado. É privacidade sobre o produto; se a curadoria reclamar de termos
   perdidos, o ajuste é no `metricas.consent.py` (não no modelo).
6. **A redigitização do `path` muda dado já coletado.** `path` sem query string
   quebra qualquer leitura histórica que usasse `path` como chave composta
   (ex.: `categoria + path+query`). Não encontrei nenhuma leitura que dependa
   disso em `services_inteligencia.py`, mas dashboards externos podem precisar
   de reprocesso do histórico anterior à data de deploy.
7. **`/healthz` ainda é o endpoint que o orquestrador chama.** A correção é de
   vazamento, não de arquitetura. Migrar Docker/PM2/Nginx/Better Stack para
   `/livez` + `/readyz` é do bloco de infra; até lá, `/healthz` segue respondendo
   por dependência obrigatória (o que é a semântica antiga, e o motivo de o
   orquestrador não ter parado antes).
8. **Teste de carga do emissor não foi feito.** O teste de throttle prova o
   `429` com a taxa configurada em cache de memória; o comportamento com Redis
   real (`IGNORE_EXCEPTIONS=True`) não foi exercitado.
9. **`ANALYTICS_CONSENT_TTL_SECONDS` continua com o default de 24 h.** O token
   podia ser mais curto (uma sessão de navegação dura minutos). O default é o
   que já existia e mudar para baixo quebraria a renovação em dispositivos com
   relógio atrasado; a escolha é do bloco de produto/política de privacidade.
10. **Sentry, Alloy, Better Stack, R2, soak de 48 h** — fora do alcance deste
    bloco; permanece igual ao Bloco A (iteração 1, pendência 10).
