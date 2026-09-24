#!/usr/bin/env bash
# Deploy-hook do Certbot para recarregar o Nginx somente depois de nginx -t.
# O Certbot executa este script como root ao renovar um lineage.
set -Eeuo pipefail

readonly TAG='certbot-deploy-hook-nginx'

log() {
  local message="$*"
  printf '%s [%s] %s\n' "$(date --iso-8601=seconds)" "$TAG" "$message" >&2
  # O systemd/Certbot já captura stderr; logger deixa um registro persistente
  # quando o utilitário está disponível no host.
  if command -v logger >/dev/null 2>&1; then
    logger -t "$TAG" -- "$message" || true
  fi
}

log "Iniciado; lineage=${RENEWED_LINEAGE:-não informado}"

if ! command -v nginx >/dev/null 2>&1; then
  log 'ERRO: executável nginx não encontrado; nenhuma recarga foi tentada.'
  exit 1
fi

log 'Executando nginx -t antes de qualquer recarga.'
if ! nginx -t; then
  log 'ERRO: nginx -t falhou; recarga abortada para manter o Nginx atual.'
  exit 1
fi
log 'nginx -t OK.'

if command -v systemctl >/dev/null 2>&1; then
  log 'Tentando systemctl reload nginx.'
  if systemctl reload nginx; then
    log 'Recarga concluída com systemctl reload nginx.'
    exit 0
  fi
  log 'AVISO: systemctl reload nginx falhou; tentando o fallback nginx -s reload.'
else
  log 'AVISO: systemctl não encontrado; tentando o fallback nginx -s reload.'
fi

if nginx -s reload; then
  log 'Recarga concluída com nginx -s reload.'
  exit 0
fi

log 'ERRO: nginx -s reload também falhou; Nginx não foi recarregado.'
exit 1
