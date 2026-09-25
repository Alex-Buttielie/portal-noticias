#!/usr/bin/env bash
# Execução do frontend Next.js em modo `output: "standalone"` fora do
# `npm start` (run 20260925-1020-observabilidade, achados B5 e critério 29).
#
# O padrão correto já existe no `frontend/Dockerfile:34-42,47`; o que faltava era
# a versão para a topologia ATIVA da VPS (PM2 + Nginx), que hoje roda
# `npm start` e portanto:
#   * não define HOSTNAME — o Next cai no hostname do container/host e o
#     servidor pode não escutar no que o Nginx espera;
#   * não tem a árvore de diretórios do standalone (que exige preservar
#     `.next/standalone/` com o `node_modules` rastreado e o `server.js` na
#     raiz) — roda o build inteiro no ar;
#   * não tem o smoke antes de promover, ou seja, uma release quebrada só é
#     descoberta pelo usuário (critério 30: o symlink ativo não pode mudar).
#
# Este script NÃO substitui o PM2 nem o systemd: ele prepara a árvore, faz o
# smoke e executa. Quem promove (symlink `current` + restart do supervisor) é o
# deploy — ver o plano de release atômica em `CI-CD.md` (seção P1-5) e a nota
# "POR QUE O PM2 AINDA NÃO USA ISSO" no fim deste arquivo.
#
# Uso típico (uma vez por release, antes de trocar o symlink):
#   infra/standalone/run-standalone.sh prepare --dir /home/apps/portal-prod/frontend/releases/<sha>/standalone
#   infra/standalone/run-standalone.sh smoke  --dir /home/apps/portal-prod/frontend/releases/<sha>/standalone
# E, com o supervisor apontando para `releases/current/standalone`:
#   infra/standalone/run-standalone.sh start
#
# Nenhum segredo é lido ou impresso aqui: as variáveis NEXT_PUBLIC_* já foram
# embutidas no bundle no momento do build e este script não as repõe.
set -euo pipefail

# Falha cedo e com nome, em vez de um `curl` que não volta: um smoke que roda
# "para sempre" segura o pipeline de deploy sem dar sinal.
ERRO_AO_USAR=64
FALHA_SMOKE=69

log() { printf '[standalone] %s\n' "$*"; }
erro() { printf '[standalone] ERRO: %s\n' "$*" >&2; }

uso() {
    cat >&2 <<'USO'
uso: run-standalone.sh <comando> [opcoes]

comandos:
  prepare   copia `public/` e `.next/static` para a árvore standalone
  smoke     sobe o servidor numa porta livre, valida e derruba
  start     executa o servidor (uso por PM2/systemd; não retorna)

opcoes:
  --dir DIR       árvore standalone (padrão: <frontend>/.next/standalone)
  --public DIR    origem dos assets públicos (padrão: <frontend>/public)
  --static DIR    origem do .next/static (padrão: <frontend>/.next/static)
  --port N        porta do smoke/start (padrão: 3000)
  --host H        bind address (padrão: 0.0.0.0)
  --timeout S     espera do smoke, em segundos (padrão: 60)
  -h | --help     esta ajuda

variáveis de ambiente lidas (todas opcionais):
  PORT, HOSTNAME, NEXT_TELEMETRY_DISABLED
USO
    exit "$ERRO_AO_USAR"
}

COMANDO="${1:-}"
case "${COMANDO:-}" in
    -h|--help|"") uso ;;
esac
shift || true

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
FRONTEND_DIR="${FRONTEND_DIR:-$REPO_DIR/frontend}"

# Globais do smoke (o trap de limpeza roda fora do escopo da função).
SMOKE_PID=""
SMOKE_LOG=""

DIR="$FRONTEND_DIR/.next/standalone"
PUBLIC_DIR="$FRONTEND_DIR/public"
STATIC_DIR="$FRONTEND_DIR/.next/static"
PORT="${PORT:-3000}"
BIND_HOST="${HOSTNAME:-0.0.0.0}"
TIMEOUT_SEGUNDOS=60

while [[ $# -gt 0 ]]; do
    case "$1" in
        --dir) DIR="${2:?--dir exige valor}"; shift 2 ;;
        --public) PUBLIC_DIR="${2:?--public exige valor}"; shift 2 ;;
        --static) STATIC_DIR="${2:?--static exige valor}"; shift 2 ;;
        --port) PORT="${2:?--port exige valor}"; shift 2 ;;
        --host) BIND_HOST="${2:?--host exige valor}"; shift 2 ;;
        --timeout) TIMEOUT_SEGUNDOS="${2:?--timeout exige valor}"; shift 2 ;;
        -h|--help) uso ;;
        *) erro "opção desconhecida: $1"; uso ;;
    esac
done

case "$COMANDO" in
    prepare|smoke|start) ;;
    *) erro "comando desconhecido: $COMANDO"; uso ;;
esac

exigir() {
    if [[ ! -e "$1" ]]; then
        erro "$2: $1 não existe"
        exit "$ERRO_AO_USAR"
    fi
}

exigir_comando() {
    command -v "$1" >/dev/null 2>&1 || { erro "dependência ausente: $1 ($3)"; exit "$ERRO_AO_USAR"; }
}

# ---------------------------------------------------------------- prepare ---
# A cópia é a mesma do `frontend/Dockerfile` (runner stage): o `server.js` do
# standalone espera `.next/static` e `public/` ao lado dele, dentro da própria
# árvore — sem eles a página abre mas TODOS os assets 404 e o portal "sobe"
# quebrado, que é o pior tipo de falha porque parece sucesso.
preparar() {
    exigir "$DIR/server.js" "árvore standalone inválida (rode \`next build\` antes)"
    log "preparando $DIR"

    if [[ -d "$PUBLIC_DIR" ]] && [[ -n "$(ls -A "$PUBLIC_DIR" 2>/dev/null)" ]]; then
        mkdir -p -- "$DIR/public"
        if [[ "$(cd "$PUBLIC_DIR" && pwd -P)" == "$(cd "$DIR/public" && pwd -P)" ]]; then
            # `prepare` idempotente: reexecutar sobre a mesma árvore não pode
            # falhar com o erro cru do `cp` ("are the same file").
            log "public/ já está no lugar em $DIR/public"
        else
            cp -a -- "$PUBLIC_DIR/." "$DIR/public/"
            log "public/ copiado de $PUBLIC_DIR"
        fi
    else
        # O repositório hoje não tem `public/` (o Dockerfile já cria a pasta
        # pelo mesmo motivo). Ausência de asset público NÃO é erro de release:
        # erro seria falhar um deploy por um diretório que não existe.
        mkdir -p -- "$DIR/public"
        log "AVISO: $PUBLIC_DIR ausente ou vazio; criada pasta public/ vazia (mesmo comportamento do frontend/Dockerfile)"
    fi

    if [[ -d "$STATIC_DIR" ]] && [[ -n "$(ls -A "$STATIC_DIR" 2>/dev/null)" ]]; then
        mkdir -p -- "$DIR/.next/static"
        if [[ "$(cd "$STATIC_DIR" && pwd -P)" == "$(cd "$DIR/.next/static" && pwd -P)" ]]; then
            log ".next/static já está no lugar em $DIR/.next/static"
        else
            cp -a -- "$STATIC_DIR/." "$DIR/.next/static/"
            log ".next/static copiado de $STATIC_DIR"
        fi
    else
        erro ".next/static ausente ou vazio: $STATIC_DIR (build incompleto; o servidor subiria sem nenhum asset)"
        exit "$ERRO_AO_USAR"
    fi
    log "prepare concluído"
}

# ------------------------------------------------------------------ smoke ---
# O smoke responde "esta release serve?", e não "o portal inteiro está
# saudável?". A diferença importa: `/` depende da API, e sem feed real e sem
# cache a Home responde 503 DE PROPÓSITO (critério 11, nunca conteúdo MOCK).
# Julgar uma release quebrada por causa de um 503 correto seria trocar um
# problema real por um falso; por isso o 503 é aceito, logged e explicado.
smoke() {
    exigir "$DIR/server.js" "árvore standalone inválida (rode \`prepare\`/build antes)"
    exigir_comando curl curl "usado para o smoke"

    local porta_efetiva="$PORT"
    local codigo_rota codigo_robots codigo_asset asset_relativo

    # `SMOKE_PID` e `SMOKE_LOG` são GLOBAIS de propósito: o `trap ... EXIT`
    # dispara quando a função já saiu do escopo, e com `set -u` uma `local`
    # inacessível ali aborta o script com "unbound variable" — exatamente no
    # caminho de erro, que é quando o log do servidor morto precisa aparecer.
    SMOKE_LOG="$(mktemp)"
    SMOKE_PID=""

    cleanup() {
        if [[ -n "$SMOKE_PID" ]] && kill -0 "$SMOKE_PID" 2>/dev/null; then
            kill -TERM "$SMOKE_PID" 2>/dev/null || true
            for _ in $(seq 1 20); do
                kill -0 "$SMOKE_PID" 2>/dev/null || break
                sleep 0.5
            done
            kill -KILL "$SMOKE_PID" 2>/dev/null || true
        fi
        [[ -n "$SMOKE_LOG" ]] && rm -f -- "$SMOKE_LOG"
        return 0
    }
    trap cleanup EXIT

    # Porta livre: smoke em porta fixa colide com o processo em produção e o
    # "sucesso" passa a ser o do processo velho, que é a release anterior.
    if command -v python3 >/dev/null 2>&1; then
        porta_efetiva="$(python3 - <<'PY'
import socket
s = socket.socket()
s.bind(("127.0.0.1", 0))
print(s.getsockname()[1])
s.close()
PY
)"
    fi

    log "subindo o servidor em 127.0.0.1:$porta_efetiva (timeout ${TIMEOUT_SEGUNDOS}s)"
    (
        cd -- "$DIR"
        PORT="$porta_efetiva" HOSTNAME=127.0.0.1 NODE_ENV=production \
            NEXT_TELEMETRY_DISABLED=1 exec node server.js
    ) >"$SMOKE_LOG" 2>&1 &
    SMOKE_PID=$!

    local deadline=$(( $(date +%s) + TIMEOUT_SEGUNDOS ))
    local pronto=0
    while [[ $(date +%s) -lt $deadline ]]; do
        if ! kill -0 "$SMOKE_PID" 2>/dev/null; then
            erro "o processo do standalone morreu durante o smoke; log:"
            sed 's|^|    |' "$SMOKE_LOG" >&2
            exit "$FALHA_SMOKE"
        fi
        if curl -fsS -o /dev/null "http://127.0.0.1:$porta_efetiva/" 2>/dev/null; then
            pronto=1
            break
        fi
        if curl -sS -o /dev/null --max-time 2 "http://127.0.0.1:$porta_efetiva/" 2>/dev/null; then
            pronto=1
            break
        fi
        sleep 1
    done
    if [[ "$pronto" != "1" ]]; then
        erro "o servidor não respondeu em ${TIMEOUT_SEGUNDOS}s; log:"
        sed 's|^|    |' "$SMOKE_LOG" >&2
        exit "$FALHA_SMOKE"
    fi

    # 1) rota gerada no app (independe da API): prova que o roteamento do
    #    standalone está de pé.
    codigo_robots="$(curl -sS -o /dev/null -w '%{http_code}' "http://127.0.0.1:$porta_efetiva/robots.txt" || echo 000)"
    log "GET /robots.txt -> $codigo_robots"
    if [[ "$codigo_robots" == "000" ]]; then
        erro "sem resposta HTTP em /robots.txt; a release não está servindo"
        exit "$FALHA_SMOKE"
    fi

    # 2) um asset real de .next/static: é o teste que pega o erro clássico de
    #    standalone (`.next/static` não copiado) — a página responde 200 e
    #    aparece sem estilo nenhum.
    asset_relativo="$(
        cd -- "$DIR/.next/static" 2>/dev/null || exit 0
        find . -type f -name '*.js' -printf '%P\n' 2>/dev/null | sort | head -1
    )"
    if [[ -n "$asset_relativo" ]]; then
        codigo_asset="$(curl -sS -o /dev/null -w '%{http_code}' "http://127.0.0.1:$porta_efetiva/_next/static/$asset_relativo" || echo 000)"
        log "GET /_next/static/$asset_relativo -> $codigo_asset"
        if [[ "$codigo_asset" != "200" ]]; then
            erro "asset estático não servido (esperado 200, veio $codigo_asset): a árvore standalone está incompleta"
            exit "$FALHA_SMOKE"
        fi
    else
        erro "nenhum .js em $DIR/.next/static; o prepare não rodou ou o build não gerou assets"
        exit "$FALHA_SMOKE"
    fi

    # 3) a Home: 2xx/3xx é o alvo; 503 é a resposta DOCUMENTADA para feed
    #    indisponível sem cache e não reprova a release; 5xx/outros reprovam.
    codigo_rota="$(curl -sS -o /dev/null -w '%{http_code}' --max-time 30 "http://127.0.0.1:$porta_efetiva/" || echo 000)"
    log "GET / -> $codigo_rota"
    case "$codigo_rota" in
        2*|3*|503)
            if [[ "$codigo_rota" == "503" ]]; then
                log "AVISO: 503 em / é o estado documentado de feed indisponível sem cache (critério 11); a release está íntegra, a dependência não"
            fi
            ;;
        *)
            erro "Home respondeu $codigo_rota; a release não deve ser promovida"
            sed 's|^|    |' "$SMOKE_LOG" >&2
            exit "$FALHA_SMOKE"
            ;;
    esac

    log "smoke aprovado: a release serve /robots.txt, assets de .next/static e a Home ($codigo_rota)"
}

# ------------------------------------------------------------------ start ---
# Executa no foreground para o supervisor. Hoje o supervisor é o PM2
# (`web_runtime: standalone` em deploy.yml). `exec` é obrigatório: sem ele o PID
# do shell é o do processo e restart/shutdown chegam ao shell, não ao Next.
iniciar() {
    exigir "$DIR/server.js" "árvore standalone inválida"
    exigir_comando node node "runtime do Next standalone (Node >= 20)"
    log "iniciando standalone em $BIND_HOST:$PORT a partir de $DIR"
    cd -- "$DIR"
    # HOSTNAME é o que o Next usa para o bind: sem ele o servidor escuta no
    # hostname do host, que nem sempre é o que o Nginx faz proxy.
    export PORT HOSTNAME="$BIND_HOST" NODE_ENV=production NEXT_TELEMETRY_DISABLED="${NEXT_TELEMETRY_DISABLED:-1}"
    exec node server.js
}

case "$COMANDO" in
    prepare) preparar ;;
    smoke) smoke ;;
    start) iniciar ;;
esac

# ---------------------------------------------------------------------------
# ESTE É O RUNTIME DO PORTAL EM PRODUÇÃO (C2.2)
# ---------------------------------------------------------------------------
# O PM2 executa este script desde C2.2 (run 20260925-1020-observabilidade), via
# `web_runtime: standalone` em `.github/workflows/deploy.yml`:
#
#   infra/standalone/run-standalone.sh prepare --dir releases/<id>/standalone
#   infra/standalone/run-standalone.sh smoke  --dir releases/<id>/standalone
#   infra/standalone/run-standalone.sh start   --dir releases/current/standalone
#
# A nota anterior deste arquivo dizia "o PM2 ainda NÃO usa isto", o que
# deixou de ser verdade quando o deploy ganhou a release atômica. O motivo
# original continua válido e é a razão de a troca ter sido adiada: usar esta
# árvore sem estratégia de release seria PIOR que o `npm start` antigo, porque
# `next build` reescreve `.next/` no lugar e o processo em produção lê essa
# mesma árvore. Por isso a ordem é invariante: preparar → fumegar a release →
# só então trocar o symlink `releases/current` e reiniciar.
#
# O QUE CONTINUA SENDO VERDADE (e não deve ser "simplificado"):
#   * `start` NÃO faz promote. Promover é ato do deploy, e só depois do smoke
#     verde. Se alguém chamar `start` apontando para uma release não validada,
#     estará servindo código que ninguém checou.
#   * `smoke` NÃO reinicia nada e NÃO toca em `current`/`previous`. Ele sobe o
#     servidor numa porta livre, valida e derruba. Um smoke que promovesse
#     alguma coisa seria um smoke que pode derrubar a produção.
#   * O bind e o `PORT` vêm do ambiente/flags, nunca de valor fixo aqui. O
#     deploy passa `--host`/`--port` explícitos porque o `HOSTNAME` ausente faz
#     o Next escutar no hostname do host, que não é o que o Nginx faz proxy.
#
# SE ALGUÉM VOLTAR AO `npm start` (caminho de escape, ainda disponível):
#   é o input `web_runtime: npm` no workflow reutilizável, exposto também no
#   dispatch de `rollback.yml`. Ele faz build in-place e sobe `npm start` sem
#   tocar em `releases/`. Voltar ao `npm start` reintroduz o problema original —
#   `.next/` reescrito embaixo do processo em produção — e por isso exige
#   decisão registrada em `CI-CD.md` §P1-6, não uma edição de workflow. NUNCA
#   remova este caminho de escape sem antes de um deploy `standalone` validado
#   num ambiente real com probes verdes.
