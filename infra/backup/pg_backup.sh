#!/usr/bin/env bash
# Backup diário do Postgres + mídia de usuário — variante DOCKER/CADDY
# (ARCHITECTURE.md §9.3, infra/DEPLOY.md:3-12). Roda NO HOST da VPS (via
# crontab) e NÃO dentro de um container, para conseguir chamar
# `docker compose exec` e sobreviver a qualquer problema nos containers da
# aplicação.
#
# =============================================================================
# ESTA SCRIPT É DA TOPOLOGIA DOCKER. A VPS ATIVA É PM2 (sem Docker Compose)
# =============================================================================
#   infra/DEPLOY.md:10-12 — "VPS roda PM2 (não Docker Compose) […] Não usar
#   `docker compose --env-file .env.production` na VPS."
#
#   Se o cron desta máquina chamar este arquivo e o `docker compose` não souber
#   resolver os serviços `db`/`web`, o script NÃO tenta adivinhar: ele falha
#   com o código 3 e diz qual script usar. Antes desta versão ele saía com 1 e
#   um `pg_dump: command not found` enterrado num log que ninguém lê.
#
#   Para a topologia PM2 (é a da VPS de produção) use
#   `infra/backup/pg_backup_pm2.sh`, que é `pg_dump` nativo no host.
#
# USO (cron, uma vez por ambiente)
#   0 3 * * * /home/deploy/brd_portal_noticias/infra/backup/pg_backup.sh \
#       >> /var/log/pg_backup.log 2>&1
#
# =============================================================================
# AS TRÊS QUEBRAS CORRIGIDAS EM 2026-09-28 (e por que cada uma importava)
# =============================================================================
#   1. MODO 100644 NO ÍNDICE DO GIT. O cron executa o arquivo pelo caminho
#      (`/bin/sh: 1: …pg_backup.sh: Permission denied`). O `deploy.yml` faz
#      `git clone` + `git reset --hard` (linhas 204-260) — ele NÃO copia
#      arquivo por arquivo — então o modo que chega à VPS é o do índice. Um
#      `chmod +x` na VPS se perde no próximo deploy. Corrigido versionando o
#      modo 100755 (`git update-index --chmod=+x`).
#   2. ARQUIVO DE AMBIENTE INEXISTENTE. A script exigia
#      `$PROJECT_DIR/.env.production`; o arquivo que o deploy realmente cria é
#      `backend/.env` (.github/workflows/deploy.yml:267-288). O erro antigo
#      nomeava UM caminho e o operador ficava sem saber onde procurar. Agora a
#      resolução é explícita, aceita `BACKUP_ENV_FILE` e nomeia TODOS os
#      caminhos que tentou.
#   3. DUMP DENTRO DA ÁRVORE DE GIT. `BACKUP_DIR="$PROJECT_DIR/infra/backup"`
#      escrevia o backup dentro do checkout — que é apagado por
#      `git reset --hard`/`git clean` evelado para a árvore versionada. O dump
#      agora vive em `/var/backups/portal/<diretório-do-deploy>/`, fora do
#      repositório, com retenção de 7 dias.
#
# =============================================================================
# POR QUE OFF-VPS É OBRIGATÓRIO
# =============================================================================
# Um volume Docker nomeado (postgres_data) protege contra o container cair, mas
# NÃO contra perda da VPS inteira (disco corrompido, conta suspensa, erro humano
# de `docker volume rm`). "Garantir a persistência dos dados" (pedido explícito
# da nova arquitetura) exige uma cópia fora da máquina que guarda o original.
#
# =============================================================================
# CÓDIGOS DE SAÍDA — o cron não distingue "deu ruim" de "deu ruim em quê"
# =============================================================================
#   0   backup publicado (dump + mídia), e remoto verificado quando há bucket
#   1   configuração inválida: env file ausente/ilegível, BACKUP_DIR não
#       gravável, configuração S3 parcial, valor malformado no env file
#   2   dependência ausente no host: `docker` ou `aws`
#   3   topologia incompatível: o Compose existe mas `db`/`web` não estão no ar
#   4   pg_dump falhou
#   5   pg_dump produziu arquivo vazio
#   6   o arquivo não é um custom dump válido (pg_restore --list)
#   7   o dump não contém dados: nenhuma tabela com dados, ou o banco de origem
#       tinha menos de BACKUP_MIN_LINHAS linhas. É o dump de 48 KB que ficou
#       semanas em produção — um banco vazio produz um dump PERFEITAMENTE VÁLIDO,
#       que passaria em qualquer validação que só olhasse a estrutura
#   8   restore de validação falhou ou a contagem de origem ≠ restaurada
#   9   a mídia não pôde ser arquivada, ficou vazia ou o tar.gz está corrompido
#   10  upload do dump ao storage remoto falhou
#   11  upload da mídia ao storage remoto falhou
#   12  objeto remoto ausente ou com tamanho diferente do local
#   13  o backup está íntegro, mas o heartbeat de alerta não foi confirmado
#
# Nenhum código 0 significa "o backup existe e foi verificado". Todo código
# diferente de zero escreve uma linha `FALHA (exit N)` no log e, se
# BACKUP_ALERT_WEBHOOK_URL estiver definido, notifica o webhook.
set -euo pipefail
# Dump e mídia contêm a base inteira. O umask do cron costuma ser 022, que
# deixaria o backup legível por qualquer usuário do host.
umask 077

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
COMPOSE_FILE="${BACKUP_COMPOSE_FILE:-$PROJECT_DIR/docker-compose.yml}"
RETENCAO_LOCAL_DIAS="${BACKUP_RETENCAO_DIAS:-7}"
VALIDATE_RESTORE="${BACKUP_VALIDATE_RESTORE:-1}"
BACKUP_REQUIRE_REMOTE="${BACKUP_REQUIRE_REMOTE:-0}"
MIN_TABLE_DATA="${BACKUP_MIN_TABLE_DATA:-1}"
MIN_LINHAS="${BACKUP_MIN_LINHAS:-1}"
HEARTBEAT_URL="${BACKUP_HEARTBEAT_URL:-}"
WEBHOOK_URL="${BACKUP_ALERT_WEBHOOK_URL:-}"

DUMP_TMP=""
MEDIA_TMP=""
VALIDATION_DB=""
VALIDATION_DB_CREATED=0
MOTIVO_FALHA="falha não classificada"
S3_REMOTE_ENABLED=0
AWS_CMD=()

log() { printf '[pg_backup] %s\n' "$*"; }
erro() { printf '[pg_backup] ERRO: %s\n' "$*" >&2; }

# --- Falha: uma linha inequívoca, limpeza e notificação -------------------
# O `trap` existe para que NENHUMA saída Early saia silenciosa: um backup que
# falha calado é pior que nenhum backup, porque cria a ilusão de proteção.
notificar_falha() {
    local url="$1" status="$2" motivo="$3" corpo
    [[ -n "$url" ]] || return 0
    command -v curl >/dev/null 2>&1 || {
        erro "curl ausente e BACKUP_ALERT_WEBHOOK_URL definido: falha não notificada"
        return 0
    }
    corpo="$(printf '{"servico":"pg_backup","status":"falha","exit":%d,"motivo":%s,"ambiente":%s,"em":%s}' \
        "$status" "$(json_texto "$motivo")" "$(json_texto "${BACKUP_ENV_LABEL:-$(basename "$PROJECT_DIR")}")" \
        "$(date -u +%Y-%m-%dT%H:%M:%SZ)")"
    if ! curl --fail --silent --show-error --max-time 20 \
        -H 'Content-Type: application/json' --data "$corpo" "$url" >/dev/null; then
        # A falha do canal NÃO sobrescreve o código da falha original: o
        # operador precisa saber por que o backup quebrou, não que o aviso
        # também quebrou.
        erro "BACKUP_ALERT_WEBHOOK_URL não recebeu a notificação (HTTP != 2xx, timeout ou DNS)"
    fi
    return 0
}

# Escapa mínima para o JSON montado à mão: `jq` não é garantido num host de
# VPS mínimo, e um consumidor quebrado por aspas é pior que um campo vazio.
json_texto() {
    local bruto="${1:-}"
    [[ -n "$bruto" ]] || { printf 'null'; return; }
    bruto="${bruto//\\/\\\\}"
    bruto="${bruto//\"/\\\"}"
    printf '"%s"' "$bruto"
}

cleanup() {
    local status=$?
    trap - EXIT
    if (( VALIDATION_DB_CREATED == 1 )) && [[ -n "$VALIDATION_DB" ]]; then
        log "descartando o banco descartável de validação: $VALIDATION_DB"
        compose_db dropdb -U "$DB_USER" --if-exists "$VALIDATION_DB" >/dev/null 2>&1 || \
            log "AVISO: não foi possível remover o banco de validação $VALIDATION_DB"
        VALIDATION_DB_CREATED=0
    fi
    [[ -z "$DUMP_TMP" ]] || rm -f -- "$DUMP_TMP" || true
    [[ -z "$MEDIA_TMP" ]] || rm -f -- "$MEDIA_TMP" || true
    if (( status != 0 )); then
        printf '[pg_backup] FALHA (exit %d): %s\n' "$status" "$MOTIVO_FALHA" >&2
        notificar_falha "$WEBHOOK_URL" "$status" "$MOTIVO_FALHA"
    fi
    exit "$status"
}
trap cleanup EXIT

falhar() {  # falhar <código> <motivo>
    MOTIVO_FALHA="$2"
    erro "$2"
    exit "$1"
}

# --- Passos no container do Compose ---------------------------------------
compose() { docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" "$@"; }
compose_db() { compose exec -T db "$@"; }
compose_web() { compose exec -T web "$@"; }

# --- 1. Dependências -------------------------------------------------------
if ! command -v docker >/dev/null 2>&1; then
    falhar 2 "docker ausente neste host. Esta script é da variante Docker/Caddy; na topologia PM2 use infra/backup/pg_backup_pm2.sh"
fi
if ! docker compose version >/dev/null 2>&1; then
    falhar 2 "plugin 'docker compose' (v2) ausente neste host"
fi

# --- 2. Arquivo de ambiente ------------------------------------------------
# Ordem: o que o operador pediu explicitamente, depois o arquivo desta variante
# Docker, depois o arquivo que o deploy PM2 realmente cria, depois o `.env` da
# raiz. O erro lista TODOS os caminhos tentados: a mensagem antiga nomeava um
# único caminho e o operador não sabia onde o arquivo estava.
ENV_FILE="${BACKUP_ENV_FILE:-}"
TENTADOS=()
if [[ -n "$ENV_FILE" ]]; then
    TENTADOS+=("$ENV_FILE")
    [[ -f "$ENV_FILE" ]] || falhar 1 "BACKUP_ENV_FILE não existe: $ENV_FILE"
else
    for candidato in "$PROJECT_DIR/.env.production" "$PROJECT_DIR/backend/.env" "$PROJECT_DIR/.env"; do
        TENTADOS+=("$candidato")
        if [[ -f "$candidato" ]]; then ENV_FILE="$candidato"; break; fi
    done
    if [[ -z "$ENV_FILE" ]]; then
        falhar 1 "nenhum arquivo de ambiente encontrado; procurei: ${TENTADOS[*]}. Defina BACKUP_ENV_FILE=<caminho> no cron ou crie o arquivo"
    fi
fi

# O arquivo é o mesmo que o `deploy.yml` FONTE como shell (`set -a; . ./.env`,
# linha 320) e o mesmo que o `pg_backup_pm2.sh` fonte. Isso é intencional: um
# arquivo que o shell lê e o Django não (ou o contrário) faz o backup
# responder por um banco diferente do que a aplicação usa.
#
# A checagem abaixo existe porque `source` é mais permissivo que o parser de
# .env do Django: `FOO=bar baz` vira `FOO=bar` no shell e "bar baz" no Django.
# Divergir assim é silencioso, e o backup errado continua parecendo certo.
while IFS= read -r linha || [[ -n "$linha" ]]; do
    case "$linha" in
        ''|'#'*|export\ *) continue ;;
    esac
    [[ "$linha" == *=* ]] || continue
    chave="${linha%%=*}"
    valor="${linha#*=}"
    [[ "$chave" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]] || continue
    case "$valor" in
        '"'*|"'"*) continue ;;
    esac
    sem_comentario="${valor%%#*}"
    sem_comentario="${sem_comentario%"${sem_comentario##*[![:space:]]}"}"
    if [[ "$sem_comentario" == *[[:space:]]* ]]; then
        falhar 1 "$ENV_FILE linha de '$chave' tem valor sem aspas com espaço — 'source' (usado pelo deploy.yml:320 e por este script) truncaria em '${sem_comentario%% *}' enquanto o Django leria o valor inteiro; coloque o valor entre aspas"
    fi
done < "$ENV_FILE"

# O env file é fallback: uma variável já exportada pelo processo/cron NÃO pode
# ser sobrescrita por uma linha vazia do arquivo (o caso de um example copiado
# sem preencher). Mesmo tratamento do pg_backup_pm2.sh:100-129.
ENV_DJANGO_DB_NAME="${DJANGO_DB_NAME:-}"
ENV_DJANGO_DB_USER="${DJANGO_DB_USER:-}"
ENV_BACKUP_S3_ENDPOINT="${BACKUP_S3_ENDPOINT-}"
ENV_BACKUP_S3_BUCKET="${BACKUP_S3_BUCKET-}"
ENV_BACKUP_S3_ACCESS_KEY="${BACKUP_S3_ACCESS_KEY-}"
ENV_BACKUP_S3_SECRET_KEY="${BACKUP_S3_SECRET_KEY-}"
ENV_BACKUP_HEARTBEAT_URL="${BACKUP_HEARTBEAT_URL-}"
ENV_BACKUP_ALERT_WEBHOOK_URL="${BACKUP_ALERT_WEBHOOK_URL-}"

log "carregando o ambiente de $ENV_FILE"
set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a

[[ -z "$ENV_DJANGO_DB_NAME" ]] || DJANGO_DB_NAME="$ENV_DJANGO_DB_NAME"
[[ -z "$ENV_DJANGO_DB_USER" ]] || DJANGO_DB_USER="$ENV_DJANGO_DB_USER"
[[ -z "$ENV_BACKUP_S3_ENDPOINT" ]] || BACKUP_S3_ENDPOINT="$ENV_BACKUP_S3_ENDPOINT"
[[ -z "$ENV_BACKUP_S3_BUCKET" ]] || BACKUP_S3_BUCKET="$ENV_BACKUP_S3_BUCKET"
[[ -z "$ENV_BACKUP_S3_ACCESS_KEY" ]] || BACKUP_S3_ACCESS_KEY="$ENV_BACKUP_S3_ACCESS_KEY"
[[ -z "$ENV_BACKUP_S3_SECRET_KEY" ]] || BACKUP_S3_SECRET_KEY="$ENV_BACKUP_S3_SECRET_KEY"
[[ -z "$ENV_BACKUP_HEARTBEAT_URL" ]] || HEARTBEAT_URL="$ENV_BACKUP_HEARTBEAT_URL"
[[ -z "$ENV_BACKUP_ALERT_WEBHOOK_URL" ]] || WEBHOOK_URL="$ENV_BACKUP_ALERT_WEBHOOK_URL"

DB_NAME="${DJANGO_DB_NAME:-brd_portal_noticias}"
DB_USER="${DJANGO_DB_USER:-postgres}"
[[ -f "$COMPOSE_FILE" ]] || falhar 1 "docker-compose.yml não encontrado em $COMPOSE_FILE (ajuste BACKUP_COMPOSE_FILE)"

# --- 3. Topologia: os serviços que esta script usa precisam estar no ar -----
# Consequência medida em 2026-09-28: o cron de produção apontava para este
# arquivo numa VPS que roda PM2. A tentativa antiga de `docker compose exec`
# falhava com um erro de `pg_dump` que não diz nada sobre topologia.
em_execucao="$(compose ps --services --status running 2>/dev/null || true)"
for servico in db web; do
    if ! grep -qx "$servico" <<<"$em_execucao"; then
        falhar 3 "o serviço '$servico' do Compose não está rodando em $COMPOSE_FILE. Se esta máquina é a topologia PM2 (a VPS de produção), o cron deve chamar infra/backup/pg_backup_pm2.sh — este arquivo é exclusivo da variante Docker/Caddy (infra/DEPLOY.md:10-12)"
    fi
done
if ! compose_web sh -c 'test -d /app/media' 2>/dev/null; then
    falhar 3 "/app/media não existe dentro do container 'web'; sem ele o backup de mídia seria um tar vazio que parece um backup"
fi

# --- 4. Destino FORA da árvore de git --------------------------------------
# `/var/backups` é a convenção do host e, por estar fora do checkout, não é
# tocado por `git reset --hard`, nem por `git clean`, nem pode ser commitado
# por engano. O nome do subdiretório é o do diretório de deploy
# (`portal-prod`, `portal-dev`, `brd_portal_noticias`), o que já separa os
# ambientes sem precisar de uma variável a mais.
BACKUP_DIR="${BACKUP_DIR:-/var/backups/portal/$(basename "$PROJECT_DIR")}"
if ! mkdir -p -- "$BACKUP_DIR" 2>/dev/null; then
    falhar 1 "não foi possível criar $BACKUP_DIR. Ele fica fora da árvore do projeto de propósito. Crie uma vez com: sudo install -d -o \"\$(id -un)\" -g \"\$(id -gn)\" -m 0750 '$BACKUP_DIR'  (ou aponte BACKUP_DIR para um caminho gravável)"
fi
[[ -w "$BACKUP_DIR" ]] || falhar 1 "$BACKUP_DIR existe mas não é gravável pelo usuário efetivo (uid $(id -u)); o cron não roda como root por padrão"

# --- 5. Storage remoto (R2 / B2 / S3) --------------------------------------
# Fail-closed quando parcial: credencial sem bucket não pode ser confundida com
# "sem storage remoto" e cair silenciosamente no modo local-only.
S3_BUCKET="${BACKUP_S3_BUCKET:-}"
S3_ENDPOINT="${BACKUP_S3_ENDPOINT:-}"
S3_ACCESS_KEY="${BACKUP_S3_ACCESS_KEY:-}"
S3_SECRET_KEY="${BACKUP_S3_SECRET_KEY:-}"

if [[ -n "$S3_BUCKET" ]]; then
    S3_REMOTE_ENABLED=1
    S3_BUCKET="${S3_BUCKET%/}"
    if [[ -n "$S3_ACCESS_KEY" || -n "$S3_SECRET_KEY" ]]; then
        if [[ -z "$S3_ACCESS_KEY" || -z "$S3_SECRET_KEY" ]]; then
            falhar 1 "BACKUP_S3_ACCESS_KEY e BACKUP_S3_SECRET_KEY devem ser definidas em conjunto"
        fi
    fi
    if ! command -v aws >/dev/null 2>&1; then
        falhar 2 "BACKUP_S3_BUCKET está configurado, mas a AWS CLI não está instalada neste host (apt install awscli)"
    fi
    AWS_CMD=(aws)
    [[ -z "$S3_ENDPOINT" ]] || AWS_CMD+=(--endpoint-url "$S3_ENDPOINT")
    if [[ -n "$S3_ACCESS_KEY" ]]; then
        export AWS_ACCESS_KEY_ID="$S3_ACCESS_KEY"
        export AWS_SECRET_ACCESS_KEY="$S3_SECRET_KEY"
    fi
elif [[ -n "$S3_ENDPOINT" || -n "$S3_ACCESS_KEY" || -n "$S3_SECRET_KEY" ]]; then
    falhar 1 "configuração S3 parcial: BACKUP_S3_BUCKET está vazio, mas endpoint/chave foram definidos — isso não é 'sem storage remoto'"
fi

case "$(printf '%s' "$VALIDATE_RESTORE" | tr '[:upper:]' '[:lower:]')" in
    1|true) VALIDAR_RESTORE=1 ;;
    0|false) VALIDAR_RESTORE=0 ;;
    *) falhar 1 "BACKUP_VALIDATE_RESTORE deve ser 1/true (padrão) ou 0/false; recebido: '$VALIDATE_RESTORE'" ;;
esac
[[ "$MIN_TABLE_DATA" =~ ^[0-9]+$ ]] || falhar 1 "BACKUP_MIN_TABLE_DATA deve ser um inteiro não negativo; recebido: '$MIN_TABLE_DATA'"
[[ "$MIN_LINHAS" =~ ^[0-9]+$ ]] || falhar 1 "BACKUP_MIN_LINHAS deve ser um inteiro não negativo; recebido: '$MIN_LINHAS'"

TIMESTAMP="$(date -u +%Y%m%dT%H%M%SZ)"
# O nome do arquivo não muda: `infra/backup/RESTORE.md:57` documenta a chave
# remota `db/db-AAAAMMDD-HHMMSS.dump` e o runbook de restore depende dele.
DUMP_FILE="$BACKUP_DIR/db-$TIMESTAMP.dump"
MEDIA_FILE="$BACKUP_DIR/media-$TIMESTAMP.tar.gz"
DUMP_TMP="$BACKUP_DIR/.db-$TIMESTAMP.dump.$$"
MEDIA_TMP="$BACKUP_DIR/.media-$TIMESTAMP.tar.gz.$$"
VALIDATION_DB="backup_validate_${TIMESTAMP}_$$"

# Publicar por `mv` e não por escrita direta: enquanto o dump é escrito, ele
# existe em disco com tamanho parcial. Um watchdog (ou um humano) que olha o
# diretório nesse instante veria "backup novo" sobre um arquivo truncado — que
# é exatamente o verde que este script existe para impedir.
# Mesma consulta de contagem do `pg_backup_pm2.sh:265-290` (tabelas|linhas):
# `query_to_xml` permite montar `SELECT count(*)` com quoting seguro para schemas
# e tabelas de nome incomum, e o resultado é sempre "tabelas|linhas".
SQL_CONTAGEM="$(
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

contar_tabelas_linhas() {  # imprime "<tabelas>|<linhas>"
    local db="$1" resultado
    if ! resultado="$(printf '%s' "$SQL_CONTAGEM" | compose_db psql -U "$DB_USER" --no-password \
            --no-psqlrc --quiet --tuples-only --no-align --field-separator='|' \
            --set=ON_ERROR_STOP=1 --dbname="$db")"; then
        return 1
    fi
    resultado="${resultado//$'\r'/}"
    resultado="${resultado//$'\n'/}"
    [[ "$resultado" =~ ^[0-9]+\|[0-9]+$ ]] || return 1
    printf '%s' "$resultado"
}

# --- 6. Dump ---------------------------------------------------------------
log "dump do Postgres: banco=$DB_NAME usuário=$DB_USER"
if ! compose_db pg_dump -U "$DB_USER" -Fc --no-password --dbname="$DB_NAME" > "$DUMP_TMP"; then
    falhar 4 "pg_dump falhou; nenhum arquivo final foi publicado"
fi
if [[ ! -s "$DUMP_TMP" ]]; then
    falhar 5 "pg_dump produziu um arquivo vazio ($DUMP_TMP); o arquivo foi descartado"
fi

# `pg_restore --list` é só a TOC. Um archive truncado passa nela, e um banco
# VAZIO também: é por isso que o dump de 48 KB de produção passou na
# validação antiga e ficou semanas sem ninguém perceber.
if ! compose_db pg_restore --list < "$DUMP_TMP" >/dev/null 2>&1; then
    falhar 6 "$DUMP_TMP não é um custom dump válido (pg_restore --list rejeitou); arquivo descartado"
fi

# A contagem de entradas TABLE DATA diz quantas TABELAS entraram no dump; ela
# não diz se entraram LINHAS. As duas coisas são necessárias, e a medição de
# produção mostra por quê: o backup que lá estava tinha 48 KB contra
# 4.599.328 bytes do dump real com 4156 notícias. Um banco com as tabelas
# criadas e zero linhas em todas elas produz um dump estruturalmente PERFEITO —
# `pg_restore --list` aprova, o `pg_restore` aprova, e o backup não restaura
# nada. Contar só a TOC deixaria esse caso passar.
TABLAS_COM_DADOS="$(compose_db pg_restore --list < "$DUMP_TMP" | grep -c 'TABLE DATA' || true)"
TABLAS_COM_DADOS="${TABLAS_COM_DADOS//[^0-9]/}"
log "entradas TABLE DATA no dump: $TABLAS_COM_DADOS"
if (( TABLAS_COM_DADOS < MIN_TABLE_DATA )); then
    falhar 7 "o dump não tem nenhuma tabela com dados (TABLE DATA=$TABLAS_COM_DADOS, mínimo=$MIN_TABLE_DATA). Um dump de banco vazio é um dump VÁLIDO para o pg_restore, e por isso passaria em qualquer validação que só olhasse a estrutura — foi assim que o dump de 48 KB ficou semanas em produção sem ninguém perceber. Nenhum arquivo foi publicado"
fi

# A contagem de linhas da ORIGEM é sempre feita, mesmo com o restore desligado:
# ela é a barreira contra o "backup que não tem nada dentro", e depende só de
# um SELECT, não de restaurar nada.
if ! CONTAGEM_ORIGEM="$(contar_tabelas_linhas "$DB_NAME")"; then
    falhar 8 "não foi possível contar tabelas/linhas no banco de origem; o dump não será publicado"
fi
LINHAS_ORIGEM="${CONTAGEM_ORIGEM#*|}"
log "contagem da origem: $CONTAGEM_ORIGEM (tabelas|linhas)"
if (( LINHAS_ORIGEM < MIN_LINHAS )); then
    falhar 7 "o dump foi gerado de um banco com $LINHAS_ORIGEM linha(s) no total (mínimo=$MIN_LINHAS). O arquivo é um dump Postgres VÁLIDO e restauraria um banco vazio — que é exatamente a forma do backup de 48 KB que passou em produção. Se este ambiente é legitimamente novo, ponha BACKUP_MIN_LINHAS=0 e registre a decisão. Nenhum arquivo foi publicado"
fi

if (( VALIDAR_RESTORE )); then
    # Um backup que nunca foi restaurado é uma esperança (RESTORE.md:1-6). O
    # restore num banco descartável + a comparação de contagens é o que
    # transforma "o pg_dump rodou" em "isto é recuperável".
    log "validando: restore completo em banco descartável + contagem de linhas"
    if ! compose_db createdb -U "$DB_USER" --no-password -T template0 "$VALIDATION_DB"; then
        falhar 8 "não foi possível criar o banco descartável para validar o restore; o dump não será publicado"
    fi
    VALIDATION_DB_CREATED=1
    if ! compose_db pg_restore -U "$DB_USER" --no-password --exit-on-error --no-owner \
            --no-privileges --dbname="$VALIDATION_DB" < "$DUMP_TMP" >/dev/null; then
        falhar 8 "pg_restore falhou ao restaurar o dump em $VALIDATION_DB; arquivo descartado"
    fi
    CONTAGEM_RESTAURADA="$(contar_tabelas_linhas "$VALIDATION_DB")" || \
        falhar 8 "não foi possível contar o banco restaurado; arquivo descartado"
    if [[ "$CONTAGEM_ORIGEM" != "$CONTAGEM_RESTAURADA" ]]; then
        falhar 8 "contagem divergente após o restore (origem=$CONTAGEM_ORIGEM restaurado=$CONTAGEM_RESTAURADA, no formato tabelas|linhas); arquivo descartado"
    fi
    log "restore validado: $CONTAGEM_RESTAURADA (tabelas|linhas)"
    VALIDATION_DB_CREATED=0
    compose_db dropdb -U "$DB_USER" --no-password --if-exists "$VALIDATION_DB" >/dev/null 2>&1 || \
        log "AVISO: não foi possível remover o banco descartável $VALIDATION_DB"
else
    log "AVISO: BACKUP_VALIDATE_RESTORE=0; o restore em banco foi desligado por decisão explícita. O dump ainda foi conferido pela TOC e pela contagem de linhas da origem ($CONTAGEM_ORIGEM), mas NINGUÉM restaurou este arquivo para provar que ele volta"
    if ! compose_db pg_restore --exit-on-error --file=/dev/null --no-owner --no-privileges < "$DUMP_TMP" >/dev/null 2>&1; then
        falhar 6 "pg_restore não conseguiu ler integralmente o archive; arquivo descartado"
    fi
fi

mv -f -- "$DUMP_TMP" "$DUMP_FILE"
DUMP_TMP=""
TAMANHO_DUMP="$(stat -c '%s' "$DUMP_FILE")"
log "dump publicado: $DUMP_FILE ($TAMANHO_DUMP bytes, $TABLAS_COM_DADOS tabelas com dados, $LINHAS_ORIGEM linhas)"

# --- 7. Mídia --------------------------------------------------------------
# Empacota a partir de DENTRO do container `web` em vez de referenciar o nome
# do volume Docker: o nome real do volume é prefixado pelo nome do projeto
# Compose, e `docker run -v <volume-inexistente>` cria silenciosamente um
# volume novo e VAZIO em vez de falhar — o pior tipo de erro, porque produz um
# backup de mídia vazio sem nenhum aviso.
log "arquivando a mídia de /app/media"
if ! compose_web tar czf - -C /app/media . > "$MEDIA_TMP"; then
    falhar 9 "tar da mídia falhou; nenhum arquivo final foi publicado"
fi
if [[ ! -s "$MEDIA_TMP" ]]; then
    falhar 9 "o tar da mídia produziu um arquivo vazio; arquivo descartado"
fi
if ! tar -tzf "$MEDIA_TMP" >/dev/null 2>&1; then
    falhar 9 "o tar.gz da mídia está corrompido; arquivo descartado"
fi
MEMBROS_MIDIA="$(tar -tzf "$MEDIA_TMP" 2>/dev/null | grep -vc '/$' || true)"
MEMBROS_MIDIA="${MEMBROS_MIDIA//[^0-9]/}"
if (( MEMBROS_MIDIA == 0 )); then
    log "AVISO: o arquivo de mídia tem 0 arquivos ($MEDIA_TMP). Legítimo num ambiente sem upload; se este ambiente já tem mídia publicada, o volume media_data está vazio"
fi
mv -f -- "$MEDIA_TMP" "$MEDIA_FILE"
MEDIA_TMP=""
TAMANHO_MEDIA="$(stat -c '%s' "$MEDIA_FILE")"
log "mídia publicada: $MEDIA_FILE ($TAMANHO_MEDIA bytes, $MEMBROS_MIDIA arquivos)"

# --- 8. Storage remoto -----------------------------------------------------
# O nome do objeto carrega o timestamp UTC do dump, então uma reexecução no
# mesmo segundo sobrescreve a MESMA chave (idempotente) e execuções diferentes
# nunca colidem. A retenção de longo prazo é lifecycle rule do bucket.
verificar_objeto() {  # <arquivo local> <chave remota>
    local local_file="$1" chave="$2" tamanho_local tamanho_remoto
    tamanho_local="$(stat -c '%s' "$local_file")"
    if ! tamanho_remoto="$("${AWS_CMD[@]}" s3api head-object --bucket "$S3_BUCKET" --key "$chave" \
            --query ContentLength --output text 2>/dev/null)"; then
        return 1
    fi
    tamanho_remoto="${tamanho_remoto//$'\r'/}"
    tamanho_remoto="${tamanho_remoto//$'\n'/}"
    [[ "$tamanho_remoto" =~ ^[0-9]+$ ]] || return 1
    [[ "$tamanho_remoto" == "$tamanho_local" ]]
}

REMOTO_CONFIRMADO="nao"
if (( S3_REMOTE_ENABLED )); then
    CHAVE_DUMP="db/$(basename "$DUMP_FILE")"
    CHAVE_MIDIA="media/$(basename "$MEDIA_FILE")"
    log "enviando o dump para s3://$S3_BUCKET/$CHAVE_DUMP"
    # O `cp` sem erro não é prova: um objeto truncado no bucket é exatamente o
    # que um watchdog verde não pegaria. O head-object compara tamanho.
    "${AWS_CMD[@]}" s3 cp "$DUMP_FILE" "s3://$S3_BUCKET/$CHAVE_DUMP" --only-show-errors || \
        falhar 10 "upload do dump falhou; NENHUM backup local foi removido (o dump e a mídia continuam em $BACKUP_DIR)"
    verificar_objeto "$DUMP_FILE" "$CHAVE_DUMP" || \
        falhar 12 "o objeto s3://$S3_BUCKET/$CHAVE_DUMP não existe ou tem tamanho diferente do local; NENHUM backup local foi removido"
    log "enviando a mídia para s3://$S3_BUCKET/$CHAVE_MIDIA"
    "${AWS_CMD[@]}" s3 cp "$MEDIA_FILE" "s3://$S3_BUCKET/$CHAVE_MIDIA" --only-show-errors || \
        falhar 11 "upload da mídia falhou; NENHUM backup local foi removido"
    verificar_objeto "$MEDIA_FILE" "$CHAVE_MIDIA" || \
        falhar 12 "o objeto s3://$S3_BUCKET/$CHAVE_MIDIA não existe ou tem tamanho diferente do local; NENHUM backup local foi removido"
    REMOTO_CONFIRMADO="sim"
    log "upload concluído e os dois objetos verificados por head-object"

    log "retenção local de $RETENCAO_LOCAL_DIAS dias (aplicada só depois dos dois uploads verificados)"
    find "$BACKUP_DIR" -maxdepth 1 -type f -name 'db-*.dump' -mtime "+$RETENCAO_LOCAL_DIAS" -print -delete
    find "$BACKUP_DIR" -maxdepth 1 -type f -name 'media-*.tar.gz' -mtime "+$RETENCAO_LOCAL_DIAS" -print -delete
elif [[ "$BACKUP_REQUIRE_REMOTE" == "1" ]]; then
    falhar 1 "BACKUP_REQUIRE_REMOTE=1 e BACKUP_S3_BUCKET está vazio: o backup ficaria SÓ nesta VPS, sem proteção contra a perda do host. Configure o bucket ou use BACKUP_REQUIRE_REMOTE=0"
else
    # Sem storage remoto, os arquivos locais são a ÚNICA cópia que existe.
    # Apagar os com mais de 7 dias apagaria todo o histórico em uma semana —
    # o oposto de "garantir a persistência dos dados".
    log "AVISO: BACKUP_S3_BUCKET não configurado — o backup ficará SOMENTE nesta VPS, que não sobrevive à perda do host, e a retenção local fica suspensa (nenhum arquivo é apagado)"
    log "AVISO: configure BACKUP_S3_ENDPOINT/BACKUP_S3_BUCKET/BACKUP_S3_ACCESS_KEY/BACKUP_S3_SECRET_KEY (Cloudflare R2 ou Backblaze B2) — ver infra/backup/RESTORE.md e infra/DEPLOY.md"
fi

# --- 9. Heartbeat ----------------------------------------------------------
# O canal que sobrevive à VPS morta. `cron_monitor_backup` em
# infra/observability/better-stack/checks.json:199-215 está COMO
# `cron_monitor_backup` documentado e FALTA o pinger — o próprio arquivo diz
# (linha 213) que sem ele "este cron monitor é um ALARTE QUE DISPARA SEMPRE".
# O ping só acontece DEPOIS do backup estar publicado e, quando há bucket,
# DEPOIS dos dois objetos terem sido verificados. Nunca em caso de falha: a
# ausência de ping é o que dispara o alerta.
if [[ -n "$HEARTBEAT_URL" ]]; then
    if ! command -v curl >/dev/null 2>&1; then
        falhar 13 "BACKUP_HEARTBEAT_URL está definido e curl não existe neste host: o backup está íntegro, mas o canal de alerta não pode ser exercitado"
    fi
    if ! curl --fail --silent --show-error --max-time 20 "$HEARTBEAT_URL" >/dev/null; then
        falhar 13 "o backup está íntegro, mas o heartbeat em BACKUP_HEARTBEAT_URL não respondeu (HTTP != 2xx, timeout ou DNS): o cron monitor externo vai abrir incidente por ausência de sinal"
    fi
    log "heartbeat confirmado em BACKUP_HEARTBEAT_URL"
elif (( S3_REMOTE_ENABLED )); then
    log "AVISO: BACKUP_HEARTBEAT_URL não configurado; o cron monitor externo (checks.json -> cron_monitor_backup) vai abrir incidente por ausência de ping mesmo com o backup íntegro"
fi

printf '[pg_backup] OK dump=%s bytes=%s tabelas_com_dados=%s linhas=%s midia=%s bytes=%s arquivos=%s contagem=%s restore_validado=%s remoto=%s dir=%s em=%s\n' \
    "$(basename "$DUMP_FILE")" "$TAMANHO_DUMP" "$TABLAS_COM_DADOS" "$LINHAS_ORIGEM" \
    "$(basename "$MEDIA_FILE")" "$TAMANHO_MEDIA" "$MEMBROS_MIDIA" \
    "$CONTAGEM_ORIGEM" "$( (( VALIDAR_RESTORE )) && printf sim || printf nao )" \
    "$REMOTO_CONFIRMADO" "$BACKUP_DIR" "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
log "concluído: $DUMP_FILE + $MEDIA_FILE"
