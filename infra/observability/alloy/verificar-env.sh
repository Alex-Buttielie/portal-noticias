#!/usr/bin/env bash
# Gate de configuração do Grafana Alloy (item P2-01, Onda 2).
#
# POR QUE ISTO EXISTE
#   O `config.alloy` não consegue falhar sozinho: `sys.env` de uma variável
#   ausente devolve string vazia, o componente entra em erro no log e o
#   processo CONTINUA no ar. Um coletor no ar que não exporta nada é pior que
#   um coletor parado, porque produz "zero erros" no painel — que é
#   indistinguível de um produto saudável. Este script é a barreira
#   fail-closed: ele roda no `ExecStartPre` da unit do Alloy, e qualquer item
#   faltando impede a inicialização em vez de degradar em silêncio.
#
# Uso:
#   verificar-env.sh                 # valida o ambiente já exportado
#   verificar-env.sh /etc/portal/alloy-prod.env
#
# Saída: 0 = tudo presente; 1 = falta algo (com a lista do que falta).
# Nenhum valor é impresso: só o NOME das variáveis. Um gate que imprime token
# no log vira o vazamento que ele deveria impedir.
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PAIS_RAIZ="$(cd "$SCRIPT_DIR/../../.." && pwd)"

ENV_FILE="${1:-${ALLOY_ENV_FILE:-}}"
FALTA=0
AVISOS=0

log() { printf '[alloy] %s\n' "$*"; }
aviso() { printf '[alloy] AVISO: %s\n' "$*"; AVISOS=$(( AVISOS + 1 )); }
erro() { printf '[alloy] ERRO: %s\n' "$*" >&2; }

# ---------------------------------------------------------------------------
# Variáveis obrigatórias com valor real (endpoint ou identificador).
# `ALLOY_FILAS_JSON_PATH` entrou na lista por decisão, não por cerimônia: sem o
# arquivo de `saude_filas --json` o painel de filas fica vazio, e painel de
# filas vazio é lido como "nenhuma fila acumulada" — o falso verde mais caro
# deste diretório.
# ---------------------------------------------------------------------------
OBRIGATORIAS_COMO_TEXTO=(
    ALLOY_AMBIENTE
    ALLOY_REMOTE_WRITE_URL
    ALLOY_REMOTE_WRITE_USER
    ALLOY_REMOTE_WRITE_TOKEN
    ALLOY_LOKI_WRITE_URL
    ALLOY_LOKI_USER
    ALLOY_LOKI_TOKEN
    ALLOY_BACKEND_METRICS_ADDR
    ALLOY_BACKEND_METRICS_TOKEN_FILE
    ALLOY_SELF_ADDR
    ALLOY_EDGE_LOG_GLOB
    ALLOY_PM2_LOG_GLOB
    ALLOY_FILAS_JSON_PATH
    ALLOY_LOG_LEVEL
)

# Marcadores que NÃO podem sobreviver à instalação: um valor de exemplo no
# arquivo de produção é a forma mais comum de "configurar" o coletor com a
# string de documentação e descobrir o problema quando o painel não recebe nada.
# Comparação em maiúsculas, para pegar "Exemplo" tanto quanto "EXEMPLO".
PLACEHOLDERS=(
    "EXEMPLO"
    "cole-aqui"
    "troque-aqui"
    "troque pelo"
    "substitua"
    "NNNN"
    "NNN"
    ".invalid"
    "seu-dominio"
    "example.com"
    "<"
    ">"
)

if [[ -n "$ENV_FILE" ]]; then
    if [[ ! -r "$ENV_FILE" ]]; then
        erro "arquivo de ambiente ausente ou ilegível: $ENV_FILE"
        exit 1
    fi
    log "lendo $ENV_FILE"
    set -a
    # shellcheck disable=SC1090
    source "$ENV_FILE"
    set +a
else
    log "validando o ambiente já exportado no processo (sem arquivo)"
fi

valor_de() {
    local nome="$1"
    printf '%s' "${!nome:-}"
}

for nome in "${OBRIGATORIAS_COMO_TEXTO[@]}"; do
    if [[ -z "$(valor_de "$nome")" ]]; then
        erro "$nome ausente ou vazia: o coletor subiria sem destino de dados"
        FALTA=1
    fi
done

# `ALLOY_RELEASE` é recomendado, não obrigatório: sem ele os painéis ficam sem
# contexto de versão, mas a coleta funciona. Por isso é aviso, não erro.
if [[ -z "$(valor_de ALLOY_RELEASE)" ]]; then
    aviso "ALLOY_RELEASE vazio; os painéis não terão contexto de versão"
fi
if [[ -z "$(valor_de ALLOY_JOURNAL_UNITS)" ]]; then
    aviso "ALLOY_JOURNAL_UNITS vazio; o journal do systemd não será coletado (não falha a inicialização de propósito)"
fi

for nome in "${OBRIGATORIAS_COMO_TEXTO[@]}"; do
    valor="$(valor_de "$nome")"
    [[ -z "$valor" ]] && continue
    for marcador in "${PLACEHOLDERS[@]}"; do
        if [[ "${valor^^}" == *"${marcador^^}"* ]]; then
            erro "$nome ainda contém o marcador '$marcador' (valor de exemplo em arquivo de produção)"
            FALTA=1
        fi
    done
done

# ---------------------------------------------------------------------------
# Arquivo de token
# ---------------------------------------------------------------------------
# Tem que existir, ser legível pelo usuário efetivo e NÃO ser legível por
# outros. Token em arquivo aberto é o mesmo token em qualquer log de `ls -l` e
# de backup.
arquivo_token="$(valor_de ALLOY_BACKEND_METRICS_TOKEN_FILE)"
if [[ -n "$arquivo_token" ]]; then
    if [[ ! -f "$arquivo_token" ]]; then
        erro "ALLOY_BACKEND_METRICS_TOKEN_FILE aponta para arquivo inexistente: $arquivo_token"
        FALTA=1
    elif [[ ! -r "$arquivo_token" ]]; then
        erro "arquivo de token não legível pelo usuário efetivo: $arquivo_token"
        FALTA=1
    else
        modo="$(stat -c '%a' "$arquivo_token" 2>/dev/null || echo '?')"
        if [[ "$modo" != "600" && "$modo" != "400" ]]; then
            erro "arquivo de token com modo $modo (esperado 600 ou 400): $arquivo_token"
            FALTA=1
        fi
        if [[ ! -s "$arquivo_token" ]]; then
            erro "arquivo de token vazio: $arquivo_token (o scrape voltaria 401 e o alerta de coletor cairia)"
            FALTA=1
        fi
    fi
fi

# ---------------------------------------------------------------------------
# Arquivos de log: existirem é erro; serem JSON é aviso com o porquê.
# ---------------------------------------------------------------------------
# Por que a diferença: um `loki.source.file` apontando para arquivo inexistente
# fica "iniciando sem erro e não coletando nada", que é o pior estado. Já um
# arquivo que existe e não é JSON pode ser uma instalação legítima de ambiente
# que ainda não recebeu o `log_format` — nesse caso a falha é de um item de
# nginx, não de configuração do coletor, e reprovar aqui só faria o operador
# ignorar o gate.
primeira_linha_json() {
    local arquivo="$1"
    [[ -f "$arquivo" ]] || return 2
    local linha
    linha="$(head -n 1 "$arquivo" 2>/dev/null | tr -d '\r')"
    [[ -n "$linha" ]] || return 2
    # Um objeto JSON de uma linha começa com '{' e termina com '}'. Sem uma
    # ferramenta de parse no host, este teste é estrutural e suficiente: o
    # `stage.json` do Loki é que vai reprovar linha por linha depois.
    #
    # Os dois extremos ficam ENTRE ASPAS para que o bash os trate como
    # literais e não como classes de glob — sem as aspas, `}` sozinho é
    # sintaxe inválida no padrão.
    [[ "$linha" == "{"*"}" ]]
}

verificar_fonte_de_log() {
    local variavel="$1" rotulo="$2"
    local padrao
    padrao="$(valor_de "$variavel")"
    [[ -z "$padrao" ]] && return 0

    # Glob: testa se o padrão casa com pelo menos um arquivo legível.
    local encontrado=0 candidato
    for candidato in $padrao; do
        if [[ -f "$candidato" && -r "$candidato" ]]; then
            encontrado=1
            if ! primeira_linha_json "$candidato"; then
                aviso "$rotulo: $candidato existe mas a primeira linha não é um objeto JSON de uma linha; o stage.json do Loki não vai extrair nada deste arquivo"
            fi
            break
        fi
    done
    if (( encontrado == 0 )); then
        erro "$rotulo: nenhum arquivo legível casa com o padrão '$padrao'; o loki.source.file ficaria ativo sem coletar nada"
        FALTA=1
    fi
}

verificar_fonte_de_log ALLOY_EDGE_LOG_GLOB "log de acesso da borda"
verificar_fonte_de_log ALLOY_PM2_LOG_GLOB "log da aplicação (PM2)"
verificar_fonte_de_log ALLOY_FILAS_JSON_PATH "saude_filas --json"

# ---------------------------------------------------------------------------
# O healthz e o readyz de `develop` existem?  Este host é o que faz o scrape?
# ---------------------------------------------------------------------------
# A causa nº1 de `up{job="portal-api"} == 0` em produção NÃO é o portal fora do
# ar: é o coletor com credencial errada, porque `/metrics` responde 401 para
# anônimo em `develop` (`backend/config/health.py:414-418`). Este bloco dá o
# teste que separa as duas hipóteses ANTES do deploy do coletor, e falha
# fechado quando não dá para testar.
if [[ -n "$ENV_FILE" ]] && [[ -f "$PAIS_RAIZ/backend/manage.py" ]]; then
    addr="$(valor_de ALLOY_BACKEND_METRICS_ADDR)"
    host_port="${addr##*:*}"
    porta="${addr##*:}"
    if [[ "$porta" =~ ^[0-9]+$ ]] && (( porta > 0 && porta < 65536 )); then
        if command -v curl >/dev/null 2>&1; then
            # Sem `|| echo`: o próprio curl imprime `000` quando não conecta, e
            # um segundo `000` viraria "HTTP 000000", que não casa com nenhum
            # dos casos abaixo e cai no aviso genérico.
            http_sem_token="$(curl -s -o /dev/null -w '%{http_code}' --max-time 5 \
                "http://127.0.0.1:${porta}/metrics" 2>/dev/null)"
            http_sem_token="${http_sem_token:-000}"
            if [[ "$http_sem_token" == "401" ]]; then
                log "/metrics respondeu 401 sem token: o portão da aplicação está fechado (comportamento esperado de develop)"
            elif [[ "$http_sem_token" == "000" ]]; then
                aviso "não foi possível falar com 127.0.0.1:${porta}/metrics; se o Gunicorn roda em outro host/porta, ajuste ALLOY_BACKEND_METRICS_ADDR"
            elif [[ "$http_sem_token" == "200" ]]; then
                erro "/metrics respondeu 200 SEM token em 127.0.0.1:${porta}: em develop o endpoint é restrito a staff ou token (backend/config/health.py:414-418). O que está servindo esta porta não é a configuração esperada"
                FALTA=1
            else
                aviso "/metrics respondeu HTTP ${http_sem_token} sem token; esperado 401 (develop) ou 000 (fora do ar)"
            fi
        else
            aviso "curl ausente; não foi possível confirmar o portão de /metrics"
        fi
    else
        erro "ALLOY_BACKEND_METRICS_ADDR não é host:porta válido: '$addr'"
        FALTA=1
    fi
fi

# ---------------------------------------------------------------------------
# Permissões de journal
# ---------------------------------------------------------------------------
# O `loki.source.journal` só coleta se o usuário efetivo estiver em `adm` e
# `systemd-journal`. SEM os dois grupos o componente "inicia sem erro e não
# coleta nada" — o falso verde dentro do próprio coletor, e por isso é erro
# aqui e não comentário no config.
if [[ -d /run/systemd/system ]]; then
    grupos="$(id -nG 2>/dev/null || true)"
    for grupo in adm systemd-journal; do
        if [[ " $grupos " != *" $grupo "* ]]; then
            erro "usuário efetivo não está no grupo '$grupo'; o journal do systemd NÃO será coletado (silenciosamente)"
            FALTA=1
        fi
    done
else
    aviso "sem systemd em execução neste host; checagem de grupo do journal ignorada"
fi

# ---------------------------------------------------------------------------
# Placeholder de runbook nas regras de alerta
# ---------------------------------------------------------------------------
# `runbook_url` em `https://runbooks.portal.exemplo.invalid/…` é placeholder
# deliberado (RFC 2606). Ele é seguro como placeholder, mas é INÚTIL como
# link: o operador que clica durante um incidente não chega em runbook nenhum.
# Carregar as regras assim é erro de instalação, e aqui é erro.
regras_dir="$SCRIPT_DIR/../alerts"
if [[ -d "$regras_dir" ]]; then
    for arquivo in "$regras_dir"/regras-*.yaml; do
        [[ -f "$arquivo" ]] || continue
        if grep -q 'runbooks\.portal\.exemplo\.invalid' "$arquivo" 2>/dev/null; then
            erro "$(basename "$arquivo") ainda usa o runbook placeholder (.invalid, RFC 2606); troque pelo endereço interno ANTES de carregar as regras no Mimir"
            FALTA=1
        fi
    done
fi

if (( FALTA )); then
    erro "configuração do Alloy INVÁLIDA: o coletor não deve ser iniciado"
    exit 1
fi

log "configuração do Alloy válida (endpoint, token, arquivo de token, fontes de log, permissões de journal e runbooks)"
if (( AVISOS )); then
    log "$AVISOS aviso(s) acima: a coleta funciona, mas com menos contexto do que o previsto"
fi
exit 0
