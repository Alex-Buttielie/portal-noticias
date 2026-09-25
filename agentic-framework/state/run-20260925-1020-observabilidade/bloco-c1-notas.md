<!--
NOTAS DE EXECUÇÃO — Bloco C1 (infra, coletor, backup)
DONO: subagente executor (bloque C1) da run 20260925-1020-observabilidade
ESCOPO: bloco-c-plano.md, itens C1.1 a C1.16
-->

# Notas do Bloco C1 — infra, coletor e backup

Run `20260925-1020-observabilidade`. Execução isolada, sem escrita de índice
git (nenhum `git add`/`commit`/`stash`), conforme instrução do orchestrator.
Branch `observability-20260925-1020` mantida.

## 0. Escopo entregue, em uma tela

31 arquivos (12 modificados, 19 novos). Nenhum arquivo bloqueado foi lido para
copiar ou editado: `.github/`, `CI-CD.md`, `PROD_DECISOES.md`,
`infra/DEPLOY.md`, `scripts/release/`, `backend/` (código), `frontend/` (código),
`run-state.json` e `implementation-history.md` estão intactos. `backend/` foi
lido (necessário para não prometer métrica inexistente) e `frontend/.env.local.example`
foi editado porque o plano (C1.14) o lista e a autorização é explícita.

| ID | Entregue | Arquivos |
|---|---|---|
| C1.1 | `/livez` + `/readyz` públicos por HTTPS; `/health-detail` e `/metrics` com gate duplo | `infra/nginx/portal-{dev,homolog,prod}.conf`, `infra/nginx/http-cache.conf` |
| C1.2 | `X-Request-ID` do cliente propagado; release/ambiente/estado em resposta de cache | idem |
| C1.3 | `log_format` JSON da borda + logrotate | `infra/nginx/http-cache.conf`, `infra/logrotate/nginx-portal.conf` |
| C1.4 | Units systemd de worker/beat + produtor do heartbeat | `infra/systemd/celery-{worker,beat}@.service`, `celery-beat-heartbeat@.{service,timer}` |
| C1.5 | Execução do Next standalone com smoke | `infra/standalone/run-standalone.sh` |
| C1.6 | Coletor Alloy + gate fail-closed de env | `infra/observability/alloy/{config.alloy,alloy.env.example,verificar-env.sh}` |
| C1.7 | 4 painéis técnicos versionados | `infra/observability/grafana/dashboards/*.json` |
| C1.8 | 16 regras de alerta com severidade/runbook/dedup | `infra/observability/alerts/*` |
| C1.9 | Checks externos Better Stack + cron monitor de backup | `infra/observability/better-stack/checks.json` |
| C1.10 | Lifecycle do bucket de backup | `infra/observability/r2/lifecycle.json` |
| C1.11 | Backup fail-closed sem destino remoto | `infra/backup/pg_backup_pm2.sh` |
| C1.12 | Watchdog de atraso + runbook da topologia PM2 | `infra/backup/verificar_backup.sh`, `infra/backup/RESTORE.md` |
| C1.13 | Healthchecks de worker/beat sem verde-por-omissão | `docker-compose.yml` |
| C1.14 | Variáveis novas documentadas; `DJANGO_LOG_JSON` divergente resolvido | `.env.production.example`, `backend/.env.example`, `.env.localhost.example`, `frontend/.env.local.example` |
| C1.15 | Validador de infra executável fora da CI | `scripts/observability/validar-infra.sh` |
| C1.16 | README da malha | `infra/observability/README.md` |

---

## C1.1 — Rotas de health e gate dos endpoints privados

**O que fiz.** Em cada um dos três site confs:

- `location = /livez` e `location = /readyz` no `server` 443, **sem**
  `allow/deny` (são públicos por contrato de
  `backend/config/observability_views.py`: liveness não toca dependência e
  readiness devolve só `{"status","ready"}`). Sem essas locations o pedido
  caía em `location /` (Next.js) e o check externo recebia 404 de um portal
  saudável — exatamente o achado B1.
- No `server` 80, as mesmas duas locations **com** `allow 127.0.0.1; allow ::1;
  deny all`, espelhando o `/healthz` existente (mesmo motivo, mesmo formato).
- `location ~ ^/(health-detail|metrics)$` — **um** location para os dois
  endpoints privados, com um único `if ($observability_acesso = 0) { return 404; }`.
  Um location só porque são a mesma política: em dois separados, uma edição
  futura esqueceria um deles. (Os caminhos privados não ganharam rota em HTTP
  plano; caem no redirect e só são avaliados em HTTPS.)
- A política de acesso virou um map só no `http-cache.conf`
  (`$observability_acesso`), com `geo` para origem de rede e comparação do
  `Authorization: Bearer` contra `__OBS_TOKEN_ESPERADO__`.

**Decisões e trade-offs.**

1. **`if` aninhado é inválido no Nginx** — descobri testando com o binário real
   (`"if" directive is not allowed here`). Por isso as três condições (rede,
  token configurado, bearer válido) foram colapsadas em **um** map
  (`"$origem $configurado $valido"`) e o site usa **um** `if` plano.
2. **Variável interpolada dentro de regex de `map`**: confirmei que o Nginx
   aceita (`sys`-style) e que funciona em runtime, com teste ao vivo.
3. **Marcador em vez de credencial no repositório**: `__OBS_TOKEN_ESPERADO__`
   nunca autoriza (há um map que zera o valor enquanto o marcador estiver
   presente), então instalar sem substituir **fecha** o acesso em vez de abrir
   uma porta com uma senha de exemplo. O mesmo valor precisa estar em
   `OBSERVABILITY_METRICS_TOKEN` no ambiente da aplicação e no arquivo de token
   do coletor — a comparação em tempo de execução é do app
   (`compare_digest`), a do Nginx é só a primeira camada.
4. **Nginx valida rede; o app valida origem.** O gate do Nginx é
   loopback-ou-bearer, e o `/health-detail` do Django repete as duas regras
   (loopback, redes declaradas, staff ou token). É defesa em camadas, e cada
   camada é fail-closed por conta própria. **Declaro isto explicitamente**:
   o `geo` do Nginx não tem lista de proxies extras como item separado — quem
   precisar acrescenta a linha `<CIDR> 1;` naquele bloco (documentado).
5. **Resposta de acesso negado é 404**, o mesmo corpo de "rota inexistente" que
   o app devolve, para não confirmar a existência do diagnóstico.

**Validação real (nginx oficial 1.31.6 em container, conf do repo renderizado):**

```
GET /livez (publico; esperado != 404)                    -> 502
GET /readyz (publico; esperado != 404)                   -> 502
GET /metrics SEM token (esperado 404)                    -> 404
GET /health-detail SEM token (esperado 404)              -> 404
GET /metrics token ERRADO (esperado 404)                 -> 404
GET /metrics marcador __OBS_TOKEN (esperado 404)         -> 404
--- de DENTRO (loopback) ---
GET /livez (loopback; esperado != 404)                   -> 502
GET /readyz (loopback; esperado != 404)                  -> 502
GET /metrics (loopback; esperado != 404)                 -> 502
GET /health-detail (loopback; esperado != 404)           -> 502
```

502 = o gate liberou e não há backend em `127.0.0.1:5103` (ausente de
propósito). 404 = o gate negou. Além disso, com o backend real de um container
fake, validei o `X-Request-ID`: válido (11 chars) é propagado, inválido (com
espaço) e ausente caem no `$request_id` do próprio Nginx.

## C1.2 — Correlação de requisição e headers em resposta de cache

**Achado B2 corrigido.** `proxy_set_header X-Request-ID $request_id` aparecia
13× em cada site conf e **sobrescrevia** o ID do cliente — o backend registrava
no log o ID que ele mesmo tinha descartado. Agora todos os 13 usam
`$portal_request_id`, definido no `http-cache.conf`:

```
map $http_x_request_id $portal_request_id {
    default $request_id;
    "~^[A-Za-z0-9._:+@/-]{1,64}$" $http_x_request_id;
}
```

O regex espelha a validação do app (`normalizar_request_id`: até 64 chars
imprimíveis). O mesmo nome alimenta o `log_format`, então **log de borda e log
do Django mostram o mesmo ID** — é isso que amarra um 500 do usuário até a linha
do traceback.

`X-Release`, `X-Environment` e `X-Operational-State` foram acrescentados com
`add_header ... always` na location de cache de borda, espelhando o padrão já
documentado no conf ("`add_header` em location substitui o do server").
`X-Operational-State` é o que permite detectar degradação pela borda (achado
B10/B12). **Escolha deliberada:** com o header do upstream vazio, o `add_header`
não emite nada (comportamento documentado do Nginx) em vez de emitir valor
inventado — header ausente é melhor que header errado, e o log técnico mostra o
valor real em `upstream_release`.

**Desvio do plano, declarado:** o plano pedia `$request_id` no `log_format`; usei
`$portal_request_id` (o ID efetivo, que pode ser o do cliente) e mantive
`$request_id` em um campo separado (`nginx_request_id`). Logar o ID nativo
enquanto o app loga o do cliente desfaria justamente a correlação que a run
quer. Evidência ao vivo:

```
{"time":"...","request_id":"9f2c1b7e-1111-4222-8333-abcdefabcdef",
 "nginx_request_id":"bb09afa0cc03e6759497c55b6e87064a", ...}
```

## C1.3 — Log de borda e rotação

`log_format portal_acesso escape=json` no `http-cache.conf`, com
`request_id`, `nginx_request_id`, `uri`, `status`, `request_time`,
`upstream_*` (incluindo `upstream_release` e `upstream_operational_state`),
`cache_status` e `user_agent`. Três decisões:

- **Todos os valores entre aspas**, inclusive os numéricos: `$status` vem vazio
  em resposta gerada antes do rewrite e `$upstream_response_time` vem vazio em
  erro de conexão e em cache HIT. JSON sem aspas quebraria a linha justamente
  nos casos que mais importam. Validei com `jq` em linha com User-Agent
  contendo aspas e barra.
- **A query string não entra** (critério 28): `$uri` é o path sem query.
- **O ambiente não é campo**, e sim label por arquivo no Loki — o
  `http-cache.conf` é compartilhado pelos três sites, então um valor fixo
 -mentiria para dois dos três ambientes.

`infra/logrotate/nginx-portal.conf`: `daily`, `rotate 30`, `maxsize 50M`,
`compress`, `copytruncate`. `copytruncate` (e não `postrotate ... reopen`)
porque o master do Nginx mantém o descritor: com `create`/`rename` o processo
em produção continuaria escrevendo no arquivo já rotacionado — o mesmo motivo
já documentado em `pg-backup.conf`.

## C1.4 — Units systemd

Quatro arquivos: `celery-worker@.service`, `celery-beat@.service`,
`celery-beat-heartbeat@.service` e `celery-beat-heartbeat@.timer`.

**Desvio do plano, justificado:** o plano pedia `celery-worker.service` /
`celery-beat.service`; entregue como **template units** (`@`). Motivo: a mesma
VPS hospeda os três ambientes (`/home/apps/portal-{dev,homolog,prod}`, portas
310x/510x, três site confs). Uma unit com `EnvironmentFile` fixo serviria a um
ambiente só — e o ambiente errado é exatamente a falha que produz backup do
banco de dev em produção. Com `%i` = ambiente, o nome da instância aparece no
`systemctl status`, no journal e no alerta.

Hardening: `NoNewPrivileges`, `ProtectSystem=full`, `ProtectHome=false` (o app
é `/home/apps`; `ProtectHome=true` esconderia `/home` e o worker nem leria o
código), `PrivateTmp`, `PrivateDevices`, `ProtectKernel*`, `ProtectProc`,
`RestrictNamespaces`, `SystemCallFilter=@system-service`,
`CapabilityBoundingSet=` vazio, `UMask=0027`. Limites: `MemoryHigh=384M` /
`MemoryMax=512M` (worker) e 192M/256M (beat), `CPUWeight`, `TasksMax`.
`TimeoutStopSec=300` porque `SIGTERM` no Celery é shutdown **quente** — com
30s o restart de deploy derrubaria uma ingestão em curso e o registro ficaria
"failed" sem causa.

Três coisas que o `systemd-analyze verify` me obrigou a corrigir (ver abaixo):
`ExecCondition` é do bloco `[Service]`, não `[Unit]`; e troquei
`Requires=redis.service` por `Wants=` — `Requires=` de uma unit inexistente
**faz a unit não subir**, e o nome da unit do broker varia (serviço nativo,
container, alias systemd). `Wants=` + `After=` é a escolha honesta: unit que
não sobe é pior que unit que sobe e espera o broker.

**Produtor do heartbeat (fecha o gap do achado B4).** `check_celery_beat`
ficava `not_configured` para sempre porque `OBSERVABILITY_BEAT_HEARTBEAT_FILE`
não tinha produtor. A unit do beat faz um `ExecStartPost` tolerante, e o timer
escreve o arquivo a cada 5 min **só se** `systemctl is-active celery-beat@%i`
responder. A armadilha — e o motivo do `ExecCondition` — é que um timer que
tocasse o arquivo sozinho manteria o check verde com o beat morto, que é
exatamente o healthcheck "sempre verde" do achado B11. **Limitação declarada:**
isto prova que o *processo* do beat está vivo, não que o agendador dispara. O
resíduo é coberto por `PortalCelerySemExecucao` e está escrito no README e no
painel de filas.

**Validação real:**

```
$ systemd-analyze verify infra/systemd/celery-worker@.service
celery-worker@test_instance.service: Command /home/apps/portal-test_instance/backend/.venv/bin/celery is not executable: No such file or directory
(exit 1, apenas o aviso esperado: o app não existe neste host)
```

O mesmo aviso nas outras três units, mais a primeira rodada de erros reais que
o verificador pegou (`Unknown key 'ExecCondition' in section [Unit]` e
`Failed to create .../start: Unit redis.service not found`) — ambos corrigidos
antes de qualquer anotação de "validado".

## C1.5 — Next standalone fora do `npm start`

`infra/standalone/run-standalone.sh`, com três comandos: `prepare` (copia
`public/` e `.next/static` para a árvore, como o runner stage do
`frontend/Dockerfile`), `smoke` e `start`.

O smoke é o ponto onde gastei mais cuidado, porque um smoke mal desenhado troca
um problema real por um falso:

- sobe numa **porta livre** (senão o "sucesso" é o do processo velho, ou seja,
  da release anterior);
- exige `/robots.txt` (rota do app, **independe da API**);
- exige **um asset real de `.next/static`** — é o teste que pega o erro clássico
  de standalone (`.next/static` não copiado: a página abre e aparece sem
  estilo);
- na Home aceita 2xx/3xx **e 503**, e explica que 503 é a resposta documentada
  para feed indisponível sem cache (critério 11, nunca conteúdo MOCK);
  reprova 5xx e outros.

`public/` ausente não é erro: o repositório hoje **não tem** `frontend/public/`
(é por isso que o Dockerfile faz `mkdir -p ./public`). Erro seria reprovar um
deploy por um diretório inexistente.

**Validação real** (árvore standalone mínima com `node server.js` fake, 4
cenários): Home 200 → exit 0; Home 503 → exit 0 com aviso; Home 500 → exit 69;
processo que morre no boot → exit 69; `prepare` idempotente → ok; nenhum
processo órfão. Durante esses testes o `bash -n` pegou um **typo meu real** —
`while ...; then` em vez de `do` — que só apareceu porque a validação é real.

## C1.6 — Coletor Grafana Alloy

`config.alloy`: scrape de `/metrics` (com `Authorization: Bearer` sempre, para
exercitar o mesmo caminho de autenticação do resto da malha), tail do log de
borda e dos logs JSON do backend/PM2, journal do systemd com allowlist,
remote-write para Mimir e Loki. Tudo por `sys.env`; nenhum endpoint, token ou
path real no arquivo.

Decisões:

- **Uma instância por ambiente.** Um coletor único misturaria dev/homolog/prod
  e uma falha em dev poderia "explicar" um painel de prod. `ambiente` vai como
  external label no Mimir e como label no Loki.
- **O token vai em arquivo** (`credentials_file`), não em variável: o
  `prometheus.scrape` relê o arquivo a cada scrape e o valor fica fora do
  environment do processo.
- **Journal com `loki.relabel` e regex ancorada, não com `matches`.** `matches`
  vazio significa "todo o journal" — um coletor de tudo, caro e ruidoso. Com
  allowlist, valor ausente faz a regex não casar com nada, ou seja, **não
  coleta**, que é o comportamento seguro. (Agrupar as units com `|` no env
  exige aspas no arquivo: sem elas o `source` do env executa as units como
  comando. Encontrei isso testando.)
- **`prometheus.exporter.textfile` NÃO existe no Alloy.** Confirmei na
  documentação antes de projetar o watchdog de backup em cima dele; por isso o
  atraso de backup é canal externo (Better Stack) + watchdog local, sem
  métrica fictícia de idade de backup no Mimir.
- **Fail-closed em duas camadas.** O `config.alloy` não consegue falhar sozinho
  (`sys.env` de variável ausente devolve vazio e o componente só erra em log),
  então `verificar-env.sh` é a barreira: sem endpoint, sem token, sem arquivo
  de token em modo 600/400, ou sem os grupos `adm`/`systemd-journal` para o
  journal, o coletor **não sobe**. A armadilha do journal ("inicia sem erro e
  não coleta nada") é a razão do check de grupo — e é o tipo de falso verde que
  existe dentro do próprio coletor.

**Validação real** — `alloy validate` com a imagem oficial e env de
placeholders, depois de **cinco rodadas de erro real** que eu cometi e que só o
parser pegou: vírgula obrigatória em literal de objeto (`{ a = 1, b = 2 }`) e
proibida em bloco (`basic_auth { a = 1 b = 2 }`); `stage.static_labels` exige
`values = {…}`; `prometheus.scrape` **não tem** `relabel_configs` (o
`ambiente` foi para `external_labels`) nem atributo `job` (existe `job_name`);
`queue_config` é bloco de `endpoint`, não do componente.

```
$ docker create --env-file <env de placeholders> grafana/alloy:latest validate /etc/alloy/config.alloy
$ docker cp config.alloy <cid>:/etc/alloy/config.alloy && docker start -a <cid>
rc=0   (sem saída: configuração válida)
```

Gate de env, testado em 4 cenários: exemplo com placeholders → 11 erros
(exit 1); env válido com token 0600 → só falha o grupo `systemd-journal`, que
nesta máquina é falha real; token 0644 → erro; token vazio → erro.

## C1.7 — Painéis

4 painéis: disponibilidade, saúde/dependências, filas/Celery, ingestão. Todos
com `__inputs` de datasource (importável pela UI, sem inventar UID de
datasource) e variáveis `ambiente`/`release`.

A regra que o plano pede — "não prometer painel que dependa de métrica
inexistente" — foi aplicada de duas formas:

1. **Antes de gerar**, um verificador recusa qualquer `expr` com métrica fora do
   inventário do backend.
2. **Depois**, `validar-infra.sh` re-chec a extração das `expr` de todos os
   painéis e regras contra `metrics.py` + `observability_views.py` + `health.py`.

Isso encontrou um erro meu: eu tinha escrito um stat sobre `portal_beat`, uma
métrica que **nada produz**. Removido e substituído pelo sinal de efeito real
(`increase(portal_celery_tasks_total[45m])`).

**Limitação escrita dentro do painel**, não escondida: `/metrics` é registro
**por processo**, então contadores subestimam e zeram a cada restart; o painel
de disponibilidade tem um painel de texto explicando, e a recomendação é `rate()`
para tendência. Cada painel tem painel de texto com o que ele **não** mostra
(por exemplo: contagem de itens ingeridos não existe como métrica).

## C1.8 — Regras de alerta

16 regras em 2 arquivos (6 de disponibilidade, 10 de operação). Cada uma com
`severity`, `runbook_url`, `description` com o que é causa provável, e
`primeiro_passo`.

**Deduplicação (critério 22).** Deduplicação em Prometheus é identidade de
rótulo, não campo. Duas decisões: as expressões usam `by (ambiente)` e **não**
filtram `ambiente="..."` — uma regra com uma instância por ambiente, sem três
arquivos; e `for:` dimensionado pelo intervalo real do sinal (ingestão a cada
15 min → 45 min de janela; scrape de 30 s → 2 min). O `alerts/README.md`
documenta os Contact Points que faltam criar e por que (mute timings sem o
qual um incidente derruba o canal com uma notificação por minuto).

Dois detalhes que valem registro: `absent(up{job="alloy"})` em vez de
`up == 0` (se o processo do coletor morre, a série fica *stale* e a comparação
com 0 **resolveria** o alerta — o alerta que se autossilencia); e o alerta de
ingestão **não** se apoia em `portal_ingestion_executions_total` (declarada e
nunca incrementada), e sim na task real `catalogo_noticias.tasks.ingerir_noticias`
do `CELERY_BEAT_SCHEDULE`.

## C1.9 — Checks externos Better Stack

`checks.json` com 7 checks e 1 cron monitor, cada um com o porquê. Decisões:

- `/readyz` e `/livez` separados: com os dois, o operador sabe em um minuto se
  caiu a API ou o banco, sem precisar de acesso ao servidor;
- a **Home** entra porque `/readyz` cobre só a API e o frontend é a outra
  metade da resposta na topologia PM2 (mesmo host, mesmo Nginx);
- aceitar 503 na Home e no feed, com o motivo escrito no arquivo: 503 é a
  resposta documentada de feed indisponível sem cache, e reprovar o monitor por
  um 503 correto treina o time a ignorar o monitor;
- o **cron monitor** é o mecanismo do atraso de backup, porque um watchdog na
  própria VPS não avisa quando a VPS morre;
- a lista do que **não** é monitorado (Postgres/Redis por TCP, endpoints
  privados, Sentry) está no próprio arquivo, com o motivo.

Nenhuma URL real foi inventada: placeholders `<DOMINIO_DE_PRODUCAO>` etc. e a
nota de que a URL de heartbeat é segredo.

## C1.10 — Lifecycle do bucket

3 regras: expiração em 90 dias, piso de 30 dias para versões não atuais, e
abort de multipart upload incompleto em 7 dias. Bucket privado declarado, com
`object_lock: false` e o motivo. A regra de MPU órfão é a que evita pagar
armazenamento por upload que nunca virou backup — o `pg_backup_pm2.sh` só
considera o backup concluído depois de validar o objeto, então o resto é lixo
caro. A retenção de 90 dias está marcada como **decisão humana pendente**.

## C1.11 — Backup fail-closed (achado B7)

Mudança restrita ao fim do script, preservando tudo que já funcionava
(validação por `pg_restore --list`, restore em banco descartável com contagem
de linhas, retenção local suspensa sem upload confirmado, `flock`, `umask 077`).

- Sem `BACKUP_S3_BUCKET`: antes dois AVISOs e **exit 0**; agora **exit 20** com
  mensagem explícita. A retenção local continua suspensa e nada é apagado.
- `BACKUP_REQUIRE_REMOTE=0` é o escape de bootstrap, com três AVISOs em stderr
  e a frase que importa: "com o escape ligado, o exit 0 deste backup **não**
  significa que existe cópia remota".
- Após sucesso, grava `$BACKUP_DIR/.ultimo-backup-ok` (modo 600) com timestamp,
  nomes, tamanhos e `remoto=confirmado|ausente` — é o que o watchdog lê.
- `BACKUP_HEARTBEAT_URL` (cron monitor do Better Stack) é pingado **depois** de
  dump, mídia, upload e verificação remota. Falha é **exit 21**: um backup
  íntegro cujo canal de alerta está quebrado é o mesmo tipo de verde sem
  destino, uma camada acima. `BACKUP_HEARTBEAT_REQUIRED=0` é o escape.
- As três variáveis novas entraram na lista de "configuração externa preservada"
  do `source` do env file, pelo mesmo motivo das `BACKUP_S3_*`: um `.env`
  copiado do exemplo, com linha vazia, não pode apagar uma decisão do crontab.

**Validação real com PostgreSQL 16 em container** (4 cenários, backup completo
rodando de verdade — `pg_dump`, `pg_restore` em banco descartável, contagem de
tabelas/linhas, `tar` da mídia):

```
A) SEM destino remoto          -> exit 20, retenção suspensa, 2 arquivos preservados
B) BACKUP_REQUIRE_REMOTE=0     -> exit 0, 3 AVISOs, nada apagado (4 arquivos)
C) bucket declarado, sem AWS CLI -> exit 10 (falha fechada pré-existente)
D) heartbeat obrigatório ausente -> exit 21
marcador .ultimo-backup-ok: -rw------- , remoto=ausente
```

## C1.12 — Watchdog de atraso e runbook da topologia PM2

`verificar_backup.sh`, executável por cron, com `umask 077` e saída em duas
vias: humano em **stderr** e **uma linha JSON em stdout** (para consumo
por máquina), mais exit code com significado (0 ok / 1 atrasado / 2 nunca
executou / 3 configuração inválida / 4 alerta não entregue).

Verifica: idade do marcador, idade do dump mais recente (checagem cruzada — um
marcador novo com dump velho é motivo para desconfiar), e — quando há bucket
configurado — `head-object` do objeto do marcador, porque "backup local" na
mesma máquina que acabou de perder o disco não é o que o backup remoto existe
para evitar. A JSON é montada à mão (sem `jq`, que não pode ser dependência de
um host mínimo) com escape e tipo numérico correto: um consumidor quebrado por
uma aspas é pior que um campo vazio.

**Validação real, 8 cenários:** nunca executou → 2; marcador novo com
`remoto=ausente` → 1 (e o motivo é explícito); tudo confirmado → 0; marcador
30 h → 1; dump 40 h com marcador novo → 1; `BACKUP_MAX_AGE_HOURS=abc` → 3
(com JSON ainda válido, `max_age_horas: null`); `BACKUP_DIR` inexistente → 3;
nome de arquivo com aspas → JSON ainda válido; bucket sem AWS CLI → 3.

`infra/backup/RESTORE.md` ganhou a seção da topologia **ativa** (PM2 + Nginx +
Postgres do host), que o arquivo não cobria: onde estão os artefatos, restore
em banco novo, contagens que provam que o restore trouxe dados, extração de
mídia em diretório vazio, download do R2, o teste mensal (critério 35) e o
procedimento de incidente com o backup como único caminho (parar de escrever
**antes** de restaurar — restore por cima do banco em uso grava sobre conexões
vivas e produz um estado que não é nem o backup nem o estado anterior).

## C1.13 — Healthchecks do compose

O `|| exit 0` sumiu dos dois. Análise do defeito, não só do sintoma:

- **worker**: o ping passa a ser feito pelo app Celery do projeto (portanto o
  broker configurado no ambiente), com o **código de saída** sendo o resultado
  (`sys.exit(0 if resp else 1)`), sem `grep` e sem parsing de texto;
- **beat**: o check antigo media o **serviço errado** — `inspect ping` responde a
  partir dos *workers*, então o beat podia estar morto e o container ficar
  "healthy" porque outro processo respondeu. Agora afirma o que pode afirmar
  honestamente: (1) o PID 1 **é** o beat (é o que `entrypoint: []` + `command`
  garantem) e (2) o arquivo de schedule avança; se ainda não existe, o check se
  apoia só no processo (leniência de boot deliberada, para não produzir
  `unhealthy` falso).

Um detalhe que só apareceu testando: **dentro de `healthcheck.test` o Compose
não expande `$$`** (ao contrário de `command`), então minha primeira versão,
com `$$(ls ...)`, chega ao `/bin/sh` como PID seguido de parêntese — erro de
sintaxe garantido, que `docker compose config` **não** acusa. Reescrevi sem
variável de shell e passei a validar o healthcheck como o que ele é: um comando
`sh` que executa Python. `depends_on` intocado.

**Validação real:** `docker compose config` OK; healthcheck de worker e beat
válidos como shell (`sh -n`) e como Python (`ast.parse`); e a lógica de decisão do
beat testada em 5 cenários com `/proc/1/cmdline` e globbing simulados: PID 1
não-beat → 1; beat sem schedule file → 0; schedule avançando → 0; schedule
parado 2 h com limite 1 h → 1; o mesmo com limite 4 h → 0.

## C1.14 — Variáveis de ambiente

Nos quatro arquivos de exemplo, com placeholders obviamente falsos e **nenhum
segredo**. Documentadas: `OBSERVABILITY_{METRICS_TOKEN,HEALTH_TOKEN,TRUSTED_PROXY_NETWORKS,BEAT_HEARTBEAT_FILE,BEAT_MAX_AGE_SECONDS,QUEUE_DEPTH_WARN,COLLECTOR_PATH,DISK_MIN_FREE_RATIO,DEGRADED_PROBE_INTERVAL_SECONDS,LOG_RETENTION_DAYS}`,
`OTEL_SERVICE_NAME`, `SENTRY_{RELEASE,TECHNICAL_CONSENT_DEFAULT}`,
`BACKUP_{REQUIRE_REMOTE,HEARTBEAT_URL,HEARTBEAT_REQUIRED,MAX_AGE_HOURS}`.

**Divergência de `DJANGO_LOG_JSON` resolvida:** o default do `settings.py` é
`true` e os exemplos diziam `false`. Agora `.env.production.example` traz
`true` com o motivo (o coletor precisa de JSON; com `false` o deploy de
produção sobe sem log parseável), `backend/.env.example` e
`.env.localhost.example` mantêm `false` para leitura no terminal **com o
default documentado ao lado**, para ninguém "corrigir" o exemplo de dev.

Em `frontend/.env.local.example` **nenhuma variável nova**: o DSN do Sentry e as
flags de consentimento do frontend são do bloco de frontend ( Bloco B, em
execução), e declarar o mesmo nome aqui criaria duas fontes de verdade. O que
escrevi foi o contrato do lado do frontend, sem nomear variável.

## C1.15 — Script de validação

`scripts/observability/validar-infra.sh`: `bash -n` + `shellcheck` (quando
existe) + bit de execução, JSON com forma de dashboard importável, YAML das
regras com `severity`/`runbook_url`/`description` obrigatórios, **invariante de
drift dos três site confs do Nginx**, `nginx -t` com o binário real, `systemd-analyze
verify`, `docker compose config` + extração e validação dos healthchecks, `alloy
validate`, Terraform (quando existir) e varredura de segredo.

A regra de ouro: **item pulado sai como PULADO, nunca como OK**, e há um nível
AVISO/pendência que vira falha com `--estrito` (para o CI, em C2.5). Um
validador que mente é pior que nenhum validador.

O invariante de drift é o que pede a tarefa: os três site confs são quase
cópia, então o script normaliza os tokens de ambiente e exige que o corpo (do
`upstream` ao fim) seja **byte-idêntico** nos três. Hoje passa; se alguém editar
só um, falha com o diff.

**Rodada completa real:**

```
$ scripts/observability/validar-infra.sh
  51 OK, 1 AVISO, 1 PULADO, 0 FALHOU    (exit 0)
```

O AVISO é o `runbook_url` com placeholder `.invalid` — pendência real e
deliberada (ver abaixo). O PULADO é `shellcheck` (não instalado aqui).

Cinco erros meus foram encontrados por essas checagens durante a escrita, e
todos corrigidos: `ExecCondition` em `[Unit]`; `${m%"$sufixo"}` que não remove
nada (a aspa vira parte do padrão — a comparação foi para Python); query
extraída 6× a mais por um regex impreciso no YAML; contagem de métricas
que não incluía as views; e o parsing do healthcheck do compose acusando um
**comentário** meu que explicava o defeito (agora roda sobre o config já
resolvido pelo Compose). Também corrigi um bug do próprio script: `ESTRITO=0`
declarado **depois** do parsing apagava a flag `--estrito`.

Para funcionar em Docker Desktop (onde `/tmp` não é caminho compartilhado), a
validação em container usa `docker create` + `docker cp` + `docker start -a`, e
não bind mount.

## C1.16 — README da malha

`infra/observability/README.md`: o mapa do desenho, log técnico × analytics (a
separação que o plano pede, em tabela), ordem de instalação **com o porquê de
cada passo** (o `http-cache.conf` antes dos sites; os marcadores), consultas
de LogQL e PromQL do dia a dia, **as 7 limitações conhecidas** e o que depende
de provisionamento externo, e o que foi adiado para C2.

---

## Validação: o que foi EXECUTADO e o que NÃO

**Executado de verdade, com saída real:**

| O que | Como |
|---|---|
| `nginx -t` nos 3 site confs + `http-cache.conf` | binário oficial `nginx:alpine` 1.31.6, conf renderizado |
| Gate de `/metrics` e `/health-detail` (7 casos) | nginx no ar, requests de dentro e de fora |
| `X-Request-ID` válido/inválido/ausente + validade do JSON do log | nginx no ar, saída conferida com `jq` |
| Drift dos 3 site confs | normalização + `diff` (byte-idêntico) |
| `systemd-analyze verify` (4 units) | systemd 259 local |
| `docker compose config` + shell/Python dos healthchecks | Docker Compose v5.5.1 |
| Lógica do healthcheck do beat (5 casos) | Python com `/proc/1/cmdline` e globbing simulados |
| `alloy validate` | imagem oficial `grafana/alloy:latest`, env de placeholders |
| Gate de env do Alloy (4 cenários) | execução local |
| Backup fail-closed (4 caminhos) | PostgreSQL 16 real em container, backup completo |
| Watchdog de backup (8 cenários) | execução local, JSON conferido com `jq` |
| Standalone `prepare`/`smoke` (6 cenários) | `node server.js` fake, portas livres |
| JSON de dashboards/checks/lifecycle | `jq -e` + forma de dashboard importável |
| Regras de alerta (16) | PyYAML + checagem de campos obrigatórios |
| `bash -n` em todos os scripts | 8 scripts |
| Varredura de segredo + `.env` versionado | `git status`/`git ls-files` |

**NÃO executado (pendências explícitas, não "validado"):**

1. **`shellcheck`** — não instalado neste ambiente. A análise estática de shell
   não foi feita. O script já o executa quando presente.
2. **`alloy fmt --test`** — deliberadamente não usado: o `alloy fmt` do Alloy
   canonicaliza com **tab** e o projeto usa 4 espaços. O que valida é
   `alloy validate` (parse + validação de componentes/argumentos). Registrado
   para quando o gate entrar na CI (C2.5).
3. **`systemd-analyze verify` na VPS** — aqui o aviso "celery não é executável"
   é esperado (o app não existe neste host). Em homologação ele deve sair limpo.
4. **Substituição do marcador `__OBS_TOKEN_ESPERADO__`** e o comportamento do
   gate com um token real: só na VPS, com o valor real fora do repositório.
5. **Rótulo interno do journal no `loki.relabel`** — usei o nome do exemplo
   oficial (`__journal__systemd_unit`); se a coleta de journal vier vazia na
   VPS, este é o primeiro lugar a olhar (verificar com
   `journalctl -o json` o nome real do campo). Não afirmei que funciona: afirmei
   que **não coletar é o comportamento seguro** quando a variável está vazia.
6. **`User=`/`Group=` das units** — o repositório não conhece o usuário do
   deploy. Deixei `User=apps` com o comando de ajuste no cabeçalho de cada unit.
7. **Carregar regras no Mimir, importar painéis, provisionar Grafana/Better
   Stack/R2/Sentry, e testar entrega de alerta** (critério 41) — ação humana com
   credencial.
8. **Restore real a partir do R2** e **teste mensal de restore** (critério 35) —
   exige bucket e janela.

## Decisões que valem revisão do orchestrator

1. **Template units no lugar dos nomes do plano** (`celery-worker@.service` em
   vez de `celery-worker.service`) — uma VPS, três ambientes. Reversível, mas
   muda o nome de arquivo em relação ao plano.
2. **`infra/nginx/http-cache.conf` deixou de ser opcional.** Os site confs
   referenciam variáveis definidas nele; sem ele, `nginx -t` falha e o
   deploy-hook de certificado não recarrega. É falha ruidosa, mas é uma
   **dependência nova de ordem de instalação** na VPS — e a documentação
   (`CI-CD.md`/`infra/DEPLOY.md`) que registraria isso está bloqueada para C2.
   **Este é o item de maior risco operacional do bloco.**
3. **`runbook_url` com domínio reservado `.invalid`** (RFC 2606, nunca resolve).
   Preferi um placeholder impossível de confundir com um endereço real a um
   inventado; `validar-infra.sh` reporta como AVISO e vira falha com
   `--estrito`.
4. **Watchdog de backup não vira métrica.** Não existe textfile collector no
   Alloy, e inventar um painel de idade de backup seria a mesma promessa vazia
   que o plano proíbe. O atraso é canal externo + exit code + JSON.
5. **`BACKUP_HEARTBEAT_REQUIRED=1` por padrão** faz o backup sair com 21 se o
   canal de alerta estiver quebrado. É deliberado (o espírito da run), mas é uma
   mudança que pode "quebrar" o cron de alguém que ainda não configurou o
   Better Stack — daí o escape explícito e documentado.
6. **Nenhuma seção de documentação em `CI-CD.md`, `infra/DEPLOY.md` ou
   `PROD_DECISOES.md`** — bloqueados. O conteúdo equivalente está no
   `infra/observability/README.md` e neste arquivo; a consolidação nos três
   docs é C2.8.

## Adiado para o Bloco C2 (por dependência de ownership)

Nenhum item depende de `.github/`, que é do lote P0-1 com diff aberto:
C2.1 release atômica; C2.2 PM2 executando o standalone (o script de C1.5 está
pronto e o plano de promoção já está escrito em `CI-CD.md` §P1-5, sem reescrita);
C2.3 instalação das units no deploy; C2.4 source maps do frontend; C2.5 gate
`validar-infra.sh --estrito` na CI; C2.6 SSH por chave; C2.7 segredos de alerta
e Grafana; C2.8 documentação nos três docs.

## Depende de ação humana (sem segredo por canal)

Contas com MFA (Grafana Cloud US, Better Stack, R2, Sentry); Contact Points
(`<CP_CRITICO_PRINCIPAL>`, `<CP_CRITICO_SUPLENTE>`, `<CP_WARNING>`) e canais
(e-mail do principal e do suplente, Telegram/Slack); domínios reais de dev,
homolog e prod e a decisão do domínio canônico; URL de heartbeat do cron
monitor; endereço interno de runbook; decisão humana sobre a retenção remota de
90 dias; e a janela de produção para o teste de restore.
