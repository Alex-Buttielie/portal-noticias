# Estratégia de Implementação — Portal de Notícias (BRD v1 → FE/BE)

> Factory: Next.js (TS) + Django/DRF + Firebase (Auth/Firestore/Storage) + OpenAI proxy + PM2/Nginx VPS (3101/5101 DEV, 3102/5102 HOMOLOG, 3103/5103 PROD) — espelha `profissional-os`. OpenAI mockado, `PAYMENT_PROVIDER=fake` até gateway barato.

## 1. Princípios
- **Vertical slice > camada**: cada HU entrega Firestore collections + DRF endpoint + Next page + teste juntos
- **TDD**: test fail → code → green (pytest + vitest ≥70%)
- **Parametrização total**: preço, intervalo, trial, grace, limites Free/Premium/B2B em `plans`/`feature_flags` — nunca hardcode
- **Pagamento plugável**: `PaymentProvider` Protocol (`create_checkout/handle_webhook/refund/get_status`) + factory `PAYMENT_PROVIDER` env — troca gateway por 1 env var, sem mudar FE
- **OpenAI só no Django**: FE nunca vê `OPENAI_API_KEY` — `POST /api/summarize` proxia + grava `prompt_version` + `source_ids`
- **Firebase Auth**: FE `firebase/auth` → `Authorization: Bearer <ID Token>` → `core.authentication.FirebaseAuthentication` (firebase-admin verify) → `request.user` + claims RBAC

## 2. BRD → Domínio (Firestore collections)
`users{uid, email, role, plano, intereses[], localidades[], canais[], created_at}`, `plans{id, nome, preco_centavos, intervalo_meses, trial_dias, grace_dias, ativo}`, `feature_flags{id, chave, free_limite, premium_limite, descricao}`, `subscriptions{user_id, plan_id, status[trial|active|past_due|unpaid|canceled|expired|encerrada], inicio, vencimento, grace_fim, auto_renova}`, `payments{user_id, plan_id, amount, status, gateway, gateway_id, created_at}`, `organizations{id, nome, plano_b2b, owner_id, membros[{user_id, role}] }`, `sources{id, nome, base_url, tipo[RSS/API], termos_uso, ativo}`, `news{id, source_id, url, titulo, categoria, publicado_em, hash_url, relevancia, urgente}`, `events{id, news_ids[], titulo, categoria, relevancia, urgente, equilibrio_score}`, `summaries{id, event_id, texto, prompt_version, source_ids[], created_by}`, `radar_snapshots{id, tipo[pais|estado|cidade|municipio], localidade_id, assuntos[{termo, volume_cobertura, volume_busca, evolucao, categoria, event_id}], gerado_em}`, `radar_follows{user_id, localidade_id}`, `authors{user_id, status[pendente|aprovado|reprovado|suspenso], diploma_url, diploma_tipo, bio, selo, analisado_por, analisado_em, prazo_24h}`, `posts{id, author_id, titulo, corpo, categoria, tags[], event_id, status[rascunho|publicado], created_at}`, `comments{id, post_id, user_id, parent_id, corpo}`, `reports{id, alvo_tipo, alvo_id, motivo, status[pendente|procedente|improcedente], autor_id}`, `moderation_logs{id, alvo_id, decisao, moderador_id, motivo, created_at}`, `notifications{id, user_id, tipo, payload}`, `newsletters{user_id, tipo[manha|noite|categoria|personalizada], hora, categorias[], ativo}`, `audit_logs{id, ator_id, acao, alvo, antes,depois, created_at}` + `consents{user_id, lgpd}`

RBAC claims: `anon | free | premium | author | moderator | admin | org_owner | org_member` — PM2 envs isolados, DB por env via `db/encontro.json` ignore (profissional-os style) ou Firestore prefix.

## 3. BRD → Features (FE / BE / Regras)

| BRD | Feature | BE | FE |
|---|---|---|---|
| §1 Resumo | Feed agrupado + resumo próprio | `news→events` dedup por hash, `POST /api/events/cluster`, `POST /api/summaries` (OpenAI prompt versionado) | `app/(feed)/page.tsx`, `EventCard` com fontes + link original + badge tipo (noticia/resumo/analise/opiniao) |
| §2 Proposta valor | Busca, agrupamento, radar, personalização | `GET /api/events?categoria=&q=` paginado, `sources` RST, `GET /api/radar?tipo=&id=` | `SearchAutocomplete` (debounce), `CategoryFilter`, `EventTimeline`, `RadarWidget` |
| §6 Assinatura Premium | Plans editáveis, ativação auto, ciclo | `GET/PUT /api/plans` (admin), `POST /api/checkout {plan_id}`, `POST /api/webhooks/payments/{provider}` → state machine + `subscriptions` + `GET /api/subscriptions/me`, `POST /api/subscriptions/{id}/cancel` | `app/premium/page.tsx` lê `plans` ao vivo, `CheckoutButton` redireciona `Checkout.url`, `app/conta/assinatura/page.tsx` status/vencimento/histórico, `MyOrders` pagamentos |
| §6-7 Free×Premium | Matriz parametrizável | `GET /api/config` expõe `plans+feature_flags`, `core.permissions` checa limite por flag (ex: `resumo_personalizado: free 3/dia, premium ilimitado`) — sem hardcode | `useEntitlement(chave)` decide UI (ex: bloqueia alerta extra Free → CTA Premium), `Paywall` |
| §8 Retenção | Onboarding + resumo/alertas/radar personalizados | `POST /api/users/onboarding {intereses, localidade, canais, horario_resumo}`, `POST /api/newsletters`, `Celery` agenda `resumo_personalizado` na hora escolhida | `app/onboarding/page.tsx` wizard, `app/configuracoes/page.tsx`, `NewsletterPrefs` |
| §9 Trial/Ciclo | Estados + grace + downgrade | `SubscriptionStatus` state machine enum `trial→active→past_due→unpaid→canceled→expired→encerrada`, `trial_dias/grace_dias` de `plans`, `Celery` cron transita `vencimento+grace→expired→free`, `payments` histórico | `SubscriptionBadge` estado + CTA renova, email `avisos vencimento` via `notifications` |
| §10 Conteúdo/Ed. | Relevância, dedup, urgência, equilíbrio | `services.relevance_service` score, `news.urgente` boolean, `tasks/ingest` RSS polling + dedup + `relevance` filter descarta baixo valor, `GET /api/admin/moderation-queue` revisão humana | `AdminModQueue`, `UrgenteBadge`, `CategoriaEquilibrio` hint |
| §11 Radar | Geo 4 níveis + evolucao + seguir | `GET /api/radar/snapshots`, `POST /api/radar/follows`, distingue `volume_cobertura` vs `volume_busca` — nunca fake oficial quando sem fonte | `RadarPage` seletor país→estado→cidade→município, `TrendChart`, `FollowButton` |
| §12 Comunidade | Posts, perfis, comentários, denúncia | `POST /api/posts`, `GET /api/posts?author_id=&event_id=`, `POST /api/comments`, `POST /api/reports`, `moderation_logs` | `app/comunidade/page.tsx`, `PostCard`, `CommentThread`, `ReportButton`, `FollowAuthor` |
| §13 Credenciamento | Diploma configurável + SLA 24h + selo | `POST /api/authors/apply {nome,email,tel,cidade,UF,foto,bio, diploma multipart pdf/jpg/png validado por env ALLOWED_DIPLOMA_TYPES}`, `GET /api/admin/authors-queue`, `POST /api/admin/authors/{id}/approve|reprove|solicitar_info` registra `analisado_por/em` + cron checa 24h, `notifications` | `app/credenciamento/page.tsx` form + upload, `AdminCredQueue` com preview diploma + Selo |
| §14 Autor poderes | Rascunho/publicar/associar | `POST /api/posts` com `status rascunho→publicado` + `event_id` FK, `PM` check `author.selo==aprovado`, `GET /api/authors/me/metrics` | `app/autor/page.tsx` editor, `MyPosts`, `Metrics` |
| §15 Reputação | Níveis internos, anti-spam | `reputation_service` calcula `denuncias_procedentes, moderacoes, correcoes` → `nivel_confianca` → `rate_limiter` + `feature_flags` throttle, nunca curtidas como credibilidade | `TrustBadge` interno, `RateLimitToast` |
| §16 Moderação | Respeito + denúncia + bloqueio | `POST /api/reports`, `GET /api/admin/reports-queue`, `POST /api/admin/users/{id}/block|unblock {temporario|permanente}`, `GET /api/appeals` | `ModQueue`, `BlockBanner`, `AppealForm` |
| §17 Governança | Auditoria | `audit_logs` toda mutação `plans/feature_flags/posts/authors`, `GET /api/admin/audit` | `AuditTimeline`, política editorial static `app/politica/page.tsx` |
| §18 Compliance | Direitos autorais + LGPD | `news` só `titulo+url+thumb` se autorizado, `summaries` próprios, `POST /api/corrections`, `GET/DELETE /api/lgpd/me` export/delete, `consents` log, `ViaCEP/IBGE` | `CorrectionButton`, `LGPDPanel` exportar/excluir, `CookieBanner` |
| §19-20 B2B | Orgs + monitoramento | `organizations`, `POST /api/orgs`, `POST /api/orgs/{id}/members`, `GET /api/b2b/monitor?tipo=empresa|concorrente|setor|keyword|legislacao`, `GET /api/b2b/reports` | `app/b2b/page.tsx`, `OrgMembers`, `MonitorDashboard`, `RelatorioExecutivo` PDF |
| §21 Métricas | 15 KPIs | `GET /api/analytics/dashboard {users, dau/mau, retencao, conversao, mrr, arpu, cac, ltv, churn, renovacao, admob, cpu, b2b_ticket}` via `tasks/analytics_daily` | `AdminDashboard` charts MUI |
| §25-27 Landing/Lista/Newsletter | Aquisição | `POST /api/waitlist {nome,email,interesses,localidade,canal,consent}`, `GET /api/newsletters` cron 07h/19h | `app/page.tsx` landing (headline, como funciona 3 passos, exemplo agrupada, resumo, radar, CTA), `WaitlistForm`, `NewsletterPrefs` |
| §28 Marca | Tematização | `feature_flags` tema cores/tipografia via `Layout` | `theme.ts` MUI indigo/pink, `Logo` |
| §30 Riscos | Observabilidade | `Sentry` FE/BE, `Celery` limites consumo OpenAI, `rate_limiter`, `nginx` | `ErrorBoundary`, `Sentry` |
| §32 Critérios sucesso | Testes E2E | Playwright + pytest integração cobrindo FE/BE | `e2e/portal.spec.ts` |

## 4. APIs (OpenAPI sketch)
`GET /api/health`, `GET /api/config`, `GET /api/plans`, `POST /api/plans` (admin), `GET /api/feature-flags`, `POST /api/checkout`, `POST /api/webhooks/payments/{provider}`, `GET /api/subscriptions/me`, `POST /api/subscriptions/{id}/cancel`, `POST /api/auth/verify` (firebase), `GET /api/events? q&categoria&page`, `POST /api/events/cluster`, `POST /api/summaries`, `GET /api/radar/snapshots?tipo&id`, `POST /api/radar/follows`, `POST /api/authors/apply` (multipart), `GET /api/admin/authors-queue`, `POST /api/admin/authors/{id}/decide`, `POST /api/posts`, `GET /api/posts`, `POST /api/comments`, `POST /api/reports`, `GET /api/admin/reports-queue`, `POST /api/admin/users/{id}/block`, `POST /api/waitlist`, `GET /api/analytics/dashboard`, `POST /api/newsletters`, `GET /api/lgpd/me`, `DELETE /api/lgpd/me`, `GET /api/cep/{cep}` (ViaCEP proxy), `GET /api/ibge/municipios?uf=` 

Paginação `?page&limit` → `{items,total,page,pages}`; auth `Bearer ID Token` (firebase) ou `FIREBASE_BYPASS_FOR_TEST=test-token` em teste; erro `{success:false,errors:[]}`.

## 5. Páginas Next (App Router)
`app/page.tsx` landing, `app/(feed)/page.tsx` feed, `app/event/[id]/page.tsx` evento+resumo+fontes+posts relacionados, `app/radar/page.tsx`, `app/comunidade/page.tsx`, `app/autor/*`, `app/credenciamento/page.tsx`, `app/onboarding/page.tsx`, `app/premium/page.tsx`, `app/conta/*`, `app/admin/*` (plans, flags, mod, cred, audit, analytics), `app/b2b/*`, `app/politica/page.tsx`, `app/lgpd/page.tsx` — todas `use client` onde interativo, guard `(protected)` via `AuthContext`.

## 6. Implementação faseada (WSJF)
- **Fase 0 (esta sprint)** — infra DEV/HOMOLOG/PROD + CI: **feito** (PM2 3101/5101 etc, VPS 108.174.147.50:22022 por senha)
- **Fase 1** — Auth + config + plans/flags CRUD + checkout fake + subscription state machine
- **Fase 2** — Ingestão RSS mock + news→events cluster + summaries OpenAI mock + feed/busca/categoria
- **Fase 3** — Radar geo mock + follows
- **Fase 4** — Credenciamento + posts/comments + moderação básica
- **Fase 5** — Reputação/rate limit + governança/audit + LGPD + newsletters (cron Celery)
- **Fase 6** — B2B orgs + monitoramento + relatórios + analytics dashboard
- **Fase 7** — Landing/waitlist + SEO + Sentry + hardening + testes E2E

## 7. Testes & Qualidade (TDD)
BE: `backend/tests/` — `conftest` app/client/db, `unit/test_subscription_state.py`, `test_payment_gateway.py`, `test_relevance.py`, `test radar`, `integration/test_slice.py`; run `pytest -q --cov --cov-fail-under=70`. FE: `vitest` + `playwright`. Gates: `ruff`, `tsc --noEmit`, `bandit`/`gitleaks`, `Sentry`.

## 8. Próximos passos
1. `POST /api/config` + `plans` seed (semestral 2000, anual 3000) — prova parametrizável
2. `PaymentProvider` fake E2E checkout→webhook→active→past_due→expired
3. `news` seed RSS fake + `events` cluster + `summaries` mock → feed
4. Abrir PRs por slice, manter `develop→DEV` auto, `PR→HOMOLOG`, `tag v*→PROD+Release`.
