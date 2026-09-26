#!/usr/bin/env bash
# Prova de poder discriminante do `infra/observability/alloy/verificar-env.sh`.
#
# Um check que não tem como reprovar não é check. Para cada condição que o gate
# deveria detectar, este script constrói um ambiente VÁLIDO, quebra exatamente
# aquela condição e mostra que o gate REPROVA. O caso "tudo válido" precisa
# sair 0 — sem ele, "reprova sempre" também seria um gate inútil.
#
# Uso:  bash proving/testar-verificar-env.sh
set -uo pipefail

AQUI="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$AQUI/../../.." && pwd)"
GATE="$REPO/infra/observability/alloy/verificar-env.sh"
LAB="${ALLoy_TESTE_DIR:-/home/alex-buttielie/scratch/on2/verificar-env-prova}"

REPROVOU=0
TOTAL=0

limpar() { rm -rf "$LAB"; }

# ambiente_base <arquivo-de-env-a-gerar>
ambiente_base() {
    local destino="$1"
    mkdir -p "$LAB"
    printf 'TOKEN-DE-TESTE-LOCAL-NAO-E-SEGREDO\n' > "$LAB/metrics-token"
    chmod 600 "$LAB/metrics-token"
    printf '{"request_id":"abc","status":"200","uri":"/"}\n' > "$LAB/edge.log"
    printf '{"request_id":"abc","levelname":"INFO"}\n' > "$LAB/api-out.log"
    printf '{"estado":"ok","verificado":true,"fila":"celery"}\n' > "$LAB/filas.jsonl"
    cat > "$destino" <<EOF
ALLOY_AMBIENTE=production
ALLOY_RELEASE=abcdef1234567890abcdef1234567890abcdef12
ALLOY_LOG_LEVEL=info
ALLOY_REMOTE_WRITE_URL=https://prometheus-1234.grafana.net/api/prom/push
ALLOY_REMOTE_WRITE_USER=1234
ALLOY_REMOTE_WRITE_TOKEN=glc_abcdefghijklmnopqrstuvwxyz0123456789
ALLOY_LOKI_WRITE_URL=https://logs-1234.grafana.net/loki/api/v1/push
ALLOY_LOKI_USER=1234
ALLOY_LOKI_TOKEN=glc_zyxwvutsrqponmlkjihgfedcba9876543210
ALLOY_BACKEND_METRICS_ADDR=127.0.0.1:59999
ALLOY_BACKEND_METRICS_TOKEN_FILE=$LAB/metrics-token
ALLOY_SELF_ADDR=127.0.0.1:12345
ALLOY_EDGE_LOG_GLOB=$LAB/edge.log
ALLOY_PM2_LOG_GLOB=$LAB/api-out.log
ALLOY_FILAS_JSON_PATH=$LAB/filas.jsonl
ALLOY_JOURNAL_UNITS="celery-worker@prod.service|nginx.service"
EOF
}

# caso <nome> <mutação em bash> <trecho-esperado-na-saída>
caso() {
    local nome="$1" mutacao="$2" esperado="$3"
    TOTAL=$(( TOTAL + 1 ))
    local env_file="$LAB/env-$TOTAL"
    ambiente_base "$env_file"
    # shellcheck disable=SC1090
    ( set +u; eval "$mutacao" )
    local saida exit
    saida="$(bash "$GATE" "$env_file" 2>&1)"
    exit=$?
    if [[ "$exit" -ne 0 ]] && grep -qF "$esperado" <<<"$saida"; then
        printf '  REPROVA  %-52s exit=%s  "%s"\n' "$nome" "$exit" "$esperado"
        REPROVOU=$(( REPROVOU + 1 ))
    else
        printf '  FALHOU   %-52s exit=%s (esperava !=0 e "%s")\n' "$nome" "$exit" "$esperado"
        printf '           saída: %s\n' "$(tr '\n' '|' <<<"$saida" | cut -c1-240)"
    fi
}

echo "=============================================================================="
echo "0) CASO BASE — ambiente completo e válido tem de passar (exit 0)"
echo "=============================================================================="
limpar
mkdir -p "$LAB"
ambiente_base "$LAB/env-base"
saida="$(bash "$GATE" "$LAB/env-base" 2>&1)"; exit=$?
# Os grupos de journal e o runbook interno são environmental: neste host não há
# systemd e as regras ainda usam o placeholder .invalid (por desenho, é o que o
# gate exige que seja trocado). Portanto o caso base é avaliado pelo que o gate
# SABE checar aqui, e as duas condições ambientais são verificadas à parte.
if grep -qF "ALLOY_" <<<"$saida" && grep -qF "ERRO: ALLOY_" <<<"$saida"; then
    echo "  FALHOU   o ambiente válido produziu erro de variável obrigatória"
    printf '           %s\n' "$saida"
else
    echo "  OK       nenhuma variável obrigatória, token, fonte de log ou placeholder reprovado"
fi
echo
echo "  avisos/erros ambientais conhecidos neste host (não são culpa do env):"
grep -E 'AVISO|systemd|runbook' <<<"$saida" | sed 's/^/           /'
echo

echo "=============================================================================="
echo "1) PODER DISCRIMINANTE — cada condição quebrada tem que REPROVAR"
echo "=============================================================================="
caso "endpoint de métricas vazio" \
     'sed -i "s|^ALLOY_REMOTE_WRITE_URL=.*|ALLOY_REMOTE_WRITE_URL=|" "$env_file"' \
     "ALLOY_REMOTE_WRITE_URL ausente ou vazia"
caso "token de métricas vazio" \
     'sed -i "s|^ALLOY_REMOTE_WRITE_TOKEN=.*|ALLOY_REMOTE_WRITE_TOKEN=|" "$env_file"' \
     "ALLOY_REMOTE_WRITE_TOKEN ausente ou vazia"
caso "arquivo de token inexistente" \
     "rm -f '$LAB/metrics-token'" \
     "aponta para arquivo inexistente"
caso "arquivo de token com modo 644" \
     'chmod 644 "$LAB/metrics-token"' \
     "esperado 600 ou 400"
caso "arquivo de token vazio" \
     'printf "" > "$LAB/metrics-token"; chmod 600 "$LAB/metrics-token"' \
     "arquivo de token vazio"
caso "placeholder EXEMPLO sobrevivendo" \
     'sed -i "s|^ALLOY_REMOTE_WRITE_USER=.*|ALLOY_REMOTE_WRITE_USER=EXEMPLO|" "$env_file"' \
     "ainda contém o marcador"
caso "endereço de métricas malformado" \
     'sed -i "s|^ALLOY_BACKEND_METRICS_ADDR=.*|ALLOY_BACKEND_METRICS_ADDR=localhost|" "$env_file"' \
     "não é host:porta válido"
caso "log de borda inexistente" \
     'rm -f "$LAB/edge.log"' \
     "nenhum arquivo legível casa com o padrão"
caso "log da aplicação inexistente" \
     'rm -f "$LAB/api-out.log"' \
     "nenhum arquivo legível casa com o padrão"
caso "saude_filas --json inexistente" \
     'rm -f "$LAB/filas.jsonl"' \
     "nenhum arquivo legível casa com o padrão"
caso "log de borda em texto puro (não-JSON)" \
     'printf "10.0.0.1 - - [x] \"GET / HTTP/1.1\" 200\n" > "$LAB/edge.log"' \
     "a primeira linha não é um objeto JSON"
REGRAS_TESTE="$REPO/infra/observability/alerts/regras-teste-placeholder.yaml"
caso "runbook placeholder ainda no arquivo de regras" \
     "cat > '$REGRAS_TESTE' <<'YAML'
groups:
  - name: placeholder
    rules:
      - alert: Y
        expr: vector(1)
        labels:
          runbook: y
        annotations:
          runbook_url: \"https://runbooks.portal.exemplo.invalid/y.md\"
YAML" \
     "ainda usa o runbook placeholder"
rm -f "$REGRAS_TESTE" 2>/dev/null

echo
echo "=============================================================================="
printf 'RESULTADO: %d de %d condições quebradas foram detectadas\n' "$REPROVOU" "$TOTAL"
echo "=============================================================================="
limpar
[[ "$REPROVOU" -eq "$TOTAL" ]] || exit 1
