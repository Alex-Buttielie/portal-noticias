#!/usr/bin/env bash
# Gate de configuração do Grafana Alloy (run 20260925-1020-observabilidade).
#
# POR QUE ISTO EXISTE
#   O `config.alloy` não consegue falhar sozinho: `sys.env` de uma variável
#   ausente devolve string vazia, o componente entra em erro no log e o
#   processo CONTINUA no ar. Um coletor no ar que não exporta nada é pior que
#   um coletor parado, porque produz "zero erros" no painel — que é
#   indistinguível de um produto saudável. Este script é a barreira
#   fail-closed: ele roda no `ExecStartPre` da unit do Alloy e no
#   `scripts/observability/validar-infra.sh`, e qualquer item faltando impede a
#   inicialização em vez de degradar em silêncio.
#
# Uso:
#   verificar-env.sh                 # valida o ambiente atual
#   verificar-env.sh /etc/portal/alloy-prod.env
#
# Saída: 0 = tudo presente; 1 = falta algo (com a lista do que falta).
# Nenhum valor é impresso: só o NOME das variáveis. Um gate que imprime token
# no log vira o vazamento que ele deveria impedir.
set -uo pipefail

ENV_FILE="${1:-${ALLOY_ENV_FILE:-}}"
FALTA=0

log() { printf '[alloy] %s\n' "$*"; }
erro() { printf '[alloy] ERRO: %s\n' "$*" >&2; }

# Variáveis obrigatórias com valor real (endpoint ou identificador).
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
    ALLOY_LOG_LEVEL
)

# Placeholders que NÃO podem sobreviver à instalação: um valor de exemplo no
# arquivo de produção é a forma mais comum de "configurar" o coletor com a
# string de documentação e descobrir o problema quando o painel não recebe nada.
PLACEHOLDERS=(
    "cole-aqui"
    "troque-aqui"
    "NNNN"
    "NNN"
    "example.invalid"
    "seu-dominio"
)

# Valores que não podem ser placeholder: comparados em maiúsculas.
VERIFICAR_PLACEHOLDER=1

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
    log "AVISO: ALLOY_RELEASE vazio; os painéis não terão contexto de versão"
fi
if [[ -z "$(valor_de ALLOY_JOURNAL_UNITS)" ]]; then
    log "AVISO: ALLOY_JOURNAL_UNITS vazio; o journal do systemd não será coletado (não falha a inicialização de propósito)"
fi

if (( VERIFICAR_PLACEHOLDER )); then
    for nome in "${OBRIGATORIAS_COMO_TEXTO[@]}"; do
        valor="$(valor_de "$nome")"
        [[ -z "$valor" ]] && continue
        for marcador in "${PLACEHOLDERS[@]}"; do
            if [[ "${valor^^}" == *"${marcador^^}"* ]]; then
                erro "$nome ainda contém o placeholder '$marcador' (valor de exemplo em arquivo de produção)"
                FALTA=1
            fi
        done
    done
fi

# Arquivo de token: tem que existir, ser legível pelo usuário efetivo e NÃO
# ser legível por outros. Token em arquivo aberto é o mesmo token em qualquer
# log de `ls -l` e de backup.
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
            erro "arquivo de token vazio: $arquivo_token (o scrape voltaria 404 e o alerta de coletor cairia)"
            FALTA=1
        fi
    fi
fi

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
    log "AVISO: sem systemd em execução neste host; checagem de grupo do journal ignorada"
fi

if (( FALTA )); then
    erro "configuração do Alloy INVÁLIDA: o coletor não deve ser iniciado"
    exit 1
fi

log "configuração do Alloy válida (endpoint, token, arquivo de token e permissões)"
exit 0
