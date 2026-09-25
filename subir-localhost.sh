#!/usr/bin/env bash
# ==============================================================================
# BRD Portal de Notícias — localhost (Linux/Mac)
# Um único arquivo para subir TUDO localmente.
#
# Uso:
#   ./subir-localhost.sh              # nativo: venv + sqlite + locmem (sem Docker) + agendador de ingestão
#   ./subir-localhost.sh --docker     # docker: postgres + redis + frontend standalone (ingestão via Celery Beat)
#   ./subir-localhost.sh --check      # só valida (tsc + next build)
#   ./subir-localhost.sh --stop       # para containers e processos nativos (inclui o agendador, esperando sair)
#   ./subir-localhost.sh --help
#
# Requisitos nativo: Python 3.12+, Node 20+, npm
# Requisitos docker: Docker + compose v2
# URLs: http://localhost:3000  http://localhost:8000/healthz  http://localhost:8000/admin/
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
  ./subir-localhost.sh              nativo (venv + sqlite, sem Docker; ingestão agendada em background)
  ./subir-localhost.sh --docker     docker (postgres + redis; ingestão pelo Celery Beat)
  ./subir-localhost.sh --check      valida tsc + build (sem subir)
  ./subir-localhost.sh --stop       para containers/processos
  ./subir-localhost.sh --help

Admin: $ADMIN_EMAIL / ****
URLs:  http://localhost:3000  http://localhost:8000/healthz  http://localhost:8000/admin/
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
    ports: ["8000:8000"]
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
    ports: ["3000:3000"]
    build:
      args:
        NEXT_PUBLIC_API_BASE_URL: "http://localhost:8000"
        NEXT_PUBLIC_SITE_URL: "http://localhost:3000"
    environment:
      API_INTERNAL_URL: "http://web:8000"
  caddy:
    profiles: ["prod"]
YML
  ok "docker-compose.localhost.yml criado"
}

check_frontend_exists() {
  [ -f "frontend/app/globals.css" ] && [ -f "frontend/app/layout.tsx" ] || die "frontend futurista ausente (globals.css/layout.tsx). Rode git status."
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
# Helpers do agendador de ingestão (Findings 1, 2, 5 e 6 do code-review-contract)
# ==============================================================================

# O pid existe? (não diz nada sobre QUEM é o processo — ver _pid_e_o_agendador)
_pid_vivo() {
  [ -n "${1:-}" ] && kill -0 "$1" 2>/dev/null
}

# Linha de comando completa do pid (compatível com ps do Linux e do macOS)
_pid_args() {
  ps -p "$1" -o args= 2>/dev/null || true
}

# Finding 6 (nit): um pid vivo NÃO é necessariamente o agendador — o pid pode
# ter sido reciclado, ou ser outro clone do repo na mesma máquina (o nome do pid
# file é fixo e compartilhado). Só tratamos/killamos o processo se a linha de
# comando for mesmo a do `manage.py agendar_ingestao`; caso contrário o pid file
# é tratado como órfão e removido, sem mandar signal em processo alheio.
#
# Finding 2 (nit, 2ª passada): os DOIS tokens são exigidos, nesta ordem. Casar
# só por `agendar_ingestao` é amplo demais — qualquer linha de comando que
# CONTENHA a substring passa, e a suíte desta run
# (`python -m pytest catalogo_noticias/tests/test_command_agendar_ingestao.py`)
# era classificada como "o agendador" (medido pelo reviewer): com um pid file
# obsoleto + reciclagem de pid, o `--stop` mandaria SIGTERM na suíte de testes
# do dev. Exigir `manage.py` antes de `agendar_ingestao` casa só a invocação
# real do script (`<venv>/bin/python <repo>/backend/manage.py agendar_ingestao`).
_pid_e_o_agendador() {
  case "$(_pid_args "$1")" in
    *manage.py*agendar_ingestao*) return 0 ;;
    *) return 1 ;;
  esac
}

# Finding 1(a): depois do kill, ESPERAR o processo sair (com limite de tempo)
# antes de mexer no pid file. 0 = saiu, 1 = continua vivo.
_aguardar_saida() {
  local pid="$1" limite="${2:-15}" i=0
  while [ "$i" -lt "$limite" ]; do
    _pid_vivo "$pid" || return 0
    sleep 1
    i=$((i + 1))
  done
  _pid_vivo "$pid" && return 1
  return 0
}

# Tamanho (em bytes) de um arquivo de log, para verificar só o que o processo
# que acabamos de iniciar escreveu (o log é em append e já tem histórico).
_log_bytes() {
  if [ -f "$1" ]; then wc -c < "$1" | tr -d '[:space:]'; else echo 0; fi
}

# Finding 1(d): `flock` fecha a corrida entre duas execuções do script (duas
# instâncias subindo ao mesmo tempo) e o caso "pid file apagado com processo
# vivo". É OPCIONAL de propósito: `flock` não existe no macOS por padrão
# (util-linux) e o fluxo normal não pode depender dele. Sem flock, sobram a
# espera do --stop, o escalonamento no 2º sinal e a validação de identidade.
# O fd 9 é fechado no processo filho (9>&-) para o agendador NÃO herdar o lock
# e não travar as próximas execuções do script.
AGENDADOR_LOCK_FD=9
travarlock_agendador() {
  command -v flock >/dev/null 2>&1 || return 1
  eval "exec $AGENDADOR_LOCK_FD>>\"$AGENDADOR_LOCK\"" 2>/dev/null || return 1
  if ! flock -w 10 "$AGENDADOR_LOCK_FD"; then
    eval "exec $AGENDADOR_LOCK_FD>&-" 2>/dev/null || true
    return 1
  fi
  return 0
}
destravarlock_agendador() {
  eval "exec $AGENDADOR_LOCK_FD>&-" 2>/dev/null || true
  return 0
}

# Finding 1(a)(b)(c): parada do agendador. O pid file só é removido DEPOIS que o
# processo morreu; se não morrer, o 2º sinal escala (o command encerra na hora)
# e, persistindo, o pid file é MANTIDO de propósito — é ele que impede uma 2ª
# instância — com um aviso explícito de que o processo continua vivo.
_parar_agendador() {
  if [ ! -f "$AGENDADOR_PID" ]; then
    return 0
  fi
  local pid
  pid="$(cat "$AGENDADOR_PID" 2>/dev/null || true)"
  if ! _pid_vivo "$pid"; then
    rm -f "$AGENDADOR_PID"
    return 0
  fi
  if ! _pid_e_o_agendador "$pid"; then
    warn "pid $pid em $AGENDADOR_PID não é o agendador ($( _pid_args "$pid" )) — pid reciclado/órfão: removendo o pid file sem mandar sinal"
    rm -f "$AGENDADOR_PID"
    return 0
  fi
  kill "$pid" 2>/dev/null || true
  if _aguardar_saida "$pid" "$ESPERA_PARADA_SEGUNDOS"; then
    echo "  parado pid $pid ($AGENDADOR_PID)"
    rm -f "$AGENDADOR_PID"
    return 0
  fi
  # Finding 1 (2ª passada da revisão): o aviso precisa dizer com precisão o que o
  # 2º sinal faz — NÃO é "a rodada não foi registrada, nada foi escrito": o
  # pipeline persiste POR GRUPO (@transaction.atomic em _persistir_grupo), então
  # os grupos já confirmados permanecem e nada é corrompido; o que não acontece
  # é o fechamento do RegistroExecucaoIngestao (fica com total_itens_ingeridos=0).
  warn "agendador pid $pid não saiu em ${ESPERA_PARADA_SEGUNDOS}s (rodada longa em curso) — 2º SIGTERM (escalonamento: o agendador encerra na hora e a rodada em curso é ABORTADA no meio; os grupos já confirmados permanecem, o registro da rodada não é finalizado)"
  kill "$pid" 2>/dev/null || true
  if _aguardar_saida "$pid" 5; then
    echo "  parado pid $pid ($AGENDADOR_PID) após o 2º sinal"
    rm -f "$AGENDADOR_PID"
    return 0
  fi
  warn "ATENÇÃO: agendador pid $pid continua VIVO após o 2º sinal — pid file MANTIDO de propósito (removê-lo permitiria uma 2ª instância concorrente). Para encerrar à força: kill -9 $pid"
  return 0
}

# ==============================================================================
# --help / --stop / --check
# ==============================================================================

case "${1:-}" in
  --help|-h)
    usage; exit 0
    ;;
  --stop)
    info "Parando containers ..."
    docker compose -f docker-compose.yml -f docker-compose.localhost.yml --env-file .env.localhost down 2>/dev/null || true
    docker compose --env-file .env.localhost down 2>/dev/null || true
    docker compose down 2>/dev/null || true
    # mata processos nativos se houver pid files
    # backend/frontend: comportamento pré-existente (SIGTERM best-effort + os
    # pkill genéricos logo abaixo). A espera/escalonamento é específico do
    # AGENDADOR (Finding 1): é o único que roda a ingestão e o único em que duas
    # instâncias concorrentes causam dano real.
    for f in "$BACKEND_PID" "$FRONTEND_PID"; do
      if [ -f "$f" ]; then
        pid="$(cat "$f" 2>/dev/null || true)"
        if _pid_vivo "$pid"; then
          kill "$pid" 2>/dev/null || true
          echo "  parado pid $pid ($f)"
        fi
        rm -f "$f"
      fi
    done
    # agendador de ingestão: espera a saída, escala no 2º sinal e só então
    # remove o pid file (Finding 1).
    if travarlock_agendador; then
      _parar_agendador
      destravarlock_agendador
    else
      warn "flock indisponível/ocupado — seguindo sem lock de instância única do agendador"
      _parar_agendador
    fi
    pkill -f "manage.py runserver" 2>/dev/null || true
    pkill -f "next-server" 2>/dev/null || true
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
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
NEXT_PUBLIC_SITE_URL=http://localhost:3000
EOF
  fi
else
  ok "frontend/.env.local ok"
fi

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

echo ""
echo "============================================================"
echo " Subindo backend + frontend ..."
echo "   Frontend: http://localhost:3000"
echo "   API:      http://localhost:8000/api/"
echo "   Health:   http://localhost:8000/healthz"
echo "   Admin:    http://localhost:8000/admin/  $ADMIN_EMAIL / $ADMIN_PASS"
echo "============================================================"

# --- sobe backend/frontend em background (se já online, reaproveita) ---
if curl -fsS http://127.0.0.1:8000/healthz >/dev/null 2>&1; then
  ok "backend já online em :8000"
else
  info "backend -> background (logs: /tmp/brd-backend.log)"
  nohup "$VENV_PY" "$BACKEND_DIR/manage.py" runserver 0.0.0.0:8000 >/tmp/brd-backend.log 2>&1 &
  echo $! > /tmp/brd-backend.pid
  echo "  pid $(cat /tmp/brd-backend.pid) — tail -f /tmp/brd-backend.log"
fi

if curl -fsS http://127.0.0.1:3000/ >/dev/null 2>&1; then
  ok "frontend já online em :3000"
else
  info "frontend -> background (logs: /tmp/brd-frontend.log)"
  nohup bash -c "cd frontend && $NPM run dev" >/tmp/brd-frontend.log 2>&1 &
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

wait_http "http://localhost:8000/healthz" "backend" 30 2 || warn "backend não respondeu em 60s — veja /tmp/brd-backend.log"
wait_http "http://localhost:3000/" "frontend" 30 2 || warn "frontend não respondeu em 60s — veja /tmp/brd-frontend.log"

echo ""
echo "============================================================"
echo " Online!"
echo "   http://localhost:3000"
echo "   http://localhost:8000/admin/"
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
(xdg-open "http://localhost:3000" 2>/dev/null || open "http://localhost:3000" 2>/dev/null || true) &
(xdg-open "http://localhost:8000/admin/" 2>/dev/null || open "http://localhost:8000/admin/" 2>/dev/null || true) &
