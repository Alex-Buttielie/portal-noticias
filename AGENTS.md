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

## Comandos (espelha profissional-os)
- `npm run lint && npm run typecheck && npm run build` (apps/web — TS 5.5 + Next)
- `ruff check . && pytest -q --cov` (apps/api — Flask/Django + firebase-admin mock)
- Local: `docker compose up --build` (redis+api+web) ou `FIRESTORE_EMULATOR_HOST=localhost:8080` + `firebase emulators:start`
- Deploy: `develop→DEV(3101/5101)` PM2, `PR→HOMOLOG(3102/5102)`, `tag v*→PROD(3103/5103)+Release` + Nginx reverse
