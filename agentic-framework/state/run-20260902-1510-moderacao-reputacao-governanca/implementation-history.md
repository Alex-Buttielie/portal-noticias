# Implementation History — 20260902-1510-moderacao-reputacao-governanca

## Iteração 1 — 2026-09-02 — orchestrator agindo como executor

App `moderacao/`: `Denuncia` (ContentType genérico — funciona para `comunidade.Comentario`/`Publicacao` sem import cruzado), `AcaoModeracao`, `RecursoModeracao`, `Reputacao`+`ReputacaoEventoLog` (baseline 100, nível calculado por faixa), `PaginaEditorial`. 6 endpoints, `IsModeradorOuAdmin` (simplificação: usa `papel=admin`, já que `identidade.User` não tem papel de moderador dedicado — documentado para trocar fácil depois). Migration manual com dependência de `contenttypes`, 5 testes.

**Decisões:**
- `aplicar_acao` recusa `aplicado_por=None` — garante estruturalmente que reputação/denúncia nunca decidem sozinhas (BRD §15, critério 6).
- Delta de reputação por tipo de ação como constante de módulo única (`DELTA_POR_TIPO_ACAO`), não espalhada — fácil de recalibrar.
- `comunidade.services.denunciar` (import tardio, escrito no run anterior) agora resolve de verdade — `comunidade` + `moderacao` juntos fecham o ciclo denúncia → fila → ação → reputação.

**Status:** 7/7 critérios implementados.

**Validação:** não realizada (mesma limitação de sessão).

**Arquivos:** `backend/moderacao/` (novo); `backend/config/settings.py`, `urls.py`.
