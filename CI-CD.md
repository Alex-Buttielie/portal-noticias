# Pipeline CI/CD — BRD Portal de Notícias

Preserva integralmente a infra do deploy anterior (ramo `backup/remote-*-20260904`):
PM2 + Nginx na VPS, `/home/apps/portal-{dev,homolog,prod}`, portas 310x/510x,
secrets `VPS_HOST/USER/PASSWORD/PORT`. **Muda só o software**: `frontend/` +
`backend/` (Django real) no lugar de `apps/*`, com as mesmas portas, processos,
domínios e segredos.

```
push develop ──┬─ CI (push/PR, feedback rápido)
               └─ Deploy DEV ── verify (mesmo ci.yml) ──> SSH/PM2 3101/5101
PR → main ─────┬─ CI (push/PR, feedback rápido)
               └─ Deploy HOMOLOG ── verify (head do PR) ──> SSH/PM2 3102/5102
tag v* ─────────── Deploy PROD ── verify (mesmo ci.yml) ──> SSH/PM2 3103/5103
                                      │
                                      └─ needs: verify: falha/cancelamento => deploy skipped
dispatch manual ── Rollback ──────── verify (mesmo ci.yml) ──> reset SHA + PM2 + smoke
```

O CI continua sendo um workflow independente para feedback nos pushes e PRs.
Ao mesmo tempo, cada deploy chama `ci.yml` por `workflow_call` dentro do
próprio run; a execução é duplicada de propósito, mas a lógica (pytest, check,
`tsc` e build) tem uma única definição e o deploy só provisiona depois do
resultado verde. Em PROD, a tag não precisa ser um trigger de `push` do CI:
o `verify` chamado pelo deploy cobre a tag e verifica seu SHA.

> Este documento descreve a configuração versionada e o contrato esperado da
> esteira. Uma execução no GitHub Actions ou na VPS só deve ser declarada
> concluída depois de observada no run correspondente e na própria VPS; validação
> local de YAML, shell ou containers não é evidência de um deploy remoto.

### Ambientes na VPS (inalterados)

| Ambiente | Ref git | Dir VPS | PM2 web/api | Portas |
|----------|---------|---------|-------------|--------|
| DEV | `develop` | `/home/apps/portal-dev` | `portal-web-dev` / `portal-api-dev` | 3101 / 5101 |
| HOMOLOG | head do PR (SHA fixo) | `/home/apps/portal-homolog` | `portal-web-homolog` / `portal-api-homolog` | 3102 / 5102 |
| PROD | `main` (tag `v*`, SHA fixo) | `/home/apps/portal-prod` | `portal-web-prod` / `portal-api-prod` | 3103 / 5103 |

Nginx (configuração canônica em `infra/nginx/portal-{dev,homolog,prod}.conf` — idênticas às ativas na VPS; aplicar conforme o cabeçalho dos arquivos):
`dev.portal-noticias.com.br` (`/`→3101, `/api/`→5101, preservando o path),
`homolog.portal-noticias.com.br` (→3102/5102),
`portal-noticias.com.br` (→3103/5103).

**Contas de teste por ambiente:** DEV e HOMOLOG recebem, a cada deploy, uma conta
por perfil — `teste-<papel>@<pm_suffix>.portal-noticias.com.br`, isto é
`teste-free@…`, `teste-premium@…` e `teste-admin@…` (só o `admin` vira
superuser). **PROD não recebe conta nenhuma.** É o input `usuarios_teste` do
`deploy.yml`: `false` por padrão, `true` em `deploy-dev.yml` e
`deploy-homolog.yml`, `false` explícito em `deploy-prod.yml` e ausente em
`rollback.yml`. O contrato do input e a lista de quem liga o gate estão na
seção *O gate `usuarios_teste` — contas de teste sem senha em DEV/HOMOLOG*,
mais abaixo neste documento; o passo a passo para entrar — inclusive onde o
e-mail de recuperação sai, que hoje **não** é uma caixa de entrada — está em
`infra/DEPLOY.md`, na seção *As contas de teste de DEV e HOMOLOG*.

> **Ativação P1-4:** os sites são seguros para `nginx -t` mesmo antes da
> instalação opcional dos snippets de cache/rate. A sequência versionada é
> `http-cache.conf` incluído no `http {}` global → snippets
> `portal-location-*.conf` → site → `sudo nginx -t` → reload do Nginx →
> restart da API correspondente no PM2. A proteção fail-closed de
> `media/credenciamento`, a lista de comandos e a verificação pós-restart
> estão em `infra/DEPLOY.md`. Não copie os snippets de location sem o include
> global; isso causaria `unknown zone`. O endpoint de ingestão
> 202+background deve ser ancestral do ref implantado antes de reduzir o
> timeout de 60s para 45s.

### O que mudou no software (única diferença)

- API: `apps/api` → `backend/` (venv em `backend/.venv`, `config.wsgi:application`,
  `manage.py migrate + collectstatic` a cada deploy, health em `/healthz`).
- Web: `apps/web` → `frontend/` (`npm ci + build` com `NEXT_PUBLIC_API_BASE_URL={http|https}://<host>` e `NEXT_PUBLIC_SITE_URL={http|https}://<host>` conforme `tls_enabled` — a ORIGEM do domínio, sem sufixo `/api`: o frontend já chama `{ORIGEM}/api/...` e o Django serve `/api/...`; sufixo duplicaria para `/api/api/...`. O Nginx preserva o path em `location /api/` — ver `infra/nginx/portal-{dev,homolog,prod}.conf`).
- `backend/.env` por ambiente é gerado no primeiro deploy (SECRET forte,
  `DJANGO_DEBUG=false`, `DJANGO_DB_ENGINE=postgresql`, domínios e credenciais do
  banco) e **preservado** nos deploys seguintes (`git reset` não apaga arquivos
  ignorados). PostgreSQL e Redis são serviços nativos da VPS.
- Validação: `localhost:51xx/healthz` (API) + `localhost:31xx/` (web).
  Um probe só é saudável quando o `curl` termina com rc `0` **e** o código HTTP
  é exatamente `200`; 3xx, 4xx, 5xx, conexão sem resposta (`000`) e resposta
  200 com transferência incompleta falham. `.deployed-sha` só é promovido quando
  API e web passam nos dois critérios e as demais barreiras (resultado do job e
  SHA verificado) também passam. Em DEV/HOMOLOG o alerta pode ser não
  bloqueante, mas o marker anterior é preservado quando qualquer probe falha.

### Fluxo Git Flow

1. **Feature**: `develop` → `feature/x` → commits → merge em `develop`
2. **Push em develop**: CI independente para feedback + deploy DEV; o
   `verify` do deploy executa o mesmo `ci.yml` e só libera o SSH se passar.
3. **PR develop → main**: CI independente + deploy HOMOLOG; o `verify`
   recebe `github.event.pull_request.head.sha`, o mesmo head que a VPS busca.
4. **Merge + tag**: `git tag vX.Y.Z && git push origin vX.Y.Z` → Release +
   deploy PROD; o `verify` Called Workflow valida o SHA da tag antes do
   provisionamento, mesmo sem um trigger de CI por tag.

### Rollback, recuperação e limite de disponibilidade

Esta arquitetura é **PM2 em uma VPS única, com restart no checkout atual**. Ela
**não garante zero downtime** em um deploy: pode existir uma breve indisponibilidade
durante o restart, e uma queda de SSH entre os dois restarts pode deixar API/web
parcial ou fora do PM2. O que existe é mitigação e recuperação, não uma troca
blue-green. O marker e o workflow manual abaixo são a mitigação operacional;
não devem ser descritos como alta disponibilidade.

#### Marker do SHA em produção

- Antes de trocar o código, o deploy preserva o SHA conhecido em
  `/home/apps/portal-<ambiente>/.deployed-sha`. Se o arquivo ainda não existir,
  usa o `HEAD` apenas quando já existe um processo PM2 daquele ambiente.
- O marker antigo **não é promovido para o SHA novo durante o restart**. Só o
  job `validate` grava o novo SHA quando API e web retornam simultaneamente
  `curl rc=0` e HTTP exatamente `200`, o job de deploy terminou com sucesso e
  o checkout corresponde ao SHA verificado. 3xx, 4xx, 5xx, erro de conexão
  (`000`) ou erro do `curl` preservam o marker anterior, mesmo que a resposta
  tenha começado com status 200. A gravação continua atômica por arquivo
  temporário + `mv`.
- O arquivo é deliberadamente fora do conteúdo versionado e não contém
  segredo. Não usar `git clean -fdx` no checkout sem copiá-lo/arquivá-lo.

#### Recuperação automatizada por dispatch manual

O workflow [`.github/workflows/rollback.yml`](.github/workflows/rollback.yml)
aceita `workflow_dispatch` com ambiente, `target_sha` completo e `confirm`.
Ele reutiliza `deploy.yml` em `git_mode: rollback`: o mesmo job `verify` (`ci.yml`)
é executado, o SHA é buscado e resetado, o build/dependências são refeitos, os
dois processos usam restart/start com retry e sanidade PM2, e o smoke deve ficar
verde antes de `.deployed-sha` ser promovido. Portanto, o rollback não é um
`git reset` cego nem um segundo script com lógica divergente. Ele também não
ignora o gate: se o SHA antigo não puder passar no CI, o operador precisa usar
o procedimento shell de emergência abaixo, sob autorização explícita.

Procedimento recomendado:

1. Na VPS, leia o alvo **antes** de iniciar o dispatch:
   `cat /home/apps/portal-prod/.deployed-sha` (ou o path do ambiente escolhido).
2. Em **Actions → Rollback manual do portal**, selecione `production`,
   cole o SHA de 40 caracteres, mantenha `tls_enabled` igual ao estado real do
   Nginx e marque `confirm`. O job falha antes do SSH se o SHA não for completo
   ou a confirmação não for verdadeira.
3. Acompanhe `verify`, o reset para o SHA, os dois restarts e o smoke. O
   workflow não cria release GitHub e não altera tags.

Para uma emergência em que o GitHub Actions não está disponível, o procedimento
shell equivalente para PROD (HTTP; para HTTPS, use as duas origens `https://`
e mantenha `tls_enabled=true`/os três flags do `.env`) é:

```bash
set -e
cd /home/apps/portal-prod
PREVIOUS_SHA="$(tr -d '[:space:]' < .deployed-sha)"
if [ "${#PREVIOUS_SHA}" -ne 40 ] || [ -n "$(printf '%s' "$PREVIOUS_SHA" | tr -d '0-9a-fA-F')" ]; then
  echo "ERRO: .deployed-sha não contém um SHA completo" >&2
  exit 1
fi
printf 'sha alvo: %s\n' "$PREVIOUS_SHA"
git fetch --all --tags --force
if ! git cat-file -e "$PREVIOUS_SHA^{commit}" 2>/dev/null; then
  git fetch origin "$PREVIOUS_SHA"
fi
git reset --hard "$PREVIOUS_SHA"

# Reinstala exatamente o runtime validado pelo CI.
cd frontend
export NPM_CONFIG_CACHE="$HOME/.npm"
npm ci --cache "$NPM_CONFIG_CACHE" --prefer-offline
TLS_ENABLED=false                 # altere para true somente se o edge estiver HTTPS
if [ "$TLS_ENABLED" = true ]; then
  API_ORIGIN=https://portal-noticias.com.br
  WEB_ORIGIN=https://portal-noticias.com.br
else
  API_ORIGIN=http://portal-noticias.com.br
  WEB_ORIGIN=http://portal-noticias.com.br
fi
NODE_OPTIONS=--max-old-space-size=1536 \
  NEXT_PUBLIC_API_BASE_URL="$API_ORIGIN" NEXT_PUBLIC_SITE_URL="$WEB_ORIGIN" \
  npm run build
cd ../backend
python3 -m venv .venv
. .venv/bin/activate
# O lock é somente runtime; ferramentas de teste ficam em requirements-dev.txt
# e são instaladas pelo job de verificação, nunca na VPS de produção.
pip install -r requirements-lock.txt
set -a; . ./.env; set +a
python manage.py check
python manage.py migrate
python manage.py collectstatic --noinput

# Não apague os processos: reinicie o existente e só inicie se ele não existir.
if pm2 describe portal-web-prod >/dev/null 2>&1; then
  API_INTERNAL_URL=http://127.0.0.1:5103 PORT=3103 \
    pm2 restart portal-web-prod --update-env
else
  API_INTERNAL_URL=http://127.0.0.1:5103 PORT=3103 \
    pm2 start npm --name portal-web-prod -- start
fi
if pm2 describe portal-api-prod >/dev/null 2>&1; then
  GUNICORN_TIMEOUT=60 DJANGO_SETTINGS_MODULE=config.settings \
    pm2 restart portal-api-prod --update-env
else
  GUNICORN_TIMEOUT=60 DJANGO_SETTINGS_MODULE=config.settings \
    pm2 start .venv/bin/gunicorn --interpreter .venv/bin/python \
      --name portal-api-prod -- --config gunicorn.conf.py config.wsgi:application \
      --bind 0.0.0.0:5103 --chdir /home/apps/portal-prod/backend
fi
pm2 save
pm2 status
probe_http_200() {
  local url="$1"
  local codigo rc
  if codigo="$(curl -sS -o /dev/null -w '%{http_code}' "$url")"; then
    rc=0
  else
    rc=$?
  fi
  if [ "$rc" -ne 0 ] || [ "$codigo" != "200" ]; then
    echo "ERRO: smoke falhou para $url (curl_rc=$rc http_code=$codigo)" >&2
    return 1
  fi
}
probe_http_200 http://127.0.0.1:5103/healthz
probe_http_200 http://127.0.0.1:3103/
# Só promova o marker depois dos dois probes verdes.
SHA_TMP=".deployed-sha.tmp.$$"
(umask 077; printf '%s\n' "$PREVIOUS_SHA" > "$SHA_TMP")
chmod 600 "$SHA_TMP"
mv -f -- "$SHA_TMP" .deployed-sha
```

O comando deve ser executado com o usuário que possui os processos e o checkout.
Se `pm2 status` não mostrar os dois processos `online`, repita o restart
correspondente (o workflow automatizado já faz três tentativas e consulta o
`jlist`). `backend/.env` e `backend/media/` são untracked/ignorados e sobrevivem ao reset;
os dados do PostgreSQL ficam no serviço nativo do host. O rollback de aplicação
**não desfaz migrations**: antes de usar um SHA antigo, confirme que as
migrations são compatíveis e não há rollback de schema automático. Se o health
check falhar, mantenha o marker anterior e faça diagnóstico; não promova um SHA
por otimismo. Uma queda de SSH pode impedir um `trap` local, por isso não há
promessa de rollback automático em todos os casos — o dispatch manual é a
recuperação explícita e auditável.

#### Quando evoluir para blue-green

Reavaliar a arquitetura para releases versionados/blue-green quando o deploy
passar a causar indisponibilidade perceptível ou o tempo de manutenção for
inaceitável. **Gatilho:** "quando o deploy passar a causar indisponibilidade perceptível ou o tempo de manutenção for inaceitável".
Até lá, retry/saúde PM2, marker e rollback manual são a mitigação conservadora;
não há promessa de zero downtime.

### Workflows

| Workflow | Arquivo | Trigger / gate |
|----------|--------|----------------|
| CI | `.github/workflows/ci.yml` | push/PR em develop e main, ou `workflow_call` pelo deploy; Python 3.12 com runtime+dev, `manage.py check`, pytest cov≥80; Node 20 com check de datas em UTC/Tokyo antes de `tsc`/`next build` |
| Deploy DEV | `deploy-dev.yml` | push em develop; `verify` (`ci.yml`) → SSH/PM2 3101/5101; `usuarios_teste: true` (3 contas de teste) |
| Deploy HOMOLOG | `deploy-homolog.yml` | PR para main; `verify` do head do PR → SSH/PM2 3102/5102; `usuarios_teste: true` (3 contas de teste) |
| Deploy PROD | `deploy-prod.yml` | tag `v*` + Release; `verify` do SHA da tag → SSH/PM2 3103/5103; `usuarios_teste: false` explícito (nenhuma conta de teste) |
| Rollback manual | `rollback.yml` | `workflow_dispatch`; `confirm` + SHA completo → mesmo `verify`/PM2/smoke, sem release; não declara `usuarios_teste`, então fica no `false` do `deploy.yml` |

### Dependências Python nos caminhos de execução

- `backend/requirements.txt` é o manifesto de runtime da aplicação e é o único
  arquivo de requirements copiado/instalado pela imagem Docker.
- `backend/requirements-lock.txt` é o lock de runtime, com pins transitivos; é
  instalado pelo runtime PM2 e pelo job de CI.
- `backend/requirements-dev.txt` é exclusivo de desenvolvimento/testes. Ele
  inclui `requirements.txt` e pode ser instalado no ambiente local e no runner
  do CI, mas não deve entrar na imagem ou no runtime PM2. O
  `backend/.dockerignore` mantém esse manifesto fora do contexto Docker. É
  **ele** — e não o lock — que satisfaz os requisitos dos testes: `pytest`,
  `pytest-django`, `pytest-cov` e `pyyaml`. O `pyyaml` não é acidental: a prova
  executada do gate `usuarios_teste`
  (`scripts/verificar-gate-usuarios-teste.sh`, executada por
  `backend/identidade/tests/test_gate_deploy_usuarios_teste.py`) lê o `script:`
  do job `deploy` e roda o shell da VPS; sem `pyyaml` no manifesto esse teste
  era **pulado** no CI, e a proteção de segurança do gate deixava de existir sem
  aparecer nenhum vermelho. O `requirements-lock.txt` é o lock de **runtime** e
  não a recebe de propósito (é ele que a imagem e o PM2 instalam); por isso a
  dependência é declarada no arquivo dev, que é o que o job `backend-tests`
  instala depois do lock.

Secrets exigidos (os mesmos de antes): `VPS_HOST`, `VPS_USER`, `VPS_PASSWORD`, `VPS_PORT` — vinculados a cada **GitHub Environment** (`development`/`homolog`/`production`) em Settings → Environments. O job `verify` não recebe secrets; o job de provisionamento roda com `environment: ${{ inputs.environment_name }}` (ver `.github/workflows/deploy.yml`), então só enxerga os secrets daquele Environment, com proteção de branch/tag. A configuração de regras de proteção/approvals do Environment continua sendo uma decisão humana no GitHub; o gate de CI já está no repositório.

### O gate `usuarios_teste` — contas de teste sem senha em DEV/HOMOLOG

Novo input booleano do `deploy.yml` (`default: false`), no mesmo formato dos
outros inputs do workflow (`tls_enabled`, `web_runtime`, `celery_systemd`):
`true` faz o job `deploy` rodar `manage.py criar_usuario_carga --sem-senha`
**uma vez por perfil**, `--email teste-<papel>@$SUF.portal-noticias.com.br`, com
`--superuser` só no `admin`. O bloco fica logo depois do `collectstatic`,
ainda dentro de `cd "$APP_DIR/backend"` com a venv ativa e **antes** do PM2 — o
código novo já está no disco e as migrations já rodaram, então o portal sobe já
encontrando as contas.

A diferença para a conta de carga do `subir-localhost.sh` é **quem entra e como
a senha nasce**. No localhost a senha é conhecida e impressa no terminal de quem
subiu; em DEV/HOMOLOG ela **não existe em lugar nenhum** — não vai no `argv`
(nem `--password`, nem `PROD_SEED_PASSWORD`), não vai para o `.env`, não vai para
o log do run e não é gravada no banco: a conta nasce com
`set_unusable_password()` e o primeiro acesso é pelo fluxo de recuperação de
senha que o produto já tem (`/recuperar-senha` → `/redefinir-senha`), com a
troca obrigatória no primeiro login (`deve_trocar_senha`). `--sem-senha` com
`--password` é `CommandError`, e o prompt interativo do comando **jamais** roda
nesse caminho (no deploy não há terminal: ele perguntaria e esperaria para
sempre).

Quem liga, e por que a tabela é essa:

| Caller | `usuarios_teste` | Efeito |
|---|---|---|
| `deploy-dev.yml` | `true` | 3 contas em `dev.portal-noticias.com.br` |
| `deploy-homolog.yml` | `true` | 3 contas em `homolog.portal-noticias.com.br` |
| `deploy-prod.yml` | `false` (explícito) | nenhuma; o valor apagado é proteção visível em revisão |
| `rollback.yml` | não declara | nenhuma (fica no `false` do `deploy.yml`) |

Três propriedades do gate importam para quem opera:

1. **Falha por perfil não derruba o deploy**: sai um `AVISO:` nomeado por perfil,
   o resumo `N de 3 contas prontas` e a receita manual para criar a conta à mão.
   O `set -e` do step não morre, porque quem trata o erro é o `if !` da chamada.
   Um deploy derrubado por causa de um atalho de acesso seria pior do que um
   ambiente sem conta de teste.
2. **O valor do input é reatribuído depois do `set -a; . ./.env`**, e o `case` de
   validação é repetido ali. Isso é deliberado: o `backend/.env` da VPS é um
   arquivo texto arbitrário, `chmod 600`, que nunca é sobrescrito, e o `set -a`
   exporta **qualquer** chave que exista nele — uma linha `USUARIOS_TESTE=true`
   nesse arquivo ligaria o gate em PROD sem alteração de repositório e sem aviso.
   Trocar o nome da variável não resolveria (o próximo nome é o mesmo problema);
   o que sobrevive é a atribuição literal do input **depois** do `source`. O
   mesmo vale para o `SUF` dos e-mails: sem essa segunda atribuição, um `SUF=prod`
   no `.env` de DEV/HOMOLOG faria o gate criar `teste-admin@prod.…` — os mesmos
   endereços de PROD.
3. **O comando é idempotente**: num redeploy, quem já passou pela recuperação
   **não** perde a senha nem é obrigado a trocar de novo. Sem isso, o gate — que
   roda a cada push — trancaria fora quem já entrou.

O caminho de entrada tem uma dependência de ambiente que **não** é do gate: o
`.env` do bootstrap não escreve `DJANGO_EMAIL_BACKEND`, então `settings.py` cai no
console backend e o e-mail de recuperação **não chega em nenhum inbox** — ele sai
no stdout do gunicorn (`pm2 logs portal-api-<env>`), com o `uid`/`token`, que é
credencial utilizável da conta. Por isso o bloco final do gate decide a mensagem
pelo valor real de `DJANGO_EMAIL_BACKEND`: com o console ele avisa onde o e-mail
sai; com um backend real, informa qual está em uso. A configuração é pendência
conhecida do projeto (credencial do Resend — `PROD_DECISOES.md`, item 2) e o
passo a passo operacional está em `infra/DEPLOY.md`, na seção *As contas de teste
de DEV e HOMOLOG*.

**Prova executada do gate (não é teste de string).** O gate é shell dentro de um
`script:` de workflow, então `scripts/verificar-gate-usuarios-teste.sh` extrai o
script **literal** do YAML com `yaml.safe_load`, renderiza os inputs e executa o
step inteiro em `dash` (o shell do `/bin/sh` da VPS) contra um `backend/.env` de
verdade, num `APP_DIR` temporário, com `git`/`npm`/`pip`/`pm2`/`python`
stubados. São 25 asserções: o exploit do `.env` (que reprova contra a versão
anterior do workflow), o argv de cada perfil, `--superuser` só no admin, a
ausência de `--password` e de `PROD_SEED_PASSWORD`, o fail-closed de valor, a
falha por perfil sem derrubar o deploy e o texto honesto sobre o e-mail. O CI a
roda por `backend/identidade/tests/test_gate_deploy_usuarios_teste.py` com
`AUTOMUTACAO=1` (que remove o selo de uma cópia do workflow e exige que o
exploit **volte** — a prova de que a prova tem dente). Para rodar fora do CI:

```bash
scripts/verificar-gate-usuarios-teste.sh                 # ~40 s
# contra outra versão do workflow (ex.: a de antes da correção):
scripts/verificar-gate-usuarios-teste.sh /caminho/deploy.yml
AUTOMUTACAO=1 scripts/verificar-gate-usuarios-teste.sh   # ~80 s, com a automutação
```

### Decisão P1-5 — mitigação conservadora, sem trocar o build ainda

O frontend **continua compilando na VPS** nesta versão. A alternativa de
compilar no runner e publicar `.next/standalone` + `.next/static` + `public` é
tecnicamente possível (`frontend/next.config.js` já declara
`output: "standalone"`), mas não foi publicada sem um deploy real porque:

- `NEXT_PUBLIC_API_BASE_URL` e `NEXT_PUBLIC_SITE_URL` são **embutidos no bundle
  durante o build**; um artifact de outro ambiente ou ref pode passar o build
  e falhar em runtime;
- o comando e o cwd do PM2 atuais são `npm start` em `frontend/`; o standalone
  roda `node server.js` e exige preservar sua árvore de diretórios. Ele já
  inclui o `node_modules` mínimo rastreado pelo Next, mas não justifica copiar
  o `node_modules` completo do runner;
- a troca deve ser atômica e ter rollback para o diretório anterior. Copiar
  arquivos soltos sobre o app enquanto o processo está no ar pode misturar duas
  versões e não é reversível.

Mitigações aplicadas agora, sem mudar a estratégia de artifact:

1. `concurrency.group = portal-deploy-<environment_name>` com
   `cancel-in-progress: false`: deploys do mesmo ambiente não disputam o
   restart in-place; um deploy iniciado nunca é morto no meio. A troca continua
   sendo in-place, portanto esta mitigação **não é zero downtime**.
2. **Gate real CI→deploy com `workflow_call` (remediação do blocker):** `ci.yml`
   continua aceitando `push`/`pull_request` e também expõe a mesma definição
   por `workflow_call`. O job `verify` de `deploy.yml` chama esse arquivo; o
   job `deploy` tem `needs: verify`. Portanto, se `backend-tests` (check,
   pytest/cobertura) ou `frontend-build` (`tsc`/`next build`) falhar, for
   cancelado ou não concluir, o SSH/PM2 não é iniciado. O job `guard` e o input
   `guard_ref` não foram reintroduzidos.
   - DEV passa `github.sha`; HOMOLOG passa
     `github.event.pull_request.head.sha`; PROD passa `github.sha` da tag.
   - O `verify` faz checkout desse mesmo SHA. O script de deploy também fixa o
     commit verificado ao buscar branch/PR/tag, evitando que um novo push ou uma
     tag movida durante a fila seja implantado sem verificação.
   - O gate fica no mesmo run, sem `workflow_run` e sem depender do status de
     outro run. A execução de CI é repetida em push/PR (uma para feedback e
     outra dentro do deploy), mas a lógica não é duplicada.
3. **Opções avaliadas:** `workflow_run` exigiria mapear `workflow_run.head_*`
   para ambiente/ref e tratar tags, além de executar com privilégios do
   workflow chamador em contexto diferente; é mais frágil para este conjunto
   de triggers. Branch protection/rulesets são configuração externa e
   continuam recomendações humanas para impedir pushes/tags diretos e exigir
   approvals, mas não são o gate do repositório.
4. Na VPS, `npm ci` usa `$HOME/.npm` com `--prefer-offline`. Esse cache está
   fora de `/home/apps/portal-<env>`, portanto sobrevive a `git reset` e pode ser
   compartilhado pelos três ambientes quando eles usam o mesmo usuário. A
   primeira execução ainda pode baixar tudo; monitore com
   `du -sh "$HOME/.npm"` e não use `npm cache clean` no meio de um deploy.
5. O build usa `NODE_OPTIONS=--max-old-space-size=1536`, limite conservador
   para a VPS de 4 GB que compartilha memória com Postgres, Redis e as três
   stacks. Aumente somente após medir o pico.

**Follow-up obrigatório antes do build remoto:** criar um job no runner com o
mesmo ref que será implantado e os mesmos dois `NEXT_PUBLIC_*`; gerar e
validar o `next build`; empacotar os três diretórios; publicar uma release em
diretório versionado; trocar symlink e reiniciar o PM2 somente após smoke
test; manter a release anterior para rollback. Para PROD, exercite primeiro
HOMOLOG e confirme no bundle que os hosts públicos são os do ambiente.
Configurar no GitHub, por decisão humana, branch protection/ruleset para
`develop`/`main`, proteção de tags e required status checks/approvals dos
Environments; essas regras complementsam o gate versionado, mas não o
substituem.

> **Rotação:** se qualquer secret (`VPS_PASSWORD`, `VPS_USER`, host/porta) for exposto em chat, log ou commit, rotacione imediatamente na VPS (`sudo passwd <usuario>` / troca de porta em `/etc/ssh/sshd_config` + `systemctl reload sshd`) e em Settings → Environments, antes do próximo deploy.

### Banco de dados (Postgres na VPS — único pré-requisito novo)

O software recusa `sqlite3` com `DEBUG=False` (fail-fast em
`config/settings.py`). Uma vez por VPS, como `root`:

```bash
apt install -y postgresql
sudo -u postgres psql -c "CREATE USER portal_app WITH PASSWORD '<senha-forte>';"
sudo -u postgres psql -c "CREATE DATABASE brd_portal_noticias OWNER portal_app;"
```

Depois preencha `DJANGO_DB_PASSWORD` em
`/home/apps/portal-{dev,homolog,prod}/backend/.env` (o workflow cria o
arquivo com placeholder e falha com mensagem clara até a senha existir).
Os 3 ambientes compartilham o servidor, mas use bancos/usuários distintos
se quiser isolamento total.

### Mapa de branches (não apagar)

| Branch | Papel | Deploy |
|--------|-------|--------|
| `main` | produção (só via merge de PR + tag `v*`) | PROD :3103/5103 |
| `develop` | integração (push direto liberado) | DEV :3101/5101 |
| PR `develop` → `main` | validação (manter aberto até aprovar) | HOMOLOG :3102/5102 |
| `homolog-retest` | legado do deploy anterior (congelada) | nenhum |
| `backup/remote-*` | foto do deploy antigo (nunca commitar em cima) | nenhum |
| `v1.0.0` | tag anulada (script Docker, não usar) | — |
| `vX.Y.Z` | releases válidas (a partir de `v1.0.1`) | PROD |

---

## Lote P0-1 — Baseline de proveniência e gate de release

> Seção adicionada pelo lote P0-1 da run `20260925-1433-go-live-producao`
> (contrato: `agentic-framework/state/run-20260925-1433-go-live-producao/lote-p0-1-proveniencia.md`).
> Nada acima desta linha foi reescrito: **nenhum workflow, gatilho, job ou
> segredo do CI/CD foi alterado, criado ou removido** por este lote.

### O que foi entregue

Uma ferramenta de linha de comando, versionada no repositório e **não
registrada em nenhum workflow**:

```bash
scripts/release/verificar-proveniencia.sh [--expected-sha <40-hex>] [--repo <dir>] [--json]
scripts/release/verificar-proveniencia.sh --help
```

O gate é **read-only** (não cria, altera, move nem apaga arquivo; não usa
arquivo temporário; não executa `git add/commit/push/merge/rebase/reset/clean/
checkout/switch/stash/restore/apply`), **não acessa a rede**, não consulta
remoto, não exige e não lê segredo. Ele reprova (fail-closed) quando:

1. o repositório ou uma ferramenta obrigatória não pode ser usado;
2. `HEAD` é diferente do SHA de release esperado (`--expected-sha`);
3. há arquivo **rastreado** modificado, removido ou renomeado;
4. há arquivo **não rastreado** (respeitando `.gitignore`) — o diretório de
   estado das runs é não rastreado por decisão de ownership e reprova o gate
   por isso mesmo, sem que `.gitignore` seja editado;
5. há `assume-unchanged`/`skip-worktree` escondendo estado de arquivo;
6. há marcador de conflito (`<<<<<<<`, `>>>>>>>`, `=======`) em arquivo rastreado;
7. há segredo aparente em arquivo **rastreado** (chave privada, AWS, GitHub,
   Slack, Stripe, Google API, webhook, ou chave/token com valor literal);
8. há `.py` rastreado que não faz parse;
9. há `.yml`/`.yaml` rastreado que não faz parse.

### Contrato da CLI

| Exit code | Significado |
|---|---|
| `0` | aprovado: todas as checagens passaram **e** `--expected-sha` foi informado e igualou `HEAD` |
| `1` | reprovado: checagem falhou, não pôde ser executada, **ou o resultado ficou incompleto** |
| `2` | uso incorreto: flag desconhecida, valor ausente, `--expected-sha` fora de 40 hex, `--repo` inválido |

- Sem `--expected-sha` o resultado fica **incompleto** e a saída é `1`.
  Ausência da flag nunca é aprovação automática nem aprovação por omissão.
- `--expected-sha` em formato inválido é **uso incorreto** (`2`), não SHA ausente.
- Falha fechada: sem `git`, sem `python3`, sem PyYAML (quando há YAML
  rastreado) ou com erro interno, o gate reprova com motivo explícito; não
  existe bypass silencioso.
- A saída é determinística (sem timestamp, sem cor; achados ordenados por
  checagem, caminho e linha) e **nunca imprime valor de segredo**: o achado
  traz só identificador de regra, caminho, número da linha e a declaração de
  que o valor foi omitido — em texto e em `--json`.

### O que o gate **não** cobre (leitura obrigatória)

- **Não roda em pipeline nenhum.** Nenhum workflow foi alterado neste lote,
  então o gate só executa quando alguém o invoca, local ou externamente. Ele
  não é today nenhum required status check.
- **Só bloqueia de fato com branch protection do GitHub configurada** (PR
  obrigatório) **e** com o gate registrado como required status check. Como
  este lote não toca em CI/CD, nenhuma das duas condições existe hoje.
  Configurar branch protection sem um check registrado **não** torna o gate
  obrigatório. Isso é **HD-2** (configuração humana) e **HD-6** (onde o gate
  rodará de forma recorrente): pré-requisitos de eficácia, não de entrega.
- **Não cobre o caminho pull request → VPS de HOMOLOG.** Ver R-1 abaixo.
- Não valida/pina host key (`known_hosts`) — atribuído a outro lote.
- Não é `.gitignore` permissivo nem `skip-worktree` que burlam: arquivo
  ignorado não é analisado (e reprova como não rastreado só se não estiver
  de fato ignorado), e `skip-worktree`/`assume-unchanged` é achado próprio.

### R-1 — supply chain: caminho PR → VPS (ACEITO e ABERTO)

O caminho continua **ativo e inalterado**:
`.github/workflows/deploy-homolog.yml` dispara em `pull_request` para `main`,
delega ao `deploy.yml` e implanta na VPS persistente em
`/home/apps/portal-homolog` (3102/5102) com `git_mode: pr` e `verify_ref`
preenchido pelo SHA do head do pull request — isto é, **código de pull request
não aprovado pode rodar em uma máquina que tem segredos**.

- Situação padronizada: **ACEITO** (decisão do solicitante), **ABERTO**,
  **NÃO MITIGADO**, **NÃO COBERTO PELO GATE**, **NÃO BLOQUEANTE para o
  go-live**.
- Este lote **não** alterou, **não** mitigou, **não** bloqueou e **não**
  compensou esse caminho, e nenhum artefato deste lote pode marcá-lo como
  resolvido.
- Por não bloquear o go-live, ele **exige aceite explícito e assinado no
  go/no-go**, com a descrição do caminho, o que está sendo aceito, por quanto
  tempo e quem assinou. A decisão futura sobre substituir esse caminho
  (branch de promoção, `workflow_dispatch` com SHA explícito, ou desabilitar
  o deploy por PR) é de um lote próprio, com revisão de CI/CD.

### R-2 — divergência de domínio (ABERTO, registrada)

O único valor de domínio adotado no programa é o canônico
`https://portal-noticias.com/`. Os workflows existentes usam hoje
`portal-noticias.com.br` (`dev.`, `homolog.`, raiz de PROD e `www.` em
`allowed_hosts_extra`). A divergência está **registrada e não foi corrigida**:
alterar valor de domínio em workflow é lote posterior, sem mudar estrutura,
gatilhos ou comportamento. Nenhum valor de domínio em workflow foi alterado
por este lote.

### Evidência

- Baseline re-derivada, inventário atribuído por run e resultados de todos os
  casos negativos: `agentic-framework/state/run-20260925-1433-go-live-producao/lote-p0-1-evidencias.md`.
- Histórico do lote: `agentic-framework/state/run-20260925-1433-go-live-producao/implementation-history.md`.
