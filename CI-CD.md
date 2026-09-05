# Pipeline CI/CD — BRD Portal de Notícias

Preserva integralmente a infra do deploy anterior (ramo `backup/remote-*-20260904`):
PM2 + Nginx na VPS, `/home/apps/portal-{dev,homolog,prod}`, portas 310x/510x,
secrets `VPS_HOST/USER/PASSWORD/PORT`. **Muda só o software**: `frontend/` +
`backend/` (Django real) no lugar de `apps/*`, com as mesmas portas, processos,
domínios e segredos.

```
                push develop                        PR develop → main                        tag v*
               ──────────────►                      ──────────────────►                     ───────────────►
               │                │                    │                  │                   │                │
               ▼                ▼                    ▼                  ▼                   ▼                ▼
          CI Workflow      Deploy DEV           CI Workflow        Deploy HOMOLOG       Deploy PROD     GitHub Release
     (tsc + check +       (PM2 3101/5101)     (tsc + check +       (PM2 3102/5102)      (PM2 3103/5103)   + Tag
      pytest/cov 80%)                          pytest/cov 80%)
```

### Ambientes na VPS (inalterados)

| Ambiente | Ref git | Dir VPS | PM2 web/api | Portas |
|----------|---------|---------|-------------|--------|
| DEV | `develop` | `/home/apps/portal-dev` | `portal-web-dev` / `portal-api-dev` | 3101 / 5101 |
| HOMOLOG | branch do PR | `/home/apps/portal-homolog` | `portal-web-homolog` / `portal-api-homolog` | 3102 / 5102 |
| PROD | `main` (tag `v*`) | `/home/apps/portal-prod` | `portal-web-prod` / `portal-api-prod` | 3103 / 5103 |

Nginx (inalterado, ver `scripts/setup-vps.sh` do deploy anterior):
`dev.portal-noticias.com.br` (`/`→3101, `/api/`→5101),
`homolog.portal-noticias.com.br` (→3102/5102),
`portal-noticias.com.br` (→3103/5103).

### O que mudou no software (única diferença)

- API: `apps/api` → `backend/` (venv em `backend/.venv`, `config.wsgi:application`,
  `manage.py migrate + collectstatic` a cada deploy, health em `/healthz`).
- Web: `apps/web` → `frontend/` (`npm ci + build` com `NEXT_PUBLIC_API_BASE_URL=https://<host>/api`).
- `backend/.env` por ambiente é gerado no primeiro deploy (SECRET forte,
  `DJANGO_DEBUG=false`, `DJANGO_DB_ENGINE=sqlite3`, domínios) e **preservado**
  nos deploys seguintes (`git reset` não apaga arquivos ignorados). Banco
  SQLite local + Redis da VPS — nenhum serviço novo instalado.
- Validação: `localhost:51xx/healthz` (API) + `localhost:31xx/` (web).
  PROD falha o workflow se a API ou a web não responderem; DEV/HOMOLOG
  reportam `warn` como no deploy anterior.

### Fluxo Git Flow

1. **Feature**: `develop` → `feature/x` → commits → merge em `develop`
2. **Push em develop**: CI + deploy DEV automático
3. **PR develop → main**: CI + deploy HOMOLOG com o código do PR
4. **Merge + tag**: `git tag vX.Y.Z && git push origin vX.Y.Z` → Release + deploy PROD

### Rollback (inalterado na forma)

```bash
cd /home/apps/portal-prod
git fetch --all --tags && git checkout <tag-anterior>   # ex.: v1.0.0
# refaz build + restart (mesmos comandos do workflow) ou aguarde a próxima tag
```
`backend/.env`, SQLite (`db.sqlite3`) e `media/` são untracked/ignorados —
sobrevivem ao `git reset`. PM2 é reiniciado, nunca apagado sem recriação.

### Workflows

| Workflow | Arquivo | Trigger |
|----------|--------|---------|
| CI | `.github/workflows/ci.yml` | push/PR em develop e main (`manage.py check`, pytest cov≥80, `tsc`, `next build`) |
| Deploy DEV | `deploy-dev.yml` | push em develop (SSH `VPS_PASSWORD`, PM2 3101/5101) |
| Deploy HOMOLOG | `deploy-homolog.yml` | PR para main (SSH `VPS_PASSWORD`, PM2 3102/5102) |
| Deploy PROD | `deploy-prod.yml` | tag `v*` + Release (SSH `VPS_PASSWORD`, PM2 3103/5103) |

Secrets exigidos (os mesmos de antes): `VPS_HOST`, `VPS_USER`, `VPS_PASSWORD`, `VPS_PORT`.

### Banco de dados (Postgres na VPS — único pré-requisito novo)

O software recusa `sqlite3` com `DEBUG=False` (fail-fast em
`config/settings.py`). Uma vez por VPS, como `root`:

```bash
apt install -y postgresql
sudo -u postgres psql -c "CREATE USER portal_app WITH PASSWORD '<senha-forte>';"
sudo -u postgres psql -c "CREATE DATABASE brd_portal_noticias OWNER portal_app;"
```

Depois preencha `DJANGO_DB_PASSWORD` em
`/home/apps/portal-{dev,homolog,prod}/backend/.env` (o workflow cria o
arquivo com placeholder e falha com mensagem clara até a senha existir).
Os 3 ambientes compartilham o servidor, mas use bancos/usuários distintos
se quiser isolamento total.

### Mapa de branches (não apagar)

| Branch | Papel | Deploy |
|--------|-------|--------|
| `main` | produção (só via merge de PR + tag `v*`) | PROD :3103/5103 |
| `develop` | integração (push direto liberado) | DEV :3101/5101 |
| PR `develop` → `main` | validação (manter aberto até aprovar) | HOMOLOG :3102/5102 |
| `homolog-retest` | legado do deploy anterior (congelada) | nenhum |
| `backup/remote-*` | foto do deploy antigo (nunca commitar em cima) | nenhum |
| `v1.0.0` | tag anulada (script Docker, não usar) | — |
| `vX.Y.Z` | releases válidas (a partir de `v1.0.1`) | PROD |
