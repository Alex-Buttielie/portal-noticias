# Bloco D2 — fechar as lacunas de integração que a remediação revelou

Run `20260925-1020-observabilidade` · branch `observability-20260925-1020` ·
pai: `5e7fe90` (remediação de backend, 4 majors).

A remediação corrigiu quatro majors **no código**. O que ela deixou para trás
são três promessas de configuração que ninguém tinha feito ainda: o leitor
seguro de IP que não tinha o que ler, o canal de job que não chegava a nenhum
dos dois lados, e duas métricas novas sem regra de alerta. É a mesma classe de
defeito duas vezes seguidas — uma variável que chega a um lado do sistema e não
ao outro — e é o que este bloco fecha.

Escopo: **configuração e documentação**. `backend/`, `frontend/`,
`docker-compose*.yml`, `scripts/release/` e o estado de outras runs não foram
tocados. Nenhum `git add`/`git commit` foi feito (o orchestrator commita).

---

## 1. As três lacunas (o que foi encontrado, com evidência)

### Lacuna 1 — o leitor seguro de XFF não tinha o que ler

`backend/config/proxies.py` (achado MAJOR-1) lê `X-Forwarded-For` **só**
quando o par (`REMOTE_ADDR`) é o loopback ou uma rede declarada, e usa **só o
último elemento** da cadeia. O próprio módulo documenta a invariante exigida do
proxy (linhas 25-26 e 33-36 do docstring): *"as duas configurações usuais do
Nginx (`$proxy_add_x_forwarded_for`, que anexa, e `$remote_addr`, que sobrescreve)
produzem o mesmo último elemento"* e *"o proxy confiável precisa reescrever ou
anexar `X-Forwarded-For` com o endereço real (é o default do Nginx)"*.

Estado encontrado nos três arquivos versionados (`grep X-Forwarded-For
infra/nginx/portal-*.conf`): **zero ocorrências** — 13 `proxy_pass` e 12
`proxy_set_header X-Real-IP` por arquivo, nenhum header de IP para a cadeia.
Consequência: o balde do rate limit do Django continuava caindo no par
(127.0.0.1) — ou, num salto com o header cru, no valor escolhido pelo cliente.

### Lacuna 2 — `OBSERVABILITY_JOB_STATE_FILE` não chegava a nenhum dos dois lados

Verificado **no código**, não por suposição:

| Papel | Onde, no código | Processo | Arquivo de ambiente |
|---|---|---|---|
| **Escritor** | `config/celery.py` sinais `task_postrun`/`task_retry` → `job_state.registrar_task/registrar_retry` → `_gravar` | `celery-worker@<env>` | `/etc/portal/celery-<env>.env` |
| **Leitor** | `config/observability_views.py::metrics_view` → `job_state.publicar_metricas`; e `config/health.py::check_celery_jobs` → `job_state.ler` | gunicorn do PM2 | `backend/.env` |

`settings.py:543` define a variável e o comentário (linhas 535-542) avisa que o
nome real do setting de idade é `OBSERVABILITY_JOB_STATE_MAX_AGE_SECONDS`
(`settings.py:544`, default 900) — registrado aqui porque a tarefa citava
`OBSERVABILITY_JOB_STATE_FILE_MAX_AGE_SECONDS`, que **não existe** no código.
O que foi documentado e provisionado é o nome que `job_state.py:47-48` lê.

Os dois processos leem arquivos de ambiente **sem nada em comum**: o gunicorn
sobe com `set -a; . ./.env` (só `backend/.env`); as units systemd leem
`/etc/portal/celery-<env>.env`. Sem a variável nos dois, o canal fica desligado
e o check `celery_jobs` responde `not_configured` — que, por desenho
(`CHECKS_SEM_SINAL_PROPRIO` em `health.py:57`), conta como degradação. O
sintoma é o pior possível: portal no ar, `degraded` "normal", e o reflexo
natural do operador seria **desligar o check** — apagando o ponto cego em vez de
fechá-lo.

### Lacuna 3 — dois sinais novos sem alerta

`backend/config/metrics.py:482` (`portal_job_task_idle_seconds`) e
`backend/config/metrics.py:495` (`portal_health_check_not_configured`) foram
declarados na remediação. As 16 regras de `infra/observability/alerts/` (7 +
9) não cobriam nenhuma das duas.

---

## 2. O que mudou

| Arquivo | Mudança |
|---|---|
| `infra/nginx/portal-{dev,homolog,prod}.conf` | `proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;` nos **13** upstreams de cada arquivo (12 que já tinham `X-Real-IP` + o `location /` do Next.js, que ganhou o par `X-Real-IP` + `X-Forwarded-For`); item 3 no bloco "Regras que o portal assume" do cabeçalho |
| `scripts/observability/validar-infra.sh` | checagem nova de XFF (1:1 com `proxy_pass`, valor aceito, `$http_x_forwarded_for` proibido); checagem nova "nada soma `portal_job_*`"; **corrigida** a checagem de métrica inexistente, que era vacuosa |
| `.github/workflows/deploy.yml` | `OBSERVABILITY_JOB_STATE_FILE` no `/etc/portal/celery-<env>.env` (na criação do arquivo) e no `backend/.env` (append sem reescrever, com aviso-e-preserva), + `OBSERVABILITY_JOB_STATE_MAX_AGE_SECONDS=900`; comparação das duas pontas no log do deploy; conferência do XFF **instalado** (`nginx -T`) e do canal no job `validate` |
| `infra/observability/alerts/regras-operacao.yaml` | 3 regras: `PortalJobAtrasado` (critical), `PortalJobNuncaConcluiu` (warning), `PortalCheckSemSinal` (warning) — total do arquivo 10 → 13, do conjunto 16 → 19 |
| `infra/observability/alerts/README.md` | cobertura das regras novas; nova decisão de dedup nº 2 (item entra na identidade) e o efeito no `mute timing` |
| `scripts/observability/pendencias-ci.txt` | comentário atualizado ("16 regras" → "19"); a chave declarada não mudou |
| `.env.production.example`, `backend/.env.example` | as duas variáveis documentadas como placeholder, sem segredo, com a explicação de qual arquivo é qual ponta |
| `CI-CD.md`, `infra/DEPLOY.md` | seções **novas** (nada reescrito): as duas pontas do canal de job, o XFF na borda, o procedimento do operador e a armadilha do CDN |

### Decisões que precisam de justificativa

**`$proxy_add_x_forwarded_for` e não `$remote_addr`.** Os dois satisfazem a
invariante que `proxies.py` documenta (último elemento = cliente real deste
salto). Escolhi o que **anexa** porque preserva a cadeia de hops — que o log de
borda (`log_format portal_acesso`, `http-cache.conf`) e uma futura CDN
precisam — e porque é o default do Nginx, que é o que o docstring do módulo
cita como esperado. Nenhum consumidor deste repositório lê o primeiro elemento
da cadeia: a única leitura de `HTTP_X_FORWARDED_FOR` no código inteiro é
`proxies.py:137` (`identificar_cliente`), que usa `entradas[-1]`; o
`X-Forwarded-Proto` é lido por `SECURE_PROXY_SSL_HEADER` e continua intacto.
Com CDN na frente, o procedimento está em `infra/DEPLOY.md` 9.4.2
(`realip` + `set_real_ip_from` do prefixo do provedor) — sem ele, todo mundo
cairia no mesmo balde de rate limit, e isso está escrito antes de acontecer.

**Não afrouxei o gating dos endpoints privados.** O `X-Forwarded-For` agora é
confiável na borda, mas `observability_views` continua ignorando-o para
autorização. A decisão é do backend e está correta por si (ignorar o header
para autorização é fail-closed); este bloco só faz a infraestrutura entregar o
que o leitor de rate limit já exigia. Ver resíduo 6.1.

**`assegurar_linha_env` no lugar do bloco do heartbeat.** O bloco do beat
(C2.3) foi deixado como está, de propósito: está no ar desde o C2.3 e
reescrevê-lo no mesmo deploy que introduz o canal de job seria trocar uma
coisa que funciona por outra que ninguém testou. A função nova tem a mesma
semântica (acrescenta sem reescrever; com valor divergente, avisa e preserva) e
está testada (§ 4, casos 1-6).

**Três regras em vez de duas.** `portal_job_task_idle_seconds` tem dois
significados distintos: *atraso* (o valor é uma idade) e *sentinela* `-1`
(a task tem registro, ou seja rodou, e nunca terminou com sucesso). Um alerta
único teria que escolher um dos dois e perder o outro. A âncora do
`PortalJobAtrasado` é a task de ingestão (15 min) e o corte é 45 min = três
intervalos — o mesmo dimensionamento de `PortalCelerySemExecucao`; as tasks
diárias (07:00, 19:00, 04:17) ficariam com 20 h de "atraso" e disparam alarme
falso garantido se o corte fosse 45 min para todas.

---

## 3. Passo a passo para o operador (sem errar a configuração)

### 3.1 `X-Forwarded-For`

```bash
# 1) Instalar o conf do ambiente (o que está no repositório, não o que está na VPS)
sudo cp infra/nginx/portal-prod.conf /etc/nginx/sites-available/portal-prod
sudo nginx -t && sudo systemctl reload nginx

# 2) Conferir o ARQUIVO INSTALADO: 13 diretivas por site conf
sudo nginx -T 2>/dev/null | grep -c 'proxy_set_header X-Forwarded-For'

# 3) Conferir o COMPORTAMENTO (o que interessa): 35 POSTs com o MESMO
#    X-Forwarded-For forjado têm de esgotar o limite do par real
for i in $(seq 1 35); do
  curl -sS -o /dev/null -w '%{http_code} ' -X POST \
    -H 'X-Forwarded-For: 10.0.0.1' -H 'Content-Type: application/json' \
    --data '{"email":"inexistente@example.invalid"}' \
    https://<host>/api/auth/cadastro/
done; echo
```

Se o passo 2 der 0: o conf da VPS é antigo (o repositório não instala nada por
conta própria). Se o passo 3 der 201 em todas: o bypass voltou — confira se
algum proxy/CDN foi posto na frente sem `realip` (DEPLOY.md 9.4.2).

Erros que produzem exatamente o bug que estamos fechando:
`proxy_set_header X-Forwarded-For $http_x_forwarded_for;` (repassa o header do
cliente) e um `proxy_set_header` só no nível do `server` com os locations
repetindo o par errado. O validador pega os dois.

### 3.2 Canal de job (as duas pontas, obrigatórias)

```bash
ENV=prod
# A) produtor — /etc/portal/celery-$ENV.env
grep -q '^OBSERVABILITY_JOB_STATE_FILE=' /etc/portal/celery-$ENV.env \
  || echo 'OBSERVABILITY_JOB_STATE_FILE=/var/lib/portal-observabilidade/jobs-'"$ENV"'.json' \
     | sudo tee -a /etc/portal/celery-$ENV.env
# B) consumidor — backend/.env (mesmo caminho, sem segredo)
grep -q '^OBSERVABILITY_JOB_STATE_FILE=' /home/apps/portal-$ENV/backend/.env \
  || printf 'OBSERVABILITY_JOB_STATE_FILE=/var/lib/portal-observabilidade/jobs-%s.json\n' "$ENV" \
     >> /home/apps/portal-$ENV/backend/.env
# C) os dois valores têm de ser IGUAIS (o log do deploy imprime os dois)
grep -h '^OBSERVABILITY_JOB_STATE_FILE=' /etc/portal/celery-$ENV.env /home/apps/portal-$ENV/backend/.env
# D) reiniciar os DOIS processos (o .env é lido no boot)
sudo systemctl restart "celery-worker@$ENV"
pm2 restart "portal-api-$ENV"
# E) provar que o canal fecha
curl -sS -H "Authorization: Bearer $TOKEN" http://127.0.0.1:5103/metrics \
  | grep -E '^portal_job_(task_idle_seconds|state_age_seconds)'
```

Regras de ouro (as duas já são o comportamento do deploy, e é o que impede o
erro): **nunca** sobrescrever `backend/.env` (é gerado uma vez); **nunca**
trocar em silêncio um valor existente (se divergir, corrija à mão e entenda por
que divergiu); **nunca** desligar o check `celery_jobs` para tirar o
`degraded` — o `degraded` está dizendo a verdade.

Com `celery_systemd: false` ou na topologia do `docker-compose.yml`, o bloco do
deploy não roda: o caminho tem de chegar ao serviço do Celery pelo mecanismo
daquele ambiente, com o **mesmo** valor. Está escrito em DEPLOY.md 9.4.1.

---

## 4. Validações executadas (saída real)

Tudo abaixo foi executado nesta máquina, nesta ordem. O que não pôde ser
executado está listado como **não executado** — não como "validado".

### 4.1 `bash -n` nos scripts e nos blocos shell dos workflows

```
bash -n scripts/observability/validar-infra.sh            -> OK
bloco shell do job deploy (deploy.yml)                     -> bash -n OK
bloco shell do job validate (deploy.yml)                   -> bash -n OK
```

Os blocos shell dos workflows foram extraídos com `yaml.safe_load` (expressões
`${{ }}` substituídas por um placeholder) e passados a `bash -n`.

### 4.2 `yaml.safe_load` dos workflows

```
deploy.yml: OK, 3 jobs (verify, deploy, validate)
ci.yml: OK, 3 jobs
rollback.yml: OK, 2 jobs
```

`actionlint` **não está instalado** nesta máquina (`command -v actionlint` vazio):
a análise estática de workflow não foi executada. O que rodou foi o parse do
YAML + `bash -n` do conteúdo shell, o que cobre a maior parte da classe de
defeito que este bloco toca.

### 4.3 `nginx -t`

Não há binário `nginx` no host. O `validar-infra.sh` cai no caminho de
container que já existia no projeto e executou de verdade:

```
[OK]     nginx -t (binário oficial, em container, imagem oficial do Nginx)
```

Os três site confs também continuam **estruturalmente idênticos** do `upstream`
ao fim (checagem existente do validador, que compara os três com normalização de
ambiente/porta/domínio).

### 4.4 `scripts/observability/validar-infra.sh --estrito`

```
57 OK, 0 AVISO, 1 PENDENTE DECLARADA, 1 PULADO, 0 FALHOU   (exit 0)
[PULADO] shellcheck não instalado (análise estática de shell não executada)
[PENDENTE] runbook_url com placeholder exemplo.invalid (chave declarada)
```

Trechos que importam desta execução:

```
[OK] 61 queries de painel/alerta extraídas
[OK] nenhuma expr usa portal_ingestion_executions_total
[OK] nenhuma expr de painel/alerta soma portal_job_* (max()/last() em toda expr de job)
[OK] métricas usadas em painel/alerta conferidas contra o inventário do backend
[OK] regras-operacao.yaml — 13 regras, todas com severity, runbook_url e description
[OK] regras-disponibilidade.yaml — 6 regras, todas com severity, runbook_url e description
[OK] dev: X-Forwarded-For escrito nos 13 upstream(s) (valor aceito)
[OK] homolog: X-Forwarded-For escrito nos 13 upstream(s) (valor aceito)
[OK] prod: X-Forwarded-For escrito nos 13 upstream(s) (valor aceito)
```

### 4.5 Teste **negativo** do validador (prova de que as checagens não são vazias)

Uma checagem que não acusa nada é pior que nenhuma. Quebrei cada regra de
propósito, rodei o validador e restaurei os arquivos (confirmado por `md5sum -c`):

| Injeção | Resultado esperado | Resultado obtido |
|---|---|---|
| tira 1 diretiva XFF de `portal-prod.conf` | FALHA (contagem 1:1) | FALHOU |
| XFF vira `$http_x_forwarded_for` | FALHA (header do cliente) | FALHOU |
| `sum by (...) (portal_job_task_idle_seconds)` no alerta | FALHA (gauge absoluto) | FALHOU |
| métrica inexistente no alerta | FALHA (métrica sem inventário) | FALHOU |

O último caso é a **correção de um defeito preexistente do validador**: a
checagem "toda métrica usada existe no backend" recebia as queries por
`printf ... | python3 - <<'EOF'`, e o heredoc **redefine o stdin** do
`python3 -` (que é o próprio programa), então `sys.stdin.read()` voltava vazio e
a comparação nunca acusou nada desde que foi escrita. Passa a ler um arquivo.
Nenhum painel nem alerta precisou de correção — a checagem agora roda de fato e
o conjunto continua passando.

### 4.6 Teste funcional do shell novo do deploy

`assegurar_linha_env` foi extraída do `deploy.yml` e exercitada contra um
`backend/.env` de mentira:

| Caso | Comportamento exigido | Resultado |
|---|---|---|
| 1. `backend/.env` ausente | avisa, não quebra o deploy | AVISO, rc 0 |
| 2. chave ausente | acrescenta, **preserva o resto**, mantém o modo 640 | OK (conteúdo + `640`) |
| 3. chave com o valor certo | não toca no arquivo | md5 idêntico |
| 4. chave com **outro** valor | avisa e **preserva** o valor do operador | md5 idêntico |
| 5. chave repetida | usa a última (mesma semântica do bloco do beat), não duplica | md5 idêntico |
| 6. segunda chave (`..._MAX_AGE_SECONDS`) | mesmo comportamento | OK |

O bloco do job `validate` também foi exercitado em sandbox (`sudo` e `nginx -T`
falsos): pontas iguais → confirmação; pontas divergentes → AVISO nomeando os
dois valores; `nginx -T` sem site confs → "NÃO verificado" (e não "ausente",
que seria acusação falsa); VPS com 3 ambientes e só 1 atualizado → detects
13 ≠ 13×3.

### 4.7 Regras de alerta: parser e comportamento reais

`promtool` (imagem oficial `prom/prometheus`, via `docker cp` — `/tmp` não é
compartilhado com o Docker Desktop nesta máquina):

```
promtool check rules regras-operacao.yaml        -> SUCCESS: 13 rules found
promtool check rules regras-disponibilidade.yaml -> SUCCESS: 6 rules found
promtool test rules  (5 cenários)                -> SUCCESS (rc 0)
```

Os cinco cenários do `test rules` (arquivo gerado a partir das próprias regras,
com as annotations extraídas delas para não divergirem):

1. **60 min sem sucesso, DUAS instâncias do coletor com o mesmo relógio
   absoluto → UM alerta** (`{ambiente=production, task=…ingerir_noticias}`). É a
   prova de que a agregação é `max()`: com `sum()` seriam 7200 e o alerta
   mediria o número de coletores, não o atraso.
2. Task no ritmo normal (5 min) + task **diária** parada há 20 h → **nenhum**
   alerta nos dois (`PortalJobAtrasado` e `PortalJobNuncaConcluiu` vazios).
3. Sentinela `-1` → `PortalJobNuncaConcluiu` dispara com o `task` no rótulo;
   `PortalJobAtrasado` **não** dispara com o mesmo dado.
4. `celery_jobs` cego dispara; `redis` (cujo `not_configured` é escolha do
   ambiente) e `celery_beat = 0` **não** disparam.
5. Mesmo problema em dois ambientes → **duas** instâncias, uma por ambiente
   (a dedup por rótulo, e o motivo de o `mute timing` precisar de `check`/`task`).

### 4.8 Diff auditado

Toda a inserção deste bloco foi revisada linha a linha no `git diff`, porque a
ferramenta de escrita **descartou um caractere** em uma das edições (o nome da
função ficou `asegurar_linha_env` em vez de `assegurar_linha_env`, 18 em vez de
19 caracteres). O sintoma apareceu como `command not found` no teste funcional
(§ 4.6), não como erro de review. Nome corrigido e conferido por contagem de
bytes; o bloco do `validate` teve um `fi`/`else` órfão de uma substituição
posterior, achado pelo `bash -n` e removido.

Além da leitura do diff, uma varredura automática conferiu, nos 13 arquivos
tocados, (a) a presença de cada token técnico com a grafia exata
(`assegurar_linha_env`, `OBSERVABILITY_JOB_STATE_FILE`,
`OBSERVABILITY_JOB_STATE_MAX_AGE_SECONDS`, `proxy_add_x_forwarded_for`,
`portal_job_task_idle_seconds`, `portal_health_check_not_configured`,
`set_real_ip_from`…) e (b) a ausência de caractere fora do português
(CJK/cirílico). Resultado: `nenhuma corrupcao por caractere detectada`. O
detector de "palavra repetida" foi **removido** do script: em português ele
acusa `não não`/`que que` legítimos e não encontra defeito nenhum.

### 4.9 Concorrência nesta árvore de trabalho (fato, não hipótese)

Enquanto este bloco trabalhava, **outra sessão** passou a editar o mesmo
`.github/workflows/deploy.yml` (o gate `usuarios_teste`, da run
`20260925-1836-usuarios-teste-dev-homolog`). O arquivo hoje contém as duas
mudanças. Consequências práticas:

* o commit deste bloco tem de ser feito com **paths explícitos** e o
  `deploy.yml` precisa passar por revisão das duas runs — as minhas três adições
  são o `OBSERVABILITY_JOB_STATE_FILE` no env do worker, a função
  `assegurar_linha_env` + a conferência das duas pontas no job `deploy`, e a
  conferência do XFF instalado e do canal no job `validate`;
* todas as validações deste bloco foram **reexecutadas** no estado atual do
  arquivo depois da mudança alheia: `yaml.safe_load` OK, `bash -n` OK nos dois
  blocos shell, e os testes funcionais (§ 4.6) continuam passando com o mesmo
  resultado — as duas mudanças não se sobrepõem em nenhuma linha;
* nenhum outro arquivo deste bloco foi tocado pela outra sessão.

---

## 5. O que ainda exige ambiente real

Nada abaixo é verificável neste repositório; a lista é o que um operador tem de
fazer na VPS, e o que a CI **não** prova.

1. **Instalar o conf novo** (`sudo cp` + `nginx -t` + reload) nos ambientes
   reais. O deploy **não** instala o conf do Nginx: a VPS pode continuar com o
   arquivo antigo, e o job `validate` agora avisa sobre isso.
2. **Comportamento do rate limit** com header forjado (§ 3.1 passo 3) — o
   único teste que prova o bypass fechado de verdade. `config/proxies.py` tem
   testes unitários, mas o caminho completo (curl → nginx → gunicorn → DRF) só
   existe na VPS.
3. **O canal de job produzindo arquivo e métrica** (§ 3.2 passo E). Em
   especial: o `celery-worker@<env>` precisa escrever
   `/var/lib/portal-observabilidade/jobs-<env>.json` — se o timer de heartbeat
   nunca rodou, o diretório ainda não existe e a gravação falha (o sintoma é
   `estado de job não gravado` no journal e `celery_jobs: error`).
4. **Disparo dos alertas novos** no Mimir: carregar as regras, disparar
   `PortalJobAtrasado`/`PortalCheckSemSinal` de verdade e confirmar a entrega
   nos canais (critério 41 da run). Os `runbook_url` continuam no domínio
   reservado `.invalid` — pendência já declarada, agora em 19 regras.
5. **Cloudflare/CDN**: se for ativado, o procedimento `realip` da DEPLOY.md
   9.4.2 precisa ser aplicado **antes** de ligar o proxy laranja, e
   conferido com o mesmo teste de header forjado.
6. **Acesso ao `nginx -T` com sudo** no job `validate`: sem ele, a conferência
   do conf instalado sai como "NÃO verificado" (por desenho — Accusation falsa é
   pior que ausência de conferência).
7. **`celery_systemd: false` / topologia Compose**: o canal precisa ser
   provisionado por fora do bloco do deploy (documentado, não automatizado —
   `docker-compose*.yml` está fora do escopo deste bloco).

---

## 6. Resíduos e pendências (nada aqui foi "resolvido" em silêncio)

1. **`backend/config/observability_views.py:33-35`** afirma que *"o Nginx não o
   sobrescreve por padrão"* como justificativa para ignorar o `X-Forwarded-For`
   na autorização. Depois deste bloco, o Nginx **passa** a sobrescrevê-lo. A
   decisão continua correta (ignorar o header para autorização é fail-closed) e
   por isso **não** mexi: o arquivo é do bloco de backend e a frase é do
   backend. O texto merece uma revisão em bloco próprio.
2. **`PortalCelerySemExecucao`** (`regras-operacao.yaml`) consome
   `portal_celery_tasks_total`, que vive no registro **por processo** do worker
   e, nesta topologia, não aparece em nenhum scrape (é o mesmo achado MAJOR-4).
   O `PortalJobAtrasado` cobre o mesmo sintoma por um caminho que de fato chega
   ao scrape. Não removi nem reescrevi a regra antiga: duas fontes para o mesmo
   sintoma, uma delas possivelmente cega, é decisão de quem opera o Mimir — e o
   comentário da regra nova registra a relação.
3. **`portal_job_state_age_seconds`** (o frescor do próprio canal) segue **sem
   alerta**. O check `celery_jobs` o vê como `degraded`, mas só quando alguém
   abre `/health-detail`. Fora do escopo pedido (as duas métricas citadas), e
   registrado para não virar esquecimento.
4. **`PortalCheckSemSinal` não usa `absent()`**, de propósito: o `/metrics` não
   roda os checks, então a série só existe depois de uma requisição ou de um
   `/health-detail` — `absent()` seria pager a cada restart. Está escrito no
   comentário da regra.
5. **Fora de escopo por instrução:** `scripts/release/verificar-proveniencia.sh`
   continua sem workflow (R-1 de outra run) e a divergência de domínio
   `.com` × `.com.br` segue sem correção (R-2). Nada nesta tarefa os tocou.
6. **`docker-compose*.yml`** não recebeu `OBSERVABILITY_JOB_STATE_FILE` no
   serviço `celery-worker` (fora de escopo por instrução). Num ambiente Compose
   o canal nasce desligado até alguém declarar a variável lá — está em DEPLOY.md
   9.4.1 como procedimento manual.
7. **Uniformização do bloco do heartbeat** com `assegurar_linha_env`: existe
   duplicação de ~20 linhas de shell sutil entre o bloco do beat (C2.3) e a
   função nova. Deixei o bloco testado intacto de propósito; unificá-lo é uma
   mudança própria, com o próprio risco.

## 7. Inventário de arquivos tocados

```
.github/workflows/deploy.yml                        (deploy + validate)
infra/nginx/portal-dev.conf
infra/nginx/portal-homolog.conf
infra/nginx/portal-prod.conf
infra/observability/alerts/regras-operacao.yaml
infra/observability/alerts/README.md
scripts/observability/validar-infra.sh
scripts/observability/pendencias-ci.txt
.env.production.example
backend/.env.example
CI-CD.md
infra/DEPLOY.md
agentic-framework/state/run-20260925-1020-observabilidade/bloco-d2-notas.md (este)
```

Nada em `backend/`, `frontend/`, `docker-compose*.yml`, `scripts/release/`,
`subir-localhost.sh` ou no estado de outras runs foi alterado.
