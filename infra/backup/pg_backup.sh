#!/usr/bin/env bash
# Backup diário do Postgres + mídia de usuário (ARCHITECTURE.md — nova
# arquitetura de infra, 2026-09-03). Roda NO HOST da VPS (via crontab, ver
# infra/DEPLOY.md), não dentro de um container — assim consegue chamar
# `docker compose exec` e sobrevive a qualquer problema nos próprios
# containers da aplicação.
#
# Por que backup off-VPS é obrigatório, não opcional: um volume Docker
# nomeado (postgres_data) protege contra o container cair/reiniciar, mas
# NÃO protege contra perda da VPS inteira (disco corrompido, conta
# suspensa, erro humano de `docker volume rm`). "Garantir a persistência
# dos dados" (pedido explícito da nova arquitetura) exige uma cópia fora
# da máquina que guarda o dado original.
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ENV_FILE="$PROJECT_DIR/.env.production"
BACKUP_DIR="$PROJECT_DIR/infra/backup"
TIMESTAMP="$(date +%Y%m%d-%H%M%S)"
RETENCAO_LOCAL_DIAS=7

if [ ! -f "$ENV_FILE" ]; then
    echo "[pg_backup] $ENV_FILE não encontrado — abortando." >&2
    exit 1
fi
# shellcheck disable=SC1090
set -a; source "$ENV_FILE"; set +a

mkdir -p "$BACKUP_DIR"

echo "[pg_backup] dump do Postgres..."
DUMP_FILE="$BACKUP_DIR/db-$TIMESTAMP.dump"
docker compose -f "$PROJECT_DIR/docker-compose.yml" --env-file "$ENV_FILE" \
    exec -T db pg_dump -U "${DJANGO_DB_USER:-postgres}" -Fc "${DJANGO_DB_NAME:-brd_portal_noticias}" \
    > "$DUMP_FILE"

echo "[pg_backup] arquivando mídia de usuário..."
MEDIA_FILE="$BACKUP_DIR/media-$TIMESTAMP.tar.gz"
# Copia do volume nomeado via um container descartável — mais simples e
# portável do que descobrir o caminho do volume no host (que varia por
# driver de storage do Docker).
docker run --rm \
    -v brd_portal_noticias_media_data:/media:ro \
    -v "$BACKUP_DIR:/backup" \
    alpine:3 \
    tar czf "/backup/media-$TIMESTAMP.tar.gz" -C / media

if [ -n "${BACKUP_S3_BUCKET:-}" ]; then
    echo "[pg_backup] enviando para storage remoto ($BACKUP_S3_BUCKET)..."
    export AWS_ACCESS_KEY_ID="$BACKUP_S3_ACCESS_KEY"
    export AWS_SECRET_ACCESS_KEY="$BACKUP_S3_SECRET_KEY"
    aws s3 cp "$DUMP_FILE" "s3://$BACKUP_S3_BUCKET/db/" --endpoint-url "$BACKUP_S3_ENDPOINT"
    aws s3 cp "$MEDIA_FILE" "s3://$BACKUP_S3_BUCKET/media/" --endpoint-url "$BACKUP_S3_ENDPOINT"
    # Retenção de longo prazo (ex.: 90 dias) deve ser configurada como
    # lifecycle rule NO BUCKET, não recalculada aqui a cada execução — mais
    # confiável (não depende deste script nunca falhar) e mais simples.
else
    echo "[pg_backup] AVISO: BACKUP_S3_BUCKET não configurado em .env.production —" >&2
    echo "[pg_backup] o backup ficou SÓ NA PRÓPRIA VPS, sem proteção contra perda da VPS." >&2
fi

echo "[pg_backup] removendo backups locais com mais de $RETENCAO_LOCAL_DIAS dias..."
find "$BACKUP_DIR" -maxdepth 1 -name '*.dump' -mtime "+$RETENCAO_LOCAL_DIAS" -delete
find "$BACKUP_DIR" -maxdepth 1 -name '*.tar.gz' -mtime "+$RETENCAO_LOCAL_DIAS" -delete

echo "[pg_backup] concluído: $DUMP_FILE, $MEDIA_FILE"
