#!/usr/bin/env bash
# Pinger de heartbeat da saúde das filas (P2-01 → ação de `cron_monitor_filas`).
#
# =============================================================================
# O QUE ESTE SCRIPT FAZ, EM UMA FRASE
# =============================================================================
#   A cada 5 minutos: roda `manage.py saude_filas --json`, anexa o registro ao
#   JSONL que o Loki já indexa, e avisa o Better Stack **só** quando o
#   relatório saiu com 0.
#
# =============================================================================
# POR QUE UM SCRIPT, E NÃO A LINHA DE CRON DE 4 LINHAS DO PROVISIONAMENTO
# =============================================================================
# `config.alloy:286-288` e `infra/filas/PROVISIONAMENTO.md` §2.3 propõem
#     */5 * * * * .venv/bin/python manage.py saude_filas --json >> …jsonl
# Isso resolve METADE do problema: produz o arquivo que o
# `loki.source.file "filas"` lê. Não resolve o outro:
#
#   * o heartbeat não existe — e sem pinger o `cron_monitor_filas` fica em
#     `desconhecido` desde o primeiro dia, que é o alarme-que-dispara-sempre
#     que o P2-01 registrou;
#   * `>>` num cron de 5 minutos é crescimento sem limite;
#   * o `--ignorar-saida` sugerido no PROVISIONAMENTO §2.3 item 1 é
#     DIRETAMENTE CONTRADITÓRIO com a regra de reprovação do mesmo arquivo
#     (checks.json:228, "crítico se o processo sai != 0"). Com
#     `--ignorar-saida` o exit é sempre 0, um monitor que trata 0 como
#     "saúde" nunca alarmaria, e o item 2 do §2.3 — "distinguir 1 de 3" —
#     fica impossível. Este script NÃO usa `--ignorar-saida`.
#
# =============================================================================
# OS TRÊS ESTADOS E OS TRÊS CÓDIGOS — A DISTINÇÃO QUE NÃO SE APLICA
# =============================================================================
# `backend/config/management/commands/saude_filas.py:10-19` define 0 `ok`,
# 1 `degradado`, 3 `desconhecido`. O 3 é DELIBERADAMENTE diferente do 0, e
# o 2 é reservado ao argparse. Este script:
#
#   * NÃO remapeia nada — o exit do `saude_filas` é o exit deste script,
#     para que a cadeia inteira (cron, systemd, quem olha o log) fale o mesmo
#     idioma que o comando;
#   * só envia o heartbeat no 0;
#   * anexa ao JSONL nos TRÊS casos, inclusive no 3. Um relatório
#     `desconhecido` é a informação mais importante que existe: é ela que
#     diz "não medi", e um JSONL onde só entram os `ok` é um JSONL que mente
#     por omissão — que é a forma mais cara de mentir, porque o painel fica
#     bonito.
#
# =============================================================================
# O JSONL NÃO CRESCE SEM LIMITE — O QUE FOI ESCOLHIDO, E POR QUÊ
# =============================================================================
# MEDIDO: uma linha de `saude_filas --json` tem ~2,3 KB. A 5 min são 288
# linhas/dia ≈ 660 KB/dia ≈ 240 MB/ano, num diretório de estado que é o
# MESMO que o Alloy lê.
#
# ESCOLHIDO: **rotação por contagem de linhas, com sobreposição de uma
# geração.** Quando o arquivo chega a `PING_FILAS_MAX_LINHAS`, ele é
# renomeado para `<arquivo>.1` (substituindo o `.1` anterior) e um arquivo
# novo é criado. O total em disco fica em, no máximo, ~2x o teto — 2x576
# linhas ≈ 2,6 MB, e o teto é configurável.
#
# POR QUE ROTAÇÃO, E NÃO TRUNCAMENTO ("manter as últimas N")
#   `loki.source.file` segue o arquivo por posição de byte. Truncar o
#   arquivo faz a posição do leitor deixar de existir, e o Loki ou pula
#   linhas ou relê do começo. Renomear e recriar dá ao leitor um arquivo
#   NOVO, com posição 0, e é a rotação que o `file_match` do Loki espera.
#   O `.1` anterior é descartado — e a janela de 24 h do `ignore_older_than`
#   (`config.alloy:302`) é maior que o tempo que 576 linhas cobrem, então o
#   que se perde na rotação já estava fora da janela de leitura.
#
# POR QUE O `.1` ANTIGO É DESCARTADO, E NÃO UM `.2` QUE CRESCE
#   Um `.2` seria "mais um lugar para o Loki não ler" e "mais um lugar para
#   o disco encher". O `ignore_older_than = "24h"` já define que nada com
#   mais de um dia interessa ao coletor; guardar duas gerações além do
#   arquivo ativo seria guardar dado que ninguém vai ler.
#
# =============================================================================
# O PINGER MORREU? — O SINAL LOCAL
# =============================================================================
# O mesmo raciocínio do pinger de backup, e a mesma resposta: um arquivo de
# estado com mtime atualizado em TODA execução, inclusive nas que falham,
# lido por `--saude-do-pinger` a partir de uma entrada de cron SEPARADA. A
# separação é o ponto: se a mesma entrada de cron fizesse as duas coisas, um
# pinger quebrado não teria como reportar que está quebrado.
#
# Para as filas existe ainda um sinal a mais, e ele é gratuito: o JSONL.
# Uma entrada de cron de 5 minutos que deixou de escrever deixa o arquivo
# com a última linha OLD — o painel de filas mostra a última leitura como
# se fosse de agora. O `--saude-do-pinger` também checa a idade da ÚLTIMA
# LINHA do JSONL, que é o mesmo dado que o painel exibe, visto do lado que
# o painel não mostra.
#
# =============================================================================
# USO
#   # uma vez por hora, no cron principal (o intervalo real é de 5 min):
#   3 * * * * /home/apps/portal-prod/infra/filas/pingar-filas.sh \
#       >> /var/log/portal/filas-pinger.log 2>&1
#
#   # a cada 10 min, numa entrada SEPARADA — é quem vigia o pinger:
#   7 * * * * /home/apps/portal-prod/infra/filas/pingar-filas.sh \
#       --saude-do-pinger >> /var/log/portal/filas-pinger.log 2>&1
#
# SAÍDA
#   * stdout: uma linha JSON;
#   * stderr: a saída humana;
#   * exit: o do `saude_filas` (0/1/3), mais os do próprio pinger.
#
#   exit 0  `ok` e ping ENTREGE
#   exit 1  `degradado` — medido e com problema. Ping NÃO enviado.
#   exit 3  `desconhecido` — não foi possível verificar. Ping NÃO enviado.
#           (3 e não 1 é deliberado: são remediações diferentes.)
#   exit 4  relatório healthy, mas o destino NÃO aceitou o heartbeat
#   exit 5  CONFIGURAÇÃO ausente/inválida
#   exit 6  modo local sem `FILAS_HEARTBEAT_URL`: veredito calculado, nenhum
#           ping enviado. NÃO é saúde.
#   exit 7  o JSONL não pôde ser escrito (disco cheio, permissão). O relatório
#           é perdido para o Loki, e isso precisa ser dito, não engolido.
#
# SEGREDOS
#   `FILAS_HEARTBEAT_URL` é CREDENCIAL — quem a tiver anuncia uma leitura de
#   filas que não houve. Vem do ambiente, nunca de arquivo versionado, e nunca
#   é impressa: o `curl` a recebe por stdin (`--config -`), fora do argv.
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Onde o `manage.py` está e qual Python roda a aplicação. Em DEV/HOMOLOG/PROD
# é o mesmo `.venv` que o PM2 e o systemd usam — usar OUTRO interpretador
# mediria um ambiente diferente do que está em produção, que é a forma
# elegante de publicar um verde que não existe.
APP_DIR="${PING_FILAS_APP_DIR:-$(cd "$SCRIPT_DIR/../.." && pwd)/backend}"
PYTHON="${PING_FILAS_PYTHON:-$APP_DIR/.venv/bin/python}"
[ -x "$PYTHON" ] || PYTHON="${PING_FILAS_PYTHON:-python3}"

# O MESMO arquivo que `ALLOY_FILAS_JSON_PATH` aponta (alloy.env.example:93).
# Se os dois divergirem, o painel de filas fica vazio sem erro nenhum — o
# pior estado possível, e por isso o valor padrão é lido do env do Alloy
# quando ele está presente.
JSONL="${PING_FILAS_JSONL:-${ALLOY_FILAS_JSON_PATH:-/var/lib/portal-noticias/saude_filas.jsonl}}"

HEARTBEAT_URL="${FILAS_HEARTBEAT_URL:-}"
# Teto de linhas do arquivo ativo. 576 linhas a cada 5 min ≈ 48 h de
# histórico no arquivo, bem acima da janela de 24 h que o `ignore_older_than`
# do Loki lê — então a rotação nunca come dado que alguém ia ler.
MAX_LINHAS="${PING_FILAS_MAX_LINHAS:-576}"
TIMEOUT_SEGUNDOS="${PING_FILAS_TIMEOUT_SEGUNDOS:-20}"
LIMITE_SAUDADE_MIN="${PING_FILAS_SINAL_IDADE_MINUTOS:-20}"
ESTADO_FILE="${PING_FILAS_ESTADO_FILE:-${JSONL}.pinger-estado}"

log() { printf '[filas-pinger] %s\n' "$*" >&2; }
erro() { printf '[filas-pinger] ERRO: %s\n' "$*" >&2; }

json_texto() {
    local bruto="${1:-}"
    [[ -n "$bruto" ]] || { printf 'null'; return; }
    bruto="${bruto//\\/\\\\}"
    bruto="${bruto//\"/\\\"}"
    printf '"%s"' "$bruto"
}

gravar_estado() {
    local conteudo="$1" tmp
    tmp="$(mktemp "${ESTADO_FILE}.XXXXXX" 2>/dev/null)" || return 1
    printf '%s\n' "$conteudo" > "$tmp" || { rm -f "$tmp"; return 1; }
    mv -f "$tmp" "$ESTADO_FILE" || { rm -f "$tmp"; return 1; }
}

emitir_json() {
    local status="$1" estado_json="$2" codigo_saude="$3" motivo="$4" \
          linhas="$5" rotacoes="$6" ping="$7" codigo="$8" destino="$9"
    local linhas_json rotacoes_json
    [[ "$linhas" =~ ^[0-9]+$ ]] && linhas_json=$linhas || linhas_json=null
    [[ "$rotacoes" =~ ^[0-9]+$ ]] && rotacoes_json=$rotacoes || rotacoes_json=null
    printf '{"servico":"filas-pinger","status":"%s","estado_saude":%s,"saida_saude_filas":%s,"motivo":%s,"linhas":%s,"rotacoes":%s,"ping_enviado":%s,"saida":%s,"destino_configurado":%s,"verificado_em":"%s"}\n' \
        "$status" "$estado_json" "$codigo_saude" "$(json_texto "$motivo")" \
        "$linhas_json" "$rotacoes_json" "$ping" "$codigo" \
        "${destino:-false}" "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
}

# =============================================================================
# MODO 2 — SAÚDE DO PRÓPRIO PINGER
# =============================================================================
saude_do_pinger() {
    if [[ ! "$LIMITE_SAUDADE_MIN" =~ ^[0-9]+$ ]] || (( LIMITE_SAUDADE_MIN <= 0 )); then
        erro "PING_FILAS_SINAL_IDADE_MINUTOS deve ser um inteiro positivo (recebido: '${LIMITE_SAUDADE_MIN}')"
        emitir_json "indisponivel" null 0 "PING_FILAS_SINAL_IDADE_MINUTOS invalido" "" "" false 5 true
        exit 5
    fi
    AGORA_S="$(date -u +%s)"
    # Sinal 1: o pinger rodou alguma vez, e recentemente?
    if [[ ! -f "$ESTADO_FILE" ]]; then
        log "nenhum estado do pinger em $ESTADO_FILE: o pinger NUNCA rodou neste host"
        emitir_json "nunca-executou" null 0 "sem estado do pinger" "" "" false 1 true
        exit 1
    fi
    mtime="$(stat -c '%Y' "$ESTADO_FILE" 2>/dev/null)"
    if [[ -z "$mtime" ]]; then
        erro "estado do pinger sem mtime legível: $ESTADO_FILE"
        emitir_json "indisponivel" null 0 "estado sem mtime legivel" "" "" false 5 true
        exit 5
    fi
    idade_min=$(( (AGORA_S - mtime) / 60 ))
    if (( idade_min > LIMITE_SAUDADE_MIN )); then
        log "O PRÓPRIO PINGER DE FILAS está parado: última execução há ${idade_min} min (limite ${LIMITE_SAUDADE_MIN} min)"
        log "isso NÃO é 'a fila parou' — é o pinger. O painel vai continuar"
        log "mostrando a ÚLTIMA leitura como se fosse de agora, e o painel não avisa."
        emitir_json "pinger-parado" null 0 "ultima execucao ha ${idade_min}min, acima do limite de ${LIMITE_SAUDADE_MIN}min" "" "" false 1 true
        exit 1
    fi
    # Sinal 2: o JSONL está sendo escrito? Grátis, e é o mesmo dado que o
    # painel exibe — visto do lado que o painel não mostra.
    if [[ -f "$JSONL" ]]; then
        mtime_linha="$(stat -c '%Y' "$JSONL" 2>/dev/null)"
        if [[ -n "$mtime_linha" ]]; then
            idade_linha=$(( (AGORA_S - mtime_linha) / 60 ))
            if (( idade_linha > LIMITE_SAUDADE_MIN )); then
                log "ERRO: o pinger roda, mas o JSONL não é escrito há ${idade_linha} min: o painel de filas vai mostrar a última leitura como se fosse de agora"
                emitir_json "jsonl-parado" null 0 "JSONL sem escrita ha ${idade_linha}min" "" "" false 1 true
                exit 1
            fi
        fi
    fi
    log "pinger vivo (execução de ${idade_min} min atrás)"
    emitir_json "pinger-vivo" null 0 "ultima execucao ha ${idade_min}min" "" "" false 0 true
    exit 0
}

if [[ "${1:-}" == "--saude-do-pinger" ]]; then
    saude_do_pinger
fi

# =============================================================================
# CONFIGURAÇÃO — falha fechada
# =============================================================================
if [[ ! -f "$APP_DIR/manage.py" ]]; then
    erro "manage.py não encontrado em $APP_DIR (ajuste PING_FILAS_APP_DIR)"
    emitir_json "indisponivel" null 0 "manage.py ausente em $APP_DIR" "" "" false 5 "${HEARTBEAT_URL:+true}"
    exit 5
fi
if ! command -v "$PYTHON" >/dev/null 2>&1 && [ ! -x "$PYTHON" ]; then
    erro "interpretador Python não encontrado: $PYTHON (ajuste PING_FILAS_PYTHON)"
    emitir_json "indisponivel" null 0 "python ausente: $PYTHON" "" "" false 5 "${HEARTBEAT_URL:+true}"
    exit 5
fi
if ! [[ "$MAX_LINHAS" =~ ^[0-9]+$ ]] || (( MAX_LINHAS < 2 )); then
    erro "PING_FILAS_MAX_LINHAS deve ser um inteiro >= 2 (recebido: '${MAX_LINHAS}')"
    emitir_json "indisponivel" null 0 "PING_FILAS_MAX_LINHAS invalido" "" "" false 5 "${HEARTBEAT_URL:+true}"
    exit 5
fi

DESTINO_CONFIGURADO=false
[[ -n "$HEARTBEAT_URL" ]] && DESTINO_CONFIGURADO=true

# =============================================================================
# PASSO 1 — MEDIR (o comando, não este script, decide o estado)
# =============================================================================
# `--ignorar-saida` NÃO é usado, e é a decisão mais importante deste bloco:
# ele faria o processo sair 0 sempre, e um monitor que trata 0 como saúde
# sobre um relatório que dice `desconhecido` é o falso verde mais caro que
# existe (checks.json:228, PROVISIONAMENTO §2.3 item 1).
relatorio=""
CODIGO_SAUDE=0
relatorio="$(cd "$APP_DIR" && DJANGO_SETTINGS_MODULE="${DJANGO_SETTINGS_MODULE:-config.settings}" \
              "$PYTHON" manage.py saude_filas --json 2>>"${PING_FILAS_LOG_TMP:-/dev/null}")"
CODIGO_SAUDE=$?

if [[ -z "$relatorio" ]]; then
    erro "saude_filas não produziu relatório (exit $CODIGO_SAUDE): o comando não rodou, e um comando que não rodou não é 'ok'"
    estado_json=null
    MOTIVO="saude_filas nao produziu relatorio (exit $CODIGO_SAUDE): o comando nao rodou"
    SAIDA=5
    ESTADO_PINGADO=null
else
    # O estado é lido do JSON que o comando IMPRIMIU — nunca adivinhado a
    # partir do exit. Os dois concordam por contrato, mas quem manda é o
    # relatório, e é ele que vai para o Loki.
    ESTADO_PINGADO="$(tail -n 1 <<<"$relatorio" | sed -n 's/.*"estado": *"\([^"]*\)".*/\1/p')"
    ESTADO_PINGADO="${ESTADO_PINGADO:-}"
    if [[ -z "$ESTADO_PINGADO" ]]; then
        estado_json=null
        MOTIVO="o relatorio de saude_filas nao tem campo 'estado': o formato mudou e o painel indexaria uma linha sem rotulo"
        log "AVISO: a última linha do relatório não é um relatório de saude_filas reconhecível"
        ESTADO_PINGADO=""
    else
        estado_json="\"$ESTADO_PINGADO\""
    fi
    case "$CODIGO_SAUDE" in
        0) MOTIVO="saude_filas ok: tudo verificado e sem problema"; SAIDA=0 ;;
        1) MOTIVO="saude_filas degradado (1): medido e com problema"; SAIDA=1 ;;
        3) MOTIVO="saude_filas desconhecido (3): nao foi possivel verificar. 3 e deliberadamente diferente de 0 — e de 1"; SAIDA=3 ;;
        *) MOTIVO="saude_filas saiu com codigo inesperado: $CODIGO_SAUDE (o contrato sao 0/1/3)"; SAIDA=5 ;;
    esac
    # Coerência exit × estado. Um comando que saiu 0 dizendo `degradado` é
    # um contrato quebrado no backend, e aceitar isso seria publicar um
    # heartbeat sobre um relatório que ele mesmo chama de ruim.
    if [[ "$SAIDA" == 0 && -n "$ESTADO_PINGADO" && "$ESTADO_PINGADO" != "ok" ]]; then
        MOTIVO="saude_filas saiu 0 mas disse estado='$ESTADO_PINGADO': contrato quebrado, e nenhum ping pode ser enviado sobre isso"
        SAIDA=5
    fi
fi

# =============================================================================
# PASSO 2 — ANEXAR AO JSONL (nos TRÊS estados, inclusive no 3)
# =============================================================================
# `flock` impede que duas execuções se intercalem: duas linhas meio
# escritas no meio do arquivo é um painel que perde NAÇÃO justamente na
# hora do incidente.
mkdir -p "$(dirname "$JSONL")" 2>/dev/null
exec {LOCK_FD}>>"${JSONL}.lock" || { log "AVISO: não foi possível abrir o lock ${JSONL}.lock"; }
flock -w 30 "$LOCK_FD" 2>/dev/null || log "AVISO: lock de ${JSONL} não obtido em 30 s"

rotacoes=0
linhas_atual=0
gravar_ok=true
if [[ -f "$JSONL" ]]; then
    linhas_atual="$(wc -l < "$JSONL" 2>/dev/null || echo 0)"
    linhas_atual="${linhas_atual// /}"
    if [[ "$linhas_atual" =~ ^[0-9]+$ ]] && (( linhas_atual >= MAX_LINHAS )); then
        # Ver o cabeçalho para POR QUE renomear e não truncar: o
        # `loki.source.file` segue por posição de byte, e truncar o arquivo
        # quebra essa posição.
        if mv -f "$JSONL" "${JSONL}.1" 2>/dev/null; then
            rotacoes=$(( rotacoes + 1 ))
            linhas_atual=0
            log "JSONL rotacionado em ${JSONL}.1 (teto de $MAX_LINHAS linhas); o total em disco fica em ~2x o teto"
        else
            log "AVISO: não foi possível rotacionar ${JSONL} (disco cheio ou permissão): a escrita continua e o arquivo pode passar do teto"
        fi
    fi
fi

if [[ -n "$relatorio" ]]; then
    # Uma linha por execução, com `printf` e não com `>>`: o `>>` de um
    # comando que wrote duas vezes (relatório em stdout + algo em stderr)
    # sujaria o JSONL, e uma linha suja no meio do arquivo é um registro que
    # o `stage.json` do Loki não extrai.
    linha_json="$(tail -n 1 <<<"$relatorio" | tr -d '\r')"
    if [[ "$linha_json" == \{*\} ]]; then
        if printf '%s\n' "$linha_json" >> "$JSONL" 2>/dev/null; then
            linhas_atual=$(( linhas_atual + 1 ))
            log "registro anexado ao JSONL: estado=${ESTADO_PINGADO:-?} exit_saude_filas=$CODIGO_SAUDE (linha $linhas_atual)"
        else
            gravar_ok=false
            log "ERRO: não foi possível escrever em $JSONL"
        fi
    else
        gravar_ok=false
        log "AVISO: a saída de saude_filas não é um objeto JSON de uma linha; nada foi anexado ao JSONL"
    fi
fi

if [[ "$gravar_ok" != "true" ]]; then
    MOTIVO="$MOTIVO — e o JSONL NAO foi escrito: o painel de filas está cego e ninguém vai saber"
    SAIDA=7
fi

# =============================================================================
# PASSO 3 — O HEARTBEAT (só no 0)
# =============================================================================
# O `status` desta linha reflete o VEREDITO, e não "ok". A primeira versão
# inicializava `STATUS="ok"` e só o sobrescrevia no caso 0 — de modo que uma
# leitura `desconhecido` (saida 3) era emitida com `"status":"ok"` ao lado de
# `"estado_saude":"desconhecido"`. Quem lesse o campo `status` — que é o que um
# painel faz primeiro — veria "ok" num relatório que o próprio comando chamou
# de não medido. É o falso verde DENTRO da própria saída JSON, e só apareceu
# porque o pinger foi rodado contra o backend REAL: com o dublê, a combinação
# de ramos que o escondia não era alcançada.
#
# Aqui o `status` é o estado do `saude_filas` quando ele existe; nos casos em
# que o comando não produziu veredito, é um status próprio que DIZ O QUÊ.
if [[ -n "$ESTADO_PINGADO" ]]; then
    STATUS="$ESTADO_PINGADO"
else
    case "$SAIDA" in
        0) STATUS="ok" ;;
        5) STATUS="indisponivel" ;;
        6) STATUS="sem-destino" ;;
        7) STATUS="jsonl-nao-escrito" ;;
        *) STATUS="sem-veredito" ;;
    esac
fi
PING_ENVIADO=false

# Estado gravado ANTES da rede: um pinger que não conseguiu falar com o
# destino ainda precisa deixar rastro do que ele mediu.
gravar_estado "$(emitir_json "$STATUS" "${estado_json:-null}" "$CODIGO_SAUDE" "$MOTIVO" "$linhas_atual" "$rotacoes" false "$SAIDA" "$DESTINO_CONFIGURADO")" \
    || log "AVISO: não foi possível gravar o estado do pinger em $ESTADO_FILE"

if (( SAIDA == 0 )) && [[ "$DESTINO_CONFIGURADO" != "true" ]]; then
    STATUS="sem-destino"
    MOTIVO="saude_filas ok, mas FILAS_HEARTBEAT_URL ausente: nenhum ping enviado, e o cron monitor continuara em desconhecido"
    SAIDA=6
elif (( SAIDA == 0 )); then
    if printf 'url = "%s"\n' "$HEARTBEAT_URL" \
        | curl --config - --fail --silent --output /dev/null \
               --max-time "$TIMEOUT_SEGUNDOS" 2>/dev/null; then
        PING_ENVIADO=true
        log "heartbeat ENTREGUE: o Better Stack sabe agora que a leitura de filas foi feita e saiu ok"
    else
        codigo_curl=$?
        STATUS="ping-nao-entregue"
        MOTIVO="saude_filas ok, mas o heartbeat nao foi aceito pelo destino (curl exit $codigo_curl). As filas podem estar otimas; o canal e que nao esta falando, e o cron monitor vai cair em desconhecido"
        SAIDA=4
        erro "$MOTIVO"
    fi
else
    log "saude_filas saiu $CODIGO_SAUDE (estado=${ESTADO_PINGADO:-?}): NENHUM ping enviado. A ausência do heartbeat é o alarme."
fi

linha_final="$(emitir_json "$STATUS" "${estado_json:-null}" "$CODIGO_SAUDE" "$MOTIVO" "$linhas_atual" "$rotacoes" "$PING_ENVIADO" "$SAIDA" "$DESTINO_CONFIGURADO")"
gravar_estado "$linha_final" || log "AVISO: não foi possível gravar o estado do pinger em $ESTADO_FILE"

case "$SAIDA" in
    0) log "OK: $MOTIVO" ;;
    1) log "DEGRADADO: $MOTIVO" ;;
    3) erro "DESCONHECIDO: $MOTIVO" ;;
    7) erro "JSONL NAO ESCRITO: $MOTIVO" ;;
    *) erro "FALHA: $MOTIVO" ;;
esac
printf '%s\n' "$linha_final"
exit "$SAIDA"
