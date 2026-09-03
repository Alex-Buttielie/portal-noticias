# Backlog MVP — Vertical Slices (cada slice = DB+API+UI+test)

> Ordem WSJF. Cada slice tem branch `feat/<id>`, testes primeiro, gate QA.

## Sprint 0 — Infra (obrigatório)
- S0-1 compose.dev/prod + nginx + Dockerfiles + .env.example + GH Actions ci/cd (este repo) — DONE scaffold
- S0-2 Firebase init + firestore.rules + auth proxy (core/authentication.py) + seed `plans` (free/semestral/anual) + `feature_flags`

## S1 — Auth & Config
- HU01 onboarding interesses/localidade/canal; C.A. persiste em `users`, reflete em feed. [GWT]
- HU02 GET /api/config expõe plans/flags sem segredo; front lê preço/limite sem hardcode.

## S2 — Assinatura + Pagamento Plugável (sem gateway real)
- HU03 PaymentProvider fake: POST /api/checkout → url fake; webhook → state machine trial/active/past_due/canceled/expired + grace + downgrade Free.
- HU04 Admin CRUD plans/flags → checkout usa novo preço sem deploy. Teste: muda preco sem rebuild.

## S3 — Ingestão + Resumo (OpenAI via Django, nunca no front)
- HU05 ingest RSS fake → `news`; dedup por url hash.
- HU06 POST /api/summarize agrupa `news→event` + chama OpenAI (mock se sem key) → `summaries{prompt_version, source_ids}` + link fonte.

## S4 — Feed/Busca/Radar
- HU07 feed agrupado, categorias, busca, timeline.
- HU08 radar geo (país/estado/cidade/município) — `radar_snapshots` mock + follow localidade.

## S5 — Comunidade & Credenciamento
- HU09 solicitação credenciamento (upload diploma pdf/img configurável) → fila admin → aprova/reprova 24h → selo.
- HU10 posts/comentários/denúncia/moderação + follow autor.

## S6 — Newsletter & Observabilidade
- HU11 newsletter manhã/noite + opt-out LGPD.
- HU12 Otel/Sentry/audit_logs + métricas BRD §21.

**Troca gateway futuro:** implementar `payments/adapters/mercadopago.py : PaymentProvider`, set `PAYMENT_PROVIDER=mercadopago` no `.env` do VPS — zero mudança no front. Mesma interface para Stripe/PagSeguro/Pix.

**Gates:** PRD /approve → Arch /approve → cada PR exige ci verde (lint+type+tests≥70%+gitleaks+banda) → cd só em main via SSH Hostgator.
