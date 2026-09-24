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
| Deploy DEV | `deploy-dev.yml` | push em develop; `verify` (`ci.yml`) → SSH/PM2 3101/5101 |
| Deploy HOMOLOG | `deploy-homolog.yml` | PR para main; `verify` do head do PR → SSH/PM2 3102/5102 |
| Deploy PROD | `deploy-prod.yml` | tag `v*` + Release; `verify` do SHA da tag → SSH/PM2 3103/5103 |
| Rollback manual | `rollback.yml` | `workflow_dispatch`; `confirm` + SHA completo → mesmo `verify`/PM2/smoke, sem release |

### Dependências Python nos caminhos de execução

- `backend/requirements.txt` é o manifesto de runtime da aplicação e é o único
  arquivo de requirements copiado/instalado pela imagem Docker.
- `backend/requirements-lock.txt` é o lock de runtime, com pins transitivos; é
  instalado pelo runtime PM2 e pelo job de CI.
- `backend/requirements-dev.txt` é exclusivo de desenvolvimento/testes. Ele
  inclui `requirements.txt` e pode ser instalado no ambiente local e no runner
  do CI, mas não deve entrar na imagem ou no runtime PM2. O
  `backend/.dockerignore` mantém esse manifesto fora do contexto Docker.

Secrets exigidos (os mesmos de antes): `VPS_HOST`, `VPS_USER`, `VPS_PASSWORD`, `VPS_PORT` — vinculados a cada **GitHub Environment** (`development`/`homolog`/`production`) em Settings → Environments. O job `verify` não recebe secrets; o job de provisionamento roda com `environment: ${{ inputs.environment_name }}` (ver `.github/workflows/deploy.yml`), então só enxerga os secrets daquele Environment, com proteção de branch/tag. A configuração de regras de proteção/approvals do Environment continua sendo uma decisão humana no GitHub; o gate de CI já está no repositório.

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
