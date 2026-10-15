# Runbook: ativação do cutover Docker em DEV

> **[HISTÓRICO/DESATUALIZADO — marcado em 2026-10-15, nunca atualizado desde
> 2026-10-11]** Este runbook assumia, pela PR #39 (2026-10-10), que
> HOMOLOG/PROD tinham voltado pra PM2+Nginx "de vez" e que só DEV iria pra
> Docker. Isso valeu por pouquíssimo tempo: no mesmo dia 2026-10-11, PROD
> completou a Fase E (inventário, backup, validação em paralelo, migração de
> dados com gate de confirmação — ver comentário de
> `.github/workflows/deploy-prod.yml`) e **também** foi cortado pra Docker;
> HOMOLOG seguiu o mesmo caminho. Este documento nunca foi atualizado para
> refletir isso. Reconfirmado por SSH em 2026-10-15: os 3 ambientes
> (dev/homolog/prod) rodam a aplicação em containers Docker — ver o estado
> real em `CI-CD.md` ("Cutover concluído").
>
> **A parte que segue correta:** a conclusão de que o Caddy compartilhado
> deste diretório (`infra/docker-edge/`) não era necessário. Isso se
> confirmou — e permanece verdade hoje: a borda dos 3 ambientes continua
> sendo o Nginx (vhosts por ambiente + Certbot), nunca o Caddy daqui. Por
> decisão do solicitante (2026-10-15), este diretório fica como "preparado,
> não ativado" no repositório, sem plano de ativação definido.
>
> O passo a passo abaixo (escrito só para DEV, assumindo que HOMOLOG/PROD
> ficariam em PM2 para sempre) está desatualizado como procedimento — DEV já
> está em Docker há tempos e HOMOLOG/PROD também migraram por um caminho
> diferente do descrito aqui (ver `agentic-framework/state/run-20260925-1433-go-live-producao/`
> para o histórico real da migração de PROD). Preservado abaixo só como
> referência histórica de como o cutover de DEV foi pensado originalmente;
> não siga estes passos para provisionar um ambiente novo.

## O que muda nesta versão

- **Sem "ordem obrigatória" entre ambientes** — é só DEV.
- **`infra/docker-edge/` (Caddy compartilhado) não é necessário.** Como
  HOMOLOG/PROD continuam com Nginx pra sempre, a opção mais simples é manter
  o Nginx como único ponto de entrada — ele já tem o catch-all `444`
  (`000-catchall-444`), os security headers e o rate-limit — e só trocar o
  `proxy_pass`/`upstream` do vhost `portal-dev` de `127.0.0.1:3101`/`5101`
  (PM2) pra `127.0.0.1:$WEB_PORT`/`$API_PORT` (o container, que o
  `docker-compose.yml` já publica em loopback). Isso evita reimplementar
  catch-all/headers num Caddy novo e evita a disputa de portas 80/443 entre
  Caddy e o Nginx que HOMOLOG/PROD vão usar pra sempre. **Se preferir seguir
  com o Caddy do `docker-edge/` mesmo assim, me avisa antes de instalar** —
  a lógica deste runbook muda.
- **Domínio correto: `portal-noticias.com.br`** (com `.br`). A versão
  anterior deste runbook e o `infra/docker-edge/README.md` usam `.com` —
  isso é um erro meu que ainda precisa ser corrigido no README do
  `docker-edge` (não fiz isso ainda porque esse Caddy deixou de ser
  necessário pra DEV; só corrigir se alguém for usá-lo de verdade).
- **TLS: nenhum certificado existe hoje, em nenhum ambiente**
  (`certbot certificates` → "No certificates found", confirmado na VPS).
  Não é regressão do cutover — é um estado pré-existente. DEV precisa de
  DNS correto antes do Certbot conseguir emitir.

## Pré-requisitos

- [x] Secrets `GHCR_PULL_TOKEN`/`GHCR_PULL_USER` + `VPS_HOST/USER/SSH_KEY/PORT`
  — já existem no GitHub.
- [x] Docker 29.7.1 + Compose v5.3.1 — já instalados na VPS.
- [ ] DNS de `dev.portal-noticias.com.br` resolvendo pra VPS — pendente de
  confirmação (pedi pra rodar a checagem e ainda não recebi o resultado).
- [ ] Escolher `API_PORT`/`WEB_PORT` do container de DEV sem colidir com o
  que já está em uso na VPS: HOMOLOG usa 3102/5102, PROD usa 3103/5103,
  `coordenador` usa 8081-8083. Os defaults do compose (8000/3000) já
  resolvem isso, mas confirme antes de subir.
- [ ] Confirmar se DEV tem dado real que precisa ser preservado — os
  processos `portal-api-dev`/`portal-web-dev` já estavam **parados** antes
  de eu tocar em qualquer coisa (motivo ainda não confirmado); se DEV não
  tem tráfego/dado que importa, o passo de restore do Postgres pode ser
  pulado e o container sobe vazio.

## Passo a passo (DEV, ambiente único)

1. **Se DEV tiver dado que precisa ser preservado:** backup com
   `infra/backup/pg_backup_pm2.sh` (ambiente dev) antes de qualquer coisa.
   Valide o `.dump` com `pg_restore --list`, não assuma que prestou só
   porque o script saiu com código 0.

2. **Preencher `.env.production` de DEV** (as portas escolhidas,
   `DJANGO_DB_PASSWORD`, etc. — o `deploy.yml`/workflow cria um com
   placeholders no primeiro run, ou crie manualmente) e subir:
   ```bash
   docker compose --env-file .env.production up -d
   ```

3. **Se houver dump do passo 1:** restaurar dentro do container seguindo
   `infra/backup/RESTORE.md` ("Restaurar o banco de dados") antes de abrir
   o tráfego pro Docker — o formato (`pg_dump -Fc`) é o mesmo entre as duas
   variantes, o restore não diferencia a origem.

4. **Trocar o roteamento no Nginx** (`/etc/nginx/sites-available/portal-dev`):
   - `upstream portal_api_dev { server 127.0.0.1:5101; ... }` → porta do
     container (`$API_PORT`)
   - `location / { proxy_pass http://127.0.0.1:3101; ... }` → porta do
     container (`$WEB_PORT`)
   - `sudo nginx -t && sudo systemctl reload nginx`

5. **Validar saúde**: `/livez`, `/readyz`, `/health-detail` (com e sem
   token), smoke de `/api/*` — os mesmos critérios que
   `infra/deploy/validate.sh` já checava na topologia PM2.

6. **PM2 de DEV**: já está parado (`portal-api-dev`/`portal-web-dev`,
   status `stopped`). Depois de validado o Docker, só falta confirmar que
   não precisa voltar — não há ação adicional aqui.

7. **TLS**: depois do DNS confirmado, emitir certificado pro domínio de DEV
   pelo Certbot normal (mesmo fluxo que HOMOLOG/PROD já usam hoje — nenhuma
   novidade de Caddy nesta abordagem).

## Rollback

Trocar o `proxy_pass`/`upstream` de volta pra `3101`/`5101` e
`pm2 start`/`pm2 resurrect portal-api-dev portal-web-dev`, se precisar
voltar pra PM2. Se o Postgres do container já tiver gravado dados novos
desde o corte, decida qual lado é fonte de verdade antes de restaurar o
dump antigo.

## O que isso NÃO muda

`infra/deploy/deploy.sh`/`validate.sh` continuam ativos pra HOMOLOG/PROD
**pra sempre** (PR #39, comentário corrigido na PR #42) — nada deste
runbook os afeta, e eles não devem ser removidos.
