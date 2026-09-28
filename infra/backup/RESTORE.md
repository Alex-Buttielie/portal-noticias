# Runbook de restore

Backup sem teste de restore não é backup — é uma esperança. Rode este
procedimento pelo menos uma vez após o primeiro deploy (num ambiente de
staging ou numa cópia local) para confirmar que ele realmente funciona
antes de precisar dele de verdade.

## Restaurar o banco de dados

```bash
# 0. Rode a partir da raiz do projeto (onde está o docker-compose.yml) e
#    carregue as variáveis de .env.production no shell atual — os comandos
#    abaixo dependem de $DJANGO_DB_USER/$DJANGO_DB_NAME já estarem
#    definidos, e sem este passo eles ficam vazios silenciosamente.
set -a; source .env.production; set +a

# 1. Copie o .dump desejado para um caminho QUALQUER. O dump da variante
#    Docker/Caddy fica em /var/backups/portal/<diretório-do-deploy>/ por padrão
#    (fora da árvore do git); baixe do bucket com o comando da seção "Baixar
#    backup do storage remoto" abaixo. A localização mudou de propósito: dentro
#    do checkout o dump era apagado por `git reset --hard` e, por estar no
#    .gitignore, nem aparecia no `git status`.
#    Exemplo: cp /var/backups/portal/brd_portal_noticias/db-<UTC>.dump /tmp/restore.dump

# 2. Suba só o serviço de banco, se ainda não estiver rodando
docker compose --env-file .env.production up -d db

# 3. Restaura para dentro do container (recria o banco do zero — ATENÇÃO:
#    isto apaga o conteúdo atual do banco de destino)
cat infra/backup/restore.dump | docker compose --env-file .env.production \
    exec -T db pg_restore -U "$DJANGO_DB_USER" -d "$DJANGO_DB_NAME" \
    --clean --if-exists --no-owner

# 4. Confirme que o restore trouxe dados reais antes de considerar
#    concluído — não assuma sucesso só porque pg_restore não imprimiu erro.
#    Uma tabela com estrutura e ZERO linhas é exatamente a forma do backup de
#    48 KB que ficou semanas em produção: o restore "funciona" e não devolve
#    nada. Compare os números com os de origem, não apenas com zero.
docker compose --env-file .env.production exec -T db \
    psql -U "$DJANGO_DB_USER" -d "$DJANGO_DB_NAME" \
    -c "select count(*) from django_migrations;" \
    -c "select relname, n_live_tup from pg_stat_user_tables order by relname;" \
    -c "select count(*) from pg_indexes where schemaname='public';"

# 5. Suba o resto da stack
docker compose --env-file .env.production up -d

# 6. Rode as migrações pendentes (o dump pode ser de uma versão do schema
#    anterior ao código que está sendo restaurado) e confira a aplicação:
docker compose --env-file .env.production exec -T web python manage.py migrate
curl -f http://localhost/healthz || echo "ATENCAO: /healthz nao respondeu OK apos o restore"
```

## Restaurar mídia de usuário

O backup de mídia é gerado de dentro do container `web` (ver `pg_backup.sh`), então o restore também entra por ele — evita depender do nome exato do volume Docker, que varia conforme o nome do diretório de deploy:

```bash
cat infra/backup/restore-media.tar.gz | docker compose --env-file .env.production \
    exec -T web sh -c "rm -rf /app/media/* && tar xzf - -C /app/media"
```

## Baixar backup do storage remoto (Cloudflare R2 / Backblaze B2)

O objeto remoto é gravado com o MESMO nome do arquivo local, e o script confere
o tamanho por `head-object` antes de dizer que o upload deu certo. Baixe sempre
o dump mais recente de `db/`:

```bash
export AWS_ACCESS_KEY_ID=... AWS_SECRET_ACCESS_KEY=...
# endpoint do Cloudflare R2:
#   https://<account-id>.r2.cloudflarestorage.com
aws s3 cp "s3://$BACKUP_S3_BUCKET/db/db-AAAAMMDDTHHMMSSZ.dump" /tmp/restore.dump \
    --endpoint-url "$BACKUP_S3_ENDPOINT"

# Confira ANTES de restaurar: o objeto do bucket precisa ter o mesmo tamanho do
# que o script registrou no log (a linha termina em `bytes=NNN`).
aws s3api head-object --bucket "$BACKUP_S3_BUCKET" \
    --key "db/db-AAAAMMDDTHHMMSSZ.dump" --query ContentLength --output text \
    --endpoint-url "$BACKUP_S3_ENDPOINT"
stat -c %s /tmp/restore.dump

pg_restore --list /tmp/restore.dump | grep -c 'TABLE DATA'   # tabelas com dados
```

Se o R2 responder `head-object` com tamanho diferente do local, o objeto está
truncado: não restaure, baixe de novo. Um archive truncado passa em
`pg_restore --list`, que só lê a tabela de conteúdo.

## O backup já se valida sozinho — mas não confie só nisso

`pg_backup.sh` (e `pg_backup_pm2.sh`) restauram o dump num banco PostgreSQL
descartável e comparam a contagem de tabelas e linhas ANTES de publicar o
arquivo, e recusam um dump sem nenhum dado de tabela ou sem nenhuma linha. Ou
seja: um backup que chega a existir já passou por um restore real.

Ainda assim, o primeiro restore de um ambiente novo é uma decisão humana: pegue
um backup de **staging**, restaure num banco descartável e confira tabela por
tabela com o runbook acima. Um backup nunca restaurado é uma esperança
(RESTORE.md:1-6), e o watchdog `infra/backup/verificar_backup.sh` só prova que
o arquivo tem menos de 26 h e que o objeto correspondente está no bucket — ele
não restaura nada.

## RPO/RTO assumidos nesta arquitetura

- **RPO (perda de dados aceitável):** até 24h — backup roda 1x/dia via cron
  (ver `infra/DEPLOY.md`). Se isso for insuficiente quando o produto tiver
  usuários pagantes reais, aumentar a frequência do cron (ex.: a cada 6h) é
  uma mudança de uma linha, sem alteração de arquitetura.
- **RTO (tempo para religar o serviço):** o gargalo é o tamanho do dump
  baixado, não o restore em si — Postgres restaura rápido para o volume de
  dados esperado no MVP/beta.
