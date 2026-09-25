<!--
CONTRACT: remediation-report (remediador)
DONO: remediador da run 20260925-1020-observabilidade
QUANDO: depois da code-review-backend.md (veredito request_changes, 0 blockers / 4 majors)
-->

# Remediação do backend — run 20260925-1020-observabilidade

Escopo: **backend** (`backend/config`, `backend/metricas`). Correções dos achados
de `code-review-backend.md` (veredito `request_changes`, 0 blockers, 4 majors).
Nenhum arquivo de `.github/`, `frontend/`, `infra/`, `docker-compose*`, `.env*`,
`CI-CD.md`, `PROD_DECISOES.md`, `infra/DEPLOY.md`, `scripts/` ou de outra run foi
tocado — outro agente está em `.github/`, `infra/` e `frontend/` agora. Nenhum
`git add`/`commit` foi executado. O relatório do reviewer **não** foi editado.

Ambiente: `backend/.venv/bin/python` (Python 3.14.4),
`DJANGO_SETTINGS_MODULE=config.settings_test` (pytest), `DJANGO_DB_ENGINE=sqlite3`.

---

## 1. Resumo do que mudou

| # | Achado | Status | Onde |
|---|---|---|---|
| MAJOR-1 | Throttle do emissor contornável por `X-Forwarded-For` | **corrigido** (2 camadas) | `config/proxies.py` (novo), `config/throttling.py`, `config/settings.py` |
| MAJOR-2 | Rótulo `method` controlado pelo cliente; séries legítimas somem; scrape caro | **corrigido** | `config/metrics.py`, `config/middleware.py` (sem mudança), `config/celery.py` |
| MAJOR-3 | Beat parado não vira degradação no default (critério 16) | **corrigido** (fail-closed) | `config/health.py`, `config/settings_test.py` |
| MAJOR-4 | Métricas de task Celery/expurgo invisíveis (critério 14) | **corrigido o que é possível nesta arquitetura**; resto documentado | `config/job_state.py` (novo), `config/celery.py`, `config/health.py`, `config/observability_views.py` |
| MINOR-1 | `Authorization: Basic <cred>` e 2º cookie escapando | **corrigido** | `config/observability.py` |
| MINOR-2 | `\n`/`\r` sobrevivendo a `redact_text` | **corrigido** (log de 500 + formatter de texto) | `config/observability.py`, `config/middleware.py`, `config/settings.py` |
| MINOR-3 | Bearer não-ASCII → 500 | **corrigido** | `config/observability_views.py` |
| MINOR-4 | `any()` faz curto-circuito e o comentário afirma o contrário | **corrigido** (comentário **e** código) | `metricas/consent.py` |
| MINOR-5 | `rows=<contagem>` como rótulo | **corrigido** (com ressalva, ver §2.5) | `metricas/tasks.py` |
| MINOR-6 | "Eventos rejeitados" contando evento persistido | **corrigido** | `metricas/views.py` |
| MINOR-9 | `except: pass` no init do Sentry | **corrigido** | `config/observability.py`, `config/settings.py` |
| NIT-1 | Teste duplicado em `test_consent_token.py` | **corrigido** | `metricas/tests/test_consent_token.py` |
| NIT-2 | `assert status in {"degraded","ok"}` que não falha | **corrigido** | `config/tests/test_health_checks.py` |
| NIT-7 | WARNING por requisição em proxy mal configurado | **corrigido** | `config/proxies.py` |
| NIT-8 | `v: 1.0` aceito | **corrigido** | `metricas/consent.py` |
| MINOR-7, MINOR-8, MINOR-10, MINOR-11, MINOR-12, NIT-3, NIT-4, NIT-5, NIT-6 | — | **não corrigidos, conscientemente** | ver §4 |

---

## 2. Achados corrigidos

### 2.1 MAJOR-1 — o throttle do emissor de token era decorativo

**Causa raiz.** O balde do rate limit era escolhido pelo próprio cliente, em duas
camadas independentes:

1. `SimpleRateThrottle.get_ident` do DRF, **sem** `NUM_PROXIES`, devolve
   `''.join(xff.split())` — o `X-Forwarded-For` **cru**. Os nginx versionados
   (`infra/nginx/portal-*.conf`) não definem esse header, então o valor chegava
   intacto.
2. Nada no resto do projeto decidia *quem* é o cliente: a única lista de redes de
   confiança que existia (`config/observability_views._redes_confiaveis`) servia
   ao gating de `/health-detail` e `/metrics` e não tinha relação com o throttle.

Como a issuing endpoint (`ConsentimentoTokenView.post`) aceita qualquer `sessao`
e não grava nada, o resultado era exatamente o que o comentário do código
descrevia e não impedia: um coletor de dados com o carimbo do site.

**Correção (duas camadas, nenhuma delas suficiente sozinha).**

- `backend/config/proxies.py` (novo, 150 linhas) — fonte única de "quem é
  confiável", já usada pelo gating de observabilidade e agora pelo throttle:
  - `redes_confiaveis()` (linha 69) — allowlist de `OBSERVABILITY_TRUSTED_PROXY_NETWORKS`,
    fail-closed (valor não parseável é ignorado, nunca aproximado) e **um aviso
    por valor inválido por processo** (NIT-7), em vez de um por requisição;
  - `identificar_cliente(request)` (linha 118) — o balde é o `REMOTE_ADDR`
    (par real); `X-Forwarded-For` **só** é lido quando o par é loopback ou uma
    rede declarada, e só o **último** elemento (que é o que o proxy confiável
    anexou) entra no balde. `Host`/`X-Forwarded-Host` nunca são consultados.
- `backend/config/throttling.py:36` — mixin `_IdentidadePorParReal.get_ident`
  aplicado às **quatro** throttles anônimas do projeto
  (`escrita_publica`, `auth_sensivel`, `enderecos`, `consentimento`).
  `DenunciaUserThrottle` (linha 76) **não** recebe o mixin de propósito: lá o
  balde é `request.user.pk`, e trocar por IP daria a um usuário o balde de todo
  mundo atrás do mesmo proxy.
- `backend/config/settings.py:400` — `"NUM_PROXIES": 0` no `REST_FRAMEWORK`:
  o default do DRF passa a ser "confie em **nenhum** header de proxy"
  (fail-closed), e a exceção explícita fica só no código, onde é testável.

**Não reintroduz bypass por `Host`/`X-Forwarded-Host`:** nenhum dos dois entra na
decisão (há teste com `Host: 127.0.0.1` + `X-Forwarded-Host: 127.0.0.1` +
`X-Forwarded-For: 127.0.0.1` de IP externo → mesmo balde, 429 no limite).

**Dependência de infra (não é do backend, e está escrita no código):** o proxy
confiável precisa **anexar ou sobrescrever** `X-Forwarded-For` com o endereço
real. O default do Nginx (`$proxy_add_x_forwarded_for`) e `$remote_addr` atendem;
um proxy que repassasse o header do cliente sem tocar nele reabriria o bypass
para quem estivesse na rede do proxy. Ver §5.

**Testes que provam (falham sem o fix — ver §3).**

- `metricas/tests/test_consent_ingestao.py::test_emissao_nao_e_contornavel_girando_x_forwarded_for`
  — o ataque do reviewer, ponta a ponta: 40 POSTs com `X-Forwarded-For`
  rotacionado, par externo não declarado → 30×`201` + 10×`429`.
- `metricas/tests/test_consent_ingestao.py::test_emissao_respeita_o_teto_por_cliente_atras_de_proxy_declarado`
  — o outro lado: atrás de proxy declarado, cada cliente real tem o seu balde e
  o mesmo cliente continua sendo barrado (a correção não vira "30/min para o
  site inteiro").
- `config/tests/test_proxies.py` (novo, 14 testes) — a regra em si: XFF forjado
  não muda o balde, `Host` forjado não abre nada, XFF vazio cai no par, proxy
  declarado usa o último elemento, configuração inválida é ignorada com um aviso
  só, par inutilizável não gera balde novo por requisição, e
  `test_toda_throttle_anonima_do_projeto_ignora_o_xff_de_par_externo` amarra a
  regra nas quatro classes de throttle (com o `api_settings.NUM_PROXIES` do DRF
  posto em `None` de propósito, senão o teste provaria o setting e não a classe).
- `config/tests/test_throttling.py::TestIdentidadeDoClienteNaoEEscolhidaPorQuemChama`
  — o mesmo bypass num escopo **pré-existente** (`auth_sensivel`, o login):
  brute force com XFF rotacionado e com `Host`/`X-Forwarded-Host` forjados é
  barrado no limite.

### 2.2 MAJOR-2 — rótulo controlado pelo cliente, séries legítimas sumindo, scrape caro

**Causa raiz.** Três defeitos no mesmo lugar:

1. `record_http` rotulava `method` com `str(request.method)[:16]`. `request.method`
   é o token da linha de requisição, controlado pelo cliente, e o parser HTTP
   aceita qualquer token: cada scanner criava **duas** séries (counter +
   histograma) e envenenava o rótulo que o operador filtra.
2. O teto de séries era **global**: quando a família barulhenta estourava
   `MAX_SERIES`, qualquer série nova — inclusive `portal_ready`, a profundidade de
   uma fila nova, `portal_http_requests_total` — era **descartada em silêncio**
   (só subia `portal_metrics_series_dropped_total`). O reviewer perdeu
   `portal_http_requests_total` exatamente assim.
3. O histograma **guardava observações** (`MAX_OBSERVATIONS = 10 000` por série) e
   o `render_prometheus` copiava e recontava tudo **dentro do lock** do registry a
   cada scrape (medido pelo reviewer: 0,89 s e 33 MB por scrape em 200 séries ×
   10 000 obs; no teto, ~1,6 GB de floats e minutos de lock com todas as
   requisições do processo aguardando).

**Correção (`backend/config/metrics.py`).**

- Allowlist de vocabulário no ponto de entrada:
  `normalizar_metodo` (linha 74) — `GET/POST/PUT/PATCH/DELETE/HEAD/OPTIONS/TRACE`
  (case normalizada para maiúsculas, para que um `get` minúsculo dobre em `GET`
  em vez de criar série), qualquer outro token → `other`;
  `normalizar_status` (linha 81) — só código HTTP de três dígitos, resto → `other`;
  `normalizar_rota` (linha 91) — truncamento (o vocabulário vem do URLconf e já
  chega colapsado em `unmatched` pelo middleware). `record_http` (linha 511) é o
  único caminho de produção e usa os três.
- Teto **por família** (`MAX_SERIES_POR_METRICA = 500`, linha 53) antes do teto
  global: a família de alta cardinalidade não pode mais comer o orçamento inteiro
  e derrubar as métricas de sistema. O global (`MAX_SERIES`) continua como rede
  de segurança para quem espalha por muitas famílias. O próprio contador de
  descarte também tem teto (`MAX_SERIES_DESCARTE = 200`, linha 70) — senão a
  métrica que existe para o teto ser visível seria o novo lugar onde ele estoura.
- Histograma com **buckets acumulados na observação** (`observe`, linha 183;
  `render_prometheus`, linha 270): `observe` custa O(#buckets), o render só lê
  contadores prontos e a cópia dentro do lock é de dicionários pequenos. Nenhuma
  lista de observações sobrevive; `MAX_OBSERVATIONS` saiu do módulo.
  Semântica de bucket cumulativo preservada (`le` maior inclui os valores dos
  `le` menores) e o recorte de buckets é fixado na primeira observação da série
  (misturar populações no mesmo `_count` mentiria).
- O resto dos rótulos foi examinado pela mesma lente e **não** precisa de
  allowlist: `route` vem do URLconf (código) e já é colapsado em `unmatched`;
  `status` vem de `int(status_code)`; `task`/`result` vêm do registro de tasks e
  do vocabulário fechado do Celery; `reason` vem de vocabulários fechados
  (`health`, `consent`); `model` do expurgo são três nomes fixos. O único rótulo
  com cardinalidade de dado era `rows` do expurgo (MINOR-5, §2.5).

**Testes que provam.**

- `test_method_forjado_vira_other_e_nao_cria_serie_nova` — 50 métodos forjados
  → **uma** série `method="other"`, nenhum vestígio de `ZZZ` na exposição.
- `test_metodos_http_reais_passam_pela_allowlist`,
  `test_status_que_nao_e_codigo_http_nao_cria_serie_no_caminho_normal` (pelo
  `record_http`, que é o caminho real), `test_rota_e_truncada_e_nunca_vazia`.
- `test_familia_farta_nao_derruba_metricas_de_sistema` — 5 100 séries barulhentas
  e ainda assim `portal_ready`, `portal_celery_queue_depth` e a série já existente
  estão na exposição (é a reprodução do que o reviewer perdeu).
- `test_teto_global_continua_valendo_entre_familias`,
  `test_descarte_nao_cria_serie_nova_para_cada_nome_de_metrica`.
- `test_histograma_acumula_buckets_e_nao_guarda_observacoes`,
  `test_buckets_acumulados_preservam_a_semantica_cumulativa`,
  `test_scrape_nao_custa_mais_que_as_series_existentes` (20 000 observações: o
  snapshot só tem `limits/counts/total/soma`).
- `config/tests/test_observability_middleware.py` (inalterado): o
  `ROUTE_UNMATCHED` continua colapsando path não resolvido.

### 2.3 MAJOR-3 — beat parado não virava degradação (critério 16)

**Causa raiz.** `check_celery_beat` devolvia `not_configured` sem
`OBSERVABILITY_BEAT_HEARTBEAT_FILE`, e a agregação excluía
`{"ok", "disabled", "not_configured"}` de `optional_bad`. Resultado com a
configuração default: `status="ok"`, `degraded=False`, sem
`X-Operational-State: degraded`, sem `portal_health_degraded_total`, sem alerta —
num componente que existe precisamente para não sumir. O comentário do Bloco A já
dizia "visível, **nunca** verde por omissão"; a agregação desmentia o comentário.

**Correção (`backend/config/health.py`).**

- `CHECKS_SEM_SINAL_PROPRIO` (linha 57) — allowlist explícita dos checks em que
  `not_configured` é **ponto cego**, não escolha de ambiente: `celery_beat` (sem
  heartbeat não há como saber se o beat disparou) e `celery_jobs` (§2.4). `redis`
  e `collector_disk` **não** entram: `not_configured` neles significa "cache local
  em desenvolvimento", que é escolha declarada, não cegueira.
- `_e_degradante(result)` (linha 379) é a **única** função que decide o peso de um
  check opcional no agregado, usada tanto por `snapshot()` quanto por
  `degraded_state()` — antes havia a lista inline duplicada nos dois, que é
  exatamente como o defeito se escondeu.
- Ponto cego também é **número**: `_timed` publica
  `portal_health_check_not_configured{check=<nome>}` (linha 102) = 1 quando o check
  está `not_configured`. Sem isso, "não há como observar" e "está tudo bem"
  seriam o mesmo número no scrape.
- Coerente com o Bloco C1: o produtor do heartbeat é
  `infra/systemd/celery-beat-heartbeat@.service`, cujo `ExecCondition` consulta a
  unit do beat antes de escrever (beat parado ⇒ arquivo envelhece ⇒ `degraded`).
  Com o arquivo configurado, o comportamento de "beat parado" é o que o Bloco C1
  projetou; o que faltava era o "não configurado" não virar verde.
- `/readyz` **não** é afetado (`include_optional=False`): dependência opcional
  continua sendo degradação, não indisponibilidade.
- `backend/config/settings_test.py` cria os dois arquivos (heartbeat e estado de
  job) em `tempfile.gettempdir()`, com comentário explicando por quê: a suíte não
  sobe beat nem worker, e "não configurado" passou a ser degradação — o que
  contaminaria todo teste que olha `X-Operational-State`, que não é sobre beat.

**Testes que provam.**

- `test_beat_sem_heartbeat_configurado_e_degradacao_agregada` — o achado exato:
  com os dois canais vazios, `reasons` contém `celery_beat:not_configured`, o
  estado é `degraded`, `snapshot()` é `degraded` **e** `ready=True` (readiness
  não cai), e o detalhe mostra o `not_configured`.
- `test_job_sem_canal_configurado_e_degradacao_agregada` — o mesmo para o canal
  de job, com o beat saudável.
- `test_check_sem_sinal_proprio_configurado_volta_a_ok` — o inverso: com
  heartbeat e estado de job atuais, o agregado volta a `ok` (senão o alerta seria
  ruído permanente).
- `test_ponto_cego_vira_metrica_alertavel` — o gauge sai com 1 para
  `celery_beat` e `celery_jobs`.

### 2.4 MAJOR-4 — métricas de task Celery e de expurgo invisíveis (critério 14)

**Causa raiz.** `config/metrics.py` é um registro **por processo** e o `/metrics`
é servido pelo processo **web**. `record_celery` roda no **worker** e o expurgo é
disparado pelo **beat**: nenhum dos dois serve `/metrics`. Logo
`portal_celery_tasks_total`, `portal_celery_task_duration_seconds` e
`portal_analytics_purge_*` não apareciam em **nenhum** scrape. Além disso não
existia métrica de **atraso** (o critério 14 pede "fila, atraso, retry, falha e
duração") e `portal_celery_queue_depth` só era atualizado quando alguém chamava
`/health-detail`.

**Correção — canal durável de job (`backend/config/job_state.py`, novo, 232 linhas).**

Escolha de canal: **arquivo de estado em disco**, o mesmo padrão que o Bloco A/C1
já aceitou para o heartbeat do beat, em vez de tabela de domínio (exigiria
migration, e `feed`/`catalogo_noticias` estão sob WIP de outra run) e em vez de
Pushgateway/exporter (exigiria bloco de infra). Decisão registrada no docstring do
módulo, com o motivo e o **limite** do que ele entrega.

- Produtor (worker): `registrar_task(nome, resultado, duracao)` (linha 152) e
  `registrar_retry(nome)` (linha 178), gravados atomicamente (`write` em
  temporário + `os.replace`, linha 111) sob `RLock`; nenhuma exceção escapa para
  o worker, e o estado é limitado a 200 nomes de task.
  Chamados de `config/celery.py`: `task_postrun` (linha 77, com o `record_celery`
  de processo que continua existindo) e o sinal `task_retry` (linha 86, novo —
  retry é um dos sinais que o critério 14 exige e não era contável).
- Consumidor (processo web): `publicar_metricas()` (linha 193) publica, do estado
  absoluto lido do arquivo:
  `portal_job_tasks_recorded{task,result}`,
  `portal_job_task_retries_recorded{task}`,
  `portal_job_task_duration_seconds_sum{task}`,
  `portal_job_task_duration_seconds_count{task}`,
  `portal_job_task_idle_seconds{task}` — **o sinal de atraso que o contrato
  pedia** (segundos desde o último término **bem-sucedido**; `-1` = a task
  nunca terminou bem, para não parecer saudosa) — e
  `portal_job_state_age_seconds` (frescor do próprio canal).
  São **gauges com valor absoluto**, não contadores incrementados: o produtor é
  outro processo, então somar por `instance` (o padrão do projeto para counters)
  multiplicaria o mesmo número. Está escrito no `# HELP` e no docstring
  ("use `max()`/`last()`, nunca `sum()` nem `rate()`").
- Ponto de publicação: no `check_celery_jobs` (`health.py:245`, que também publica
  as métricas) **e** no scrape (`observability_views.py:199`) — um scrape é um dos
  momentos em que o operador precisa do dado, e o processo pode não ter atendido
  requisição nenhuma desde o último scrape (tráfego baixo, probe que só bate em
  `/readyz`).
- `check_celery_jobs` também fecha o critério 16 para o canal: `not_configured` /
  arquivo ausente / arquivo velho > `OBSERVABILITY_JOB_STATE_MAX_AGE_SECONDS` (900 s)
  → degradação, nunca `ok` por omissão.

**O que fica cross-process e por quê (documentado no docstring do módulo):** o
histograma por task (`portal_celery_task_duration_seconds`) e o contador por task
(`portal_celery_tasks_total`) continuam no processo worker. Expor métrica de outro
processo exige um exporter no worker (Pushgateway ou porta própria) e isso é do
bloco de infra; o que o canal durável entrega é o **agregável** (`_sum`/`_count`),
a **frescor** e a contagem por resultado, que é a maior parte do alerta de "job
travado". Preferi expor metade do sinal honestamente a fingir o todo — o
achado original é justamente "métrica que não existe em nenhum scrape".

Settings novas: `OBSERVABILITY_JOB_STATE_FILE` (vazio = canal desligado),
`OBSERVABILITY_JOB_STATE_MAX_AGE_SECONDS` (900) — `config/settings.py:543`.

**Testes que provam.**

- `config/tests/test_job_state.py` (novo, 10 testes):
  `test_task_terminada_e_publicada_para_o_processo_que_expoe_metrics` (todas as
  séries + "nada de dado pessoal" no arquivo), `test_atraso_de_job_e_a_idade_do_ultimo_sucesso`
  (o sinal de atraso, incluindo o caso "só falhou" = `-1`),
  `test_escrita_e_atomica_e_acumula_por_task` (sem `.tmp-*` sobrando),
  `test_sem_canal_configurado_nao_inventa_sinal`,
  `test_check_de_job_reporta_cada_estado_do_canal` (`not_configured`/`error`/`ok`/`stale`),
  `test_arquivo_corrompido_e_erro_e_nao_explode`,
  `test_metrica_de_job_aparece_no_scrape_do_processo_web` (chama a **view**
  direto, sem middleware e sem probe — é o caminho do scrape),
  `test_metrica_de_job_aparece_no_scrape_ponta_a_ponta` (via HTTP, e o gating
  continua negando IP externo),
  `test_worker_registra_o_fim_de_task_no_canal` (sinais Celery reais: `postrun`
  + `retry`), `test_nome_de_task_dinamico_nao_cresce_o_arquivo_sem_teto`.

### 2.5 MINOR-5 — `rows` como rótulo (com uma armadilha do caminho sugerido)

**Causa raiz.** `METRICS.inc("portal_analytics_purge_deleted_total", model=nome,
rows=total)`: a contagem era rótulo, então três execuções com 0/1234/1235 linhas
criavam três séries do mesmo contador, e o alerta por `rows` não agregava nada.

**Correção** (`metricas/tasks.py:128`): a contagem é o **valor** do contador e o
rótulo é só `model`.

> **Ressalva importante:** a correção literal sugerida na revisão
> (`METRICS.inc(..., value=total, model=nome)`) **não funciona** neste registry e
> teria passado silenciosamente: o segundo parâmetro de
> `MetricsRegistry.inc(self, name, value=1, **labels)` chama-se `value`, então
> `value=total` vira incremento e **não** rótulo — a série sairia como
> `{model="..."}` com o incremento errado, sem nenhum sintoma. A forma correta é o
> valor posicional: `METRICS.inc("portal_analytics_purge_deleted_total", total, model=nome)`.
> O comentário no código registra isso para quem "corrigir" de novo.

**Testes que provam:** `test_contagem_de_linhas_e_valor_e_nao_rotulo` (nenhum
`rows=`, uma série por modelo, valor = contagem) e
`test_contagem_acumula_entre_execucoes` (3 + 2 = 5 na mesma série — contador
cumulativo, que é o que alerta de "o expurgo parou").

### 2.6 MINOR-1, MINOR-2, MINOR-3 — redação e negação limpa

- **MINOR-1** (`config/observability.py`): `_AUTH_SCHEME` (linha 92) cobre
  `Bearer`/`Basic`/`Token` com credencial, e `_HEADER_VALUE` (linha 109) consome
  **até o fim da linha** o valor de `authorization`, `proxy-authorization`,
  `cookie` e `set-cookie` — são os quatro em que `[^\s,;&]+` parava cedo demais
  (a credencial base64 e o 2º par de cookie sobreviviam). O custo aceito está
  escrito no comentário: uma linha que mencione "cookie:" perde o resto.
  `test_log_nao_contem_email_authorization_token_ou_query_sensive` foi adaptado
  (o resto da linha agora é redigido **com** o header, o que é mais forte), e a
  força original do teste foi preservada em
  `test_log_redige_atribuicoes_sem_header_de_credencial` (as outras regras
  contam quando não há header) e
  `test_redact_text_preserva_o_resto_da_linha_quando_nao_ha_header`.
  `test_header_com_credencial_nao_deixa_valor_escapar` cobre os quatro casos
  (`Basic` maiúsculo/minúsculo, cookie com separador por espaço, `Set-Cookie`).
- **MINOR-2** (`config/observability.py`, `config/middleware.py`,
  `config/settings.py`): `redact_single_line` (linha 232) aplica a redação e
  achata CR/LF/TAB em escape visível; `RedactingTextFormatter` (linha 509) usa
  isso na **mensagem** e redige o `formatException` (o traceback continua
  multilinha — quebrá-lo destruiria a legibilidade do modo texto, e é ele que
  está sendo preservado de propósito). O modo `verbose` deixou de ser um
  `logging.Formatter` cru (`settings.py:1090`): a redação, declarada como última
  barreira, simplesmente **não existia** nesse caminho. O log do 500 passou a
  usar `redact_single_line(safe_path(request.path))`
  (`middleware.py:230`) — antes o `request.path` ia cru.
  Testes: `test_redact_single_line_achata_quebra_de_linha`,
  `test_formatter_de_texto_redige_e_nao_quebra_linha`,
  `test_formatter_de_texto_configurado_redige_e_nao_quebra_linha` (formata pelo
  **formulário resolvido do setting** — é o ligamento que quebrava, não a classe),
  `test_formatter_de_texto_preserva_traceback_multilinha`,
  `test_log_do_500_nao_aceita_path_forjado` e
  `test_log_do_500_nao_vaza_query_string`.
- **MINOR-3** (`config/observability_views.py:78`): `secrets.compare_digest` em
  **bytes** (`valor.strip().encode("utf-8")`), porque a função só aceita `str`
  ASCII e um `Authorization` não-ASCII levantava `TypeError` → 500 + evento no
  Sentry. Teste parametrizado para `/health-detail` e `/metrics`: 404 com o corpo
  genérico, nos dois casos.

### 2.7 MINOR-4, MINOR-6, MINOR-9 e NITs

- **MINOR-4** (`metricas/consent.py:468`): laço explícito com `|=` (sem
  curto-circuito) **e** comentário corrigido — o agora verdadeiro. O teste
  `test_rotacao_percorre_todas_as_chaves_sem_curto_circuito` espiona
  `_assinatura` e exige que a chave ativa **e as duas anteriores** sejam
  avaliadas; com o `any()` original ele falha. Contraprova:
  `test_rotacao_aceita_token_assinado_pela_chave_anterior` (a rotação continua
  funcionando).
- **MINOR-6** (`metricas/views.py:200`): removido o `inc` de
  `portal_analytics_events_rejected_total` para campo em excesso — o evento **é**
  persistido e o descarte já é contado em
  `portal_analytics_payload_fields_dropped_total` dentro de `sanear_payload`.
  `test_campo_em_excesso_e_descartado_e_nao_persiste` passou a exigir que o
  contador de recusa **não** apareça na exposição naquele caso.
- **MINOR-9** (`config/observability.py:362`, `config/settings.py:1176`): o
  `except Exception` do `init` do Sentry chama
  `reportar_falha_de_init_sentry(exc)`, que avisa em WARNING (só o **tipo** da
  exceção — DSN e traceback podem carregar segredo) e conta
  `portal_sentry_init_failed_total{error=<Tipo>}`. O único sinal anterior
  (`portal_sentry_events_dropped_total`) não subia, porque não houve init. A função
  foi extraída para poder ser testada sem reimportar `settings`.
- **NIT-1**: a segunda definição (idêntica) de `test_sujeito_invalido_nao_e_emitido`
  foi removida.
- **NIT-2** (`test_health_checks.py`): `assert resultado.status in {"degraded","ok"}`
  virou `!= "ok"` com o motivo (a fila sem leitura possível não pode virar `ok`).
- **NIT-7** (`config/proxies.py`): o WARNING de rede inválida sai **uma vez por
  valor** por processo (conjunto `_avisados`), não a cada requisição.
- **NIT-8** (`metricas/consent.py:418`): `v` tem de ser `int` de verdade
  (`bool` e `float` barrados antes da comparação). `test_claim_v_com_tipo_frouxo_e_recusado`
  cobre `1.0`, `"1"`, `True` e `None`.

---

## 3. Prova de regressão (o teste falha sem o fix)

Não é "ajustei e passou": cada fix foi **revertido em memória** (um a um, arquivo
restaurado em seguida — nada foi gravado no repositório) e o teste
correspondente foi rodado. Script: `/tmp/opencode/prova_regressao.py`
(26 casos; o harness é descartável e fica fora do repositório, como o do
reviewer).

```console
$ cd backend && python3 /tmp/opencode/prova_regressao.py
OK [quebra  ] MAJOR-1: baseline do reviewer (classe sem o mixin + DRF no padrao cru)
      metricas/tests/test_consent_ingestao.py::test_emissao_nao_e_contornavel_girando_x_forwarded_for -> quebra sem o fix
OK [quebra  ] MAJOR-1: so a classe volta ao padrao do DRF (NUM_PROXIES neutralizado)
      config/tests/test_proxies.py::test_toda_throttle_anonima_do_projeto_ignora_o_xff_de_par_externo -> quebra sem o fix
OK [aguanta ] MAJOR-1: so o NUM_PROXIES volta a None (a classe segura sozinha)
      config/tests/test_proxies.py::test_toda_throttle_anonima_do_projeto_ignora_o_xff_de_par_externo -> continua passando
... (MAJOR-2 x4, MAJOR-3 x2, MAJOR-4 x4, MINOR-1/2 x4, MINOR-3/4/5/6/9, NIT-1/2/7)
26 casos verificados: cada fix tem teste que depende dele.
```

O caso `aguenta` é informação, não desculpa: a correção do MAJOR-1 tem **duas**
camadas e cada uma segura sozinha (defesa em profundidade) — remover só uma não
quebra nada, remover as duas quebra.

Evidência direta com os **settings de produção** (`config.settings`, sem
override), script `/tmp/opencode/evidencia_producao.py`:

```console
$ cd backend && .venv/bin/python /tmp/opencode/evidencia_producao.py
=== MAJOR-1: emissor de token de consentimento ===
NUM_PROXIES: 0
taxa: 30/min
40 POSTs com XFF rotacionado -> [201, 201, ... (30x 201) ..., 429, 429, 429, 429, 429, 429, 429, 429, 429, 429]
201: 30 429: 10

=== MAJOR-3: estado agregado com a configuracao default ===
OBSERVABILITY_JOB_STATE_FILE: ''
check_celery_beat -> error            (arquivo do .env aponta para caminho inexistente aqui)
check_celery_jobs -> not_configured
degraded_state -> {'status': 'degraded', 'reasons': ('celery:degraded', 'celery_beat:error', 'celery_jobs:not_configured')}
GET /readyz -> 200 {"status": "ready", "ready": true}
X-Operational-State: degraded
   portal_health_check_not_configured{check="celery_jobs"} 1
   portal_health_check_not_configured{check="redis"} 1        (dev: locmem — NÃO degrada, por escolha)
```

O baseline do reviewer era 40×`201` e zero `429`; agora são 30×`201` + 10×`429`.

---

## 4. Achados **não** corrigidos (com o motivo)

Nada aqui é "não deu tempo": cada item é uma decisão, e o motivo de cada decisão
é o mesmo para quem ler daqui a seis meses.

| Achado | Decisão | Motivo |
|---|---|---|
| **MINOR-7** — `X-Release`/`X-Environment` em toda resposta, inclusive negadas e 404 | **mantido** | Decisão **deliberada** do Bloco A (o comentário do `CORS_EXPOSE_HEADERS` explica o uso no código de suporte) e o reviewer concordou ("não é blocker; registrei para decisão explícita"). Remover agora é decisão de produto/segurança que cabe ao dono do produto, não a uma remediação. Se a decisão for por remover, é uma linha em `_add_response_headers` + teste. |
| **MINOR-8** — o probe de degradação segura `_degrade_lock` durante I/O de rede | **não corrigido** | O cenário real exige um Redis que *blackholeia* (não recusa) e a topologia implantada é Redis em localhost, que recusa na hora. A correção sugerida (probe fora do lock) troca "lock durante I/O" por "N threads sondando ao mesmo tempo" — thundering herd numa dependência que **toda requisição** consulta. Risco de indisponibilidade maior que o problema. Fica registrado como dívida de latência, não de correção. |
| **MINOR-10** — exceção de task Celery não chega ao Sentry com o consentimento default | **não corrigido (decisão de privacidade)** | A sugestão do reviewer (`set_technical_consent(True)` no `task_prerun`) faria o worker enviar **sempre**, contrariando o fail-closed do critério 27 ("ausência de consentimento não pode gerar envio"). O que é verdade é que o operador precisa **ligar** `SENTRY_TECHNICAL_CONSENT_DEFAULT=true`; com a flag ligada, o evento de task já passa (o `before_send` aceita o default e o `task_id` entra como tag — `test_task_id_do_celery_entra_no_evento_do_sentry`). É documentação de operação (runbook), não código. |
| **MINOR-11** — `POST /api/metricas/eventos/` sem throttle | **não corrigido (decisão deliberada do Bloco A2, risco 3)** | O histórico registra: "**Não** throttlei a ingestão de propósito: `page_view` em rajada é uso legítimo e um limite por IP quebraria o tracking de navegação real. O freio correto seria por sujeito (`sub`), não por IP — pendência para o Bloco B/infra". Um limite por IP aqui reintroduziria o problema que o MAJOR-1 expôs (NAT/egress corporativo = balde compartilhado) em um endpoint de alto volume legítimo. A correção do MAJOR-1 não muda esse argumento. |
| **MINOR-12** — critério 17 parcial: só os *probes* de health são instrumentados, não as chamadas externas reais (Resend, ViaCEP/IBGE, fetch de feed) | **não corrigido (escopo de remediação)** | Instrumentar `config/email_resend.py` e `enderecos/` é **escopo novo** (a revisão já o classificou fora do diff), e a tarefa do remediador é corrigir achado, não ampliar escopo. O gancho já existe e é reaproveitável: `record_dependency(name, ok, duration)` em `config/metrics.py:520` é a mesma função que `health._timed` usa. Fica como pendência de bloco próprio. |
| **NIT-3** — `is_sensitive_key` é denylist (`mail`, `user`, `login`, `senhaAntiga` não são sensíveis) | **não corrigido** | O reviewer confirmou que **não há hoje** nenhum `logger.*` que imprima e-mail/usuário sem rótulo: é profundidade defensiva, não vazamento. Converter para allowlist é um refactor de comportamento com risco de falso positivo (esconder diagnóstico), e a proteção que realmente importa está no **caminho de entrada** (payload com allowlist, `redact_text`, e agora `_HEADER_VALUE`/`_AUTH_SCHEME`). |
| **NIT-4** — `X-Request-ID` do cliente pode colidir em `EventoBusca.request_id` (`unique`) e perder o evento de busca em silêncio | **não corrigido (pré-existente + arquivo de outra run)** | Colisão em coluna `unique` é pré-existente ao diff e a correção mexe em `feed/busca.py`, que está no raio do WIP de outro agente nesta sessão. Registrar aqui para o dono de `feed`. |
| **NIT-5** — importar `config.*` antes do `django.setup()` define `DJANGO_SETTINGS_MODULE=config.settings` (`config/celery.py:15`) | **não corrigido (pré-existente)** | É armadilha de ambiente de teste, não defeito de produto, e mexer nisso agora quebraria o `celery` (que depende do `setdefault`). Os módulos novos (`proxies.py`, `job_state.py`) **não** trazem esse padrão. Anotado para quem medir cobertura por módulo. |
| **NIT-6** — `_eh_staff` autoriza por `is_staff`/`is_superuser`, o resto do projeto por `papel == "admin"` | **não corrigido** | Os dois lados falham fechados no lado perigoso e a coerência com o restante do projeto é decisão de produto (papel × flag do Django) que atravessa `PainelMetricasView`/`CentralInteligenciaView` — fora deste diff. |

---

## 5. Pendências para o bloco de infra (não são do backend, e são bloqueantes de operação)

1. **`proxy_set_header X-Forwarded-For`** no nginx: a regra de
   `config/proxies.py` só lê o header quando o par é **declarado** como proxy
   confiável e usa o **último** elemento. O default do Nginx
   (`$proxy_add_x_forwarded_for`) e `$remote_addr` atendem; um proxy que
   repassasse o header do cliente sem tocar nele reabriria o bypass. Está
   escrito no docstring de `config/proxies.py`.
2. **`OBSERVABILITY_JOB_STATE_FILE`** na env do worker
   (`/etc/portal/celery-<amb>.env`, a mesma que o `celery-beat-heartbeat@.service`
   já exige para `BEAT_HEARTBEAT_FILE`). Sem ela, o `check_celery_jobs` fica
   `not_configured` e — **por desenho fail-closed** — o portal responde
   `X-Operational-State: degraded` e `portal_health_degraded_total` sobe. Isso é o
   sinal correto ("você não tem telemetria de job"), mas é um alarme permanente
   até a env ser declarada. Default: `/var/lib/portal-observabilidade/jobs.json`.
3. **Regras de alerta** para `portal_health_check_not_configured{check=...} == 1`
   e para `portal_job_task_idle_seconds{task=...}` acima do intervalo esperado de
   cada task (o "atraso" do critério 14) — as séries agora existem, mas quem as
   consome é o Grafana (Bloco C/infra).
4. **`portal_job_*` são gauges absolutos**: somar por `instance` multiplica. As
   regras precisam de `max()`/`last()`.

---

## 6. Arquivos tocados

Novos:

```text
backend/config/job_state.py
backend/config/proxies.py
backend/config/tests/test_job_state.py
backend/config/tests/test_proxies.py
agentic-framework/state/run-20260925-1020-observabilidade/remediacao-backend.md
```

Modificados:

```text
backend/config/celery.py                    (postrun grava o canal de job; sinal task_retry)
backend/config/health.py                    (CHECKS_SEM_SINAL_PROPRIO, _e_degradante, check_celery_jobs, gauge de ponto cego)
backend/config/metrics.py                   (allowlist de rótulos, teto por família, histograma acumulado, describes novos)
backend/config/middleware.py                (log do 500 com safe_path + redact_single_line)
backend/config/observability.py             (_AUTH_SCHEME, _HEADER_VALUE, redact_single_line, RedactingTextFormatter, reportar_falha_de_init_sentry)
backend/config/observability_views.py       (proxies.py no gating, compare_digest em bytes, publica job no scrape)
backend/config/settings.py                  (NUM_PROXIES=0, formatter verbose redigido, env do canal de job, sinal de init do Sentry)
backend/config/settings_test.py             (arquivos de heartbeat/estado de job para a suíte)
backend/config/throttling.py                (mixin de identidade de cliente nas 4 throttles anônimas)
backend/metricas/consent.py                 (laço sem curto-circuito, claim v tipado)
backend/metricas/tasks.py                   (contagem do expurgo como valor, não rótulo)
backend/metricas/views.py                   (campo em excesso não é "evento rejeitado")
backend/config/tests/test_health_checks.py
backend/config/tests/test_health_endpoints.py
backend/config/tests/test_metrics_registry.py
backend/config/tests/test_observability_contexto.py
backend/config/tests/test_observability_middleware.py
backend/config/tests/test_observability_redaction.py
backend/config/tests/test_throttling.py
backend/metricas/tests/test_consent_ingestao.py
backend/metricas/tests/test_consent_token.py
backend/metricas/tests/test_tasks_expurgo.py
```

Nenhuma migration (`makemigrations --check --dry-run` → *No changes detected*),
nenhuma dependência nova (só stdlib: `ipaddress`, `json`, `pathlib`, `os`,
`threading`, `time`, `logging`).

**Fora do escopo, por instrução (nenhum toque):** `.github/`, `frontend/`,
`infra/`, `docker-compose*.yml`, `.env*`, `CI-CD.md`, `PROD_DECISOES.md`,
`infra/DEPLOY.md`, `scripts/release/`, `scripts/observability/`,
`agentic-framework/state/run-20260924-*`,
`agentic-framework/state/run-20260925-1433-go-live-producao/`, `run-state.json`
desta run; e o WIP estrangeiro `backend/feed/views.py`,
`backend/catalogo_noticias/services/deduplicacao.py`,
`backend/feed/tests/test_p1_feed_cache_indices.py`,
`backend/catalogo_noticias/management/commands/agendar_ingestao.py`.

---

## 7. Testes: comandos e saída real

```console
$ cd backend && .venv/bin/python manage.py check
System check identified no issues (0 silenced).

$ cd backend && .venv/bin/python manage.py makemigrations --check --dry-run
No changes detected
```

```console
$ cd backend && .venv/bin/python -m pytest config metricas -q
353 passed, 101 warnings in 20.86s
```

(Baseline do Bloco A2: 287 passed → **353**; +66 testes, todos com comportamento
assertado.)

```console
$ cd backend && .venv/bin/python -m pytest -q
811 passed, 289 warnings in 94.66s (0:01:34)
```

**As 7 falhas externas em `catalogo_noticias/tests/test_command_agendar_ingestao.py`
(WIP da run 2136) NÃO existem mais**: o outro agente corrigiu o arquivo durante
esta sessão e o arquivo está verde.

```console
$ cd backend && .venv/bin/python -m pytest catalogo_noticias/tests/test_command_agendar_ingestao.py -q
24 passed in 16.67s
```

Cobertura com o gate (mesmo comando do Bloco A2):

```console
$ cd backend && .venv/bin/python -m pytest config metricas -q --cov=config --cov=metricas --cov-report=term --cov-fail-under=80
config/celery.py                    51     7   86%
config/health.py                   220     8   96%
config/job_state.py                125    13   90%   (novo)
config/metrics.py                  225    14   94%
config/middleware.py               114     5   96%
config/observability.py            232    29   88%
config/observability_views.py       87     5   94%
config/proxies.py                   63     7   89%   (novo)
config/settings.py                 180    28   84%
config/settings_test.py             20     1   95%
config/throttling.py                15     0  100%
config/urls.py                       5     0  100%
config/views.py                     19     0  100%
metricas/consent.py                295    23   92%
metricas/tasks.py                   50     2   96%
metricas/views.py                  143    19   87%
TOTAL                             4968   330    93%
Required test coverage of 80% reached. Total coverage: 93.36%
353 passed, 101 warnings in 22.96s
```

Cobertura com o **comando exato da CI** (`--cov=.`, gate 80%):

```console
$ cd backend && .venv/bin/python -m pytest -q --cov=. --cov-report=term-missing --cov-fail-under=80
Required test coverage of 80% reached. Total coverage: 90.96%
811 passed, 289 warnings in 109.95s (0:01:49)
```

### Testes que precisaram de adaptação (com o motivo, não como conveniência)

1. `test_beat_sem_heartbeat_configurado_nao_fica_verde` passou a usar
   `override_settings(OBSERVABILITY_BEAT_HEARTBEAT_FILE="")`, porque
   `settings_test.py` agora cria o arquivo (§2.3). A asserção continua a mesma.
2. `test_snapshot_com_opcionais_agrega_degraded_...`,
   `test_degraded_state_memoiza_...` e `test_degraded_state_forcado_reavalia`
   passaram a mockar `check_celery_beat`/`check_celery_jobs` como `ok` (antes
   mockavam `not_configured` e isso **parava de ser um caso neutro** quando
   `not_configured` passou a degradar — o "ok" final do terceiro teste era
   impossível). A intenção de cada teste (agregação, memoização, reavaliação forçada)
   está preservada, e a regra nova tem testes próprios.
3. `test_filas_sem_leitura_possivel_e_degraded_nao_ok` (NIT-2) ficou
   `assert resultado.status != "ok"` com o motivo — o `in {"degraded","ok"}`
   original não podia falhar.
4. `test_log_nao_contem_email_authorization_token_ou_query_sensive` (MINOR-1): com a
   regra de header, o resto da linha é redigido **com** o header. O teste passou a
   exigir exatamente isso, e a contagem de redações original foi preservada em um
   teste novo para mensagem sem header de credencial (§2.6).
5. `test_observacoes_sao_limitadas_por_serie` saiu (não existe mais lista de
   observações) e foi substituído por
   `test_histograma_acumula_buckets_e_nao_guarda_observacoes` +
   `test_scrape_nao_custa_mais_que_as_series_existentes`.

---

## 8. Critérios do contrato: como ficaram

| # | antes da revisão | agora |
|---|---|---|
| 9 (Redis/Celery/beat degradado, metricado, alertado) | verificado, **exceto beat** | **atendido**: beat sem sinal próprio é degradação (header + `portal_health_degraded_total` + `portal_health_check_not_configured`), e o job idem |
| 14 (fila, **atraso**, retry, falha, duração consultáveis) | parcial | **atendido no que a arquitetura de processo único permite**: fila (`portal_celery_queue_depth`), atraso (`portal_job_task_idle_seconds`), retry (`portal_job_task_retries_recorded`), falha (`portal_job_tasks_recorded{result="FAILURE"}`), duração (`portal_job_task_duration_seconds_sum/_count`) — todos no `/metrics` do processo web. **Histograma por task continua cross-process** (exporter no worker = bloco de infra), documentado |
| 16 (worker/beat paradoxos aparecem como falha e geram alerta) | **não atendido** | **atendido no backend**: a condição aparece como degradação em header/métrica/`/health-detail`; o "gera alerta" é regra no Grafana (pendência de infra, §5) |
| 18 (log com ambiente, serviço, release e request/task ID) | verificado | mantido, e agora **também** no modo texto (`verbose`), que não redigia nada |
| 28 (query string, Authorization e PII omitidos/mascarados) | parcial (MINOR-1/2) | **atendido**: header com credencial (incluindo `Basic`) e 2º cookie, CR/LF, e o modo texto passa pelo redactor |
| Restrição "instrumentação de baixo overhead" | parcial (MAJOR-2) | **atendido**: buckets acumulados, teto por família, nada de recontagem dentro do lock |
| 3 (ID inválido → UUID seguro sem colisão) | verificado (com NIT-4) | inalterado (NIT-4 pré-existente, em `feed/`) |

## 9. Riscos que esta remediação deixa abertos

1. **Alarme permanente até a env do canal de job ser declarada** (§5.2) — é o
   comportamento fail-closed pedido, mas precisa entrar no runbook de provisionamento
   junto com o heartbeat do beat, senão alguém "conserta" desabilitando o check.
2. **O histograma por task segue invisível** sem exporter no worker (§2.4). O
   agregado (`_sum`/`_count`) e o atraso cobrem o alerta essencial; percentis por
   task, não.
3. **O canal de job é single-node por construção** (arquivo local). Se o projeto
   um dia rodar em multi-node, o arquivo vira o gargalo (e o "não-objetivo" da
   run já exclui multi-node/HA). O docstring do módulo diz isso.
4. **A regra `_HEADER_VALUE` come o resto da linha** quando a mensagem menciona
   `cookie:`/`authorization:` como palavra. Custo aceito e testado, mas quem
   escrever a próxima mensagem de log com essas palavras precisa saber que o
   trecho seguinte do diagnóstico some.
