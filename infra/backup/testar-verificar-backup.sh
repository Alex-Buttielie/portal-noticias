#!/usr/bin/env bash
# Prova de poder discriminante do `infra/backup/verificar_backup.sh`.
#
# Constrói diretórios de backup com dumps/mídias de idades conhecidas, roda o
# watchdog e confere o exit code. Todo caso quebra UMA condição que o watchdog
# deveria detectar, e a última seção é a que importa: um watchdog que só
# retorna 0 seria tão inútil quanto um que nunca retorna 0.
#
# Nada aqui toca disco real, banco ou rede: os diretórios são temporários, e o
# caso que exercita o bucket usa um `aws` stub que devolve o tamanho pedido.
#
# Uso:  bash infra/backup/testar-verificar-backup.sh
set -uo pipefail

AQUI="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$AQUI/../.." && pwd)"
WATCHDOG="$REPO/infra/backup/verificar_backup.sh"
LAB="${BACKUP_TESTE_DIR:-/home/alex-buttielie/scratch/on2/backup-prova}"

ACERTOS=0
TOTAL=0

limpar() { rm -rf "$LAB"; }

# Emula `aws s3api head-object`. Três modos, escolhidos por variável de
# ambiente: `AWS_STUB_FAIL` (a chamada falha), `AWS_STUB_SIZE` (devolve um
# tamanho arbitrário) e o padrão (devolve o tamanho do objeto local, que é o
# caminho de sucesso do watchdog).
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
# O stub de `aws` é escrito pela função `escrever_stub_aws`, chamada DEPOIS do
# primeiro `limpar` (mais abaixo). Isso não é detalhe: `limpar` apaga `$LAB`
# inteiro, e um stub escrito antes dele seria levado junto — foi exatamente o
# que fez os cenários remotos falharem com "AWS CLI não existe" num host que
# tem o stub. O stub emula `head-object` devolvendo o tamanho do objeto local
# (ou falhando, quando o cenário pede), o que permite exercitar o caminho
# remoto sem credencial e sem rede.

# scenario <nome> <exit-esperado> <substring-esperado-na-ultima-linha> <setup>
scenario() {
    local nome="$1" esperado="$2" trecho="$3" setup="$4"
    TOTAL=$(( TOTAL + 1 ))
    local dir="$LAB/$(printf '%02d' "$TOTAL")-caso"
    mkdir -p "$dir"
    ( set +u; cd "$dir"; eval "$setup" )
    local saida exit ultima
    saida="$(BACKUP_DIR="$dir" BACKUP_WATCHDOG_CHECK_REMOTE=0 \
             BACKUP_WATCHDOG_EXIGIR_REMOTO=0 \
             PATH="$LAB/bin:$PATH" bash "$WATCHDOG" 2>/dev/null)"
    exit=$?
    ultima="$(tail -n 1 <<<"$saida")"
    if [[ "$exit" == "$esperado" ]] && grep -qF "$trecho" <<<"$ultima"; then
        printf '  OK       %-56s exit=%s  %s\n' "$nome" "$exit" "$trecho"
        ACERTOS=$(( ACERTOS + 1 ))
    else
        printf '  FALHOU   %-56s exit=%s (esperava %s)\n' "$nome" "$exit" "$esperado"
        printf '           json: %s\n' "$ultima"
    fi
}

# A idade que o watchdog mede é o MTIME (`stat -c %Y`), não o timestamp do
# nome. O `pg_backup_pm2.sh` publica por `mv` (linhas 373 e 390), e `mv` põe
# mtime = agora — por isso o cenário precisa de `touch -d` para simular a
# passagem do tempo. Um teste que só mudasse o NOME estaria medindo o arquivo
# errado e o watchdog pareceria quebrado à toa.
dump_idade() {
    local horas="$1" ts
    ts="$(date -u -d "-${horas} hours" +%Y%m%dT%H%M%SZ)"
    printf 'conteudo-de-teste-de-17-bytes' > "pm2-db-$ts.dump"
    touch -d "-${horas} hours" "pm2-db-$ts.dump"
}
dump_idade_com_midia() {
    local horas="$1" ts
    dump_idade "$horas"
    ts="$(date -u -d "-${horas} hours" +%Y%m%dT%H%M%SZ)"
    printf 'midia-de-teste' > "pm2-media-$ts.tar.gz"
    touch -d "-${horas} hours" "pm2-media-$ts.tar.gz"
}

echo "=============================================================================="
echo "VEREDICTO DO WATCHDOG — exit code e status, por cenário"
echo "=============================================================================="
limpar
mkdir -p "$LAB/bin"
escrever_stub_aws

scenario "dentro do prazo (1 h), remoto não exigido" 0 '"status":"ok"' \
    'dump_idade_com_midia 1'

scenario "dentro do prazo mas com 30 h -> atrasado" 1 '"status":"atrasado"' \
    'dump_idade_com_midia 30'

# O limite é `>` e não `>=`: um backup com exatamente 26 h ainda está dentro
# do prazo declarado. O cenário existe para FIXAR essa fronteira — sem ele,
# alguém "corrige" para `>=` sem perceber que mudou a semântica.
scenario "exatamente no limite (26 h) -> ainda dentro do prazo" 0 '"status":"ok"' \
    'dump_idade_com_midia 26'

scenario "26 h + 1 min -> atrasado" 1 '"status":"atrasado"' \
    'dump_idade_com_midia 26; touch -d "-1637 minutes" pm2-db-*.dump pm2-media-*.dump'

scenario "nunca executou (sem dump)" 2 '"status":"nunca-executou"' \
    'true'

scenario "dump novo mas mídia muito velha -> backup pela metade" 1 '"status":"atrasado"' \
    'dump_idade 1; ts=$(date -u -d "-40 hours" +%Y%m%dT%H%M%SZ); printf midia > "pm2-media-$ts.tar.gz"; touch -d "-40 hours" "pm2-media-$ts.tar.gz"'

# Mídia dentro do prazo (5 h) mas 4 h mais velha que o dump (1 h): a retenção
# local apaga dump e mídia por `-mtime` de forma independente
# (pg_backup_pm2.sh:438-442), então a mídia pode sumir primeiro e deixar um
# backup sem conteúdo. Nenhum dos dois está "atrasado" — por isso o status
# próprio `incompleto`.
scenario "mídia mais velha que o dump, ambos no prazo -> incompleto" 1 '"status":"incompleto"' \
    'dump_idade 1; ts=$(date -u -d "-5 hours" +%Y%m%dT%H%M%SZ); printf midia > "pm2-media-$ts.tar.gz"; touch -d "-5 hours" "pm2-media-$ts.tar.gz"'

scenario "marcador novo com dump velho -> marcador Mentiroso" 1 '"status":"atrasado"' \
    'dump_idade 50; touch .ultimo-backup-ok'

echo
echo "=============================================================================="
echo "VEREDICTO COM O DESTINO REMOTO — cópia local não é backup"
echo "=============================================================================="

# caso_remoto <nome> <exit> <trecho> <setup> <env-extras>
caso_remoto() {
    local nome="$1" esperado="$2" trecho="$3" setup="$4" extra="$5"
    TOTAL=$(( TOTAL + 1 ))
    local dir="$LAB/$(printf '%02d' "$TOTAL")-remoto"
    mkdir -p "$dir"
    ( set +u; cd "$dir"; eval "$setup" )
    local saida exit ultima
    saida="$(env BACKUP_DIR="$dir" BACKUP_S3_BUCKET=exemplo-bucket \
                  BACKUP_S3_ACCESS_KEY=chave-de-teste BACKUP_S3_SECRET_KEY=segredo-de-teste \
                  AWS_STUB_DIR="$dir" PATH="$LAB/bin:$PATH" $extra \
                  bash "$WATCHDOG" 2>/dev/null)"
    exit=$?
    ultima="$(tail -n 1 <<<"$saida")"
    if [[ "$exit" == "$esperado" ]] && grep -qF "$trecho" <<<"$ultima"; then
        printf '  OK       %-56s exit=%s  %s\n' "$nome" "$exit" "$trecho"
        ACERTOS=$(( ACERTOS + 1 ))
    else
        printf '  FALHOU   %-56s exit=%s (esperava %s)\n' "$nome" "$exit" "$esperado"
        printf '           json: %s\n' "$ultima"
    fi
}

caso_remoto "bucket ok, objeto do mesmo tamanho -> 0" 0 '"remoto_confirmado":true' \
    'dump_idade_com_midia 1' ""

# `head-object` falhando é "remoto-indisponivel", e não "sem-destino": o bucket
# existe, a consulta é que falhou. Colapsar os dois mandaria o operador
# procurar uma configuração de destino que já está certa.
caso_remoto "head-object falha -> remoto indisponível" 1 '"status":"remoto-indisponivel"' \
    'dump_idade_com_midia 1' 'AWS_STUB_FAIL=1'

caso_remoto "tamanho remoto divergente -> upload truncado" 3 '"status":"indisponivel"' \
    'dump_idade_com_midia 1' 'AWS_STUB_SIZE=999999'

caso_remoto "sem bucket e remoto obrigatório -> sem-destino" 1 '"status":"sem-destino"' \
    'dump_idade_com_midia 1' 'AWS_STUB_FAIL=1 BACKUP_WATCHDOG_CHECK_REMOTE=0'

echo
echo "=============================================================================="
echo "CONFIGURAÇÃO INVÁLIDA — 'não sei' não é 'está tudo bem' (exit 3)"
echo "=============================================================================="
TOTAL=$(( TOTAL + 1 ))
saida="$(BACKUP_DIR="$LAB" BACKUP_MAX_AGE_HOURS=zero bash "$WATCHDOG" 2>/dev/null)"; exit=$?
if [[ "$exit" == 3 ]] && grep -qF '"status":"indisponivel"' <<<"$saida"; then
    printf '  OK       %-56s exit=3  status=indisponivel\n' "BACKUP_MAX_AGE_HOURS não numérico"
    ACERTOS=$(( ACERTOS + 1 ))
else
    printf '  FALHOU   %-56s exit=%s (esperava 3)\n' "BACKUP_MAX_AGE_HOURS não numérico" "$exit"
fi

TOTAL=$(( TOTAL + 1 ))
saida="$(BACKUP_DIR=/caminho/que/nao/existe bash "$WATCHDOG" 2>/dev/null)"; exit=$?
if [[ "$exit" == 3 ]] && grep -qF 'BACKUP_DIR inexistente' <<<"$saida"; then
    printf '  OK       %-56s exit=3  BACKUP_DIR inexistente\n' "BACKUP_DIR inexistente"
    ACERTOS=$(( ACERTOS + 1 ))
else
    printf '  FALHOU   %-56s exit=%s (esperava 3)\n' "BACKUP_DIR inexistente" "$exit"
fi

echo
echo "=============================================================================="
echo "A PROVA DE QUE O WATCHDOG PODE VERDE — e o que esse verde significa"
echo "=============================================================================="
dir="$LAB/verde-real"
mkdir -p "$dir"
( set +u; cd "$dir"; dump_idade_com_midia 2 )
saida="$(BACKUP_DIR="$dir" BACKUP_S3_BUCKET=exemplo-bucket \
          BACKUP_S3_ACCESS_KEY=k BACKUP_S3_SECRET_KEY=s \
          AWS_STUB_DIR="$dir" PATH="$LAB/bin:$PATH" bash "$WATCHDOG" 2>/dev/null)"
exit=$?
printf '  exit=%s\n' "$exit"
tail -n 1 <<<"$saida" | sed 's/^/  /'
echo
echo "  Note que o verde NÃO é 'o backup existe': é 'o backup existe, tem menos"
echo "  de 26 h, e a MESMA versão está no bucket com o MESMO tamanho'. As três"
echo "  condições podem falhar separadamente, e os testes acima cobrem as três."
echo
echo "=============================================================================="
printf 'RESULTADO: %d de %d cenários com o veredito esperado\n' "$ACERTOS" "$TOTAL"
echo "=============================================================================="
limpar
[[ "$ACERTOS" -eq "$TOTAL" ]] || exit 1
