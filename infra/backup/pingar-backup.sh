#!/usr/bin/env bash
# Pinger de heartbeat do backup (P2-01 → ação de `cron_monitor_backup`).
#
# =============================================================================
# O QUE ESTE SCRIPT FAZ, EM UMA FRASE
# =============================================================================
#   Ele diz ao Better Stack que o backup de HOVE rodou — e, mais importante,
#   se CALAR quando o backup não rodou. A ausência do ping é o alarme.
#
# =============================================================================
# POR QUE UM SCRIPT SEPARADO, E NÃO UM `curl` DENTRO DO pg_backup_pm2.sh
# =============================================================================
# O `checks.json` (linha 213) pede o ping "depois de `verify_s3_object` ter
# confirmado os dois objetos, e só ali", o que sugere pôr a linha no backup.
# Isso foi deliberadamente NÃO feito, e o motivo é o estado real medido em
# 2026-09-28 na VPS de produção:
#
#   * os três cron de backup recebem `Permission denied`; o `pg_backup_pm2.sh`
#     NUNCA chega a ser executado. Um ping dentro dele nunca dispararia — e o
#     `cron_monitor_backup` ficaria em `desconhecido` para sempre, que é o
#     falso-vermelho que o item existe para evitar;
#   * o `pg_backup_pm2.sh` está sendo corrigido por outro fluxo. Acoplá-lo a
#     esta mudança aumentaria o conflito sem nenhum ganho de garantia.
#
# Um pinger que VERIFICA O ESTADO POR CONTA PRÓPRIA cobre um caso que um ping
# interno não cobre: o backup não rodou. E "o backup não rodou" é exatamente o
# que o canal precisa dizer.
#
# =============================================================================
# A REGRA QUE FAZ ESTE SCRIPT EXISTIR: "RODOU" ≠ "O SCRIPT FOI CHAMADO"
# =============================================================================
# Um wrapper ingênuo seria `pg_backup_pm2.sh; curl "$URL"`. Esse wrapper dá
# o heartbeat mesmo quando o backup FALHOU — que é o pinger mentindo junto
# com o backup, e é o motivo de o programa existir.
#
# Aqui o pinger só chama o destino quando TRÊS coisas são verdade ao mesmo
# tempo, e as três são medidas, não assumidas:
#
#   1. `verificar_backup.sh` (o watchdog que já existe e já codifica a
#      política: idade, mídia pareada, marcador mentiroso, objeto remoto)
#      devolveu 0. O exit 0 dele JÁ implica cópia remota confirmada
#      (verificar_backup.sh:280-301), porque `sem-destino` e
#      `remoto-indisponivel` saem com 1. A política de 26 h, de "nunca
#      executou" e de "sem destino" NÃO foi reimplementada aqui.
#   2. O dump mais recente passa num PISO DE CONTEÚDO. Este é o item que
#      NENHUM dos mecanismos existentes cobre — ver a seção seguinte.
#   3. O objeto da MÍDIA também está no bucket. O watchdog confirma o dump
#      (verificar_backup.sh:220) e não a mídia; o contrato do cron monitor
#      fala nos DOIS objetos (checks.json:213), então os dois são conferidos.
#
# =============================================================================
# O PISO DE CONTEÚDO, E POR QUE "EXISTE UM ARQUIVO" NÃO BASTA
# =============================================================================
# MEDIDO em Postgres 16.15 real (container isolado, 2026-09-28):
#
#   banco sem tabelas de usuário ............    809 bytes,  0 TABLE DATA
#   2 tabelas, ZERO linhas ...................  4.144 bytes,  2 TABLE DATA
#   40 tabelas, ZERO linhas ................. 79.150 bytes, 40 TABLE DATA
#   1 tabela, 2.000 linhas × 200 bytes ......  8.599 bytes,  1 TABLE DATA
#
# Duas conclusões que mudaram o desenho:
#
#   * CONTAR LINHAS DE `TABLE DATA` NO TOC NÃO DETECTA DUMP VAZIO. Um banco
#     com 40 tabelas e zero linhas produz 40 linhas de TABLE DATA. A
#     discriminação que parecia óbvia está errada. O que sobra do TOC como
#     sinal de conteúdo é apenas "o arquivo tem ≥1 TABLE DATA", que separa
#     os 809 bytes de um banco sem tabelas do resto — e é por isso que ele é
#     usado, SEM aclaim que prova que há dados.
#   * `pg_restore --list` imprime `dumpId; tableoid oid DESC` e não traz
#     tamanho de bloco de dados (medido nos dois dumps). O formato de saída
#     não tem a informação. Não existe leitura barata e exata de "este dump
#     tem conteúdo" — o que resta é um PISO EM BYTES, e é isso que o script
#     faz, com o piso explícito e sobrescrevível.
#
# O dump de 48 KB citado para a produção de hoje fica ABAIXO do piso padrão
# de 1 MiB: um dump que é sintoma de esquema sem dados não vira verde só
# porque passou pelo `pg_restore --list`.
# =============================================================================
#
# USO
#   BACKUP_HEARTBEAT_URL=... bash infra/backup/pingar-backup.sh
#
#   No cron, DEPOIS do backup diário (o pinger é idempotente: pode rodar
#   quantas vezes por hora o operador quiser, e reenviar o heartbeat é
#   inofensivo para o Better Stack):
#     17 4 * * * /home/apps/portal-prod/infra/backup/pingar-backup.sh \
#         >> /var/log/portal/backup-pinger.log 2>&1
#
#   Para o PRÓPRIO PINGER saber se está vivo (ver seção "O PINGER MORREU"):
#     */10 * * * * /home/apps/portal-prod/infra/backup/pingar-backup.sh \
#         --saude-do-pinger >> /var/log/portal/backup-pinger.log 2>&1
#
# SAÍDA
#   * stdout: uma linha JSON (o veredito), sempre;
#   * stderr: a saída humana;
#   * exit code: tabela abaixo. Os códigos são distintos dos do watchdog de
#     propósito — quem watchdog "1" e quem pinger "1" estão dizendo coisas
#     diferentes, e um painel que mistura os dois é um painel que mente.
#
#   exit 0  backup real e ping ENTREGUE ao destino
#   exit 1  backup NÃO real (atrasado / nunca executou / sem destino /
#              remoto indisponível / backup pela metade). Ping NÃO enviado.
#   exit 2  backup dentro do prazo, mas o dump NÃO passa no piso de
#              conteúdo. Ping NÃO enviado. (Este é o caso do dump de 48 KB.)
#   exit 3  CONFIGURAÇÃO ausente ou inválida. Ping NÃO enviado.
#   exit 4  backup real, mas o pinger NÃO conseguiu falar com o destino
#              (DNS, rede, 4xx/5xx, token revogado).
#   exit 5  o pinger não conseguiu nem AVALIAR o backup (watchdog ausente ou
#              quebrado). Não é "está tudo bem": é "não sei".
#   exit 6  modo local sem `BACKUP_HEARTBEAT_URL`: o veredito foi calculado e
#              NENHUM ping foi enviado. NÃO é saúde — é ausência de canal.
#
# SEGREDOS
#   A URL de heartbeat é CREDENCIAL: quem a tiver consegue anunciar um
#   backup que não houve. Ela vem de `BACKUP_HEARTBEAT_URL`, nunca de
#   arquivo versionado, e NUNCA é impressa — nem no erro, nem no `ps`, nem
#   no log. O `curl` a recebe por stdin (`--config -`), fora do argv.
set -uo pipefail

# `pg_backup_pm2.sh` também usa `umask 077` no mesmo diretório; repetir aqui
# é o que garante que o arquivo de estado deste script não fique legível por
# outros, mesmo com um umask mais frouxo herdado do cron.
umask 077

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$SCRIPT_DIR/../.." && pwd)"
WATCHDOG="${BACKUP_WATCHDOG:-$SCRIPT_DIR/verificar_backup.sh}"

# O MESMO número do watchdog e do `expect_period_seconds` do cron monitor
# (checks.json:202, 26 h = 24 h + 2 h de margem). Se os três divergirem, o
# alerta chega na hora errada — ou tarde demais.
BACKUP_MAX_AGE_HOURS="${BACKUP_MAX_AGE_HOURS:-26}"
BACKUP_DIR="${BACKUP_DIR:-$SCRIPT_DIR}"

# Piso de conteúdo do dump, em BYTES. O padrão (1 MiB) está deliberadamente
# MUITO acima dos 48 KB do dump vazio medido em produção, e muito abaixo de um
# backup real de um portal com conteúdo. É um piso, não uma prova: quem
# souber o tamanho do dump real de produção deve subir este valor para perto
# dele (com folga), em vez de deixar o padrão adivinhar.
PISO_BYTES="${BACKUP_PING_TAMANHO_MINIMO_BYTES:-1048576}"
# `0` desliga o piso de conteúdo. É um estado de DESENVOLVIMENTO, e o script
# diz isso em voz alta na saída: um piso desligado devolve "ok" para o dump
# vazio, e quem lê o painel precisa poder ver essa diferença.
EXIGIR_CONTEUDO="${BACKUP_PING_EXIGIR_CONTEUDO:-1}"
TIMEOUT_SEGUNDOS="${BACKUP_PING_TIMEOUT_SEGUNDOS:-20}"
# `1` = exigir que o objeto da MÍDIA também esteja no bucket (o contrato do
# cron monitor fala nos dois objetos; o watchdog só confirma o dump).
EXIGIR_MEDIA_REMOTA="${BACKUP_PING_EXIGIR_MEDIA_REMOTA:-1}"
# `0` = não rodar a checagem ESTRUTURAL do archive (`pg_restore --list`),
# deixando só o piso em bytes. Existe para DEVELOPMENT e para o teste
# isolar uma camada da outra; em produção o padrão é 1, e desligar isso é o
# mesmo tipo de decisión que desligar o piso inteiro: o script avisa.
PULAR_ESTRUTURA="${BACKUP_PING_PULAR_ESTRUTURA:-0}"

HEARTBEAT_URL="${BACKUP_HEARTBEAT_URL:-}"
ESTADO_FILE="${BACKUP_PING_ESTADO_FILE:-$BACKUP_DIR/.ping-backup-ultimo.json}"
AGORA="$(date -u +%s)"

log() { printf '[backup-pinger] %s\n' "$*" >&2; }
erro() { printf '[backup-pinger] ERRO: %s\n' "$*" >&2; }

# Escape mínimo para JSON montado à mão, com a mesma razão do watchdog
# (verificar_backup.sh:100-106): o host de VPS mínimo não tem `jq`, e um
# consumidor quebrado por aspas é pior que um campo vazio.
json_texto() {
    local bruto="${1:-}"
    [[ -n "$bruto" ]] || { printf 'null'; return; }
    bruto="${bruto//\\/\\\\}"
    bruto="${bruto//\"/\\\"}"
    printf '"%s"' "$bruto"
}

# Grava o estado do pinger de forma ATÔMICA (temporário + `mv` no mesmo
# diretório). Sem isso, um leitor concorrente — o `--saude-do-pinger` — pode
# ler um arquivo pela metade e concluir que o pinger está morto quando ele
# está no meio de uma execução.
gravar_estado() {
    local conteudo="$1" tmp
    tmp="$(mktemp "${ESTADO_FILE}.XXXXXX" 2>/dev/null)" || return 1
    printf '%s\n' "$conteudo" > "$tmp" || { rm -f "$tmp"; return 1; }
    mv -f "$tmp" "$ESTADO_FILE" || { rm -f "$tmp"; return 1; }
}

emitir_json() {
    local status="$1" motivo="$2" dump="$3" bytes="$4" piso="$5" \
          ping="$6" codigo="$7" destino="$8"
    local bytes_json piso_json dump_json
    if [[ "$bytes" =~ ^[0-9]+$ ]]; then bytes_json=$bytes; else bytes_json=null; fi
    if [[ "$piso" =~ ^[0-9]+$ ]]; then piso_json=$piso; else piso_json=null; fi
    if [[ -n "$dump" && "$dump" != "null" ]]; then dump_json="$(json_texto "$dump")"; else dump_json=null; fi
    printf '{"servico":"backup-pinger","status":"%s","motivo":%s,"dump":%s,"bytes":%s,"piso_bytes":%s,"ping_enviado":%s,"saida":%s,"destino_configurado":%s,"verificado_em":"%s"}\n' \
        "$status" "$(json_texto "$motivo")" "$dump_json" "$bytes_json" \
        "$piso_json" "$ping" "$codigo" "$destino" "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
}

# =============================================================================
# MODO 2 — SAÚDE DO PRÓPRIO PINGER
# =============================================================================
# Um pinger que depende de rede externa é um ponto único de falha: se ele
# para de rodar, o `cron_monitor_backup` continua em `desconhecido` — o mesmo
# estado de "o backup parou", com a mesma página, e a pessoa vai procurar o
# backup quando o defeito é o pinger. Ver o README desta pasta, §"O pinger
# morreu", para o raciocínio inteiro.
#
# A resposta é um arquivo de estado local com mtime atualizado em TODA
# execução (inclusive as que falham), lido por uma entrada de cron SEPARADA
# desta. Separada de propósito: se a mesma entrada de cron fosse a que
# executa o ping, um pinger quebrado não teria como reportar que quebrou.
saude_do_pinger() {
    local limite_horas="${BACKUP_PING_SINAL_IDADE_HORAS:-1}"
    local motivo status codigo
    if [[ ! "$limite_horas" =~ ^[0-9]+$ ]] || (( limite_horas <= 0 )); then
        erro "BACKUP_PING_SINAL_IDADE_HORAS deve ser um inteiro positivo de horas (recebido: '${limite_horas}')"
        emitir_json "indisponivel" "BACKUP_PING_SINAL_IDADE_HORAS invalido" "" "" "" false 3 true
        exit 3
    fi
    if [[ ! -f "$ESTADO_FILE" ]]; then
        log "nenhum estado do pinger em $ESTADO_FILE: o pinger NUNCA rodou neste host (ou BACKUP_PING_ESTADO_FILE mudou de lugar)"
        emitir_json "nunca-executou" "sem arquivo de estado do pinger em $ESTADO_FILE" "" "" "" false 1 true
        exit 1
    fi
    local mtime idade
    mtime="$(stat -c '%Y' "$ESTADO_FILE" 2>/dev/null)"
    if [[ -z "$mtime" ]]; then
        erro "estado do pinger sem mtime legível: $ESTADO_FILE"
        emitir_json "indisponivel" "arquivo de estado sem mtime legivel" "" "" "" false 3 true
        exit 3
    fi
    idade=$(( AGORA - mtime ))
    if (( idade > limite_horas * 3600 )); then
        log "O PRÓPRIO PINGER está parado: última execução há $(( idade / 3600 ))h (limite ${limite_horas}h)"
        log "isso NÃO é 'o backup parou' — é o pinger. O backup pode estar;"
        log "o canal é que não está dizendo. Verifique o cron e o log do pinger."
        emitir_json "pinger-parado" "ultima execucao ha $(( idade / 3600 ))h, acima do limite de ${limite_horas}h" "" "" "" false 1 true
        exit 1
    fi
    status="$(sed -n 's/.*"status":"\([^"]*\)".*/\1/p' "$ESTADO_FILE" 2>/dev/null | head -1)"
    log "pinger vivo (execução de $(( idade / 60 )) min atrás); última execução Bakeup= '${status:-desconhecido}'"
    emitir_json "pinger-vivo" "ultima execucao ha $(( idade / 60 ))min" "" "" "" false 0 true
    exit 0
}

if [[ "${1:-}" == "--saude-do-pinger" ]]; then
    saude_do_pinger
fi

# =============================================================================
# CONFIGURAÇÃO — falha fechada
# =============================================================================
if [[ ! "$BACKUP_MAX_AGE_HOURS" =~ ^[0-9]+$ ]] || (( BACKUP_MAX_AGE_HOURS <= 0 )); then
    erro "BACKUP_MAX_AGE_HOURS deve ser um inteiro positivo de horas (recebido: '${BACKUP_MAX_AGE_HOURS}')"
    emitir_json "indisponivel" "BACKUP_MAX_AGE_HOURS invalido" "" "" "$PISO_BYTES" false 3 "${HEARTBEAT_URL:+true}"
    exit 3
fi
if [[ ! -f "$WATCHDOG" ]]; then
    erro "watchdog de backup ausente: $WATCHDOG (BACKUP_WATCHDOG aponta para onde?)"
    emitir_json "indisponivel" "watchdog de backup ausente em $WATCHDOG" "" "" "$PISO_BYTES" false 3 "${HEARTBEAT_URL:+true}"
    exit 5
fi

DESTINO_CONFIGURADO=false
[[ -n "$HEARTBEAT_URL" ]] && DESTINO_CONFIGURADO=true
if [[ "$DESTINO_CONFIGURADO" != "true" ]]; then
    # Não é erro de configuração do pinger: é ausência de canal. O veredito
    # do backup ainda é calculado e impresso — mas NENHUM ping é enviado, e o
    # exit 6 é separado do 0 justamente para que "não tenho para onde dizer"
    # nunca seja lido como "está tudo bem".
    log "BACKUP_HEARTBEAT_URL não configurado: o veredito será calculado e NENHUM ping será enviado"
    log "este exit 6 NÃO é saúde do backup; é ausência de canal externo"
fi

# =============================================================================
# PASSO 1 — O BACKUP RODOU? (política do watchdog, não reimplementada aqui)
# =============================================================================
saida_watchdog=""
codigo_watchdog=0
saida_watchdog="$(BACKUP_MAX_AGE_HOURS="$BACKUP_MAX_AGE_HOURS" \
                   BACKUP_DIR="$BACKUP_DIR" \
                   bash "$WATCHDOG" 2>>"${BACKUP_PING_LOG_TMP:-/dev/null}")"
codigo_watchdog=$?

status_watchdog="$(tail -n 1 <<<"$saida_watchdog" \
    | sed -n 's/.*"status":"\([^"]*\)".*/\1/p')"
status_watchdog="${status_watchdog:-desconhecido}"
motivo_watchdog="$(tail -n 1 <<<"$saida_watchdog" \
    | sed -n 's/.*"motivo":\(.*\),"dump".*/\1/p')"
motivo_watchdog="${motivo_watchdog:-veredito do watchdog nao foi legivel}"
DUMP_MAIS_NOVO="$(tail -n 1 <<<"$saida_watchdog" \
    | sed -n 's/.*"dump":\(null\|"[^"]*"\).*/\1/p')"
DUMP_MAIS_NOVO="${DUMP_MAIS_NOVO#\"}"; DUMP_MAIS_NOVO="${DUMP_MAIS_NOVO%\"}"

# =============================================================================
# PASSO 2 — O DUMP TEM CONTEÚDO?
# =============================================================================
# Roda mesmo quando o watchdog reprovou, para que o motivo reportado seja o
# MAIS ESPECÍFICO possível: "o backup está atrasado E o último dump era
# vazio" é uma informação; "o backup está atrasado" esconde a segunda.
bytes_dump=""
piso_ativo="$PISO_BYTES"
piso_fracassa=0
PISO_MOTIVO=""

if [[ "$EXIGIR_CONTEUDO" == "0" ]]; then
    piso_ativo=0
    PISO_MOTIVO="BACKUP_PING_EXIGIR_CONTEUDO=0: o piso de conteudo esta DESLIGADO, e um dump vazio seria aceito como ok"
    log "AVISO: piso de conteúdo DESLIGADO por BACKUP_PING_EXIGIR_CONTEUDO=0"
elif ! [[ "$PISO_BYTES" =~ ^[0-9]+$ ]]; then
    erro "BACKUP_PING_TAMANHO_MINIMO_BYTES deve ser um inteiro de bytes (recebido: '${PISO_BYTES}')"
    emitir_json "indisponivel" "BACKUP_PING_TAMANHO_MINIMO_BYTES invalido" "$DUMP_MAIS_NOVO" "" "$Piso_BYTES" false 3 "$DESTINO_CONFIGURADO"
    exit 3
fi

if [[ -n "$DUMP_MAIS_NOVO" && "$DUMP_MAIS_NOVO" != "null" && "$piso_ativo" -gt 0 ]]; then
    CAMINHO_DUMP="$BACKUP_DIR/$DUMP_MAIS_NOVO"
    if [[ ! -f "$CAMINHO_DUMP" ]]; then
        # O watchdog nomeou um dump que não está no disco. Discrepância entre
        # o que ele mediu e o que existe: não se pode afirmar nada sobre o
        # conteúdo de um arquivo que não existe.
        PISO_MOTIVO="o dump nomeado pelo watchdog nao existe em disco: $CAMINHO_DUMP"
        piso_fracassa=1
    else
        bytes_dump="$(stat -c '%s' "$CAMINHO_DUMP" 2>/dev/null)"
        if [[ ! "$bytes_dump" =~ ^[0-9]+$ ]]; then
            PISO_MOTIVO="nao foi possivel ler o tamanho de $CAMINHO_DUMP"
            piso_fracassa=1
            bytes_dump=""
        elif (( bytes_dump < piso_ativo )); then
            PISO_MOTIVO="o dump tem $bytes_dump bytes, abaixo do piso de $piso_ativo: um dump deste tamanho e sintoma de esquema sem dados, e nao de um backup do portal com conteudo"
            piso_fracassa=1
        elif [[ "$PULAR_ESTRUTURA" == "1" ]]; then
            log "AVISO: checagem estrutural DESLIGADA por BACKUP_PING_PULAR_ESTRUTURA=1; o veredito se apoia SÓ no piso de $piso_ativo bytes"
        elif ! command -v pg_restore >/dev/null 2>&1; then
            # Fail closed: sem `pg_restore` não dá para afirmar que o
            # arquivo é um archive legível, e "não sei" não é "está tudo
            # bem". O dump grande o bastante para passar do piso, mas
            # estruturalmente ilegível, é exatamente o que este ramo pega.
            PISO_MOTIVO="pg_restore ausente neste host: nao da para confirmar que o dump de $bytes_dump bytes e um archive valido"
            piso_fracassa=1
        elif ! pg_restore --list "$CAMINHO_DUMP" >/dev/null 2>&1; then
            PISO_MOTIVO="pg_restore --list rejeitou o dump de $bytes_dump bytes: o archive esta corrompido"
            piso_fracassa=1
        else
            toc="$(pg_restore --list "$CAMINHO_DUMP" 2>/dev/null | grep -c 'TABLE DATA' || true)"
            if [[ ! "$toc" =~ ^[0-9]+$ ]] || (( toc < 1 )); then
                # Sinal fraco e declarado como tal: separa o archive de 809
                # bytes de um banco sem tabelas do resto. NÃO prova que há
                # dados — medido: 40 tabelas com ZERO linhas também produzem
                # 40 linhas de TABLE DATA. É o piso em bytes que carrega a
                # garantia; isto é um corrimão extra.
                PISO_MOTIVO="o archive nao lista nenhum TABLE DATA (${bytes_dump} bytes): o dump pode ser de um banco sem tabelas de usuario"
                piso_fracassa=1
            else
                log "dump conteudo: $DUMP_MAIS_NOVO, $bytes_dump bytes (piso $piso_ativo), $toc entradas TABLE DATA"
            fi
        fi
    fi
fi

# =============================================================================
# PASSO 3 — O OBJETO DA MÍDIA TAMBÉM ESTÁ NO BUCKET?
# =============================================================================
# O watchdog confirma o objeto do DUMP (verificar_backup.sh:220) e não
# confirma o da mídia. O contrato do cron monitor fala nos DOIS objetos
# (checks.json:213) — e um backup só com dump, sem a mídia que o serve, é
# metade do backup.
media_fracassa=0
if [[ "$EXIGIR_MEDIA_REMOTA" == "1" ]] && (( codigo_watchdog == 0 )) && [[ -n "${BACKUP_S3_BUCKET:-}" ]]; then
    if ! command -v aws >/dev/null 2>&1; then
        log "AVISO: BACKUP_S3_BUCKET definido e AWS CLI ausente: a confirmacao do objeto da MIDIA nao pode ser feita"
        media_fracassa=1
    else
        MEDIA_MAIS_NOVA="$(find "$BACKUP_DIR" -maxdepth 1 -type f -name 'pm2-media-*.tar.gz' \
            -printf '%T@ %p\n' 2>/dev/null | sort -rn | head -1 | cut -d' ' -f2-)"
        if [[ -z "$MEDIA_MAIS_NOVA" ]]; then
            log "AVISO: nenhum pm2-media-*.tar.gz em $BACKUP_DIR: nao ha midia para confirmar no bucket"
            media_fracassa=1
        else
            AWS_CMD=(aws)
            [[ -z "${BACKUP_S3_ENDPOINT:-}" ]] || AWS_CMD+=(--endpoint-url "$BACKUP_S3_ENDPOINT")
            export AWS_ACCESS_KEY_ID="${BACKUP_S3_ACCESS_KEY:-${AWS_ACCESS_KEY_ID:-}}"
            export AWS_SECRET_ACCESS_KEY="${BACKUP_S3_SECRET_KEY:-${AWS_SECRET_ACCESS_KEY:-}}"
            chave_media="media/$(basename "$MEDIA_MAIS_NOVA")"
            tamanho_local="$(stat -c '%s' "$MEDIA_MAIS_NOVA" 2>/dev/null)"
            tamanho_remoto="$("${AWS_CMD[@]}" s3api head-object \
                --bucket "${BACKUP_S3_BUCKET%/}" --key "$chave_media" \
                --query ContentLength --output text 2>/dev/null)"
            tamanho_remoto="${tamanho_remoto//$'\r'/}"; tamanho_remoto="${tamanho_remoto//$'\n'/}"
            if [[ ! "$tamanho_remoto" =~ ^[0-9]+$ ]] || [[ "$tamanho_remoto" != "$tamanho_local" ]]; then
                log "ERRO: o objeto da midia s3://${BACKUP_S3_BUCKET%/}/$chave_media nao confere (local=${tamanho_local:-?} remoto=${tamanho_remoto:-sem-resposta})"
                media_fracassa=1
            else
                log "midia remota confirmada: $chave_media ($tamanho_remoto bytes, igual ao local)"
            fi
        fi
    fi
fi

# =============================================================================
# VEREDITO — a ordem importa
# =============================================================================
STATUS="ok"
MOTIVO="backup verificado e conteudo dentro do piso"
SAIDA=0
PING_ENVIADO=false

if (( codigo_watchdog != 0 )); then
    # 3 = "não sei" (configuração). Sai com 3, não com 1: um watchdog que não
    # pôde ser rodado não é um backup que está ruim.
    if [[ "$codigo_watchdog" == "3" ]]; then
        STATUS="indisponivel"
        MOTIVO="o watchdog nao pode afirmar nada: $motivo_watchdog"
        SAIDA=3
    else
        STATUS="backup-nao-verificado"
        MOTIVO="watchdog reprovou (exit $codigo_watchdog, status $status_watchdog): $motivo_watchdog"
        SAIDA=1
    fi
elif (( piso_fracassa == 1 )); then
    STATUS="conteudo-insuficiente"
    MOTIVO="$PISO_MOTIVO"
    SAIDA=2
elif (( media_fracassa == 1 )); then
    STATUS="midia-sem-confirmacao"
    MOTIVO="o dump esta no bucket, mas o objeto da midia nao foi confirmado: um backup sem midia nao e um backup do portal"
    SAIDA=1
fi

# O piso DESLIGADO é o único caminho em que o veredito `ok` convive com uma
# ressalva — e a ressalva tem que aparecer no `status`, não numa linha de
# log que ninguém lê. Um painel que mostra "ok" sem mostrar que o piso está
# desligado é o falso verde de volta, por outro caminho.
if (( SAIDA == 0 )) && [[ -n "$PISO_MOTIVO" ]]; then
    STATUS="ok-sem-piso"
    MOTIVO="$PISO_MOTIVO"
fi

# O estado local é gravado ANTES de qualquer tentativa de rede, e de novo
# depois. Assim, um pinger que não consegue falar com o destino ainda deixa
# um rastro local do que ele tentou — que é a evidência que o operador
# precisa para separar "a internet caiu" de "o pinger está quebrado".
if [[ "$PING_ENVIADO" == "false" ]]; then
    gravar_estado "$(emitir_json "$STATUS" "$MOTIVO" "$DUMP_MAIS_NOVO" "$bytes_dump" "$piso_ativo" false "$SAIDA" "$DESTINO_CONFIGURADO")" \
        || log "AVISO: nao foi possivel gravar o estado do pinger em $ESTADO_FILE"
fi

# =============================================================================
# O PING — só aqui, e só com os três veredictos acima
# =============================================================================
if (( SAIDA != 0 )); then
    log "veredito=$STATUS (exit $SAIDA): NENHUM ping enviado. A ausência do heartbeat é o alarme."
elif [[ "$DESTINO_CONFIGURADO" != "true" ]]; then
    log "veredito=ok, mas BACKUP_HEARTBEAT_URL ausente: nenhum ping enviado"
    STATUS="sem-destino"
    MOTIVO="backup verificado, mas nao ha canal externo configurado: o cron monitor continuara em desconhecido"
    SAIDA=6
else
    # A URL vai por STDIN, fora do argv: com a URL direto no `argv`, qualquer
    # outro usuário da VPS lê a credencial em `ps` durante a execução. O
    # `printf` é um BUILTIN do bash, então a URL não aparece no argv de
    # processo nenhum — nem do curl, nem do printf.
    if printf 'url = "%s"\n' "$HEARTBEAT_URL" \
        | curl --config - --fail --silent --output /dev/null \
               --max-time "$TIMEOUT_SEGUNDOS" 2>/dev/null; then
        PING_ENVIADO=true
        log "heartbeat ENTREGUE: o Better Stack sabe agora que houve backup verificado"
    else
        codigo_curl=$?
        # A URL NÃO é impressa aqui, nem em parte. O código do curl basta para
        # a remediação (6=DNS, 7=conexão, 22=HTTP, 28=timeout), e um log com
        # a credencial dentro seria o vazamento que o token tenta evitar.
        STATUS="ping-nao-entregue"
        MOTIVO="o backup esta verificado, mas o heartbeat nao foi aceito pelo destino (curl exit $codigo_curl: DNS, rede, 4xx/5xx ou token revogado). O cron monitor vai cair em desconhecido em ate 26 h, e a causa probable NAO e o backup"
        SAIDA=4
        erro "$MOTIVO"
    fi
fi

linha_final="$(emitir_json "$STATUS" "$MOTIVO" "$DUMP_MAIS_NOVO" "$bytes_dump" "$piso_ativo" "$PING_ENVIADO" "$SAIDA" "$DESTINO_CONFIGURADO")"
gravar_estado "$linha_final" || log "AVISO: nao foi possivel gravar o estado do pinger em $ESTADO_FILE"

case "$SAIDA" in
    0) log "OK: $MOTIVO" ;;
    1) erro "BACKUP NAO VERIFICADO: $MOTIVO" ;;
    2) erro "CONTEUDO INSUFICIENTE: $MOTIVO" ;;
    3) erro "CONFIGURACAO: $MOTIVO" ;;
    4) erro "PING NAO ENTREGUE: $MOTIVO" ;;
    6) erro "SEM CANAL: $MOTIVO" ;;
esac
printf '%s\n' "$linha_final"
exit "$SAIDA"
