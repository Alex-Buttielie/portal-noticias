#!/usr/bin/env bash
# Prova de poder discriminante do `infra/backup/pingar-backup.sh`.
#
# Um pinger que só sabe dizer "ok" é pior que nenhum pinger: ele transforma
# o `cron_monitor_backup` em um monitor que nunca alarma, que é exatamente o
# que o P2-01 registrou como o motivo de NÃO cadastrar o check ainda.
#
# O teste prova as DUAS metades:
#   1. cada estado ruim produz exit != 0 E NENHUM ping no destino (o servidor
#      HTTP local que faz as vezes de Better Stack conta as requisições);
#   2. o estado bom produz exit 0 E exatamente um ping.
#
# E prova a coisa que este programa já descobriu três vezes: a prova só vale
# se o teste REPROVAR quando a garantia é revertida. A seção 5 reverte a
# garantia de propósito e mostra que o teste pega.
#
# Nada aqui toca disco real, banco ou rede: os dumps são dublês, o diretório
# é temporário e o "Better Stack" é um servidor HTTP em 127.0.0.1.
#
# Uso:  bash infra/backup/testar-pingar-backup.sh
set -uo pipefail

AQUI="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PINGER="$AQUI/pingar-backup.sh"
WATCHDOG="$AQUI/verificar_backup.sh"
LAB="${BACKUP_PING_TESTE_DIR:-/home/alex-buttielie/scratch/g3/pinger-backup-prova}"

ACERTOS=0
TOTAL=0
PORTA=0
SERVIDOR_PID=""

limpar() {
    [[ -n "$SERVIDOR_PID" ]] && kill "$SERVIDOR_PID" 2>/dev/null
    SERVIDOR_PID=""
    # O `setsid` sobrevive ao `kill` do último PID, então o servidor que
    # FALHOU no meio do teste (ou de uma execução abortada) continuaria
    # escutando e contaminaria a próxima. Mata por PADRÃO, não por PID.
    [[ -n "$LAB" ]] && pkill -f "$LAB/bin/servidor-heartbeat.py" 2>/dev/null
    rm -rf "$LAB"
    return 0
}

# --- o `pg_restore` REAL -----------------------------------------------------
# O pinger chama `pg_restore --list` de verdade, e o certo é não enfraquecer o
# pinger para que o teste passe. Este bloco garante um `pg_restore` REAL no
# PATH do teste:
#
#   * se o host já tem `pg_restore` (VPS de produção tem — `pg_backup_pm2.sh`
#     exige em 76-81), usa o do host;
#   * senão, se `PG_TESTE_PG_RESTORE` apontar para um, usa esse;
#   * senão, o teste ABORTA com mensagem, em vez de pular a checagem. Um
#     teste que pula a checagem de archive e ainda assim passa é pior que nenhum teste.
escrever_pg_restore() {
    if command -v pg_restore >/dev/null 2>&1; then
        log "usando o pg_restore do host: $(command -v pg_restore)"
        return 0
    fi
    if [[ -n "${PG_TESTE_PG_RESTORE:-}" && -x "${PG_TESTE_PG_RESTORE}" ]]; then
        mkdir -p "$LAB/bin"
        cp "${PG_TESTE_PG_RESTORE}" "$LAB/bin/pg_restore"
        chmod +x "$LAB/bin/pg_restore"
        log "usando o pg_restore de teste: ${PG_TESTE_PG_RESTORE}"
        return 0
    fi
    cat >&2 <<'AVISO'
==============================================================================
ABORTOU: este teste precisa de um `pg_restore` REAL e não achou um.
O pinger NÃO pode ser enfraquecido para que o teste passe — a checagem de
archive (`pg_restore --list`) é parte da garantia, e um teste que a pula
verde é pior que nenhum teste.

Para rodar, aponte para um binário real:
    PG_TESTE_PG_RESTORE=/caminho/para/pg_restore bash testar-pingar-backup.sh
Em DEV/HOMOLOG/PROD o binário do host serve, sem configuração nenhuma.
==============================================================================
AVISO
    return 1
}
# Um servidor HTTP mínimo que CONTA cada GET. A contagem é a prova de que o
# pinger mandou ou não mandou o heartbeat — que é o que separa "o pinger
# reprovou por lógica própria" de "o pinger reprovou e mesmo assim mandou o sinal".
escrever_servidor() {
    mkdir -p "$LAB/bin"
    cat > "$LAB/bin/servidor-heartbeat.py" <<'PY'
import http.server, sys
class H(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        with open(sys.argv[2], "a") as f:
            f.write(self.path + "\n")
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"ok")
    def log_message(self, *a):
        pass
http.server.HTTPServer(("127.0.0.1", int(sys.argv[1])), H).serve_forever()
PY
    start_servidor() {
        local log_recebidos="$3"
        # A PORTA TEM QUE ESTAR LIVRE antes de subir. Um servidor órfão de
        # uma execução anterior (o `setsid` sobrevive ao `limpar`, que só
        # conhece o último PID) fica escutando, o novo processo morre no bind
        # com "Address already in use" — em silêncio, porque o stderr vai
        # para /dev/null — e é o VELHO que responde 200. O resultado é um
        # teste que conta pings num log que ninguém escreve e acusa FALHA
        # num pinger correto, ou pior: conta pings de outra execução e
        # aprova uma Mutação que devia reprovar.
        if (exec 3<>"/dev/tcp/127.0.0.1/$2") 2>/dev/null; then
            exec 3>&- 3<&-
            echo "  FALHOU   a porta $2 já está em uso por outro processo (servidor órfão de uma execução anterior?)" >&2
            return 1
        fi
        setsid python3 "$LAB/bin/servidor-heartbeat.py" "$2" "$log_recebidos" \
            </dev/null >"$LAB/servidor-$2.err" 2>&1 &
        SERVIDOR_PID=$!
        local tentas=0
        while (( tentas < 50 )); do
            if (exec 3<>"/dev/tcp/127.0.0.1/$2") 2>/dev/null; then exec 3>&- 3<&-; return 0; fi
            if ! kill -0 "$SERVIDOR_PID" 2>/dev/null; then
                echo "  FALHOU   o servidor da porta $2 morreu ao subir: $(cat "$LAB/servidor-$2.err" 2>/dev/null)" >&2
                return 1
            fi
            tentas=$(( tentas + 1 )); sleep 0.1
        done
        return 1
    }
}

recebidos() { [[ -f "$1" ]] && wc -l < "$1" | tr -d ' ' || echo 0; }

# O nome do log de recebidos é derivado de `SECONDS`, e NÃO de um contador de
# caso: a primeira rodada usava o contador, e dois casos que não usam a
# função `caso` (os de mutação e o de reexecução) acabavam com o MESMO nome de
# arquivo de um caso anterior. O `: >` do `start_servidor` truncava o log,
# a contagem vinha 0, e o teste acusava FALHA num pinger que estava
# correto. `SECONDS` é monotônico dentro do processo e não volta.
log_recebidos_novo() {
    local f="$LAB/recebidos-$SECONDS.log"
    : > "$f"
    printf '%s' "$f"
}

# --- o stub de `aws` --------------------------------------------------------
# O mesmo desenho do `testar-verificar-backup.sh` (mesmo motivo: head-object
# com o tamanho do objeto local), para que os dois testes leiam igual.
escrever_stub_aws() {
    mkdir -p "$LAB/bin"
    cat > "$LAB/bin/aws" <<'STUB'
#!/usr/bin/env bash
# stub: `aws s3api head-object --bucket B --key K --query ContentLength --output text`
key=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --key) key="$2"; shift 2 ;;
    --bucket|--query|--output|--endpoint-url) shift 2 ;;
    *) shift ;;
  esac
done
base="${key##*/}"
if [[ -n "${AWS_STUB_FAIL:-}" ]]; then echo "stub: head-object falhou" >&2; exit 255; fi
if [[ -n "${AWS_STUB_SIZE:-}" ]]; then printf '%s\n' "$AWS_STUB_SIZE"; exit 0; fi
f="${AWS_STUB_DIR:-.}/$base"
[[ -f "$f" ]] || { echo "stub: no such key $key" >&2; exit 254; }
stat -c '%s' "$f"
STUB
    chmod +x "$LAB/bin/aws"
}

# --- dublês de dump ---------------------------------------------------------
# `dump_com_conteudo` cria um dump de 1 MiB (passa do piso padrão) e um
# arquivo de mídia; `dump_vazio_48kb` cria o dump de 48 KB que está em
# produção hoje — sintoma de esquema sem dados.
#
# `dd if=/dev/zero` NÃO produz um archive PostgreSQL: o formato custom começa
# com o magic `PGDMP` (medido: todos os dumps reais começam assim), e
# `/dev/zero` não. Para os cenários que precisam de um dump que PASSE no
# `pg_restore --list`, o conteúdo é um archive real gerado por `pg_dump`.
# Para o dump de 48 KB o conteúdo é irrelevante — ele reprova pelo PISO, que
# vem antes da checagem estrutural, e é isso que o teste está provando.
GERAR_ARCHIVE_REAL() {
    # Requer PING_TESTE_PG_DUMP + PG_TESTE_CONTAINER. Devolve 1 se conseguiu.
    [[ -n "${PING_TESTE_PG_DUMP:-}" ]] || return 1
    [[ -n "${PG_TESTE_CONTAINER:-}" ]] || return 1
    return 0
}
dump_com_conteudo() {
    local horas="${1:-1}" ts
    ts="$(date -u -d "-${horas} hours" +%Y%m%dT%H%M%SZ)"
    if GERAR_ARCHIVE_REAL; then
        docker exec "${PG_TESTE_CONTAINER}" "$PING_TESTE_PG_DUMP" -U postgres -Fc cheio > "pm2-db-$ts.dump" 2>/dev/null \
            || dd if=/dev/zero of="pm2-db-$ts.dump" bs=1024 count=1024 status=none
        # O archive real de 8,6 KB ficaria ABAIXO do piso de 1 MiB, então o
        # cenário "backup bom" precisa de um dump que passe do piso. O
        # archive é repetido com `cat` até cruzar o piso: continua sendo um
        # archive válido, que é o que a checagem estrutural exige.
        while [[ "$(stat -c '%s' "pm2-db-$ts.dump")" -lt 1048576 ]]; do
            cat "pm2-db-$ts.dump" "pm2-db-$ts.dump" > tmp.dump.$$ && mv -f tmp.dump.$$ "pm2-db-$ts.dump"
        done
    else
        dd if=/dev/zero of="pm2-db-$ts.dump" bs=1024 count=1024 status=none
    fi
    printf 'midia-de-teste' > "pm2-media-$ts.tar.gz"
    touch -d "-${horas} hours" "pm2-db-$ts.dump" "pm2-media-$ts.tar.gz"
    LAST_DUMP="pm2-db-$ts.dump"; LAST_MEDIA="pm2-media-$ts.tar.gz"
}
dump_vazio_48kb() {
    local horas="${1:-1}" ts
    ts="$(date -u -d "-${horas} hours" +%Y%m%dT%H%M%SZ)"
    dd if=/dev/zero of="pm2-db-$ts.dump" bs=1024 count=48 status=none
    printf 'midia-de-teste' > "pm2-media-$ts.tar.gz"
    touch -d "-${horas} hours" "pm2-db-$ts.dump" "pm2-media-$ts.tar.gz"
    LAST_DUMP="pm2-db-$ts.dump"; LAST_MEDIA="pm2-media-$ts.tar.gz"
}

# caso <nome> <exit-esperado> <pings-esperados> <trecho-esperado> <setup> <env-extra>
# `pings-esperados` é a parte que prova o ponto: 0 pings num estado ruim, 1
# ping num estado bom. Contar pings é o que separa um pinger que decide do
# um pinger que sempre sinaliza.
caso() {
    local nome="$1" esperado="$2" pings_esp="$3" trecho="$4" setup="$5" extra="${6:-}"
    TOTAL=$(( TOTAL + 1 ))
    local dir="$LAB/$(printf '%02d' "$TOTAL")-caso"
    mkdir -p "$dir"
    ( set +u; cd "$dir"; eval "$setup" ) >/dev/null 2>&1
    local log_rec; log_rec="$(log_recebidos_novo)"
    local porta=$(( 56000 + TOTAL ))
    start_servidor "$TOTAL" "$porta" "$log_rec" || { echo "  FALHOU   servidor não subiu"; return; }
    local url="http://127.0.0.1:$porta/hb/SEGREDO-DE-TESTE"
    # O stub de `aws` resolve o objeto por `AWS_STUB_DIR/$nome`, e ele roda
    # com o CWD do PINGER — não o do caso. Por isso o diretório precisa ser
    # ABSOLUTO: com `AWS_STUB_DIR=.` o stub procuraria o objeto no diretório
    # de trabalho do pinger e não acharia, e todo cenário remoto cairia em
    # `remoto-indisponivel` — que é o que aconteceu na primeira rodada.
    local saida exit
    saida="$(env BACKUP_DIR="$dir" \
                  BACKUP_HEARTBEAT_URL="$url" \
                  BACKUP_PING_ESTADO_FILE="$dir/.estado.json" \
                  PATH="$LAB/bin:$PATH" \
                  AWS_STUB_DIR="$dir" \
                  $extra \
                  bash "$PINGER" 2>/dev/null)"
    exit=$?
    local pings; pings="$(recebidos "$log_rec")"
    local ultima; ultima="$(tail -n 1 <<<"$saida")"
    kill "$SERVIDOR_PID" 2>/dev/null; SERVIDOR_PID=""

    if [[ "$exit" == "$esperado" && "$pings" == "$pings_esp" ]] && grep -qF "$trecho" <<<"$ultima"; then
        printf '  OK       %-50s exit=%-2s pings=%s  %s\n' "$nome" "$exit" "$pings" "$trecho"
        ACERTOS=$(( ACERTOS + 1 ))
    else
        printf '  FALHOU   %-50s exit=%s (esperava %s)  pings=%s (esperava %s)\n' \
            "$nome" "$exit" "$esperado" "$pings" "$pings_esp"
        printf '           json: %s\n' "$ultima"
    fi
}

echo "=============================================================================="
echo "PINGER DE BACKUP — quem recebe o heartbeat, e quem NÃO recebe"
echo "=============================================================================="
limpar
mkdir -p "$LAB"
escrever_servidor
escrever_stub_aws
escrever_pg_restore || { echo "  FALHOU   sem pg_restore real"; exit 1; }

# --- 1. ESTADO REAL DE HOJE -------------------------------------------------
# O backup de produção está quebrado. O pinger tem que dizer isso, e o mais
# importante: NÃO mandar o heartbeat. Um pinger que manda o sinal com o
# backup quebrado é o pinger mentindo junto com o backup.
echo
echo "--- 1. O ESTADO REAL DE HOJE (backup quebrado) ---"

caso "nenhum dump (backup nunca rodou)" 1 0 '"status":"backup-nao-verificado"' \
    'true' \
    'BACKUP_WATCHDOG_CHECK_REMOTE=0 BACKUP_WATCHDOG_EXIGIR_REMOTO=0'

caso "dump de 30 h (atrasado)" 1 0 '"status":"backup-nao-verificado"' \
    'dump_com_conteudo 30' \
    'BACKUP_WATCHDOG_CHECK_REMOTE=0 BACKUP_WATCHDOG_EXIGIR_REMOTO=0'

# O caso que este programa existe para pegar: o dump de 48 KB. Ele passa no
# `pg_restore --list` do watchdog, tem mtime de hoje, e é sintoma de esquema
# sem dados. O watchdog sozinho devolve 0 para ele. O pinger tem que ver
# através disso — e o heartbeat tem que NÃO sair.
caso "DUMP DE 48 KB (o caso de produção hoje)" 2 0 '"status":"conteudo-insuficiente"' \
    'dump_vazio_48kb 1' \
    'BACKUP_WATCHDOG_CHECK_REMOTE=0 BACKUP_WATCHDOG_EXIGIR_REMOTO=0'

caso "DUMP DE 48 KB mas com S3 ok" 2 0 '"status":"conteudo-insuficiente"' \
    'dump_vazio_48kb 1' \
    'BACKUP_S3_BUCKET=exemplo-bucket BACKUP_S3_ACCESS_KEY=k BACKUP_S3_SECRET_KEY=s'

# O piso é configurável, e o teste tem que mostrar que mexer nele muda o
# veredito — senão "configurável" é só uma palavra no comentário.
caso "48 KB com o piso em 1 KB -> aceito como backup real" 0 1 '"status":"ok"' \
    'dump_vazio_48kb 1' \
    'BACKUP_WATCHDOG_CHECK_REMOTE=0 BACKUP_WATCHDOG_EXIGIR_REMOTO=0 BACKUP_PING_TAMANHO_MINIMO_BYTES=1024 BACKUP_PING_PULAR_ESTRUTURA=1'

# E desligar o piso tem que ser VISÍVEL, não silencioso: é o modo em que o
# dump vazio vira verde, e quem lê o painel precisa conseguir ver que ele está
# nesse modo.
caso "48 KB com o piso DESLIGADO -> ok, mas o motivo diz" 0 1 'piso de conteudo esta DESLIGADO' \
    'dump_vazio_48kb 1' \
    'BACKUP_WATCHDOG_CHECK_REMOTE=0 BACKUP_WATCHDOG_EXIGIR_REMOTO=0 BACKUP_PING_EXIGIR_CONTEUDO=0'

# --- 2. O ESTADO BOM, E SÓ ELE MANDA O SINAL --------------------------------
echo
echo "--- 2. O ESTADO BOM: heartbeat ENTREGUE ---"

caso "dump de 1 MiB dentro do prazo, sem exigir remoto" 0 1 '"ping_enviado":true' \
    'dump_com_conteudo 1' \
    'BACKUP_WATCHDOG_CHECK_REMOTE=0 BACKUP_WATCHDOG_EXIGIR_REMOTO=0'

caso "dump de 1 MiB, bucket ok (dump e mídia confirmados)" 0 1 '"ping_enviado":true' \
    'dump_com_conteudo 1' \
    'BACKUP_S3_BUCKET=exemplo-bucket BACKUP_S3_ACCESS_KEY=k BACKUP_S3_SECRET_KEY=s'

# O dump está no bucket mas a MÍDIA não. O watchdog confirma só o dump
# (verificar_backup.sh:220), então é o pinger que tem que ver isso — o
# contrato do cron monitor fala nos DOIS objetos (checks.json:213).
# O `dump_com_conteudo` sem `.tar.gz` é o cenário: o setup cria o dump e a
# mídia, e a linha abaixo apaga a mídia, então o bucket de fato não a tem.
caso "dump no bucket, mídia AUSENTE do bucket" 1 0 '"status":"midia-sem-confirmacao"' \
    'dump_com_conteudo 1; rm -f pm2-media-*.tar.gz' \
    'BACKUP_S3_BUCKET=exemplo-bucket BACKUP_S3_ACCESS_KEY=k BACKUP_S3_SECRET_KEY=s'

# --- 3. O PINGER MORRIDO ----------------------------------------------------
echo
echo "--- 3. O PRÓPRIO PINGER ESTÁ VIVO? (o sinal local) ---"

TOTAL=$(( TOTAL + 1 ))
dir="$LAB/$(printf '%02d' "$TOTAL")-sinal"
mkdir -p "$dir"
saida="$(BACKUP_PING_ESTADO_FILE="$dir/.estado.json" bash "$PINGER" --saude-do-pinger 2>/dev/null)"; exit=$?
if [[ "$exit" == 1 ]] && grep -qF '"status":"nunca-executou"' <<<"$saida"; then
    printf '  OK       %-50s exit=1  nunca-executou\n' "sem estado: o pinger nunca rodou"
    ACERTOS=$(( ACERTOS + 1 ))
else
    printf '  FALHOU   %-50s exit=%s (esperava 1)\n' "sem estado: o pinger nunca rodou" "$exit"
    printf '           json: %s\n' "$(tail -n 1 <<<"$saida")"
fi

# Estado recem-escrito -> vivo.
TOTAL=$(( TOTAL + 1 ))
dir="$LAB/$(printf '%02d' "$TOTAL")-sinal"
mkdir -p "$dir"
printf '{"servico":"backup-pinger","status":"ok"}\n' > "$dir/.estado.json"
saida="$(BACKUP_PING_ESTADO_FILE="$dir/.estado.json" bash "$PINGER" --saude-do-pinger 2>/dev/null)"; exit=$?
if [[ "$exit" == 0 ]] && grep -qF '"status":"pinger-vivo"' <<<"$saida"; then
    printf '  OK       %-50s exit=0  pinger-vivo\n' "estado fresco: o pinger está vivo"
    ACERTOS=$(( ACERTOS + 1 ))
else
    printf '  FALHOU   %-50s exit=%s (esperava 0)\n' "estado fresco: o pinger está vivo" "$exit"
    printf '           json: %s\n' "$(tail -n 1 <<<"$saida")"
fi

# Estado velho -> o pinger está PARADO. Este é o sinal que separa "o backup
# parou" de "o canal parou", que o cron monitor externo não distingue.
TOTAL=$(( TOTAL + 1 ))
dir="$LAB/$(printf '%02d' "$TOTAL")-sinal"
mkdir -p "$dir"
printf '{"servico":"backup-pinger","status":"ok"}\n' > "$dir/.estado.json"
touch -d "-3 hours" "$dir/.estado.json"
saida="$(BACKUP_PING_ESTADO_FILE="$dir/.estado.json" BACKUP_PING_SINAL_IDADE_HORAS=1 \
         bash "$PINGER" --saude-do-pinger 2>/dev/null)"; exit=$?
if [[ "$exit" == 1 ]] && grep -qF '"status":"pinger-parado"' <<<"$saida"; then
    printf '  OK       %-50s exit=1  pinger-parado\n' "estado de 3 h: o pinger está parado"
    ACERTOS=$(( ACERTOS + 1 ))
else
    printf '  FALHOU   %-50s exit=%s (esperava 1)\n' "estado de 3 h: o pinger está parado" "$exit"
    printf '           json: %s\n' "$(tail -n 1 <<<"$saida")"
fi

# --- 4. O DESTINO RECUSA ----------------------------------------------------
echo
echo "--- 4. O PINGER NÃO CONSEGUE FALAR COM O DESTINO ---"
# Nada de servidor no ar: a porta está fechada. O backup está bom, o pinger
# está vivo, e o canal não funciona. Isso tem que ser DISTINTO de "o backup
# falhou" — são duas paginações com duas remediações opostas.
TOTAL=$(( TOTAL + 1 ))
dir="$LAB/$(printf '%02d' "$TOTAL")-destino-morto"
mkdir -p "$dir"
( set +u; cd "$dir"; dump_com_conteudo 1 )
saida="$(env BACKUP_DIR="$dir" \
              BACKUP_HEARTBEAT_URL="http://127.0.0.1:1/hb/SEGREDO" \
              BACKUP_PING_ESTADO_FILE="$dir/.estado.json" \
              BACKUP_WATCHDOG_CHECK_REMOTE=0 BACKUP_WATCHDOG_EXIGIR_REMOTO=0 \
              PATH="$LAB/bin:$PATH" \
              bash "$PINGER" 2>/dev/null)"; exit=$?
if [[ "$exit" == 4 ]] && grep -qF '"status":"ping-nao-entregue"' <<<"$saida"; then
    printf '  OK       %-50s exit=4  ping-nao-entregue\n' "destino inalcançável: o backup está bom"
    ACERTOS=$(( ACERTOS + 1 ))
else
    printf '  FALHOU   %-50s exit=%s (esperava 4)\n' "destino inalcançável: o backup está bom" "$exit"
    printf '           json: %s\n' "$(tail -n 1 <<<"$saida")"
fi
# E o estado local tem que ter sobrado, mesmo com a rede morta: é a evidência
# que separa "a internet caiu" de "o pinger está quebrado".
if grep -qF '"ping_enviado":false' "$dir/.estado.json" 2>/dev/null; then
    printf '  OK       %-50s              rastro local preservado\n' "com a rede morta, o estado local existe"
    ACERTOS=$(( ACERTOS + 1 ))
    TOTAL=$(( TOTAL + 1 ))
else
    printf '  FALHOU   %-50s              sem rastro local\n' "com a rede morta, o estado local existe"
    TOTAL=$(( TOTAL + 1 ))
fi

# Sem destino configurado: exit 6, e NENHUM ping. "Não tenho para onde dizer"
# nunca pode ser lido como "está tudo bem".
TOTAL=$(( TOTAL + 1 ))
dir="$LAB/$(printf '%02d' "$TOTAL")-sem-destino"
mkdir -p "$dir"
( set +u; cd "$dir"; dump_com_conteudo 1 )
saida="$(env -u BACKUP_HEARTBEAT_URL BACKUP_DIR="$dir" \
              BACKUP_PING_ESTADO_FILE="$dir/.estado.json" \
              BACKUP_WATCHDOG_CHECK_REMOTE=0 BACKUP_WATCHDOG_EXIGIR_REMOTO=0 \
              PATH="$LAB/bin:$PATH" \
              bash "$PINGER" 2>/dev/null)"; exit=$?
if [[ "$exit" == 6 ]] && grep -qF '"status":"sem-destino"' <<<"$saida"; then
    printf '  OK       %-50s exit=6  sem-destino\n' "sem BACKUP_HEARTBEAT_URL: exit 6, não 0"
    ACERTOS=$(( ACERTOS + 1 ))
else
    printf '  FALHOU   %-50s exit=%s (esperava 6)\n' "sem BACKUP_HEARTBEAT_URL: exit 6, não 0" "$exit"
    printf '           json: %s\n' "$(tail -n 1 <<<"$saida")"
fi

# --- 5. PODER DISCRIMINANTE -------------------------------------------------
echo
echo "--- 5. REVERTENDO A GARANTIA: o teste tem que REPROVAR ---"
# Um pinger de 48 KB-verde é exatamente o falso verde que este programa
# existe para acabar. A prova de que o teste pega isso é inverter a garantia
# e mostrar que ele falha — não afirmar que ele falha.
echo "    (a garantia é revertida numa CÓPIA; o pinger versionado não é tocado)"
COPIA="$LAB/pinger-com-piso-desligado.sh"
cp "$PINGER" "$COPIA"
# A CÓPIA mora em $LAB, e o pinger resolve o watchdog por `SCRIPT_DIR`. Sem
# este env, a cópia não acha o `verificar_backup.sh` e sai com 5 — que
# reprovaria por um motivo SEM RELAÇÃO com a garantia, e a mutação passaria
# "pernas" sem ser provada. `BACKUP_WATCHDOG` é o gancho que existe para
# isso (e para deploys com o watchdog em outro diretório).
sed -i 's|^PISO_BYTES="${BACKUP_PING_TAMANHO_MINIMO_BYTES:-1048576}"|PISO_BYTES="${BACKUP_PING_TAMANHO_MINIMO_BYTES:-0}"|' "$COPIA"
sed -i 's|^EXIGIR_CONTEUDO="${BACKUP_PING_EXIGIR_CONTEUDO:-1}"|EXIGIR_CONTEUDO="${BACKUP_PING_EXIGIR_CONTEUDO:-0}"|' "$COPIA"
TOTAL=$(( TOTAL + 1 ))
dir="$LAB/$(printf '%02d' "$TOTAL")-mutacao"
mkdir -p "$dir"
( set +u; cd "$dir"; dump_vazio_48kb 1 )
log_rec="$(log_recebidos_novo)"
start_servidor "mutacao" 56999 "$log_rec" || echo "  FALHOU   servidor não subiu"
saida="$(env BACKUP_DIR="$dir" \
              BACKUP_HEARTBEAT_URL="http://127.0.0.1:56999/hb/SEGREDO" \
              BACKUP_PING_ESTADO_FILE="$dir/.estado.json" \
              BACKUP_WATCHDOG="$WATCHDOG" \
              BACKUP_WATCHDOG_CHECK_REMOTE=0 BACKUP_WATCHDOG_EXIGIR_REMOTO=0 \
              PATH="$LAB/bin:$PATH" \
              bash "$COPIA" 2>/dev/null)"; exit=$?
pings="$(recebidos "$log_rec")"
kill "$SERVIDOR_PID" 2>/dev/null; SERVIDOR_PID=""
# QUANDO a garantia está revertida, o caso do dump de 48 KB tem que PARAR de
# dar o veredito esperado — é isso que "o teste tem poder discriminante"
# significa. A leitura correta é a oposta da ingênua:
#
#   exit=2, pings=0  → o teste NÃO distingue a garantia revertida; o caso
#                      passaria igual com e sem o piso. O TESTE está fraco.
#   exit=0, pings=1  → o dump de 48 KB virou verde e o heartbeat SAIU. O
#                      caso do topo (mesmo dump, garantia intacta) reprova.
#                      A diferença entre os dois é a garantia, e é prova.
#
# A segunda leitura é a boa, e é a que o caso 1 já exercise: lá, o MESMO
# dump de 48 KB dá exit=2 e pings=0. Aqui dá exit=0 e pings=1.
if [[ "$exit" == 0 && "$pings" == "1" ]]; then
    printf '  OK       %-50s exit=0  pings=%s\n' "MUTAÇÃO: piso desligado, dump de 48 KB" "$pings"
    printf '           o dump de 48 KB virou VERDE e o heartbeat SAIU com a garantia revertida.\n'
    printf '           No caso 1 (mesmo dump, garantia INTACTA) o veredito foi exit=2, pings=0.\n'
    printf '           A diferença entre os dois é a garantia. O teste tem poder discriminante.\n'
    ACERTOS=$(( ACERTOS + 1 ))
else
    printf '  FALHOU   %-50s exit=%s pings=%s\n' "MUTAÇÃO: piso desligado, dump de 48 KB" "$exit" "$pings"
    printf '           a garantia revertida NÃO mudou o veredito deste caso, então este\n'
    printf '           caso não distingue ter o piso de não tê-lo. O TESTE é fraco aqui.\n'
fi

# A MESMA mutação, agora com o piso desligado de propósito por env. Este
# caso é o CONTROLE de que a diferença acima veio da garantia e não do `sed`:
# se o `sed` tivesse mudado alguma outra coisa, os dois diverge.
TOTAL=$(( TOTAL + 1 ))
dir="$LAB/$(printf '%02d' "$TOTAL")-mutacao-env"
mkdir -p "$dir"
( set +u; cd "$dir"; dump_vazio_48kb 1 )
log_rec="$(log_recebidos_novo)"
start_servidor "mutacaoenv" 56998 "$log_rec" || echo "  FALHOU   servidor não subiu"
saida="$(env BACKUP_DIR="$dir" \
              BACKUP_HEARTBEAT_URL="http://127.0.0.1:56998/hb/SEGREDO" \
              BACKUP_PING_ESTADO_FILE="$dir/.estado.json" \
              BACKUP_PING_EXIGIR_CONTEUDO=0 \
              BACKUP_WATCHDOG_CHECK_REMOTE=0 BACKUP_WATCHDOG_EXIGIR_REMOTO=0 \
              PATH="$LAB/bin:$PATH" \
              bash "$PINGER" 2>/dev/null)"; exit=$?
pings="$(recebidos "$log_rec")"
kill "$SERVIDOR_PID" 2>/dev/null; SERVIDOR_PID=""
if [[ "$exit" == 0 && "$pings" == "1" ]]; then
    printf '  OK       %-50s exit=0  pings=%s\n' "controle: piso desligado por env, 48 KB" "$pings"
    printf '           o mesmo resultado da mutação por sed: a diferença do caso\n'
    printf '           anterior é a GARANTIA, não o mecanismo usado para reverter\n'
    ACERTOS=$(( ACERTOS + 1 ))
else
    printf '  FALHOU   %-50s exit=%s pings=%s (esperava exit=0, 1 ping)\n' \
        "controle: piso desligado por env, 48 KB" "$exit" "$pings"
fi

# E a mutação que NÃO desfaz a garantia — declaradas, não escondidas.
# Ligar `PULAR_ESTRUTURA=1` mantém o piso em bytes, e o dump de 48 KB continua
# reprovando: a garantia é do PISO, e a checagem estrutural é uma segunda
# camada, não a que carrega o peso. Se este caso passasse com o piso
# desligado, o teste da mutação acima não provaria nada.
TOTAL=$(( TOTAL + 1 ))
dir="$LAB/$(printf '%02d' "$TOTAL")-mutacao-inocua"
mkdir -p "$dir"
( set +u; cd "$dir"; dump_vazio_48kb 1 )
saida="$(env BACKUP_DIR="$dir" BACKUP_PING_ESTADO_FILE="$dir/.estado.json" \
              BACKUP_PING_PULAR_ESTRUTURA=1 \
              BACKUP_WATCHDOG_CHECK_REMOTE=0 BACKUP_WATCHDOG_EXIGIR_REMOTO=0 \
              PATH="$LAB/bin:$PATH" \
              bash "$PINGER" 2>/dev/null)"; exit=$?
if [[ "$exit" == 2 ]]; then
    printf '  OK       %-50s exit=%s  igual\n' "MUTAÇÃO INOCUA: só a camada estrutural off" "$exit"
    printf '           o piso em BYTES é o que carrega a garantia: sem ele, o veredito\n'
    printf '           do dump de 48 KB NÃO muda. Declarado porque testar a mutação\n'
    printf '           errada é tão enganoso quanto não testar.\n'
    ACERTOS=$(( ACERTOS + 1 ))
else
    printf '  FALHOU   %-50s exit=%s (esperava 2, igual ao caso 1)\n' \
        "MUTAÇÃO INOCUA: só a camada estrutural off" "$exit"
fi

# --- 6. IDEMPOTÊNCIA --------------------------------------------------------
echo
echo "--- 6. REEXECUÇÃO: rodar duas vezes não muda o veredito ---"
TOTAL=$(( TOTAL + 1 ))
dir="$LAB/$(printf '%02d' "$TOTAL")-idem"
mkdir -p "$dir"
( set +u; cd "$dir"; dump_com_conteudo 1 )
log_rec="$(log_recebidos_novo)"
start_servidor "idem" 56997 "$log_rec" || echo "  FALHOU   servidor não subiu"
e1=0; e2=0
for i in 1 2; do
    env BACKUP_DIR="$dir" BACKUP_HEARTBEAT_URL="http://127.0.0.1:56997/hb/SEGREDO" \
        BACKUP_PING_ESTADO_FILE="$dir/.estado.json" \
        BACKUP_WATCHDOG_CHECK_REMOTE=0 BACKUP_WATCHDOG_EXIGIR_REMOTO=0 \
        PATH="$LAB/bin:$PATH" bash "$PINGER" >/dev/null 2>&1
    [[ $? == 0 ]] || e1=1
done
pings="$(recebidos "$log_rec")"
kill "$SERVIDOR_PID" 2>/dev/null; SERVIDOR_PID=""
if [[ "$pings" == "2" ]]; then
    printf '  OK       %-50s 2 pings, 2 execuções\n' "reexecutar: 2 pings, nenhum arquivo criado"
    ACERTOS=$(( ACERTOS + 1 ))
else
    printf '  FALHOU   %-50s pings=%s (esperava 2)\n' "reexecutar: 2 pings, nenhum arquivo criado" "$pings"
fi

# Um pinger idempotente não deixa lixo: rodar 5 vezes não pode criar 5 dumps.
TOTAL=$(( TOTAL + 1 ))
if [[ "$(find "$dir" -name 'pm2-db-*.dump' | wc -l)" == "1" ]]; then
    printf '  OK       %-50s 1 dump\n' "reexecutar não cria dump novo"
    ACERTOS=$(( ACERTOS + 1 ))
else
    printf '  FALHOU   %-50s\n' "reexecutar não cria dump novo"
fi

# --- 7. O SEGREDO NÃO VAZA --------------------------------------------------
echo
echo "--- 7. O TOKEN NÃO APARECE EM LUGAR NENHUM ---"
# Cada verificação incrementa TOTAL e ACERTOS exatamente UMA vez, em ponto
# único. A primeira versão somava TOTAL só no caminho feliz do primeiro
# teste, e o total ficava um a menos que o número real de verificações — o
# resultado final acusava 22 de 23 com TODOS os cenários tendo passado, e
# essa aritmética quebrada é a forma mais fácil de um gate verde ser lido
# como reprovação.
TOTAL=$(( TOTAL + 1 ))
dir="$LAB/$(printf '%02d' "$TOTAL")-segredo"
mkdir -p "$dir"
( set +u; cd "$dir"; dump_com_conteudo 1 )
saida_completa="$(env BACKUP_DIR="$dir" \
              BACKUP_HEARTBEAT_URL="http://127.0.0.1:56996/hb/SEGREDO-DE-TESTE-NAO-VER" \
              BACKUP_PING_ESTADO_FILE="$dir/.estado.json" \
              BACKUP_WATCHDOG_CHECK_REMOTE=0 BACKUP_WATCHDOG_EXIGIR_REMOTO=0 \
              PATH="$LAB/bin:$PATH" \
              bash "$PINGER" 2>&1)"
if grep -qF "SEGREDO-DE-TESTE-NAO-VER" <<<"$saida_completa"; then
    printf '  FALHOU   %-50s\n' "a URL de heartbeat aparece na saída"
    printf '           ocorrência: %s\n' "$(grep -oF -m1 'SEGREDO-DE-TESTE-NAO-VER' <<<"$saida_completa")"
else
    printf '  OK       %-50s\n' "a URL de heartbeat não aparece na saída (stdout+stderr)"
    ACERTOS=$(( ACERTOS + 1 ))
fi

TOTAL=$(( TOTAL + 1 ))
if grep -rqF "SEGREDO-DE-TESTE-NAO-VER" "$dir/.estado.json" 2>/dev/null; then
    printf '  FALHOU   %-50s\n' "a URL de heartbeat aparece no arquivo de estado"
else
    printf '  OK       %-50s\n' "a URL de heartbeat não aparece no arquivo de estado"
    ACERTOS=$(( ACERTOS + 1 ))
fi

# E o mais importante dos três: a URL não pode estar no ARGV de nenhum
# processo. Com a URL direto no `curl "$URL"`, qualquer outro usuário da VPS
# a lê em `ps` durante os 20 s do `--max-time` — e o arquivo de estado, o
# log e a saída JSON não são o único lugar por onde um segredo vaza.
TOTAL=$(( TOTAL + 1 ))
argv_vazado=0
: > "$LAB/ps-capturado.txt"
# O pinger é rodado em background para haver uma janela em que o processo
# existe; durante ela, `ps` é lido procurando a URL.
env BACKUP_DIR="$dir" \
    BACKUP_HEARTBEAT_URL="http://127.0.0.1:56996/hb/SEGREDO-DE-TESTE-NAO-VER" \
    BACKUP_PING_ESTADO_FILE="$dir/.estado.json" \
    BACKUP_PING_TIMEOUT_SEGUNDOS=3 \
    BACKUP_WATCHDOG_CHECK_REMOTE=0 BACKUP_WATCHDOG_EXIGIR_REMOTO=0 \
    PATH="$LAB/bin:$PATH" \
    bash "$PINGER" >/dev/null 2>&1 &
pid_pinger=$!
for _ in 1 2 3 4 5 6 7 8 9 10; do
    ps -eo args --no-headers 2>/dev/null >> "$LAB/ps-capturado.txt"
    kill -0 "$pid_pinger" 2>/dev/null || break
    sleep 0.05
done
wait "$pid_pinger" 2>/dev/null
if grep -qF "SEGREDO-DE-TESTE-NAO-VER" "$LAB/ps-capturado.txt"; then
    argv_vazado=1
    printf '  FALHOU   %-50s\n' "a URL aparece no argv de algum processo (ps)"
fi
if (( argv_vazado == 0 )); then
    printf '  OK       %-50s\n' "a URL não aparece no argv de nenhum processo (ps)"
    ACERTOS=$(( ACERTOS + 1 ))
fi

echo
echo "=============================================================================="
printf 'RESULTADO: %d de %d cenários com o veredito esperado\n' "$ACERTOS" "$TOTAL"
echo "=============================================================================="
limpar
[[ "$ACERTOS" -eq "$TOTAL" ]] || exit 1
