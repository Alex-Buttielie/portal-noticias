# Notas do Bloco C2 — deploy atômico, PM2 standalone, systemd, CI/CD

Run: `20260925-1020-observabilidade`. Branch: `observability-20260925-1020`.
Execução: subagente delegado, 2026-09-25. Itens **C2.1 a C2.8** do
`bloco-c-plano.md`.

`.github/` foi liberado nesta iteração (era o bloqueio do C1), e
`CI-CD.md`/`PROD_DECISOES.md`/`infra/DEPLOY.md` saíram do diff do lote P0-1,
então as duas runs puderam ser reconciliadas. `backend/` e `frontend/`
pertencem a outros dois agentes e **não** foram tocados por este bloco
(exceção: leitura de `frontend/package.json`, `next.config.js` e `package-lock.json`
para descobrir a versão do `sentry-cli` e a configuração de sourcemaps).

---

## 0. Escopo entregue, em uma tela

| ID | O que foi feito | Onde |
|---|---|---|
| C2.1 | Release do tier web em `frontend/releases/<id>/`, smoke nela, symlink `current` alternado **só depois**, release anterior em `previous`, retorno automático quando o processo não sobe | `.github/workflows/deploy.yml` |
| C2.2 | PM2 executa `node .next/standalone/server.js` via `infra/standalone/run-standalone.sh`, com `HOSTNAME`/`PORT` explícitos e `public/`+`.next/static` copiados; `npm start` mantido como `web_runtime: npm` | idem |
| C2.3 | `celery-worker@<env>` e `celery-beat@<env>` instaladas e ativadas pelo deploy, com `%i` e `User=`/`Group=` resolvidos e `/etc/portal/celery-<env>.env` provisionado | idem |
| C2.4 | `sentry-cli sourcemaps upload` no `frontend-build`, fail-open em duas camadas | `.github/workflows/ci.yml` |
| C2.5 | Job `infra-validate` rodando `validar-infra.sh --estrito`, com terceiro estado "pendência declarada" | idem + `scripts/observability/` |
| C2.6 | `VPS_SSH_KEY` e `VPS_HOST_FINGERPRINT` aceitos como alternativa, **senha preservada** | 6 workflows |
| C2.7 | Inventário de secrets com "o que fazer quando falta" | `CI-CD.md` §P1-6 |
| C2.8 | Seções novas em `CI-CD.md` (§P1-6), `infra/DEPLOY.md` (§9), `PROD_DECISOES.md` (8-16), `README.md`, `ARCHITECTURE.md` | 4 docs |

**Fronteiras respeitadas:** `scripts/release/verificar-proveniencia.sh` segue
fora de qualquer workflow (R-1); a divergência de domínio `.com` × `.com.br`
segue sem correção (R-2); `DJANGO_ALLOWED_HOSTS` com o IP fixo foi apenas
**registrado** como pendência, sem ser tocado. `backend/`, `docker-compose*.yml`,
`.env*`, `agentic-framework/state/run-20260924-*`,
`agentic-framework/state/run-20260925-1433-go-live-producao/`, `scripts/release/` e
`run-state.json` desta run: intocados.

---

## C2.1 — Release atômica

### Decisão central: a release é do TIER WEB, não do app inteiro

Isto é o desvio mais importante em relação à leitura literal do plano, e vale
deixar explícito porque a §P1-5 de `CI-CD.md` pede "publicar uma release em
diretório versionado; trocar symlink e reiniciar o PM2 somente após smoke".

O symlink só pode promover o que **não tem migration e não tem estado**. O
backend usa `git reset --hard` + `migrate` in-place, e mudar isso exigiria:

- mover as units systemd de `/home/apps/portal-%i/backend` para dentro da
  release (o `%i` continua resolvendo, mas o caminho mudaria);
- mover `backend/media/` e o `backend/.env`, que hoje sobrevivem ao `reset`
  por serem untracked;
- um `.venv` por release (centenas de MB × 3 ambientes numa VPS de 4 GB, que
  ainda divide memória com Postgres, Redis e as três stacks);
- revisar `infra/backup/pg_backup_pm2.sh`, que assume o caminho do backend.

O ganho seria **zero**: `git reset --hard` já é atômico quanto ao conteúdo do
arquivo, e o `.venv` é reaproveitado. Já a troca de versão do **frontend** é
justamente onde o problema existia — `next build` reescrevia `.next/` enquanto o
processo em produção lia essa mesma árvore. A release do tier web remove esse
risco específico, que é o risco real.

### Ordem exata e o que cada passo pode quebrar

```text
1. npm ci + next build                    (na VPS, como antes; heap 1536 MB)
2. preparar_release  → copia .next/standalone para releases/<id>/,
                       chama run-standalone.sh prepare (public/ + .next/static)
                       e grava .deployed-sha DENTRO da release
3. smoke_release     → sobe a release em porta livre; /robots.txt,
                       um asset real de .next/static e a Home.
                       ACEITA 503 na Home; REPROVA 5xx e asset ausente.
4. promover_release  → previous = alvo antigo de current;
                       current = release nova  (ln -s + mv -T)
5. restart_or_start  → PM2 sobe current/standalone.
                       Se NÃO ficar online em 3 tentativas:
                       current volta para previous, PM2 sobe nela,
                       e o deploy TERMINA COM ERRO.
6. podar_releases    → mantém 3 por data, protegendo current e previous.
```

Falha em 2 ou 3 aborta o deploy **antes de qualquer mudança visível**: sem symlink
novo, sem restart, sem migration, sem promoção do marker. É a propriedade que o
plano pedia e a razão de o smoke existir.

### Decisões e trade-offs

- **`ln -s` + `mv -T`, nunca `ln -sfn`.** `ln -sfn` remove o link antigo antes
  de criar o novo, e um leitor nesse instante vê `current` inexistente. O par
  usa `rename(2)` sobre o symlink: quem lê vê a release antiga ou a nova, nunca
  um estado quebrado. Cópia do mesmo cuidado está em `infra/DEPLOY.md` §9.2
  para o procedimento manual.
- **O retorno automático termina o deploy com erro de qualquer forma.** Se o PM2
  não sobe na release nova, `current` volta para `previous` e o processo sobe na
  anterior — mas o script faz `exit 1`. Um exit 0 promoveria no `.deployed-sha`
  um SHA cuja release não está no ar, e o marker é a fronteira de recuperação
  (`validate` só promove com `deploy.result == success`). Portal no ar e marker
  correto é melhor que portal no ar e marker mentindo.
- **O caminho "o processo subiu mas o comportamento está ruim" NÃO é
  automaticado.** Um probe verde seguido de decisão ruim exige julgamento: a
  release pode ter migration, e desfazer migration automaticamente não é
  seguro. O procedimento manual está em `infra/DEPLOY.md` §9.2.
- **`RELEASES_TO_KEEP=3` (variável `PORTAL_RELEASES_TO_KEEP`).** Mais que isso
  multiplica o disco pela release; menos que 3 elimina o "anterior do
  anterior". A poda **proíbe** remover os alvos de `current` e `previous` mesmo
  quando ficaram fora do recorte — caso de quatro deploys seguidos, em que o alvo
  do retorno sumiria. `rm -rf` sempre com `${dir:?}`.
- **`releases/` dentro de `frontend/`** porque o symlink `current` é relativo ao
  checkout e o PM2 recebe um caminho estável: trocar o alvo troca a versão
  servida sem reescrever caminho nenhum no `pm2 save`. `frontend/.gitignore`
  ganhou `releases/` (artefato de build, promoção é por symlink).
- **`.deployed-sha` dentro da release.** O rollback por symlink descobre o commit
  sem depender do marker global nem do git. O marker global
  (`$APP_DIR/.deployed-sha`) segue intocado e é o que o `rollback.yml` lê.
- **O que isto NÃO é:** não é blue-green, não é zero downtime. Continua havendo
  janela de restart no mesmo PM2. O §P1-5 e seu gatilho ("quando o deploy
  passar a causar indisponibilidade perceptível") continuam valendo — o ganho
  aqui é **reversibilidade**, não disponibilidade. Isso está escrito no
  documento, não só nas notas.

### Invariantes preservadas (conferidos no diff)

| Invariante | Onde continua |
|---|---|
| `concurrency` sem cancelamento | inalterado (`cancel-in-progress: false`) |
| marker `.deployed-sha` | `write_deployed_sha` inalterado nos dois jobs |
| promoção só após probes verdes | bloco de marker do `validate` inalterado |
| `strict_validate` | inalterado |
| `git_mode: rollback` | inalterado, e `rollback.yml` reaproveita o mesmo script |
| build na VPS, heap 1536 MB | inalterado |

---

## C2.2 — PM2 do frontend no standalone

Reaproveitei `infra/standalone/run-standalone.sh` (C1.5) sem reescrevê-lo: o
deploy invoca `prepare`, `smoke` e `start` dele.

- **Comando do PM2:** `run-standalone.sh start --dir releases/current/standalone
  --host 0.0.0.0 --port <web_port>`, com `HOSTNAME`/`PORT` no ambiente do
  processo. O `exec node server.js` do script garante que o PID do PM2 é o do
  Node.
- **`PATH` explícito no start.** O `npm start` resolvia o node por dentro do npm;
  o `node server.js` não tem essa indireção, e o PM2 executa com o ambiente do
  daemon, que pode não ter o node do nvm no `PATH`. `NODE_BIN="$(command -v node)"`
  é resolvido após `nvm use 20` e o `PATH` é prefixado no start — e o script
  **falha** se o node não for encontrado, em vez de deixar o PM2 iniciar um
  processo que morre sozinho.
- **`HOSTNAME=0.0.0.0` explícito.** Preserva o alcance de hoje (`npm start`
  escutava em todas as interfaces). Sem `HOSTNAME`, o Next standalone escuta no
  hostname do host, que nem sempre é o que o Nginx faz proxy. O
  `run-standalone.sh` já validates.
- **Comportamento do smoke reconfirmado com execução real** (não por leitura):
  Home em 503 **aceita**, 500 **reprovada**, asset estático ausente (404)
  **reprovado**. Ver T6/T8 na tabela de validação.
- **Escape hatch `web_runtime`** (`standalone` | `npm`, padrão `standalone`),
  exposto no dispatch de `rollback.yml`. Sem ele, trocar o runtime do processo em
  produção não teria volta. O caminho `npm` é o código anterior, intacto —
  build in-place, `releases/` não tocado, nenhum symlink.

**Ponto de atenção que só a VPS revela:** o symlink `current` é lido pelo PM2 na
hora do `start`. O processo em execução tem o `server.js` aberto por inode, então
ele **não** muda quando o symlink muda — é por isso que o restart é necessário,
e por isso que a promoção vem antes do restart e não depois.

---

## C2.3 — Units systemd de worker/beat

O achado B4 (Celery inexistente na topologia ativa) é addressed sem tocar em
nenhum processo que o PM2 gerencia: web e API continuam PM2, worker e beat
entraram no systemd.

- **Placeholders resolvidos no deploy:** `%i` = `$SUF` (`dev`/`homolog`/`prod`)
  e `User=`/`Group=` = `id -un`/`id -gn` (o dono do app, o mesmo do PM2). É
  literalmente o que o cabeçalho de cada unit prescreve; root é proibido porque
  o worker tem o mesmo acesso a mídia e banco que a aplicação web.
- **`/etc/portal/celery-<env>.env` é criado se não existir**, com os mesmos
  valores que o serviço `celery-worker` do `docker-compose.yml` já usa
  (`--concurrency=2 --max-tasks-per-child=100`) mais
  `BEAT_HEARTBEAT_FILE`/`OBSERVABILITY_BEAT_HEARTBEAT_FILE`. Os dois
  `EnvironmentFile` das units **não** têm o prefixo `-`, então sem esse arquivo
  a unit **não sobe** (fail-closed proposital): criá-lo aqui é provisionar o que
  a unit exige, não afrouxar a barreira. **Nunca sobrescrito** (T3).
- **Falha de Celery não derruba o deploy.** Web e API já estão no ar, e o worker
  parado é degradação visível em `/health-detail` e no alerta
  `PortalFilaCelery`. Um deploy que caísse por causa do Celery seria pior que o
  Celery parado. `celery_systemd: false` desliga o bloco inteiro.
- **`sudo -n true` como gate.** Sem sudo sem senha (ou sem `systemctl`), a função
  avisa e retorna 0 — não é o caso de uma VPS de produção, mas é o caso de uma
  máquina de teste, e um `sudo` pedindo senha travaria o deploy.

### Correção mínima em arquivo do C1 (declarada, não escondida)

`infra/systemd/celery-beat-heartbeat@.service` ganhou
`StateDirectory=portal-observabilidade` (+ `StateDirectoryMode=0755`).

**Por que era necessário:** a unit tem `ProtectSystem=strict`, que deixa o
sistema de arquivos inteiro somente-leitura exceto as rotas que o systemd
declara graváveis. `/var/lib/portal-observabilidade` (o diretório de
`BEAT_HEARTBEAT_FILE`) não era uma delas, então o `touch -m` do `ExecStart`
falharia **a cada tick** — com o beat VIVO. O efeito seria o oposto do que a
unit existe para ser: `check_celery_beat` envelhecendo até `degraded` e um alerta
disparando com o beat saudável. `StateDirectory` resolve **sem** afrouxar o
`ProtectSystem` (que existe para travar o resto do disco): o systemd cria o
diretório com o dono certo e o libera para escrita. `celery-beat@` não precisa
disto — usa `ProtectSystem=full` e só toca o arquivo num `ExecStartPost`
tolerante a falha. O deploy também faz `install -d` do diretório, o que cobre
`celery-beat@` antes do primeiro tick do timer.

Nenhum outro arquivo do C1 foi alterado. `run-standalone.sh` também não: a nota
"POR QUE O PM2 AINDA NÃO USA ISTO" no fim dele agora descreve uma situação
resolvida e **será atualizada pelo Bloco B/revisão** — não a editei aqui para não
reescrever um artefato de outro bloco sem o contexto dele. Sinalizado como
pendência menor abaixo.

---

## C2.4 — Source maps no CI

Passo novo no final de `frontend-build`, depois do `npm run build`.

- **Fail-open camada 1 — sem token, o passo nem roda.** A detecção é um passo
  anterior que publica um output, porque `if:` **não pode** referenciar
  `secrets` (o GitHub recusa a expressão; isso é constraint da plataforma, não
  escolha de estilo). Com token e org/projeto, o upload roda.
- **Fail-open camada 2 — falha de upload não reprova o build**
  (`continue-on-error`). Source map é insumo de diagnóstico; bloquear um deploy
  por indisponibilidade do Sentry troca um problema pequeno por um grande. A
  alternativa (falhar o build) foi descartada por esse motivo.
- **`sentry-cli` vem como transitiva do `@sentry/nextjs`** (via
  `@sentry/bundler-plugin-core`), versão 2.58.6 no lockfile, e é a **mesma** que
  o `withSentryConfig` usa no build. Cheguei a escrever `npx @sentry/cli@<versão
  do @sentry/nextjs>` e isso está **errado**: o CLI tem linha de versionamento
  própria (2.x) e `@sentry/cli@10.75.3` não existe. A versão agora vem do
  lockfile, com fallback explícito que **avisa e pula** se o binário não
  estiver em `node_modules/.bin`.
- **`release` = `git rev-parse HEAD`**, não `github.sha`: no `workflow_call` o
  checkout é `inputs.checkout_ref`, e em PR o `github.sha` é o merge commit.
  Source map de outro release não correlaciona stack trace.
- **Secrets declarados em `on.workflow_call.secrets` do `ci.yml`**, todos
  `required: false` — é o que mantém o CI verde em fork e antes de a conta
  existir. `deploy.yml` os repassa no job `verify` (única exceção à regra "o
  verify não recebe secrets", e ela está justificada no próprio arquivo: **PROD
  sai de uma tag, que não dispara o CI por `push`**, então sem o repasse o
  source map da release de produção nunca seria enviado).

---

## C2.5 — Gate de validação de infra na CI

Novo job `infra-validate` no `ci.yml`, com o mesmo `checkout_ref` dos outros
jobs, executando `scripts/observability/validar-infra.sh --estrito`.

Instala `pyyaml` via `actions/setup-python@v5` (o `ubuntu-latest` já tem
Docker, `jq` e `shellcheck`). Sem PyYAML o validador acusa **falha**, e isso é
o comportamento correto: item que não pôde ser validado não é item validado.
Upload de artefato em `if: failure()` para diagnóstico.

### A decisão consciente sobre o `--estrito`

Sem tratamento, `--estrito` reprova para sempre por um `runbook_url` com domínio
reservado `.invalid` (RFC 2606) — pendência real que só se resolve com o
endereço interno de runbook, que é decisão humana com dependência externa. Um
gate vermelho permanente acaba sendo ignorado, e gate ignorado é pior que a
pendência: ele deixa de proteger contra as pendências *novas*.

**Escolhi tornar a pendência explícita em vez de puni-la.** O validador ganhou um
terceiro estado, `PENDENTE DECLARADA`, e a lista vive em
`scripts/observability/pendencias-ci.txt`:

- pendência **declarada** → `[PENDENTE]`, listada no resumo, **não reprova**;
- pendência **não declarada** → reprova o gate estrito na hora;
- chave declarada que **não ocorre mais** → **falha** (lista envelhecida
  passaria a esconder pendência nova).

O `--estrito` continua sendo o padrão no CI, e continua reprovando defeito de
configuração. O que mudou não é o peso do gate, é a distinção entre
"defeito" e "aguardando dependência externa declarada".

Corrigi de passagem um bug de apresentação do resumo do C1: a lista "Itens que
falharam" imprimia também AVISOs e PENDENTES (o `RESUMO` era único), o que
permitia ler "falhou: shellcheck não instalado" e concluir que o gate reprovou
por causa disso. Agora há listas separadas para FALHAS, PENDÊNCIAS e a contagem
de avisos/pulados, e o rótulo de resumo distingue `PENDENTE DECLARADA` de
`AVISO`.

---

## C2.6 — SSH com chave e `known_hosts` pinado

`VPS_SSH_KEY` e `VPS_HOST_FINGERPRINT`, **ambos opcionais**, adicionados aos
6 workflows e passados aos dois steps SSH do `deploy.yml`.

Vazios, a action simplesmente ignora as entradas e o comportamento é
**exatamente** o de antes (autenticação por senha, sem host key pinning). A
senha continua no lugar.

Duas coisas que precisei verificar no código da action antes de prometer
qualquer coisa (não confiei na documentação):

1. **A ordem das credenciais é do cliente SSH da action, não deste workflow.**
   Com as duas presentes, a senha é oferecida primeiro e a chave em seguida;
   qualquer uma das duas autentica. A chave **não** tem precedência enquanto
   `VPS_PASSWORD` existir, e isso não é corrigível aqui sem remover a senha — que
   é exatamente o passo adiado. Documentado, para ninguém descobrir em
   incidente.
2. **A impressão digital tem que ser do host key ED25519.** A action compara com
   a primeira host key que o servidor oferece, e o ED25519 é o primeiro da lista
   padrão. Passar a impressão de outro tipo faz a conexão **falhar** — que é o
   comportamento fail-closed correto, mas confuso se não for esperado.
   O procedimento (`ssh-keygen -lf /etc/ssh/ssh_host_ed25519_key.pub`) está em
   `infra/DEPLOY.md` §9.5.

**A remoção da senha não está nesta mudança.** Depende de acesso real à VPS e de
um run verde autenticando **só** com a chave. A sequência completa está em
`infra/DEPLOY.md` §9.5, com o teste fora do Actions antes de cadastrar qualquer
secret.

---

## C2.7 — Secrets

Inventário com "o que fazer quando falta" em `CI-CD.md` §P1-6, incluindo os
casos "sem efeito" (`VPS_SSH_KEY` e `VPS_HOST_FINGERPRINT` ausentes = caminho
por senha) e os casos "pulado com aviso" (os do Sentry). A seção também separa
o que **não** é secret de repositório: `DJANGO_SECRET_KEY`/`DJANGO_DB_PASSWORD`/
`BACKUP_S3_*` ficam em `backend/.env` na VPS; os tokens do Alloy em
`/etc/portal/alloy-<env>.env` em 0640; e `OBSERVABILITY_METRICS_TOKEN` precisa
ser o **mesmo valor** em três lugares.

---

## C2.8 — Documentação

Acréscimo seccionado. **Nada do que existia foi reescrito**, em especial:

- `CI-CD.md` §P1-5 (`:262-327`): intacta. A nova §P1-6 vem **depois** dela e a
  referenciá-la explicitamente. O bloco "Secrets exigidos" ganhou uma frase
  sobre o `verify`, e a tabela de ambientes ganhou a coluna systemd.
- `infra/DEPLOY.md` §3A (runbook TLS, `:330-607`): **intacto**. A nova §9 foi
  anexada ao final do arquivo, com aviso de que a §3A continua sendo o caminho
  do certificado.
- `PROD_DECISOES.md`: decisões 8-16, no formato do arquivo, e uma entrada no
  registro de conclusões.
- `README.md`: a seção "Observabilidade" foi corrigida — `@sentry/nextjs` **já
  está** em `frontend/package.json` (o Bloco B2 adicionou, versão fixada em
  `10.75.3`), então a afirmação "é opcional, não dependência obrigatória" e o
  `npm i @sentry/nextjs` estavam errados.
- `ARCHITECTURE.md`: **corrigida a afirmação incorreta do diagrama** (9.2), que
  desenhava "Celery worker + beat" como bloco gerenciado pelo PM2. O achado B4
  confirmou que nunca existiram em supervisor nenhum. O diagrama agora separa
  PM2 (web/API) de systemd (Celery, Alloy), e o texto de 9.3 (Confiabilidade)
  foi atualizado para o que a topologia realmente faz.

---

## Validação: o que foi EXECUTADO e o que NÃO

Ambiente local: sem acesso à VPS, sem GitHub Actions. Ferramentas usadas:
`python3` + PyYAML 6.0.3, `actionlint` 1.7.7 (baixado para `/tmp`), `bash`,
`node` v24, `docker` (o `validar-infra.sh` usa).

### Executado, com saída real

| # | O que | Comando | Resultado |
|---|---|---|---|
| V1 | YAML dos 6 workflows | `python3 -c "import yaml; yaml.safe_load(...)"` em cada um | 6/6 `YAML OK` |
| V2 | Semântica dos workflows | `actionlint 1.7.7 .github/workflows/*.yml` | **exit 0, nenhum achado** (com shellcheck integrado) |
| V3 | Shell embutido dos 2 scripts do `deploy.yml` | extração + `bash -n` | 2/2 `bash -n OK` |
| V4 | Shell do passo de source maps | extração + `bash -n` | `OK` |
| V5 | `bash -n` do validador | `bash -n scripts/observability/validar-infra.sh` | `OK` |
| V6 | Validador estrito (completo) | `scripts/observability/validar-infra.sh --estrito` | `52 OK, 0 AVISO, 1 PENDENTE DECLARADA, 1 PULADO, 0 FALHOU` — **exit 0** |
| V7 | Estrito reprova pendência **não** declarada | pendencias-ci.txt removido + `--estrito --somente alertas` | **exit 1**, `[FALHOU] runbook_url ainda com o placeholder…` |
| V8 | Estrito reprova chave declarada obsoleta | chave fictícia adicionada + `--estrito --rapido` | **exit 1**, `[FALHOU] pendência declarada e não mais existente: chave-que-nao-existe` |
| V9 | Ajuda do validador não quebra com edição do cabeçalho | `--help` | imprime o bloco de comentário completo (agora recortado por regex, não por número de linha) |
| V10 | 9 cenários de release (T1-T9) | funções extraídas de `deploy.yml` + `run-standalone.sh` real + servidor Node | **TODOS OS TESTES PASSARAM** |
| V11 | 5 cenários de Celery systemd (T1-T5) | função extraída + `sudo`/`systemctl`/`install` falsos | **TODOS OS TESTES PASSARAM** |

**V10 — detalhe dos 9 cenários** (árvore falsa em `mktemp`, nada real tocado):

```text
T1 ok: preparar + smoke da release A (static/public copiados, .deployed-sha gravado)
T1 ok: smoke verde (Home 200, /robots.txt 200, asset 200)
T2 ok: nenhum symlink criado antes do smoke (current não existia)
T3 ok: current -> A, sem previous (primeira release)
T4 ok: current -> B, previous -> A
T5 ok: current -> A (voltar_release_anterior)
T6 ok: smoke REPROVOU release com 500 e asset 404
T6 ok: current continua em A — nada foi promovido apesar do smoke reprovado
T7 ok: 6 -> 4 releases podadas, current e previous intactos
T8 ok: Home em 503 ACEITO (estado documentado de feed indisponível)
T9 ok: build sem .next/standalone/server.js reprovado
```

**V11 — detalhe dos 5 cenários:**

```text
T1 ok: 4 units instaladas, User/Group resolvidos para o dono do app
T1 ok: StateDirectory=portal-observabilidade presente na unit do heartbeat
T2 ok: /etc/portal/celery-prod.env gerado com %i resolvido no nome do heartbeat
T3 ok: segundo deploy PRESERVA o tuning ajustado à mão
T4 ok: celery_systemd=false não executa nada
T5 ok: sem sudo -> avisa, não falha, retorna 0
```

### NÃO executado — pendências, não "validado"

1. **Nenhum deploy real.** Nem DEV, nem HOMOLOG, nem PROD. O primeiro deploy com
   `web_runtime: standalone` na VPS é o teste que importa, e ele exige acesso.
2. **`actionlint` não substitui execução no Actions.** Ele valida o esquema dos
   workflows e o shell embutido, mas não executa steps, não resolve
   `secrets` e não verifica que a action aceita a combinação de inputs. Em
   especial, a combinação `key` + `password` + `fingerprint` foi verificada
   **lendo o código da action**, não rodando-a.
3. **O passo de source maps nunca rodou** (precisa de token e de `.next/` com
   mapas). Só o `bash -n` e a leitura de sintaxe do `sentry-cli`.
4. **Celery nunca subiu.** As units não foram `systemd-analyze verify`-adas
   *depois* do `sed` de `User=`/`Group=` (a verificação do C1 rodou sobre o
   template do repositório, não sobre a cópia instalada com o usuário real) e
   nenhum processo Celery foi executado.
5. **`nginx -t`, `docker compose config` e `alloy validate` dentro do gate de
   CI** rodaram **localmente** (V6), não no runner do GitHub. O runner tem as
   ferramentas, mas a versão pode diferir.
6. **A imagem do Alloy e do Nginx foi baixada do Docker Hub** nesta máquina
   (usada pelo V6). O runner vai baixar de novo.

---

## Fronteiras de ownership: o que NÃO foi tocado

Registrado como pede a instrução, **sem mudança de status**:

- **R-1 — caminho PR → VPS.** `scripts/release/verificar-proveniencia.sh`
  continua **fora** de qualquer workflow. O risco é aceito, aberto, **não
  mitigado** e **não coberto pelo gate** por decisão da run de go-live, com
  assinatura exigida no go/no-go. Fronteira registrada em `CI-CD.md` §P1-6
  (pendências) e `PROD_DECISOES.md` decisão 16.
- **R-2 — divergência de domínio `.com` × `.com.br`.** Não corrigida. Registrada
  em `CI-CD.md` §P1-6 com uma **consequência nova** que vale Known: com
  `tls_enabled=true` o `validate` faz o probe em `https://$HOST/…`, e um hostname
  que não resolve reprova o probe. O valor efetivo de `HOST` nos três ambientes
  precisa ser confirmado antes de ativar TLS.
- **`DJANGO_ALLOWED_HOSTS` com IP fixo** (`108.174.147.50` no `printf` do
  bootstrap de `backend/.env`): **não tocado**, registrado como pendência em
  `CI-CD.md` §P1-6. Fixar um IP em arquivo de configuração gerado é
  problemático, mas corrigi-lo mudaria o comportamento de hosts aceitos sem
  combinado — decisão de quem opera a VPS.

---

## Pendências que continuam abertas

**Viram pendência nesta iteração (não resolvidas aqui):**

1. **Primeiro deploy `standalone` numa VPS real.** Precisa de janela em DEV.
   O checklist: deploy verde → conferir `readlink -f releases/current` → dois
   probes 200 → `curl` na Home e num asset de `/_next/static/` **pelo Nginx**
   (o smoke já prova direto na porta, mas a diferença importa) → `pm2 logs
   portal-web-dev --lines 50` para confirmar que é o standalone.
2. **Teste de falha controlada.** O caminho de retorno automático (T5/V10) foi
   provado com função isolada, mas o cenário real — release nova que não sobe no
   PM2, `current` voltando, marker preservado — **nunca aconteceu em produção**.
   É o teste que dá confiança ao resto.
3. **Ordem do promote e a janela de downtime.** O symlink troca antes do restart,
   então existe uma janela (segundos) em que `current` aponta para a release nova
   e o processo ainda é o antigo. Nesse intervalo o processo antigo continua
   servindo de um diretório que **continua existindo** (as releases antigas são
   podadas só no fim, e a poda protege `current`/`previous`). Não há requests
   quebrados, mas o `pm2 jlist` mostra um processo com `pm_cwd` de um diretório
   que já não é `current`. Documentado; se incomodar, dá para trocar `current` e
   reiniciar em ordem inversa aceitando a troca pré-verificada.
4. **`StateDirectory` × `celery-beat@`.** O deploy faz `install -d` do
   diretório do heartbeat, e o systemd também o criaria pelo `StateDirectory` da
   unit do heartbeat. Se o `install -d` do deploy criar com dono diferente do
   `User=` da unit, há um `chown` implícito em conflito. Não reproduzível sem a
   VPS; provável próximo passo é o deploy **não** criar o diretório e deixar o
   `StateDirectory` ser a única fonte.
5. **A nota no fim de `run-standalone.sh`** ("POR QUE O PM2 AINDA NÃO USA ISTO")
   descreve uma situação que esta run resolveu. Não a editei (é artefato do C1 e
   a reescrita correcta exige o contexto do Bloco B) — **atualizar**.
6. **`/healthz` legado** continua sendo o alvo do healthcheck do Docker e do
   smoke de deploy; a migração para `/livez`+`/readyz` é do bloco de infra/backend.

**Continuam com a run `20260925-1433-go-live-producao` (não tocadas aqui):**

- **R-1** (proveniência PR → VPS): aceito, aberto, não mitigado, assinatura
  exigida no go/no-go.
- **R-2** (domínio `.com` × `.com.br`): registrada, não corrigida.
- A run de go-live também é dona do **go/no-go**; o gate desta §P1-6 (release
  atômica com retorno, validação de infra no CI) é evidência **adicional**, não
  substitui o que R-1 exige nem a assinatura.

**Depende de ação humana, sem segredo por canal:**

- Contas e MFA: Sentry, Grafana Cloud (US), Better Stack, Cloudflare R2;
- Contact Points (`CP_CRITICO_PRINCIPAL`, `CP_CRITICO_SUPLENTE`, `CP_WARNING`) e
  canais (e-mail do principal e do suplente, Telegram/Slack);
- URLs reais de dev/homolog/prod e a decisão do domínio canônico (R-2);
- **endereço interno de runbook** (a pendência `runbook-url-placeholder` que
  motivou o terceiro estado do validador);
- provisionamento de SSH por chave na VPS (`infra/DEPLOY.md` §9.5) e, **depois**
  de um run verde, a remoção de `VPS_PASSWORD`;
- janela de produção para o teste de restore do backup e para a validação em
  homologação/produção da malha de observabilidade.

---

## Decisões que valem revisão do orchestrator

1. **Release do tier web, não do app inteiro** (§ C2.1). É o desvio mais
   substancial em relação à leitura literal do plano; a justificativa está em
   `CI-CD.md` §P1-6, mas a decisão em si precisa de aval.
2. **`web_runtime: npm` mantido como escape hatch.** Removê-lo é a última etapa
   da mudança, não uma parte dela.
3. **Retorno automático só no caminho "o processo não subiu"**, e sempre com
   `exit 1`. O caminho "comportamento ruim" ficou manual por decisão, e essa
   decisão também precisa de aval.
4. **Falha no upload de source map não reprova o build.** Discutível: a
   alternativa (falhar) garante que o mapa existe, ao custo de bloquear deploy
   por indisponibilidade de terceiro.
5. **Terceiro estado no validador (`PENDENTE_DECLARADA`)** em vez de usar o modo
   normal no CI. O gate continua estrito; o que mudou é a distinção entre
   defeito de configuração e dependência externa declarada.
6. **A senha do SSH continua.** Correto pela instrução e pelo risco, mas é
   dívida: enquanto ela existir, a chave não tem precedência.
7. **Correção mínima em `celery-beat-heartbeat@.service`** (`StateDirectory`)
   — inevitável para que o C2.3 funcione; declarado em vez de silencioso.
8. **Exceção do `verify` que recebe secrets** (só os do Sentry). Justificada no
   arquivo: PROD sai de tag e o CI por `push` não a cobre.
