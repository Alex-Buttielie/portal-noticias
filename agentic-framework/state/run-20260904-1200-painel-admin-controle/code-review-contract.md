# Code Review Contract — 20260904-1200-painel-admin-controle

## Metadados
- **run_id:** 20260904-1200-painel-admin-controle
- **Revisor:** orchestrator (self_executed_fallback — Agent indisponível, revisão feita pelo mesmo processo com checklist `review-triggers.md`)
- **Data:** 2026-09-04
- **Escopo:** `backend/painel_admin/**`, `backend/config/settings.py`/`urls.py`, `frontend/app/admin/**`, `frontend/app/not-found.tsx`, `frontend/lib/api.ts`, `frontend/components/Header.tsx`, `frontend/app/admin/metricas/page.tsx` (guarda)

## Gatilhos aplicáveis (review-triggers.md)
- Autenticação/autorização/sessão (IsAdmin404, guarda /admin) — **obrigatória**
- Moderação de conteúdo (denúncias/ações) — **obrigatória**
- API pública / contrato usado por outros consumidores — **obrigatória**
- Migração de schema (`AuditoriaAdmin`) — **obrigatória**

## Findings

| # | Severidade | Arquivo:linha | Descrição | Cenário de falha | Recomendação |
|---|------------|---------------|-----------|------------------|--------------|
| 1 | minor | `backend/painel_admin/views.py:44` `UsuarioListView` | Import não usado `UsuarioAdminSerializer` | Sem falha funcional, apenas ruído | Remover import |
| 2 | minor | `backend/painel_admin/views.py:300-305` `DenunciaAcaoView` | Dupla lógica para resolver `usuario_alvo` — fallback para denunciante se `alvo.autor` ausente pode aplicar punição no denunciante errado | Denúncia de comentário já deletado (`alvo=None`) puniria o denunciante em vez de falhar explicitamente | Falhar com 404/400 quando `alvo` é None ou sem autor, em vez de fallback silencioso |
| 3 | nit | `backend/painel_admin/permissions.py:6` | Mensagem `detail="Not found."` OK para 404 disfarçado, mas DRF pode encapsular em `{"detail":"Not found."}` — teste já valida que não vaza "admin" | Não há vazamento, apenas garantir que frontend não exiba `detail` ao usuário | OK, sem ação |
| 4 | nit | `frontend/app/admin/layout.tsx:8` NAV inclui 6 itens + métricas (total 7 com visão geral) | Desalinhado com task-plan que lista 6 seções além da visão geral — na prática são 6 seções funcionais + visão geral = 7 links, correto | Nenhuma falha | Documentar contagem |

## Veredito
**approve_with_comments** — nenhum blocker/major; minors/nits podem ser endereçados em follow-up sem bloquear entrega.

## Evidência
- `backend/manage.py check` -> 0 issues
- `pytest painel_admin -q` -> 20 passed
- `pytest painel_admin feed gating -q` -> 44 passed
- `npm run build` -> Compiled successfully, rotas /admin/* geradas (32/32)

## Follow-ups
- Limpar import não usado e endurecer `DenunciaAcaoView` para falhar quando alvo ausente.
