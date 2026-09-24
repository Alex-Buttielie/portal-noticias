#!/usr/bin/env bash
# Backup nativo da topologia ATIVA da VPS (PostgreSQL do host + PM2/Nginx).
# NÃO use este script na variante Docker; para Docker/Caddy, use pg_backup.sh.
#
# Instalação na VPS PM2:
#   0 3 * * * BACKUP_ENV_FILE=/home/apps/portal-prod/backend/.env /home/apps/portal-prod/infra/backup/pg_backup_pm2.sh >> /var/log/pg_backup.log 2>&1
#
# O env padrão é <checkout>/backend/.env, que é o arquivo criado/preservado
# pelo deploy PM2. O fallback <checkout>/.env e as variáveis PG* também são
# aceitos. O path da mídia é <checkout>/backend/media (MEDIA_ROOT no Django).
#
# BACKUP_VALIDATE_RESTORE=0 é um escape de emergência: nesse caso o archive
# ainda é lido integralmente por pg_restore, mas o restore em banco descartável
# e a contagem de linhas ficam desligados. O padrão é 1; desligar a validação
# exige registrar explicitamente o risco no log.
set -euo pipefail
umask 077

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
BACKUP_DIR="${BACKUP_DIR:-$SCRIPT_DIR}"
MEDIA_DIR="${BACKUP_MEDIA_DIR:-$PROJECT_DIR/backend/media}"
RETENCAO_LOCAL_DIAS=7

DUMP_TMP=""
MEDIA_TMP=""
VALIDATION_DB=""
VALIDATION_DB_CREATED=0
DB_HOST=""
DB_PORT=""
DB_USER=""

log() {
    printf '[pg_backup_pm2] %s\n' "$*"
}

erro() {
    printf '[pg_backup_pm2] ERRO: %s\n' "$*" >&2
}

# A validação cria um banco no mesmo cluster. Em qualquer saída — inclusive
# interrupção — tenta descartá-lo; nunca deixa o dump ser publicado antes de
# a contagem de linhas passar.
drop_validation_db() {
    if [[ "$VALIDATION_DB_CREATED" != "1" ]]; then
        return 0
    fi
    if dropdb "${PG_CONNECTION_ARGS[@]}" --if-exists --no-password "$VALIDATION_DB" >/dev/null 2>&1; then
        log "banco descartável de validação removido: $VALIDATION_DB"
        VALIDATION_DB_CREATED=0
    else
        log "AVISO: não foi possível remover o banco descartável $VALIDATION_DB; uma segunda tentativa ocorrerá no cleanup"
    fi
}

cleanup() {
    local status=$?
    trap - EXIT
    drop_validation_db || true
    if [[ -n "$DUMP_TMP" ]]; then
        rm -f -- "$DUMP_TMP" || true
    fi
    if [[ -n "$MEDIA_TMP" ]]; then
        rm -f -- "$MEDIA_TMP" || true
    fi
    if (( status != 0 )); then
        printf '[pg_backup_pm2] FALHA (exit %d); nenhum temporário foi propagado.\n' "$status" >&2
    fi
    exit "$status"
}
trap cleanup EXIT

# Dependências comuns. As ferramentas de restore/psql são exigidas somente
# quando BACKUP_VALIDATE_RESTORE está ligado (o escape de emergência continua
# utilizável em uma máquina sem CREATEDB, mas ainda faz leitura integral).
for comando in pg_dump pg_restore tar flock find stat id; do
    if ! command -v "$comando" >/dev/null 2>&1; then
        erro "dependência obrigatória ausente: $comando"
        exit 127
    fi
done

# Um env explícito sempre precisa existir. Sem BACKUP_ENV_FILE, prefere o
# arquivo real do deploy PM2 e aceita o .env da raiz como compatibilidade.
ENV_FILE="${BACKUP_ENV_FILE:-}"
if [[ -z "$ENV_FILE" ]]; then
    if [[ -f "$PROJECT_DIR/backend/.env" ]]; then
        ENV_FILE="$PROJECT_DIR/backend/.env"
    elif [[ -f "$PROJECT_DIR/.env" ]]; then
        ENV_FILE="$PROJECT_DIR/.env"
    fi
elif [[ ! -f "$ENV_FILE" ]]; then
    erro "BACKUP_ENV_FILE não existe: $ENV_FILE"
    exit 1
fi

if [[ -n "$ENV_FILE" ]]; then
    # Preserva PG* e BACKUP_S3_* explicitamente exportadas pelo processo/cron:
    # o env file é um fallback e não deve sobrescrever uma configuração externa
    # com uma linha vazia (por exemplo, um .env.example copiado sem valores).
    ENV_PGDATABASE="${PGDATABASE:-}"
    ENV_PGUSER="${PGUSER:-}"
    ENV_PGPASSWORD="${PGPASSWORD:-}"
    ENV_PGHOST="${PGHOST:-}"
    ENV_PGPORT="${PGPORT:-}"
    ENV_BACKUP_S3_ENDPOINT="${BACKUP_S3_ENDPOINT-}"
    ENV_BACKUP_S3_BUCKET="${BACKUP_S3_BUCKET-}"
    ENV_BACKUP_S3_ACCESS_KEY="${BACKUP_S3_ACCESS_KEY-}"
    ENV_BACKUP_S3_SECRET_KEY="${BACKUP_S3_SECRET_KEY-}"
    ENV_BACKUP_VALIDATE_RESTORE="${BACKUP_VALIDATE_RESTORE-}"

    log "carregando credenciais de $ENV_FILE"
    set -a
    # O arquivo é mantido pelo mesmo usuário do deploy e deve ter modo 600.
    # shellcheck disable=SC1090
    source "$ENV_FILE"
    set +a

    [[ -z "$ENV_PGDATABASE" ]] || PGDATABASE="$ENV_PGDATABASE"
    [[ -z "$ENV_PGUSER" ]] || PGUSER="$ENV_PGUSER"
    [[ -z "$ENV_PGPASSWORD" ]] || PGPASSWORD="$ENV_PGPASSWORD"
    [[ -z "$ENV_PGHOST" ]] || PGHOST="$ENV_PGHOST"
    [[ -z "$ENV_PGPORT" ]] || PGPORT="$ENV_PGPORT"
    [[ -z "$ENV_BACKUP_S3_ENDPOINT" ]] || BACKUP_S3_ENDPOINT="$ENV_BACKUP_S3_ENDPOINT"
    [[ -z "$ENV_BACKUP_S3_BUCKET" ]] || BACKUP_S3_BUCKET="$ENV_BACKUP_S3_BUCKET"
    [[ -z "$ENV_BACKUP_S3_ACCESS_KEY" ]] || BACKUP_S3_ACCESS_KEY="$ENV_BACKUP_S3_ACCESS_KEY"
    [[ -z "$ENV_BACKUP_S3_SECRET_KEY" ]] || BACKUP_S3_SECRET_KEY="$ENV_BACKUP_S3_SECRET_KEY"
    [[ -z "$ENV_BACKUP_VALIDATE_RESTORE" ]] || BACKUP_VALIDATE_RESTORE="$ENV_BACKUP_VALIDATE_RESTORE"
fi

# Variáveis PG* têm precedência sobre os aliases Django quando ambas estão
# definidas. PGPASSWORD é exportado apenas no processo deste backup e nunca é
# impresso.
DB_NAME="${PGDATABASE:-${DJANGO_DB_NAME:-}}"
DB_USER="${PGUSER:-${DJANGO_DB_USER:-}}"
DB_PASSWORD="${PGPASSWORD:-${DJANGO_DB_PASSWORD:-}}"
DB_HOST="${PGHOST:-${DJANGO_DB_HOST:-localhost}}"
DB_PORT="${PGPORT:-${DJANGO_DB_PORT:-5432}}"

if [[ -z "$DB_NAME" || -z "$DB_USER" || -z "$DB_PASSWORD" || -z "$DB_HOST" || -z "$DB_PORT" ]]; then
    erro "credenciais incompletas; defina PGDATABASE/PGUSER/PGPASSWORD/PGHOST/PGPORT ou DJANGO_DB_NAME/DJANGO_DB_USER/DJANGO_DB_PASSWORD/DJANGO_DB_HOST/DJANGO_DB_PORT"
    exit 2
fi
if [[ "$DB_PASSWORD" == "troque-aqui" ]]; then
    erro "DJANGO_DB_PASSWORD ainda contém o placeholder 'troque-aqui'"
    exit 2
fi

VALIDATE_RESTORE="${BACKUP_VALIDATE_RESTORE:-1}"
VALIDATE_RESTORE="$(printf '%s' "$VALIDATE_RESTORE" | tr '[:upper:]' '[:lower:]')"
case "$VALIDATE_RESTORE" in
    1|true) VALIDATE_RESTORE_ENABLED=1 ;;
    0|false) VALIDATE_RESTORE_ENABLED=0 ;;
    *)
        erro "BACKUP_VALIDATE_RESTORE deve ser 1/true (padrão) ou 0/false"
        exit 2
        ;;
esac
if (( VALIDATE_RESTORE_ENABLED )); then
    for comando in psql createdb dropdb; do
        if ! command -v "$comando" >/dev/null 2>&1; then
            erro "BACKUP_VALIDATE_RESTORE=1 exige a dependência: $comando"
            exit 127
        fi
    done
fi

# A configuração S3 é fail-closed quando está parcial. Credenciais sem bucket
# e endpoint/chave sem bucket não podem ser confundidas com "sem storage" e
# cair silenciosamente no modo local-only.
S3_BUCKET="${BACKUP_S3_BUCKET:-}"
S3_ENDPOINT="${BACKUP_S3_ENDPOINT:-}"
S3_ACCESS_KEY="${BACKUP_S3_ACCESS_KEY:-}"
S3_SECRET_KEY="${BACKUP_S3_SECRET_KEY:-}"
S3_REMOTE_ENABLED=0
AWS_CMD=()

if [[ -n "$S3_BUCKET" ]]; then
    S3_REMOTE_ENABLED=1
    if [[ -n "$S3_ACCESS_KEY" || -n "$S3_SECRET_KEY" ]]; then
        if [[ -z "$S3_ACCESS_KEY" || -z "$S3_SECRET_KEY" ]]; then
            erro "BACKUP_S3_ACCESS_KEY e BACKUP_S3_SECRET_KEY devem ser definidas em conjunto"
            exit 12
        fi
    fi
    if ! command -v aws >/dev/null 2>&1; then
        erro "BACKUP_S3_BUCKET está configurado, mas a AWS CLI não está instalada"
        exit 10
    fi
    AWS_CMD=(aws)
    if [[ -n "$S3_ENDPOINT" ]]; then
        AWS_CMD+=(--endpoint-url "$S3_ENDPOINT")
    fi
    if [[ -n "$S3_ACCESS_KEY" ]]; then
        export AWS_ACCESS_KEY_ID="$S3_ACCESS_KEY"
        export AWS_SECRET_ACCESS_KEY="$S3_SECRET_KEY"
    elif [[ -n "${AWS_ACCESS_KEY_ID:-}" && -n "${AWS_SECRET_ACCESS_KEY:-}" ]]; then
        log "usando credenciais AWS já presentes no ambiente"
    elif ! "${AWS_CMD[@]}" sts get-caller-identity --output json >/dev/null 2>&1; then
        erro "BACKUP_S3_BUCKET está configurado sem credenciais explícitas e a cadeia IAM/AWS CLI não foi validada; retenção e upload permanecem bloqueados"
        exit 13
    fi
elif [[ -n "$S3_ENDPOINT" || -n "$S3_ACCESS_KEY" || -n "$S3_SECRET_KEY" ]]; then
    erro "configuração S3 parcial: BACKUP_S3_BUCKET está vazio, mas endpoint/chave foram definidos"
    exit 12
fi

if [[ ! -d "$MEDIA_DIR" ]]; then
    erro "MEDIA_ROOT não existe: $MEDIA_DIR (ajuste BACKUP_MEDIA_DIR somente se o layout da VPS mudar)"
    exit 1
fi

mkdir -p -- "$BACKUP_DIR"

# Check informativo, não destrutivo: o contexto do cron deve ser o mesmo
# usuário do PM2. O shell pode continuar para que a mensagem ajude a corrigir
# a instalação, mas a incapacidade real de ler/escrever falhará na operação.
check_runtime_permissions() {
    local uid path owner mode
    uid="$(id -u)"
    log "contexto de execução: uid=$uid usuário=$(id -un 2>/dev/null || printf desconhecido)"
    for path in "$BACKUP_DIR" "$MEDIA_DIR"; do
        if ! read -r owner mode < <(stat -c '%u %a' "$path" 2>/dev/null); then
            log "AVISO: não foi possível ler owner/mode de $path"
            continue
        fi
        if [[ "$owner" != "$uid" ]]; then
            log "AVISO: $path pertence ao uid $owner (modo $mode), mas o cron está no uid $uid"
        fi
        if [[ ! -r "$path" ]]; then
            log "AVISO: o usuário efetivo não consegue ler $path"
        fi
        if [[ ! -w "$path" ]]; then
            log "AVISO: o usuário efetivo não consegue escrever $path"
        fi
    done
    if [[ -n "$ENV_FILE" && -e "$ENV_FILE" && ! -r "$ENV_FILE" ]]; then
        log "AVISO: o usuário efetivo não consegue ler o env file $ENV_FILE"
    fi
}
check_runtime_permissions

# Impede dois cron jobs simultâneos de copiárem/apagarem o mesmo conjunto. A
# execução permanece reentrante: um rerun após término cria outro par validado.
exec {LOCK_FD}>"$BACKUP_DIR/.pg_backup_pm2.lock"
if ! flock -n "$LOCK_FD"; then
    erro "outro backup PM2 já está em execução; esta chamada foi cancelada"
    exit 3
fi

TIMESTAMP="$(date -u +%Y%m%dT%H%M%SZ)"
DUMP_FILE="$BACKUP_DIR/pm2-db-$TIMESTAMP.dump"
MEDIA_FILE="$BACKUP_DIR/pm2-media-$TIMESTAMP.tar.gz"
DUMP_TMP="$BACKUP_DIR/.pm2-db-$TIMESTAMP.dump.$$"
MEDIA_TMP="$BACKUP_DIR/.pm2-media-$TIMESTAMP.tar.gz.$$"
VALIDATION_DB="backup_validate_${TIMESTAMP}_$$"

export PGPASSWORD="$DB_PASSWORD"
export PGCONNECT_TIMEOUT="${PGCONNECT_TIMEOUT:-10}"
PG_CONNECTION_ARGS=(--host="$DB_HOST" --port="$DB_PORT" --username="$DB_USER")

# Conta todas as tabelas de usuário e todas as linhas antes e depois do restore.
# query_to_xml permite montar SELECT count(*) com quoting seguro para schemas e
# tabelas com nomes incomuns; o resultado é apenas "tabelas|linhas".
DATABASE_COUNT_SQL="$(
    cat <<'SQL'
WITH user_tables AS (
    SELECT n.nspname AS schema_name, c.relname AS table_name
    FROM pg_catalog.pg_class AS c
    JOIN pg_catalog.pg_namespace AS n ON n.oid = c.relnamespace
    WHERE c.relkind IN ('r', 'p')
      AND n.nspname NOT IN ('pg_catalog', 'information_schema')
      AND n.nspname !~ '^pg_toast'
), counts AS (
    SELECT COALESCE(
        (xpath(
            '/row/c/text()',
            query_to_xml(
                format('SELECT count(*) AS c FROM %I.%I', schema_name, table_name),
                false, true, ''
            )
        ))[1]::text,
        '0'
    )::bigint AS row_count
    FROM user_tables
)
SELECT (SELECT count(*) FROM user_tables), COALESCE(sum(row_count), 0)
FROM counts;
SQL
)"

database_counts() {
    local db_name="$1"
    local result
    if ! result="$(psql "${PG_CONNECTION_ARGS[@]}" --no-password --no-psqlrc --quiet \
        --tuples-only --no-align --field-separator='|' --set=ON_ERROR_STOP=1 \
        --dbname="$db_name" --command="$DATABASE_COUNT_SQL")"; then
        erro "não foi possível contar tabelas/linhas no banco $db_name"
        return 1
    fi
    result="${result//$'\r'/}"
    result="${result//$'\n'/}"
    if [[ ! "$result" =~ ^[0-9]+\|[0-9]+$ ]]; then
        erro "contagem de tabelas/linhas inválida para $db_name: $result"
        return 1
    fi
    printf '%s' "$result"
}

log "gerando dump PostgreSQL nativo (host=$DB_HOST, porta=$DB_PORT, banco=$DB_NAME, usuário=$DB_USER)"
if ! pg_dump \
    "${PG_CONNECTION_ARGS[@]}" \
    --dbname="$DB_NAME" \
    -Fc \
    --no-password \
    --file="$DUMP_TMP"; then
    erro "pg_dump falhou; nenhum dump final foi publicado"
    exit 4
fi

if [[ ! -s "$DUMP_TMP" ]]; then
    erro "pg_dump produziu um arquivo vazio: $DUMP_TMP"
    exit 5
fi
# --list continua sendo uma checagem rápida da TOC, mas não é aceito sozinho:
# archives truncados podem passar nessa etapa.
if ! pg_restore --list "$DUMP_TMP" >/dev/null; then
    erro "pg_restore --list rejeitou o custom dump; arquivo inválido descartado"
    exit 6
fi

if (( VALIDATE_RESTORE_ENABLED )); then
    log "validando integridade: restore completo em banco descartável + contagem de linhas"
    if ! SOURCE_COUNTS="$(database_counts "$DB_NAME")"; then
        erro "a contagem do banco de origem falhou; dump não será publicado"
        exit 7
    fi
    if ! createdb "${PG_CONNECTION_ARGS[@]}" --no-password -T template0 "$VALIDATION_DB"; then
        erro "não foi possível criar o banco descartável para validar o restore; o dump não será publicado (permissão CREATEDB é necessária)"
        exit 8
    fi
    VALIDATION_DB_CREATED=1
    if ! pg_restore \
        "${PG_CONNECTION_ARGS[@]}" \
        --no-password \
        --exit-on-error \
        --no-owner \
        --no-privileges \
        --dbname="$VALIDATION_DB" \
        "$DUMP_TMP" >/dev/null; then
        erro "pg_restore falhou ao restaurar o dump em $VALIDATION_DB; arquivo inválido descartado"
        exit 9
    fi
    if ! RESTORED_COUNTS="$(database_counts "$VALIDATION_DB")"; then
        erro "não foi possível contar o banco restaurado; arquivo descartado"
        exit 10
    fi
    if [[ "$SOURCE_COUNTS" != "$RESTORED_COUNTS" ]]; then
        erro "contagem divergente após restore (origem=$SOURCE_COUNTS, restaurado=$RESTORED_COUNTS); arquivo descartado"
        exit 11
    fi
    log "restore validado: $VALIDATION_DB ($RESTORED_COUNTS; tabelas|linhas)"
    drop_validation_db
else
    log "AVISO: BACKUP_VALIDATE_RESTORE=0; restore descartável e contagem desligados por decisão explícita"
    if ! pg_restore --exit-on-error --file=/dev/null "$DUMP_TMP" >/dev/null; then
        erro "pg_restore não conseguiu ler integralmente o archive; arquivo descartado"
        exit 12
    fi
    log "leitura integral do archive validada, mas o restore em banco foi pulado"
fi

mv -f -- "$DUMP_TMP" "$DUMP_FILE"
DUMP_TMP=""
log "dump validado: $DUMP_FILE"

log "arquivando MEDIA_ROOT: $MEDIA_DIR"
if ! tar -czf "$MEDIA_TMP" -C "$MEDIA_DIR" .; then
    erro "tar da mídia falhou; nenhum arquivo final foi publicado"
    exit 13
fi
if [[ ! -s "$MEDIA_TMP" ]]; then
    erro "tar da mídia produziu um arquivo vazio: $MEDIA_TMP"
    exit 14
fi
if ! tar -tzf "$MEDIA_TMP" >/dev/null; then
    erro "o arquivo compactado da mídia está corrompido; arquivo inválido descartado"
    exit 15
fi
mv -f -- "$MEDIA_TMP" "$MEDIA_FILE"
MEDIA_TMP=""
log "mídia validada: $MEDIA_FILE"

if (( S3_REMOTE_ENABLED )); then
    BUCKET="${S3_BUCKET%/}"
    if [[ -z "$BUCKET" ]]; then
        erro "BACKUP_S3_BUCKET contém apenas barras; configuração S3 inválida"
        exit 16
    fi
    DUMP_KEY="db/$(basename "$DUMP_FILE")"
    MEDIA_KEY="media/$(basename "$MEDIA_FILE")"

    log "enviando dump para s3://$BUCKET/$DUMP_KEY"
    if ! "${AWS_CMD[@]}" s3 cp "$DUMP_FILE" "s3://$BUCKET/$DUMP_KEY" --only-show-errors; then
        erro "upload do dump falhou; nenhum backup local será removido"
        exit 17
    fi
    log "enviando mídia para s3://$BUCKET/$MEDIA_KEY"
    if ! "${AWS_CMD[@]}" s3 cp "$MEDIA_FILE" "s3://$BUCKET/$MEDIA_KEY" --only-show-errors; then
        erro "upload da mídia falhou; nenhum backup local será removido"
        exit 18
    fi

    # Não confie apenas no exit zero de `cp`: confirma o objeto e o tamanho
    # antes de liberar qualquer retenção local.
    verify_s3_object() {
        local local_file="$1" remote_key="$2" local_size remote_size
        local_size="$(stat -c '%s' "$local_file")"
        if ! remote_size="$("${AWS_CMD[@]}" s3api head-object --bucket "$BUCKET" --key "$remote_key" --query ContentLength --output text)"; then
            erro "não foi possível verificar o objeto remoto s3://$BUCKET/$remote_key"
            return 1
        fi
        remote_size="${remote_size//$'\r'/}"
        remote_size="${remote_size//$'\n'/}"
        if [[ ! "$remote_size" =~ ^[0-9]+$ || "$remote_size" != "$local_size" ]]; then
            erro "tamanho remoto divergente para s3://$BUCKET/$remote_key (local=$local_size remoto=$remote_size)"
            return 1
        fi
    }
    if ! verify_s3_object "$DUMP_FILE" "$DUMP_KEY"; then
        exit 19
    fi
    if ! verify_s3_object "$MEDIA_FILE" "$MEDIA_KEY"; then
        exit 19
    fi
    log "upload S3 concluído e objetos verificados"

    log "aplicando retenção local de $RETENCAO_LOCAL_DIAS dias somente aos artefatos pm2-*"
    find "$BACKUP_DIR" -maxdepth 1 -type f -name 'pm2-db-*.dump' \
        -mtime "+$RETENCAO_LOCAL_DIAS" -print -delete
    find "$BACKUP_DIR" -maxdepth 1 -type f -name 'pm2-media-*.tar.gz' \
        -mtime "+$RETENCAO_LOCAL_DIAS" -print -delete
else
    log "AVISO: BACKUP_S3_BUCKET não configurado — o backup ficará SOMENTE nesta VPS; a retenção local fica suspensa e NENHUM backup será apagado."
    log "AVISO: configure R2/B2/S3 e uma lifecycle rule remota; esta cópia local não sobrevive à perda do host."
fi

log "backup concluído: $DUMP_FILE + $MEDIA_FILE"
