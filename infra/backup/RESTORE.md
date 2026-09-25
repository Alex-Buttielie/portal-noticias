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

# 1. Copie o .dump desejado (local ou baixado do storage remoto) para
#    infra/backup/restore.dump

# 2. Suba só o serviço de banco, se ainda não estiver rodando
docker compose --env-file .env.production up -d db

# 3. Restaura para dentro do container (recria o banco do zero — ATENÇÃO:
#    isto apaga o conteúdo atual do banco de destino)
cat infra/backup/restore.dump | docker compose --env-file .env.production \
    exec -T db pg_restore -U "$DJANGO_DB_USER" -d "$DJANGO_DB_NAME" \
    --clean --if-exists --no-owner

# 4. Confirme que o restore trouxe dados reais antes de considerar
#    concluído — não assuma sucesso só porque pg_restore não imprimiu erro.
docker compose --env-file .env.production exec -T db \
    psql -U "$DJANGO_DB_USER" -d "$DJANGO_DB_NAME" \
    -c "select count(*) from django_migrations;"

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

## Baixar backup do storage remoto (Backblaze B2 / Cloudflare R2)

```bash
export AWS_ACCESS_KEY_ID=... AWS_SECRET_ACCESS_KEY=...
aws s3 cp s3://$BACKUP_S3_BUCKET/db/db-AAAAMMDD-HHMMSS.dump infra/backup/restore.dump \
    --endpoint-url $BACKUP_S3_ENDPOINT
```

## Topologia ATIVA (PM2 + Nginx + PostgreSQL do host)

O runbook acima é da variante Docker/Caddy, que **não é a topologia em
produção**. Na topologia ativa (o mesmo host com `/home/apps/portal-<env>`, o
PostgreSQL nativo, o PM2 e o Nginx) o restore é diferente em três pontos: não
existe container, o `MEDIA_ROOT` é um diretório do host, e o backup é o
`pg_backup_pm2.sh`. Erro aqui custa o incidente inteiro.

### 1. Onde os artefatos estão

```bash
# Dump e mídia mais recentes, no diretório do backup (retenção local de 7 dias):
ls -lh /home/apps/portal-prod/infra/backup/pm2-db-*.dump \
      /home/apps/portal-prod/infra/backup/pm2-media-*.tar.gz

# O marcador de ÚLTIMO BACKUP CONFIRMADO (modo 600). Leia-o antes de restaurar:
# `dump=` e `remoto=` dizem qual arquivo é o válido e se ele foi confirmado
# no bucket. Um backup sem marcador é um backup que NÃO completou.
sudo cat /home/apps/portal-prod/infra/backup/.ultimo-backup-ok
```

### 2. Restore do banco, na topologia ativa

Restaure SEMPRE num banco novo primeiro. O dump é de um `pg_dump -Fc`; o
`--clean --if-exists` abaixo é para o caso de restaurar sobre o banco existente,
e é o passo que APAGA o conteúdo atual.

```bash
# 0. Carregue as credenciais do MESMO arquivo do deploy (modo 600):
set -a; source /home/apps/portal-prod/backend/.env; set +a

# 1. Crie o banco de restore (isolado) e restaure nele:
createdb -h "$PGHOST" -U "$PGUSER" portal_restore_teste
pg_restore -h "$PGHOST" -U "$PGUSER" --exit-on-error --no-owner --no-privileges \
  -d portal_restore_teste /home/apps/portal-prod/infra/backup/pm2-db-<TIMESTAMP>.dump

# 2. Confirme que o restore trouxe dados REAIS. `pg_restore` sem erro não é
#    prova de nada — um archive truncado passa.
psql -h "$PGHOST" -U "$PGUSER" -d portal_restore_teste \
  -c "select count(*) from django_migrations;"
psql -h "$PGHOST" -U "$PGUSER" -d portal_restore_teste \
  -c "select relname, n_live_tup from pg_stat_user_tables order by n_live_tup desc limit 10;"

# 3. As migrations pendentes (o dump pode ser de uma versão anterior do
#    código). Num banco de restore, o comando é de leitura de estado:
python manage.py showmigrations --plan | grep '\[ \]' || echo "sem migrations pendentes"

# 4. Remova o banco de teste:
dropdb -h "$PGHOST" -U "$PGUSER" portal_restore_teste
```

### 3. Restore da mídia

```bash
# Extraia num diretório VAZIO. Nunca sobre /home/apps/portal-prod/backend/media:
# sobrescrever a mídia atual com um backup antigo é perder os uploads novos.
mkdir -p /tmp/midia-restore
tar xzf /home/apps/portal-prod/infra/backup/pm2-media-<TIMESTAMP>.tar.gz -C /tmp/midia-restore
find /tmp/midia-restore -type f | head
# Compare com o que está no disco atual antes de qualquer substituição.
```

### 4. Backup vindo do object storage (R2/B2)

```bash
export AWS_ACCESS_KEY_ID=... AWS_SECRET_ACCESS_KEY=...
aws s3 cp "s3://$BACKUP_S3_BUCKET/db/pm2-db-<TIMESTAMP>.dump" /tmp/restore.dump \
  --endpoint-url "$BACKUP_S3_ENDPOINT"
pg_restore --list /tmp/restore.dump >/dev/null && echo "TOC íntegra"
```

### 5. Teste de restore MENSAL (critério 35)

Backup sem restore testado é uma hope, não um backup. Uma vez por mês, sem
exceção, rode as seções 2 e 3 num banco descartável e registre o resultado
**antes** de precisar dele:

```bash
# O mesmo relógio do watchdog, para que a data do teste e a do backup não
# divirjam de zona horária:
date -u +%Y-%m-%dT%H:%M:%SZ

# E o atraso do backup agora (mesmo par de arquivos que o alerta externo usa):
BACKUP_DIR=/home/apps/portal-prod/infra/backup \
  /home/apps/portal-prod/infra/backup/verificar_backup.sh
# exit 0 = dentro do prazo; 1 = atrasado; 2 = nunca executou; 3 = config inválida
```

Registre em `implementation-history.md` da run: data, arquivo restaurado, banco
de teste, contagens comparadas e resultado. Um restore que nunca foi testado em
produção é uma hipótese sobre o seu plano de recuperação.

### 6. Quando o restore é o ÚNICO caminho (incidente em produção)

Este é o cenário que a run quer evitar, então ele fica escrito:

1. **Pare de escrever antes de restaurar.** Um restore por cima do banco em uso
   grava por cima de conexões vivas e produz um estado misto que não é nem o
   backup nem o estado anterior. Coloque a aplicação em manutenção no Nginx
   (`return 503` no `location /api/`) ou pare os processos PM2.
2. **Restaure num banco novo** (`portal_restore_<data>`), corrija o
   `DJANGO_DB_NAME` no env e **reinicie os processos** — `pm2 restart` +
   `pm2 save`. Um `SIGUSR2` no Gunicorn recarrega sem trocar a configuração de
   banco, que é o que NÃO resolve o problema.
3. **Valide antes de reabrir**: `/livez` (processo), `/readyz` (banco +
   migrations), e uma requisição real de feed.
4. **Só então** reabra o tráfego e registre o incidente com o `request_id` que
   o usuário colou (é o que amarra o Nginx, o Gunicorn e o Postgres no log).
5. **Não apague o dump nem o banco antigo** até a causa estar entendida; é o
   único caminho de volta se o restore estiver errado.

## RPO/RTO assumidos nesta arquitetura

- **RPO (perda de dados aceitável):** até 24h — backup roda 1x/dia via cron
  (ver `infra/DEPLOY.md`). Se isso for insuficiente quando o produto tiver
  usuários pagantes reais, aumentar a frequência do cron (ex.: a cada 6h) é
  uma mudança de uma linha, sem alteração de arquitetura.
- **RTO (tempo para religar o serviço):** o gargalo é o tamanho do dump
  baixado, não o restore em si — Postgres restaura rápido para o volume de
  dados esperado no MVP/beta.
