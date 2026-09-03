# PRD — Portal de Notícias v1 (caso de teste da Factory)

> Derivado de `BRD_portal_noticias_versao_1.docx`. Status: **draft — aguarda /approve (GATE 1)**.

## 1. Objetivo
Plataforma web freemium (Free com ads / Premium sem ads + recursos) + radar geo + comunidade com credenciamento manual + B2B futuro. Entregar vertical slices com parametrização total.

## 2. Personas (BRD §4)
Ocupada, Profissional, Estudante — valorizam resumo rápido, agrupamento por acontecimento, fonte rastreável, radar local.

## 3. Requisitos Funcionais (resumo RF)

| ID | Módulo | Descrição | Origem |
|---|---|---|---|
| RF01 | Auth & Perfil | Cadastro/login Firebase Auth, onboarding interesses/localidade/canais | §8 |
| RF02 | Assinatura | Plans configuráveis (Free/R$0, Semestral R$20, Anual R$30), estados trial/active/past_due/canceled/expired, grace period, downgrade Free | §6,9 |
| RF03 | Pagamento plugável | PaymentProvider (create_checkout/webhook/refund), invoice history, switch por env | §5-6 |
| RF04 | Ingestão | RSS/API feeds autorizados, dedup, relevância, fila p/ resumo OpenAI (proxy pelo Django) | §10,18 |
| RF05 | Agrupamento & Resumo | cluster por acontecimento, resumo próprio (prompt versionado), link fonte | §2,10 |
| RF06 | Radar | por país/estado/cidade/município, alta cobertura vs busca, follow localidade | §11 |
| RF07 | Busca & Feed | categorias, busca, timeline, equilíbrio entre categorias | §7,10 |
| RF08 | Comunidade | posts de autores credenciados, comentários/respostas, denúncia, moderação, follow autor | §12,16 |
| RF09 | Credenciamento | solicitação com diploma (PDF/img configurável), fila admin, SLA 24h, selo, suspensão | §13 |
| RF10 | Admin & Flags | CRUD plans/feature_flags, fila moderação/credenciamento, audit log | §6-9,17 |
| RF11 | Newsletter & Distribuição | resumo manhã/noite, por categoria, personalizada, com opt-out LGPD | §27 |
| RF12 | B2B (futuro) | orgs, multi-usuário, monitoramento palavra-chave/setor, relatórios | §19-20 |

Regras críticas: preço/limite/trial/grace **nunca no código** → collections `plans`/`feature_flags`; resumo = OpenAI só via Django; IDs de fonte + prompt_version salvos.

## 4. Matriz Free x Premium (parametrizável via feature_flags)
`personalizacao_avancada, alertas, resumo_personalizado, newsletter_personalizada, radar_avancado, historico_avancado, distribuicao` = limitada Free / completa Premium. Limites editáveis sem deploy.

## 5. RNF
Performance p95 <300ms API, SEO (Next SSR), LGPD (consent, export/delete, audit), acessibilidade WCAG 2.1 AA, observabilidade Otel+Sentry, i18n pt-BR, 70%+ coverage.

## 6. Data Model (Firestore)
`users{uid, plano, trial_ate}`, `plans{id, nome, preco, intervalo, trial_dias, grace_dias}`, `feature_flags{chave, free_limite, premium_limite}`, `subscriptions{user_id, plan_id, status, inicio, vencimento}`, `payments{...}`, `sources{...}`, `news{source_id, url, titulo, categoria}`, `events{news_ids[], resumo_id, relevancia}`, `summaries{event_id, texto, prompt_version, source_ids}`, `radar_snapshots{localidade_tipo, localidade_id, assuntos[]}`, `authors{user_id, status, diploma_url, selo}`, `posts{author_id, event_id}`, `comments{post_id, parent_id}`, `reports{alvo, motivo}`, `organizations{membros[], plano}` + `audit_logs`.

## 7. Fluxos chave
Credenciamento: solicitação → fila admin → aprova/reprova/pede info → notifica → selo. Assinatura: checkout → webhook → state machine → ativa/renova/grace/downgrade.

## 8. Critérios de aceite (ex)
- Admin altera preço em `plans` e checkout reflete sem deploy.
- Trocar `PAYMENT_PROVIDER` env alterna gateway sem mudar código cliente.
- ID Token inválido → 401; válido mas sem claim premium → 403 em recurso premium.
- Gateway fake → teste E2E completo sem rede externa.

## 9. Próximo passo
Aprovar este PRD (`/approve`) → architect gera ADRs + OpenAPI + `firestore.rules` finais.
