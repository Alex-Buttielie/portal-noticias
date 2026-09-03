# AGENTS.md — AI Software Factory

Stack-alvo: **Next.js (TS) + Django/DRF (Python) + Firebase + OpenAI + VPS Hostgator + GH Actions**.
BRD `portal_noticias` é caso de teste; factory é genérica.

## Regras globais
- Vertical slice > camada. Cada feature entrega DB+API+UI+test juntos.
- TDD: test fail → code → green. Nunca code sem teste.
- Parametrização via `feature_flags`/`plans` no Firebase/Firestore — nunca hardcode preço, limite, trial.
- Pagamento via `PaymentProvider` interface — troca por env `PAYMENT_PROVIDER`.
- Firebase Auth: front `ID Token` → `Authorization: Bearer` → `firebase-admin` verify. Nunca expor OPENAI_API_KEY ao front.
- Gates humanos: PRD, Arquitetura, QA, Deploy exigem `/approve`.
- Commits: conventional commits. Branch `feat/<id>`.

## Comandos
- `npm run lint && npm run typecheck && npm run test` (web)
- `ruff check . && mypy . && pytest -q --cov` (api)
- `docker compose -f infra/compose.dev.yml up --build`
- Deploy: push em `main` → GHCR → SSH VPS `docker compose -f infra/compose.prod.yml pull && up -d`
