#!/usr/bin/env bash
# ==============================================================================
# BRD Portal de Notícias — localhost (Linux/Mac)
# Um único arquivo para subir TUDO localmente.
#
# Uso:
#   ./subir-localhost.sh              # nativo: venv + sqlite + locmem (sem Docker)
#   ./subir-localhost.sh --docker     # docker: postgres + redis + frontend standalone
#   ./subir-localhost.sh --check      # só valida (tsc + next build)
#   ./subir-localhost.sh --stop       # para containers e processos nativos
#   ./subir-localhost.sh --help
#
# Requisitos nativo: Python 3.12+, Node 20+, npm
# Requisitos docker: Docker + compose v2
# URLs: http://localhost:3000  http://localhost:8000/healthz  http://localhost:8000/admin/
#   (as portas do modo nativo são configuráveis: LOCAL_API_PORT / LOCAL_WEB_PORT.
#    O exit code é 0 só quando API e frontend responderam de verdade.)
# Logs nativos: /tmp/brd-backend.log /tmp/brd-frontend.log /tmp/brd-agendador.log (agendador de ingestão)
# Pid files: /tmp/brd-backend.pid /tmp/brd-frontend.pid /tmp/brd-agendador.pid
# Admin padrão: admin@local.test / LocalAdmin123 (ou defina LOCAL_ADMIN_EMAIL/PASSWORD)
# ==============================================================================
set -euo pipefail
cd "$(dirname "$0")"

# --- config ---
ADMIN_EMAIL="${LOCAL_ADMIN_EMAIL:-admin@local.test}"
ADMIN_PASS="${LOCAL_ADMIN_PASSWORD:-LocalAdmin123}"
BACKEND_DIR="backend"
FRONTEND_DIR="frontend"
VENV_DIR="$BACKEND_DIR/.venv"
PY="" # detectado abaixo
NPM="npm"

# Portas do modo nativo. Configuráveis porque a máquina de desenvolvimento não
# é uma máquina limpa: qualquer outro serviço que ocupe a porta (um servidor
# local de IA, um painel, outro projeto) fazia o `runserver` morrer com
# "Error: That port is already in use." — e o script seguia anunciando "Online!".
API_PORT="${LOCAL_API_PORT:-8000}"
WEB_PORT="${LOCAL_WEB_PORT:-3000}"

# --- paths de runtime (pid files/logs) ---
BACKEND_PID="/tmp/brd-backend.pid"
FRONTEND_PID="/tmp/brd-frontend.pid"
AGENDADOR_PID="/tmp/brd-agendador.pid"
AGENDADOR_LOG="/tmp/brd-agendador.log"
AGENDADOR_LOCK="/tmp/brd-agendador.lock"
# Finding 1 (code-review-contract.md): o `--stop` espera o agendador sair até
# este limite ANTES de mandar o 2º sinal (escalonamento) e, principalmente,
# antes de remover o pid file — remover antes abria a janela de duas instâncias
# concorrentes (o agendador termina a rodada em curso antes de sair).
ESPERA_PARADA_SEGUNDOS=15
# Finding 2: se o agendador não subir, o banner final não pode dizer que a
# ingestão está agendada.
AGENDADOR_FALHOU=0

# cores
if [ -t 1 ]; then
  C="\033[36m"; G="\033[32m"; Y="\033[33m"; R="\033[31m"; NC="\033[0m"
else
  C=""; G=""; Y=""; R=""; NC=""
fi
info()  { echo -e "${C}==>${NC} $*"; }
ok()    { echo -e "${G}  OK${NC} $*"; }
warn()  { echo -e "${Y}  ->${NC} $*"; }
die()   { echo -e "${R}ERRO:${NC} $*" >&2; exit 1; }

detect_python() {
  if command -v python3 >/dev/null 2>&1; then PY="python3"
  elif command -v python >/dev/null 2>&1; then PY="python"
  else die "python não encontrado no PATH. Instale Python 3.12+."; fi
  # garante que venv existe
  "$PY" -c "import sys; exit(0 if sys.version_info >= (3,12) else 1)" 2>/dev/null || warn "Python <3.12 detectado — pode funcionar, mas o recomendado é 3.12+."
}

usage() {
  cat <<EOF
BRD Portal de Notícias — localhost

Uso:
  ./subir-localhost.sh              nativo (venv + sqlite, sem Docker)
  ./subir-localhost.sh --docker     docker (postgres + redis)
  ./subir-localhost.sh --check      valida tsc + build (sem subir)
  ./subir-localhost.sh --stop       para containers/processos
  ./subir-localhost.sh --porta-pid N  mostra o pid que está escutando na porta N
  ./subir-localhost.sh --help

Portas (nativo): API $API_PORT, frontend $WEB_PORT. Se outra coisa da máquina
estiver usando a porta, o script diz quem é e PARA — não sobe pela metade. Para
escolher outras portas:

  LOCAL_API_PORT=8001 ./subir-localhost.sh
  LOCAL_API_PORT=8001 LOCAL_WEB_PORT=3002 ./subir-localhost.sh

O exit code é 0 só quando API e frontend responderam de verdade.

Admin: $ADMIN_EMAIL / ****
URLs:  http://localhost:$WEB_PORT  http://localhost:$API_PORT/healthz  http://localhost:$API_PORT/admin/
Logs:  /tmp/brd-backend.log /tmp/brd-frontend.log /tmp/brd-agendador.log
Pids:  /tmp/brd-backend.pid /tmp/brd-frontend.pid /tmp/brd-agendador.pid
EOF
}

# --- helpers ---
gen_secret() {
  "$PY" -c "import secrets; print(secrets.token_urlsafe(50))" 2>/dev/null || echo "django-insecure-localhost-only-$(date +%s)"
}

ensure_env_localhost() {
  if [ -f ".env.localhost" ]; then ok ".env.localhost ok"; return; fi
  info "Gerando .env.localhost ..."
  SECRET="$(gen_secret)"
  cat > .env.localhost <<EOF
# Gerado por subir-localhost.sh --docker em $(date -Iseconds)
DJANGO_SECRET_KEY=$SECRET
DJANGO_DEBUG=true
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1,web,frontend
DJANGO_DB_NAME=brd_portal_noticias
DJANGO_DB_USER=postgres
DJANGO_DB_PASSWORD=postgres
DJANGO_CACHE_BACKEND=redis
DJANGO_CACHE_REDIS_URL=redis://redis:6379/2
CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/1
FRONTEND_BASE_URL=http://localhost:3000
DJANGO_SECURE_SSL_REDIRECT=false
DJANGO_SESSION_COOKIE_SECURE=false
DJANGO_CSRF_COOKIE_SECURE=false
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
NEXT_PUBLIC_SITE_URL=http://localhost:3000
API_INTERNAL_URL=http://web:8000
DOMAIN_API=localhost
DOMAIN_FRONTEND=localhost
DJANGO_EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend
DJANGO_DEFAULT_FROM_EMAIL=no-reply@brdportalnoticias.local
ASSINATURA_PAYMENT_GATEWAY_PROVIDER=manual
LOCAL_ADMIN_EMAIL=$ADMIN_EMAIL
LOCAL_ADMIN_PASSWORD=$ADMIN_PASS
EOF
  ok ".env.localhost criado (postgres/redis, SECRET nova)"
}

ensure_compose_localhost() {
  if [ -f "docker-compose.localhost.yml" ]; then ok "docker-compose.localhost.yml ok"; return; fi
  info "Gerando docker-compose.localhost.yml ..."
  cat > docker-compose.localhost.yml <<'YML'
# Override localhost — mesmo docker-compose.yml de produção, sem domínio/TLS.
# Uso: docker compose -f docker-compose.yml -f docker-compose.localhost.yml --env-file .env.localhost up -d --build
services:
  web:
    # Porta já publicada pela base (docker-compose.yml) em
    # 127.0.0.1:${API_PORT:-8000}:8000 — repetir aqui duplicaria a
    # publicação da mesma porta e o `up` falharia.
    env_file: [.env.localhost]
    environment:
      DJANGO_DB_HOST: db
      DJANGO_DEBUG: "true"
      DJANGO_ALLOWED_HOSTS: "localhost,127.0.0.1,web"
      FRONTEND_BASE_URL: "http://localhost:3000"
      DJANGO_SECURE_SSL_REDIRECT: "false"
      DJANGO_SESSION_COOKIE_SECURE: "false"
      DJANGO_CSRF_COOKIE_SECURE: "false"
      CELERY_BROKER_URL: "redis://redis:6379/0"
      CELERY_RESULT_BACKEND: "redis://redis:6379/1"
      DJANGO_CACHE_REDIS_URL: "redis://redis:6379/2"
  celery-worker:
    env_file: [.env.localhost]
    environment:
      DJANGO_DB_HOST: db
      DJANGO_DEBUG: "true"
  celery-beat:
    env_file: [.env.localhost]
    environment:
      DJANGO_DB_HOST: db
      DJANGO_DEBUG: "true"
  frontend:
    # Mesmo motivo do `web` acima — já publicada pela base em
    # 127.0.0.1:${WEB_PORT:-3000}:3000.
    build:
      args:
        NEXT_PUBLIC_API_BASE_URL: "http://localhost:8000"
        NEXT_PUBLIC_SITE_URL: "http://localhost:3000"
    environment:
      API_INTERNAL_URL: "http://web:8000"
  # O serviço já nasce com profiles: ["standalone"] na base
  # (docker-compose.yml) — inativo por padrão nesta variante local.
YML
  ok "docker-compose.localhost.yml criado"
}

check_frontend_exists() {
  [ -f "frontend/app/globals.css" ] && [ -f "frontend/app/layout.tsx" ] || die "frontend futurista ausente (globals.css/layout.tsx). Rode git status."
}

# ==============================================================================
# Portas: quem está ocupando, e o que fazer a respeito
# ==============================================================================
# Descobre o pid que escuta na porta, sem depender do `ss` (whose dados de
# processo exigem privilégio em algumas máquinas) nem do `lsof` (nem sempre
# instalado). Tenta `ss`, depois `lsof`, e por fim `fuser`.
_pid_da_porta() {
  local porta="$1" pid=""
  if command -v ss >/dev/null 2>&1; then
    pid="$(ss -ltnp 2>/dev/null | awk -v p=":$porta\$" '$4 ~ p' | grep -o 'pid=[0-9]*' | head -1 | cut -d= -f2)"
    [ -n "$pid" ] && { echo "$pid"; return 0; }
  fi
  if command -v lsof >/dev/null 2>&1; then
    pid="$(lsof -ti "tcp:$porta" -sTCP:LISTEN 2>/dev/null | head -1)"
    [ -n "$pid" ] && { echo "$pid"; return 0; }
  fi
  if command -v fuser >/dev/null 2>&1; then
    pid="$(fuser -n tcp "$porta" 2>/dev/null | tr -s ' ' | awk '{print $1}')"
    [ -n "$pid" ] && { echo "$pid"; return 0; }
  fi
  echo ""
}

_descricao_do_pid() {
  local pid="$1"
  [ -n "$pid" ] || { echo "processo desconhecido"; return 0; }
  local args
  args="$(ps -p "$pid" -o args= 2>/dev/null | cut -c1-110)"
  [ -n "$args" ] || args="(sem permissão para ler a linha de comando do pid $pid)"
  # O nome do binário costuma ser mais legível que a linha inteira, e é o que
  # a pessoa precisa reconhecer para decidir o que fazer.
  local comm
  comm="$(ps -p "$pid" -o comm= 2>/dev/null | cut -c1-60)"
  echo "${comm:-$args}"
}

# Verdadeiro quando a porta está livre. Imprime o pid no stdout quando está
# ocupada (e nada quando está livre), o que evita o truque de "variável pelo
# nome": com `local nome="$2"` o callee cria um NOVO local e sombreia a
# variável do caller, então o valor nunca voltava — e a mensagem de porta
# ocupada saía com o nome do processo em branco.
porta_ocupada_por() {
  local porta="$1" pid
  pid="$(_pid_da_porta "$porta")"
  [ -n "$pid" ] || return 1
  printf '%s' "$pid"
}

# Falha ANTES de subir qualquer coisa, com o nome do culpado e a saída. Sem
# isso o Django morria com "That port is already in use." no log, o script
# continuava, e o banner dizia "Online!" — o pior desfecho possível, porque
# mente sobre o estado do ambiente.
# `permitido_reiniciar=1` significa: se o ocupante for o NOSSO processo
# (backend/frontend deste repo), ele é encerrado em vez de dar erro.
_exigir_porta_livre() {
  local porta="$1" rotulo="$2" uso="$3" permitir_reinicio="${4:-0}"
  local pid ocupante
  if ! pid="$(porta_ocupada_por "$porta")"; then
    ok "porta $porta livre ($rotulo)"
    return 0
  fi
  ocupante="$(_descricao_do_pid "$pid")"
  if [ "$permitir_reinicio" = "1" ] && _pid_e_do_script "$porta" "$pid"; then
    warn "porta $porta ocupada por $ocupante — que é deste projeto; encerrando"
    _encerrar_na_porta "$porta"
    if ! porta_ocupada_por "$porta" >/dev/null; then
      ok "porta $porta liberada ($rotulo)"
      return 0
    fi
  fi
  die "porta $porta já está em uso por: $ocupante (pid $pid)

  A $rotulo local não sobe, e isso não é um bug do projeto: outro serviço da
  máquina tomou a porta. Escolha uma das saídas:

    1. Encerrar o processo acima, se ele não estiver em uso agora:
         kill $pid          #ou feche o outro programa
    2. Subir o portal em outra porta (o frontend acompanha sozinho):
         LOCAL_API_PORT=8001 $0                      #so a API muda
         LOCAL_API_PORT=8001 LOCAL_WEB_PORT=3002 $0   # API e frontend
    3. Conferir quem está na porta:
         ss -ltnp | grep \":$porta\"

  Uso esperado da $rotulo aqui: $uso"
}

# O ocupante é um processo DESTE repositório? Sem isso, `--stop` ou a próxima
# execução matariam o serviço alheio que estiver na porta.
_pid_e_do_script() {
  local porta="$1" pid="${2:-}"
  [ -n "$pid" ] || pid="$(_pid_da_porta "$porta")"
  [ -n "$pid" ] || return 1
  local args
  args="$(ps -p "$pid" -o args= 2>/dev/null)"
  case "$args" in
    *"$PWD"*) return 0 ;;
  esac
  # `next-server` reescreve a própria linha de comando e some o caminho do
  # projeto, então ele precisa ser reconhecido pelo nome.
  case "$args" in
    next-server*|*"/next dev"*) return 0 ;;
  esac
  return 1
}

# Encerra o ocupante da porta e toda a sua árvore de processos. `kill` no pai
# sozinho não basta: `npm run dev` deixa `sh -c next dev`, `node .../next dev`
# e `next-server`, e é o último que segura a porta. Era por isso que o
# `--stop` rodava, imprimia "Pronto", e a porta continuava ocupada.
_encerrar_na_porta() {
  local porta="$1" pid
  pid="$(_pid_da_porta "$porta")"
  [ -n "$pid" ] || return 0
  local grupo
  grupo="$(ps -p "$pid" -o pgid= 2>/dev/null | tr -d ' ')"
  if [ -n "$grupo" ] && [ "$grupo" != "$$" ]; then
    kill -TERM "-$grupo" 2>/dev/null || kill -TERM "$pid" 2>/dev/null || true
  else
    kill -TERM "$pid" 2>/dev/null || true
  fi
  local i=0
  while [ "$i" -lt 10 ]; do
    porta_ocupada_por "$porta" >/dev/null || return 0
    sleep 1
    i=$((i + 1))
  done
  if [ -n "$grupo" ] && [ "$grupo" != "$$" ]; then
    kill -KILL "-$grupo" 2>/dev/null || kill -KILL "$pid" 2>/dev/null || true
  else
    kill -KILL "$pid" 2>/dev/null || true
  fi
  sleep 1
  porta_ocupada_por "$porta" >/dev/null
}

wait_http() {
  local url="$1" label="$2" tries="${3:-30}" sleep_s="${4:-2}"
  info "Aguardando $label ($url) ..."
  for _ in $(seq 1 "$tries"); do
    if curl -fsS "$url" >/dev/null 2>&1; then ok "$label OK"; return 0; fi
    sleep "$sleep_s"
  done
  warn "$label não respondeu em $((tries*sleep_s))s"
  return 1
}

# ==============================================================================
# --help / --stop / --check
# ==============================================================================

case "${1:-}" in
  --help|-h)
    usage; exit 0
    ;;
  --porta-pid)
    # Só existe para a mensagem de erro acima poder sugerir um comando
    # copiável (`kill $(./subir-localhost.sh --porta-pid 8000)`).
    _pid_da_porta "${2:?informe a porta}"
    exit 0
    ;;
  --stop)
    info "Parando containers ..."
    docker compose -f docker-compose.yml -f docker-compose.localhost.yml --env-file .env.localhost down 2>/dev/null || true
    docker compose --env-file .env.localhost down 2>/dev/null || true
    docker compose down 2>/dev/null || true
    # mata processos nativos se houver pid files
    for f in /tmp/brd-backend.pid /tmp/brd-frontend.pid; do
      if [ -f "$f" ]; then
        pid="$(cat "$f" 2>/dev/null || true)"
        if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
          kill "$pid" 2>/dev/null || true
          echo "  parado pid $pid ($f)"
        fi
        rm -f "$f"
      fi
    done
    pkill -f "manage.py runserver" 2>/dev/null || true
    # As portas primeiro, e pelo grupo de processos: matar o pid do `npm run
    # dev` deixava `sh -c next dev`, `node .../next dev` e `next-server` vivos,
    # e o último continuava segurando a porta 3000. O `--stop` imprimia "Pronto"
    # e a execução seguinte subia o frontend em 3001, sem que nada indicasse o
    # que tinha acontecido.
    #
    # Aqui o alvo é o processo NA PORTA, e só se ele for deste repositório — o
    # `pkill -f "next-server"` global de antes matava o `next dev` de qualquer
    # outro projeto na mesma máquina.
    for porta in "$WEB_PORT" "$API_PORT"; do
      # O `|| true` é obrigatório: `porta_ocupada_por` devolve 1 quando a porta
      # está livre, e sob `set -e` uma atribuição simples cujo comando
      #-substituto devolve 1 encerra o SCRIPT — o `--stop` morria logo na
      # primeira porta livre, sem dizer nada.
      pid_ocupante="$(porta_ocupada_por "$porta")" || true
      if [ -z "$pid_ocupante" ]; then
        ok "porta $porta livre"
        continue
      fi
      ocupante="$(_descricao_do_pid "$pid_ocupante")"
      if _pid_e_do_script "$porta" "$pid_ocupante"; then
        _encerrar_na_porta "$porta" && echo "  porta $porta liberada (era deste projeto: $ocupante, pid $pid_ocupante)" \
          || warn "porta $porta não liberou (era deste projeto: $ocupante, pid $pid_ocupante)"
      else
        warn "porta $porta ocupada por outro programa, deixado intacto: $ocupante (pid $pid_ocupante)"
      fi
    done
    # Varredura final por LINHA DE COMANDO, e não por porta: um `next dev`
    # que subiu numa porta diferente da configurada (porque a configurada já
    # estava ocupada) não aparece em $WEB_PORT nem em $API_PORT e sobrevivia ao
    # `--stop`. É o que deixava a porta 3001 ocupada depois de um "Pronto" que
    # dizia ter parado tudo. O filtro é o caminho DESTE repositório, então nada
    # alheio é tocado — e o `next-server` reescreve a própria linha de comando
    # e perde o caminho, o que obriga a casar pelo nome também.
    _varredura_repo() {
      local pids args_p matados=0
      # `pgrep -x next-server` NAO serve: o kernel trunca o nome do processo em
      # 15 caracteres e o nome real e "next-server (v1...", entao a igualdade
      # exata do -x nunca casa. Foi assim que o next-server da 3001 sobreviveu
      # a um --stop que dizia ter parado tudo. -f casa pela linha de comando
      # inteira, que e o que o next-server preserva.
      for pids in $(pgrep -f "$PWD/frontend/node_modules" 2>/dev/null; \
                    pgrep -f "$PWD/backend/manage.py" 2>/dev/null; \
                    pgrep -f "next-server" 2>/dev/null); do
        [ "$pids" = "$$" ] && continue
        args_p="$(ps -p "$pids" -o args= 2>/dev/null)" || true
        case "$args_p" in
          *"$PWD"*) ;;
          next-server*) ;;
          *) continue ;;
        esac
        if kill -TERM "$pids" 2>/dev/null; then matados=$((matados + 1)); fi
      done
      [ "$matados" -gt 0 ] && echo "  encerrados $matados processo(s) deste repositário fora das portas configuradas"
      return 0
    }
    _varredura_repo
    ok "Pronto. Feche as janelas/terminais se abriu manual."
    exit 0
    ;;
  --check)
    detect_python
    command -v node >/dev/null 2>&1 || die "node não no PATH. Instale Node 20+."
    check_frontend_exists
    echo "  $($PY --version 2>&1)  Node $(node --version 2>&1)"
    info "tsc --noEmit ..."
    (cd frontend && npx --yes tsc --noEmit)
    ok "tsc OK"
    info "next build (pode demorar) ..."
    (cd frontend && $NPM run build)
    ok "build OK — CHECK passou."
    exit 0
    ;;
  --docker)
    MODE="docker"
    ;;
  --native|"")
    MODE="native"
    ;;
  *)
    echo "Opção desconhecida: $1" >&2; usage; exit 1
    ;;
esac

detect_python

# ==============================================================================
# DOCKER
# ==============================================================================
if [ "$MODE" = "docker" ]; then
  echo "============================================================"
  echo " BRD Portal de Notícias — localhost [DOCKER]"
  echo " postgres + redis + frontend standalone"
  echo "============================================================"
  command -v docker >/dev/null 2>&1 || die "docker não instalado."
  docker info >/dev/null 2>&1 || die "Docker não está rodando."
  docker compose version >/dev/null 2>&1 || die "docker compose v2 requerido."
  check_frontend_exists
  ensure_env_localhost
  ensure_compose_localhost

  if [ -d "frontend/node_modules" ]; then
    info "tsc antes do build docker ..."
    (cd frontend && npx --yes tsc --noEmit) || die "tsc falhou — corrija antes do docker build."
    ok "tsc OK"
  else
    warn "frontend/node_modules ausente — pulando tsc local (será validado no build)."
  fi

  info "compose up --build ..."
  docker compose -f docker-compose.yml -f docker-compose.localhost.yml --env-file .env.localhost up -d --build || die "compose up falhou."

  wait_http "http://localhost:8000/healthz" "web :8000" 30 3 || docker compose -f docker-compose.yml -f docker-compose.localhost.yml --env-file .env.localhost logs --tail=50 web || true
  wait_http "http://localhost:3000/" "frontend :3000" 20 3 || docker compose -f docker-compose.yml -f docker-compose.localhost.yml --env-file .env.localhost logs --tail=50 frontend || true

  info "Criando admin ($ADMIN_EMAIL) ..."
  # tenta via exec direto; se falhar, copia o comando alternativo
  if ! docker compose -f docker-compose.yml -f docker-compose.localhost.yml --env-file .env.localhost exec -T web python manage.py criar_usuario_carga --email "$ADMIN_EMAIL" --password "$ADMIN_PASS" --superuser --papel admin 2>/dev/null; then
    # fallback: cria via shell se o comando não existir ainda
    docker compose -f docker-compose.yml -f docker-compose.localhost.yml --env-file .env.localhost exec -T web python -c "
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password
U=get_user_model()
u,created=U.objects.get_or_create(email='$ADMIN_EMAIL', defaults={'email':'$ADMIN_EMAIL','is_staff':True,'is_superuser':True,'is_active':True,'email_verificado':True,'papel':'admin'})
u.email='$ADMIN_EMAIL'; u.is_staff=True; u.is_superuser=True; u.is_active=True; u.email_verificado=True; u.papel='admin'
u.set_password('$ADMIN_PASS'); u.save()
print('admin ok' if u else 'fail')
" 2>/dev/null || warn "Falha ao criar admin — crie manualmente: docker compose exec web python manage.py criar_usuario_carga --email $ADMIN_EMAIL --superuser"
  fi

  docker compose -f docker-compose.yml -f docker-compose.localhost.yml --env-file .env.localhost ps
  echo ""
  echo "============================================================"
  echo " Online (docker)!"
  echo "   http://localhost:3000"
  echo "   http://localhost:8000/admin/  $ADMIN_EMAIL / $ADMIN_PASS"
  echo " Parar: ./subir-localhost.sh --stop"
  echo "============================================================"
  # tenta abrir navegador se houver xdg-open/open
  (xdg-open "http://localhost:3000" 2>/dev/null || open "http://localhost:3000" 2>/dev/null || true) &
  exit 0
fi

# ==============================================================================
# NATIVO (venv + sqlite + locmem) — sem Docker
# ==============================================================================
echo "============================================================"
echo " BRD Portal de Notícias — localhost [NATIVO]"
echo " venv + sqlite + locmem (sem Docker)"
echo "============================================================"
command -v node >/dev/null 2>&1 || die "node não no PATH. Instale Node 20+."
command -v npm >/dev/null 2>&1 || die "npm não no PATH. Reinstale Node."
check_frontend_exists
echo "  $($PY --version 2>&1)  Node $(node --version 2>&1)"
ok "frontend OK"

if [ ! -x "$VENV_DIR/bin/python" ]; then
  info "Criando $VENV_DIR ..."
  "$PY" -m venv "$VENV_DIR" || die "falha ao criar venv"
else
  ok "$VENV_DIR ok"
fi
VENV_PY="$VENV_DIR/bin/python"

info "pip install ..."
"$VENV_PY" -m pip install --upgrade pip --quiet
"$VENV_PY" -m pip install -r "$BACKEND_DIR/requirements.txt" || die "pip install falhou"

if [ ! -f "$BACKEND_DIR/.env" ]; then
  info "Gerando $BACKEND_DIR/.env ..."
  cp "$BACKEND_DIR/.env.example" "$BACKEND_DIR/.env"
  SECRET="$(gen_secret)"
  # troca SECRET, engine e debug; garante locmem
  if [ "$(uname)" = "Darwin" ]; then
    sed -i '' "s/troque-por-uma-chave-secreta-gerada/$SECRET/" "$BACKEND_DIR/.env"
    sed -i '' "s/DJANGO_DB_ENGINE=postgresql/DJANGO_DB_ENGINE=sqlite3/" "$BACKEND_DIR/.env"
    sed -i '' "s/DJANGO_DEBUG=false/DJANGO_DEBUG=true/" "$BACKEND_DIR/.env"
  else
    sed -i "s/troque-por-uma-chave-secreta-gerada/$SECRET/" "$BACKEND_DIR/.env"
    sed -i "s/DJANGO_DB_ENGINE=postgresql/DJANGO_DB_ENGINE=sqlite3/" "$BACKEND_DIR/.env"
    sed -i "s/DJANGO_DEBUG=false/DJANGO_DEBUG=true/" "$BACKEND_DIR/.env"
  fi
  if ! grep -q "DJANGO_CACHE_BACKEND" "$BACKEND_DIR/.env"; then
    echo "DJANGO_CACHE_BACKEND=locmem" >> "$BACKEND_DIR/.env"
  else
    if [ "$(uname)" = "Darwin" ]; then
      sed -i '' "s/DJANGO_CACHE_BACKEND=redis/DJANGO_CACHE_BACKEND=locmem/" "$BACKEND_DIR/.env"
    else
      sed -i "s/DJANGO_CACHE_BACKEND=redis/DJANGO_CACHE_BACKEND=locmem/" "$BACKEND_DIR/.env"
    fi
  fi
  ok "$BACKEND_DIR/.env criado (sqlite, locmem, SECRET nova)"
else
  ok "$BACKEND_DIR/.env ok"
fi

if [ ! -d "frontend/node_modules" ]; then
  info "npm install ..."
  (cd frontend && $NPM install) || die "npm install falhou"
else
  ok "frontend/node_modules ok"
fi

if [ ! -f "frontend/.env.local" ]; then
  info "Gerando frontend/.env.local ..."
  if [ -f "frontend/.env.local.example" ]; then
    cp "frontend/.env.local.example" "frontend/.env.local"
  else
    cat > frontend/.env.local <<EOF
NEXT_PUBLIC_API_BASE_URL=http://localhost:$API_PORT
NEXT_PUBLIC_SITE_URL=http://localhost:$WEB_PORT
EOF
  fi
else
  ok "frontend/.env.local ok"
fi

# `NEXT_PUBLIC_API_BASE_URL` é embutido no bundle no BUILD, então um valor
# desatualizado no arquivo não é corrigido só por reiniciar: o navegador
# continuaria chamando a porta antiga. Por isso a porta da API é reescrita
# quando (e só quando) difere da que este script vai usar.
_garantir_api_no_frontend() {
  local atual="$1"
  if [ "$atual" = "http://localhost:$API_PORT" ]; then return 0; fi
  if grep -q '^NEXT_PUBLIC_API_BASE_URL=' frontend/.env.local 2>/dev/null; then
    cp frontend/.env.local "frontend/.env.local.bak.$RANDOM"
    if [ "$(uname)" = "Darwin" ]; then
      sed -i '' "s|^NEXT_PUBLIC_API_BASE_URL=.*|NEXT_PUBLIC_API_BASE_URL=http://localhost:$API_PORT|" frontend/.env.local
    else
      sed -i "s|^NEXT_PUBLIC_API_BASE_URL=.*|NEXT_PUBLIC_API_BASE_URL=http://localhost:$API_PORT|" frontend/.env.local
    fi
    ok "frontend/.env.local: NEXT_PUBLIC_API_BASE_URL ajustada de '$atual' para http://localhost:$API_PORT (backup em frontend/.env.local.bak.*)"
  else
    printf '\nNEXT_PUBLIC_API_BASE_URL=http://localhost:%s\n' "$API_PORT" >> frontend/.env.local
    ok "frontend/.env.local: NEXT_PUBLIC_API_BASE_URL acrescentada (http://localhost:$API_PORT)"
  fi
}
_garantir_api_no_frontend "$(grep -m1 '^NEXT_PUBLIC_API_BASE_URL=' frontend/.env.local 2>/dev/null | cut -d= -f2- || true)"

# Mesma ideia para os LINKS de e-mail do Django (recuperação de senha, redefinição):
# `FRONTEND_BASE_URL` é o que `identidade/emails.py` usa para montar o link. Se o
# frontend subiu em outra porta e o backend continua mandando o link para a
# antiga, a pessoa clica e recebe uma página que não existe — e a falha só
# aparece no meio do fluxo de login, muito depois da subida.
_atualizar_variavel_env() {
  local arquivo="$1" chave="$2" valor="$3" atual backup
  atual="$(grep -m1 "^${chave}=" "$arquivo" 2>/dev/null | cut -d= -f2- || true)"
  [ "$atual" = "$valor" ] && return 0
  if grep -q "^${chave}=" "$arquivo" 2>/dev/null; then
    backup="$arquivo.bak.$RANDOM"
    cp "$arquivo" "$backup"
    if [ "$(uname)" = "Darwin" ]; then
      sed -i '' "s|^${chave}=.*|${chave}=${valor}|" "$arquivo"
    else
      sed -i "s|^${chave}=.*|${chave}=${valor}|" "$arquivo"
    fi
    ok "$(basename "$arquivo"): $chave ajustada de '${atual:-vazio}' para '$valor' (backup em $backup)"
  else
    printf '%s=%s\n' "$chave" "$valor" >> "$arquivo"
    ok "$(basename "$arquivo"): $chave acrescentada ($valor)"
  fi
}
_atualizar_variavel_env "$BACKEND_DIR/.env" "FRONTEND_BASE_URL" "http://localhost:$WEB_PORT"
_atualizar_variavel_env frontend/.env.local "NEXT_PUBLIC_SITE_URL" "http://localhost:$WEB_PORT"

info "tsc --noEmit ..."
(cd frontend && npx --yes tsc --noEmit) || die "tsc falhou"
ok "tsc OK"

info "migrate ..."
"$VENV_PY" "$BACKEND_DIR/manage.py" migrate --noinput || die "migrate falhou"

info "admin ($ADMIN_EMAIL) ..."
# tenta via management command; se falhar, cria direto via shell
if ! LOCAL_ADMIN_EMAIL="$ADMIN_EMAIL" LOCAL_ADMIN_PASSWORD="$ADMIN_PASS" "$VENV_PY" "$BACKEND_DIR/manage.py" criar_usuario_carga --email "$ADMIN_EMAIL" --password "$ADMIN_PASS" --superuser --papel admin 2>/dev/null; then
  "$VENV_PY" -c "
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings')
import pathlib, sys
sys.path.insert(0, 'backend')
os.chdir('backend')
django.setup()
from django.contrib.auth import get_user_model
U=get_user_model()
email='$ADMIN_EMAIL'
pwd='$ADMIN_PASS'
u,created=U.objects.get_or_create(email=email, defaults={'email':email,'is_staff':True,'is_superuser':True,'is_active':True,'email_verificado':True,'papel':'admin'})
u.email=email; u.is_staff=True; u.is_superuser=True; u.is_active=True; u.email_verificado=True; u.papel='admin'
u.set_password(pwd); u.save()
print(f'admin {\"criado\" if created else \"atualizado\"}: {email}')
" || warn "Falha ao criar admin — crie manualmente: $VENV_PY backend/manage.py createsuperuser"
fi

info "django check ..."
"$VENV_PY" "$BACKEND_DIR/manage.py" check || die "django check falhou"

# --- portas ANTES de subir qualquer processo ---
# A ordem aqui importa: PRIMEIRO se pergunta se já existe um serviço saudável
# na porta, e só depois se exige a porta. Na ordem inversa, um portal já no ar
# era derrubado e reiniciado a cada execução — o "já online" existia no
# código, mas ficava inalcançável porque a checagem de porta matava o processo
# antes dele ser consultado.
BACKEND_NO_AR=0
FRONTEND_NO_AR=0

if curl -fsS "http://127.0.0.1:$API_PORT/healthz" >/dev/null 2>&1; then
  ok "backend já online e saudável em :$API_PORT (reaproveitado)"
  BACKEND_NO_AR=1
else
  # É aqui que a falha aparecia e era engolida: o `runserver` morria com "That
  # port is already in use." dentro do log, o script continuava, e o banner
  # final dizia "Online!". Checar agora transforma isso em um erro que diz quem
  # está na porta e como sair.
  _exigir_porta_livre "$API_PORT" "API" "Django em http://localhost:$API_PORT" 1
fi

if curl -fsS "http://127.0.0.1:$WEB_PORT/" >/dev/null 2>&1; then
  ok "frontend já online em :$WEB_PORT (reaproveitado)"
  FRONTEND_NO_AR=1
else
  _exigir_porta_livre "$WEB_PORT" "frontend" "Next.js em http://localhost:$WEB_PORT" 1
fi

echo ""
echo "============================================================"
echo " Subindo backend + frontend ..."
echo "   Frontend: http://localhost:$WEB_PORT"
echo "   API:      http://localhost:$API_PORT/api/"
echo "   Health:   http://localhost:$API_PORT/healthz"
echo "   Admin:    http://localhost:$API_PORT/admin/  $ADMIN_EMAIL / $ADMIN_PASS"
echo "============================================================"

if [ "$BACKEND_NO_AR" = "0" ]; then
  info "backend -> background (logs: /tmp/brd-backend.log)"
  nohup "$VENV_PY" "$BACKEND_DIR/manage.py" runserver "0.0.0.0:$API_PORT" >/tmp/brd-backend.log 2>&1 &
  echo $! > /tmp/brd-backend.pid
  echo "  pid $(cat /tmp/brd-backend.pid) — tail -f /tmp/brd-backend.log"
fi

if [ "$FRONTEND_NO_AR" = "0" ]; then
  info "frontend -> background (logs: /tmp/brd-frontend.log)"
  # `API_INTERNAL_URL` é o que o proxy server-side (`app/api/[...path]/route.ts`)
  # usa para falar com o Django. Sem ele, o proxy cai no default
  # http://127.0.0.1:8000 e o frontend devolve 404 em toda chamada de API —
  # que é exatamente o HTTP 500 na home quando a API não está na porta 8000.
  # `--port` é explícito porque sem ele o Next migra sozinho para 3001 quando a
  # porta configurada está ocupada, e nada no script perceberia.
  nohup env API_INTERNAL_URL="http://127.0.0.1:$API_PORT" \
    bash -c "cd frontend && $NPM run dev -- --port $WEB_PORT" >/tmp/brd-frontend.log 2>&1 &
  echo $! > /tmp/brd-frontend.pid
  echo "  pid $(cat /tmp/brd-frontend.pid) — tail -f /tmp/brd-frontend.log"
fi

# --- agendador de ingestão (nativo não sobe Celery/Redis) ---
# Primeira rodada imediata; depois a cada CATALOGO_NOTICIAS_INTERVALO_INGESTAO_MINUTOS
# (padrão 15 min). Não sobe segunda instância: pid file + `kill -0` + validação da
# IDENTIDADE do processo (Finding 6) — tudo sob `flock` quando disponível
# (Finding 1d). O log é em APPEND (Finding 5): é a única observabilidade da
# ingestão e `>` já apagou 88 KB de histórico na Iteração 6.
if travarlock_agendador; then
  COM_LOCK=1
else
  COM_LOCK=0
  warn "flock indisponível/ocupado — a proteção de instância única do agendador fica só no pid file + identidade do processo"
fi

if [ -f "$AGENDADOR_PID" ]; then
  pid_agendador="$(cat "$AGENDADOR_PID" 2>/dev/null || true)"
  if _pid_vivo "$pid_agendador" && _pid_e_o_agendador "$pid_agendador"; then
    ok "agendador de ingestão já ativo (pid $pid_agendador — log: $AGENDADOR_LOG)"
  elif _pid_vivo "$pid_agendador"; then
    # Finding 6: pid vivo, mas não é o agendador (reciclado / outro clone).
    warn "pid $pid_agendador em $AGENDADOR_PID NÃO é o agendador ($( _pid_args "$pid_agendador" )) — tratando como órfão e removendo o pid file"
    rm -f "$AGENDADOR_PID"
  else
    warn "pid órfão em $AGENDADOR_PID — removendo"
    rm -f "$AGENDADOR_PID"
  fi
fi
if [ ! -f "$AGENDADOR_PID" ]; then
  log_offset="$(_log_bytes "$AGENDADOR_LOG")"
  info "agendador de ingestão -> background (log: $AGENDADOR_LOG)"
  # 9>&- fecha o fd do lock no filho: o agendador não pode herdar o flock,
  # senão as próximas execuções do script ficariam esperando um lock que só é
  # liberado quando o agendador morresse.
  nohup "$VENV_PY" "$BACKEND_DIR/manage.py" agendar_ingestao >>"$AGENDADOR_LOG" 2>&1 9>&- &
  echo $! > "$AGENDADOR_PID"
  # Finding 2(a): não anunciar o agendador sem provar que ele subiu. Basta o
  # processo continuar vivo E o banner "Agendador de ingestão iniciado" ter
  # apparaître no log — procurado SÓ a partir do offset anterior (o log é
  # append, então o histórico não pode satisfazer a checagem). Sem isso, um
  # `manage.py` que morre no start (ex.: settings.py quebrado) era anunciado
  # como "agendado" e a ingestão ficava parada sem ninguém saber.
  AGENDADOR_CONFIRMADO=0
  for _ in $(seq 1 10); do
    if ! _pid_vivo "$(cat "$AGENDADOR_PID" 2>/dev/null || true)"; then
      break # processo morreu no start — não vamos anunciar sucesso
    fi
    # grep sem -q: com `set -o pipefail`, o -q mata o tail com SIGPIPE e o
    # pipeline voltaria com status de falha mesmo tendo encontrado a linha.
    if tail -c "+$((log_offset + 1))" "$AGENDADOR_LOG" 2>/dev/null \
      | grep -F "Agendador de ingestão iniciado" >/dev/null 2>&1; then
      AGENDADOR_CONFIRMADO=1
      # Finding 3 (nit, 2ª passada): reconfere a vivacidade UMA vez depois de
      # achar o banner. Sem isso, um processo que morre nos microssegundos
      # seguintes ao banner (ex.: banco travado já no começo da 1ª rodada)
      # seria anunciado como "NO AR" — falso sucesso, a direção errada. Se
      # morreu aqui, cai no mesmo caminho AGENDADOR_FALHOU (banner "NÃO subiu"
      # + últimas linhas do log + aviso de ingestão PARADA).
      _pid_vivo "$(cat "$AGENDADOR_PID" 2>/dev/null || true)" || AGENDADOR_CONFIRMADO=0
      break
    fi
    sleep 1
  done
  if [ "$AGENDADOR_CONFIRMADO" = "1" ]; then
    ok "agendador de ingestão NO AR (pid $(cat "$AGENDADOR_PID")) — primeira rodada iniciada"
  else
    AGENDADOR_FALHOU=1
    warn "o agendador de ingestão NÃO subiu (pid $(cat "$AGENDADOR_PID" 2>/dev/null || echo '?')). Ultimas linhas de $AGENDADOR_LOG:"
    tail -n 15 "$AGENDADOR_LOG" 2>/dev/null | sed 's/^/      | /' || true
    warn "a ingestão está PARADA. Corrija a causa e rode de novo ./subir-localhost.sh"
  fi
fi
if [ "$COM_LOCK" = "1" ]; then
  destravarlock_agendador
fi

BACKEND_OK=1
wait_http "http://localhost:$API_PORT/healthz" "backend" 30 2 || BACKEND_OK=0
FRONTEND_OK=1
wait_http "http://localhost:$WEB_PORT/" "frontend" 30 2 || FRONTEND_OK=0

echo ""
echo "============================================================"
if [ "$BACKEND_OK" = "1" ] && [ "$FRONTEND_OK" = "1" ]; then
  echo " Online!"
  echo "   http://localhost:$WEB_PORT"
  echo "   http://localhost:$API_PORT/admin/"
# Finding 2(a): o banner não pode afirmar que a ingestão está agendada se o
# agendador não subiu (verificação logo acima, por `kill -0` + banner no log).
if [ "$AGENDADOR_FALHOU" = "1" ]; then
  echo " Ingestão: ATENÇÃO — agendador NÃO subiu; a ingestão está PARADA (veja $AGENDADOR_LOG)"
elif [ -f "$AGENDADOR_PID" ] \
  && _pid_vivo "$(cat "$AGENDADOR_PID" 2>/dev/null || true)" \
  && _pid_e_o_agendador "$(cat "$AGENDADOR_PID" 2>/dev/null || true)"; then
  echo " Ingestão: agendador em background (pid $(cat "$AGENDADOR_PID"), log $AGENDADOR_LOG)"
else
  echo " Ingestão: agendador em background (pid $(cat "$AGENDADOR_PID" 2>/dev/null || echo "?"), log $AGENDADOR_LOG) — NÃO confirmado como vivo; confira o log"
fi
  echo " Logs: tail -f /tmp/brd-backend.log /tmp/brd-frontend.log $AGENDADOR_LOG"
  echo " Parar: ./subir-localhost.sh --stop  (ou kill \$(cat /tmp/brd-*.pid))"
  echo "============================================================"
  (xdg-open "http://localhost:$WEB_PORT" 2>/dev/null || open "http://localhost:$WEB_PORT" 2>/dev/null || true) &
  (xdg-open "http://localhost:$API_PORT/admin/" 2>/dev/null || open "http://localhost:$API_PORT/admin/" 2>/dev/null || true) &
  exit 0
fi

# O caminho de erro é o que faltava. A versão anterior imprimia "Online!" e
# saía com 0 mesmo com as duas peças fora do ar — quem confiasse no exit code
# (CI, script, outra ferramenta) recebia sucesso com o ambiente quebrado. Aqui
# o banner diz o que FALHOU e o código de saída é diferente de zero.
echo " PARCIAL — o portal NÃO está todo no ar."
echo "============================================================"
[ "$BACKEND_OK" = "1" ] || {
  echo "   ✗ API (:$API_PORT) não respondeu. Últimas linhas de /tmp/brd-backend.log:"
  tail -n 12 /tmp/brd-backend.log 2>/dev/null | sed 's/^/       | /' || true
  echo "     As duas causas mais comuns: porta ocupada (o script já teria avisado"
  echo "     antes de subir) e falha no migrate/check — veja o log acima."
}
[ "$FRONTEND_OK" = "1" ] || {
  echo "   ✗ frontend (:$WEB_PORT) não respondeu. Últimas linhas de /tmp/brd-frontend.log:"
  tail -n 12 /tmp/brd-frontend.log 2>/dev/null | sed 's/^/       | /' || true
  echo "     Se o log mostrar 'Port ... is in use, trying ... instead', sobrou"
  echo "     um processo deste projeto na porta; ./subir-localhost.sh --stop resolve."
}
echo " Logs: tail -f /tmp/brd-backend.log /tmp/brd-frontend.log"
echo "============================================================"
exit 1
