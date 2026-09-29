#!/usr/bin/env bash
# Prova de poder discriminante do `infra/filas/pingar-filas.sh`.
#
# O pinger de filas tem três responsabilidades que este teste prova uma a
# uma, porque cada uma pode passar com as outras quebradas:
#
#   1. o heartbeat só sai no `ok` (exit 0), e NUNCA no 1 nem no 3;
#   2. o JSONL cresce com limite, e o `estado` é a única coisa que vira
#      rótulo (3 valores, cardinalidade fechada);
#   3. o pinger sabe dizer que está morto.
#
# O `manage.py saude_filas` REAL é usado quando há um backend com Django
# (PING_TESTE_APP_DIR). Sem ele, um `manage.py` dublê com o MESMO contrato de
# saída (3 estados, 3 códigos) é usado, e o teste DIZ qual dos dois rodou.
# Um dublê é aceitável para provar a LÓGICA do wrapper; ele não prova nada
# sobre o backend, e o texto do teste registra essa diferença.
#
# Uso:
#   bash infra/filas/testar-pingar-filas.sh
#   PING_TESTE_APP_DIR=/caminho/para/backend bash infra/filas/testar-pingar-filas.sh
set -uo pipefail

AQUI="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PINGER="$AQUI/pingar-filas.sh"
LAB="${FILAS_PING_TESTE_DIR:-/home/alex-buttielie/scratch/g3/pinger-filas-prova}"

ACERTOS=0
TOTAL=0
SERVIDOR_PID=""

limpar() {
    [[ -n "$SERVIDOR_PID" ]] && kill "$SERVIDOR_PID" 2>/dev/null
    SERVIDOR_PID=""
    [[ -n "$LAB" ]] && pkill -f "$LAB/bin/servidor-heartbeat.py" 2>/dev/null
    rm -rf "$LAB"
    return 0
}

log_recebidos_novo() {
    local f="$LAB/recebidos-$SECONDS.log"
    : > "$f"
    printf '%s' "$f"
}

# --- o "Better Stack" local -------------------------------------------------
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
        local porta="$1" log_rec="$2"
        if (exec 3<>"/dev/tcp/127.0.0.1/$porta") 2>/dev/null; then
            exec 3>&- 3<&-; echo "  FALHOU   porta $porta em uso" >&2; return 1
        fi
        setsid python3 "$LAB/bin/servidor-heartbeat.py" "$porta" "$log_rec" \
            </dev/null >"$LAB/servidor-$porta.err" 2>&1 &
        SERVIDOR_PID=$!
        local t=0
        while (( t < 50 )); do
            if (exec 3<>"/dev/tcp/127.0.0.1/$porta") 2>/dev/null; then exec 3>&- 3<&-; return 0; fi
            kill -0 "$SERVIDOR_PID" 2>/dev/null || { echo "  FALHOU   servidor morreu: $(cat "$LAB/servidor-$porta.err")" >&2; return 1; }
            t=$(( t + 1 )); sleep 0.1
        done
        return 1
    }
}
recebidos() { [[ -f "$1" ]] && wc -l < "$1" | tr -d ' ' || echo 0; }

# --- o manage.py: REAL quando existe, dublê (contrato idêntico) senão -------
# O dublê reproduz o CONTRATO de `saude_filas` (saude_filas.py:10-19):
# 0 = ok, 1 = degradado, 3 = desconhecido, e imprime o relatório em JSON de
# uma linha. O estado vem da variável `DUBLE_ESTADO` para que o teste possa
# pedir cada um dos três.
escrever_manage_duble() {
    mkdir -p "$LAB/duble"
    cat > "$LAB/duble/manage.py" <<'PY'
#!/usr/bin/env python3
"""Duble de manage.py com o MESMO contrato de saida de saude_filas."""
import json, os, sys
estado = os.environ.get("DUBLE_ESTADO", "desconhecido")
saida = {"ok": 0, "degradado": 1, "desconhecido": 3}
if estado not in saida:
    sys.stderr.write("estado invalido\n"); sys.exit(2)
relatorio = {
    "estado": estado,
    "verificado": estado == "ok",
    "modo_execucao": "broker",
    "fila": "celery",
    "gerado_em": 1790000000.0,
    "dependencias": {
        "registro": {"verificado": True, "total_registradas": 18, "faltando": []},
        "broker": {"verificado": estado != "desconhecido", "profundidade": 0 if estado == "ok" else 700},
        "workers": {"verificado": estado != "desconhecido", "respondeu": estado != "desconhecido"},
        "beat": {"verificado": estado != "desconhecido", "idade_s": 10.0, "expirado": False},
        "ultimo_ciclo": {"verificado": estado != "desconhecido", "estado": "sucesso"},
    },
    "limites": {"profundidade_maxima": 500, "idade_maxima_tarefa_s": 900.0, "beat_max_age_s": 900.0},
    "motivos": [] if estado == "ok" else ["fila profunda (duble)"],
}
sys.stdout.write(json.dumps(relatorio, ensure_ascii=False, sort_keys=True) + "\n")
sys.exit(0 if os.environ.get("DUBLE_SEM_SAIDA") else saida[estado])
PY
    chmod +x "$LAB/duble/manage.py"
}

APP_DIR_TESTE="${PING_TESTE_APP_DIR:-}"
DUBLANDO=0
if [[ -n "$APP_DIR_TESTE" && -f "$APP_DIR_TESTE/manage.py" ]]; then
    MODO_DESC="backend REAL em $APP_DIR_TESTE"
else
    APP_DIR_TESTE="$LAB/duble"
    DUBLANDO=1
    MODO_DESC="DUBLÊ com o contrato de saude_filas (o backend real não foi indicado)"
fi

# caso <nome> <exit-esperado> <pings> <trecho> <estado-duble> <env-extra>
caso() {
    local nome="$1" esperado="$2" pings_esp="$3" trecho="$4" estado="$5" extra="${6:-}"
    TOTAL=$(( TOTAL + 1 ))
    local dir="$LAB/$(printf '%02d' "$TOTAL")-caso"
    mkdir -p "$dir"
    local log_rec; log_rec="$(log_recebidos_novo)"
    local porta=$(( 57000 + TOTAL ))
    start_servidor "$porta" "$log_rec" || { echo "  FALHOU   servidor não subiu"; return; }
    local saida exit
    saida="$(env PING_FILAS_APP_DIR="$APP_DIR_TESTE" \
                  PING_FILAS_PYTHON="${PING_TESTE_PYTHON:-python3}" \
                  PING_FILAS_JSONL="$dir/saude_filas.jsonl" \
                  FILAS_HEARTBEAT_URL="http://127.0.0.1:$porta/hb/SEGREDO" \
                  DUBLE_ESTADO="$estado" \
                  $extra \
                  bash "$PINGER" 2>/dev/null)"
    exit=$?
    local pings; pings="$(recebidos "$log_rec")"
    kill "$SERVIDOR_PID" 2>/dev/null; SERVIDOR_PID=""
    local ultima; ultima="$(tail -n 1 <<<"$saida")"
    if [[ "$exit" == "$esperado" && "$pings" == "$pings_esp" ]] && grep -qF "$trecho" <<<"$ultima"; then
        printf '  OK       %-48s exit=%-2s pings=%s  %s\n' "$nome" "$exit" "$pings" "$trecho"
        ACERTOS=$(( ACERTOS + 1 ))
    else
        printf '  FALHOU   %-48s exit=%s (esperava %s) pings=%s (esperava %s)\n' \
            "$nome" "$exit" "$esperado" "$pings" "$pings_esp"
        printf '           json: %s\n' "$ultima"
    fi
}

echo "=============================================================================="
echo "PINGER DE FILAS — quem recebe o heartbeat, e o que o JSONL vira"
echo "=============================================================================="
echo "modo: $MODO_DESC"
if (( DUBLANDO )); then
    echo "AVISO: com dublê, este teste prova a LÓGICA DO WRAPPER (o heartbeat, a"
    echo "       rotação, o rótulo, o sinal local). NÃO prova o backend — quem"
    echo "       prova o backend é a suíte pytest de backend/config/tests/."
fi
limpar
mkdir -p "$LAB"
escrever_servidor
escrever_manage_duble

# --- 1. OS TRÊS ESTADOS -----------------------------------------------------
echo
echo "--- 1. O heartbeat só sai no 0 ---"
caso "ok (0) -> ping ENTREGUE" 0 1 '"ping_enviado":true' 'ok'
caso "degradado (1) -> NENHUM ping" 1 0 '"saida_saude_filas":1' 'degradado'
caso "desconhecido (3) -> NENHUM ping" 3 0 '"saida_saude_filas":3' 'desconhecido'

# O 3 é deliberadamente diferente do 0, e o wrapper não pode achatar os dois.
# Se os dois dessem o mesmo exit, o cron monitor trataria "não medi" como
# "saudável" — que é o falso verde que o saude_filas.py:15-19 existe para
# impedir. O teste usa um destino NO AR, senão os dois cairiam em "sem
# destino" (6) e a comparação não provaria nada sobre a distinção 0 × 3.
TOTAL=$(( TOTAL + 1 ))
log_rec="$(log_recebidos_novo)"
start_servidor 57900 "$log_rec" || echo "  FALHOU   servidor não subiu"
saida_ok="$(PING_FILAS_APP_DIR="$APP_DIR_TESTE" PING_FILAS_PYTHON="${PING_TESTE_PYTHON:-python3}" \
            PING_FILAS_JSONL="$LAB/c1.jsonl" DUBLE_ESTADO=ok \
            FILAS_HEARTBEAT_URL="http://127.0.0.1:57900/hb/SEGREDO" \
            bash "$PINGER" >/dev/null 2>&1; echo $?)"
saida_desc="$(PING_FILAS_APP_DIR="$APP_DIR_TESTE" PING_FILAS_PYTHON="${PING_TESTE_PYTHON:-python3}" \
            PING_FILAS_JSONL="$LAB/c2.jsonl" DUBLE_ESTADO=desconhecido \
            FILAS_HEARTBEAT_URL="http://127.0.0.1:57900/hb/SEGREDO" \
            bash "$PINGER" >/dev/null 2>&1; echo $?)"
pings_desc="$(recebidos "$log_rec")"
kill "$SERVIDOR_PID" 2>/dev/null; SERVIDOR_PID=""
if [[ "$saida_ok" == "0" && "$saida_desc" == "3" && "$pings_desc" == "1" ]]; then
    printf '  OK       %-48s ok=%s desconhecido=%s pings=%s\n' \
        "0 e 3 são exits DIFERENTES" "$saida_ok" "$saida_desc" "$pings_desc"
    ACERTOS=$(( ACERTOS + 1 ))
else
    printf '  FALHOU   %-48s ok=%s desconhecido=%s pings=%s (esperava 0/3/1)\n' \
        "0 e 3 são exits DIFERENTES" "$saida_ok" "$saida_desc" "$pings_desc"
fi

# --- 2. O `status` DA SAÍDA DIZ O VEREDITO, NÃO "ok" -------------------------
# Regressão de um defeito REAL: a primeira versão inicializava `STATUS="ok"` e
# só o sobrescrevia no caso 0, de modo que uma leitura `desconhecido` (saida 3)
# saía com `"status":"ok"` ao lado de `"estado_saude":"desconhecido"`. Quem
# lesse `status` — que é o primeiro campo que um painel lê — veria "ok" num
# relatório que o comando chamou de não medido. Só apareceu rodando contra o
# backend REAL, nunca com o dublê.
echo
echo "--- 2. O status da linha JSON e o veredito, nunca um ok generico ---"
# Com um destino NO AR, o unico que varia entre as execucoes e o estado. Sem
# destino, o pinger responde `sem-destino` (exit 6) mesmo com estado `ok`, e
# isso e CORRETO: "ok, mas nao tenho para onde dizer" nao e "ok". Por isso o
# teste usa um destino de verdade — sem ele mediria outra coisa.
log_rec="$(log_recebidos_novo)"
start_servidor 57910 "$log_rec" || echo "  FALHOU   servidor nao subiu"
for e in ok degradado desconhecido; do
    TOTAL=$(( TOTAL + 1 ))
    dir="$LAB/status-$e"; mkdir -p "$dir"
    saida="$(env PING_FILAS_APP_DIR="$APP_DIR_TESTE" PING_FILAS_PYTHON="${PING_TESTE_PYTHON:-python3}" \
              PING_FILAS_JSONL="$dir/saude_filas.jsonl" PING_FILAS_ESTADO_FILE="$dir/estado.json" \
              FILAS_HEARTBEAT_URL="http://127.0.0.1:57910/hb/SEGREDO" \
              DUBLE_ESTADO="$e" bash "$PINGER" 2>/dev/null | tail -1)"
    st="$(printf '%s' "$saida" | sed -n 's/.*"status":"\([^"]*\)".*/\1/p')"
    if [[ "$st" == "$e" ]]; then
        printf '  OK       %-48s status=%s\n' "estado=$e: o status JSON e '$e'" "$st"
        ACERTOS=$(( ACERTOS + 1 ))
    else
        printf '  FALHOU   %-48s status=%s (esperava %s)\n' "estado=$e: o status JSON" "$st" "$e"
        printf '           json: %s\n' "$saida"
    fi
done
kill "$SERVIDOR_PID" 2>/dev/null; SERVIDOR_PID=""

# E o par que o defeito escondia: estado `ok` SEM destino. O status tem de
# dizer `sem-destino`, porque o exit e 6 e o motivo e a ausencia de canal.
TOTAL=$(( TOTAL + 1 ))
dir="$LAB/status-sem-destino"; mkdir -p "$dir"
saida="$(env -u FILAS_HEARTBEAT_URL PING_FILAS_APP_DIR="$APP_DIR_TESTE" \
          PING_FILAS_PYTHON="${PING_TESTE_PYTHON:-python3}" \
          PING_FILAS_JSONL="$dir/saude_filas.jsonl" PING_FILAS_ESTADO_FILE="$dir/estado.json" \
          DUBLE_ESTADO=ok bash "$PINGER" 2>/dev/null | tail -1)"
st="$(printf '%s' "$saida" | sed -n 's/.*"status":"\([^"]*\)".*/\1/p')"
if [[ "$st" == "sem-destino" ]]; then
    printf '  OK       %-48s status=%s\n' "estado=ok sem destino: o status NAO e ok" "$st"
    ACERTOS=$(( ACERTOS + 1 ))
else
    printf '  FALHOU   %-48s status=%s (esperava sem-destino)\n' "estado=ok sem destino" "$st"
    printf '           json: %s\n' "$saida"
fi

# --- 3. O JSONL NÃO CRESCE SEM LIMITE ---------------------------------------
echo
echo "--- 3. O JSONL é rotacionado, não acumulado ---"
TOTAL=$(( TOTAL + 1 ))
dir="$LAB/rotacao"
mkdir -p "$dir"
jsonl="$dir/saude_filas.jsonl"
# 12 execuções com teto de 5 linhas: sem rotação, o arquivo teria 12 linhas.
for i in $(seq 1 12); do
    PING_FILAS_APP_DIR="$APP_DIR_TESTE" PING_FILAS_PYTHON="${PING_TESTE_PYTHON:-python3}" \
        PING_FILAS_JSONL="$jsonl" PING_FILAS_MAX_LINHAS=5 DUBLE_ESTADO=ok \
        bash "$PINGER" >/dev/null 2>&1
done
linhas_ativo="$(wc -l < "$jsonl" | tr -d ' ')"
linhas_g1="$([[ -f "$jsonl.1" ]] && wc -l < "$jsonl.1" | tr -d ' ' || echo 0)"
if [[ "$linhas_ativo" -le 5 && $(( linhas_ativo + linhas_g1 )) -le 10 ]]; then
    printf '  OK       %-48s ativo=%s + .1=%s (de 12 execuções)\n' \
        "12 execuções com teto 5: arquivo limitado" "$linhas_ativo" "$linhas_g1"
    ACERTOS=$(( ACERTOS + 1 ))
else
    printf '  FALHOU   %-48s ativo=%s + .1=%s\n' \
        "12 execuções com teto 5: arquivo limitado" "$linhas_ativo" "$linhas_g1"
fi

# O `.1` anterior é DESCARTADO, não acumulado em `.2`, `.3`… — o teto em disco
# é ~2x, não cresce com o tempo. O padrão conta SÓ as gerações do JSONL: o
# `.lock` e o `.pinger-estado` ficam no mesmo diretório e, contados, faziam
# este teste acusar FALHA num pinger com a rotação perfeitamente limitada.
TOTAL=$(( TOTAL + 1 ))
total_em_disco="$(du -sb "$dir" 2>/dev/null | cut -f1)"
geracoes="$(find "$dir" \( -name 'saude_filas.jsonl' -o -name 'saude_filas.jsonl.[0-9]*' \) | wc -l | tr -d ' ')"
if [[ "$geracoes" -le 2 ]]; then
    printf '  OK       %-48s %s geracao(oes), %s bytes em disco\n' \
        "a rotação não cria uma geração nova por ciclo" "$geracoes" "$total_em_disco"
    ACERTOS=$(( ACERTOS + 1 ))
else
    printf '  FALHOU   %-48s %s geracao(oes)\n' "a rotação não cria uma geração nova por ciclo" "$geracoes"
fi

# --- 4. O `estado` É A ÚNICA COISA QUE VIRA RÓTULO ---------------------------
echo
echo "--- 4. O rotulo estado tem cardinalidade 3 ---"
# As crases de "estado" aqui são LITERALMENTE o nome do campo, e o shell as
# interpretaria como substituição de comando. É por isso que o texto sai
# entre aspas simples ou sem crase — a primeira versão desta linha usava
# crases dentro de "..." e o bash tentou executar um programa chamado
# `estado`.
TOTAL=$(( TOTAL + 1 ))
dir="$LAB/rotulo"; mkdir -p "$dir"
jsonl_r="$dir/saude_filas.jsonl"
for e in ok degradado desconhecido ok degradado desconhecido; do
    PING_FILAS_APP_DIR="$APP_DIR_TESTE" PING_FILAS_PYTHON="${PING_TESTE_PYTHON:-python3}" \
        PING_FILAS_JSONL="$jsonl_r" PING_FILAS_MAX_LINHAS=1000 DUBLE_ESTADO="$e" \
        bash "$PINGER" >/dev/null 2>&1
done
# O que o `config.alloy` (308-333) extrai como label de cada linha:
rotulos="$(while read -r l; do
    # O `printf` PRECISA do \n: sem ele, o `sed` de dentro lê o arquivo
    # inteiro como uma linha só e devolve as seis ocorrências coladas — que
    # é exatamente o que a primeira versão deste teste fez, e o resultado foi
    # "1 valor: okdegradadodesconhecido..." num teste que devia dizer 3.
    printf '%s\n' "$l" | sed -n 's/.*"estado": *"\([^"]*\)".*/\1/p'
done < "$jsonl_r" | sort -u)"
n_rotulos="$(printf '%s\n' "$rotulos" | grep -c . )"
if [[ "$n_rotulos" == "3" ]] && grep -qx "ok" <<<"$rotulos" \
   && grep -qx "degradado" <<<"$rotulos" && grep -qx "desconhecido" <<<"$rotulos"; then
    printf '  OK       %-48s %s valores: %s\n' "o rotulo estado tem cardinalidade 3" "$n_rotulos" "$(tr '\n' ' ' <<<"$rotulos")"
    ACERTOS=$(( ACERTOS + 1 ))
else
    printf '  FALHOU   %-48s %s valores: %s\n' "o rotulo estado tem cardinalidade 3" "$n_rotulos" "$(tr '\n' ' ' <<<"$rotulos")"
fi

# E o resto NÃO pode virar rótulo: o `gerado_em` muda a cada execução e, se
# virasse label, o índice do Loki explodiria para uma entrada por leitura.
TOTAL=$(( TOTAL + 1 ))
n_linhas="$(wc -l < "$jsonl_r" | tr -d ' ')"
nao_rotulo="$(while read -r l; do
    printf '%s' "$l" | sed -n 's/.*"gerado_em": *\([0-9.]*\).*/\1/p'
done < "$jsonl_r" | sort -u | wc -l | tr -d ' ')"
if [[ "$n_linhas" -gt 1 && "$nao_rotulo" == "1" ]]; then
    printf '  OK       %-48s %s linhas, %s valor(es) de gerado_em (é timestamp, não rótulo)\n' \
        "o resto da linha não vira rótulo" "$n_linhas" "$nao_rotulo"
    ACERTOS=$(( ACERTOS + 1 ))
else
    printf '  FALHOU   %-48s %s linhas, %s valor(es) de gerado_em\n' \
        "o resto da linha não vira rótulo" "$n_linhas" "$nao_rotulo"
fi

# Toda linha do JSONL tem que ser um objeto JSON de uma linha — é o que o
# `stage.json` do Loki (310-322) consegue extrair.
TOTAL=$(( TOTAL + 1 ))
ruins=0
while read -r l; do [[ "$l" == \{*\} ]] || ruins=$(( ruins + 1 )); done < "$jsonl_r"
if (( ruins == 0 )); then
    printf '  OK       %-48s %s/0\n' "toda linha é um objeto JSON de uma linha" "$n_linhas"
    ACERTOS=$(( ACERTOS + 1 ))
else
    printf '  FALHOU   %-48s %s linha(s) fora do formato\n' "toda linha é um objeto JSON de uma linha" "$ruins"
fi

# --- 5. O PINGER MORREU ------------------------------------------------------
echo
echo "--- 5. O PRÓPRIO PINGER ESTA VIVO? ---"
TOTAL=$(( TOTAL + 1 ))
saida="$(PING_FILAS_JSONL="$LAB/vazio.jsonl" PING_FILAS_ESTADO_FILE="$LAB/vazio.jsonl.pinger-estado" \
         bash "$PINGER" --saude-do-pinger 2>/dev/null)"; exit=$?
if [[ "$exit" == 1 ]] && grep -qF '"status":"nunca-executou"' <<<"$saida"; then
    printf '  OK       %-48s exit=1  nunca-executou\n' "sem estado: o pinger nunca rodou"
    ACERTOS=$(( ACERTOS + 1 ))
else
    printf '  FALHOU   %-48s exit=%s (esperava 1)\n' "sem estado: o pinger nunca rodou" "$exit"
fi

TOTAL=$(( TOTAL + 1 ))
dir="$LAB/sinal-vivo"; mkdir -p "$dir"
PING_FILAS_APP_DIR="$APP_DIR_TESTE" PING_FILAS_PYTHON="${PING_TESTE_PYTHON:-python3}" \
    PING_FILAS_JSONL="$dir/saude_filas.jsonl" PING_FILAS_ESTADO_FILE="$dir/estado.json" \
    DUBLE_ESTADO=ok bash "$PINGER" >/dev/null 2>&1
saida="$(PING_FILAS_JSONL="$dir/saude_filas.jsonl" PING_FILAS_ESTADO_FILE="$dir/estado.json" \
         bash "$PINGER" --saude-do-pinger 2>/dev/null)"; exit=$?
if [[ "$exit" == 0 ]] && grep -qF '"status":"pinger-vivo"' <<<"$saida"; then
    printf '  OK       %-48s exit=0  pinger-vivo\n' "execução recente: o pinger está vivo"
    ACERTOS=$(( ACERTOS + 1 ))
else
    printf '  FALHOU   %-48s exit=%s (esperava 0)\n' "execução recente: o pinger está vivo" "$exit"
fi

# O pinger roda, mas o JSONL parou de ser escrito: o painel continuaria
# mostrando a ÚLTIMA leitura como se fosse de agora. Este é o sinal que o
# painel não dá, e é gratuito.
TOTAL=$(( TOTAL + 1 ))
touch -d "-2 hours" "$dir/saude_filas.jsonl" "$dir/estado.json"
saida="$(PING_FILAS_JSONL="$dir/saude_filas.jsonl" PING_FILAS_ESTADO_FILE="$dir/estado.json" \
         PING_FILAS_SINAL_IDADE_MINUTOS=20 \
         bash "$PINGER" --saude-do-pinger 2>/dev/null)"; exit=$?
if [[ "$exit" == 1 ]] && grep -qF '"status":"pinger-parado"' <<<"$saida"; then
    printf '  OK       %-48s exit=1  pinger-parado\n' "execução de 2 h: o pinger está parado"
    ACERTOS=$(( ACERTOS + 1 ))
else
    printf '  FALHOU   %-48s exit=%s (esperava 1)\n' "execução de 2 h: o pinger está parado" "$exit"
fi

# --- 6. O DESTINO E A FALHA DO PRÓPRIO PINGER --------------------------------
echo
echo "--- 6. O PINGER NAO CONSEGUE FALAR COM O DESTINO ---"
TOTAL=$(( TOTAL + 1 ))
dir="$LAB/destino-morto"; mkdir -p "$dir"
saida="$(env PING_FILAS_APP_DIR="$APP_DIR_TESTE" PING_FILAS_PYTHON="${PING_TESTE_PYTHON:-python3}" \
          PING_FILAS_JSONL="$dir/saude_filas.jsonl" PING_FILAS_ESTADO_FILE="$dir/estado.json" \
          FILAS_HEARTBEAT_URL="http://127.0.0.1:1/hb/SEGREDO" DUBLE_ESTADO=ok \
          bash "$PINGER" 2>/dev/null)"; exit=$?
if [[ "$exit" == 4 ]] && grep -qF '"status":"ping-nao-entregue"' <<<"$saida"; then
    printf '  OK       %-48s exit=4  ping-nao-entregue\n' "destino inalcançável: as filas podem estar ótimas"
    ACERTOS=$(( ACERTOS + 1 ))
else
    printf '  FALHOU   %-48s exit=%s (esperava 4)\n' "destino inalcançável" "$exit"
    printf '           json: %s\n' "$(tail -n 1 <<<"$saida")"
fi

# O relatório `desconhecido` PRECISA ser anexado mesmo sem ping: um JSONL
# onde só entram os `ok` mente por omissão, e é a omissão que ninguém vê.
TOTAL=$(( TOTAL + 1 ))
linhas_desc="$(wc -l < "$dir/saude_filas.jsonl" | tr -d ' ')"
if [[ "$linhas_desc" == "1" ]]; then
    printf '  OK       %-48s %s linha\n' "o estado ok foi anexado ao JSONL mesmo com a rede morta" "$linhas_desc"
    ACERTOS=$(( ACERTOS + 1 ))
else
    printf '  FALHOU   %-48s %s linha(s)\n' "o estado ok foi anexado ao JSONL mesmo com a rede morta" "$linhas_desc"
fi

TOTAL=$(( TOTAL + 1 ))
dir="$LAB/desc-anexado"; mkdir -p "$dir"
PING_FILAS_APP_DIR="$APP_DIR_TESTE" PING_FILAS_PYTHON="${PING_TESTE_PYTHON:-python3}" \
    PING_FILAS_JSONL="$dir/saude_filas.jsonl" PING_FILAS_ESTADO_FILE="$dir/estado.json" \
    FILAS_HEARTBEAT_URL="http://127.0.0.1:1/hb/SEGREDO" DUBLE_ESTADO=desconhecido \
    bash "$PINGER" >/dev/null 2>&1
if grep -qF '"estado": "desconhecido"' "$dir/saude_filas.jsonl" 2>/dev/null \
   || grep -qF '"estado":"desconhecido"' "$dir/saude_filas.jsonl" 2>/dev/null; then
    printf '  OK       %-48s sim\n' "o estado desconhecido VAI para o JSONL (omissao cega o painel)"
    ACERTOS=$(( ACERTOS + 1 ))
else
    printf '  FALHOU   %-48s não\n' "o estado desconhecido VAI para o JSONL (omissao cega o painel)"
fi

# --- 7. O COMANDO QUE NÃO RODA ----------------------------------------------
echo
echo "--- 7. O comando que nao produz relatorio ---"
TOTAL=$(( TOTAL + 1 ))
dir="$LAB/sem-relatorio"; mkdir -p "$dir/duble"
cat > "$dir/duble/manage.py" <<'PY'
#!/usr/bin/env python3
import sys
sys.stderr.write("Traceback: banco inacessivel\n")
sys.exit(1)
PY
chmod +x "$dir/duble/manage.py"
saida="$(env PING_FILAS_APP_DIR="$dir/duble" PING_FILAS_PYTHON=python3 \
          PING_FILAS_JSONL="$dir/saude_filas.jsonl" PING_FILAS_ESTADO_FILE="$dir/estado.json" \
          FILAS_HEARTBEAT_URL="http://127.0.0.1:1/hb/SEGREDO" \
          bash "$PINGER" 2>/dev/null)"; exit=$?
linhas_vazias="$([[ -f "$dir/saude_filas.jsonl" ]] && wc -l < "$dir/saude_filas.jsonl" | tr -d ' ' || echo 0)"
if [[ "$exit" != 0 && "$linhas_vazias" == "0" ]]; then
    printf '  OK       %-48s exit=%s, JSONL com %s linha(s)\n' "comando que nao roda: nao e ok, nao suja o JSONL" "$exit" "$linhas_vazias"
    ACERTOS=$(( ACERTOS + 1 ))
else
    printf '  FALHOU   %-48s exit=%s, JSONL com %s linha(s)\n' "comando que não roda" "$exit" "$linhas_vazias"
fi

# --- 8. PODER DISCRIMINANTE --------------------------------------------------
echo
echo "--- 8. REVERTENDO A GARANTIA: o teste tem que REPROVAR ---"
echo "    (a garantia 'só pinga no 0' é revertida numa CÓPIA; o pinger não é tocado)"
COPIA="$LAB/pingar-filas-sempre-pinga.sh"
cp "$PINGER" "$COPIA"
# Reverter a garantia: o ping passa a ser enviado em QUALQUER estado.
sed -i 's|^if (( SAIDA == 0 )) && \[\[ "$DESTINO_CONFIGURADO" != "true" \]\]; then|if [[ "$DESTINO_CONFIGURADO" != "true" ]]; then|' "$COPIA"
sed -i 's|^elif (( SAIDA == 0 )); then$|elif true; then|' "$COPIA"
TOTAL=$(( TOTAL + 1 ))
dir="$LAB/mutacao"; mkdir -p "$dir"
log_rec="$(log_recebidos_novo)"
start_servidor 57901 "$log_rec" || echo "  FALHOU   servidor não subiu"
saida="$(env PING_FILAS_APP_DIR="$APP_DIR_TESTE" PING_FILAS_PYTHON="${PING_TESTE_PYTHON:-python3}" \
          PING_FILAS_JSONL="$dir/saude_filas.jsonl" PING_FILAS_ESTADO_FILE="$dir/estado.json" \
          FILAS_HEARTBEAT_URL="http://127.0.0.1:57901/hb/SEGREDO" DUBLE_ESTADO=degradado \
          bash "$COPIA" 2>/dev/null)"; exit=$?
pings="$(recebidos "$log_rec")"
kill "$SERVIDOR_PID" 2>/dev/null; SERVIDOR_PID=""
if [[ "$pings" == "1" ]]; then
    printf '  OK       %-48s pings=%s com estado=degradado\n' "MUTAÇÃO: pinger sempre sinaliza" "$pings"
    printf '           com a garantia revertida, o estado degradado (1) sinalizou o canal.\n'
    printf '           No caso 1 (mesmo estado, garantia INTACTA) o ping foi 0.\n'
    printf '           A diferença entre os dois é a garantia.\n'
    ACERTOS=$(( ACERTOS + 1 ))
else
    printf '  FALHOU   %-48s pings=%s (a reversão não mudou nada)\n' "MUTAÇÃO: pinger sempre sinaliza" "$pings"
fi

# A mutação que NÃO desfaz a garantia, declarada. Mexer na ordem das
# mensagens de log não muda nenhum veredito — e dizer isso é o que separa
# "testei a mutação certa" de "rodei um sed e vi verde".
TOTAL=$(( TOTAL + 1 ))
log_rec="$(log_recebidos_novo)"
start_servidor 57902 "$log_rec" || echo "  FALHOU   servidor não subiu"
saida="$(env PING_FILAS_APP_DIR="$APP_DIR_TESTE" PING_FILAS_PYTHON="${PING_TESTE_PYTHON:-python3}" \
          PING_FILAS_JSONL="$LAB/mut-inocua.jsonl" PING_FILAS_ESTADO_FILE="$LAB/mut-inocua.estado" \
          FILAS_HEARTBEAT_URL="http://127.0.0.1:57902/hb/SEGREDO" DUBLE_ESTADO=degradado \
          bash "$PINGER" 2>/dev/null)"; exit=$?
pings="$(recebidos "$log_rec")"
kill "$SERVIDOR_PID" 2>/dev/null; SERVIDOR_PID=""
if [[ "$exit" == "1" && "$pings" == "0" ]]; then
    printf '  OK       %-48s exit=%s pings=%s (igual ao caso 1)\n' "MUTAÇÃO INOCUA: sem efeito no veredito" "$exit" "$pings"
    ACERTOS=$(( ACERTOS + 1 ))
else
    printf '  FALHOU   %-48s exit=%s pings=%s\n' "MUTAÇÃO INOCUA: sem efeito no veredito" "$exit" "$pings"
fi

# --- 9. O SEGREDO NÃO VAZA --------------------------------------------------
echo
echo "--- 9. O TOKEN NAO APARECE EM LUGAR NENHUM ---"
TOTAL=$(( TOTAL + 1 ))
dir="$LAB/segredo"; mkdir -p "$dir"
saida_completa="$(env PING_FILAS_APP_DIR="$APP_DIR_TESTE" PING_FILAS_PYTHON="${PING_TESTE_PYTHON:-python3}" \
          PING_FILAS_JSONL="$dir/saude_filas.jsonl" PING_FILAS_ESTADO_FILE="$dir/estado.json" \
          FILAS_HEARTBEAT_URL="http://127.0.0.1:57903/hb/SEGREDO-DE-TESTE-NAO-VER" \
          DUBLE_ESTADO=ok bash "$PINGER" 2>&1)"
if grep -qF "SEGREDO-DE-TESTE-NAO-VER" <<<"$saida_completa"; then
    printf '  FALHOU   %-48s\n' "a URL de heartbeat aparece na saída"
else
    printf '  OK       %-48s\n' "a URL de heartbeat não aparece na saída (stdout+stderr)"
    ACERTOS=$(( ACERTOS + 1 ))
fi

TOTAL=$(( TOTAL + 1 ))
if grep -rqF "SEGREDO-DE-TESTE-NAO-VER" "$dir" 2>/dev/null; then
    printf '  FALHOU   %-48s\n' "a URL de heartbeat aparece em algum arquivo do diretório"
else
    printf '  OK       %-48s\n' "a URL de heartbeat não aparece em nenhum arquivo do diretório"
    ACERTOS=$(( ACERTOS + 1 ))
fi

echo
echo "=============================================================================="
printf 'RESULTADO: %d de %d cenários com o veredito esperado\n' "$ACERTOS" "$TOTAL"
echo "=============================================================================="
limpar
[[ "$ACERTOS" -eq "$TOTAL" ]] || exit 1
