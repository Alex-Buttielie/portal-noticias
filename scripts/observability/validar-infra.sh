#!/usr/bin/env bash
# Validação de configuração de infra do portal (run 20260925-1020-observabilidade,
# critério 40).
#
# POR QUE ESTE SCRIPT EXISTE
#   Configuração de Nginx, systemd, Compose, JSON e HCL só quebra quando alguém
#   a instala — e a instalação acontece na VPS, em produção, no meio de um
#   deploy. Este script roda a MESMA verificação localmente, antes disso, e é o
#   mesmo código que o gate de CI executa (job `infra-validate` de ci.yml, com
#   `--estrito`, desde C2.5).
#
#   A regra de ouro deste script: ele RELATA o que não conseguiu validar. Item
#   pulado por falta de binário sai como "PULADO", nunca como "OK" — um
#   validador que mente é pior que nenhum validador.
#
# Uso:
#   scripts/observability/validar-infra.sh              # tudo que for possível
#   scripts/observability/validar-infra.sh --rapido    # pula o que usa container
#   scripts/observability/validar-infra.sh --somente nginx,systemd
#   scripts/observability/validar-infra.sh --estrito   # pendências viram falha (use no CI)
#
# Saída: exit 0 se nada FALHOU (pulados são aceitáveis e listados no resumo);
# exit 1 se qualquer verificação falhou.
#
# PENDÊNCIA DECLARADA (`--estrito`, C2.5): uma pendência real listada em
# `scripts/observability/pendencias-ci.txt` NÃO reprova o gate estrito — ela é
# impressa como [PENDENTE], listada no resumo e reprova qualquer pendência que
# NÃO esteja na lista. A diferença é deliberada: sem a lista, `--estrito`
# puniria para sempre o CI por algo que só se resolve com acesso ao serviço
# externo (domínio de runbook, conta, DNS), e um gate vermelho permanente
# acaba sendo ignorado — que é pior do que a pendência. Com a lista, uma
# pendência NOVA reprova na hora e a conhecida continua visível. E uma chave
# declarada que não ocorre mais também falha: sem isso a lista envelheceria em
# silêncio e passaria a esconder pendência nova.
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$REPO_DIR" || exit 1

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

# Contadores e flags são inicializados ANTES do parsing: declarar depois faria
# `--estrito` ser sobrescrito por `ESTRITO=0` e o "estrito" seria fiction — o
# tipo de bug que só aparece quando você mais precisa da checagem.
FALHAS=0
PULADOS=0
OKS=0
AVISOS=0
ESTRITO=0
RAPIDO=0
FILTRO=""
PENDENTES_RECONHECIDOS=0

while [[ $# -gt 0 ]]; do
    case "$1" in
        --rapido) RAPIDO=1; shift ;;
        --estrito) ESTRITO=1; shift ;;
        --somente) FILTRO="${2:-}"; shift 2 ;;
        -h|--help)
            # O bloco de ajuda é o cabeçalho de comentário: recortado pelo
            # início do código para não depender de contagem de linhas (que
            # quebraria sozinho na próxima edição do cabeçalho).
            sed -n '2,/^set -/p' "$0" | sed 's/^# \{0,1\}//' | sed '$d'
            exit 0
            ;;
        *) printf 'opção desconhecida: %s\n' "$1" >&2; exit 64
    esac
done

declare -a RESUMO=()
declare -a RESUMO_FALHAS=()
declare -a RESUMO_PENDENCIAS=()
declare -a PENDENCIAS_VISTAS=()

# Arquivo de pendências declaradas (C2.5). Ver o cabeçalho.
PENDENCIAS_FILE="scripts/observability/pendencias-ci.txt"

titulo() { printf '\n\033[1m== %s ==\033[0m\n' "$*"; }
ok()      { OKS=$((OKS+1));       printf '  [OK]     %s\n' "$*"; }
pulado()  { PULADOS=$((PULADOS+1)); printf '  [PULADO] %s\n' "$*"; RESUMO+=("PULADO: $*"); }
aviso()   { AVISOS=$((AVISOS+1)); printf '  [AVISO]  %s\n' "$*"; RESUMO+=("AVISO: $*"); }
falha()   { FALHAS=$((FALHAS+1)); printf '  [FALHOU] %s\n' "$*"; RESUMO_FALHAS+=("$*"); }

# Verdadeiro quando a chave está declarada no arquivo de pendências. O
# casamento é por PREFIXO de linha, então a linha pode trazer o motivo depois
# da chave; `index` evita qualquer interpretação de metacaractere da chave.
chave_declarada() {
    local chave="$1"
    [[ -r "$PENDENCIAS_FILE" ]] || return 1
    awk -v k="$chave" '
        {
            linha = $0
            sub(/#.*/, "", linha)
            gsub(/^[ \t]+|[ \t]+$/, "", linha)
            if (index(linha, k) == 1) {
                resto = substr(linha, length(k) + 1)
                if (resto == "" || resto ~ /^[ \t]/) achou = 1
            }
        }
        END { exit(achou ? 0 : 1) }
    ' "$PENDENCIAS_FILE"
}

# Item que é erro no CI e apenas aviso no uso local (configuração que depende
# de provisionamento externo ainda por vir). `--estrito` transforma em falha,
# SALVO quando a pendência está declarada em `pendencias-ci.txt` (aí ela
# continua impressa e listada no resumo, mas não reprova o gate).
pendencia() {
    local chave="$1"
    shift
    PENDENCIAS_VISTAS+=("$chave")
    if chave_declarada "$chave"; then
        PENDENTES_RECONHECIDOS=$((PENDENTES_RECONHECIDOS+1))
        printf '  [PENDENTE] %s\n' "$*"
        printf '             declarada em %s (chave: %s)\n' "$PENDENCIAS_FILE" "$chave"
        RESUMO_PENDENCIAS+=("$chave — $*")
        return 0
    fi
    if (( ESTRITO )); then falha "$*"; else aviso "$*"; fi
}

interessa() {
    [[ -z "$FILTRO" ]] && return 0
    [[ ",$FILTRO," == *",$1,"* ]]
}

# ---------------------------------------------------------------------------
# Scripts: sintaxe de shell
# ---------------------------------------------------------------------------
if interessa shell; then
titulo "Sintaxe dos scripts (bash -n)"
mapfile -t SCRIPTS < <(find infra/backup infra/standalone infra/observability scripts/observability -type f -name '*.sh' 2>/dev/null | sort)
for s in "${SCRIPTS[@]}"; do
    if out="$(bash -n "$s" 2>&1)"; then
        ok "$s"
    else
        falha "$s — $out"
    fi
done

# Permissão de execução: um script de cron sem `+x` falha em silêncio no crontab
# (que ignora a linha com "command not found" e segue para a próxima).
for s in infra/backup/pg_backup_pm2.sh infra/backup/verificar_backup.sh \
         infra/standalone/run-standalone.sh infra/observability/alloy/verificar-env.sh; do
    if [[ -x "$s" ]]; then ok "executável: $s"; else falha "sem permissão de execução: $s"; fi
done

# `shellcheck` quando existir: análise estática real, mas não obrigatória.
if command -v shellcheck >/dev/null 2>&1; then
    if out="$(shellcheck -S warning "${SCRIPTS[@]}" 2>&1)"; then
        ok "shellcheck (${SCRIPTS[@]##*/} sem warning)"
    else
        printf '%s\n' "$out" | sed 's/^/          /'
        falha "shellcheck reportou problemas"
    fi
else
    pulado "shellcheck não instalado (análise estática de shell não executada)"
fi
fi

# ---------------------------------------------------------------------------
# JSON: dashboards, checks externos, lifecycle do bucket
# ---------------------------------------------------------------------------
if interessa json; then
titulo "JSON (dashboards, checks externos, lifecycle)"
if command -v jq >/dev/null 2>&1; then
    while IFS= read -r j; do
        if out="$(jq -e . "$j" 2>&1 >/dev/null)"; then ok "$j"; else falha "$j — $out"; fi
    done < <(find infra/observability -type f -name '*.json' | sort)

    # Forma mínima de um dashboard importável pelo Grafana. Um JSON sintaticamente
    # válido que o Grafana recusa na importação é o modo de falha clássico.
    for d in infra/observability/grafana/dashboards/*.json; do
        problemas=""
        jq -e 'has("title") and has("uid") and has("panels") and (.panels|length>0)' "$d" >/dev/null 2>&1 \
            || problemas="$problemas falta title/uid/panels;"
        jq -e 'has("__inputs")' "$d" >/dev/null 2>&1 \
            || problemas="$problemas falta __inputs (datasource);"
        jq -e '[.panels[] | select(.type != "text") | .targets[0].expr] | all(test("^[a-zA-Z_:]"))' "$d" >/dev/null 2>&1 \
            || problemas="$problemas painel com expr ausente ou nao-PromQL;"
        if [[ -z "$problemas" ]]; then ok "dashboard importável: $d"; else falha "$d —$problemas"; fi
    done

    # As queries reais dos painéis e das regras — e SÓ elas. Texto livre
    # (descrição de painel, anotação de alerta) pode e DEVE citar uma métrica
    # para explicar por que ela não é usada; o que não pode é uma `expr`.
    mapfile -t QUERIES < <(
        { jq -r '.panels[]? | select(.targets) | .targets[]?.expr // empty' \
              infra/observability/grafana/dashboards/*.json 2>/dev/null
          python3 - <<'PYEOF_YAML' 2>/dev/null
import glob, yaml
for arquivo in sorted(glob.glob("infra/observability/alerts/*.yaml")):
    doc = yaml.safe_load(open(arquivo, encoding="utf-8")) or {}
    for grupo in doc.get("groups") or []:
        for regra in grupo.get("rules") or []:
            expr = regra.get("expr")
            if expr:
                print(expr)
PYEOF_YAML
        } | grep -v '^$'
    )
    ok "${#QUERIES[@]} queries de painel/alerta extraídas"

    # Arquivo com as queries, para os dois testes de Prometheus em Python.
    # POR QUE UM ARQUIVO: `printf ... | python3 - <<'EOF'` NÃO funciona — o
    # heredoc redefine o stdin do `python3 -` (que é o próprio programa), e o
    # `sys.stdin.read()` voltava VAZIO. O teste de métrica inexistente já
    # passava por isso desde que foi escrito: ele comparava um conjunto de nomes
    # com um inventário e não encontrava nome nenhum para acusar. Um validador
    # que não olha nada é pior que nenhum validador (é o que o cabeçalho deste
    # script diz), então as duas checagens leem o arquivo.
    printf '%s\n' "${QUERIES[@]:-}" > "$TMP/queries.txt"

    # A REGRA que protege o critério "não prometa painel de métrica inexistente":
    # `portal_ingestion_executions_total` é DECLARADA em backend/config/metrics.py
    # e nunca incrementada, então usá-la num painel/alerta vira promessa vazia.
    if grep -q "portal_ingestion_executions_total" "$TMP/queries.txt"; then
        falha "portal_ingestion_executions_total usada em expr de painel/alerta (métrica declarada e nunca incrementada)"
    else
        ok "nenhuma expr usa portal_ingestion_executions_total"
    fi

    # Gauge ABSOLUTO produzido por OUTRO processo (`config/job_state.py`: o
    # worker grava, o processo web publica) nunca pode entrar em `sum()`: o
    # valor é uma idade em segundos, e somar por instância multiplica o mesmo
    # relógio pelo número de coletores — o alerta passa a medir o tamanho da
    # topologia em vez do atraso. A regra correta é `max()`/`last()` (e nunca
    # `rate()`), como os docstrings de `job_state.py`/`metrics.py` prescrevem.
    # Cada `expr` é conferida SEPARADAMENTE (regra a regra, painel a painel): o
    # texto agregado de todas as queries junto produziria acusação cruzada entre
    # uma query com `sum()` e outra que só cita `portal_job_*` no nome do
    # painel — que foi exatamente o falso positivo da primeira versão.
    PY_SUM="$(command -v python3 || true)"
    if [[ -z "$PY_SUM" ]]; then
        pulado "python3 não instalado: checagem de sum() em gauge de job NÃO executada"
    else
        soma_gauge_job="$("$PY_SUM" - <<'PYEOF_SUM'
import glob, json, re, sys
try:
    import yaml
except ImportError:
    sys.exit(3)
padrao = re.compile(r"(^|[^a-z_])sum\s*\(")
acusos = []
for arquivo in sorted(glob.glob("infra/observability/alerts/*.yaml")):
    doc = yaml.safe_load(open(arquivo, encoding="utf-8")) or {}
    for grupo in doc.get("groups") or []:
        for regra in grupo.get("rules") or []:
            expr = str(regra.get("expr") or "")
            if "portal_job_" in expr and padrao.search(expr):
                acusos.append(f"{regra.get('alert')} ({arquivo})")
for arquivo in sorted(glob.glob("infra/observability/grafana/dashboards/*.json")):
    doc = json.load(open(arquivo, encoding="utf-8"))
    for painel in doc.get("panels") or []:
        for alvo in painel.get("targets") or []:
            expr = str(alvo.get("expr") or "")
            if "portal_job_" in expr and padrao.search(expr):
                acusos.append(f"painel {painel.get('title')} ({arquivo})")
print(" | ".join(acusos))
PYEOF_SUM
)"
        rc_sum=$?
        if [[ $rc_sum -eq 3 ]]; then
            falha "checagem de sum() em gauge de job NÃO EXECUTADA (PyYAML não instalado no ambiente de validação)"
        elif [[ -n "$soma_gauge_job" ]]; then
            falha "sum() sobre portal_job_* (gauge absoluto de outro processo: use max()/last()): $soma_gauge_job"
        else
            ok "nenhuma expr de painel/alerta soma portal_job_* (max()/last() em toda expr de job)"
        fi
    fi

    # Toda métrica usada tem que existir de fato no backend. O inventário vem
    # dos TRÊS lugares onde nome de métrica aparece: `config/metrics.py` (as
    # declaradas e as registradas), `config/observability_views.py` (contadores
    # de probe/acesso) e `config/health.py` (gauge de fila e de disco).
    mapfile -t METRICAS_BACKEND < <(
        grep -ho '"portal_[a-z_]*"' backend/config/metrics.py \
            backend/config/observability_views.py backend/config/health.py \
        | tr -d '"' | sort -u
    )
    # `_bucket`/`_sum`/`_count` são séries derivadas de um histograma (o backend
    # emite as três a partir de uma observação), então basta a base existir. A
    # comparação é feita em Python: `${m%$sufixo}` depende de detalhe de
    # parsing do shell que já enganou esta checagem uma vez.
    ausentes="$(python3 - "$TMP/queries.txt" "${METRICAS_BACKEND[@]}" <<'PYEOF_METRICAS'
import re, sys
inventario = set(sys.argv[2:])
consulta = open(sys.argv[1], encoding="utf-8").read()
faltando = []
for nome in sorted(set(re.findall(r"portal_[a-z_]*", consulta))):
    base = nome
    for sufixo in ("_bucket", "_sum", "_count"):
        if base.endswith(sufixo):
            base = base[: -len(sufixo)]
            break
    if base not in inventario:
        faltando.append(nome)
print(", ".join(faltando))
PYEOF_METRICAS
)"
    if [[ -n "$ausentes" ]]; then
        falha "métrica(s) usada(s) em painel/alerta e ausente(s) do backend (metrics.py/observability_views.py/health.py): $ausentes"
    else
        ok "métricas usadas em painel/alerta conferidas contra o inventário do backend"
    fi
else
    pulado "jq não instalado: validação de JSON não executada"
fi
fi

# ---------------------------------------------------------------------------
# Regras de alerta: YAML + placeholders
# ---------------------------------------------------------------------------
if interessa alertas; then
titulo "Regras de alerta (YAML)"
PY="$(command -v python3 || true)"
if [[ -n "$PY" ]]; then
    for y in infra/observability/alerts/*.yaml; do
        if "$PY" - "$y" <<'PYEOF'
import re, sys
try:
    import yaml
except ImportError:
    print("SEM_PYYAML"); sys.exit(3)
doc = yaml.safe_load(open(sys.argv[1], encoding="utf-8"))
erros = []
grupos = doc.get("groups") or []
if not grupos:
    erros.append("sem groups")
vistas = set()
for g in grupos:
    for r in g.get("rules", []):
        nome = r.get("alert")
        if not nome:
            erros.append("regra sem nome")
            continue
        if nome in vistas:
            erros.append(f"nome duplicado: {nome}")
        vistas.add(nome)
        if "expr" not in r:
            erros.append(f"{nome} sem expr")
        an = r.get("annotations") or {}
        lb = r.get("labels") or {}
        for campo, valor in (("severity", lb.get("severity")), ("runbook_url", an.get("runbook_url"))):
            if not valor:
                erros.append(f"{nome} sem {campo}")
        if not an.get("description"):
            erros.append(f"{nome} sem description")
if erros:
    print("ERROS: " + "; ".join(erros)); sys.exit(1)
print(f"OK: {len(vistas)} regras, todas com severity, runbook_url e description")
PYEOF
        then
            ok "$y"
        else
            case $? in
                3) falha "$y — PyYAML não instalado (adicione pyyaml ao ambiente de validação)" ;;
                *) falha "$y — $( "$PY" -c 'import sys' 2>/dev/null; echo "ver saída acima" )" ;;
            esac
        fi
    done
    if grep -q "exemplo.invalid" infra/observability/alerts/*.yaml; then
        pendencia runbook-url-placeholder "runbook_url ainda com o placeholder exemplo.invalid (RFC 2606, nunca resolve): trocar pelo endereço interno ANTES de carregar as regras no Mimir"
    else
        ok "nenhum runbook_url de placeholder"
    fi
else
    pulado "python3 não instalado: regras de alerta não validadas"
fi
fi

# ---------------------------------------------------------------------------
# Nginx
# ---------------------------------------------------------------------------
if interessa nginx; then
titulo "Nginx"
# 1) Os três site confs precisam ser estruturalmente idênticos (fora o
#    cabeçalho e os tokens de ambiente). Drift entre eles é um risco real: hoje
#    os três arquivos são quase cópia, e uma correção em um só vira falha que só
#    aparece em dois dos três ambientes.
NORMALIZA='s/portal_api_\(dev\|homolog\|prod\)/portal_api_AMB/g; s/127\.0\.0\.1:510[123]/127.0.0.1:51XX/g; s/127\.0\.0\.1:310[123]/127.0.0.1:31XX/g; s/portal-\(dev\|homolog\|prod\)/portal-AMB/g; s/ __DOMAIN_FRONTEND_WWW__//g'
for e in dev homolog prod; do
    sed -n '/^upstream /,$p' "infra/nginx/portal-$e.conf" | sed -e "$NORMALIZA" > "$TMP/$e.norm"
done
if diff -q "$TMP/dev.norm" "$TMP/homolog.norm" >/dev/null \
   && diff -q "$TMP/dev.norm" "$TMP/prod.norm" >/dev/null; then
    ok "os três site confs são estruturalmente idênticos (do upstream ao fim)"
else
    falha "os site confs divergem entre si; veia o diff:"
    diff -u "$TMP/dev.norm" "$TMP/homolog.norm" | head -20 | sed 's/^/          /'
    diff -u "$TMP/dev.norm" "$TMP/prod.norm" | head -20 | sed 's/^/          /'
fi

# 2) Nenhum `proxy_set_header X-Request-ID $request_id` pode sobrar: sobrescrever
#    o ID do cliente quebra a correlação browser -> nginx -> Django (achado B2).
if grep -n 'X-Request-ID \$request_id' infra/nginx/portal-*.conf >/dev/null 2>&1; then
    falha "sobrou proxy_set_header X-Request-ID \$request_id (sobrescreve o ID do cliente)"
    grep -n 'X-Request-ID \$request_id' infra/nginx/portal-*.conf | sed 's/^/          /'
else
    ok "todo X-Request-ID propagado usa \$portal_request_id (ID do cliente quando válido)"
fi

# 3) Marcador do token: presente no http-cache.conf (é o template) e ausente de
#    qualquer conf JÁ instalado seria o oposto do desejado.
if grep -q '__OBS_TOKEN_ESPERADO__' infra/nginx/http-cache.conf; then
    ok "http-cache.conf tem o marcador __OBS_TOKEN_ESPERADO__ (substituir ao instalar)"
else
    falha "http-cache.conf perdeu o marcador __OBS_TOKEN_ESPERADO__ (revisar o gate privado)"
fi

# 4) `X-Forwarded-For` tem que ser ESCRITO em TODO upstream que fala com o
#    Django (D2). O leitor (`backend/config/proxies.py::identificar_cliente`)
#    só considera o header quando quem abriu a conexão é o loopback ou uma rede
#    declarada, e só usa o ÚLTIMO elemento da cadeia. Sem a diretiva, o header
#    não existe e o balde de rate limit volta a ser o par do proxy (ou, pior, o
#    valor cru que o cliente mandou): foi o achado MAJOR-1 da revisão de backend,
#    que a configuração de infra não fechava.
#
#    Valores aceitos: `$proxy_add_x_forwarded_for` (anexa o `$remote_addr` ao
#    fim) e `$remote_addr` (sobrescreve) — os dois garantem que o último
#    elemento é o cliente real deste salto, que é a invariante que o módulo do
#    backend documenta. `$http_x_forwarded_for` é PROIBIDO: repassa o header do
#    cliente sem tocá-lo e reabriria o bypass.
xff_ruim=0
for e in dev homolog prod; do
    f="infra/nginx/portal-$e.conf"
    passes="$(grep -c 'proxy_pass ' "$f")"
    # Uma diretiva por `proxy_pass`: nenhum destes arquivos usa
    # `proxy_set_header` no nível do `server` (tudo é por location), então a
    # contagem 1:1 é o que impede um location novo sem a diretiva.
    xffs="$(grep -c 'proxy_set_header X-Forwarded-For ' "$f")"
    if [[ "$passes" -ne "$xffs" ]]; then
        falha "$f: $passes proxy_pass e $xffs X-Forwarded-For (todo upstream precisa da diretiva)"
        xff_ruim=1
    fi
    if grep -nE 'X-Forwarded-For[[:space:]]+\$http_x_forwarded_for' "$f" >/dev/null 2>&1; then
        falha "$f: X-Forwarded-For repassando \$http_x_forwarded_for (header do cliente)"
        grep -nE 'X-Forwarded-For[[:space:]]+\$http_x_forwarded_for' "$f" | sed 's/^/          /'
        xff_ruim=1
    fi
    if grep -qE 'X-Forwarded-For[[:space:]]+\$(proxy_add_x_forwarded_for|remote_addr)[[:space:]]*;' "$f"; then
        ok "$e: X-Forwarded-For escrito nos $passes upstream(s) (valor aceito)"
    else
        falha "$f: nenhum X-Forwarded-For com valor aceito"
        xff_ruim=1
    fi
done
if (( ! xff_ruim )); then
    ok "X-Forwarded-For presente nos três ambientes com valor aceito"
fi

# 5) Validação real com o binário do nginx.
#    `nginx -t` no host: os marcadores de domínio impedem instalar o conf como
#    está, então renderizamos uma cópia com valores de teste e validamos essa.
validar_nginx_host() {
    command -v nginx >/dev/null 2>&1 || return 127
    local d="$TMP/nginx"
    mkdir -p "$d/conf.d"
    command -v openssl >/dev/null 2>&1 \
        && openssl req -x509 -newkey rsa:2048 -nodes -days 1 -subj "/CN=portal.invalid" \
            -keyout "$d/privkey.pem" -out "$d/fullchain.pem" 2>/dev/null
    local e
    for e in dev homolog prod; do
        sed -e "s|__DOMAIN_FRONTEND__|portal-$e.invalid|g" \
            -e "s|__DOMAIN_FRONTEND_WWW__||g" \
            -e "s|/etc/letsencrypt/live/portal-$e.invalid/privkey.pem|$d/privkey.pem|g" \
            -e "s|/etc/letsencrypt/live/portal-$e.invalid/fullchain.pem|$d/fullchain.pem|g" \
            "infra/nginx/portal-$e.conf" > "$d/conf.d/portal-$e.conf"
    done
    cat > "$d/nginx.conf" <<EOF
worker_processes 1;
error_log stderr;
pid /tmp/nginx-valida.pid;
events { worker_connections 64; }
http {
    include $REPO_DIR/infra/nginx/http-cache.conf;
    include $d/conf.d/*.conf;
}
EOF
    nginx -t -c "$d/nginx.conf" 2>&1
}
if (( RAPIDO )); then
    pulado "nginx -t pulado por --rapido"
elif command -v nginx >/dev/null 2>&1; then
    if out="$(validar_nginx_host)"; then ok "nginx -t (binário local)"; else falha "nginx -t: $out"; fi
elif command -v docker >/dev/null 2>&1; then
    if docker info >/dev/null 2>&1; then
        D="$TMP/nginx"; mkdir -p "$D/conf.d"
        openssl req -x509 -newkey rsa:2048 -nodes -days 1 -subj "/CN=portal.invalid" \
            -keyout "$D/privkey.pem" -out "$D/fullchain.pem" 2>/dev/null
        for e in dev homolog prod; do
            sed -e "s|__DOMAIN_FRONTEND__|portal-$e.invalid|g" \
                -e "s|__DOMAIN_FRONTEND_WWW__||g" \
                -e "s|/etc/letsencrypt/live/portal-$e.invalid/privkey.pem|/etc/nginx/privkey.pem|g" \
                -e "s|/etc/letsencrypt/live/portal-$e.invalid/fullchain.pem|/etc/nginx/fullchain.pem|g" \
                "infra/nginx/portal-$e.conf" > "$D/conf.d/portal-$e.conf"
        done
        printf 'worker_processes 1;\nerror_log stderr;\npid /tmp/nginx-valida.pid;\nevents { worker_connections 64; }\nhttp {\n    include /etc/nginx/http-cache.conf;\n    include /etc/nginx/conf.d/*.conf;\n}\n' > "$D/nginx.conf"
        C_ID="$(docker create nginx:alpine nginx -t 2>/dev/null)"
        if [[ -z "$C_ID" ]]; then
            falha "não foi possível criar o container de validação do Nginx"
        else
            # `docker cp` em vez de bind mount: em Docker Desktop só caminhos
            # compartilhados podem ser montados e o /tmp quase nunca é um deles,
            # o que faria a validação falhar por motivo sem relação com a config.
            docker cp "$D/nginx.conf" "$C_ID:/etc/nginx/nginx.conf" >/dev/null 2>&1
            docker cp "$REPO_DIR/infra/nginx/http-cache.conf" "$C_ID:/etc/nginx/http-cache.conf" >/dev/null 2>&1
            docker cp "$D/conf.d" "$C_ID:/etc/nginx/conf.d" >/dev/null 2>&1
            docker cp "$D/privkey.pem" "$C_ID:/etc/nginx/privkey.pem" >/dev/null 2>&1
            docker cp "$D/fullchain.pem" "$C_ID:/etc/nginx/fullchain.pem" >/dev/null 2>&1
            if out="$(docker start -a "$C_ID" 2>&1)"; then
                ok "nginx -t (binário oficial, em container, imagem oficial do Nginx)"
            else
                falha "nginx -t em container: $(printf '%s' "$out" | tail -4)"
            fi
            docker rm -f "$C_ID" >/dev/null 2>&1
        fi
    else
        pulado "daemon do Docker indisponível: nginx -t não executado"
    fi
else
    pulado "sem nginx local e sem Docker: nginx -t NÃO executado"
fi
fi

# ---------------------------------------------------------------------------
# systemd
# ---------------------------------------------------------------------------
if interessa systemd; then
titulo "systemd (systemd-analyze verify)"
if command -v systemd-analyze >/dev/null 2>&1; then
    for u in infra/systemd/*.service infra/systemd/*.timer; do
        [[ -e "$u" ]] || continue
        out="$(systemd-analyze verify "$u" 2>&1)"
        rc=$?
        # Ruído esperado fora da VPS: o app não existe neste host, então o
        # executável do Celery não existe. Isso NÃO é erro de configuração.
        filtrado="$(printf '%s\n' "$out" | grep -v 'is not executable: No such file or directory' | grep -v 'not found$')"
        if [[ -z "$filtrado" ]]; then
            ok "$u${filtrado:+ (aviso esperado: app ausente neste host)}"
        else
            printf '%s\n' "$filtrado" | sed 's/^/          /'
            falha "$u"
        fi
    done
    # Hardening mínimo que o plano exige.
    for u in infra/systemd/celery-worker@.service infra/systemd/celery-beat@.service; do
        for chave in NoNewPrivileges ProtectSystem Restart=on-failure MemoryMax; do
            if grep -q "^$chave" "$u"; then ok "$u tem $chave"; else falha "$u sem $chave"; fi
        done
    done
else
    pulado "systemd-analyze não instalado: units não verificadas"
fi
fi

# ---------------------------------------------------------------------------
# Docker Compose
# ---------------------------------------------------------------------------
if interessa compose; then
titulo "Docker Compose (docker compose config)"
if (( RAPIDO )); then
    pulado "docker compose config pulado por --rapido"
elif command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then
    # Env de VALIDAÇÃO com placeholders obviously-falsos, num diretório
    # temporário: nunca criamos `.env.production` real, e nenhuma credencial
    # entra no repositório.
    cat > "$TMP/env.validacao" <<'EOF'
NEXT_PUBLIC_API_BASE_URL=https://exemplo.invalid
NEXT_PUBLIC_SITE_URL=https://exemplo.invalid
DJANGO_DB_PASSWORD=placeholder-de-validacao-nao-e-segredo
EOF
    if out="$(docker compose --env-file "$TMP/env.validacao" config -q 2>&1)"; then
        ok "docker compose config (compose principal)"
    else
        falha "docker compose config: $out"
    fi
    # Healthcheck "sempre verde" (achado B11): o defeito é o `|| exit 0` no
    # TESTE, não em comentário. A checagem roda sobre o config JÁ RESOLVIDO
    # pelo Compose, senão um comentário explicando o defeito seria acusado
    # como defeito.
    docker compose --env-file "$TMP/env.validacao" config --format json > "$TMP/compose.json" 2>/dev/null
    sempre_verde="$(jq -r '
        .services
        | to_entries[]
        | select(.value.healthcheck != null)
        | "\(.key): \(.value.healthcheck.test | join(" "))"
    ' "$TMP/compose.json" 2>/dev/null | grep -n 'exit 0' || true)"
    if [[ -n "$sempre_verde" ]]; then
        falha "healthcheck do compose com 'exit 0' no teste (sempre verde): $sempre_verde"
    else
        ok "nenhum healthcheck do compose tem 'exit 0' no teste"
    fi
    # O script dentro do healthcheck tem que ser shell E python válidos.
    for s in celery-worker celery-beat; do
        docker compose --env-file "$TMP/env.validacao" config --format json 2>/dev/null \
            | jq -r ".services[\"$s\"].healthcheck.test[1]" > "$TMP/$s.cmd" 2>/dev/null
        [[ -s "$TMP/$s.cmd" ]] || { falha "não foi possível extrair o healthcheck de $s"; continue; }
        if sh -n "$TMP/$s.cmd" 2>/dev/null; then ok "healthcheck de $s: shell válido"; else falha "healthcheck de $s: shell inválido"; fi
        if python3 -c '
import ast, shlex, sys
p = shlex.split(open(sys.argv[1], encoding="utf-8").read().strip())
ast.parse(p[p.index("-c") + 1])
' "$TMP/$s.cmd" 2>/dev/null; then
            ok "healthcheck de $s: python válido"
        else
            falha "healthcheck de $s: python inválido"
        fi
    done
else
    pulado "Docker indisponível: docker compose config NÃO executado"
fi
fi

# ---------------------------------------------------------------------------
# Alloy
# ---------------------------------------------------------------------------
if interessa alloy; then
titulo "Grafana Alloy (config.alloy)"
ALLOY_CMD=""
for c in alloy; do command -v "$c" >/dev/null 2>&1 && ALLOY_CMD="$c"; done
if [[ -n "$ALLOY_CMD" ]]; then
    # `alloy validate` com env de PLACEHOLDER: o objetivo é validar a ESTRUTURA
    # do config (componentes, blocos e nomes de argumento), não os endpoints.
    cat > "$TMP/alloy.env" <<'EOF'
ALLOY_LOG_LEVEL=info
ALLOY_AMBIENTE=production
ALLOY_RELEASE=exemplo
ALLOY_BACKEND_METRICS_ADDR=127.0.0.1:5103
ALLOY_BACKEND_METRICS_TOKEN_FILE=/tmp/alloy-token-validacao
ALLOY_SELF_ADDR=127.0.0.1:12345
ALLOY_REMOTE_WRITE_URL=https://prometheus-exemplo.grafana.net/api/prom/push
ALLOY_REMOTE_WRITE_USER=0
ALLOY_REMOTE_WRITE_TOKEN=placeholder
ALLOY_LOKI_WRITE_URL=https://logs-exemplo.grafana.net/loki/api/v1/push
ALLOY_LOKI_USER=0
ALLOY_LOKI_TOKEN=placeholder
ALLOY_EDGE_LOG_GLOB=/var/log/nginx/portal-prod.access.log
ALLOY_PM2_LOG_GLOB=/home/apps/portal-prod/.pm2/logs/portal-api-prod-*.log
ALLOY_JOURNAL_UNITS="celery-worker@prod.service|celery-beat@prod.service"
EOF
    if out="$(env $(grep -v '^#' "$TMP/alloy.env" | xargs) "$ALLOY_CMD" validate infra/observability/alloy/config.alloy 2>&1)"; then
        ok "alloy validate (binário local)"
    else
        falha "alloy validate: $(printf '%s' "$out" | head -6)"
    fi
elif command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1 && (( ! RAPIDO )); then
    cat > "$TMP/alloy.env" <<'EOF'
ALLOY_LOG_LEVEL=info
ALLOY_AMBIENTE=production
ALLOY_RELEASE=exemplo
ALLOY_BACKEND_METRICS_ADDR=127.0.0.1:5103
ALLOY_BACKEND_METRICS_TOKEN_FILE=/tmp/alloy-token
ALLOY_SELF_ADDR=127.0.0.1:12345
ALLOY_REMOTE_WRITE_URL=https://prometheus-exemplo.grafana.net/api/prom/push
ALLOY_REMOTE_WRITE_USER=0
ALLOY_REMOTE_WRITE_TOKEN=placeholder
ALLOY_LOKI_WRITE_URL=https://logs-exemplo.grafana.net/loki/api/v1/push
ALLOY_LOKI_USER=0
ALLOY_LOKI_TOKEN=placeholder
ALLOY_EDGE_LOG_GLOB=/var/log/nginx/portal-prod.access.log
ALLOY_PM2_LOG_GLOB=/home/apps/portal-prod/.pm2/logs/portal-api-prod-*.log
ALLOY_JOURNAL_UNITS=celery-worker@prod.service|celery-beat@prod.service
EOF
    echo "placeholder" > "$TMP/alloy-token"
    C_ID="$(docker create --env-file "$TMP/alloy.env" grafana/alloy:latest validate /etc/alloy/config.alloy 2>/dev/null)"
    if [[ -z "$C_ID" ]]; then
        falha "não foi possível criar o container de validação do Alloy"
    else
        docker cp "$REPO_DIR/infra/observability/alloy/config.alloy" "$C_ID:/etc/alloy/config.alloy" >/dev/null 2>&1
        docker cp "$TMP/alloy-token" "$C_ID:/tmp/alloy-token" >/dev/null 2>&1
        if out="$(docker start -a "$C_ID" 2>&1)"; then
            ok "alloy validate (imagem oficial grafana/alloy)"
        else
            falha "alloy validate em container: $(printf '%s' "$out" | head -8)"
        fi
        docker rm -f "$C_ID" >/dev/null 2>&1
    fi
else
    pulado "sem binário do Alloy e sem Docker: config.alloy NÃO validado"
fi
fi

# ---------------------------------------------------------------------------
# Terraform (se um dia existir)
# ---------------------------------------------------------------------------
if interessa terraform; then
titulo "Terraform"
mapfile -t TFS < <(find . -name '*.tf' -not -path './node_modules/*' -not -path './.git/*' 2>/dev/null)
if [[ "${#TFS[@]}" -eq 0 ]]; then
    ok "nenhum arquivo .tf no repositório (nada que validar)"
elif command -v terraform >/dev/null 2>&1; then
    falha "há .tf no repositório e o Terraform precisa ser inicializado antes de validar (pendência real)"
else
    falha "há .tf no repositório e o binário do Terraform não está instalado: validate NÃO executado"
fi
fi

# ---------------------------------------------------------------------------
# Segredos
# ---------------------------------------------------------------------------
if interessa segredos; then
titulo "Varredura de segredo acidental"
# Padrões de segredo COMUM no formato de exemplo do projeto (`troque-aqui`,
# `troque-por-uma-chave`) são legítimos e não devem acusar. O que NÃO pode
# aparecer é um valor com cara de segredo real.
ACUSADOS=0
while IFS= read -r linha; do
    arquivo="${linha%%:*}"
    if grep -nE '(sk-[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|xox[baprs]-[A-Za-z0-9-]{10,}|glpat-[A-Za-z0-9_-]{20,}|-----BEGIN [A-Z ]*PRIVATE KEY-----)' "$arquivo" >/dev/null 2>&1; then
        falha "possível segredo em $arquivo"
        grep -nE '(sk-[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|xox[baprs]-[A-Za-z0-9-]{10,}|glpat-[A-Za-z0-9_-]{20,}|-----BEGIN [A-Z ]*PRIVATE KEY-----)' "$arquivo" | sed 's/^/          /'
        ACUSADOS=1
    fi
done < <(git -C "$REPO_DIR" status --porcelain --untracked-files=all 2>/dev/null | awk '{print $2}')
if (( ! ACUSADOS )); then
    ok "nenhum padrão de segredo real nos arquivos alterados"
fi
# Arquivos .env REAIS nunca podem estar versionados.
if git -C "$REPO_DIR" ls-files --error-unmatch .env .env.production .env.localhost backend/.env frontend/.env.local >/dev/null 2>&1; then
    falha "há arquivo .env REAL versionado no repositório"
else
    ok "nenhum .env real versionado"
fi
fi

# ---------------------------------------------------------------------------
# Consistência da lista de pendências declaradas
# ---------------------------------------------------------------------------
# Só faz sentido na rodada completa: com `--somente X`, a checagem que produz a
# pendência pode nem rodar, e "não encontrei" seria mentira.
if [[ -z "$FILTRO" ]]; then
    if [[ ! -r "$PENDENCIAS_FILE" ]]; then
        falha "arquivo de pendências declaradas ausente ou ilegível: $PENDENCIAS_FILE"
    else
        while read -r chave _resto; do
            [[ -n "$chave" ]] || continue
            declarado=0
            for vista in ${PENDENCIAS_VISTAS[@]+"${PENDENCIAS_VISTAS[@]}"}; do
                if [ "$vista" = "$chave" ]; then declarado=1; break; fi
            done
            if [ "$declarado" -eq 0 ]; then
                falha "pendência declarada e não mais existente: $chave — remova a linha de $PENDENCIAS_FILE (a lista envelhecida passaria a esconder pendência nova)"
            else
                ok "pendência declarada e ainda real: $chave"
            fi
        done < <(sed -e 's/#.*//' -e 's/[[:space:]]*$//' "$PENDENCIAS_FILE" | grep -v '^$')
    fi
fi

# ---------------------------------------------------------------------------
printf '\n\033[1m== Resumo ==\033[0m\n'
printf '  %d OK, %d AVISO, %d PENDENTE DECLARADA, %d PULADO, %d FALHOU\n' \
    "$OKS" "$AVISOS" "$PENDENTES_RECONHECIDOS" "$PULADOS" "$FALHAS"
if (( ${#RESUMO_PENDENCIAS[@]} )); then
    printf '\n  Pendências reais declaradas (não reprovam o gate; não são "OK"):\n'
    printf '    %s\n' "${RESUMO_PENDENCIAS[@]}"
fi
if (( FALHAS )); then
    printf '\n  Itens que FALHARAM:\n'
    printf '    %s\n' "${RESUMO_FALHAS[@]}"
fi
if (( AVISOS || PULADOS )); then
    printf '\n  %d aviso(s) e %d pulado(s) — um item PULADO NÃO é um item validado.\n' "$AVISOS" "$PULADOS"
fi
if (( FALHAS )); then
    exit 1
fi
exit 0
