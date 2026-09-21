#!/bin/sh
# Roda a cada start do container `web` (docker-compose.yml). Migrations e
# collectstatic são idempotentes — reaplicar em todo restart é mais simples
# e mais confiável do que exigir um passo manual separado no deploy (fonte
# comum de "esqueci de rodar a migration em produção").
set -e

echo "[entrypoint] aplicando migrations..."
python manage.py migrate --noinput

echo "[entrypoint] coletando arquivos estáticos..."
python manage.py collectstatic --noinput

echo "[entrypoint] iniciando: $@"
exec "$@"
