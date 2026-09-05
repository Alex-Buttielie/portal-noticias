# Pipeline CI/CD — BRD Portal de Notícias

Modelo herdado do `profissional-os/CI-CD.md` (3 ambientes via GitHub Actions + SSH),
adaptado para a arquitetura Docker + Caddy deste projeto (sem PM2/Nginx manual).

```
                push develop                        PR develop → main                        tag v*
               ──────────────►                      ──────────────────►                     ───────────────►
               │                │                    │                  │                   │                │
               ▼                ▼                    ▼                  ▼                   ▼                ▼
          CI Workflow      Deploy DEV           CI Workflow        Deploy HOMOLOG       Deploy PROD     GitHub Release
     (pytest/postgres     (VPS 8081/8444)     (pytest/postgres    (VPS 8080/8443)      (VPS 80/443)      + Tag
      + tsc/build)                             + tsc/build)
```

### Ambientes na VPS

| Ambiente | Ref git | Compose `-p` | Portas host | `.env` na VPS |
|----------|---------|--------------|-------------|---------------|
| DEV | `develop` | `brd-dev` | 8081/8444 | `.env.dev` |
| HOMOLOG | branch do PR | `brd-homolog` | 8080/8443 | `.env.homolog` |
| PROD | `main` (tag `v*`) | `brd-prod` | 80/443 | `.env.production` |

Os 3 clones vivem em `/home/deploy/brd_portal_noticias[-dev|-homolog]`.
Volumes são isolados por `-p`. Os arquivos `.env.*` ficam **só na VPS**
(`chmod 600`, nunca commitados — ver `.gitignore`).

### Fluxo Git Flow

1. **Feature**: `git checkout develop` → `feature/x` → commits → merge em `develop`
2. **Push em develop**: CI + deploy DEV (validação `Host: DOMAIN_API → :8081/healthz`)
3. **PR develop → main**: CI + deploy HOMOLOG com o código do PR (`:8080/healthz`)
4. **Merge + tag**: `git tag v1.0.0 && git push origin v1.0.0` → Release + deploy PROD (`https://DOMAIN_API/healthz`)

### Configuração — PASSO ÚNICO

**Secrets** (repo GitHub → Settings → Secrets → Actions): `VPS_HOST`, `VPS_USER`,
`VPS_SSH_KEY` (privada ed25519 sem passphrase), `VPS_PORT`.

**Environments**: `development` (sem proteção), `homolog` (aprovação opcional),
`production` (aprovação manual recomendada).

**VPS**: seguir `infra/DEPLOY.md` (hardening + Docker + Cloudflare). Depois, por ambiente:
```bash
git clone <repo> /home/deploy/brd_portal_noticias-dev && cd $_
git checkout develop
cp .env.production.example .env.dev  # trocar domínios (dev-*) + senhas/SECRET
chmod 600 .env.dev
```
Repetir para `-homolog` (branch do PR é trocada automaticamente pelo workflow).

**DNS**: `A dev-api/dev`, `homolog-api/homolog`, `api + raiz` → IP da VPS (proxy Cloudflare + Full strict).

### Rollback

```bash
cd /home/deploy/brd_portal_noticias
git fetch origin && git reset --hard <tag-anterior>   # ex.: v0.9.0
docker compose --env-file .env.production -p brd-prod up -d --build
```
Dados preservados (volumes `postgres_data/media_data` não são recriados).

### Workflows

| Workflow | Arquivo | Trigger |
|----------|--------|---------|
| CI | `.github/workflows/ci.yml` | push/PR em develop e main (pytest+postgres, `manage.py check`, `tsc`, `next build`) |
| Deploy DEV | `deploy-dev.yml` | push em develop |
| Deploy HOMOLOG | `deploy-homolog.yml` | PR para main |
| Deploy PROD | `deploy-prod.yml` | tag `v*` (+ GitHub Release) |
