# Implementation History — 20260924-1200-ops-higiene

<!-- Uma seção "## Iteração N" por evento relevante, em ordem cronológica. -->

## Iteração 1 — 2026-09-24 12:45 -03:00 — executor (implementação inicial)

**O que foi feito:**

1. **P0-2 — backup nativo PM2**
   - Criado `infra/backup/pg_backup_pm2.sh` com `set -euo pipefail`, `umask 077`, `flock`, arquivos temporários + rename atômico, `pg_dump -Fc`, validação por `pg_restore --list`, `tar` de `backend/media`, validação por `tar -tzf`, AWS CLI/S3 opcional e retenção de 7 dias limitada a `pm2-*`.
   - O env padrão é o arquivo real do deploy, `backend/.env`; há fallback para `.env` da raiz e `BACKUP_ENV_FILE`. Variáveis `PG*` explícitas do processo têm precedência sobre aliases `DJANGO_DB_*` do arquivo.
   - Sem `BACKUP_S3_BUCKET`, o script conclui as operações locais, mas imprime dois avisos explícitos de que a cópia ficará somente na VPS. Com bucket, ausência da AWS CLI ou falha de upload retorna exit não zero e preserva os arquivos locais já validados.
   - `infra/backup/pg_backup.sh` não foi alterado. `.gitignore` passou a ignorar o lock do novo script.
   - `infra/DEPLOY.md` ganhou um runbook PM2 prioritário com paths reais, pré-requisitos, S3/R2/B2, execução manual, comando de crontab idempotente, distinção Docker × PM2 e validação de artefato para restore. A seção de cron Docker deixou de sugerir `pg_backup.sh` para a VPS ativa.

2. **P1-5 — decisão conservadora de CI/CD**
   - Adicionado `concurrency.group = portal-deploy-<environment_name>` com `cancel-in-progress: false` no workflow reutilizável.
   - Removidos job `guard`, input `guard_ref` e suas duas chamadas. `ci.yml` permanece o gate de check/pytest/tsc/build.
   - O build continua na VPS, agora com cache persistente `$HOME/.npm`, `npm ci --prefer-offline` e `NODE_OPTIONS=--max-old-space-size=1536` limitado ao comando de build.
   - `CI-CD.md` documenta os riscos de `NEXT_PUBLIC_*` no build, a troca de `npm start` por `node server.js`, a necessidade de diretório versionado/symlink/rollback e o plano de validação do artefato standalone.
   - Corrigido também um SC2086 preexistente em `deploy-prod.yml` (`"$GITHUB_OUTPUT"`), encontrado pelo actionlint e necessário para validar o workflow inteiro.

3. **P2-6 — Postgres e logs**
   - Criado `infra/postgres-tuning.conf` com `shared_buffers=1GB`, `effective_cache_size=3GB`, `work_mem=8MB` e `maintenance_work_mem=256MB`; o repositório não o aplica.
   - Criado `infra/logrotate/pg-backup.conf` com 14 rotações, 20 MB máximos, compressão, `missingok`, `notifempty` e `copytruncate` para preservar owner/mode do log do operador.
   - `docker-compose.yml` passou a usar uma âncora `json-file` (`10m` × `3`) nos sete serviços, sem alterar a topologia PM2.

4. **P2-7 — higiene**
   - `backend/requirements-lock.txt` foi regenerado exatamente do `backend/.venv` (Python 3.14.4). O conjunto também foi instalado do zero em Python 3.12, a versão do CI, e passou em `pip check` + `manage.py check`.
   - `backend/requirements.txt` e o cabeçalho do lock documentam o comando de regeneração e reconhecem que pytest/pytest-cov/pytest-django ainda estão no conjunto/runtime.
   - Adicionadas as quatro variáveis `BACKUP_S3_*` ao `backend/.env.example`, que é o env da topologia PM2.
   - Alterado somente o comentário de `backend/config/settings.py`: o cache do feed existe e expira por TTL de 45 s; `plano.preco_alterado` não o invalida.

5. **Artefatos da run**
   - `task-plan.md` e `implementation-contract.md` preenchidos e conferidos contra `contract-checklist.md`: sem placeholders, escopo interno/externo explícito, critérios verificáveis, riscos, papéis e follow-ups rastreáveis.
   - `run-state.json` inicializado e validado contra `run-state.schema.json`; planner concluído e implementação encerrada, aguardando tester/reviewer.

**Por quê:**

O backup existente depende de Docker Compose e não atende à topologia ativa
PM2 + Nginx. P1-5 foi deliberadamente mantido conservador porque migrar o
frontend para artefato sem um deploy real poderia embutir `NEXT_PUBLIC_*`
errados, misturar uma versão parcial ou remover o cwd esperado pelo PM2. P2-6 e P2-7
foram tratados como configuração/runbook, sem aplicar mudanças privilegiadas
nem tocar lógica da aplicação.

**Arquivos tocados:**

- `infra/backup/pg_backup_pm2.sh` (novo)
- `infra/postgres-tuning.conf` (novo)
- `infra/logrotate/pg-backup.conf` (novo)
- `infra/DEPLOY.md`
- `.github/workflows/deploy.yml`
- `.github/workflows/deploy-dev.yml`
- `.github/workflows/deploy-prod.yml`
- `CI-CD.md`
- `docker-compose.yml`
- `.gitignore`
- `backend/.env.example`
- `backend/requirements.txt`
- `backend/requirements-lock.txt`
- `backend/config/settings.py` (somente comentário)
- `agentic-framework/state/run-20260924-1200-ops-higiene/{task-plan.md,implementation-contract.md,implementation-history.md,run-state.json}`

**Comandos executados / evidência:**

```text
bash -n infra/backup/pg_backup_pm2.sh
  -> exit 0

Teste com binários pg_dump/pg_restore/aws simulados:
  -> 2 execuções sucessivas, 4 uploads, retenção apenas de pm2-*, dumps 600,
     nenhum segredo no log, modo local-only com aviso, dump inválido sem final,
     lock ocupado retornando exit 3: ok

Docker postgres:16-alpine real:
  -> pg_dump -Fc -> pg_restore --list -> tar czf -> tar -tzf,
     banco vazio e mídia de teste, ambos arquivos modo 600: ok

docker compose --env-file .env.production.example -f docker-compose.yml config --quiet
  -> exit 0

Docker rhysd/actionlint:latest:
  -> exit 0 após a correção de "$GITHUB_OUTPUT"

Parser YAML 1.2 (chaves únicas) nos 3 workflows + docker-compose.yml:
  -> 4 arquivos ok

logrotate -d em container root:
  -> leu 1 pattern; rotação diária, 14 retenções, maxsize 20M: ok

postgres:16-alpine, include de infra/postgres-tuning.conf:
  ->shared_buffers=131072 blocos de 8 kB (1 GB)
  ->effective_cache_size=393216 blocos de 8 kB (3 GB)
  ->work_mem=8192 kB (8 MB)
  ->maintenance_work_mem=262144 kB (256 MB)

backend/.venv/bin/python -m pip freeze comparado ao lock:
  -> diff vazio

Python 3.12 slim, instalação limpa do requirements-lock:
  -> pip check: No broken requirements found
  -> manage.py check: no issues

Ambiente local:
  -> pip check: No broken requirements found
  -> manage.py check: no issues
  -> pytest -q feed/tests/test_sanity.py: 12 passed, 11 warnings
     (warnings esperados de staticfiles ainda inexistente)

Ajv Draft 2020 + ajv-formats:
  -> run-state.schema.json validado sem erros

git diff --check:
  -> exit 0
```

**Resultado:**

Sucesso do ponto de vista do executor. Todos os critérios implementáveis sem
acesso à VPS foram cobertos; os comandos de shell, os dois formatos de configuração,
os workflows, o lock e o settings check passaram. Não houve commit. A aprovação
formal e a revisão de credenciais/CI-CD pertencem ao tester e ao reviewer.

**Decisões e notas fora do escopo:**

- **Build standalone deferido:** publicar `.next/standalone`, `.next/static` e
  `public` fica para uma run com deploy real em HOMOLOG, validação do bundle,
  smoke, troca atômica e rollback. O plano está em `CI-CD.md`.
- **Requirements dev/runtime deferido:** retirar `pytest*` da imagem e criar
  requirements de desenvolvimento exigiria alterar Dockerfile, CI e PM2 de forma coordenada.
- **`ingestao-service/` deferido:** a decisão arquivar/ativar é arquitetural e
  nenhum arquivo desse diretório foi tocado.
- **Ações humanas na VPS:** instalar/configurar cron, criar log, configurar
  bucket/lifecycle, executar backup + restore descartável, aplicar tuning com
  `SHOW` antes/depois e medir RAM. Nenhuma configuração privilegiada foi aplicada.
- **Gate CI × deploy:** remover o guard torna obrigatório um gate explícito
  (`workflow_run` ou equivalente) ou uma política que impeça push/tag fora do
  CI verde. Workflows separados não se aguardam sozinhos e branch protection não
  bloqueia o evento `push` de DEV; o risco está documentado em `CI-CD.md` como
  follow-up, pois reintroduzir um job de CI completo no deploy seria justamente
  a duplicação que P1-5 pediu para remover.
- **Workspace compartilhado:** alterações preexistentes de outras runs em
  `deploy.yml`, `CI-CD.md`, `infra/DEPLOY.md`, `settings.py` e
  `backend/.env.example` foram preservadas por edições cirúrgicas. Nenhum arquivo
  de `run-20260923-2238-pendencias-pre-deploy` foi modificado.

---

## Remediação (iteração 1) — 2026-09-24 — remediator

**Finding tratado:** o blocker único da fase `testing` (CI não era aguardado
pelos três deploys; tags `v*` não eram cobertas pelo trigger de branches do
`ci.yml`). O `guard` removido não foi reintroduzido.

### Escolha e justificativa

Escolhi a opção **(b), `workflow_call` reutilizável**, por ser a mais simples e
robusta para os triggers existentes:

- `ci.yml` permanece um workflow normal de `push`/`pull_request` para feedback
  rápido e passa a aceitar `workflow_call` sem copiar jobs ou lógica.
- `deploy.yml` chama esse workflow no job `verify`; `deploy` declara
  `needs: verify`. O gate e o provisionamento ficam no mesmo run, sem a corrida
  de dois workflows independentes e sem depender do contexto privilegiado de
  `workflow_run`.
- `workflow_run` foi rejeitado para esta topologia porque precisaria reconstruir
  ambiente/ref a partir de `workflow_run.head_*`, tratar a tag de release e
  copiar as permissões do workflow chamador. Branch protection/ruleset é
  configuração externa: pode impedir push/tag direto, mas não implementa o gate
  no repositório e não protege o evento `push` sozinho.

### Alterações por workflow

- **`.github/workflows/ci.yml`:** adicionados `on.workflow_call.inputs.checkout_ref`
  e o mesmo `ci.yml` como fonte única de `manage.py check`, pytest/cobertura,
  `tsc` e `next build`. Os triggers diretos `push`/`pull_request` em
  `develop`/`main` foram preservados; cada checkout usa o SHA/ref fornecido
  pelo caller ou, no trigger direto, o SHA do evento.
- **`.github/workflows/deploy.yml`:** adicionado `verify_ref` e o job
  `verify` com `uses: ./.github/workflows/ci.yml`; `deploy` agora tem
  `needs: verify`. O SSH/PM2 continua idêntico, mas o script fixa no checkout
  o mesmo commit verificado, inclusive quando uma branch avança ou uma tag é
  movida enquanto o run está na fila. O job `guard` e o input `guard_ref` não existem.
- **`.github/workflows/deploy-dev.yml`:** mantém `push` em `develop` e passa
  `github.sha` como `verify_ref`.
- **`.github/workflows/deploy-homolog.yml`:** mantém PR para `main` e passa
  `github.event.pull_request.head.sha`, que é o head buscado pela VPS.
- **`.github/workflows/deploy-prod.yml`:** mantém tag `v*` e passa
  `github.sha`; portanto a tag é verificada pelo workflow chamado, mesmo sem
  adicionar `tags` ao trigger de push do CI. O job `pre` continua apenas
  preparando versão/release; o job que altera a VPS é o reusable deploy gated.
- **`CI-CD.md`:** diagrama, tabela de workflows, decisão do gate, comparação
  das opções e configuração externa remanescente foram atualizados.

### Fluxo e dry-run conceitual

```text
push develop ──┬─ CI standalone (feedback)
               └─ Deploy DEV
                  └─ verify = workflow_call(ci.yml, SHA do push)
                     └─ needs: verify → SSH/PM2 DEV

PR → main ─────┬─ CI standalone (feedback)
               └─ Deploy HOMOLOG
                  └─ verify = workflow_call(ci.yml, head SHA do PR)
                     └─ needs: verify → SSH/PM2 HOMOLOG

tag v* ─────────── Deploy PROD
                     └─ verify = workflow_call(ci.yml, SHA da tag)
                        └─ needs: verify → SSH/PM2 PROD
```

- Se qualquer job interno de `ci.yml` falhar, for cancelado ou não concluir,
  o reusable workflow `verify` não fica `success`; por `needs`, `deploy` e
  `validate` ficam `skipped` e nenhuma conexão SSH é aberta.
- Se `verify` ficar verde, o job de deploy provisiona o ambiente e só então o
  job `validate` faz o smoke check existente. A `concurrency` por ambiente
  continua serializando o run inteiro.
- Push/PR gera uma execução standalone de CI para feedback e outra execução
  da mesma definição dentro do run de deploy. Isso duplica o *tempo de runner*,
  mas não a implementação de teste; foi o trade-off explícito da opção (b).
- No fluxo PROD, `pre` pode criar a release antes da verificação, mas não toca
  a VPS; o requisito de bloquear o provisionamento PROD é satisfeito pelo
  `needs: verify` dentro de `deploy.yml`. Uma política que exija criar a
  release somente depois do verify é uma decisão operacional adicional.

### Validações executadas

```text
docker run --rm -v "$PWD:/repo" -w /repo rhysd/actionlint:latest \\
  -color=false .github/workflows/*.yml
  -> exit 0; actionlint 1.7.12 nos 5 workflows

Parser YAML Python + verificações de grafo:
  -> 5 workflows parseados; workflow_call, needs: verify, triggers
     develop/main, PR main e tag v*; mappings de verify_ref conferidos

Bloco `script` do deploy com expressões substituídas por valores de teste:
  -> bash -n: exit 0

grep dos 5 workflows:
  -> nenhum job guard, needs: guard ou guard_ref

git diff --check -- .github/workflows CI-CD.md
  -> exit 0
```

Não houve alteração de código de aplicação, backend, `infra/backup`,
`docker-compose.yml` ou secrets; não houve commit. A validação foi estática
e conceitual — não houve acesso à VPS nem disparo real de um workflow do
GitHub. A configuração de branch protection/rulesets,
proteção de tags, required status checks e approvals dos GitHub Environments
continua dependendo de configuração humana externa; ela complementa, mas não
substitui, o gate versionado.

---

## Remediação (iteração 2) — 2026-09-24 — remediator

**Escopo:** os seis findings da revisão (`1 blocker`, `4 majors`, `1 minor`)
foram tratados. O blocker de gate que já havia sido resolvido na iteração 1
continua resolvido; não houve commit e não foram tocados os arquivos de
documentação/aplicação bloqueados para esta sub-run.

### Finding 1 — blocker — integridade do dump

- `pg_restore --list` foi mantido apenas como checagem de TOC. O script agora
  captura `SOURCE_COUNTS` (tabelas e linhas de usuário), cria
  `backup_validate_<timestamp>_<pid>` com `createdb -T template0`, executa
  `pg_restore --exit-on-error --no-owner --no-privileges` nesse banco e compara
  a contagem restaurada com a origem. Só depois o temporário é renomeado para
  `pm2-db-*.dump`; o banco descartável é removido em sucesso e no `trap` de
  falha.
- `BACKUP_VALIDATE_RESTORE=1` é o padrão. `0/false` é um escape explícito:
  ainda executa a leitura integral com `pg_restore --exit-on-error
  --file=/dev/null`, mas imprime aviso de que o restore/contagem foram
  desligados. Sem `CREATEDB`, falha no `createdb` (exit 8), não publica o
  dump, não envia ao S3 e não apaga nada.
- **Custo:** a validação restaurará o dump inteiro e fará `COUNT(*)` em todas
  as tabelas de usuário; o tempo é proporcional ao tamanho do banco e usa
  CPU/I/O e espaço temporário no mesmo cluster. Deve ser agendada com folga de
  disco e monitorada; o modo de escape deve ser raro e auditado.

### Finding 2 — major — retenção e configuração S3

- As variáveis `BACKUP_S3_ENDPOINT`, `BACKUP_S3_BUCKET`,
  `BACKUP_S3_ACCESS_KEY` e `BACKUP_S3_SECRET_KEY` exportadas pelo processo
  agora têm precedência sobre linhas vazias do env file. Credenciais sem
  bucket, endpoint/chave sem bucket, par access/secret incompleto e bucket sem
  credencial efetiva (a AWS CLI/`sts` não valida a cadeia IAM) falham fechado.
- Após `aws s3 cp` para dump e mídia, o script executa
  `s3api head-object` e compara `ContentLength` com `stat` do arquivo local.
  A retenção de sete dias só é liberada depois dos dois uploads e das duas
  verificações. Sem bucket, o script continua local-only, mas **não executa
  `find ... -delete`** e mantém todos os arquivos.

### Finding 3 — major — lockfile no deploy

- `.github/workflows/deploy.yml` passou a instalar
  `backend/requirements-lock.txt`, o mesmo conjunto usado pelo job
  `backend-tests` do CI. O comentário no workflow registra a consequência: o
  lock é mais rígido; qualquer atualização de dependência exige regenerar o
  lock e passar pelo CI antes do próximo deploy.

### Finding 4 — major — interrupção do deploy

- O caminho normal não usa mais `pm2 delete`: `restart_or_start` executa
  `pm2 restart --update-env` quando o nome já existe e `pm2 start` apenas na
  primeira criação. Não há janela explícita de delete; se o comando falhar, o
  shell aborta sem apagar o processo antigo.
- A criação inicial de `backend/.env` foi trocada por arquivo temporário
  privado + `chmod 600` + `mv` atômico, depois do `git reset --hard` que fixa
  `VERIFY_REF`; o script ainda compara `git rev-parse HEAD` com o SHA do gate.
  O `.env` existente continua sem sobrescrita e com a checagem de flags TLS.
- `validate` passou a ter `needs: [verify, deploy]` e `if: always()`, portanto
  o health check/API-web é tentado mesmo após falha parcial do job SSH. Não foi
  introduzido rollback/blue-green; o objetivo foi remover a janela delete/start
  e tornar a falha observável, conforme o finding.

### Finding 5 — major — release PROD antes do gate

- Em `deploy-prod.yml`, o input `tls_enabled` foi mantido intacto. O job `pre`
  agora calcula somente a versão; `gh release create --verify-tag` está em um job
  `release` com `needs: [pre, deploy-prod]`, que também confere que a tag ainda
  aponta para o SHA verificado. Logo, verify, SSH/deploy e validate precisam
  terminar com sucesso antes de qualquer release/tag ser publicada.

### Finding 6 — minor — contexto do cron

- Antes do lock, o script registra UID/usuário, owner e modo de
  `BACKUP_DIR` e `MEDIA_DIR`, e avisa (sem falhar por isso) quando owner,
  leitura ou escrita não combinam com o usuário efetivo. Também avisa se o
  env file não é legível. A operação real continua fail-closed quando a
  permissão necessária impede criar o lock, ler a mídia ou escrever o dump.

### Evidência da iteração 2

```text
bash -n infra/backup/pg_backup_pm2.sh
  -> exit 0

actionlint 1.7.12 (container rhysd/actionlint:latest) nos 5 workflows
  -> exit 0; tls_enabled preservado nos callers e no reusable workflow

PostgreSQL real postgres:16-alpine (container, bash/util-linux/coreutils
instalados no container de teste), restore do script:
  -> exit 0; log "restore validado ... (1|10000; tabelas|linhas)";
     novo pm2-db-*.dump + pm2-media-*.tar.gz publicados
  -> segundo restore manual em createdb -T template0:
     ALPINE_MANUAL_RERESTORE_ROWS=10000; drop posterior bem-sucedido

Archive real truncado em 99% (pg_dump real + truncate; a cópia usada no
  segundo comando foi feita depois do truncate), mesmo archive:
  -> pg_restore --list: exit 0
  -> pg_restore real no banco descartável: exit 9,
     "could not read from input file: end of file"
  -> script exit 9; nenhum pm2-db final e nenhum temporário .pm2-* publicado

Usuário sem CREATEDB (restore real):
  -> createdb: permission denied; script exit 8;
     nenhum artefato final publicado

Sem bucket (dump válido + sentinelas com 10 dias):
  -> script exit 0; aviso explícito de retenção suspensa;
     pm2-db/pm2-media antigos preservados

BACKUP_VALIDATE_RESTORE=0 (escape explícito):
  -> script exit 0; aviso de restore/contagem desligados presente;
     leitura integral do archive ainda passou

S3 simulado + env file com BACKUP_S3_* vazios e variáveis externas:
  -> uploads + head-object por tamanho: exit 0;
     retenção removeu apenas PM2 antigos e preservou sentinela db-* Docker

Falha de upload S3 (fake `s3 cp` exit 42):
  -> script exit 17; arquivo PM2 antigo e sentinel Docker preservados;
     nenhuma retenção executada

Configuração S3 órfã (access key sem bucket):
  -> exit 12 antes de gerar/publicar artefato

Bucket sem credenciais explícitas e sem cadeia IAM válida (AWS CLI simulado):
  -> exit 13 antes de gerar/publicar artefato

Cron postgres contra diretórios root-owned (postgres:16-alpine):
  -> avisos de owner UID 0 vs UID 70 e de escrita antes da falha real do lock;
     nenhum dump foi publicado

git diff --check
  -> exit 0

Smoke final após os últimos ajustes (PostgreSQL 16-alpine real):
  -> dump válido exit 0; re-restore manual=10000 linhas;
     archive truncado: --list exit 0, script exit 9;
     sem bucket exit 0 e dois artefatos antigos preservados
```

Não houve acesso a uma VPS, bucket S3 real ou disparo real do GitHub; os
testes S3 acima são simulados, enquanto o restore/truncamento são PostgreSQL
16 real. A documentação de runbook não foi editada nesta sub-run para evitar a
colisão de arquivos indicada; o custo, o novo default e o escape de
validação ficam registrados nesta evidência para a etapa de documentação.

---

## Remediação (iteração 3) — 2026-09-24 — remediator

**Finding tratado:** Finding 4 residual (interrupção entre os dois restarts e
recuperação). Esta é a última iteração; a mitigação foi deliberadamente
conservadora para PM2 em VPS única, sem introduzir blue-green ou rollback de
migrations.

### Implementação

1. **Retry e sanidade PM2 no reusable `deploy.yml`**
   - `restart_or_start` agora tenta o comando de `restart`/`start` até 3 vezes,
     com 3 s de espera entre tentativas. Um comando que falha não é considerado
     sucesso por causa de apenas o exit code zero.
   - Depois de cada comando, `pm2_state` consulta `pm2 jlist`; o processo precisa
     aparecer como `online` em duas confirmações antes do próximo processo ser
     tocado. `errored`, `stopped`, `missing` ou JSON inválido esgotam a tentativa
     e chegam à mensagem de recuperação com o SHA anterior.
   - A função imprime o alvo do dispatch manual (`target_sha=<anterior>`) e o
     caminho do marker quando as três tentativas falham. O job `validate` com
     `always()` e o gate `verify` foram preservados.

2. **Marker de produção e promoção somente após smoke**
   - Antes do `git reset`, o script lê/cria `/home/apps/portal-<env>/.deployed-sha`
     com o SHA anterior. O fallback para `HEAD` só ocorre se já existir processo
     PM2; uma instalação nova não recebe um SHA inventado.
   - O marker é escrito por temporário + `mv`, mas **não é promovido para o SHA
     novo no restart**. Só o SSH de `validate`, depois de API e web retornarem
     200 e o checkout coincidir com o SHA verificado, faz a promoção atômica.
     Falha/cancelamento do job SSH ou smoke parcial mantém o marker antigo.

3. **Rollback manual automatizável e seguro**
   - Criado `.github/workflows/rollback.yml` com `workflow_dispatch`, seleção de
     `development`/`homolog`/`production`, SHA hexadecimal de 40 caracteres,
     `tls_enabled` e `confirm` explícito.
   - O workflow reutiliza `deploy.yml` com `git_mode: rollback`; portanto o mesmo
     `verify`/`ci.yml` é executado, o SHA é resetado, build e lockfile são
     reinstalados, PM2 faz retry/sanidade e `validate` exige smoke verde. Não há
     release/tag nem um segundo script de provisionamento.
   - `CI-CD.md` documenta o dispatch e o comando shell de emergência, incluindo
     `git reset --hard`, `npm ci`/build, `pip install -r requirements-lock.txt`,
     migrations, `pm2 restart/start`, probes e a limitação de migrations.

4. **Disponibilidade declarada**
   - `CI-CD.md` afirma explicitamente que a arquitetura **não garante zero
     downtime**: o restart é in-place e uma queda de SSH pode deixar API/web
     parciais. Marker + retry + smoke + rollback manual são a mitigação, não uma
     promessa de alta disponibilidade.
   - O gatilho para revisar blue-green ficou registrado: “quando o deploy passar
     a causar indisponibilidade perceptível ou o tempo de manutenção for
     inaceitável”.

### Limitações aceitas

- Não foi implementado rollback automático por `trap`/blue-green. Um trap não
  é garantido quando a conexão SSH cai, e reverter migrations automaticamente
  seria mais perigoso do que uma reversão automática de schema. O operador pode disparar o workflow manual
  com o marker anterior; esse é o caminho de recuperação explícito e auditável.
- O rollback de aplicação não desfaz migrations nem substitui um backup do
  banco. O procedimento exige confirmar compatibilidade do schema antes de usar
  um SHA antigo.
- Não houve disparo real no GitHub nem SSH a uma VPS. A validação do workflow
  é estática; a lógica PM2 foi exercitada com mocks.

### Validações da iteração 3

```text
Parser YAML (PyYAML) nos 6 workflows
  -> exit 0; deploy.yml e rollback.yml incluídos

actionlint 1.7.12 (container rhysd/actionlint:latest) nos 6 workflows
  -> exit 0

bash -n em todos os blocos `script`/`run` extraídos dos 6 workflows
  -> exit 0

dash -n nos mesmos blocos (compatibilidade com o shell remoto)
  -> exit 0

Mock PM2: dois `restart` falham, o terceiro retorna e o jlist fica online
  -> 3 chamadas; a função retorna sucesso após 2 confirmações online

Mock PM2: estado permanece `errored`
  -> 3 chamadas, exit diferente de zero e mensagem com target_sha/marker

grep dos callers
  -> `verify` continua presente; `tls_enabled` preservado em DEV/HOMOLOG/PROD
     e também no workflow manual de rollback

Guarda do input `target_sha` do rollback
  -> aceita somente 40 hex; rejeita comprimento/caractere inválido antes do SSH

Bloco bash do procedimento de emergência em `CI-CD.md`
  -> bash -n e dash -n ok

grep de segurança/escopo
  -> nenhum `pm2 delete` reintroduzido; forbidden files não foram editados
     por esta remediação

git diff --check -- .github/workflows CI-CD.md
  -> exit 0
```

Não houve commit. `infra/DEPLOY.md`, `infra/certbot/` e
`infra/backup/pg_backup_pm2.sh` permaneceram preservados para não colidir com a
run TLS; a documentação desta recuperação foi limitada a `CI-CD.md` e ao
workflow.


