# Task Plan — 20260902-1517-landing-lista-espera

Spec: `agentic-framework/specs/landing-lista-espera.md`. Formato conciso.

## Objetivo
App `landing`: modelo de lista de espera (nome, e-mail, interesses, localidade, canal, consentimento), endpoint público de cadastro, endpoint admin de segmentação/exportação. Página web (Next.js) simples de captação.

## Critérios de aceite (técnicos)
1. `POST /api/landing/lista-espera/` (público, sem autenticação) cria um registro com data de entrada.
2. E-mail duplicado não cria segundo registro (idempotente, mensagem clara).
3. Admin consegue filtrar/segmentar por interesse e localidade (Django admin `list_filter`/`search_fields` já resolve isso sem endpoint dedicado).
4. Consentimento de comunicação obrigatório (mesmo padrão de `identidade` — sem aceite, requisição é rejeitada).
5. Página `frontend/app/lista-de-espera/page.tsx` com formulário funcional consumindo o endpoint acima (mesma ressalva de validação por execução do run de frontend anterior).
