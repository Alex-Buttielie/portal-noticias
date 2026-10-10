# Runbook: ativação do cutover Docker+GHCR em produção

> Este runbook existe porque o código do cutover (`cutover-docker-dev`) está
> pronto, mas a ativação na VPS tem passos manuais que nenhum workflow
> automatiza hoje — em especial o restore do Postgres dentro do container.
> Ver o banner no topo de `CI-CD.md` para o estado atual.

## Ordem obrigatória

**DEV → HOMOLOG → PROD, nunca pular pra PROD primeiro.** Repita a seção
"Por ambiente" três vezes, uma por ambiente, e só avance pro próximo depois
de confirmar saúde do anterior por um tempo razoável.

## Pré-requisitos (uma vez, antes do primeiro ambiente)

### Secrets do GitHub (Environments `dev`/`homolog`/`production`)

- [ ] `GHCR_PULL_TOKEN` — token com escopo `read:packages` no GHCR
- [ ] `GHCR_PULL_USER`
- [ ] Confirmar que `VPS_HOST`, `VPS_USER`, `VPS_SSH_KEY`, `VPS_HOST_FINGERPRINT`,
  `VPS_PORT` já existem (reaproveitados do pipeline PM2 atual — o
  `deploy.yml` novo usa os mesmos nomes)

### VPS

- [ ] Docker + Docker Compose instalados
- [ ] DNS dos 4 hosts (`dev.`, `homolog.`, `portal-noticias.com`,
  `www.portal-noticias.com`) já resolvendo pra VPS (devem estar, já que
  Nginx serve esses domínios hoje)
- [ ] Portas 80/443: Nginx ocupa elas hoje. O Caddy único do
  `infra/docker-edge/` também quer 80/443 — **ver "Caddy compartilhado"
  abaixo antes de instalar**, porque o README dele assume os 3 ambientes
  já containerizados, o que não é o caso num corte gradual.

## Por ambiente (repita pra dev, depois homolog, depois prod)

1. **Backup do Postgres atual (PM2).** Rode `infra/backup/pg_backup_pm2.sh`
   pra esse ambiente (ou use o dump do cron das 03h, se recente o
   suficiente). Confirme o arquivo `pm2-db-<timestamp>.dump` e valide com
   `pg_restore --list` antes de seguir — não assuma que o dump prestou só
   porque o script saiu com código 0.

2. **Primeiro deploy Docker do ambiente.** Dispare o workflow correspondente
   (`deploy-dev.yml`/`deploy-homolog.yml`/`deploy-prod.yml`). Isso builda a
   imagem, publica no GHCR e faz `docker compose pull && up -d` na VPS — os
   containers sobem com um Postgres **vazio** (volume novo). O `.env.production`
   é criado com placeholders no primeiro run e o deploy avisa se
   `DJANGO_DB_PASSWORD` não for preenchido (`deploy.yml`, bloco que cria
   `.env.production`) — preencha antes de seguir.

3. **Restaurar o dump do passo 1 dentro do container.** Siga
   `infra/backup/RESTORE.md` ("Restaurar o banco de dados") usando o dump do
   PM2 do passo 1 em vez do dump Docker — o formato (`pg_dump -Fc`) é o
   mesmo, o restore não diferencia a origem:
   ```bash
   set -a; source .env.production; set +a
   docker compose --env-file .env.production up -d db
   cat pm2-db-<timestamp>.dump | docker compose --env-file .env.production \
       exec -T db pg_restore -U "$DJANGO_DB_USER" -d "$DJANGO_DB_NAME" \
       --clean --if-exists --no-owner
   # confirme números reais, não só "sem erro" (RESTORE.md, passo 4)
   docker compose --env-file .env.production up -d
   docker compose --env-file .env.production exec -T web python manage.py migrate
   ```
   **Isto não está automatizado em nenhum script do repo hoje** — é manual,
   comando por comando, e deve ser testado em DEV antes de confiar nele em
   HOMOLOG/PROD.

4. **Restaurar mídia** com o mesmo backup, via `RESTORE.md` ("Restaurar
   mídia de usuário").

5. **Validar saúde** antes de tocar em Nginx/PM2: `/livez`, `/readyz`,
   `/health-detail` (com e sem token), smoke de `/api/*` — os mesmos
   critérios que `infra/deploy/validate.sh` já checava na topologia antiga.

6. **Só com saúde confirmada:** apontar o domínio desse ambiente pro Docker.
   Ver "Caddy compartilhado" abaixo — a forma exata (editar Nginx pra
   proxy-pass pro Caddy, ou trocar Nginx→Caddy direto nesse domínio) é uma
   decisão sua, o repo não resolve isso automaticamente hoje.

7. **Desligar PM2 desse ambiente** (`pm2 delete portal-web-<env>
   portal-api-<env>; pm2 save`) e remover o vhost Nginx correspondente — só
   depois de um tempo observando estável, não no mesmo dia da migração.

## Caddy compartilhado (`infra/docker-edge/`)

O `README.md` desse diretório documenta instalação **uma vez por VPS**, com
pré-requisito de que os 3 ambientes já estejam containerizados (ele deriva
os nomes de volume `static_data`/`media_data` dos 3). Isso não combina
diretamente com um corte gradual ambiente-por-ambiente: se você instalar o
Caddy único já apontando pros 3 domínios antes de homolog/prod estarem
containerizados, as rotas desses dois vão falhar.

Duas formas de resolver, nenhuma automatizada hoje — escolha uma antes de
instalar:

- **Atrasar a instalação do Caddy** até os 3 ambientes estarem
  containerizados (Nginx continua servindo todos os domínios até lá, você
  só troca Nginx→Caddy pra todos de uma vez no final); ou
- **Subir o Caddy já no primeiro ambiente** (dev) editando o `Caddyfile` pra
  conter só o domínio pronto, e ir acrescentando `__DOMAIN_*__` + `docker
  compose restart caddy` (ou reload) a cada ambiente migrado.

## Depois dos três ambientes migrados

- [ ] Rotacionar/confirmar `OBSERVABILITY_METRICS_TOKEN` igual nos 4 lugares
  (3 `backend/.env.production` + `infra/docker-edge/.env` — ver
  `infra/docker-edge/README.md`, "Rotação do token de observabilidade")
- [ ] Atualizar o banner de `CI-CD.md`/`infra/DEPLOY.md` (mesma convenção já
  usada pra outras retiradas: nota no topo da seção, sem apagar o histórico
  da topologia PM2)
- [ ] Portar o gate `usuarios_teste`
  (`backend/identidade/tests/test_gate_deploy_usuarios_teste.py`) pra Docker
  e destravar o `xfail` — só depois disso remover
  `infra/deploy/deploy.sh`/`validate.sh` (ver nota no cabeçalho deles)

## Plano de rollback por ambiente

Se o Docker falhar depois do corte desse ambiente: reinstale o vhost Nginx,
religue o PM2 (`pm2 start`/`pm2 resurrect`, conforme o que foi salvo antes de
desligar). **Se o Postgres do container já tiver gravado dados novos** desde
o corte, decida qual lado é a fonte de verdade antes de restaurar o dump
antigo no host — não é só apontar o domínio de volta, dados gravados só no
container Docker seriam perdidos.
