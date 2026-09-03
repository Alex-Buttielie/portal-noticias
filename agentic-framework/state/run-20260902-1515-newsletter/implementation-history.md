# Implementation History — 20260902-1515-newsletter

## Iteração 1 — 2026-09-02 — orchestrator agindo como executor

App `newsletter/`: `InscricaoNewsletter` (padrão/categoria/personalizada — personalizada gated via `gating.has_feature`), `EnvioNewsletter` (log de execução), reaproveita `feed.services.itens_publicaveis` para montar conteúdo (não duplica lógica de "o que é publicável"), descadastro por token sem login, task Celery resiliente a falha individual. 2 endpoints, 4 testes (incluindo verificação real de `mail.outbox`).

**Status:** 6/6 critérios implementados. Validação: não realizada.

**Arquivos:** `backend/newsletter/` (novo); `backend/config/settings.py` (`INSTALLED_APPS`, `CELERY_BEAT_SCHEDULE`), `urls.py`.
