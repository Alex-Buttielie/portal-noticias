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

> **Cutover para Docker Compose + GHCR — pronto no código, NÃO ativo na VPS.**
> O restante deste documento descreve a topologia **PM2 + Nginx**, que é a
> que roda de verdade hoje. Em paralelo, os cinco workflows
> (`deploy.yml`, `deploy-{dev,homolog,prod}.yml`, `rollback.yml`) e o
> `docker-compose.yml` da raiz já foram reescritos para uma topologia nova:
> as imagens são buildadas e publicadas no GHCR pelo próprio Actions (nunca
> mais pip/npm na VPS), a VPS só faz `docker compose pull && up -d`, e um
> Caddy único compartilhado (`infra/docker-edge/`) substitui o Nginx —
> dizer isto "entregue" antes do corte real na VPS seria o mesmo falso
> verde que este projeto existe para evitar. Verificado até aqui (sem
> acesso à VPS): `actionlint` limpo nos 6 workflows, sintaxe shell dos
> scripts embutidos, `docker compose config`/`caddy validate`/`alloy
> validate` com as imagens oficiais, e um teste de ponta a ponta com
> containers reais (Django + Next.js + Caddy) respondendo corretamente a
> `/livez`, `/readyz`, `/health-detail` (com e sem token) e `/api/*`. O que
> falta para a seção abaixo deixar de valer: provisionar os secrets
> `GHCR_PULL_TOKEN`/`GHCR_PULL_USER`, instalar `infra/docker-edge/` na VPS,
> migrar os dados do Postgres do host para os volumes dos containers
> (backup-first, ambiente por ambiente) e confirmar saudável antes de
> desligar PM2/Nginx — nessa ordem, nunca em produção primeiro. Ver
> `infra/docker-edge/README.md` para a instalação do Caddy compartilhado.
> **Retirada, não portada: o gate `usuarios_teste`** (contas de teste
> sem senha em DEV/HOMOLOG — ver a seção dedicada mais abaixo). Decisão
> registrada ali, não um gap pendente.

### Ambientes na VPS (PM2 + Nginx — topologia ATIVA hoje)

| Ambiente | Ref git | Dir VPS | PM2 web/api | Portas |
|----------|---------|---------|-------------|--------|
| DEV | `develop` | `/home/apps/portal-dev` | `portal-web-dev` / `portal-api-dev` | 3101 / 5101 |
| HOMOLOG | head do PR (SHA fixo) | `/home/apps/portal-homolog` | `portal-web-homolog` / `portal-api-homolog` | 3102 / 5102 |
| PROD | `main` (tag `v*`, SHA fixo) | `/home/apps/portal-prod` | `portal-web-prod` / `portal-api-prod` | 3103 / 5103 |

Nginx (configuração canônica em `infra/nginx/portal-{dev,homolog,prod}.conf` — idênticas às ativas na VPS; aplicar conforme o cabeçalho dos arquivos):
`dev.portal-noticias.com` (`/`→3101, `/api/`→5101, preservando o path),
`homolog.portal-noticias.com` (→3102/5102),
`portal-noticias.com` (→3103/5103).

**Contas de teste por ambiente:** DEV e HOMOLOG recebem, a cada deploy, uma conta
por perfil — `teste-<papel>@<pm_suffix>.portal-noticias.com`, isto é
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
  API_ORIGIN=https://portal-noticias.com
  WEB_ORIGIN=https://portal-noticias.com
else
  API_ORIGIN=http://portal-noticias.com
  WEB_ORIGIN=http://portal-noticias.com
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
  `pytest-django` e `pytest-cov`. (Teve `pyyaml` até a retirada do gate
  `usuarios_teste` no cutover Docker — ver a seção dedicada mais abaixo — cujo
  harness era o único consumidor; removido junto, sem substituto.)

Secrets exigidos: `VPS_HOST`, `VPS_USER`, `VPS_PORT` e **`VPS_SSH_KEY`** — vinculados a cada **GitHub Environment** (`development`/`homolog`/`production`) em Settings → Environments. O job `verify` não recebe secrets; o job de provisionamento roda com `environment: ${{ inputs.environment_name }}` (ver `.github/workflows/deploy.yml`), então só enxerga os secrets daquele Environment, com proteção de branch/tag. `VPS_PASSWORD` saiu do contrato em 2026-10-08: o SSH autentica por chave, o secret no GitHub era obsoleto desde a rotação da senha do root, e não há fallback para a senha por desenho. A configuração de regras de proteção/approvals do Environment continua sendo uma decisão humana no GitHub; o gate de CI já está no repositório.

### O gate `usuarios_teste` — contas de teste sem senha em DEV/HOMOLOG

> **Retirado no cutover Docker (decisão de 2026-10-09), não portado.** O que
> esta seção descreve abaixo é real **enquanto PM2 + Nginx for a topologia
> ativa** (ver a nota no topo deste documento). O `deploy.yml` do cutover
> Docker (`feat(deploy): reescreve deploy.yml/callers/rollback.yml para
> Docker+GHCR`) eliminou inteiramente o input `usuarios_teste`, o
> `script_path`/`infra/deploy/deploy.sh` e qualquer caminho de criação de
> conta — não sobrou onde pendurar o gate. A decisão foi **retirar a
> feature**, não redesenhá-la, por dois motivos: (1) o `docker-entrypoint.sh`
> roda a cada *restart* do container `web`, em **todos** os ambientes
> (inclusive PROD) — amarrar uma mutação de banco condicional a esse ponto
> trocaria um script de deploy único por uma superfície de risco maior, sob
> o pretexto de "portar"; (2) nada no plano do cutover (`agentic-framework/
> state/run-20260925-1433-go-live-producao/`) lista as contas de teste como
> bloqueador do go-live Docker. Se precisar de login sem senha em DEV/HOMOLOG
> depois do cutover, criar a conta à mão (receita em `infra/DEPLOY.md`,
> seção *Como entrar*) continua funcionando — só o automatismo do deploy que
> não existe mais. `backend/identidade/tests/test_gate_deploy_usuarios_teste.py`
> e `scripts/verificar-gate-usuarios-teste.sh` foram removidos junto com esta
> decisão; o texto abaixo é histórico da topologia PM2.

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

> **Rotação:** se qualquer secret (`VPS_SSH_KEY`, `VPS_USER`, host/porta) for exposto em chat, log ou commit, rotacione imediatamente na VPS (`sudo passwd <usuario>` / troca de porta em `/etc/ssh/sshd_config` + `systemctl reload sshd`) e em Settings → Environments, antes do próximo deploy.

### §P1-6 — release atômica, runtime standalone e Celery no systemd (C2)

> Acrescimo seccionado: a §P1-5 acima **não foi reescrita** e continua
> descrevendo as mitigações que valem. Esta seção registra o que foi
> executado a partir do plano de release atômica que a própria §P1-5 exigia
> ("follow-up obrigatório antes do build remoto"), e o que continua
> exatamente igual.

#### O que mudou, em uma tela

| Antes | Agora | Onde |
|---|---|---|
| `npm start` no PM2, `.next/` reescrito embaixo do processo em produção | `node .next/standalone/server.js` com `public/` e `.next/static` no lugar, `HOSTNAME`/`PORT` explícitos | `web_runtime: standalone` (padrão) |
| deploy in-place: um probe verde era a única barreira | release em `frontend/releases/<id>/`, smoke NELA, e só então o symlink `current` alterna; release anterior preservada em `previous` | `.github/workflows/deploy.yml` |
| sem retorno automático | se o PM2 não sobe na release nova, `current` volta para a anterior, o processo sobe nela e o deploy **falha** (marker preservado) | `voltar_release_anterior` |
| Celery inexistente na topologia ativa (achado B4) | `celery-worker@<env>` e `celery-beat@<env>` instaladas e ativadas pelo deploy, com `%i` = ambiente | `ativar_celery_systemd` |
| SSH por senha, host key não conferida | chave dedicada e impressão digital do host **aceitas como alternativa**, com o caminho por senha intacto | `VPS_SSH_KEY` / `VPS_HOST_FINGERPRINT` |
| source maps não subiam | `sentry-cli sourcemaps upload` no `frontend-build`, fail-open sem token | `.github/workflows/ci.yml` |
| config de infra só quebrava na VPS | gate `validar-infra.sh --estrito` no CI, com pendência declarada | job `infra-validate` |

**O que NÃO mudou, deliberadamente:** o build continua compilando **na VPS**
(heap 1536 MB, três stacks na mesma máquina) — a estratégia de build não foi
trocada; `concurrency` sem cancelamento; o marker `.deployed-sha` e a sua
promoção só após os dois probes verdes; `strict_validate`; o caminho
`git_mode: rollback` usado por `rollback.yml`; e o backend, que continua com
`git reset --hard` + `migrate` in-place.

#### Release atômica: o desenho e o porquê do escopo

A §P1-5 escrevera "publicar uma release em diretório versionado; trocar symlink
e reiniciar o PM2 somente após smoke test; manter a release anterior para
rollback". Feito — com um recorte que vale explicar, porque é a parte em que a
promessa e o fato divergem se ninguém disser:

**A release é do TIER WEB, não do app inteiro.** O symlink só pode promover o
que não tem migration e não tem estado. O backend usa `git reset --hard` +
`migrate` no lugar de propósito: `backend/.env` e `backend/media/` são
untracked e sobrevivem ao reset, `.venv` é reaproveitado, e trocar o diretório
do backend exigiria mover as units systemd (`/home/apps/portal-%i/backend`),
os scripts de backup e a árvore de mídia — centenas de MB por release numa VPS
de 4 GB, sem ganho de atomicidade. Promover o frontend sozinho é onde a troca
de versão realmente acontece: era `next build` reescrevendo `.next/` enquanto o
processo em produção lia essa mesma árvore.

Layout em `$APP_DIR/frontend/releases/`:

```text
releases/
  20260925T180000Z-aaaaaaaaaaaa/     release imutável
    standalone/                        server.js + node_modules + public/ + .next/static
    .deployed-sha                      o commit desta release (rollback por symlink descobre sem git)
  20260925T183000Z-bbbbbbbbbbbb/     release anterior
  current -> 20260925T183000Z-bbbb…   symlink que o PM2 consome (caminho estável)
  previous -> 20260925T180000Z-aaaa…  alvo do retorno automático
```

Ordem exata do deploy, e o que cada passo pode quebrar:

1. `npm ci` + `next build` na VPS, como antes;
2. `preparar_release` copia a árvore standalone para a pasta da release e
   chama `infra/standalone/run-standalone.sh prepare` (que copia `public/` e
   `.next/static` — o mesmo padrão do `frontend/Dockerfile`);
3. `smoke_release` sobe a release em **porta livre** e valida `/robots.txt`, um
   asset real de `.next/static` e a Home. O smoke **aceita 503** na Home
   (estado documentado de feed indisponível sem cache) e **reprova 5xx** e
   asset ausente — comportamento testado, não presumido;
4. **só depois** `promover_release` grava `previous` com o alvo antigo de
   `current` e alterna `current` por `ln -s` + `mv -T` (rename(2) sobre o
   symlink: quem lê o link vê a release antiga ou a nova, nunca um estado
   quebrado — `ln -sfn` NÃO é atômico);
5. `restart_or_start` sobe o processo. Se não ficar `online` em 3 tentativas,
   `current` volta para `previous` e o processo sobe na anterior — e o deploy
   **termina com erro de qualquer forma**: um exit 0 promoveria no
   `.deployed-sha` um SHA cuja release não está no ar, e o marker é a
   fronteira de recuperação;
6. `podar_releases` mantém as 3 mais recentes por data, **protegendo** os
   alvos de `current` e `previous` mesmo quando ficaram fora do recorte (o caso
   de quatro deploys seguidos, em que o alvo do retorno sumiria).

Falha nos passos 2 ou 3 aborta o deploy **antes** de qualquer mudança
visível: sem `current` novo, sem restart, sem migration, sem promoção do
marker. É a propriedade que o plano pedia e a que o smoke existia para dar.

**O que isso não é:** não é blue-green e não é zero downtime. Continua havendo
uma janela em que o processo do frontend é reiniciado no mesmo PM2; o que
muda é que existe uma versão anterior pronta e um retorno de um comando. A
§P1-5 e o gatilho de "quando evoluir para blue-green" continuam valendo — o
ganho aqui é reversibilidade, não disponibilidade.

#### `web_runtime`: o caminho novo tem escape hatch

O input `web_runtime` (`standalone` | `npm`, padrão `standalone`) existe porque
trocar o runtime do processo em produção sem rede de segurança seria(o) o
arriscado, e o §P1-5 já mostra o que acontece quando se copia arquivo solto
por cima de app no ar. Com `npm`, o deploy faz exatamente o que fazia antes
(build in-place + `npm start`), sem tocar em `releases/`. Está exposto no
dispatch de `rollback.yml`, que é onde o operador precisa dele durante um
incidente. **Não remova o caminho `npm` sem antes de um deploy `standalone`
ter sido validado num ambiente real com probes verdes** — a remoção do escape
hatch é a última etapa da mudança, não uma parte dela.

#### Celery no systemd: placeholders resolvidos, falha não derruba deploy

As units são **template** (`celery-worker@.service`, com `%i`), porque a mesma
VPS hospeda os três ambientes e uma unit com `EnvironmentFile` fixo serviria a
um só — e o ambiente errado é exatamente a falha que produz backup do banco de
dev em produção. O deploy resolve os dois placeholders: `%i` = `$SUF`
(`dev`/`homolog`/`prod`) e `User=`/`Group=` = o dono do app (`id -un`), como o
cabeçalho de cada unit prescreve (root é proibido: o worker tem o mesmo acesso
a mídia e banco que a aplicação web).

Ele também cria `/etc/portal/celery-<env>.env` **se não existir**, com os
mesmos valores que o serviço `celery-worker` do `docker-compose.yml` já usa
(`--concurrency=2 --max-tasks-per-child=100`) mais o
`BEAT_HEARTBEAT_FILE`/`OBSERVABILITY_BEAT_HEARTBEAT_FILE`. Os dois
`EnvironmentFile` das units não têm o prefixo `-`, então sem esse arquivo a
unit **não sobe** (fail-closed proposital): criá-lo aqui é provisionar o que a
unit exige, não afrouxar a barreira. O arquivo **nunca é sobrescrito** — ajuste
do operador é preservado. `celery_systemd: false` não toca em nada.

Falha de Celery **não derruba o deploy**: web e API já estão no ar, e o estado
do worker é degradação visível em `/health-detail` e no alerta
`PortalFilaCelery`. Um deploy que caísse por causa do Celery seria pior que o
Celery parado.

Correção mínima em arquivo do Bloco C1: `celery-beat-heartbeat@.service` ganhou
`StateDirectory=portal-observabilidade`. Com `ProtectSystem=strict` (C1), o
diretório do heartbeat ficava somente-leitura, o `touch` falharia a cada tick
e a unit passaria a falhar **com o beat vivo** — o oposto do produtor que ela
existe para ser. `StateDirectory` resolve sem afrouxar o `ProtectSystem`.

**A unit é a fonte única da verdade desse diretório** — o deploy não o cria.
`StateDirectory` faz o systemd criar o diretório com o `User=`/`Group=` *da
própria unit* e o coloca na lista de escrita do `ProtectSystem=strict`. Um
`install -d` do deploy daria ao diretório o dono do usuário do deploy: hoje
coincide com o `User=` da unit, mas divergiria no primeiro ambiente em que
alguém ajustasse o `User=` (que é o ajuste que o cabeçalho da unit prescreve), e
o sintoma seria `touch` falhando por permissão com o beat vivo.

**E o heartbeat tem duas pontas, em arquivos diferentes** (achado do follow-up,
que a primeira entrega do C2.3 tinha errado):

| Ponta | Quem lê | De onde |
|---|---|---|
| **Produtor** — `celery-beat-heartbeat@<env>.service` faz o `touch` | unit systemd | `/etc/portal/celery-<env>.env` (`BEAT_HEARTBEAT_FILE`) |
| **Consumidor** — `check_celery_beat` em `/health-detail` | gunicorn do PM2 | `backend/.env` (`OBSERVABILITY_BEAT_HEARTBEAT_FILE`) |

O gunicorn sobe com `set -a; . ./.env`, ou seja, lê **só** `backend/.env` — ele
nunca vê `/etc/portal/celery-<env>.env`, que é lido apenas pelas units systemd.
Com a entrega anterior, o produtor escrevia o arquivo e o consumidor não tinha
como saber o caminho: `check_celery_beat` ficava `not_configured` para sempre,
com o beat vivo e o heartbeat sendo tocado a cada 5 min. É o pior tipo de falha
de observabilidade — não há sintoma, porque nada acusa nada.

O deploy agora também acrescenta `OBSERVABILITY_BEAT_HEARTBEAT_FILE` ao
`backend/.env`, **sem reescrever o arquivo** (o `.env` é gerado uma vez e nunca
sobrescrito, por invariante do projeto): se a chave já existir com o caminho
certo, nada muda; se existir com **outro** valor, o deploy **avisa e preserva** —
mudar o `.env` do operador em silêncio faria o check passar a ler um arquivo que
ninguém produz. Falha de escrita também vira aviso, nunca derruba o deploy.

O caminho é o mesmo nos três ambientes porque ambos vêm da mesma variável
`$SUF` (`pm_suffix` do caller): `/var/lib/portal-observabilidade/beat-<env>.heartbeat`
para `dev`, `homolog` e `prod`. O consumidor precisa apenas de travessia (`x`) no
diretório para o `Path.stat()` — nunca de permissão de leitura no arquivo, cujo
conteúdo é irrelevante (só o `st_mtime` é lido). Por isso a unit declara
`StateDirectoryMode=0755`.

#### O gate `usuarios_teste`: contas de teste sem senha em DEV/HOMOLOG

Novo input booleano do `deploy.yml` (`default: false`), no mesmo formato de
`tls_enabled`, `web_runtime` e `celery_systemd`: `true` faz o job `deploy`
rodar `manage.py criar_usuario_carga --sem-senha` **uma vez por perfil**,
`--email teste-<papel>@$SUF.portal-noticias.com`, com `--superuser` só no
`admin`. O bloco fica logo depois do `collectstatic`, ainda dentro de
`cd "$APP_DIR/backend"` com a venv ativa e **antes** do PM2 — o código novo já
está no disco e as migrations já rodaram, então o portal sobe já encontrando as
contas.

A diferença para a conta de carga do `subir-localhost.sh` é **quem entra e como
a senha nasce**. No localhost a senha é conhecida e impressa no terminal de quem
subiu; em DEV/HOMOLOG ela **não existe em lugar nenhum** — não vai no `argv`
(nem `--password`, nem `PROD_SEED_PASSWORD`), não vai para o `.env`, não vai para
o log do run e não é gravada no banco: a conta nasce com `set_unusable_password()`
e o primeiro acesso é pelo fluxo de recuperação de senha que o produto já tem
(`/recuperar-senha` → `/redefinir-senha`), com a troca obrigatória no primeiro
login (`deve_trocar_senha`). `--sem-senha` com `--password` é `CommandError`, e
o prompt interativo do comando **jamais** roda nesse caminho (no deploy não há
terminal: ele perguntaria e esperaria para sempre).

Quem liga, e por que a tabela é essa:

| Caller | `usuarios_teste` | Efeito |
|---|---|---|
| `deploy-dev.yml` | `true` | 3 contas em `dev.portal-noticias.com` |
| `deploy-homolog.yml` | `true` | 3 contas em `homolog.portal-noticias.com` |
| `deploy-prod.yml` | `false` (explícito) | nenhuma; o valor apagado é proteção visível em revisão |
| `rollback.yml` | não declara | nenhuma (fica no `false` do `deploy.yml`) |

Três propriedades do gate importam para quem opera:

1. **Falha por perfil não derruba o deploy**, com a mesma política do Celery: um
   `AVISO:` nomeado por perfil, o resumo `N de 3 contas prontas` e a receita
   manual para criar a conta à mão. O `set -e` do step não morre, porque quem
   trata o erro é o `if !` da chamada. Um deploy derrubado por causa de um atalho
   de acesso seria pior do que um ambiente sem conta de teste.
2. **O valor do input é reatribuído depois do `set -a; . ./.env`**, e o `case` de
   validação é repetido ali. Isso é deliberado: o `backend/.env` da VPS é um
   arquivo texto arbitrário, `chmod 600`, que nunca é sobrescrito, e o `set -a`
   exporta **qualquer** chave que exista nele — uma linha `USUARIOS_TESTE=true`
   nesse arquivo ligaria o gate em PROD sem alteração de repositório e sem aviso.
   Trocar o nome da variável não resolveria (o próximo nome é o mesmo problema);
   o que sobrevive é a atribuição literal do input **depois** do `source`.
3. **O comando é idempotente**: num redeploy, quem já passou pela recuperação
   **não** perde a senha nem é obrigado a trocar de novo, e o `Token` de quem está
   logado é preservado. Sem isso, o gate — que roda a cada push — trancaria fora
   quem já entrou.

O caminho de entrada tem uma dependência de ambiente que **não** é do gate: o
`.env` do bootstrap não escreve `DJANGO_EMAIL_BACKEND`, então `settings.py` cai no
console backend e o e-mail de recuperação **não chega em nenhum inbox** — ele sai
no stdout do gunicorn (`pm2 logs portal-api-<env>`), com o `uid`/`token`, que é
credencial utilizável da conta. Por isso o bloco final do gate decide a mensagem
pelo valor real de `DJANGO_EMAIL_BACKEND`: com o console ele avisa onde o e-mail
sai; com um backend real, informa qual está em uso. A configuração é pendência
conhecida do projeto (credencial do Resend — `PROD_DECISOES.md`, item 2) e o
passo a passo operacional está em `infra/DEPLOY.md` §9.7.

**Prova executada do gate (não é teste de string).** O gate é shell dentro de um
`script:` de workflow, então `scripts/verificar-gate-usuarios-teste.sh` extrai o
script **literal** do YAML com `yaml.safe_load`, renderiza os inputs e executa o
step inteiro em `dash` (o shell do `/bin/sh` da VPS) contra um `backend/.env` de
verdade, num `APP_DIR` temporário, com `git`/`npm`/`pip`/`pm2`/`python`
stubados. São 21 asserções: o exploit do `.env` (que reprova contra a versão
anterior do workflow), o argv de cada perfil, `--superuser` só no admin, a
ausência de `--password` e de `PROD_SEED_PASSWORD`, o fail-closed de valor, a
falha por perfil sem derrubar o deploy e o texto honesto sobre o e-mail. O CI a
roda por `backend/identidade/tests/test_gate_deploy_usuarios_teste.py` com
`AUTOMUTACAO=1` (que remove o selo de uma cópia do workflow e exige que o
exploit **volte** — a prova de que a prova tem dente). Para rodar fora do CI:

```bash
scripts/verificar-gate-usuarios-teste.sh                 # ~40 s
AUTOMUTACAO=1 scripts/verificar-gate-usuarios-teste.sh   # ~80 s, com a automutação
```

#### O canal de job tem o mesmo formato e as duas pontas (D2)

O canal durável de telemetria de job (`backend/config/job_state.py`, achado
MAJOR-4 da revisão de backend) reproduz o padrão do heartbeat porque tem
**exatamente o mesmo defeito estrutural**: quem produz o dado e quem o consome
são processos diferentes, que leem arquivos de ambiente diferentes.

| Ponta | Quem | De onde |
|---|---|---|
| **Produtor** — grava o estado ao fim de cada task (`config/celery.py`, sinais `task_postrun`/`task_retry`) | `celery-worker@<env>` | `/etc/portal/celery-<env>.env` (`OBSERVABILITY_JOB_STATE_FILE`) |
| **Consumidor** — publica `portal_job_task_idle_seconds` no `/metrics` e roda o check `celery_jobs` | gunicorn do PM2 | `backend/.env` (`OBSERVABILITY_JOB_STATE_FILE`) |

O nome da variável é o mesmo nos dois lados **de propósito**: é o mesmo canal, e
divergência silenciosa entre produtor e consumidor é o modo de falha que esta
run existe para eliminar. Com o valor ausente ou divergente, o check fica
`not_configured` — que conta como degradação (fail-closed), então o portal
responde `degraded` por desenho e **ninguém é avisado por nada**. O caminho
também vem da mesma `$SUF`: `/var/lib/portal-observabilidade/jobs-<env>.json`.

O que o deploy passou a fazer (e o que ele deliberadamente **não** faz):

* acrescenta `OBSERVABILITY_JOB_STATE_FILE` ao `/etc/portal/celery-<env>.env`
  **na criação** do arquivo (nunca sobrescreve, igual ao resto do tuning);
* acrescenta `OBSERVABILITY_JOB_STATE_FILE` **e**
  `OBSERVABILITY_JOB_STATE_MAX_AGE_SECONDS` ao `backend/.env` **sem reescrever
  o arquivo** — se a chave já existir com o caminho certo, nada muda; se existir
  com **outro** valor, avisa e **preserva** (mesma política do heartbeat: mudar o
  `.env` do operador em silêncio faria o consumidor ler um arquivo que o produtor
  não escreve);
* imprime as duas pontas lado a lado no log do run e no job `validate`, para que
  a divergência apareça no mesmo lugar onde se olha o resultado do deploy.

`OBSERVABILITY_JOB_STATE_MAX_AGE_SECONDS` (900 s) é lido **só** pelo processo web
(`health.py::check_celery_jobs` → `job_state.idade_maxima`): é a janela de
frescor do arquivo, e o stale dela é o que denuncia um canal rompido.

O diretório **não** é criado pelo deploy: a fonte única continua sendo o
`StateDirectory=` de `celery-beat-heartbeat@.service`. O worker grava dentro dele
com `ProtectSystem=full` (que trava `/usr` e `/boot`, não `/var`) e o
`UMask=0027` da unit deixa o arquivo em 0640 do dono do app — que é o mesmo
usuário que o gunicorn usa para ler. Nenhum afrouxamento de hardening foi
necessário, e é por isso que a unit do worker não mudou.

**O que continua manual:** com `celery_systemd: false` (sem worker de systemd) ou
na topologia do `docker-compose.yml`, o caminho tem de chegar ao serviço do
Celery por fora do bloco do deploy — ver `infra/DEPLOY.md`, seção 9.4.

#### `X-Forwarded-For` na borda: o leitor seguro precisa de algo para ler (D2)

`backend/config/proxies.py` (achado MAJOR-1) só considera o `X-Forwarded-For`
quando quem abriu a conexão é o loopback ou uma rede declarada, e só usa o
**último** elemento da cadeia. Os três `infra/nginx/portal-<env>.conf` agora
escrevem o header em **todos** os 13 upstreams de cada arquivo com
`proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;`, que anexa o
`$remote_addr` ao fim da cadeia — o último elemento é sempre o cliente real
deste salto, e nenhum header enviado pelo cliente se passa por proxy confiável.
Os três arquivos continuam estruturalmente idênticos, e
`scripts/observability/validar-infra.sh` (gate do `ci.yml`) passa a **falhar**
se a diretiva sumir, se aparecer `$http_x_forwarded_for` (que repassaria o
header do cliente) ou se a contagem de diretivas deixar de ser 1:1 com a de
`proxy_pass`. O job `validate` do deploy ainda confere o arquivo **instalado**
(`nginx -T`), porque é ele — e não o repositório — que está no caminho do tráfego.

Cloudflare/CDN continua opcional, mas se um for posto na frente depois, leia a
seção de XFF de `infra/DEPLOY.md` antes: sem o módulo `realip` com
`set_real_ip_from`, todo mundo passa a aparecer com o IP do CDN.

#### SSH: chave com fallback, e por que a senha continua lá

`VPS_SSH_KEY` (conteúdo PEM da chave privada) e `VPS_HOST_FINGERPRINT`
(impressão digital `SHA256:…` do host key) são **opcionais**. Vazias, o
comportamento é exatamente o de antes — a action simplesmente ignora as entradas
vazias e autentica por senha. Preenchidas, elas entram como credencial
alternativa e a impressão digital passa a ser conferida: divergência **derruba
a conexão** em vez de aceitar qualquer host.

Duas coisas que valem saber antes de mexer nisso:

- **A ordem é do cliente SSH da action, não deste workflow.** Com as duas
  credenciais presentes, a senha é oferecida primeiro e a chave em seguida;
  qualquer uma das duas autentica. A chave **não** tem precedência enquanto
  `VPS_PASSWORD` existir, e isso não é corrigível aqui sem remover a senha — que
  é justamente o passo adiado.
- **A impressão digital tem que ser do host key ED25519.** A action compara
  com a primeira host key que o servidor oferecer, e o ED25519 é o primeiro da
  lista padrão do cliente Go. `ssh-keygen -lf /etc/ssh/ssh_host_ed25519_key.pub`
  na VPS. Passar a impressão de outro tipo de host key faz a conexão falhar —
  fail-closed, que é o comportamento desejado, mas confuso se não for esperado.

**A remoção da senha não está nesta mudança.** Ela depende de acesso real à VPS
e de um deploy que tenha autenticado **só** com a chave. A sequência está em
`infra/DEPLOY.md` §9.

#### Source maps no CI (fail-open)

Passo no `frontend-build`, depois do `npm run build`, com `sentry-cli`:

- **sem `SENTRY_AUTH_TOKEN` o passo nem roda.** PR de fork e clone local não
  têm secrets, e um CI que exige segredo para buildar trava o projeto
  inteiro, inclusive para quem só quer abrir PR. A decisão sai de um passo
  anterior que publica um output, porque `if:` não pode referenciar `secrets`;
- **com token, uma falha de upload não reprova o build**
  (`continue-on-error`). Source map é insumo de diagnóstico: transformar
  indisponibilidade do Sentry em indisponibilidade de deploy troca um problema
  pequeno por um grande;
- **sem nenhum `.map` em `.next`, o upload é pulado com aviso.** Hoje o
  `next.config.js` (Bloco B2) usa `withSentryConfig` com
  `deleteSourcemapsAfterUpload: false`, então os mapas **permanecem** e o passo
  acima é quem os envia. Se essa opção voltar ao default do SDK (apagar depois
  do upload), o passo vira no-op inofensivo com `::notice::` — não um erro;
- **`sentry-cli` vem como transitiva do `@sentry/nextjs`** (via
  `@sentry/bundler-plugin-core`) e a versão usada é a do lockfile, a mesma do
  `withSentryConfig`. Não tente "usar a versão do @sentry/nextjs": o CLI tem
  linha de versionamento própria (2.x) e `@sentry/cli@10.x` não existe. Se o
  binário sumir do `node_modules/.bin`, o passo avisa e pula em vez de buscar
  versão adivinhada;
- o `release` enviado é o **commit realmente verificado**
  (`git rev-parse HEAD`), não `github.sha` — no `workflow_call` o checkout é
  `inputs.checkout_ref` e em PR o `github.sha` é o merge commit. Source map de
  outro release não correlaciona stack trace.

#### Gate de validação de infra na CI

Novo job `infra-validate` no `ci.yml`, que roda
`scripts/observability/validar-infra.sh --estrito`. Instala `pyyaml`
(requisito do validador; sem ele o script acusa **falha**, o que é correto —
item que não pôde ser validado não é item validado) e o `ubuntu-latest` já tem
Docker, `jq` e `shellcheck`.

**A decisão consciente sobre o `--estrito`:** sem tratamento, ele reprova
para sempre por um `runbook_url` com domínio reservado `.invalid` — pendência
real que só se resolve com o endereço interno de runbook, que é decisão humana.
Um gate vermelho permanente acaba sendo ignorado, que é pior que a pendência.
Então o validador ganhou um terceiro estado, **PENDENTE DECLARADA**, e a lista
fica em `scripts/observability/pendencias-ci.txt`:

- pendência **declarada** → impressa como `[PENDENTE]`, listada no resumo, **não
  reprova** o gate;
- pendência **não declarada** → reprova o gate estrito na hora;
- chave declarada que **não ocorre mais** → **falha**, porque lista que
  envelhece em silêncio passa a esconder pendência nova.

Ambas as direções foram testadas com saída real (ver `bloco-c2-notas.md`).

#### Secrets do repositório: inventário e o que fazer quando falta um

Todos no mesmo escopo dos `VPS_*` já existentes (Settings → Environments para
os de VPS; repositório para os demais).

| Secret | Quem usa | Ausente → |
|---|---|---|
| `VPS_HOST`, `VPS_USER`, `VPS_PASSWORD`, `VPS_PORT` | todos os steps SSH | workflow falha no `with:` (`required: true`) — comportamento de sempre |
| `VPS_SSH_KEY` | `deploy.yml` (deploy + validate) | **sem efeito**: autenticação por senha, como antes |
| `VPS_HOST_FINGERPRINT` | `deploy.yml` (deploy + validate) | sem efeito, e a host key **não** é conferida (o comportamento atual) |
| `SENTRY_AUTH_TOKEN` | `ci.yml` (`frontend-build`) | upload de source map **pulado**, com `::notice::`; CI verde |
| `SENTRY_ORG`, `SENTRY_PROJECT` | `ci.yml` | com token presente e org/projeto ausente: `::warning::` e upload pulado |
| `SENTRY_URL` | `ci.yml` | sem efeito: assume o SaaS do Sentry |

Secrets que **não** são do repositório, e por quê: `DJANGO_SECRET_KEY`,
`DJANGO_DB_PASSWORD`, `BACKUP_S3_*` e o bucket ficam em `backend/.env` na VPS
(gerado uma vez pelo bootstrap do deploy); os tokens do Alloy/ Grafana Cloud
(`ALLOY_REMOTE_WRITE_TOKEN`, `ALLOY_LOKI_TOKEN`, `ALLOY_BACKEND_METRICS_TOKEN_FILE`)
ficam em `/etc/portal/alloy-<env>.env` na VPS, em 0640; e
`OBSERVABILITY_METRICS_TOKEN` precisa ser **o mesmo valor** nos três lugares
(`backend/.env`, `__OBS_TOKEN_ESPERADO__` no `http-cache.conf` instalado e o
arquivo de token do Alloy). Detalhes e ordem de instalação em
`infra/observability/README.md`.

#### Pendências que continuam abertas (não resolvidas aqui)

- **R-1 (caminho PR → VPS)**: `scripts/release/verificar-proveniencia.sh`
  continua **fora** de qualquer workflow. O risco é aceito e aberto, **não
  mitigado** e **não coberto pelo gate** por decisão da run de go-live, com
  assinatura exigida no go/no-go. Registrado aqui como fronteira, sem mudança
  de status.
- **R-2 (domínio `.com` × `.com.br`): RESOLVIDO em 2026-09-30.** A decisão
  humana foi `portal-noticias.com`, o canônico do programa. Os valores
  efetivos de `host` nos três callers (`deploy-dev`, `deploy-homolog`,
  `deploy-prod`), no `rollback.yml` e na documentação de operador foram
  corrigidos, e a checagem de consistência passou a fazer parte do portão de
  infra.
  O que **não** foi feito: confirmar que o DNS resolve. Enquanto
  `portal-noticias.com` não tiver registro A apontando para a VPS, o
  `validate` falha — porque com `tls_enabled=true` o probe é feito em
  `https://$HOST/…`. O requisito de DNS é o que bloqueia o TLS agora, não a
  configuração dos workflows.
  **Consequência operacional a saber:** as contas de teste já criadas em DEV e
  HOMOLOG têm e-mail no domínio antigo (`…@dev.portal-noticias.com.br`). Elas
  continuam válidas como login; os documentos agora descrevem o estado futuro.
  Para ter as duas, é preciso recriar as contas com `--sem-senha` depois do
  DNS — as antigas não quebram, apenas não seguem o padrão dos documentos.
- **`DJANGO_ALLOWED_HOSTS` com IP fixo** (`deploy.yml`, no `printf` do
  bootstrap de `backend/.env`): o bootstrap do
  `.env` grava `108.174.147.50` literalmente. Não foi tocado; registrar como
  pendência porque fixa um IP em arquivo de configuração gerado.
- **`DJANGO_EMAIL_BACKEND` nos três ambientes**: o bootstrap do `.env` não escreve
  a chave, então `settings.py` cai no console backend e **todo** e-mail
  transacional — verificação de cadastro, recuperação de senha, newsletter e
  alertas de critérios do B2B — sai no stdout do processo web em vez de chegar a
  um inbox. É o que faz o caminho de entrada das contas de teste
  (`usuarios_teste`) depender do log da VPS, e vale para os três ambientes,
  inclusive PROD. O backend Resend já está implementado
  (`backend/config/email_resend.py`); o que falta é a credencial
  (`RESEND_API_KEY` + remetente de domínio verificado) — `PROD_DECISOES.md`,
  item 2, e a dependência humana **HD-E** da run de go-live. Enquanto isso, o
  log do deploy avisa que o link não chega e diz onde ele sai.

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
