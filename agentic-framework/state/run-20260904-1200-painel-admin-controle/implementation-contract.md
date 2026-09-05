# Implementation Contract — 20260904-1200-painel-admin-controle

## Metadados
- **run_id:** 20260904-1200-painel-admin-controle
- **Deriva de:** task-plan.md (20260904-1200-painel-admin-controle)
- **Versão do contrato:** 1

## O que deve ser construído
Painel de controle unificado em `frontend/app/admin/` com guarda 404 disfarçado e backend `api/admin/*` só-admin (404 para não-admin). Gestão completa: usuários, fila editorial (NewsCluster/NewsItem pendentes), planos/limites, assinaturas, moderação e métricas reaproveitadas.

## Áreas/arquivos esperados
- `backend/painel_admin/` (novo app Django: `views.py`, `urls.py`, `serializers.py`, `services.py`, `permissions.py`, `admin.py`)
- `backend/config/urls.py`, `backend/config/settings.py` (INSTALLED_APPS)
- `backend/gating/models.py` / `assinatura/models.py` / `catalogo_noticias/models.py` / `moderacao/models.py` (apenas leitura; auditoria via `LogAlteracaoAdmin` novo se necessário)
- `frontend/app/admin/layout.tsx`, `frontend/app/admin/page.tsx`, `frontend/app/admin/usuarios/page.tsx`, `frontend/app/admin/fila/page.tsx`, `frontend/app/admin/planos/page.tsx`, `frontend/app/admin/assinaturas/page.tsx`, `frontend/app/admin/moderacao/page.tsx`
- `frontend/app/admin/metricas/page.tsx` (adaptar guarda para notFound + manter dentro do layout)
- `frontend/app/not-found.tsx` (se não existir, garantir 404 genérico não vaze admin)
- `frontend/lib/api.ts` (novos helpers `api/admin/*`)
- `frontend/components/Header.tsx` (link Admin só para papel=admin, já existe métricas — expandir para /admin)
- `frontend/lib/auth-context.tsx` (sem mudança de lógica, só consumo)

## Interfaces afetadas
- Novos endpoints `api/admin/usuarios/`, `api/admin/usuarios/<id>/`, `api/admin/fila/`, `api/admin/fila/<id>/decisao/`, `api/admin/planos/`, `api/admin/limites/`, `api/admin/assinaturas/`, `api/admin/assinaturas/<id>/`, `api/admin/moderacao/denuncias/`, `api/admin/moderacao/denuncias/<id>/acao/` — todos com `IsAuthenticated` + checagem `papel=admin` retornando 404 para não-admin
- Frontend rotas `/admin`, `/admin/usuarios`, `/admin/fila`, `/admin/planos`, `/admin/assinaturas`, `/admin/moderacao`, `/admin/metricas`

## Critérios de aceite (técnicos, testáveis)
1. Dado usuário não autenticado, quando GET `api/admin/usuarios/` sem token, então status 401
2. Dado usuário autenticado com `papel=free` ou `premium`, quando GET qualquer `api/admin/*`, então status 404 (não 403) e body não menciona "admin"
3. Dado usuário `papel=admin`, quando GET `api/admin/usuarios/?search=<email>`, então retorna lista paginada filtrada por email/nome
4. Dado admin, quando PATCH `api/admin/usuarios/<id>/` com `{papel:"premium"}` ou `{is_active:false}`, então usuário alvo atualizado, resposta 200 e auditoria registrada
5. Dado admin, quando GET `api/admin/fila/?status=pendente`, então retorna clusters/itens pendentes paginados; quando POST `api/admin/fila/<id>/decisao/` com `{"acao":"aprovar"}`, então item/cluster muda para aprovado e aparece no feed
6. Dado admin, quando CRUD em `api/admin/planos/` e PATCH `api/admin/limites/<id>/`, então criação/edição persiste e loga antes/depois
7. Dado admin, quando GET `api/admin/assinaturas/?status=ativa`, então lista filtrada paginada; GET `api/admin/assinaturas/<id>/` retorna detalhe + histórico de pagamentos
8. Dado admin, quando GET `api/admin/moderacao/denuncias/?status=pendente` e POST ação, então denúncia muda de status e conteúdo alvo refletido
9. Dado usuário não-admin acessando `/admin` ou `/admin/*` no frontend, quando renderiza, então `notFound()` (404) sem revelar existência; dado admin, quando acessa, então vê layout com navegação para 6 seções

## Não-objetivos
- Remover ou substituir o Django Admin em `/admin/` (backend Django)
- Criar novos papéis além de free/premium/admin
- Exportação CSV/PDF ou novos gráficos além dos existentes em métricas
- Edição livre de conteúdo de notícias fora do fluxo aprovar/rejeitar

## Restrições técnicas
- **Performance:** paginação (page_size 20) em todas as listagens admin; sem N+1 (select_related/prefetch)
- **Segurança/privacidade:** todo endpoint admin retorna 404 para não-admin (disfarçado); sem exposição de password hash; sem listar token; LGPD audit trail em alterações sensíveis
- **Dependências permitidas:** sem nova dependência; reusar DRF, Next.js existentes
- **Estilo/convenções:** seguir `frontend/app/globals.css` tokens e componentes existentes; backend seguir padrão services/views/serializers dos apps atuais

## Definição de pronto (Definition of Done)
- [ ] Critérios de aceite implementados
- [ ] Testes escritos e passando (tester)
- [ ] Revisão de código aprovada, se exigida por `review-triggers.md` (reviewer)
- [ ] Documentação atualizada (documenter)
- [ ] `implementation-history.md` completo e coerente
