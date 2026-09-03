# Implementation History — 20260902-1517-landing-lista-espera

## Iteração 1 — 2026-09-02 — orchestrator agindo como executor

App `landing/`: `InscricaoListaEspera` (idempotente por e-mail via `get_or_create`, consentimento obrigatório), 1 endpoint público, segmentação via filtros nativos do Django admin (sem endpoint dedicado — suficiente para o critério de aceite 3). 3 testes.

**Status:** 4/5 critérios de backend implementados (1-4). **Critério 5 (página `frontend/app/lista-de-espera/page.tsx`) NÃO implementado nesta iteração** — dado o volume de módulos restantes do BRD, priorizei fechar o backend de todos os módulos primeiro; frontend desta e das demais páginas novas fica como follow-up consolidado.

**Validação:** não realizada (mesma limitação de sessão).

**Arquivos:** `backend/landing/` (novo); `backend/config/settings.py`, `urls.py`.
