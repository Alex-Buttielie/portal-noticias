#!/usr/bin/env bash
# Watchdog de atraso do backup diário (item P2-01, Onda 2).
#
# =============================================================================
# POR QUE ESTE SCRIPT FOI REESCRITO, E NÃO COPIADO
# =============================================================================
# A versão do rascunho do WIP lia um marcador `.ultimo-backup-ok` e linhas
# `dump=` / `remoto=` dentro dele. VERIFICADO em `develop` (1dec732):
# `infra/backup/pg_backup_pm2.sh` **não escreve esse marcador** — ele termina em
# `log "backup concluído"` (linha 448) e sai. Ele também não faz ping de
# heartbeat em lugar nenhum.
#
# A consequência de usar o script do WIP contra o `pg_backup_pm2.sh` de develop
# seria: `MARCADOR` nunca existe, e com um dump local presente o veredito cai
# sempre em `atrasado` (linha 174-177 do WIP), exit 1, para sempre. Isso é
# fail-closed, e por isso é PIOR que não ter check: um alerta que está sempre
# vermelho ensina o time a ignorá-lo, e o dia em que o backup realmente parar
# ninguém olha.
#
# O que este script faz, então, é deduzir o estado a partir do que o
# `pg_backup_pm2.sh` de develop REALMENTE deixa no disco, e usar o marcador
# apenas se algum dia existir um produtor que o escreva.
#
# O QUE O pg_backup_pm2.sh DE DEVELOP DEIXA (verificado, com linha)
# -------------------------------------------------------------------------
#   $BACKUP_DIR/pm2-db-<UTC>.dump        publicado após pg_restore + contagem
#                                         de linhas conferida (linhas 373-375)
#   $BACKUP_DIR/pm2-media-<UTC>.tar.gz    publicado após `tar -tzf` (390)
#   $BACKUP_DIR/.pg_backup_pm2.lock       flock, sempre criado (245)
#   nada mais. Nenhum marcador, nenhum JSON, nenhum ping.
#
# POR QUE ISTO NÃO BASTA SOZINHO, E O QUE COMPLEMENTA
# -----------------------------------------------------
#   * validação só acontece QUANDO O SCRIPT RODA. Se o cron parou, se a VPS não
#     subiu, ou se o env quebrou, ninguém percebe: o próximo dia de precisar do
#     backup é o dia de descobrir que ele não existe. Daí a verificação
#     INDEPENDENTE deste script, em cadence horário;
#   * o canal externo (cron monitor do Better Stack) é o que cobre o caso que
#     nenhum watchdog na VPS pode cobrir: a VPS morta. Esse canal **precisa de
#     um pinger que ainda não existe** — registrado em
#     `infra/observability/better-stack/checks.json` -> `cron_monitor_backup`.
#
# USO (cron — a cada hora, bem antes do limite de 26 h)
#   5 * * * * /home/apps/portal-prod/infra/backup/verificar_backup.sh \
#       >> /var/log/portal/backup-watchdog.log 2>&1
#
# SAÍDA
#   * última linha, sempre em JSON, com `status`, `idade_horas` e `motivo`;
#   * exit code com significado (tabela abaixo);
#   * a saída humana vai para stderr, para o JSON não se misturar ao log.
#
#   exit 0  dentro do prazo E com cópia remota confirmada
#   exit 1  ATRASADO, ou sem destino remoto (o backup rodou mas é local-only)
#   exit 2  NUNCA EXECUTOU (sem dump na retenção local)
#   exit 3  CONFIGURAÇÃO ausente/inválida — não dá para afirmar saúde (falha
#           fechada: "não sei" não é "está tudo bem")
#   exit 4  o canal de alerta (--webhook) não recebeu a notificação
#
# Nenhum segredo é lido, impresso ou transmission: a URL do webhook e as
# credenciais S3 vêm do ambiente e nunca aparecem na saída.
set -uo pipefail

# Já existe um `pg_backup_pm2.sh` com `umask 077` no mesmo diretório; repetir
# aqui é o que garante que o arquivo temporário deste script não fique legível
# por outros, mesmo com um umask mais frouxo herdado do cron.
umask 077

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

BACKUP_DIR="${BACKUP_DIR:-$SCRIPT_DIR}"
# 26 h = 24 h de cadência + 2 h de margem. O MESMO número precisa estar no
# cron monitor do Better Stack (`expect_period_seconds` em
# infra/observability/better-stack/checks.json): se os dois divergirem, o
# alerta chega na hora errada — ou tarde demais.
BACKUP_MAX_AGE_HOURS="${BACKUP_MAX_AGE_HOURS:-26}"
# Verificar no bucket é o PADRÃO porque "backup recuperável" e "backup local"
# não são a mesma coisa: um watchdog que só prova que existe um arquivo na
# mesma máquina que acabou de perder o disco prova o oposto do que o backup
# remoto existe para evitar.
VERIFICAR_REMOTO="${BACKUP_WATCHDOG_CHECK_REMOTE:-1}"
# `1` (padrão) = ausência de destino remoto é FALHA, e sai com 1 e status
# `sem-destino`. Isto não é rigor burocrático: `pg_backup_pm2.sh:443-446` já
# avisa que, sem `BACKUP_S3_BUCKET`, "esta cópia local não sobrevive à perda do
# host". Um watchdog que dissesse "ok" nesse estado seria um verde que mente
# sobre a única propriedade que importa num backup. Para desenvolvimento local,
# onde não há bucket, ponha `BACKUP_WATCHDOG_EXIGIR_REMOTO=0` — e a saída passa
# a dizer `remoto_nao_exigido`, para que o alívio não se confunda com saúde.
EXIGIR_REMOTO="${BACKUP_WATCHDOG_EXIGIR_REMOTO:-1}"
WEBHOOK_URL="${BACKUP_ALERT_WEBHOOK_URL:-}"
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

# --- Idade do backup mais recente ------------------------------------------
# O nome do dump é `pm2-db-<UTC>.dump` (pg_backup_pm2.sh:252) e ele só é
# publicado em `mv` DEPOIS de pg_restore e da contagem de linhas batirem
# (linhas 343-375). Existir o arquivo é, portanto, prova de dump VALIDADO — o
# mesmo que o watchdog do WIP queria saber, sem depender de marcador.
DUMP_MAIS_NOVO=""
IDADE_DUMP=""
DUMP_MAIS_NOVO="$(find "$BACKUP_DIR" -maxdepth 1 -type f -name 'pm2-db-*.dump' -printf '%T@ %p\n' 2>/dev/null | sort -rn | head -1 | cut -d' ' -f2-)"
if [[ -n "$DUMP_MAIS_NOVO" ]]; then
    IDADE_DUMP="$(( AGORA - $(stat -c '%Y' "$DUMP_MAIS_NOVO") ))"
    log "dump validado mais recente: $(basename "$DUMP_MAIS_NOVO") (idade $(( IDADE_DUMP / 3600 ))h$(( (IDADE_DUMP % 3600) / 60 ))min)"
else
    log "nenhum pm2-db-*.dump em $BACKUP_DIR"
fi

# O dump é meio do backup: o script também publica a mídia
# (`pm2-media-<UTC>.tar.gz`, pg_backup_pm2.sh:390). Dump novo com mídia velho é
# sinal de retenção local desalinhada, e é motivo para desconfiar do par.
MEDIA_MAIS_NOVA=""
IDADE_MEDIA=""
MEDIA_MAIS_NOVA="$(find "$BACKUP_DIR" -maxdepth 1 -type f -name 'pm2-media-*.tar.gz' -printf '%T@ %p\n' 2>/dev/null | sort -rn | head -1 | cut -d' ' -f2-)"
if [[ -n "$MEDIA_MAIS_NOVA" ]]; then
    IDADE_MEDIA="$(( AGORA - $(stat -c '%Y' "$MEDIA_MAIS_NOVA") ))"
    log "mídia mais recente: $(basename "$MEDIA_MAIS_NOVA") (idade $(( IDADE_MEDIA / 3600 ))h$(( (IDADE_MEDIA % 3600) / 60 ))min)"
else
    log "nenhum pm2-media-*.tar.gz em $BACKUP_DIR"
fi

# Marcador: OPCIONAL e nunca exigido. Se algum dia existir um produtor que o
# escreva (item futuro), ele passa a ser a fonte preferencial e o dump vira
# checagem cruzada. Hoje, em develop, ele não existe — e continuar exigindo
# seria o falso-vermelho descrito no cabeçalho.
IDADE_MARCADOR=""
if [[ -f "$MARCADOR" ]]; then
    if IDADE_MARCADOR="$(( AGORA - $(stat -c '%Y' "$MARCADOR") ))"; then
        log "marcador de sucesso presente: $MARCADOR (idade $(( IDADE_MARCADOR / 3600 ))h$(( (IDADE_MARCADOR % 3600) / 60 ))min)"
    else
        IDADE_MARCADOR=""
        erro "marcador $MARCADOR sem mtime legível; o estado do backup é desconhecido"
    fi
fi

# O DUMP é a fonte de verdade. O marcador, quando existe, é um sinalIZADOR que
# tem de concordar com ele — e a discordância tem um sentido só:
#
#   marcador MAIS NOVO que o dump  =>  o marcador está MENTINDO. Ele afirma
#     sucesso onde não há backup novo. Isso é a pior das combinações: é
#     exatamente o "verde com nome de configuração" que este watchdog existe
#     para matar, e a idade que vale é a do DUMP (50 h atrás), não a do
#     marcador (agora).
#
#   marcador MAIS VELHO que o dump  =>  discardável; o dump é mais recente e
#     mais confiável. Não é motivo de alarme.
#
# Em develop o marcador não existe (pg_backup_pm2.sh não o escreve), então o
# caminho normal é só o dump. A lógica existe para o dia em que algum produtor
# o escrever, e para não dar a um arquivo de texto precedence sobre um dump
# que passou por `pg_restore`.
IDADE_EFETIVA="$IDADE_DUMP"
ORIGEM_EFETIVA="dump"
MARCADOR_MENTIROSO=0
if [[ -n "$IDADE_MARCADOR" ]]; then
    if [[ -z "$IDADE_DUMP" ]]; then
        IDADE_EFETIVA="$IDADE_MARCADOR"
        ORIGEM_EFETIVA="marcador"
    elif (( IDADE_MARCADOR + 3600 < IDADE_DUMP )); then
        MARCADOR_MENTIROSO=1
    fi
fi

# --- Verificação remota: backup recuperável ≠ backup local ------------------
# Chave remota: `db/<nome do dump>`, que é a MESMA forma que o
# `pg_backup_pm2.sh` usa no upload (linha 400: `DUMP_KEY="db/$(basename
# "$DUMP_FILE")"`). Não há marcador com `dump=` para ler, então a chave é
# derivada do arquivo — o que também é uma checagem de coerência: se o nome do
# objeto remoto não bater com o nome do dump local, algo renomeou um dos lados.
REMOTO_CONFIRMADO=false
FALHA_REMOTA=""
CHAVE_REMOTA=""
if [[ "$VERIFICAR_REMOTO" == "1" && -n "${BACKUP_S3_BUCKET:-}" ]]; then
    if ! command -v aws >/dev/null 2>&1; then
        config_invalida "BACKUP_S3_BUCKET está definido mas a AWS CLI não existe neste host: impossível confirmar que o backup está fora da VPS"
    fi
    if [[ -z "$DUMP_MAIS_NOVO" ]]; then
        config_invalida "BACKUP_S3_BUCKET está definido mas não há dump local para comparar com o bucket: não dá para afirmar que o backup remoto é o mesmo"
    fi
    CHAVE_REMOTA="db/$(basename "$DUMP_MAIS_NOVO")"
    AWS_CMD=(aws)
    [[ -z "${BACKUP_S3_ENDPOINT:-}" ]] || AWS_CMD+=(--endpoint-url "$BACKUP_S3_ENDPOINT")
    export AWS_ACCESS_KEY_ID="${BACKUP_S3_ACCESS_KEY:-${AWS_ACCESS_KEY_ID:-}}"
    export AWS_SECRET_ACCESS_KEY="${BACKUP_S3_SECRET_KEY:-${AWS_SECRET_ACCESS_KEY:-}}"
    tamanho_local="$(stat -c '%s' "$DUMP_MAIS_NOVO")"
    if remote_size="$("${AWS_CMD[@]}" s3api head-object --bucket "${BACKUP_S3_BUCKET%/}" --key "$CHAVE_REMOTA" --query ContentLength --output text 2>/dev/null)"; then
        remote_size="${remote_size//$'\r'/}"; remote_size="${remote_size//$'\n'/}"
        if [[ "$remote_size" =~ ^[0-9]+$ ]] && [[ "$remote_size" -gt 0 ]] && [[ "$remote_size" == "$tamanho_local" ]]; then
            # O tamanho igual ao local é o que separa "o objeto existe" de "o
            # objeto é ESTE backup". Um `head-object` que responde 200 para um
            # dump de outra execução é exatamente o tipo de verde que a
            # retenção remota deve dar.
            REMOTO_CONFIRMADO=true
            log "objeto remoto confirmado: $CHAVE_REMOTA ($remote_size bytes, igual ao local)"
        else
            config_invalida "head-object em $CHAVE_REMOTA devolveu tamanho inesperado (remoto='${remote_size}' local=${tamanho_local}): ou o objeto não é este backup, ou o upload ficou truncado"
        fi
    else
        erro "head-object em s3://${BACKUP_S3_BUCKET%/}/$CHAVE_REMOTA falhou: o backup mais recente NÃO está no bucket"
        # Flag própria, e não só um `erro` no log: "a consulta ao bucket falhou"
        # (credencial, DNS, endpoint, 403) e "não há bucket configurado" são
        # remediações DIFERENTES. Sem esta distinção, o veredito final cai no
        # ramo `sem-destino` e diz ao operador que o destino não existe — o que
        # é factualmente falso e manda a pessoa procurar a coisa errada.
        FALHA_REMOTA="head-object em ${CHAVE_REMOTA} falhou: o backup mais recente nao esta no bucket (credencial, DNS, endpoint ou 403)"
    fi
fi

# --- Veredito --------------------------------------------------------------
# A ordem importa: nunca executou é diferente de atrasou, e "não sei" é
# diferente de "atrasou". Cada um sai com o seu código.
STATUS="ok"
MOTIVO="backup dentro do prazo"
SAIDA=0

if [[ -z "$IDADE_EFETIVA" ]]; then
    STATUS="nunca-executou"
    MOTIVO="sem pm2-db-*.dump em $BACKUP_DIR: o backup nunca rodou ou mudou de BACKUP_DIR"
    SAIDA=2
elif (( IDADE_EFETIVA > MAX_AGE_SEGUNDOS )); then
    STATUS="atrasado"
    MOTIVO="backup mais recente ha $(( IDADE_EFETIVA / 3600 ))h (origem: $ORIGEM_EFETIVA), limite de ${BACKUP_MAX_AGE_HOURS}h"
    SAIDA=1
elif (( MARCADOR_MENTIROSO == 1 )); then
    STATUS="atrasado"
    MOTIVO="marcador com $(( IDADE_MARCADOR / 3600 ))h e dump com $(( IDADE_DUMP / 3600 ))h: o marcador afirma um backup que nao existe no disco (a idade que vale e a do dump)"
    SAIDA=1
elif [[ -n "$IDADE_MEDIA" ]] && (( IDADE_MEDIA > MAX_AGE_SEGUNDOS )); then
    STATUS="atrasado"
    MOTIVO="dump dentro do prazo mas a midia arquivada tem $(( IDADE_MEDIA / 3600 ))h: o backup esta pela metade"
    SAIDA=1
elif [[ -n "$IDADE_MEDIA" ]] && [[ -n "$IDADE_DUMP" ]] && (( (IDADE_MEDIA - IDADE_DUMP) > 3600 )); then
    STATUS="incompleto"
    MOTIVO="midia com $(( IDADE_MEDIA / 3600 ))h e dump com $(( IDADE_DUMP / 3600 ))h: a midia esta mais velha que o dump em mais de 1 h, e a retencao local (pg_backup_pm2.sh:438-442) apaga os dois por -mtime de forma independente, entao a midia pode sumir primeiro e o backup ficar sem conteudo"
    SAIDA=1
fi

# Sem destino remoto, o backup é local-only. `pg_backup_pm2.sh:443-446` já
# avisa que essa cópia não sobrevive à perda do host; aqui isso é veredito.
if (( SAIDA == 0 )) && [[ "$REMOTO_CONFIRMADO" != "true" ]]; then
    if [[ -n "$FALHA_REMOTA" ]]; then
        # Distingue "a consulta ao bucket FALHOU" de "não há bucket". São
        # remediações distintas e colapse-las manda o operador procurar a coisa
        # errada.
        STATUS="remoto-indisponivel"
        MOTIVO="$FALHA_REMOTA"
        SAIDA=1
    elif [[ "$EXIGIR_REMOTO" == "1" ]]; then
        STATUS="sem-destino"
        if [[ "$VERIFICAR_REMOTO" != "1" ]]; then
            MOTIVO="backup dentro do prazo, mas BACKUP_WATCHDOG_CHECK_REMOTE=0 desligou a verificacao no bucket: a copia pode estar so nesta VPS"
        else
            MOTIVO="backup dentro do prazo, mas sem copia remota confirmada: ha backup apenas nesta VPS (ver pg_backup_pm2.sh:443-446)"
        fi
        SAIDA=1
    elif [[ "$EXIGIR_REMOTO" == "0" ]]; then
        MOTIVO="backup dentro do prazo; remoto NAO exigido por BACKUP_WATCHDOG_EXIGIR_REMOTO=0 (estado de desenvolvimento, nao saude)"
    else
        config_invalida "BACKUP_WATCHDOG_EXIGIR_REMOTO deve ser 1 (padrão) ou 0; recebido: '${EXIGIR_REMOTO}'"
    fi
fi

# --- Canal de alerta opcional ----------------------------------------------
# O canal primário é o cron monitor do Better Stack (externo). Este webhook é o
# canal local para quem quer alerta no mesmo instante. Falha de envio é erro
# explícito: engolir seria transformar o watchdog em mais um falso verde.
if [[ -n "$WEBHOOK_URL" ]] && (( SAIDA != 0 )); then
    if command -v curl >/dev/null 2>&1; then
        if curl --fail --silent --show-error --max-time 20 \
            -H 'Content-Type: application/json' \
            --data "$(printf '{\"status\":\"%s\",\"idade_horas\":%s,\"motivo\":%s}' "$STATUS" "$(( ${IDADE_EFETIVA:-0} / 3600 ))" "$(json_texto "$MOTIVO")")" \
            "$WEBHOOK_URL" >/dev/null; then
            log "notificação enviada em BACKUP_ALERT_WEBHOOK_URL"
        else
            erro "BACKUP_ALERT_WEBHOOK_URL não recebeu a notificação (HTTP != 2xx, timeout ou DNS)"
            emitir_json "$STATUS" "$IDADE_EFETIVA" "$MOTIVO (alerta nao entregue)" "${DUMP_MAIS_NOVO##*/}" "$REMOTO_CONFIRMADO"
            exit 4
        fi
    else
        erro "curl ausente e BACKUP_ALERT_WEBHOOK_URL definido: notificação de atraso não entregue"
        emitir_json "$STATUS" "$IDADE_EFETIVA" "$MOTIVO (curl ausente, alerta nao entregue)" "${DUMP_MAIS_NOVO##*/}" "$REMOTO_CONFIRMADO"
        exit 4
    fi
elif (( SAIDA != 0 )) && [[ -z "$WEBHOOK_URL" ]]; then
    log "AVISO: atraso detectado sem BACKUP_ALERT_WEBHOOK_URL; o aviso chega pelo cron monitor do Better Stack (BACKUP_HEARTBEAT_URL)"
fi

case "$SAIDA" in
    0) log "OK: $MOTIVO" ;;
    1) erro "ATRASADO: $MOTIVO" ;;
    2) erro "NUNCA EXECUTOU: $MOTIVO" ;;
esac

emitir_json "$STATUS" "$IDADE_EFETIVA" "$MOTIVO" "${DUMP_MAIS_NOVO##*/}" "$REMOTO_CONFIRMADO"
exit "$SAIDA"
