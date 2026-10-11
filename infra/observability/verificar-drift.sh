#!/bin/sh
# Gate de deriva (drift) entre o que o repositório descreve e o que está de
# fato instalado/rodando na VPS, para UM ambiente (DEV/HOMOLOG/PROD).
# Executado por `appleboy/ssh-action@v1.2.0` via
# `script_path: infra/observability/verificar-drift.sh`, chamado pelo
# workflow agendado `drift-check.yml`.
#
# POR QUE ESTE SCRIPT EXISTE
# Auditoria de 2026-10-11 achou 3 bugs reais com a MESMA causa: o estado da
# VPS divergiu silenciosamente do repo, e nada detectou isso até algo
# quebrar ao vivo — `/etc/nginx/http-cache.conf` instalado há semanas sem o
# `log_format portal_acesso` que o repo já tinha (nginx -t só falhou quando
# alguém tentou usar o recurso novo), `DJANGO_ALLOWED_HOSTS` com o domínio
# `.com.br` morto por 2 semanas depois da troca pra `.com`, e um cutover
# Docker de homolog disputando porta com um workflow PM2 que ninguém lembrou
# de atualizar. Este script não corrige nada — só IMPEDE que a próxima
# divergência fique invisível até virar incidente.
#
# SAÍDA: exit 0 = sem deriva encontrada. exit 1 = deriva encontrada (lista
# cada achado em stdout antes de sair). Nunca corrige nada sozinho — drift
# é sempre uma decisão humana (reaplicar o repo? ou o repo que está
# desatualizado?).
#
# MAPA input do workflow -> variavel de ambiente
#   env_label            -> ENV_LABEL
#   app_dir              -> APP_DIR       (checkout git deste ambiente na VPS)
#   host                 -> HOST          (domínio canônico)
#   expected_runtime     -> EXPECTED_RUNTIME   "docker" | "pm2"
#   web_port             -> WEB_PORT
#   api_port             -> API_PORT
#
# SHELL: /bin/sh (dash) na VPS — mesma convenção de deploy.sh/validate.sh.
set -e

ACHADOS=0
achado() {
  echo "DRIFT: $1"
  ACHADOS=$((ACHADOS + 1))
}

echo "=== Verificação de drift: $ENV_LABEL ($HOST) ==="

# --- 1. http-cache.conf: global, compartilhado pelos 3 ambientes -----------
# Só compara uma vez (o primeiro ambiente a rodar no matrix faz a checagem;
# os outros dois reconfirmam o mesmo arquivo global, o que é redundante mas
# inofensivo e não exige coordenação entre jobs do matrix).
if [ -f /etc/nginx/http-cache.conf ] && [ -f "$APP_DIR/infra/nginx/http-cache.conf" ]; then
  INSTALADO="$(sha256sum /etc/nginx/http-cache.conf | cut -d' ' -f1)"
  ESPERADO="$(sha256sum "$APP_DIR/infra/nginx/http-cache.conf" | cut -d' ' -f1)"
  if [ "$INSTALADO" != "$ESPERADO" ]; then
    achado "http-cache.conf instalado (/etc/nginx/http-cache.conf) difere do repo em $APP_DIR/infra/nginx/http-cache.conf — reinstale com: sudo install -m 0644 $APP_DIR/infra/nginx/http-cache.conf /etc/nginx/http-cache.conf && sudo nginx -t && sudo systemctl reload nginx"
  fi
else
  echo "aviso: http-cache.conf ausente (instalado ou no repo) — pulando checagem"
fi

# --- 2. vhost Nginx: server_name tem que ser o domínio canônico ------------
# Não compara o arquivo inteiro (TLS pode ou não estar ativo, o que muda o
# conf inteiro de propósito — ver infra/DEPLOY.md §3A). Só confere que o
# vhost não ficou preso num domínio morto.
VHOST="/etc/nginx/sites-enabled/portal-$(echo "$ENV_LABEL" | tr '[:upper:]' '[:lower:]')"
if [ -f "$VHOST" ]; then
  if ! grep -q "server_name[^;]*\b$HOST\b" "$VHOST"; then
    achado "vhost $VHOST não contém '$HOST' em server_name — provavelmente preso num domínio antigo"
  fi
else
  echo "aviso: $VHOST ausente — ambiente pode estar atrás de edge diferente (Caddy/docker-edge); não é necessariamente drift"
fi

# --- 3. .env: domínio canônico tem que estar em DJANGO_ALLOWED_HOSTS -------
# O arquivo certo depende do runtime: Docker lê `.env.production` na raiz do
# app_dir (docker-compose.yml --env-file); PM2 lê `backend/.env` (deploy.sh,
# set -a; . ./.env). Um ambiente Docker pode ter um `backend/.env` ÓRFÃO,
# sobra da era PM2 antes do cutover — checar o arquivo errado produz falso
# positivo (achado real desta auditoria: dev tem os dois, só o
# `.env.production` é lido de verdade).
case "$EXPECTED_RUNTIME" in
  docker) ENV_FILE="$APP_DIR/.env.production" ;;
  *) ENV_FILE="$APP_DIR/backend/.env" ;;
esac
if [ -f "$ENV_FILE" ]; then
  if ! sed -n 's/^DJANGO_ALLOWED_HOSTS=//p' "$ENV_FILE" | tr ',' '\n' | grep -Fxq "$HOST"; then
    achado "$ENV_FILE: DJANGO_ALLOWED_HOSTS não contém o domínio canônico ($HOST)"
  fi
else
  echo "aviso: $ENV_FILE ausente — ambiente pode não estar provisionado ainda"
fi

# --- 4. dono real das portas tem que bater com o runtime esperado ----------
# Ex.: homolog cutover pra Docker e o workflow PM2 ainda rodar por engano
# deixaria o PM2 disputando a porta com o container — achado real desta
# auditoria (2026-10-11).
dono_da_porta() {
  port="$1"
  ss -tlnp 2>/dev/null | grep ":$port " | head -1
}
checar_porta() {
  port="$1"
  linha="$(dono_da_porta "$port")"
  if [ -z "$linha" ]; then
    achado "porta $port ($ENV_LABEL) não tem nenhum processo escutando"
    return
  fi
  case "$EXPECTED_RUNTIME" in
    docker)
      if ! echo "$linha" | grep -q docker-proxy; then
        achado "porta $port ($ENV_LABEL) esperava docker-proxy (runtime=docker) mas tem: $linha"
      fi
      ;;
    pm2)
      if echo "$linha" | grep -q docker-proxy; then
        achado "porta $port ($ENV_LABEL) esperava um processo PM2 (runtime=pm2) mas tem docker-proxy — Docker roubou a porta do PM2 ou vice-versa"
      fi
      ;;
    *)
      echo "aviso: EXPECTED_RUNTIME='$EXPECTED_RUNTIME' desconhecido — pulando checagem de porta"
      ;;
  esac
  # Bind público (0.0.0.0/*) num processo que não é o Nginx/docker-proxy é
  # sempre errado, qualquer que seja o runtime — achado real desta auditoria.
  if echo "$linha" | grep -qE '^\S+\s+\S+\s+\S+\s+(\*|0\.0\.0\.0):' && ! echo "$linha" | grep -qE 'nginx|docker-proxy'; then
    achado "porta $port ($ENV_LABEL) bindada publicamente (0.0.0.0/*) por um processo que não é Nginx/docker-proxy: $linha"
  fi
}
checar_porta "$WEB_PORT"
checar_porta "$API_PORT"

echo "=== $ACHADOS achado(s) de drift em $ENV_LABEL ==="
if [ "$ACHADOS" -gt 0 ]; then
  exit 1
fi
exit 0
