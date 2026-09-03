# Implementation History — 20260902-1534-frontend-comunidade-credenciamento

## Iteração 1 — 2026-09-02 — orchestrator agindo como executor

`lib/api.ts` estendido com tipos/funções de `credenciamento` (incluindo suporte a `FormData` no cliente HTTP central, para upload de arquivo — `request()` agora detecta `body instanceof FormData` e evita fixar `Content-Type`, deixando o navegador gerar o boundary do multipart) e `comunidade`.

6 páginas novas: `/jornalista/solicitar`, `/jornalista/status`, `/comunidade`, `/comunidade/nova`, `/comunidade/[id]`, `/autor/[id]`. `Header.tsx` ganhou links de navegação para Comunidade e Jornalista.

**Lacuna de backend encontrada e corrigida:** faltava `GET /api/comunidade/publicacoes/<id>/` — só existia listagem. Adicionado `PublicacaoDetailView` em `comunidade/views.py` + rota + 2 testes (publicada é pública; rascunho não vaza para outro usuário). Registrado também em `agentic-framework/state/run-20260902-1506-comunidade-blog/implementation-history.md` (Iteração 2), já que é uma correção sobre aquele módulo.

**Status:** 6/6 critérios implementados. Validação: não realizada (mesma limitação de sessão — build do frontend nunca rodou, nem `pytest` do backend).

**Arquivos:** `frontend/lib/api.ts` (modificado); `frontend/app/jornalista/solicitar/page.tsx`, `frontend/app/jornalista/status/page.tsx`, `frontend/app/comunidade/page.tsx`, `frontend/app/comunidade/nova/page.tsx`, `frontend/app/comunidade/[id]/page.tsx`, `frontend/app/autor/[id]/page.tsx` (novos); `frontend/components/Header.tsx` (modificado); `backend/comunidade/views.py`, `urls.py`, `tests/test_sanity.py` (modificados).
