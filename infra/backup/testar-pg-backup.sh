#!/usr/bin/env bash
# Prova de poder discriminante do `infra/backup/pg_backup.sh` (variante
# Docker/Caddy).
#
# ESTE TESTE SUBE UM POSTGRES DE VERDADE E EXECUTA O SCRIPT DE VERDADE. Não é
# um teste de "o texto do script contém a palavra X": cada cenário quebra UMA
# das três correções e mostra que o resultado muda. Um teste que passa com a
# correção e sem ela não prova nada.
#
# O QUE É MEDIDO AQUI
#   A. modo de execução: o índice do git entrega um arquivo executável, e um
#      arquivo 644 produz exatamente o `Permission denied` do cron;
#   B. arquivo de ambiente: `backend/.env` (o que o deploy.yml cria) é lido;
#      apontar para `.env.production` aborta como abortava antes;
#   C. destino: o dump vai para fora da árvore do git; apontar BACKUP_DIR para
#      dentro do checkout o traz de volta;
#   D. execução real: dump gerado, tamanho e tabelas com dados;
#   E. restauração num banco NOVO, feita FORA do script, com comparação
#      tabela a tabela — um backup não verificado não é backup;
#   F. matriz de falhas: cada código de saída, e a garantia de que nenhuma
#      delas apaga o backup local;
#   G. storage remoto: o `aws` stub confirma as chamadas e os objetos, e prova
#      que upload falhado NÃO remove nada do disco local.
#
# O QUE ESTE TESTE NÃO FAZ
#   Não toca a VPS, não usa a senha dela, não precisa de credencial real e não
#   fala com a internet. O destino remoto é um stub de `aws`; a prova contra
#   uma API S3 de verdade (MinIO/moto, com a AWS CLI real) foi feita à parte.
#
# Uso:  bash infra/backup/testar-pg-backup.sh [--manter]
#
# Variáveis de ambiente:
#   BACKUP_TESTE_DIR         onde o laboratório é montado
#                             (padrão ~/scratch/<usuário>/pg-backup-lab)
#   BACKUP_TESTE_MANTER=1    não apaga o laboratório no fim
set -uo pipefail

AQUI="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$AQUI/../.." && pwd)"
LAB="${BACKUP_TESTE_DIR:-$HOME/scratch/$(id -un)/pg-backup-lab}"
DEPLOY="$LAB/portal-prod"
BACKUPS="$LAB/backups"
BIN="$LAB/bin"
PROJETO="pg-backup-lab"
export COMPOSE_PROJECT_NAME="$PROJETO"
ENV_ARQUIVO="$DEPLOY/backend/.env"
COMPOSE_ARQUIVO="$DEPLOY/docker-compose.yml"

ACERTOS=0
TOTAL=0
FALHAS=()

log() { printf '\n\033[1m%s\033[0m\n' "$*"; }
# Os contadores vivem AQUI, e não espalhados pelo teste: um `TOTAL` manual
# que some com um caminho sem asserção faria o veredito final dizer "48 de 56"
# sem que ninguém soubesse quais 8 faltavam.
passou() { printf '  OK       %-58s exit=%-3s %s\n' "$1" "$2" "$3"; ACERTOS=$(( ACERTOS + 1 )); TOTAL=$(( TOTAL + 1 )); }
falhou() {
    printf '  FALHOU   %-58s exit=%-3s (esperava %s) %s\n' "$1" "$2" "$3" "$4"
    FALHAS+=("$1"); TOTAL=$(( TOTAL + 1 ))
}

limpar() {
    if [[ -d "$LAB" ]]; then
        ( cd "$DEPLOY" 2>/dev/null && docker compose -f "$COMPOSE_ARQUIVO" --env-file "$ENV_ARQUIVO" \
            down -v --remove-orphans >/dev/null 2>&1 )
    fi
    [[ "${BACKUP_TESTE_MANTER:-0}" == "1" ]] || rm -rf "$LAB"
}
trap 'limpar; [[ ${#FALHAS[@]} -eq 0 ]] || exit 1' EXIT

# --- pré-requisitos ---------------------------------------------------------
for requisito in docker git; do
    command -v "$requisito" >/dev/null 2>&1 || {
        printf 'este teste precisa de %s no PATH\n' "$requisito" >&2
        exit 127
    }
done
docker compose version >/dev/null 2>&1 || {
    printf 'este teste precisa do plugin docker compose v2\n' >&2
    exit 127
}

# =============================================================================
log "0. LABORATÓRIO — o mesmo caminho que a VPS percorre no deploy"
# =============================================================================
# `deploy.yml:204-260` faz `git clone` e `git reset --hard`: não há cópia de
# arquivo por arquivo. O que chega na VPS é o que está no índice do git. O
# laboratório reproduz esse caminho — é por isso que o teste de modo abaixo
# mede a coisa certa e não um `chmod` local.
limpar
mkdir -p "$LAB" "$BIN"
git clone -q "$REPO" "$DEPLOY"
git -C "$DEPLOY" checkout -q "$(git -C "$REPO" rev-parse --abbrev-ref HEAD)"
mkdir -p "$BACKUPS" "$DEPLOY/backend"

# O `docker-compose.yml` real constrói a imagem Django de ./backend e roda
# migrations no entrypoint do serviço `web`. Nada disso é o que o backup
# exercita: o script só pede `pg_dump` ao serviço `db` e `tar -C /app/media`
# ao serviço `web`. O fixture abaixo reproduz exatamente esse contrato — mesmo
# nome de serviço, mesma imagem do Postgres, mesmo volume de mídia em
# /app/media — para que o teste não dependa de um build de 65 pacotes.
cat > "$COMPOSE_ARQUIVO" <<'YAML'
services:
  db:
    image: postgres:16-alpine
    restart: unless-stopped
    environment:
      POSTGRES_DB: ${DJANGO_DB_NAME:-brd_portal_noticias}
      POSTGRES_USER: ${DJANGO_DB_USER:-postgres}
      POSTGRES_PASSWORD: ${DJANGO_DB_PASSWORD:?defina DJANGO_DB_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${DJANGO_DB_USER:-postgres}"]
      interval: 2s
      timeout: 5s
      retries: 30
  web:
    image: alpine:3
    command: ["sleep", "3600"]
    volumes:
      - media_data:/app/media
volumes:
  postgres_data:
  media_data:
YAML

# O arquivo de ambiente que o `deploy.yml:267-288` cria. NÃO é
# `.env.production`: essa é justamente a quebra 2.
cat > "$ENV_ARQUIVO" <<'ENV'
DJANGO_SECRET_KEY=chave-de-teste-nao-e-segredo
DJANGO_DEBUG=false
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1
DJANGO_DB_ENGINE=postgresql
DJANGO_DB_NAME=brd_portal_noticias
DJANGO_DB_USER=portal_app
DJANGO_DB_PASSWORD=senha-de-teste-do-lab
DJANGO_DB_HOST=localhost
DJANGO_DB_PORT=5432
FRONTEND_BASE_URL=http://localhost
BACKUP_S3_ENDPOINT=
BACKUP_S3_BUCKET=
BACKUP_S3_ACCESS_KEY=
BACKUP_S3_SECRET_KEY=
ENV
chmod 600 "$ENV_ARQUIVO"

cd "$DEPLOY" || exit 1
docker compose -f "$COMPOSE_ARQUIVO" --env-file "$ENV_ARQUIVO" up -d --wait >/dev/null 2>&1 || {
    echo "não foi possível subir o Postgres de teste" >&2
    exit 1
}

compose() { docker compose -f "$COMPOSE_ARQUIVO" --env-file "$ENV_ARQUIVO" "$@"; }
psql_q() { compose exec -T db psql -U portal_app -d brd_portal_noticias -qAt -c "$1" < /dev/null; }

printf '  projeto compose: %s   deploy: %s\n' "$PROJETO" "$DEPLOY"

# =============================================================================
log "1. O BANCO DE TESTE — mesmo volume de dados medido em PROD"
# =============================================================================
compose exec -T db psql -U portal_app -d brd_portal_noticias -v ON_ERROR_STOP=1 -q <<'SQL' >/dev/null
CREATE TABLE django_migrations (
    id serial PRIMARY KEY, app varchar(100) NOT NULL, name varchar(100) NOT NULL, applied timestamptz NOT NULL);
CREATE TABLE config_usuario (
    id serial PRIMARY KEY, username varchar(150) UNIQUE NOT NULL, email varchar(254) NOT NULL,
    is_staff boolean NOT NULL DEFAULT false);
CREATE TABLE feed_fonte (id serial PRIMARY KEY, nome varchar(200) NOT NULL, url text NOT NULL);
CREATE TABLE noticias_noticia (
    id serial PRIMARY KEY, titulo text NOT NULL, slug varchar(200) NOT NULL, corpo text NOT NULL,
    url_origem text NOT NULL, publicada_em timestamptz NOT NULL, ativo boolean NOT NULL DEFAULT true);
INSERT INTO config_usuario (username, email, is_staff) VALUES
    ('admin','admin@exemplo.test',true), ('redacao','redacao@exemplo.test',false);
INSERT INTO django_migrations (app, name, applied)
SELECT 'noticias', 'migra_'||g, now() - (g||' days')::interval FROM generate_series(1,82) g;
INSERT INTO feed_fonte (nome, url) SELECT 'Fonte '||g, 'https://exemplo.test/'||g FROM generate_series(1,10) g;
INSERT INTO noticias_noticia (titulo, slug, corpo, url_origem, publicada_em, ativo)
SELECT 'Notícia número '||g, 'noticia-'||g, repeat('paragrafo de conteudo de teste de noticia ', 100),
       'https://exemplo.test/noticia/'||g, now() - (g||' minutes')::interval, (g % 7) <> 0
FROM generate_series(1,4156) g;
CREATE INDEX ix_noticias_ativa ON noticias_noticia (ativo);
CREATE INDEX ix_noticias_publicada ON noticias_noticia (publicada_em DESC);
CREATE INDEX ix_noticias_slug ON noticias_noticia (slug);
SQL
for i in 1 2 3; do
    head -c 2048 /dev/urandom | base64 > "$LAB/midia-$i.txt"
    compose cp "$LAB/midia-$i.txt" "web:/app/media/foto-$i.jpg" >/dev/null 2>&1
    rm -f "$LAB/midia-$i.txt"
done
printf '  origem: %s\n' "$(psql_q "select 'noticias='||(select count(*) from noticias_noticia)||' usuarios='||(select count(*) from config_usuario)||' migrations='||(select count(*) from django_migrations)||' indices='||(select count(*) from pg_indexes where schemaname='public')")"

# Banco para o cenário do backup vazio: as tabelas existem e NÃO há uma linha
# em nenhuma. É a forma exata do dump de 48 KB que ficou em produção — um dump
# estruturalmente perfeito que não restaura nada.
compose exec -T db dropdb -U portal_app --if-exists banco_vazio >/dev/null 2>&1
compose exec -T db createdb -U portal_app -T template0 banco_vazio >/dev/null 2>&1
compose exec -T db psql -U portal_app -d banco_vazio -q -c \
    "create table django_migrations(id serial primary key, app varchar(100) not null, name varchar(100) not null, applied timestamptz not null);" \
    >/dev/null 2>&1

# Roda o script como o cron roda: pelo caminho, com o shell do cron.
rodar() {  # rodar <saida-em> <atribuições-de-ambiente...>  -> exit no retorno
    local saida ec
    shift  # o primeiro argumento é o nome da variável, não uma atribuição
    saida="$(env "$@" /bin/sh -c "$DEPLOY/infra/backup/pg_backup.sh" 2>&1)"; ec=$?
    SAIDA="$saida"
    return $ec
}

# =============================================================================
log "2. QUEBRA 1 — bit de execução versionado"
# =============================================================================
# O modo que o cron encontra é o do índice. Um `chmod +x` na VPS não é
# versionado e o próximo `git reset --hard` o desfaz (medido: 755 -> 664).
MODO_INDICE="$(git -C "$DEPLOY" ls-tree HEAD infra/backup/pg_backup.sh | cut -d' ' -f1)"
[[ "$MODO_INDICE" == "100755" ]] && passou "índice do git declara 100755" "$MODO_INDICE" "o deploy entrega um arquivo executável" \
    || falhou "índice do git declara 100755" 0 "$MODO_INDICE" "o deploy entrega um arquivo não-executável"

MODO_CLOADO="$(stat -c '%a' "$DEPLOY/infra/backup/pg_backup.sh")"
if [[ -x "$DEPLOY/infra/backup/pg_backup.sh" ]]; then
    passou "arquivo recém-clonado é executável" "$MODO_CLOADO" "sobrevive ao clone (= o deploy)"
else
    falhou "arquivo recém-clonado é executável" "executável" "$MODO_CLOADO" "o cron levaria Permission denied"
fi

# DISCRIMINANTE: o mesmo comando, com o arquivo em 644 (o estado do índice
# antes da correção) tem de dar Permission denied — é o erro de produção.
chmod 644 "$DEPLOY/infra/backup/pg_backup.sh"
SAIDA_644="$(/bin/sh -c "$DEPLOY/infra/backup/pg_backup.sh" 2>&1)"; EC_644=$?
if (( EC_644 == 126 )) && grep -q 'Permission denied' <<<"$SAIDA_644"; then
    passou "reverter a correção 1 (644) reproduz o erro do cron" "$EC_644" "Permission denied"
else
    falhou "reverter a correção 1 (644) reproduz o erro do cron" "126/Permission denied" "$EC_644" "${SAIDA_644:0:60}"
fi
chmod 755 "$DEPLOY/infra/backup/pg_backup.sh"

# =============================================================================
log "3. QUEBRA 2 — o arquivo de ambiente que o deploy realmente cria"
# =============================================================================
if rodar SAIDA COMPOSE_PROJECT_NAME="$PROJETO" BACKUP_DIR="$BACKUPS" >/dev/null 2>&1; then
    passou "sem BACKUP_ENV_FILE, acha backend/.env e roda" 0 "${SAIDA##*$'\n'}"
else
    falhou "sem BACKUP_ENV_FILE, acha backend/.env e roda" 0 "$?" "${SAIDA##*$'\n'}"
fi
grep -q "carregando o ambiente de .*backend/.env" <<<"$SAIDA" \
    && passou "o log diz qual arquivo de ambiente foi lido" 0 "backend/.env" \
    || falhou "o log diz qual arquivo de ambiente foi lido" 0 "?" "o log não nomeia o arquivo"

# DISCRIMINANTE: apontar para o caminho antigo reproduz a quebra 2 original.
if rodar SAIDA COMPOSE_PROJECT_NAME="$PROJETO" BACKUP_DIR="$BACKUPS" \
        BACKUP_ENV_FILE="$DEPLOY/.env.production" >/dev/null 2>&1; then
    falhou "reverter a correção 2 (.env.production) aborta" 1 0 "o script achou o arquivo errado"
else
    EC_ANTIGO=$?
    [[ "$EC_ANTIGO" == "1" ]] \
        && passou "reverter a correção 2 (.env.production) aborta" "$EC_ANTIGO" "${SAIDA##*$'\n'}" \
        || falhou "reverter a correção 2 (.env.production) aborta" 1 "$EC_ANTIGO" "$SAIDA"
fi

# =============================================================================
log "4. QUEBRA 3 — o dump não pode morar dentro da árvore do git"
# =============================================================================
DUMP_CORRIGIDO="$(ls -1t "$BACKUPS"/db-*.dump 2>/dev/null | head -1)"
[[ -n "$DUMP_CORRIGIDO" ]] \
    && passou "BACKUP_DIR padrão/publicado fora do checkout" 0 "$DUMP_CORRIGIDO" \
    || falhou "BACKUP_DIR padrão/publicado fora do checkout" "1 dump" "-" "nenhum dump em $BACKUPS"
if find "$DEPLOY" -name '*.dump' -print -quit 2>/dev/null | grep -q .; then
    falhou "nenhum dump dentro da árvore do repositório" 0 "achado" "$(find "$DEPLOY" -name '*.dump' | head -1)"
else
    passou "nenhum dump dentro da árvore do repositório" 0 "árvore limpa"
fi

# DISCRIMINANTE: o destino antigo era `BACKUP_DIR="$PROJECT_DIR/infra/backup"`
# — o diretório onde ESTE script mora. O teste escreve ali de propósito (é o
# que a versão anterior fazia) e só remove os artefatos depois; apagar o
# diretório inteiro derrubaria o próprio laboratório.
DESTINO_ANTIGO="$DEPLOY/infra/backup"
limpar_artefatos_antigos() {
    rm -f "$DESTINO_ANTIGO"/db-*.dump "$DESTINO_ANTIGO"/media-*.tar.gz \
          "$DESTINO_ANTIGO"/.db-* "$DESTINO_ANTIGO"/.media-* 2>/dev/null
}
limpar_artefatos_antigos
if rodar SAIDA COMPOSE_PROJECT_NAME="$PROJETO" BACKUP_DIR="$DESTINO_ANTIGO" >/dev/null 2>&1; then
    EC_ANTIGO3=0
else
    EC_ANTIGO3=$?
fi
if ls -1 "$DESTINO_ANTIGO"/db-*.dump >/dev/null 2>&1; then
    passou "reverter a correção 3 volta a gravar no checkout" "$EC_ANTIGO3" "$(ls -1 "$DESTINO_ANTIGO"/db-*.dump | head -1)"
else
    falhou "reverter a correção 3 volta a gravar no checkout" 0 "-" "não gravou um dump em infra/backup"
fi
# E o pior efeito: lá dentro, o dump some do `git status` — é coberto pelo
# .gitignore (linhas 7-8) e ninguém o vê, nem por engano.
if git -C "$DEPLOY" status --short --untracked-files=all -- "$DESTINO_ANTIGO" | grep -q .; then
    falhou "o dump dentro do checkout NÃO aparece no git status" 0 "aparece" "não devia aparecer (é ignorado)"
else
    passou "o dump dentro do checkout NÃO aparece no git status" 0 "invisível — o silêncio de origem"
fi
limpar_artefatos_antigos

# =============================================================================
log "5. EXECUÇÃO REAL — o backup roda e produz um dump de verdade"
# =============================================================================
rm -f "$BACKUPS"/db-*.dump "$BACKUPS"/media-*.tar.gz
rodar SAIDA COMPOSE_PROJECT_NAME="$PROJETO" BACKUP_DIR="$BACKUPS" >/dev/null 2>&1
EC_RUN=$?
[[ "$EC_RUN" == "0" ]] && passou "execução completa" "$EC_RUN" "$(grep -o 'OK dump=.*' <<<"$SAIDA" | head -1)" \
    || falhou "execução completa" 0 "$EC_RUN" "${SAIDA##*$'\n'}"
DUMP="$(ls -1t "$BACKUPS"/db-*.dump 2>/dev/null | head -1)"
TAM="$(stat -c '%s' "$DUMP" 2>/dev/null || echo 0)"
# Comparação RELATIVA, e não um número mágico: o mesmo cluster, o mesmo
# pg_dump, duas vezes — uma no banco com 4156 notícias e outra no banco com
# as tabelas criadas e zero linhas. É essa razão que distingue "backup de
# verdade" de "backup de 48 KB", e ela não depende do tamanho do texto de
# teste. (O dump de produção mede 48 KB vazio contra 4.599.328 bytes real.)
TAM_VAZIO="$(compose exec -T db pg_dump -U portal_app -Fc --no-password -d banco_vazio 2>/dev/null < /dev/null | wc -c)"
if (( TAM > 3 * TAM_VAZIO )); then
    passou "o dump com dados é muito maior que o dump do banco vazio" "$TAM" "${TAM_VAZIO} bytes vazio no mesmo cluster"
else
    falhou "o dump com dados é muito maior que o dump do banco vazio" ">3x$TAM_VAZIO" "$TAM" "não distinguiu do banco vazio"
fi
grep -q 'contagem da origem: 4|4250' <<<"$SAIDA" \
    && passou "contagem de tabelas e linhas na origem" 0 "4|4250" \
    || falhou "contagem de tabelas e linhas na origem" 0 "4|4250" "$(grep 'contagem da origem' <<<"$SAIDA")"
grep -q 'restore validado: 4|4250' <<<"$SAIDA" \
    && passou "o próprio script validou o restore antes de publicar" 0 "4|4250" \
    || falhou "o próprio script validou o restore antes de publicar" 0 "4|4250" "(sem validação)"

# =============================================================================
log "6. RESTAURAÇÃO INDEPENDENTE — fora do script, num banco novo"
# =============================================================================
# O script dizer que restaurou não é a prova. A prova é restaurar o ARQUIVO,
# com o pg_restore, num banco criado do zero, e comparar.
compose exec -T db dropdb -U portal_app --if-exists restore_prova >/dev/null 2>&1
compose exec -T db createdb -U portal_app -T template0 restore_prova >/dev/null 2>&1
if compose exec -T db pg_restore -U portal_app --exit-on-error --no-owner --no-privileges \
        -d restore_prova < "$DUMP" >/dev/null 2>&1; then
    passou "pg_restore do dump num banco inexistente" 0 "$(( $(stat -c '%s' "$DUMP") )) bytes restaurados"
else
    falhou "pg_restore do dump num banco inexistente" 0 "$?" "pg_restore falhou"
fi
for tabela in config_usuario django_migrations feed_fonte noticias_noticia; do
    A="$(psql_q "SELECT count(*) FROM $tabela;")"
    B="$(compose exec -T db psql -U portal_app -d restore_prova -qAt -c "SELECT count(*) FROM $tabela;" < /dev/null)"
    [[ -n "$A" && "$A" == "$B" ]] && passou "linhas em $tabela" "$B" "origem=$A" \
        || falhou "linhas em $tabela" "$A" "$B" "divergência"
done
A="$(psql_q "SELECT count(*) FROM pg_indexes WHERE schemaname='public';")"
B="$(compose exec -T db psql -U portal_app -d restore_prova -qAt -c "SELECT count(*) FROM pg_indexes WHERE schemaname='public';" < /dev/null)"
[[ "$A" == "$B" ]] && passou "índices reconstruídos" "$B" "origem=$A" || falhou "índices reconstruídos" "$A" "$B" "divergência"
A="$(psql_q "SELECT count(*) FROM pg_constraint WHERE connamespace='public'::regnamespace;")"
B="$(compose exec -T db psql -U portal_app -d restore_prova -qAt -c "SELECT count(*) FROM pg_constraint WHERE connamespace='public'::regnamespace;" < /dev/null)"
[[ "$A" == "$B" ]] && passou "constraints preservadas" "$B" "origem=$A" || falhou "constraints preservadas" "$A" "$B" "divergência"
if tar -tzf "$(ls -1t "$BACKUPS"/media-*.tar.gz | head -1)" 2>/dev/null | grep -q 'foto-1.jpg'; then
    passou "o tar da mídia é legível e tem o conteúdo" 0 "foto-1.jpg presente"
else
    falhou "o tar da mídia é legível e tem o conteúdo" 0 "vazio/corrompido" "tar -tzf"
fi

# =============================================================================
log "7. O BACKUP VAZIO — o dump de 48 KB que passou em produção"
# =============================================================================
# Um banco com as tabelas criadas e zero linhas produz um dump PERFEITAMENTE
# VÁLIDO: `pg_restore --list` aprova, `pg_restore` aprova, e o backup não
# restaura nada. A única barreira é contar linhas.
cp "$ENV_ARQUIVO" "$LAB/env.bak"
printf 'DJANGO_DB_NAME=banco_vazio\n' >> "$ENV_ARQUIVO"
if rodar SAIDA COMPOSE_PROJECT_NAME="$PROJETO" BACKUP_DIR="$BACKUPS" >/dev/null 2>&1; then
    EC_VAZIO=0
else
    EC_VAZIO=$?
fi
[[ "$EC_VAZIO" == "7" ]] && passou "banco com 0 linhas é recusado (exit 7)" "$EC_VAZIO" "dump de banco vazio não é publicado" \
    || falhou "banco com 0 linhas é recusado (exit 7)" 7 "$EC_VAZIO" "$SAIDA"
DUMP_VAZIO_NOVO="$(ls -1t "$BACKUPS"/db-*.dump | head -1)"
[[ "$DUMP_VAZIO_NOVO" == "$DUMP" ]] \
    && passou "nenhum arquivo foi publicado na recusa" 0 "o dump válido anterior continua intocado" \
    || falhou "nenhum arquivo foi publicado na recusa" "$DUMP" "$DUMP_VAZIO_NOVO" "sobrescreveu"
cp "$LAB/env.bak" "$ENV_ARQUIVO"; rm -f "$LAB/env.bak"

# =============================================================================
log "8. MATRIZ DE FALHAS — nenhum backup falha calado"
# =============================================================================
espera_exit() {  # espera_exit <nome> <exit-esperado> <trecho-esperado> <env...>
    local nome="$1" esperado="$2" trecho="$3"; shift 3
    if rodar SAIDA "$@" >/dev/null 2>&1; then ec=0; else ec=$?; fi
    if [[ "$ec" == "$esperado" ]] && grep -qF "$trecho" <<<"$SAIDA"; then
        passou "$nome" "$ec" "$trecho"
    else
        falhou "$nome" "$esperado" "$ec" "$(grep -m1 'ERRO\|FALHA' <<<"$SAIDA")"
    fi
}
espera_exit "env file apontado que não existe -> 1" 1 "BACKUP_ENV_FILE não existe" \
    COMPOSE_PROJECT_NAME="$PROJETO" BACKUP_DIR="$BACKUPS" BACKUP_ENV_FILE=/nao/existe/.env
espera_exit "destino não gravável -> 1 com o comando de correção" 1 "sudo install -d" \
    COMPOSE_PROJECT_NAME="$PROJETO" BACKUP_DIR=/proc/nao/posso/escrever
espera_exit "S3 parcial (chave sem bucket) -> 1" 1 "configuração S3 parcial" \
    COMPOSE_PROJECT_NAME="$PROJETO" BACKUP_DIR="$BACKUPS" \
    BACKUP_S3_ENDPOINT=https://exemplo.invalid BACKUP_S3_ACCESS_KEY=k
espera_exit "BACKUP_REQUIRE_REMOTE=1 sem bucket -> 1" 1 "SÓ nesta VPS" \
    COMPOSE_PROJECT_NAME="$PROJETO" BACKUP_DIR="$BACKUPS" BACKUP_REQUIRE_REMOTE=1
espera_exit "BACKUP_MIN_LINHAS não numérico -> 1" 1 "BACKUP_MIN_LINHAS deve ser um inteiro" \
    COMPOSE_PROJECT_NAME="$PROJETO" BACKUP_DIR="$BACKUPS" BACKUP_MIN_LINHAS=dez

# Topologia incompatível: o serviço `web` realmente parado. É o estado de uma
# VPS PM2 chamando o script da variante Docker, e é a falha que a correção
# transforma em diagnóstico em vez de `pg_dump: command not found` enterrado.
compose stop web >/dev/null 2>&1
if rodar SAIDA COMPOSE_PROJECT_NAME="$PROJETO" BACKUP_DIR="$BACKUPS" >/dev/null 2>&1; then ec=0; else ec=$?; fi
compose start web >/dev/null 2>&1
[[ "$ec" == "3" ]] && grep -qF "pg_backup_pm2.sh" <<<"$SAIDA" \
    && passou "serviço web fora do ar -> 3 e aponta pg_backup_pm2.sh" "$ec" "topologia diagnosticada" \
    || falhou "serviço web fora do ar -> 3 e aponta pg_backup_pm2.sh" 3 "$ec" "$(grep -m1 'ERRO' <<<"$SAIDA")"

# Valor sem aspas com espaço: `source` (que o deploy.yml também usa) trunca o
# valor e o Django não — o backup passaria a responder por outro banco.
cp "$ENV_ARQUIVO" "$LAB/env.bak"
printf 'FRONTEND_BASE_URL=http://exemplo.test com espaco\n' >> "$ENV_ARQUIVO"
if rodar SAIDA COMPOSE_PROJECT_NAME="$PROJETO" BACKUP_DIR="$BACKUPS" >/dev/null 2>&1; then ec=0; else ec=$?; fi
cp "$LAB/env.bak" "$ENV_ARQUIVO"; rm -f "$LAB/env.bak"
[[ "$ec" == "1" ]] && grep -qF "coloque o valor entre aspas" <<<"$SAIDA" \
    && passou "valor sem aspas com espaço no env file -> 1" "$ec" "divergência source/Django barrada" \
    || falhou "valor sem aspas com espaço no env file -> 1" 1 "$ec" "$(grep -m1 'ERRO' <<<"$SAIDA")"

# =============================================================================
log "9. STORAGE REMOTO — chamado certo, e falha de upload não apaga nada"
# =============================================================================
# Stub de `aws`: grava cada chamada e responde ao `head-object` com o tamanho
# que o `aws s3 cp` acabou de "gravar". `AWS_STUB_CP_FALHA` faz o `cp` falhar;
# `AWS_STUB_HEAD_FALHA` faz o `head-object` falhar; `AWS_STUB_HEAD_SIZE`
# devolve um tamanho mentiroso (upload truncado).
cat > "$BIN/aws" <<'STUB'
#!/usr/bin/env bash
set -uo pipefail
REGISTRO="${AWS_STUB_REGISTRO:-/dev/null}"
printf '%s\n' "$*" >> "$REGISTRO"
# O script monta a chamada como `aws --endpoint-url <ep> s3 cp ...`: as
# opções GLOBAIS vêm ANTES do subcomando. Um stub que lê só $1 e $2 enxerga
# `--endpoint-url` e nunca encontra o `cp` — foi exatamente o que aconteceu
# na primeira versão deste teste, e o sintoma (head-object "não existe")
# parecia um defeito do script de backup, não do stub.
pos=()
pular=0
for a in "$@"; do
    if (( pular == 1 )); then pular=0; continue; fi
    case "$a" in
        --endpoint-url) pular=1 ;;
        --*) ;;
        *) pos+=("$a") ;;
    esac
done
subcomando="${pos[0]:-}"; acao="${pos[1]:-}"
if [[ "$subcomando" == "s3" && "$acao" == "cp" ]]; then
    if [[ -n "${AWS_STUB_CP_FALHA:-}" ]]; then
        echo "stub: upload falhou" >&2
        exit 1
    fi
    origem="${pos[2]:-}"; destino="${pos[3]:-}"
    chave="${destino#s3://}"; chave="${chave#*/}"
    mkdir -p "${AWS_STUB_OBJETOS:?}/$(dirname "$chave")" 2>/dev/null
    cp "$origem" "${AWS_STUB_OBJETOS}/${chave}"
    exit 0
fi
if [[ "$subcomando" == "s3api" && "$acao" == "head-object" ]]; then
    if [[ -n "${AWS_STUB_HEAD_FALHA:-}" ]]; then
        echo "stub: head-object falhou" >&2
        exit 254
    fi
    if [[ -n "${AWS_STUB_HEAD_SIZE:-}" ]]; then printf '%s\n' "$AWS_STUB_HEAD_SIZE"; exit 0; fi
    chave=""; anterior=""
    for a in "$@"; do [[ "$anterior" == "--key" ]] && chave="$a"; anterior="$a"; done
    arquivo="${AWS_STUB_OBJETOS:?}/$chave"
    [[ -f "$arquivo" ]] || { echo "stub: NoSuchKey $chave" >&2; exit 254; }
    stat -c '%s' "$arquivo"
    exit 0
fi
exit 0
STUB
chmod +x "$BIN/aws"

OBJETOS="$LAB/objetos"; rm -rf "$OBJETOS"; mkdir -p "$OBJETOS"
REGISTRO="$LAB/aws-registro.txt"; : > "$REGISTRO"
R2="COMPOSE_PROJECT_NAME=$PROJETO BACKUP_DIR=$BACKUPS AWS_STUB_OBJETOS=$OBJETOS AWS_STUB_REGISTRO=$REGISTRO
    BACKUP_S3_ENDPOINT=https://conta-id.r2.cloudflarestorage.com
    BACKUP_S3_BUCKET=portal-backups BACKUP_S3_ACCESS_KEY=chave BACKUP_S3_SECRET_KEY=segredo
    PATH=$BIN:/usr/bin:/bin"

espera_exit "upload completo e verificado -> 0" 0 "objetos verificados por head-object" $R2
DUMP_REMOVIDO="$(ls -1t "$BACKUPS"/db-*.dump | head -1)"
grep -qF -- "--endpoint-url https://conta-id.r2.cloudflarestorage.com" "$REGISTRO" \
    && grep -qF -- "s3 cp $DUMP_REMOVIDO s3://portal-backups/db/$(basename "$DUMP_REMOVIDO")" "$REGISTRO" \
    && passou "a chamada de upload usa --endpoint-url e a chave db/<arquivo>" 0 "conferido no registro" \
    || falhou "a chamada de upload usa --endpoint-url e a chave db/<arquivo>" 0 "?" "$(tail -3 "$REGISTRO")"
[[ "$(stat -c '%s' "$OBJETOS/db/$(basename "$DUMP_REMOVIDO")")" == "$(stat -c '%s' "$DUMP_REMOVIDO")" ]] \
    && passou "o objeto remoto tem exatamente o tamanho do local" 0 "$(stat -c '%s' "$DUMP_REMOVIDO")" \
    || falhou "o objeto remoto tem exatamente o tamanho do local" 0 "?" "tamanho divergente"
[[ -f "$OBJETOS/media/$(basename "$(ls -1t "$BACKUPS"/media-*.tar.gz | head -1)")" ]] \
    && passou "a mídia também foi enviada" 0 "prefixo media/" \
    || falhou "a mídia também foi enviada" 0 "?" "sem objeto em media/"

# DISCRIMINANTE / GARANTIA: upload falhado não pode apagar o backup local.
QUANTIDADE_ANTES="$(ls -1 "$BACKUPS" | wc -l)"
TAM_ANTES="$(stat -c '%s' "$(ls -1t "$BACKUPS"/db-*.dump | head -1)")"
espera_exit "upload do dump falhando -> 10" 10 "NENHUM backup local foi removido" $R2 AWS_STUB_CP_FALHA=1
[[ -f "$(ls -1t "$BACKUPS"/db-*.dump | head -1)" && "$(stat -c '%s' "$(ls -1t "$BACKUPS"/db-*.dump|head -1)")" == "$TAM_ANTES" \
   && "$(ls -1 "$BACKUPS" | wc -l)" -gt "$QUANTIDADE_ANTES" ]] \
    && passou "depois do upload falhado, o dump local está intacto" 0 "$TAM_ANTES bytes, nada apagado" \
    || falhou "depois do upload falhado, o dump local está intacto" 0 "$TAM_ANTES" "o local mudou"

espera_exit "head-object mentindo (upload truncado) -> 12" 12 "NENHUM backup local foi removido" $R2 AWS_STUB_HEAD_SIZE=999999
[[ -f "$(ls -1t "$BACKUPS"/db-*.dump | head -1)" ]] \
    && passou "depois do head-object divergente, o local continua" 0 "intacto" \
    || falhou "depois do head-object divergente, o local continua" 0 "sumiu" "o local foi apagado"
espera_exit "head-object falhando (credencial/DNS) -> 12" 12 "NENHUM backup local foi removido" $R2 AWS_STUB_HEAD_FALHA=1

# =============================================================================
log "10. O CANAL EXTERNO — heartbeat no sucesso, webhook na falha, ping nunca na falha"
# =============================================================================
cat > "$BIN/curl" <<'STUB'
#!/usr/bin/env bash
set -uo pipefail
REGISTRO="${CURL_STUB_REGISTRO:-/dev/null}"
metodo=""; url=""; anterior=""
for a in "$@"; do
    case "$anterior" in
        --data) metodo="POST $a" ;;
    esac
    case "$a" in http*) url="$a" ;; esac
    anterior="$a"
done
printf '%s %s\n' "$metodo" "$url" >> "$REGISTRO"
if [[ -n "${CURL_STUB_FALHAR:-}" ]]; then echo "stub: curl falhou" >&2; exit 22; fi
printf 'ok'
STUB
chmod +x "$BIN/curl"
LOG_CANAL="$LAB/canal.txt"; : > "$LOG_CANAL"
CANAL="CURL_STUB_REGISTRO=$LOG_CANAL PATH=$BIN:/usr/bin:/bin"

espera_exit "sucesso com heartbeat -> 0" 0 "heartbeat confirmado" $R2 $CANAL \
    BACKUP_HEARTBEAT_URL=https://uptime.exemplo.test/heartbeat/backup
grep -q 'https://uptime.exemplo.test/heartbeat/backup' <<<"$(cat "$LOG_CANAL"; )" \
    && passou "o canal externo recebeu o ping no sucesso" 0 "1 GET" \
    || falhou "o canal externo recebeu o ping no sucesso" 0 "0" "nenhum ping"

: > "$LOG_CANAL"
espera_exit "sucesso com canal quebrado -> 13" 13 "backup está íntegro, mas o heartbeat" $R2 $CANAL \
    BACKUP_HEARTBEAT_URL=https://uptime.exemplo.test/heartbeat/backup CURL_STUB_FALHAR=1

: > "$LOG_CANAL"
espera_exit "falha de upload notifica o webhook -> 10" 10 "FALHA (exit 10)" $R2 $CANAL \
    BACKUP_HEARTBEAT_URL=https://uptime.exemplo.test/heartbeat/backup \
    BACKUP_ALERT_WEBHOOK_URL=https://alerta.exemplo.test/backup \
    AWS_STUB_CP_FALHA=1
grep -q 'https://alerta.exemplo.test/backup' <<<"$(cat "$LOG_CANAL")" \
    && passou "a falha chegou ao webhook" 0 "1 POST" \
    || falhou "a falha chegou ao webhook" 0 "0" "o webhook não foi chamado"
grep -q 'heartbeat/backup' <<<"$(cat "$LOG_CANAL")" \
    && falhou "NENHUM ping de heartbeat quando o backup falha" 0 "ping" "o script declarou um backup que não houve" \
    || passou "NENHUM ping de heartbeat quando o backup falha" 0 "ausência de ping = o alerta externo dispara"

# =============================================================================
log "11. RETENÇÃO — some o que é velho, e só depois do upload verificado"
# =============================================================================
ANTIGO="$BACKUPS/db-20000101T000000Z.dump"
printf 'dump-antigo' > "$ANTIGO"; touch -d "-30 days" "$ANTIGO"
ANTIGO_M="$BACKUPS/media-20000101T000000Z.tar.gz"
printf 'midia-antiga' > "$ANTIGO_M"; touch -d "-30 days" "$ANTIGO_M"
# um dump recente NÃO pode ser apagado
if rodar SAIDA $R2 $CANAL >/dev/null 2>&1; then ec=0; else ec=$?; fi
[[ ! -f "$ANTIGO" && ! -f "$ANTIGO_M" ]] \
    && passou "backup de 30 dias foi removido" 0 "retenção de 7 dias aplicada" \
    || falhou "backup de 30 dias foi removido" 0 "ainda existe" "retenção não agiu"
# o arquivo de outro script que mora no mesmo diretório não é tocado
PM2="$BACKUPS/pm2-db-20000101T000000Z.dump"; printf 'pm2' > "$PM2"; touch -d "-30 days" "$PM2"
if rodar SAIDA $R2 $CANAL >/dev/null 2>&1; then ec=0; else ec=$?; fi
[[ -f "$PM2" ]] && passou "a retenção não toca nos arquivos pm2-* do script irmão" 0 "intacto" \
    || falhou "a retenção não toca nos arquivos pm2-* do script irmão" 0 "apagou" "escopo de nome ausente"
rm -f "$PM2"

# =============================================================================
log "12. O QUE ESTE TESTE NÃO PROVA"
# =============================================================================
cat <<'TXT'
  * A VPS de produção roda PM2, sem Docker Compose (infra/DEPLOY.md:10-12).
    Este script é da variante Docker/Caddy: na VPS ele agora falha com o
    código 3 e diz para usar infra/backup/pg_backup_pm2.sh. O script correto
    para a topologia ativa tem prova própria, fora deste arquivo.
  * O destino remoto aqui é um STUB de `aws`. A prova de que `aws s3 cp
    --endpoint-url` funciona contra uma API S3 de verdade foi feita com a AWS
    CLI real e um servidor S3 local, e é relatada no relatório da mudança.
  * Nenhuma credencial real é usada, e nada aqui fala com a internet.
TXT

# =============================================================================
log "VEREDITO"
# =============================================================================
printf '  %d de %d verificações com o resultado esperado\n' "$ACERTOS" "$TOTAL"
if (( ${#FALHAS[@]} > 0 )); then
    printf '  FALHARAM:\n'
    for f in "${FALHAS[@]}"; do printf '    - %s\n' "$f"; done
    exit 1
fi
printf '  TODAS as verificações passaram, incluindo as três que quebram a\n'
printf '  correção de propósito. Um teste que passasse nos dois lados não\n'
printf '  provaria nada.\n'
