# Task Plan — 20260902-1515-newsletter

Spec: `agentic-framework/specs/newsletter.md`. Formato conciso.

## Objetivo
App `newsletter`: inscrição (padrão/categoria/personalizada), envio periódico via Celery reaproveitando `EMAIL_BACKEND` já configurado, descadastro sem login via token.

## Critérios de aceite (técnicos)
1. Usuário autenticado se inscreve escolhendo `tipo` (padrão/categoria/personalizada) — personalizada exige `gating.has_feature(user, "newsletter_personalizada")`.
2. Conteúdo da newsletter reaproveita `feed.services.itens_publicaveis` (top itens recentes, opcionalmente filtrados por categoria/interesses do `User`).
3. Todo item da newsletter inclui link para a fonte original (mesma regra de atribuição já garantida em `catalogo_noticias`).
4. Descadastro funciona via `GET/POST /api/newsletter/descadastrar/?token=...` SEM exigir login.
5. Task periódica (`tasks.enviar_newsletters`) processa inscrições ativas e envia — não falha a execução inteira se o envio de UM usuário falhar (mesmo padrão de resiliência de `catalogo_noticias`).
6. Nunca envia para usuário sem consentimento (`user.consentimento_aceito_em` preenchido) ou com inscrição inativa.

## Suposições assumidas
- Token de descadastro gerado na criação da inscrição (`secrets.token_urlsafe`), armazenado no próprio registro — mesmo espírito dos tokens de `identidade/`, mais simples (não precisa expirar).
