# Runbook de restore

Backup sem teste de restore não é backup — é uma esperança. Rode este
procedimento pelo menos uma vez após o primeiro deploy (num ambiente de
staging ou numa cópia local) para confirmar que ele realmente funciona
antes de precisar dele de verdade.

## Restaurar o banco de dados

```bash
# 1. Copie o .dump desejado (local ou baixado do storage remoto) para
#    infra/backup/restore.dump

# 2. Suba só o serviço de banco, se ainda não estiver rodando
docker compose --env-file .env.production up -d db

# 3. Restaura para dentro do container (recria o banco do zero — ATENÇÃO:
#    isto apaga o conteúdo atual do banco de destino)
cat infra/backup/restore.dump | docker compose --env-file .env.production \
    exec -T db pg_restore -U "$DJANGO_DB_USER" -d "$DJANGO_DB_NAME" \
    --clean --if-exists --no-owner

# 4. Suba o resto da stack
docker compose --env-file .env.production up -d
```

## Restaurar mídia de usuário

```bash
docker run --rm \
    -v brd_portal_noticias_media_data:/media \
    -v "$(pwd)/infra/backup:/backup" \
    alpine:3 \
    sh -c "rm -rf /media/* && tar xzf /backup/restore-media.tar.gz -C / "
```

## Baixar backup do storage remoto (Backblaze B2 / Cloudflare R2)

```bash
export AWS_ACCESS_KEY_ID=... AWS_SECRET_ACCESS_KEY=...
aws s3 cp s3://$BACKUP_S3_BUCKET/db/db-AAAAMMDD-HHMMSS.dump infra/backup/restore.dump \
    --endpoint-url $BACKUP_S3_ENDPOINT
```

## RPO/RTO assumidos nesta arquitetura

- **RPO (perda de dados aceitável):** até 24h — backup roda 1x/dia via cron
  (ver `infra/DEPLOY.md`). Se isso for insuficiente quando o produto tiver
  usuários pagantes reais, aumentar a frequência do cron (ex.: a cada 6h) é
  uma mudança de uma linha, sem alteração de arquitetura.
- **RTO (tempo para religar o serviço):** o gargalo é o tamanho do dump
  baixado, não o restore em si — Postgres restaura rápido para o volume de
  dados esperado no MVP/beta.
