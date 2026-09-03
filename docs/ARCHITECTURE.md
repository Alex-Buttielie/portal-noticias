# AI Software Factory — Arquitetura Madura (TS + Django + Firebase + OpenAI + VPS)

> BRD `portal_noticias v1` usado como **caso de teste**. Factory é genérica para qualquer web software.

## 1. Visão
Factory transforma `BRD.docx` → software em produção no VPS Hostgator via pipeline de agentes com gates humanos. Stack-alvo fixo: **Next.js (TS) + Django/DRF (Python) + Firebase (Auth/Firestore/Storage) + OpenAI + Docker + GitHub Actions**.

## 2. Meta-Arquitetura (Opencode)

```
BRD.docx ─► ingest-agent (OpenAI) ─► docs/PRD.md + prd.json
                │
                ▼
         analyst-agent ─► epics + HUs + critérios (GATE 1: você aprova PRD)
                │
                ▼
         architect-agent ─► ADRs + C4 + OpenAPI + data-model (GATE 2)
                │
                ▼
         pm-agent ─► backlog priorizado + DAG (docs/BACKLOG_MVP.md)
                │
          ┌─────┴─────┐
          ▼           ▼
   frontend-agent  backend-agent  (paralelos, vertical slice, TDD)
          └─────┬─────┘
                ▼
         qa/sec-agent ─► lint/typecheck/pytest/coverage/SAST/secrets (GATE 3)
                ▼
         devops-agent ─► build → GHCR → SSH deploy VPS (GATE 4)
                ▼
         operate ─► Otel/Sentry/logs + feedback → backlog
```

**Orquestração:** `opencode` (opencode.json) + MCPs: `github`, `firebase`, `ssh-vps`, `openai`. Estado em `docs/run/<id>/`.

## 3. Agentes (.opencode/agents/)

| Agente | Modelo | Ferramentas | Output |
|---|---|---|---|
| ingest/analyst | gpt-4o | read docx, write PRD | PRD.md, hus.json |
| architect | gpt-4o | adr, openapi, mermaid | ADR-*, openapi.yaml, firestore.rules |
| frontend | gpt-4o-mini | next, vitest, playwright | app/*, components/* |
| backend | gpt-4o-mini | django, pytest, firebase-admin | api/* |
| qa/sec | gpt-4o-mini | ruff, mypy, bandit, gitleaks | coverage, audit |
| devops | gpt-4o-mini | docker, compose, ssh | deploy |

Prompts com `role + constraints + checklist + no hallucinations`.

## 4. Fluxo Maduro E2E (SDLC)

1. **Intake** — parse BRD → valida completude (MoSCoW) → gera PRD draft
2. **Discovery** — refina HUs (Given/When/Then), NFRs, matriz Free/Premium/B2B parametrizável
3. **Architecture** — C4 L1-L3, ADRs, OpenAPI 3.1, ER/Firestore collections, RBAC, LGPD
4. **Plan** — DAG de tasks, estimativa WSJF, sprint 0 (infra) + slices verticais
5. **Build** — TDD: test fail → code → green → refactor. Branch `feat/<id>` → PR → CI
6. **Quality Gates** — `ruff+eslint+tsc+mypy` 0 erros, `pytest+vitest` ≥70% coverage, bandit, sem segredos, a11y
7. **Deploy** — `main` → GHCR → `ssh vps "docker compose pull && up -d"` + migrate + smoke
8. **Operate** — logs Otel → Grafana, Sentry, uptime, métricas de negócio → retro → backlog

**Gates humanos:** PRD, Arquitetura, QA, Prod — você aprova via comentário `/approve`.

## 5. Runtime Alvo (todo projeto herda)

```
[CDN/Cloudflare] → [Nginx :80/443 (VPS)] → /api/* → Django:8000 (gunicorn)
                                    └→ /*    → Next.js:3000 (standalone)
[Firebase] Auth (JWT) ↔ Django (firebase-admin verify) ↔ Firestore
[OpenAI] via backend proxy (nunca expõe key ao front)
[Storage] Firebase Storage (diplomas, thumbs) + local /srv/media backup
[Jobs] Celery + Redis (resumos, radar, newsletters) | Cron
```

**Repo:** `apps/web` (Next), `apps/api` (Django), `packages/shared` (zod schemas), `infra/` (compose, nginx, tf-ish shell).

## 6. Data Model (Firestore + Django mirror)

Collections: `users`, `subscriptions`, `plans`, `payments`, `organizations` (B2B), `sources`, `news`, `events` (agrupamento), `summaries`, `radar_snapshots`, `authors`, `posts`, `comments`, `reports`, `audit_logs`, `feature_flags`.
`plans` e `feature_flags` tornam **preços, limites Free/Premium, trial, grace period 100% configuráveis via Admin sem deploy** (req BRD §6-9).

RBAC: `anon | free | premium | author | moderator | admin | org_owner | org_member`.

## 7. Pagamento Plugável (req #5)

```python
# apps/api/payments/base.py
class PaymentProvider(Protocol):
    def create_checkout(self, plan, user, success_url, cancel_url) -> Checkout: ...
    def handle_webhook(self, request) -> PaymentEvent: ...
    def refund(self, payment_id): ...
    def get_status(self, payment_id) -> str: ...

# adapters: mercadopago.py, stripe.py, pagseguro.py, pix_manual.py
# Factory via settings.PAYMENT_PROVIDER="mercadopago" (env)
# Webhook único: POST /api/webhooks/payments/<provider>/ → normaliza → subscription state machine
```
State machine: `trial → active → past_due (+grace) → unpaid → canceled → expired → free_downgrade`. Histórico em `payments`. Troca de gateway = 1 env var.

## 8. Firebase no Django

- Auth: front `firebase/auth` → `ID Token` → `Authorization: Bearer` → `FirebaseAuthentication` (verify via admin-sdk) → `request.user`
- Firestore: `firebase-admin` + `firestore` lib; Django models como DTOs (opcional Django ORM → Firestore via `django-firestore` ou espelho Postgres-lite se preferir; default: Firestore direto)
- Rules: `firestore.rules` geradas pelo architect-agent, validadas em CI (`firebase emulators:exec`)
- Storage: upload direto com signed URL → webhook salva metadata

## 9. Infra VPS Hostgator

VPS Ubuntu 22.04, Docker + Compose, Nginx (reverse + certbot), 2GB+ RAM.
Deploy sem k8s: `docker compose -f infra/compose.prod.yml pull && up -d --remove-orphans`.
GH Actions → `appleboy/ssh-action` com `HOST, USER, SSH_KEY` secrets.
Zero-downtime: `blue-green` simples (2 compose projects) ou `traefik` se escalar.
Backups: `cron` dump Firestore via `gcloud` + `pg_dump` se houver Postgres + snapshots VPS.

## 10. CI/CD (GitHub Actions)

`ci.yml` (PR): `lint → typecheck → test (matrix) → coverage gate → SAST → build preview`
`cd.yml` (main): `build → push GHCR → ssh deploy → migrate → smoke e2e (playwright) → notify`
Branch protection: exige `ci` verde.

## 11. Qualidade & Compliance

- Observabilidade: OpenTelemetry → Loki/Tempo, Sentry, Uptime Kuma
- LGPD: consent log, export/delete user, audit trail, DPA
- Editorial: `summaries` guardam `source_ids[] + prompt_version` (rastreabilidade)
- Rate limit + moderação: quotas por reputação (BRD §15)

## 12. Roadmap Factory vs Produto

Factory (esta arquitetura) entrega **Sprint 0** infra + primeiro slice (Auth+Plans+Pay mock) em 1-2 dias; depois itera slices: Ingestão → Agrupamento/Resumo (OpenAI) → Radar → Comunidade → B2B.

## 13. Próximo Passo

`/approve` nesta arquitetura → scaffold gera `apps/web`, `apps/api`, `infra/compose.*`, `openapi.yaml`, `firestore.rules`, `plans seed`.
