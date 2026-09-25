# Code Review — Backend (parcial) — run 20260925-1020-observabilidade

<!--
CONTRACT: code-review (PARCIAL — apenas backend)
DONO: reviewer independente
RUN: 20260925-1020-observabilidade
-->

## Escopo

Revisão **parcial** e **somente-leitura** do backend da run `20260925-1020-observabilidade`.
Frontend, infra, CI/CD e documentação **não** foram revisados aqui: eles entram no
`code-review-contract.md` (revisão completa).

**Commits revisados** (branch `observability-20260925-1020`):

| commit | conteúdo |
|---|---|
| `672ffba` | baseline de telemetria do backend (health, métricas, redação, Sentry) — sem testes |
| `1b97836` | Bloco A: liga `/livez`, `/readyz`, `/health-detail`, `/metrics`, cria `expurar_analytics`, corrige bugs do baseline |
| `ca3ae4d` | Bloco A2: consentimento assinado de analytics e fechamento do vazamento do `/healthz` |
| `2bf82c0` | histórico (documentação — não avaliado aqui) |

Base do diff: `git diff 7715dae..ca3ae4d -- backend/` (28 arquivos, +6477/−131).
Arquivos novos: `config/{observability,health,metrics,observability_views}.py`,
`metricas/{consent,tasks}.py` + 10 arquivos de teste.

**Fora do escopo (deliberadamente, conforme instrução):** WIP estrangeiro em
`backend/feed/views.py`, `backend/catalogo_noticias/services/deduplicacao.py`,
`backend/feed/tests/test_p1_feed_cache_indices.py`,
`backend/catalogo_noticias/management/commands/agendar_ingestao.py` e as 7 falhas de
`catalogo_noticias/tests/test_command_agendar_ingestao.py`; diff aberto da run
`20260925-1433-go-live-producao` em `CI-CD.md`, `PROD_DECISOES.md`, `infra/DEPLOY.md`,
`scripts/release/`. Nenhum achado abaixo se refere a esses arquivos.

**Como foi verificado**

- Leitura integral dos 8 módulos de produção do diff e dos 10 arquivos de teste novos.
- `pytest config metricas -q` → **287 passed** (12 s).
- `pytest config metricas -q --cov=config --cov=metricas --cov-fail-under=80` → **287 passed, 92,59%** (confere com o declarado).
- `manage.py check --settings=config.settings_test` → `System check identified no issues`.
- Testes adversariais **descartáveis**, criados **fora do repositório** em `/tmp/opencode/rev/`
  (gating, path/header/método, redaction, cardinalidade, consentimento, throttle, custo de render).
  Nada foi escrito no repositório; nenhum arquivo do projeto foi editado, criado ou commitado.

---

## Veredito

**`request_changes`**

Não há **blocker**: o núcleo do bloco está correto e eu tentei quebrá-lo sem sucesso —
o gating de `/health-detail` e `/metrics` **não foi quebrado** por nenhuma das tentativas
(listadas abaixo), o consentimento é **fail-closed de verdade** em todas as combinações de
flag que testei, e a allowlist de payload é a barreira certa (não uma lista de termos).
O que segura o veredito são **4 majors**, todos de correção barata:

1. o rate limit do emissor de token de consentimento **não funciona** (bypass por
   `X-Forwarded-For`) — é um controle de privacidade introduzido por esta run;
2. o rótulo `method` das métricas HTTP é **controlado pelo cliente** e, com o teto de
   séries, isso derruba em silêncio séries legítimas e onera o scrape;
3. com a configuração **default**, um beat parado **não** aparece como degradação
   (critério 16 não atendido);
4. as métricas de task Celery e de expurgo são gravadas num processo que **não expõe
   `/metrics`** (critério 14 apenas parcialmente atendido).

---

## Achados

Gravidade: **blocker** / **major** / **minor** / **nit**. "Risco teórico" = não encontrei
caminho concreto no código atual, mas a barreira declarada não cobre o caso.

### Major

#### MAJOR-1 — O throttle do emissor de token de consentimento é contornado por `X-Forwarded-For`

- **Arquivo/linha:** `backend/config/throttling.py:76-89` (`ConsentimentoAnonThrottle`),
  `backend/config/settings.py:389` (`"consentimento": 30/min`),
  `backend/metricas/views.py:100-101` (`throttle_classes = [ConsentimentoAnonThrottle]`).
- **O que acontece:** o DRF usa `SimpleRateThrottle.get_ident`, que, sem `NUM_PROXIES`
  configurado (`grep NUM_PROXIES config/settings.py` → nada), devolve
  `''.join(xff.split())` — ou seja, **o bucket é o header `X-Forwarded-For` cru**. Os
  nginx versionados (`infra/nginx/portal-{dev,homolog,prod}.conf`) definem
  `X-Real-IP`/`X-Forwarded-Proto` mas **não** definem `X-Forwarded-For`, então o valor
  fornecido pelo cliente chega intacto ao Django. E o emissor aceita qualquer `sessao`
  (`ConsentimentoTokenView.post` → `normalizar_sub`), ou seja, não há nada que impeça
  mintação em massa.
- **Reprodução** (`/tmp/opencode/rev/test_adv_throttle.py`, 40 POSTs com XFF rotacionado):
  `STATUS: [201, 201, ... 201]` — **nenhum 429**, contra um teto configurado de 30/min.
- **Impacto:** o controle introduzido nesta run ("um emissor sem teto é um script de coleta
  de dados com o carimbo do próprio site", `throttling.py:79-87`) **não se sustenta**; a
  issue de privacidade é volume de eventos coletáveis sem consentimento humano por sessão
  arbitrária. O mesmo bypass vale para os escopos pré-existentes (`auth_sensivel`,
  `escrita_publica`, `enderecos`) — fora do escopo deste diff, mas a mesma causa.
- **Correção:** `NUM_PROXIES = 1` no `REST_FRAMEWORK` (ou `get_ident` próprio usando
  `REMOTE_ADDR`/`X-Real-IP`) **e** `proxy_set_header X-Forwarded-For $remote_addr` no nginx;
  cobrir com um teste que env requests excedendo a taxa.

#### MAJOR-2 — Rótulo `method` controlado pelo cliente: envenenamento e descarte silencioso de séries

- **Arquivo/linha:** `backend/config/metrics.py:364-371` (`record_http`), chamado em
  `backend/config/middleware.py:177`; descarte em `config/metrics.py:82-93` e `130-151`.
- **O que acontece:** `labels = {"method": str(method)[:16], ...}`. `request.method` vem
  do cliente e o parser HTTP do Gunicorn aceita qualquer token como método, sem
  allowlist. O teto `MAX_SERIES = 5000` existe, mas quando estourado **descarta em
  silêncio** qualquer série nova — inclusive as legítimas — e só aumenta um contador
  agregado (`portal_metrics_series_dropped_total`).
- **Reprodução:**
  - `record_http` via middleware com `REQUEST_METHOD="ZZZ<random>"` produz
    `portal_http_requests_total{method="ZZZ1790367602.72",route="unmatched",status="200"} 1`
    — série nova por request (2 séries por request: counter + histograma).
  - Registro novo com 6000 séries ruidosas + 1 série legítima →
    `portal_metrics_series_dropped_total 1001` e **`portal_http_requests_total{...}` ausente**
    (o teste `assert "portal_http_requests_total{" in corpo` falha).
- **Impacto:** (a) *poisoning* — um cliente anônimo escolhe rótulos; (b) *perda*: depois
  de 5000 séries, `portal_ready`, `portal_celery_queue_depth{queue=...}` de uma fila nova e
  qualquer rota nova deixam de existir no `/metrics`; (c) *custo*: cada scrape copia e
  reordena todas as observações **dentro do lock** do registry — medi
  **200 séries × 10 000 obs → 0,89 s e 33 MB de cópia transitória por scrape**
  (200 séries × 10k = 2 M observações). No teto (5000 × 10 000) isso vira ~1,6 GB de
  floats e minutos de lock, com todas as requisições do processo aguardando.
- **Correção:** normalizar o método contra uma allowlist (`GET/POST/PUT/PATCH/DELETE/HEAD/OPTIONS` → `other`),
  e/ou isolar o teto por nome de métrica; considerar contador cumulativo de buckets no
  histograma em vez de reter observações.

#### MAJOR-3 — Beat parado não vira degradação com a configuração default (critério 16)

- **Arquivo/linha:** `backend/config/health.py:198-205` (`check_celery_beat` →
  `not_configured` quando `OBSERVABILITY_BEAT_HEARTBEAT_FILE` está vazio) e
  `health.py:343` (`optional_bad` exclui `{"ok","disabled","not_configured"}`);
  default em `config/settings.py:521`.
- **O que acontece:** com o default (variável vazia), `check_celery_beat` devolve
  `not_configured`; como `not_configured` não entra em `optional_bad`, o agregado
  continua `status="ok"`, `degraded=False` → **sem** `X-Operational-State: degraded`,
  **sem** `portal_health_degraded_total`, **sem** sinal para alerta. Confirmei em execução:
  `check_celery_beat → not_configured` e `degraded_state() → {'status': 'ok', 'reasons': ()}`.
  O beat aparece no detalhe privado, mas o critério 16 pede "a condição aparece como
  falha/degradação e gera alerta".
- **Impacto:** falso verde justamente no componente que a run existe para vigiar
  (o comentário do código assume que "a causa fica no endpoint privado"; o alerta não olha
  para lá). **Nota para a revisão completa:** o fecha pode ser o bloco de infra
  (heartbeat writer no systemd + regra de alerta). Se o infra não criar o heartbeat nem
  tratar `not_configured`, o critério fica permanentemente não atendido.
- **Correção (backend, barata):** contar `not_configured` de `celery_beat` como degraded,
  ou no mínimo emitir `METRICS.inc("portal_health_check_not_configured_total", check="celery_beat")`
  e um WARNING no boot.

#### MAJOR-4 — Métricas de task Celery e de expurgo nunca são consultáveis (critério 14 parcial)

- **Arquivo/linha:** `backend/config/celery.py:44-71` (`record_celery` no `task_postrun`),
  `backend/metricas/tasks.py:121,127`, `backend/config/metrics.py:267-268` (singleton
  process-local), `backend/config/urls.py` (só o app web expõe `/metrics`).
- **O que acontece:** `METRICS` é um registro **por processo** (o próprio docstring de
  `metrics.py:1-8` assume isso). `record_celery` roda no **worker** e o expurgo roda no
  processo disparado pelo **beat**; nenhum dos dois serve `/metrics`. Logo
  `portal_celery_tasks_total`, `portal_celery_task_duration_seconds`,
  `portal_analytics_purge_deleted_total` e `portal_analytics_purge_duration_seconds`
  **não existem em nenhum scrape**. Além disso: não há métrica de **atraso** de fila
  (o critério 14 pede "fila, atraso, retry, falha e duração") e
  `portal_celery_queue_depth` só é atualizado quando alguém chama `/health-detail`
  (`health.py:339-340`).
- **Reprodução:** `record_celery` num processo de worker; nenhum endpoint de métricas
  nesse processo (`config/urls.py` só declara `/metrics` no app web).
- **Impacto:** o painel de jobs que a run promete não tem como ser construído só com o
  backend; alerta de job travado/fila acumulada fica sem dado. **Risco teórico** no curto
  prazo (depende de o bloco de infra não exporter de worker/Pushgateway).
- **Correção:** exporter no worker (ou push para backend) no bloco de infra; no backend,
  publicar as métricas de job em tabela de domínio (o padrão que o próprio `metrics.py`
  sugere) e adicionar a métrica de atraso.

### Minor

#### MINOR-1 — Redação não cobre `Authorization: Basic <credencial>` nem o 2º cookie

- **Arquivo/linha:** `backend/config/observability.py:89-95` (`_SECRET_ASSIGNMENT`) e
  `192-195` (`redact_text`).
- **Reprodução:**
  - `redact_text("Authorization: Basic ZGV2OnNlcmV0YQ==")` → `Authorization=[REDACTED] ZGV2OnNlcmV0YQ==` (**credencial vaza**);
  - `redact_text("Cookie: sessao=abc123 csrf=def456")` → `Cookie=[REDACTED] csrf=def456` (**segundo valor vaza**).
  Causa: `[^\s,;&]+` para no primeiro espaço, então "Basic"/"sessao" são consumidos como
  valor e a credencial fica de fora; no cookie, o `;` salva o primeiro valor e o
  separador por espaço não.
- **Impacto:** **risco teórico no código atual** — nenhum log do backend imprime headers
  de request (`grep logger.*email|user|request.headers` → nada). Mas a redação é
  declarada como "última barreira" e qualquer integração futura que despeje
  `str(exc)` de uma lib HTTP pode vazar credencial basic para o log/Loki e para o Sentry.
- **Correção:** em `_SECRET_ASSIGNMENT`, consumir o valor até o fim da linha para
  `authorization`/`cookie` (ou adicionar uma regra `Basic\s+[A-Za-z0-9+/=]+`), e um teste
  de regressão para os dois casos.

#### MINOR-2 — `\n`, `\r` e `\t` sobrevivem a `redact_text` (injeção de linha no formatter "verbose")

- **Arquivo/linha:** `backend/config/observability.py:96` (`_CONTROL` exclui 0x09/0x0a/0x0d
  de propósito — traceback precisa de newline) e `backend/config/middleware.py:222-224`
  (log do 500 com `request.path` cru); formatter `verbose` em `config/settings.py:1064-1071`.
- **Reprodução:** `redact_text("linha1\nforjada\rlinha2\tTAB")` → `'linha1\nforjada\rlinha2\tTAB'`.
  Com `DJANGO_LOG_JSON=true` (default novo) o `json.dumps` neutraliza (confirmei: a
  linha continua sendo um único objeto JSON válido). Com `DJANGO_LOG_JSON=false` o
  formatter `verbose` é um `logging.Formatter` puro e o `\n` de um `path` com `%0a`
  quebraria a linha de log.
- **Impacto:** forja de linha de log apenas no modo verbose (não é o default de produção).
- **Correção:** escapar `\n`/`\r` no caminho do formatter "verbose" (ou usar o redactor
  também no formatter de texto).

#### MINOR-3 — `Authorization` não-ASCII transforma o 404 do endpoint privado em 500

- **Arquivo/linha:** `backend/config/observability_views.py:100-108` (`secrets.compare_digest`
  com `str`).
- **Reprodução:**
  `Client().get("/health-detail", REMOTE_ADDR="203.0.113.10", HTTP_AUTHORIZATION="Bearer çéé")`
  → `TypeError: comparing strings with non-ASCII characters is not supported` → **500**
  (com `ERROR django.request` + traceback + `got_request_exception`, ou seja, **evento
  no Sentry**), em vez do 404 silencioso que o módulo promete.
- **Impacto:** qualquer cliente anônimo, com um único header, gera ruído de 5xx (que o
  próprio contrato usa para alerta) e evento de APM. Sem vazamento.
- **Correção:** comparar bytes (`valor.strip().encode()`) ou `try/except TypeError → False`;
  teste de regressão.

#### MINOR-4 — `any()` faz curto-circuito na busca de chaves, e o comentário afirma o contrário

- **Arquivo/linha:** `backend/metricas/consent.py:455-461` — *"Percorrer as chaves candidatas
  inteiro é proposital: um atacante não consegue medir 'acertou na 1ª chave'"*.
- **Reprodução:** com um gerador, `any()` para no primeiro `True`; medi
  `CHAVES TESTADAS (short-circuit de any): ['k1']`.
- **Impacto:** o comentário afirma uma propriedade de tempo constante que o código não tem
  (o vazamento é "qual chave assinou", de baixo valor). Mais grave é o deceive: a próxima
  pessoa que mexer nesse trecho acredita numa garantia que não existe.
- **Correção:** reescrever o comentário para o que o código faz, ou usar um laço sem
  curto-circuito (`for ...: ok |= compare_digest(...)`).

#### MINOR-5 — `portal_analytics_purge_deleted_total` usa a **contagem** como label

- **Arquivo/linha:** `backend/metricas/tasks.py:121` — `METRICS.inc("portal_analytics_purge_deleted_total", model=nome, rows=total)`.
- **Reprodução:** três execuções com `rows` 0/1234/1235 →
  `portal_analytics_purge_deleted_total{model="metricas.EventoSite",rows="0"} 1`,
  `...{rows="1234"} 1`, `...{rows="1235"} 1` — três séries para o mesmo contador.
- **Impacto:** série nova por contagem distinta (cresce com a variação diário) e semântica
  errada: somar por `model` dá o total, mas o alerta por `rows` não agrega nada.
- **Correção:** `METRICS.inc("portal_analytics_purge_deleted_total", value=total, model=nome)`.

#### MINOR-6 — `portal_analytics_events_rejected_total` conta evento que é **persistido**

- **Arquivo/linha:** `backend/metricas/views.py:200-204`.
- **O que acontece:** quando há campo excedente, o contador de "eventos **rejeitados**"
  sobe e a gravação segue normalmente (`dados` já saneado é persistido logo abaixo).
- **Impacto:** dashboard/alerta de "eventos rejeitados" dispara com eventos sendo aceitos —
  falso alarme na métrica que existe justamente para não ser verde-mentira.
- **Correção:** usar o contador de campos descartados (`portal_analytics_payload_fields_dropped_total`,
  que já existe) e não o de eventos rejeitados.

#### MINOR-7 — `X-Release`/`X-Environment` em **toda** resposta, inclusive nas negadas e em 404

- **Arquivo/linha:** `backend/config/middleware.py:235-245`.
- **Reprodução:** `GET /health-detail` de IP externo → 404 com
  `{'X-Environment': 'development', 'X-Release': 'local', 'X-Service': 'portal-api', ...}`;
  o mesmo em `/rota-que-nao-existe`.
- **Impacto:** identificação de ambiente e SHA de release públicos (fingerprinting de
  versão). É **decisão deliberada** (o comentário do `CORS_EXPOSE_HEADERS` explica o uso
  no código de suporte), então não é blocker; registrei para decisão explícita.

#### MINOR-8 — O probe de degradação segura um lock global durante I/O de rede

- **Arquivo/linha:** `backend/config/health.py:385-409` (`with _degrade_lock:` em volta de
  `check_cache`/`check_celery`/`check_celery_beat`/`check_filesystem`).
- **Reprodução:** 4 threads com um `check_cache` de 0,6 s →
  `['inicio','fim','0.60s','inicio','fim','1.20s','inicio','fim','1.80s','inicio','fim','2.40s']`
  — serialização total (as outras 3 esperam o lock; a memoização evita o 2º probe, mas
  **não** o tempo de espera).
- **Impacto:** a latência de toda requisição que colide com o probe é a duração do probe.
  Como `CACHES` não define `SOCKET_CONNECT_TIMEOUT` no cliente Redis
  (`settings.py:426-442`), um Redis "inalcançável" (em vez de "recusado") seguraria o
  lock pelo timeout do SO. **Risco teórico** no deployment real (Redis em localhost →
  recusa imediata). Sugestão: tirar o I/O de dentro do lock (double-checked: probing
  fora, publicando o resultado dentro).

#### MINOR-9 — `except Exception: pass` no `sentry_sdk.init` engole tudo sem sinal

- **Arquivo/linha:** `backend/config/settings.py:1128-1145`.
- **O que acontece:** DSN inválido, integração ausente, `ImportError`, `TypeError` em
  qualquer argumento → o portal sobe e **nada é logado**. O operador fica com a
  sensação de APM ativo sem nenhum evento (o único sinal posterior é
  `portal_sentry_events_dropped_total`, que **não** sobe se o init falhou).
- **Impacto:** falha silenciosa de observabilidade; o "fail-safe" é legítimo (o portal não
  pode depender do Sentry), mas o swallow **completo** não é.
- **Correção:** `except Exception as exc: logger.warning("sentry init falhou: %s", type(exc).__name__)`
  (sem DSN, sem traceback completo).

#### MINOR-10 — Exceção de task Celery nunca chega ao Sentry (mesmo com consentimento)

- **Arquivo/linha:** `backend/config/observability.py:322-334` (`before_send` exige
  consentimento) e `backend/config/celery.py:44-71` (nada seta consentimento na task).
- **O que acontece:** no caminho HTTP o ContextVar **está** correto no momento do
  `got_request_exception` (verifiquei: `CONSENT QUANDO O SINAL DISPARA: [True]`, e
  `request_id` disponível). No caminho da task não existe request → `technical_consent()`
  é `False` →, com o default `SENTRY_TECHNICAL_CONSENT_DEFAULT=False`
  (`settings.py:1114`), **todo** erro de worker é descartado.
- **Impacto:** o critério 19 ("exceção de backend ... ambiente e release corretos") fica
  sem cobertura para jobs, que é justamente onde job travado/erro de ingestão acontecem.
- **Correção:** `set_technical_consent(True)` no `task_prerun` (consentimento técnico de
  backend não depende do browser) ou um `before_send` que trate contexto de task
  separadamente.

#### MINOR-11 — `POST /api/metricas/eventos/` continua sem throttle

- **Arquivo/linha:** `backend/metricas/views.py:165-166` (só `permission_classes`).
- **O que acontece:** o emissor tem teto (embora furado, MAJOR-1), mas o **consumidor**
  não tem. Com um token válido (que qualquer um pode obter para um `sessao` arbitrário),
  o mesmo par `sessao`+token pode ser reenviado sem limite, escrevendo em
  `EventoSite`/`InteracaoNoticia`/`EventoBusca`.
- **Impacto:** amplificador de escrita pública e poluição de dado de produto com evento
  atribuído a sessão que nunca consentiu. O Bloco A2 adicionou throttle **no vizinho** e
  deixou este de fora.
- **Correção:** reaproveitar um escopo existente (ex.: `escrita_publica`) no
  `EventoIngestaoView` (após corrigir o MAJOR-1, senão o limite é decorativo).

#### MINOR-12 — Critério 17 só é atendido para os *probes*, não para as chamadas reais

- **Arquivo/linha:** `backend/config/health.py:83` é o **único** chamador de
  `record_dependency` (verificado por grep em todo o backend). Não há instrumentação das
  chamadas externas reais (Resend em `config/email_resend.py`, proxy ViaCEP/IBGE em
  `enderecos/`, fetch de feed).
- **Impacto:** status/duração/resultado/erro sanitizado de dependências externas não viram
  métrica nem log estruturado — o critério 17 fica parcial neste bloco.

### Nit

- **NIT-1** — `backend/metricas/tests/test_consent_token.py:439` e `:458`: o mesmo teste
  `test_sujeito_invalido_nao_e_emitido` está duplicado (a segunda definição sobrescreve a
  primeira; os casos são idênticos, então nada quebra — mas é cópia esquecida).
- **NIT-2** — `backend/config/tests/test_health_checks.py:232`: `assert resultado.status in {"degraded", "ok"}`
  não pode falhar de forma útil; o nome do teste afirma `degraded`.
- **NIT-3** — `is_sensitive_key` é **denylist**, não allowlist: `mail`, `e_mail`, `user`,
  `username`, `login`, `rg`, `senhaAntiga`, `passwordAntigo`, `sessao` **não** são
  sensíveis (`config/observability.py:72-84`). Verifiquei que **não há hoje** nenhum
  `logger.*` no backend que imprima e-mail/usuário sem rótulo, então é profundidade
  defensiva, não vazamento. (`telefone_contato`, `cpf_titular`, `ip_origem`,
  `X-Real-IP`, `session_key` são cobertos.)
- **NIT-4** — `X-Request-ID` do cliente vai para `EventoBusca.request_id`, que é
  `unique` (`feed/models.py:21`, `feed/busca.py:421-433`): um id repetido faz o evento de
  busca ser **perdido em silêncio** (IntegrityError dentro da task, engolido por
  `try/except` em `_rotear_feed`). **Pré-existente** ao diff (só a docstring do
  normalizador mudou), mas é a leitura literal do "sem colisão" do critério 3.
- **NIT-5** — Importar qualquer `config.*` **antes** do `django.setup()` define
  `DJANGO_SETTINGS_MODULE=config.settings` (`config/celery.py:15`) e o pytest-django passa
  a usar os settings de **produção** em vez de `config.settings_test`. Descoberto porque
  rodei `--cov=config.observability` (alvo pontual) e 2 testes passaram a falhar
  (`X-Operational-State == "degraded"` porque `OBSERVABILITY_CHECK_CELERY` é True e o
  broker real em `localhost:6379` é recusado). Com `--cov=config`/`--cov=.` (o que o
  histórico e a CI usam) a suíte fica verde. Nenhum defeito de produto; é uma armadilha
  para quem for medir cobertura por módulo.
- **NIT-6** — `_eh_staff` (`config/observability_views.py:111-120`) autoriza por
  `is_staff`/`is_superuser`, enquanto o resto do projeto (`PainelMetricasView`,
  `CentralInteligenciaView`) autoriza por `papel == "admin"`. Um `is_staff=True,
  papel="free"` veria o diagnóstico completo; um `papel="admin", is_staff=False` (que o
  modelo permite) seria negado. Ambos fail-closed no lado perigoso.
- **NIT-7** — `_redes_confiaveis()` (`config/observability_views.py:70-75`) emite um
  `WARNING` por valor inválido **a cada requisição** em `OBSERVABILITY_TRUSTED_PROXY_NETWORKS`
  mal configurado (flood de log). Sugestão: logar uma vez por valor.
- **NIT-8** — `metricas/consent.py:414`: `v: 1.0` é **aceito** (`1.0 != 1` é `False` e só
  `bool` é barrado), embora o docstring prometa "sem tipo frouxo, sem float". Sem impacto
  funcional (o valor precisa ser 1); corrigir com `isinstance(claims.get("v"), int)` para
  o contrato do docstring valer.

---

## O que eu tentei quebrar e **não** consegui (verificações negativas)

Gating de `/health-detail` e `/metrics` — **nenhum bypass**. Testes em
`/tmp/opencode/rev/test_adv_gating.py`, todos passando com o código atual:

| tentativa | resultado |
|---|---|
| `X-Forwarded-For`, `X-Real-IP`, `X-Client-IP`, `True-Client-IP`, `CF-Connecting-IP`, `Forwarded`, `X-Original-URL`, `X-Rewrite-URL` = `127.0.0.1` de IP externo | 404 |
| `Host` forjado (`localhost`, `127.0.0.1`, `metrics.internal`, `api`) | 400 (DisallowedHost, tratado pelo `SecurityMiddleware`, não pelo gate) |
| `/health-detail/`, `?x=1`, `#frag`, `/health%2Fdetail`, `//health-detail`, `/health-detail%00`, `/HEALTH-DETAIL`, `/health-detail/..`, `/./health-detail` | 404/301, sem vazar o payload |
| `GET/POST/PUT/HEAD/OPTIONS/DELETE/PATCH` de IP externo em `/health-detail` e `/metrics` | 404 em todos |
| token vazio, `Bearer undefined`, token do outro endpoint, sem `Bearer` | 404 |
| `OBSERVABILITY_TRUSTED_PROXY_NETWORKS` inválido (`nao-e-uma-rede,999.999.0.0/8`) | 404 (fail-closed) |
| `::ffff:127.0.0.1` (IPv4-mapped loopback) | 200 — `is_loopback` do `ipaddress` trata corretamente; **não** é bypass |
| usuário autenticado não-staff, e `papel=admin` com `is_staff=False` | 404 |
| corpo do 404 de negação | `{"detail": "Not found."}`, sem nome de check, host, versão, filas ou coletor |

Outros caminhos verificados **sem** vazamento:

- **Consentimento fail-closed:** sem token / token vazio / expirado / assinatura trocada /
  re-assinado com outra chave / claims extras (`jti`, `email`, `escopo`) / claims a menos /
  `iat` e `exp` como `str`/`float`/`bool` / `sub` inválido / token reaproveitado em outra
  sessão / TTL acima do configurado / `iat` no futuro → todos recusados, nada persistido.
  Ordem correta: HMAC (`compare_digest` sobre bytes) **antes** de interpretar as claims.
  `sub` amarra o evento à sessão quando ela é válida; quando não é, o evento é atribuído
  ao `sub` **do token**, nunca ao alegado.
- **HMAC/canonicalização:** mensagem assinada = `"v1." + payload_b64url` (versão dentro da
  assinatura), base64url canônico sem padding, payload canônico com `sort_keys` e sem
  espaços, assinatura de tamanho fixo (32 bytes) verificada antes de confiar no payload.
  Como a assinatura cobre os bytes exatos recebidos, não existe ambiguidade de codificação
  para explorar.
- **Recusa não vaza oráculo:** o 202 devolve só um código de vocabulário fechado
  (`consent_<motivo>`); nenhum motivo revela nada sobre o visitante ou a chave. Razoável.
- **`/metrics` sem dado pessoal:** após postar um evento com `sessao` e `email` em `path`
  e `extra`, o `/metrics` não contém nenhum dos dois (rótulos são método/rota/status,
  dependência, fila, modelo — todos de vocabulário do código).
- **Payload → banco:** a allowlist `CAMPOS_ACEITOS` é a barreira real; todo campo de texto
  passa por `redact_text`, `path` perde query/fragmento, `sessao` é normalizada,
  `extra`/`filtros` têm teto de chaves/tamanho, e campos fora da lista são descartados e
  contabilizados. `consent_token` é transporte, nunca conteúdo.
- **Middleware:** `Http404` continua 404 (teste que falha se a guarda sair), `PermissionDenied`
  e `MultiPartParserError` também estão na guarda, `DEBUG_PROPAGATE_EXCEPTIONS` é respeitado,
  `X-Request-ID` volta no 500, `record.args` como dict não quebra, CR/LF não injeta header
  (id não-printable → UUID4; `release()/environment()/service()` removem controle e espaço).
  `DisallowedHost`/`Rejection` de CSFE não passam pelo `process_exception` (são tratados pelo
  `convert_exception_to_response` do próprio middleware interno) — **minha hipótese inicial
  de "CSRF viraria 500" estava errada** e foi descartada.
- **Semântica de health:** `/livez` não toca banco (teste com `connection.cursor` explodindo
  → 200 `{"status":"alive"}`); `/readyz` detecta banco fora do ar e **migration pendente**
  (executor falso com plano não vazio → 503) e devolve só `{"status","ready"}`;
  dependência opcional (Redis) não derruba o `/readyz`; banco que cai depois do start é
  detectado (checks obrigatórios rodam a cada chamada, sem memoização).
- **Exposição:** os nginx versionados só encaminham `/api/` e `/healthz` ao Django —
  `/metrics`, `/livez`, `/readyz` e `/health-detail` **não** são roteados pelo vhost público
  nem pelo Caddyfile, então o gating por loopback não é a única barreira em produção.
  (O endpoint privado expõe versão, profundidade de fila, disco e **caminho absoluto** do
  coletor — aceitável atrás do gate, e o contrato pede a causa.)
- **Consentimento técnico no caminho do 500:** o ContextVar **sobrevive** ao
  `finally` do middleware no momento do `got_request_exception` (o `process_exception_by_middleware`
  roda dentro da cadeia, antes do unwind) — `technical_consent() == True` e
  `request.request_id` presente. Com `SENTRY_TECHNICAL_CONSENT_DEFAULT=False` e sem header,
  o evento é descartado e `portal_sentry_events_dropped_total` conta (sem falso verde).
- **Concorrência/estado:** memoização do probe não duplica trabalho (as outras threads
  reusam o cache); `ContextVar` de `request_id` e de `task_id` é resetado com token
  (sem vazar para a requisição/tarefa seguinte — teste dedicated); `task_prerun` preserva um
  `set_task_id` externo e o `postrun` restaura.
- **Expurgo (critério 24):** idempotente (2ª execução = 0), em lotes (7 linhas com
  `lote=2` → 4 lotes), para em `deleted=0` em vez de girar, audita contagem/janela/duração
  **sem** query/path/sessão/e-mail no log, e `CELERY_BEAT_SCHEDULE` →
  `metricas.tasks.expurar_analytics` está **registrada no app** (varredura de todas as
  entradas do beat). Agregados: este projeto calcula agregado na leitura
  (`feed/recomendacao.py:113` usa janela de 7d) — confirmei que o **único** cache de
  agregado derivado é `feed:autocomplete:v2:populares`, e o job o invalida. Janela:
  `criado_em__lt = now − 365d` (fuso via `timezone.now()`, `USE_TZ`); é 365 dias, não 12
  meses corridos — o histórico admite 365 dias, e o teste cobre 364 (preserva) / 366 (remove).
- **Testes:** os 287 testes **assertam** comportamento, não só exercitam código; há
  regressões que quebram se o fix for revertido (o `Http404`→500, o `dict()` em
  `_render_labels`, o `X-Environment` em produção, o `record.args` dict, CR/LF no header,
  a varredura do beat). Cobertura **medida** em código alcançável: 92,59% no comando do
  histórico (confiro), 92% só nos módulos tocados (confiro), 100% em `metricas/consent.py`
  (consenso) e `metricas/tasks.py`. Não achei teste que só "passe por passar" além do NIT-2.

---

## Critérios do contrato: o que consegui verificar

| # | critério | veredito | como |
|---|---|---|---|
| 1 | ID UUID seguro gerado no browser, aceito pelo Django | **parcial** | metade backend verificada (normalização/aceite); geração é frontend |
| 2 | mesmo ID normalizado no header / `ApiError` | **parcial** | header verificado ponta a ponta; `ApiError` é frontend |
| 3 | ID inválido/longo/com controle → UUID seguro, sem colisão | **verificado (com NIT-4)** | testes de middleware + endpoint; colisão na coluna `unique` é pré-existente |
| 6 | consentimento técnico aceito → evento com ambiente/release, sem token/e-mail/IP | **verificado (backend)** | `before_send` popula environment/release e remove user/cookies/headers/query/data |
| 7 | `/livez` com banco fora do ar; `/readyz` indisponível sem `str(exc)` | **verificado** | teste com `cursor` explodindo; corpo público genérico |
| 8 | `/readyz` 200 com resposta pública genérica | **verificado** | `{"status":"ready","ready":true}` |
| 9 | Redis/Celery fora do ar → estado degradado registrado, metricado, detalhado no privado | **verificado** (exceto beat, MAJOR-3) | `X-Operational-State`, `portal_degraded_responses_total`, `portal_dependency_checks_total`, detalhe no `/health-detail` |
| 12 | sem fallback fictício em produção | **não verificado** | frontend |
| 13 | registro de disparo de ingestão (queued/running/…/retries) | **não verificado** | fora do diff (WIP da run `20260924-2136-ingestao-noticias`) |
| 14 | métricas de fila, **atraso**, retry, falha e duração consultáveis no Grafana | **parcial** (MAJOR-4) | fila/disco ok; atraso inexistente; métricas de task em processo sem exposition |
| 17 | status/duração/resultado/erro sanitizado de dependência externa | **parcial** (MINOR-12) | só os probes de health; não as chamadas reais |
| 18 | log com ambiente, serviço, release e request/task ID | **verificado** | formatter + `RequestIdLogFilter`; `task_id` nos sinais Celery; ressalva MINOR (log 500 duplicado) |
| 19 | Sentry com ambiente/release corretos e PII padrão desligada | **verificado com ressalva** | `send_default_pii=False`, env/release dos settings, `before_send`; MAS default de consentimento = nada é enviado (MINOR-10) e init engole erro (MINOR-9) |
| 21 | logs JSON pesquisáveis por request ID, release, serviço, nível | **verificado** | campos no formatter JSON + filtro no handler `console` |
| 24 | retenção 12 meses: brutos + agregados, idempotente, auditável | **verificado** | testes de expurgo; único agregado em cache é invalidado |
| 25 | payload com tipo desconhecido/campo a mais/token → rejeitado, redigido ou descartado **com sinal técnico** | **verificado** (MINOR-6) | 400/202 + `registrar_recusa` + métricas; `consent_token` nunca persistido |
| 26 | token ausente/inválido/expirado → evento não persistido | **verificado** | fail-closed em todas as combinações que testei |
| 27 | consentimento técnico recusado → nenhum envio externo | **verificado** | `before_send`/`before_send_transaction` retornam `None` + contador de descarte |
| 28 | query string sensível, `Authorization` e PII omitidos/mascarados no log | **parcial** (MINOR-1, MINOR-2) | baseline forte (allowlist no payload, redator no log/Sentry); furos pontuais em `Basic`/2º cookie e no modo verbose |

**Restrições técnicas de privacidade auditadas:** fail-closed do consentimento ✔;
redação obrigatória — **parcial** (MINOR-1/2/3); sem secret em log/fixture/dashboard ✔
(nenhum literal de segredo nos testes; tokens de teste são obviously-fake);
token de consentimento assinado e rotacionável ✔ (rotação testada, revogação real);
"código não deve fingir aprovação jurídica" — não encontrei texto de consentimento/privacidade
neste diff (backend); sampling de traces 10% ✔ (`SENTRY_TRACES_SAMPLE_RATE` default 0.1,
clampado); baixo overhead — **parcial** (MAJOR-2/MINOR-8).

---

## Recomendações de sequência

1. **Bloqueadores de merge barata:** MAJOR-1 (`NUM_PROXIES`/nginx) + MAJOR-2 (allowlist de
   método) + MINOR-3 (compare em bytes) + MINOR-4 (comentário) + NIT-8 (`v` int).
2. **Critérios em aberto:** MAJOR-3 (beat) e MAJOR-4 (métricas de job) — decidir se o
   backend entrega ou se o fecha fica no bloco de infra; registrar isso no contrato.
3. **Qualidade de sinal:** MINOR-5, MINOR-6, MINOR-9 (nomes/semântica de métrica e log de
   init), MINOR-11.
4. **Rever na revisão completa:** a exposição dos endpoints depende de o nginx **não**
   rotear `/metrics`, `/livez`, `/readyz`, `/health-detail` (verifiquei o estado atual dos
   arquivos versionados, mas a run `20260925-1433-go-live-producao` está mexendo em
   `infra/DEPLOY.md` e `scripts/release/`); e se o frontend realmente envia
   `X-Technical-Consent` e consome `X-Consent-Token`/`X-Request-ID` nos Criteria 1, 2, 5, 6.

**Nada foi alterado no repositório.** Este arquivo é o único artefato escrito por esta
revisão; `run-state.json` não foi tocado.
