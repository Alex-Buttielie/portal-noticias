#!/bin/sh
# Deploy de UM ambiente (DEV/HOMOLOG/PROD) na VPS. Executado por
# `appleboy/ssh-action@v1.2.0` via `script_path: infra/deploy/deploy.sh`
# (o `deploy.yml` so aponta o caminho).
#
# POR QUE O SHELL SAIU DO WORKFLOW
# O script vivia dentro de um `script:` do `.github/workflows/deploy.yml`: 450
# linhas / 21.629 chars de shell num arquivo que chegou a 762 linhas / 40.966
# bytes. O GitHub passou a recusar esse arquivo ANTES de qualquer job ("Deploy
# DEV" com 0 jobs, conclusion=failure, 0 s). As sondas nao acharam o limite
# exato — cortar 16 linhas resolvia, cortar 8 nao, e as duas metades de um bloco
# falhavam isoladas, o que descarta conteudo e aponta volume — e a solucao
# escolhida nao depende do numero: o shell sai para o arquivo. O que sobra no
# `deploy.yml` e so o que o GitHub tem de fato de avaliar.
#
# POR QUE ISSO VALE MAIS QUE O TAMANHO: O SCRIPT AGORA E TESTAVEL
# As expressoes de input do GitHub (a sintaxe de chaves duplas do Actions, tipo
# `inputs.app_dir` entre `$` e `}}`) so funcionam porque o GitHub substitui a
# expressao por um valor ANTES de enviar o script. Fora do GitHub esse texto nao
# existe e nao ha quem o expanda. Por isso TODO input deste script chega por
# VARIAVEL DE AMBIENTE, montada no bloco `env:` do step do `deploy.yml` e
# exportada para a VPS pela lista `envs:` da action. Com o arquivo em disco, o
# mesmo shell roda fora do GitHub (`scripts/verificar-gate-usuarios-teste.sh`
# roda em dash, o shell da VPS). Os dois `.sh` deste diretorio NAO podem conter
# nenhuma expressao do GitHub: o `grep -c` do padrao de chaves duplas tem que
# dar 0 nos dois.
#
# MAPA input do workflow -> variavel de ambiente (step `env:` do job `deploy`)
#   app_dir              -> APP_DIR              chega pronto do ambiente
#   web_port             -> WEB_PORT             chega pronto do ambiente
#   api_port             -> API_PORT             chega pronto do ambiente
#   host                 -> HOST                 chega pronto do ambiente
#   db_name              -> DB_NAME              chega pronto do ambiente
#   db_user              -> DB_USER              chega pronto do ambiente
#   git_mode             -> GIT_MODE             chega pronto do ambiente
#   git_ref              -> GIT_REF              chega pronto do ambiente
#   verify_ref           -> VERIFY_REF           chega pronto do ambiente
#   tls_enabled          -> TLS_ENABLED          chega pronto do ambiente (a
#                                               linha seguinte normaliza caixa)
#   pr_number            -> PR_NUMBER            chega pronto do ambiente
#   allowed_hosts_extra  -> ALLOWED_HOSTS_EXTRA  chega pronto do ambiente
#   env_label            -> ENV_LABEL            lido em LABEL="$ENV_LABEL"
#   pm_suffix            -> GATE_PM_SUFFIX       lido em SUF="$GATE_PM_SUFFIX"
#   usuarios_teste       -> GATE_USUARIOS_TESTE  lido em
#                                               USUARIOS_TESTE="$GATE_USUARIOS_TESTE"
#   RESEND_API_KEY       -> secret (nao e input) chega por `envs:` da action; o
#                                               bloco do backend/.env tem o
#                                               fallback "console" para o vazio
#   environment_name     -> NAO usado por este script (o input so aparece nos
#                           campos `environment:`/`concurrency:` do proprio YAML)
#   strict_validate      -> NAO usado por este script (so o `validate.sh` le)
#
# POR QUE `GATE_` EM DOIS NOMES
# `usuarios_teste` e `pm_suffix` sao REATRIBUIDOS deste arquivo depois do
# `set -a; . ./.env` (os selos, marcados no corpo). O `.env` da VPS e um
# arquivo `chmod 600` do usuario de deploy e o `set -a` atribui ao shell
# QUALQUER chave que exista nele; se o selo lesse `USUARIOS_TESTE` ou `SUF`, um
# `USUARIOS_TESTE=true` deixado nesse arquivo religaria o gate em PROD sem
# mudanca no repositorio. Ler de um nome proprio (`GATE_*`) e o que mantem o
# lacre de pé. Isto NAO e criptografia: um `.env` que contivesse
# o harness exercita `GATE_USUARIOS_TESTE=true` no .env justamente para
# travar a regressao que foi medida com essa troca. O
# `USUARIOS_TESTE` e o `SUF` sao os dois unicos lacres do arquivo; os outros
# inputs sao lidos uma vez e chegam pelo mesmo `.env` — exposicao pre-existente
# a esta mudanca, nao introduzida aqui.
#
# SHELL: /bin/sh (dash) na VPS. Este arquivo roda em dash, e o harness nao
# aceita bash como substituto silencioso.
set -e
export NVM_DIR="$HOME/.nvm"; [ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh"; nvm use 20
# app_dir, web_port, api_port, host, db_name, db_user, git_mode, git_ref,
# verify_ref, tls_enabled, pr_number e allowed_hosts_extra chegam prontos no
# ambiente (ver o mapa no topo). env_label e pm_suffix sao lidos de
# ENV_LABEL/GATE_PM_SUFFIX porque sao religidos DEPOIS do `set -a; . ./.env`,
# que sobrescreve qualquer nome comum (ver os dois selos mais abaixo).
# ---- selo: por que um arquivo, e nao uma variavel ----
# `set -a; . ./.env` executa o .env como shell e sobrescreve QUALQUER variavel
# cujo nome apareca la. Trocar o nome (`GATE_*`) so afasta o acidente comum.
# E o furo nao era hipotetico: foi MEDIDO com `GATE_USUARIOS_TESTE=true` no
# .env e o input do workflow em `false` — o gate LIGAVA e criava 3 contas em
# PROD (teste-free@prod..., teste-premium@prod..., teste-admin@prod...).
#
# Antes da extracao o selo era um LITERAL que o GitHub substituiu no texto do
# script, e nenhum .env alcanca texto. O arquivo abaixo restaura a mesma
# imunidade: o `.env` atribui variaveis, e nao escreve arquivos. Um operator que
# deixou `GATE_USUARIOS_TESTE=true` no .env continua sem efeito; sobriaria se o
# .env tracexe codigo de proposito para gravar este caminho — o que ja e outra
# coisa, e nao e o cenario de acidente que este selo cobre.
#
# O arquivo e criado ANTES do `set -a; . ./.env` e lido DEPOIS, e apagado em
# seguida. Modo 600: o valor nao e segredo, mas nao ha motivo para deixa-lo
# legivel por outros usuarios da maquina.
ARQUIVO_SELOS="$APP_DIR/.selos-deploy"
gravar_selos() {
  {
    printf 'USUARIOS_TESTE=%s\n' "$GATE_USUARIOS_TESTE"
    printf 'PM_SUFFIX=%s\n' "$GATE_PM_SUFFIX"
  } > "$ARQUIVO_SELOS.tmp.$$" || return 1
  chmod 600 "$ARQUIVO_SELOS.tmp.$$" || return 1
  mv -f "$ARQUIVO_SELOS.tmp.$$" "$ARQUIVO_SELOS" || return 1
}
ler_selo() {
  # $1 = nome do selo. Imprime o valor, ou nada se ausente.
  [ -f "$ARQUIVO_SELOS" ] || return 0
  sed -n "s/^$1=//p" "$ARQUIVO_SELOS" 2>/dev/null | head -n 1
}
gravar_selos || { echo "ERRO: nao foi possivel gravar os selos em $ARQUIVO_SELOS"; exit 1; }

SUF="$GATE_PM_SUFFIX"; LABEL="$ENV_LABEL"
DEPLOYED_SHA_FILE="$APP_DIR/.deployed-sha"
PM2_MAX_ATTEMPTS=3
PM2_RETRY_DELAY=3
PM2_ONLINE_CHECKS=10
PM2_ONLINE_DELAY=2
PM2_ONLINE_CONFIRMATIONS=2
TLS_ENABLED=$(printf '%s' "$TLS_ENABLED" | tr '[:upper:]' '[:lower:]')
case "$TLS_ENABLED" in
  true|false) ;;
  *) echo "ERRO: tls_enabled deve ser true ou false"; exit 1 ;;
esac
USUARIOS_TESTE="$GATE_USUARIOS_TESTE"
case "$USUARIOS_TESTE" in
  true|false) ;;
  *) echo "ERRO: usuarios_teste deve ser true ou false"; exit 1 ;;
esac
case "$GIT_MODE" in
  branch|pr|tag|rollback) ;;
  *) echo "ERRO: git_mode inválido: $GIT_MODE"; exit 1 ;;
esac
if [ "$GIT_MODE" = "rollback" ] && { [ "${#VERIFY_REF}" -ne 40 ] || [ -n "$(printf '%s' "$VERIFY_REF" | tr -d '0-9a-fA-F')" ]; }; then
  echo "ERRO: rollback exige verify_ref com exatamente 40 caracteres hexadecimais"
  exit 1
fi
if [ -z "$VERIFY_REF" ]; then echo "ERRO: verify_ref obrigatório para impedir deploy de commit não verificado"; exit 1; fi
# O marker só é promovido no job validate, depois dos dois probes.
# Até lá, este valor é a referência de recuperação da VPS.
write_deployed_sha() {
  local sha="$1"
  local marker_tmp="$DEPLOYED_SHA_FILE.tmp.$$"
  if ! (umask 077; printf '%s\n' "$sha" > "$marker_tmp"); then
    rm -f -- "$marker_tmp" || true
    return 1
  fi
  if ! chmod 600 -- "$marker_tmp" || ! mv -f -- "$marker_tmp" "$DEPLOYED_SHA_FILE"; then
    rm -f -- "$marker_tmp" || true
    return 1
  fi
}
SSL_REDIRECT=false
SESSION_COOKIE_SECURE=false
CSRF_COOKIE_SECURE=false
if [ "$TLS_ENABLED" = true ]; then
  SSL_REDIRECT=true
  SESSION_COOKIE_SECURE=true
  CSRF_COOKIE_SECURE=true
fi
if [ -z "$GIT_REF" ] && [ "$GIT_MODE" != "pr" ] && [ "$GIT_MODE" != "rollback" ]; then
  echo "ERRO: git_ref obrigatório para git_mode=$GIT_MODE"; exit 1
fi
# Origens públicas via Nginx (mesma origem do navegador — ver
# infra/nginx/portal-{dev,homolog,prod}.conf): o frontend chama a
# API pelo path /api/ do próprio domínio, então não há
# mixed-content nem CORS — e o backend usa o mesmo host para CORS
# e links de e-mail. NUNCA usar http://IP:porta aqui: é bloqueado
# como mixed-content em página https e não está na allowlist de
# A origem pública acompanha o estado real do edge: não grave
# https no bundle enquanto o vhost ainda responde apenas em HTTP.
if [ "$TLS_ENABLED" = true ]; then
  API_ORIGIN="https://$HOST"; WEB_ORIGIN="https://$HOST"
else
  API_ORIGIN="http://$HOST"; WEB_ORIGIN="http://$HOST"
fi
echo "=== Deploy $LABEL portal-noticias ==="
mkdir -p /home/apps
if [ ! -d "$APP_DIR/.git" ]; then
  if [ "$GIT_MODE" = "pr" ] || [ "$GIT_MODE" = "rollback" ]; then
    git clone https://github.com/Alex-Buttielie/portal-noticias.git "$APP_DIR"
  else
    git clone -b "$GIT_REF" https://github.com/Alex-Buttielie/portal-noticias.git "$APP_DIR"
  fi
fi
cd "$APP_DIR"

# Antes de trocar o checkout, conserva o SHA que o PM2 já executava.
# O fallback para HEAD só é aceito quando pelo menos um processo do
# ambiente existe; em uma primeira instalação não há referência
# antiga e o marker só será criado após o smoke bem-sucedido.
PREVIOUS_SHA=""
if [ -f "$DEPLOYED_SHA_FILE" ]; then
  PREVIOUS_SHA="$(tr -d '[:space:]' < "$DEPLOYED_SHA_FILE" 2>/dev/null || true)"
fi
if ! printf '%s' "$PREVIOUS_SHA" | grep -Eq '^[0-9a-fA-F]{40}$'; then
  PREVIOUS_SHA=""
  if pm2 describe "portal-web-$SUF" >/dev/null 2>&1 || pm2 describe "portal-api-$SUF" >/dev/null 2>&1; then
    PREVIOUS_SHA="$(git rev-parse HEAD 2>/dev/null || true)"
  fi
fi
if printf '%s' "$PREVIOUS_SHA" | grep -Eq '^[0-9a-fA-F]{40}$'; then
  echo "PM2: SHA anterior registrado: $PREVIOUS_SHA"
  if ! write_deployed_sha "$PREVIOUS_SHA"; then
    echo "ERRO: não foi possível registrar/preservar $DEPLOYED_SHA_FILE antes do deploy"
    exit 1
  fi
else
  echo "PM2: nenhum SHA anterior encontrado; este será o primeiro marker após o smoke"
fi

if [ "$GIT_MODE" = "pr" ]; then
  # Fetch direto do ref do PR: funciona tanto para PR do mesmo
  # repo quanto de fork (origin/${head_ref} só existe no primeiro).
  git fetch origin "+refs/pull/$PR_NUMBER/head:pr-head"
  git reset --hard "$VERIFY_REF"
elif [ "$GIT_MODE" = "tag" ]; then
  git fetch --all --tags --force; git reset --hard "origin/main"; git checkout "$GIT_REF"
  # A tag e o commit do evento podem divergir se a tag for movida;
  # o reset final mantém o código igual ao testado pelo verify.
  git reset --hard "$VERIFY_REF"
elif [ "$GIT_MODE" = "rollback" ]; then
  echo "Rollback solicitado para o SHA verificado $VERIFY_REF"
  git fetch --all --tags --force
  if ! git cat-file -e "$VERIFY_REF^{commit}" 2>/dev/null; then
    if ! git fetch origin "$VERIFY_REF"; then
      echo "ERRO: SHA de rollback $VERIFY_REF não pôde ser obtido do origin"
      exit 1
    fi
  fi
  git reset --hard "$VERIFY_REF"
else
  git fetch origin
  git reset --hard "$VERIFY_REF"
fi
ACTUAL_COMMIT="$(git rev-parse HEAD)"
EXPECTED_COMMIT="$(git rev-parse "$VERIFY_REF^{commit}" 2>/dev/null || true)"
if [ -z "$EXPECTED_COMMIT" ] || [ "$ACTUAL_COMMIT" != "$EXPECTED_COMMIT" ]; then
  echo "ERRO: checkout ficou em $ACTUAL_COMMIT, mas o gate verificou $EXPECTED_COMMIT"
  exit 1
fi
if [ ! -f backend/.env ]; then
  SECRET=$(python3 -c "import secrets;print(secrets.token_urlsafe(50))")
  # O arquivo é criado uma única vez. tls_enabled=false é o
  # bootstrap seguro para uma VPS que ainda não tem certificado;
  # tls_enabled=true grava os três flags de TLS, mas nunca emite
  # o certificado — a emissão é um passo humano anterior.
  # Escreve fora do caminho final e publica por rename. Uma
  # interrupção no meio do printf nunca deixa backend/.env parcial.
  ENV_TMP="$APP_DIR/backend/.env.tmp.$$"
  (umask 077; : > "$ENV_TMP")
  # Canal de e-mail (P1-04). A chave chega por env da step (secret
  # do GitHub) e NUNCA pelo repositório. A escolha do backend é
  # derivada da chave, e não fixa:
  #  - chave presente e com formato aceitável -> backend do Resend,
  #    que de fato entrega;
  #  - chave ausente, vazia ou fora do formato esperado -> console,
  #    exatamente o estado de hoje, e o gate continua recusando
  #    cadastro (fail-closed, 503, sem 500) em vez de fingir
  #    entrega.
  # Fixar o backend do Resend com a chave vazia faria
  # `manage.py check` (rodado mais abaixo, já com este .env no
  # ambiente) importar o backend e estourar ValueError — o deploy
  # inteiro abortaria. Por isso o fallback é console, e não
  # Resend-vazio.
  #
  # A forma da chave também é filtrada, e isso não é paranoia: mais
  # adiante o deploy faz `set -a; . ./.env`, ou seja, SOURCE o
  # arquivo como shell. Uma chave com aspa ou quebra de linha
  # escreveria um .env que o shell não consegue carregar
  # ("unexpected EOF" / "command not found"), e por `set -e` isso
  # abortaria o deploy inteiro — derrubando um deploy por causa de
  # um segredo mal colado, que é exatamente o que não pode
  # acontecer. Chave fora do alfabeto esperado é tratada como
  # ausente: console + aviso, e o aviso diz o que fazer.
  RESEND_API_KEY_ENV="${RESEND_API_KEY:-}"
  case "$RESEND_API_KEY_ENV" in
    *[!A-Za-z0-9._-]*)
      echo "AVISO: RESEND_API_KEY tem formato inesperado (caractere fora de [A-Za-z0-9._-]); ignorando o valor e gravando DJANGO_EMAIL_BACKEND=console."
      RESEND_API_KEY_ENV=""
      ;;
  esac
  if [ -n "$RESEND_API_KEY_ENV" ]; then
    DJANGO_EMAIL_BACKEND="config.email_resend.ResendEmailBackend"
  else
    DJANGO_EMAIL_BACKEND="django.core.mail.backends.console.EmailBackend"
    if [ -z "${RESEND_API_KEY+x}" ] || [ -z "$RESEND_API_KEY" ]; then
      echo "AVISO: secret RESEND_API_KEY ausente/vazio; gravando DJANGO_EMAIL_BACKEND=console. O cadastro segue recusado pelo gate de e-mail (503) até a chave existir."
    fi
  fi
  if ! printf 'DJANGO_SECRET_KEY=%s\nDJANGO_DEBUG=false\nDJANGO_ALLOWED_HOSTS=%s%s,108.174.147.50,localhost,127.0.0.1\nDJANGO_SECURE_SSL_REDIRECT=%s\nDJANGO_SESSION_COOKIE_SECURE=%s\nDJANGO_CSRF_COOKIE_SECURE=%s\nDJANGO_DB_ENGINE=postgresql\nDJANGO_DB_NAME=%s\nDJANGO_DB_USER=%s\nDJANGO_DB_PASSWORD=troque-aqui\nDJANGO_DB_HOST=localhost\nDJANGO_DB_PORT=5432\nFRONTEND_BASE_URL=%s\nDJANGO_EMAIL_BACKEND=%s\nRESEND_API_KEY=%s\n' \
    "$SECRET" "$HOST" "$ALLOWED_HOSTS_EXTRA" \
    "$SSL_REDIRECT" "$SESSION_COOKIE_SECURE" "$CSRF_COOKIE_SECURE" \
    "$DB_NAME" "$DB_USER" "$WEB_ORIGIN" \
    "$DJANGO_EMAIL_BACKEND" "$RESEND_API_KEY_ENV" > "$ENV_TMP"; then
    rm -f -- "$ENV_TMP" || true
    exit 1
  fi
  if ! chmod 600 "$ENV_TMP" || ! mv -f -- "$ENV_TMP" backend/.env; then
    rm -f -- "$ENV_TMP" || true
    echo "ERRO: não foi possível publicar atomicamente backend/.env"
    exit 1
  fi
else
  # Não sobrescreve o .env nem faz downgrade automático. Se o
  # operador trocou tls_enabled, o arquivo precisa ser editado de
  # forma explícita antes do redeploy; caso contrário o deploy
  # falha antes de iniciar um processo com flags incoerentes.
  if [ "$TLS_ENABLED" = true ]; then EXPECTED_TLS=true; else EXPECTED_TLS=false; fi
  for setting in DJANGO_SECURE_SSL_REDIRECT DJANGO_SESSION_COOKIE_SECURE DJANGO_CSRF_COOKIE_SECURE; do
    if ! grep -Eq "^${setting}=${EXPECTED_TLS}$" backend/.env; then
      echo "ERRO: $setting deve ser $EXPECTED_TLS em backend/.env para tls_enabled=$TLS_ENABLED; ajuste o arquivo e redeploy"
      exit 1
    fi
  done
  # DJANGO_ALLOWED_HOSTS: aqui o arquivo NÃO é reescrito (o
  # operador pode ter ajustado à mão), então a única forma de
  # pegar um valor quebrado é validá-lo. Um host errado não é um
  # detalhe: com DEBUG=false o Django responde 400 em TODAS as
  # URLs do site inteiro, e nem o smoke deste run nem o restart
  # do PM2 ficariam sabendo disso — o deploy "passaria" com o
  # site fora.
  # Por isso a validação é dura (exit 1), no mesmo estilo dos
  # três flags de TLS acima e no mesmo ponto do script: antes de
  # qualquer npm/pip/migrate/restart, então abortar aqui NÃO
  # derruba o site — o processo anterior do PM2 continua no ar.
  # Valida formato e conteúdo; nunca corrige nem sobrescreve.
  if ! grep -q '^DJANGO_ALLOWED_HOSTS=' backend/.env; then
    echo "ERRO: DJANGO_ALLOWED_HOSTS ausente em backend/.env; sem ele o Django responde 400 em todo request. Ajuste o arquivo e redeploy"
    exit 1
  fi
  ALLOWED_HOSTS_RAW="$(sed -n 's/^DJANGO_ALLOWED_HOSTS=//p' backend/.env | head -n 1)"
  if [ -z "$ALLOWED_HOSTS_RAW" ]; then
    echo "ERRO: DJANGO_ALLOWED_HOSTS vazio em backend/.env; sem host o Django responde 400 em todo request. Ajuste o arquivo e redeploy"
    exit 1
  fi
  # Formato: lista separada por vírgula, sem esquema (://),
  # sem barra (/), sem espaço/tab e sem elemento vazio
  # (vírgula no início, no fim ou duplicada).
  if ! printf '%s' "$ALLOWED_HOSTS_RAW" | grep -Eq '^[^,[:space:]/]+(,[^,[:space:]/]+)*$'; then
    echo "ERRO: DJANGO_ALLOWED_HOSTS com formato inválido em backend/.env: '$ALLOWED_HOSTS_RAW'"
    echo "      esperado: host1,host2 (vírgula, sem https://, sem barra, sem espaço, sem vírgula vazia)"
    exit 1
  fi
  # Conteúdo: o domínio canônico deste ambiente tem de estar na
  # lista. Sem ele o vhost deste ambiente responde 400 em todas
  # as URLs; é o erro que o operador introduz ao editar à mão.
  if ! printf '%s\n' "$ALLOWED_HOSTS_RAW" | tr ',' '\n' | grep -Fxq "$HOST"; then
    echo "ERRO: DJANGO_ALLOWED_HOSTS em backend/.env não contém o domínio canônico deste ambiente ($HOST): '$ALLOWED_HOSTS_RAW'"
    echo "      sem ele o site responde 400 em todas as URLs. Ajuste o arquivo e redeploy"
    exit 1
  fi
fi
cd "$APP_DIR/frontend"
# P1-5 conservador: o build continua na VPS até existir um teste
# real do artifact standalone. O cache vive no home do usuário
# (fora do APP_DIR, preservado pelo git reset) e o heap fica
# limitado para não disputar RAM com Postgres e as 3 stacks.
export NPM_CONFIG_CACHE="$HOME/.npm"
mkdir -p "$NPM_CONFIG_CACHE"
npm ci --cache "$NPM_CONFIG_CACHE" --prefer-offline
# D-09 (solicitante, 2026-10-08): 1024 em vez de 1536. A VPS tem 3915 MB de RAM
# com os 3 ambientes + 3 stacks disputando; o kernel ja matou `npm ci` por OOM
# em 09/09, e um deploy derrubou o ambiente vizinho. Build mais lento, menos pico.
NODE_OPTIONS="--max-old-space-size=1024" \
  NEXT_PUBLIC_API_BASE_URL="$API_ORIGIN" NEXT_PUBLIC_SITE_URL="$WEB_ORIGIN" \
  API_INTERNAL_URL="http://127.0.0.1:$API_PORT" \
  npm run build
cd "$APP_DIR/backend"
python3 -m venv .venv 2>/dev/null || true
. .venv/bin/activate
# O CI instalou e validou exatamente este lock; manter o mesmo
# conjunto na VPS torna o deploy reproduzível. Atualizar uma
# dependência exige regenerar requirements-lock.txt e rodar o CI.
pip install -r requirements-lock.txt
set -a; . ./.env; set +a
if [ "${DJANGO_DB_PASSWORD:-troque-aqui}" = "troque-aqui" ]; then echo "ERRO: preencha DJANGO_DB_PASSWORD em $APP_DIR/backend/.env (Postgres da VPS — ver CI-CD.md)"; exit 1; fi
python manage.py check
python manage.py migrate
python manage.py collectstatic --noinput
# ---- selo pos-.env: o input do workflow decide o gate ----
# O set -a e o source do .env abaixo atribuem ao shell qualquer
# chave que exista no backend/.env da VPS: arquivo do usuario de
# deploy, criado uma vez e nunca sobrescrito. Como esse source roda
# DEPOIS da validacao do input e ANTES do gate ler o valor, uma
# linha USUARIOS_TESTE=true nesse arquivo ligaria o gate em PROD,
# sem alteracao de repositorio e sem aviso. Trocar o nome da
# variavel nao resolve: o .env e arbitrario quanto a nomes de chave.
# O que sobrevive e o arquivo de selos gravado no topo, antes deste
# source: o `.env` atribui variaveis, e nao escreve arquivos.
USUARIOS_TESTE="$(ler_selo USUARIOS_TESTE)"
case "$USUARIOS_TESTE" in
  true|false) ;;
  *) echo "ERRO: usuarios_teste deve ser true ou false (revalidado apos carregar $APP_DIR/backend/.env)"; exit 1 ;;
esac
SUF="$(ler_selo PM_SUFFIX)"
rm -f "$ARQUIVO_SELOS" 2>/dev/null || true
# ---- usuarios de teste: uma conta por perfil, sem senha ----
# A conta nasce sem senha utilizavel: a senha nao existe em log,
# argv, ambiente, arquivo ou banco. Quem entra e a pessoa que esta
# testando, pelo fluxo de recuperacao de senha que o produto ja tem
# (/recuperar-senha e depois /trocar-senha no primeiro login).
# O comando e idempotente: um redeploy NAO apaga a senha que
# alguem ja definiu. Fica depois do collectstatic e antes do PM2,
# com o codigo novo no disco e as migrations ja rodadas.
provisionar_usuarios_teste() {
  local papel email extra okados=0
  if [ "$USUARIOS_TESTE" != "true" ]; then
    echo "Usuarios de teste: usuarios_teste=false; nenhuma conta criada"
    return 0
  fi
  for papel in free premium admin; do
    email="teste-$papel@$SUF.portal-noticias.com.br"
    extra=""
    if [ "$papel" = "admin" ]; then
      extra="--superuser"
    fi
    if python manage.py criar_usuario_carga --email "$email" --sem-senha --papel "$papel" $extra; then
      okados=$((okados + 1))
      echo "Usuarios de teste: $email pronto (papel=$papel)"
    else
      echo "AVISO: falha ao criar/atualizar $email (papel=$papel); o deploy do codigo continua"
    fi
  done
  echo "Usuarios de teste: $okados de 3 contas prontas. Entrada: /recuperar-senha com o e-mail acima; a senha e definida por quem acessa, nao pelo deploy."
  case "${DJANGO_EMAIL_BACKEND:-django.core.mail.backends.console.EmailBackend}" in
    *console*)
      echo "  AVISO: DJANGO_EMAIL_BACKEND ausente ou console em backend/.env. O link de /recuperar-senha NAO chega em nenhum inbox: o e-mail (com uid/token, que e credencial da conta) sai no stdout do gunicorn. Leia com: pm2 logs portal-api-$SUF --lines 200 --nostream" ;;
    *)
      echo "  Entrega do e-mail de recuperacao: DJANGO_EMAIL_BACKEND=$DJANGO_EMAIL_BACKEND" ;;
  esac
  if [ "$okados" -eq 3 ]; then return 0; fi
  return 1
}
if ! provisionar_usuarios_teste; then
  echo "AVISO: provisionamento dos usuarios de teste terminou com erro; o deploy do codigo esta no ar. Crie as contas a mao com: python manage.py criar_usuario_carga --email teste-<papel>@$SUF.portal-noticias.com.br --sem-senha --papel <papel>"
fi
# PM2 faz o restart no próprio processo: não há delete seguido de
# start, portanto uma interrupção nessa janela não deixa os dois
# serviços fora do daemon. Se o processo ainda não existir, start
# é o caminho inicial. Cada comando é tentado até 3 vezes e só
# volta a deployar o próximo processo depois de confirmar `online`.
pm2_state() {
  local process_name="$1"
  local jlist_output
  if ! jlist_output="$(pm2 jlist 2>/dev/null)"; then
    echo "PM2: não foi possível consultar jlist para $process_name" >&2
    return 1
  fi
  if ! printf '%s' "$jlist_output" | python3 -c 'import json,sys; name=sys.argv[1]; data=json.load(sys.stdin); assert isinstance(data,list), "jlist root must be a list"; matches=[p for p in data if isinstance(p,dict) and p.get("name")==name]; print(((matches[0].get("pm2_env") or {}).get("status") or "unknown") if matches else "missing")' "$process_name" 2>/dev/null; then
    echo "PM2: jlist inválido ao consultar $process_name" >&2
    return 1
  fi
}

wait_for_pm2_online() {
  local process_name="$1"
  local attempt=1
  local state="unknown"
  local online_confirmations=0
  PM2_LAST_STATE="unknown"
  while [ "$attempt" -le "$PM2_ONLINE_CHECKS" ]; do
    if state="$(pm2_state "$process_name")"; then
      if [ "$state" = "online" ]; then
        online_confirmations=$((online_confirmations + 1))
        if [ "$online_confirmations" -ge "$PM2_ONLINE_CONFIRMATIONS" ]; then
          return 0
        fi
      else
        online_confirmations=0
      fi
    else
      state="jlist-error"
      online_confirmations=0
    fi
    PM2_LAST_STATE="$state"
    if [ "$attempt" -lt "$PM2_ONLINE_CHECKS" ]; then
      sleep "$PM2_ONLINE_DELAY"
    fi
    attempt=$((attempt + 1))
  done
  echo "PM2: $process_name não ficou online após $PM2_ONLINE_CHECKS verificações (último estado: $PM2_LAST_STATE)" >&2
  return 1
}

# Aplica a DEFINICAO do processo, não apenas reinicia-lo.
#
# Por que delete+start e nunca `pm2 restart`: o restart reaproveita
# os argumentos ja salvos pelo proprio PM2 e ignora os argumentos
# novos passados aqui. Efeito observado em producao (2026-09-24):
# o `--config gunicorn.conf.py` foi adicionado ao comando da API,
# mas `pm2 restart` manteve `--workers 2` sem `--config` — o conf
# NUNCA era carregado, o gunicorn ficava em workers `sync`
# (1 thread por worker) com o timeout default de 30s, e o timeout
# do `GUNICORN_TIMEOUT` (lido so pelo conf) ficava inerte. O
# objetivo do P1-3 (gthread) nao estava em vigor em nenhum
# ambiente. Confirmado via /proc/<pid>/status (Threads: 1).
#
# `delete` + `start` curto o servico, mas e o unico jeito de
# garantir que o processo suba com os args desta run. O retry e o
# wait_for_pm2_online abaixo mantem a mesma garantia de antes: so
# retorna 0 com o processo online.
restart_or_start() {
  local process_name="$1"
  shift
  local attempt=1
  local command_ok=1
  while [ "$attempt" -le "$PM2_MAX_ATTEMPTS" ]; do
    command_ok=1
    echo "PM2: tentativa $attempt/$PM2_MAX_ATTEMPTS para $process_name (delete+start)"
    pm2 delete "$process_name" >/dev/null 2>&1 || true
    if pm2 start "$@"; then
      command_ok=0
    else
      echo "PM2: start de $process_name falhou; será repetido" >&2
    fi
    if wait_for_pm2_online "$process_name"; then
      if [ "$command_ok" -eq 0 ]; then
        echo "PM2: $process_name confirmado online"
        return 0
      fi
      echo "PM2: start de $process_name falhou apesar do estado online; será repetido" >&2
    fi
    if [ "$attempt" -lt "$PM2_MAX_ATTEMPTS" ]; then
      sleep "$PM2_RETRY_DELAY"
    fi
    attempt=$((attempt + 1))
  done
  echo "ERRO: $process_name não está online após $PM2_MAX_ATTEMPTS tentativas (último estado: ${PM2_LAST_STATE:-unknown})" >&2
  if [ -n "$PREVIOUS_SHA" ]; then
    echo "Recuperação manual: rode o workflow 'Rollback manual do portal' com target_sha=$PREVIOUS_SHA; o marker antigo permanece em $DEPLOYED_SHA_FILE." >&2
  else
    echo "Recuperação manual: restaure o último checkout conhecido com o procedimento de rollback em CI-CD.md; não há marker anterior." >&2
  fi
  return 1
}
cd "$APP_DIR/frontend"
# API_INTERNAL_URL (runtime E build): e a base que o SERVIDOR usa para falar
# com a API Django, e que o route handler /api/[...path] le.
#
# NOS DOIS MOMENTOS, e isso e o ponto. MEDIDO em 2026-10-08: passar a variavel
# so no runtime (a linha do restart_or_start abaixo) NAO FUNCIONA -- o
# Next/webpack substitui `process.env.X` no bundle do servidor pelo valor
# disponivel no BUILD, e uma variavel ausente no build vira literalmente
# `undefined` dentro do bundle. Resultado medido no bundle deployed: 549
# ocorrencias do hostname publico, ZERO mencoes a API_INTERNAL_URL, e o SSR
# continuando a falhar com `getaddrinfo ENOTFOUND`. Por isso a mesma variavel
# e passada tambem na linha do `npm run build`, mais abaixo.
#
# NAO e um `rewrites` do next.config.js: esse arquivo nao tem rewrite nenhum,
# e um rewrite seria congelado no build -- que e justamente o que nao pode
# acontecer aqui, porque a porta do gunicorn muda por ambiente. O proxy mora no
# route handler para poder ler a variavel e funcionar via dominio, IP ou
# localhost sem depender do Nginx (incidente 2026-09-19: acesso direto por
# IP:porta nao passa pelo Nginx).
#
# Como nao tem o prefixo `NEXT_PUBLIC_`, o valor NAO e embutido no bundle do
# navegador: `http://127.0.0.1:$API_PORT` nao existe na maquina de quem le o
# site, e vazaria a porta interna do gunicorn.
#
# D-24 (solicitante, 2026-10-09): o `next start` le a porta da variavel PORT e,
# sem ela, sobe em 3000. MEDIDO em 2026-10-09: o env do pm2 de portal-web-dev
# tinha WEB_PORT=3101 e NAO tinha PORT — o processo subiu em 3000 e o probe web
# do validate.sh deu connection refused em 127.0.0.1:3101; todo deploy de DEV
# falhou desde 0a45c2f por isso. O WEB_PORT so e lido por este script (mapa
# input->variavel no cabecalho) — o next nunca o ve. O export abaixo e o que
# leva a porta ao processo: o pm2 herda o env do shell do deploy.
export PORT="$WEB_PORT"
restart_or_start "portal-web-$SUF" npm --name "portal-web-$SUF" -- start
cd "$APP_DIR/backend"
# Binário + args separados: pm2 não resolve string única citada
# como executável. --interpreter explícito: o binário gunicorn não
# tem extensão e o pm2 o executaria com node (SyntaxError).
# O `cd "$APP_DIR/backend"` imediatamente acima é importante:
# o PM2 captura esse cwd (pm_cwd) e, por isso, encontra o
# conf local; não dependemos só do --chdir. --config absoluto
# torna a garantia explícita mesmo se um PM2 futuro for iniciado
# de outro diretório.
# O default atual é 60s: o POST /api/admin/robos/executar/ só
# pode passar a 45s depois que o commit 202+background for
# ancestral do ref implantado (Nginx também deve ir a 45s).
# Só o bind varia por ambiente ($API_PORT).
GUNICORN_TIMEOUT=60 DJANGO_SETTINGS_MODULE=config.settings \
  restart_or_start "portal-api-$SUF" "$APP_DIR/backend/.venv/bin/gunicorn" \
  --interpreter "$APP_DIR/backend/.venv/bin/python" --name "portal-api-$SUF" -- \
  --config "$APP_DIR/backend/gunicorn.conf.py" config.wsgi:application \
  --bind "0.0.0.0:$API_PORT" --chdir "$APP_DIR/backend"
pm2 save
echo "=== $LABEL deployed $WEB_PORT(web) $API_PORT(api) ==="
