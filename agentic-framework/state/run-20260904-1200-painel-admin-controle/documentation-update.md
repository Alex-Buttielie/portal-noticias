# Documentation Update — 20260904-1200-painel-admin-controle

## Resumo
Painel /admin gestão completa com 404 disfarçado para não-admin.

## Mudanças aplicadas

### README.md
- Adicionada linha na tabela de páginas: `/admin` (Visão geral), `/admin/usuarios`, `/admin/fila`, `/admin/planos`, `/admin/assinaturas`, `/admin/moderacao`, `/admin/metricas`.
- Adicionada tabela de endpoints `painel_admin` (`/api/admin/usuarios/`, `/api/admin/fila/`, `/api/admin/planos/`, `/api/admin/limites/`, `/api/admin/assinaturas/`, `/api/admin/moderacao/denuncias/`) com nota de 404 disfarçado e paginação.

### ARCHITECTURE.md §4 RBAC
- Documentado que `api/admin/*` usa `IsAdmin404` (404 para não-admin, não 403) e que frontend `app/admin/layout.tsx` usa `notFound()`.

## Mudanças não aplicadas (adiadas)
- Nenhuma.

## Validação
- Links conferidos contra `backend/painel_admin/urls.py` e `frontend/app/admin/*`
