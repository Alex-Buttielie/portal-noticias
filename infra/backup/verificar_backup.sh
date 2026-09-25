#!/usr/bin/env bash
# Watchdog de atraso do backup diário (run 20260925-1020-observabilidade,
# achado B8, critérios 34 e 35).
#
# POR QUE ISTO EXISTE, E POR QUE NÃO BASTA
#   O `pg_backup_pm2.sh` valida o dump, o restore em banco descartável e o
#   upload remoto — mas validação só acontece QUANDO O SCRIPT RODA. Se o cron
#   parou, se a VPS não subiu, ou se o env quebrou, ninguém percebe: o
#   dashboard de backup fica tranquilo e o próximo dia de precisar do backup é
#   o dia de descobrir que ele não existe.
#   Este script é a verificação INDEPENDENTE dessa passaram. E o canal externo
#   (cron monitor do Better Stack, pingado pelo `pg_backup_pm2.sh`) é o que
#   cobre o caso que nenhum watchdog na VPS pode cobrir: a VPS morta.
#
# USO (cron — a cada hora, bem antes do limite de 26 h):
#   5 * * * * BACKUP_ENV_FILE=/home/apps/portal-prod/backend/.env \
#       /home/apps/portal-prod/infra/backup/verificar_backup.sh \
#       >> /var/log/portal/backup-watchdog.log 2>&1
#
# SAÍDA, para quem quiser consumir por máquina (critério 22: "destino definido"):
#   * última linha, sempre em JSON, com `status`, `idade_horas` e `motivo`;
#   * exit code com significado (tabela abaixo);
#   * a saída humana vai para stderr, para o JSON não se misturar ao log.
#
#   exit 0  dentro do prazo
#   exit 1  ATRASO: o último backup confirmado é mais velho que o limite
#   exit 2  NUNCA EXECUTOU (sem marcador e sem dump na retenção local)
#   exit 3  CONFIGURAÇÃO ausente/inválida — não dá para afirmar saúde (falha
#           fechada: "não sei" não é "está tudo bem")
#   exit 4  o canal de alerta (--webhook) não recebeu a notificação
#
# Nenhum segredo é lido, impresso ou transmission: a URL do webhook e as
# credenciais S3 vêm do ambiente e nunca aparecem na saída.
set -uo pipefail

# Já existe um `pg_backup_pm2.sh` com `umask 077` no mesmo diretório; repetir
# aqui é o que garante que o marcador lido e qualquer arquivo temporário não
# fiquem legíveis por outros, mesmo com um umask mais frouxo herdado do cron.
umask 077

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"

BACKUP_DIR="${BACKUP_DIR:-$SCRIPT_DIR}"
# 26 h = 24 h de cadência + 2 h de margem. O MESMO número precisa estar no
# cron monitor do Better Stack (`expect_period_seconds` em
# infra/observability/better-stack/checks.json): se os dois divergirem, o
# alerta chega na hora errada — ou tarde demais.
BACKUP_MAX_AGE_HOURS="${BACKUP_MAX_AGE_HOURS:-26}"
ARQUIVO_RELATIVO="${BACKUP_WATCHDOG_LOGFILE:-}"
WEBHOOK_URL="${BACKUP_ALERT_WEBHOOK_URL:-}"
VERIFICAR_REMOTO="${BACKUP_WATCHDOG_CHECK_REMOTE:-1}"
MARCADOR="$BACKUP_DIR/.ultimo-backup-ok"
AGORA="$(date -u +%s)"

log() { printf '[backup-watchdog] %s\n' "$*" >&2; }
erro() { printf '[backup-watchdog] ERRO: %s\n' "$*" >&2; }

# Uma linha de JSON, sempre na stdout. Sem segredo: só estado, idade e motivo.
# Escapa mínima para o JSON montado à mão: o script não pode depender de `jq`
# num host de VPS mínimo, e um consumidor quebrado por aspas é pior que um
# campo vazio — faz o alerta ser ignorado em silêncio.
json_texto() {
    local bruto="${1:-}"
    [[ -n "$bruto" ]] || { printf 'null'; return; }
    bruto="${bruto//\\/\\\\}"
    bruto="${bruto//\"/\\\"}"
    printf '"%s"' "$bruto"
}

emitir_json() {
    local status="$1" idade="$2" motivo="$3" dump="$4" remoto="$5"
    local idade_json max_age_json dump_json
    if [[ "$idade" =~ ^[0-9]+$ ]]; then idade_json=$(( idade / 3600 )); else idade_json=null; fi
    if [[ "$BACKUP_MAX_AGE_HOURS" =~ ^[0-9]+$ ]]; then max_age_json="$BACKUP_MAX_AGE_HOURS"; else max_age_json=null; fi
    if [[ -n "$dump" && "$dump" != "null" ]]; then dump_json="$(json_texto "$dump")"; else dump_json=null; fi
    printf '{"servico":"backup-watchdog","status":"%s","idade_horas":%s,"motivo":%s,"dump":%s,"remoto_confirmado":%s,"max_age_horas":%s,"verificado_em":"%s"}\n' \
        "$status" "$idade_json" "$(json_texto "$motivo")" "$dump_json" \
        "$remoto" "$max_age_json" "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
}

config_invalida() {
    erro "$1"
    emitir_json "indisponivel" "" "$1" "" false
    exit 3
}

# --- Configuração: falha fechada -------------------------------------------
if ! [[ "$BACKUP_MAX_AGE_HOURS" =~ ^[0-9]+$ ]] || [[ "$BACKUP_MAX_AGE_HOURS" -le 0 ]]; then
    config_invalida "BACKUP_MAX_AGE_HOURS deve ser um inteiro positivo de horas (recebido: '${BACKUP_MAX_AGE_HOURS}')"
fi
if [[ ! -d "$BACKUP_DIR" ]]; then
    config_invalida "BACKUP_DIR inexistente: $BACKUP_DIR (o backup roda em outro diretório? ajuste BACKUP_DIR)"
fi
MAX_AGE_SEGUNDOS=$(( BACKUP_MAX_AGE_HOURS * 3600 ))

# --- Idade do último backup CONFIRMADO -------------------------------------
# O marcador é escrito pelo `pg_backup_pm2.sh` só depois de dump, mídia, upload
# e verificação remota. Ele é a fonte da verdade; o dump mais recente é a
# checagem cruzada (um marcador com dump apagado embaixo é motivo para
# desconfiar, não motivo para ficar tranquilo).
IDADE_MARCADOR=""
DUMP_MAIS_NOVO=""
if [[ -f "$MARCADOR" ]]; then
    if IDADE_MARCADOR="$(( AGORA - $(stat -c '%Y' "$MARCADOR") ))"; then
        log "marcador de sucesso: $MARCADOR (idade $(( IDADE_MARCADOR / 3600 ))h$(( (IDADE_MARCADOR % 3600) / 60 ))min)"
    else
        IDADE_MARCADOR=""
        erro "marcador $MARCADOR sem mtime legível; o estado do backup é desconhecido"
    fi
else
    log "marcador ausente: $MARCADOR"
fi

DUMP_MAIS_NOVO="$(find "$BACKUP_DIR" -maxdepth 1 -type f -name 'pm2-db-*.dump' -printf '%T@ %p\n' 2>/dev/null | sort -rn | head -1 | cut -d' ' -f2-)"
IDADE_DUMP=""
if [[ -n "$DUMP_MAIS_NOVO" ]]; then
    IDADE_DUMP="$(( AGORA - $(stat -c '%Y' "$DUMP_MAIS_NOVO") ))"
    log "dump mais recente: $(basename "$DUMP_MAIS_NOVO") (idade $(( IDADE_DUMP / 3600 ))h$(( (IDADE_DUMP % 3600) / 60 ))min)"
else
    log "nenhum dump pm2-db-*.dump em $BACKUP_DIR"
fi

# --- Verificação remota: backup recuperável ≠ backup local ------------------
# Sem isto o watchdog só prova que existe um arquivo na mesma máquina que
# acabou de perder o disco — que é justamente o que o backup remoto existe
# para evitar. Só roda quando o destino está configurado; `aws` ausente com
# bucket declarado é falha fechada, não "pulado".
REMOTO_CONFIRMADO=false
CHAVE_REMOTA=""
if [[ -f "$MARCADOR" ]]; then
    CHAVE_REMOTA="$(sed -n 's/^dump=//p' "$MARCADOR" | head -1)"
    REMOTO_CONFIGURADO="$(sed -n 's/^remoto=//p' "$MARCADOR" | head -1)"
fi
if [[ "$VERIFICAR_REMOTO" == "1" && -n "${BACKUP_S3_BUCKET:-}" ]]; then
    if ! command -v aws >/dev/null 2>&1; then
        config_invalida "BACKUP_S3_BUCKET está definido mas a AWS CLI não existe neste host: impossível confirmar que o backup está fora da VPS"
    fi
    if [[ -z "$CHAVE_REMOTA" ]]; then
        config_invalida "marcador sem a linha dump=, não é possível localizar o objeto remoto"
    fi
    AWS_CMD=(aws)
    [[ -z "${BACKUP_S3_ENDPOINT:-}" ]] || AWS_CMD+=(--endpoint-url "$BACKUP_S3_ENDPOINT")
    export AWS_ACCESS_KEY_ID="${BACKUP_S3_ACCESS_KEY:-${AWS_ACCESS_KEY_ID:-}}"
    export AWS_SECRET_ACCESS_KEY="${BACKUP_S3_SECRET_KEY:-${AWS_SECRET_ACCESS_KEY:-}}"
    if remote_size="$("${AWS_CMD[@]}" s3api head-object --bucket "${BACKUP_S3_BUCKET%/}" --key "db/$CHAVE_REMOTA" --query ContentLength --output text 2>/dev/null)"; then
        remote_size="${remote_size//$'\r'/}"; remote_size="${remote_size//$'\n'/}"
        if [[ "$remote_size" =~ ^[0-9]+$ ]] && [[ "$remote_size" -gt 0 ]]; then
            REMOTO_CONFIRMADO=true
            log "objeto remoto confirmado: db/$CHAVE_REMOTA ($remote_size bytes)"
        else
            config_invalida "head-object em db/$CHAVE_REMOTA devolveu tamanho inesperado: '${remote_size}'"
        fi
    else
        erro "head-object em s3://${BACKUP_S3_BUCKET%/}/db/$CHAVE_REMOTA falhou: o último backup CONFIRMADO não está mais no bucket"
    fi
fi

# --- Veredito --------------------------------------------------------------
# A ordem importa: nunca executou é diferente de atrasou, e "não sei" é
# diferente de "atrasou". Cada um sai com o seu código.
STATUS="ok"
MOTIVO="backup dentro do prazo"
SAIDA=0

if [[ -z "$IDADE_MARCADOR" && -z "$IDADE_DUMP" ]]; then
    STATUS="nunca-executou"
    MOTIVO="sem marcador de sucesso e sem dump na retencao local: o backup nunca rodou ou BACKUP_DIR mudou"
    SAIDA=2
elif [[ -n "$IDADE_MARCADOR" && "$IDADE_MARCADOR" -gt "$MAX_AGE_SEGUNDOS" ]]; then
    STATUS="atrasado"
    MOTIVO="ultimo backup confirmado ha $(( IDADE_MARCADOR / 3600 ))h, limite de ${BACKUP_MAX_AGE_HOURS}h"
    SAIDA=1
elif [[ -z "$IDADE_MARCADOR" ]]; then
    STATUS="atrasado"
    MOTIVO="existe dump local mas nenhum marcador de sucesso: a ultima execucao nao completou (upload ou ping falharam)"
    SAIDA=1
elif [[ -n "$IDADE_DUMP" && "$IDADE_DUMP" -gt "$MAX_AGE_SEGUNDOS" ]]; then
    STATUS="atrasado"
    MOTIVO="marcador recente mas o dump mais antigo tem $(( IDADE_DUMP / 3600 ))h: desconfie do marcador"
    SAIDA=1
fi

if (( SAIDA == 0 )) && [[ "${REMOTO_CONFIGURADO:-}" == "ausente" ]]; then
    STATUS="sem-destino"
    MOTIVO="o backup rodou, mas o ultimo marcador registra remoto=ausente: ha copia apenas nesta VPS"
    SAIDA=1
fi

# --- Canal de alerta opcional ----------------------------------------------
# O canal primário é o cron monitor do Better Stack (externo). Este webhook é o
# canal local para quem quer alerta no mesmo instante. Falha de envio é erro
# explícito: engolir seria transformar o watchdog em mais um falso verde.
if [[ -n "$WEBHOOK_URL" ]] && (( SAIDA != 0 )); then
    if command -v curl >/dev/null 2>&1; then
        if curl --fail --silent --show-error --max-time 20 \
            -H 'Content-Type: application/json' \
            --data "$(printf '{\"status\":\"%s\",\"idade_horas\":%s,\"motivo\":%s}' "$STATUS" "$(( ${IDADE_MARCADOR:-0} / 3600 ))" "$(json_texto "$MOTIVO")")" \
            "$WEBHOOK_URL" >/dev/null; then
            log "notificação enviada em BACKUP_ALERT_WEBHOOK_URL"
        else
            erro "BACKUP_ALERT_WEBHOOK_URL não recebeu a notificação (HTTP != 2xx, timeout ou DNS)"
            emitir_json "$STATUS" "$IDADE_MARCADOR" "$MOTIVO (alerta nao entregue)" "${DUMP_MAIS_NOVO##*/}" "$REMOTO_CONFIRMADO"
            exit 4
        fi
    else
        erro "curl ausente e BACKUP_ALERT_WEBHOOK_URL definido: notificação de atraso não entregue"
        emitir_json "$STATUS" "$IDADE_MARCADOR" "$MOTIVO (curl ausente, alerta nao entregue)" "${DUMP_MAIS_NOVO##*/}" "$REMOTO_CONFIRMADO"
        exit 4
    fi
elif (( SAIDA != 0 )) && [[ -z "$WEBHOOK_URL" ]]; then
    log "AVISO: atraso detectado sem BACKUP_ALERT_WEBHOOK_URL; o aviso chega pelo cron monitor do Better Stack (BACKUP_HEARTBEAT_URL)"
fi

case "$SAIDA" in
    0) log "OK: $MOTIVO" ;;
    1) erro "ATRASO: $MOTIVO" ;;
    2) erro "NUNCA EXECUTOU: $MOTIVO" ;;
esac

emitir_json "$STATUS" "$IDADE_MARCADOR" "$MOTIVO" "${DUMP_MAIS_NOVO##*/}" "$REMOTO_CONFIRMADO"
exit "$SAIDA"
