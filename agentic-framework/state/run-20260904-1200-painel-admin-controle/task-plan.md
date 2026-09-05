# Task Plan — 20260904-1200-painel-admin-controle

## Metadados
- **run_id:** 20260904-1200-painel-admin-controle
- **Data de abertura:** 2026-09-04T12:16:00-03:00
- **Solicitado por:** humano (conversa 2026-09-04 — "preciso de um painel de controle para o site, apenas administradores poderão ter acesso")
- **Spec de origem:** sem spec dedicada (pedido direto); requisitos mapeados do BRD + ARCHITECTURE.md seções 3/4 + apps existentes

## Objetivo
Entregar um painel de controle em `frontend/app/admin/` restrito a `papel=admin`, com navegação e operações de gestão completa do site, retornando 404 disfarçado para qualquer não-admin (autenticado ou não), sem expor a existência da área administrativa.

## Escopo
### Dentro do escopo
- Layout `/admin` com sidebar/navegação, guarda de rota (404 disfarçado) e link visível só para admin no Header
- Gestão de usuários: listar/buscar, ver detalhe, alterar papel (free/premium/admin), ativar/desativar
- Fila editorial: listar clusters/itens com `status_revisao=pendente`, aprovar/rejeitar, ver detalhe e custo LLM do período
- Planos e limites: CRUD de `assinatura.Plan` e `gating.FeatureLimit` com auditoria
- Assinaturas: listar assinaturas com filtro por status/plano, ver detalhe e histórico de pagamentos
- Moderação: listar denúncias por status, ver detalhe, tomar ação (remover/restaurar/suspender), listar recursos
- Métricas: reaproveitar `/admin/metricas` existente dentro do novo layout (sem duplicar lógica), mantendo guarda 404
- Backend: endpoints `api/admin/*` só-admin com 404 disfarçado (não 403) para não-admin/autenticado sem permissão, e 401 para não-autenticado; paginação e busca onde fizer sentido
- Auditoria mínima: quem/quando/antes/depois para alterações de papel, plano e limite

### Fora do escopo (explicitamente)
- Django Admin (`/admin/` do Django): não será removido, apenas não é o painel solicitado; hardening adicional do Django Admin fica para outra run
- Criação de novos papéis (moderador, jornalista, B2B) além de `free/premium/admin` já existentes
- Edição direta de conteúdo de notícias/comunidade fora do fluxo de aprovação/rejeição
- Relatórios exportáveis (CSV/PDF) e gráficos novos além dos já existentes em métricas

## Suposições assumidas
- `User.papel` continua sendo a fonte de verdade para RBAC (ARCHITECTURE.md §3/§4); `is_staff` não é usado para guarda do painel Next.js — motivo: todo o projeto já usa `papel=admin` como critério (metricas, moderacao, gating)
- 404 disfarçado significa: backend retorna 404 para usuário autenticado não-admin (em vez de 403), e frontend chama `notFound()` para não-admin/autenticado sem permissão — 401 continua para não-autenticado sem token (comportamento de auth padrão) — motivo: requisito explícito do usuário na coleta
- Reaproveitar modelos/serializers existentes; não criar novas tabelas salvo auditoria se necessário — motivo: evitar migração desnecessária quando log já pode ser derivado

## Restrições
- Stack: Django+DRF (backend), Next.js (frontend), PostgreSQL; sem nova dependência sem aprovação no implementation-contract
- Segurança: nenhum endpoint admin pode vazar existência para não-admin (404, não 403); listagens paginadas; sem exposição de hash de senha
- LGPD: alterações de usuário devem ser auditáveis

## Divisão de trabalho
| Etapa | Agente responsável | Entrada esperada | Saída esperada |
|---|---|---|---|
| 1 | executor | implementation-contract.md | código backend+frontend + implementation-history.md |
| 2 | tester | implementation-contract.md | veredito passed/failed/blocked |
| 3 | reviewer (se `review-triggers.md` aplicar) | diff do executor | code-review-contract.md |
| 4 | remediator (se necessário) | code-review-contract.md | correções + revalidação |
| 5 | documenter | implementation-history.md | documentation-update.md + docs atualizadas |
| 6 | historian | todos os artefatos acima | report.md + entrada em HISTORY.md |

## Critérios de aceite (nível de negócio/produto)
1. Usuário não autenticado que acessa qualquer rota `/admin/*` vê 404 (não 403, não redirect para login que denuncie existência); usuário autenticado com `papel != admin` também vê 404
2. Usuário com `papel=admin` acessa `/admin` e vê navegação para: Usuários, Fila editorial, Planos & Limites, Assinaturas, Moderação, Métricas
3. Em Usuários, admin lista, busca por email/nome, vê detalhe, altera papel e ativa/desativa conta com feedback e auditoria
4. Em Fila editorial, admin vê itens/clusters pendentes, aprova ou rejeita, e a mudança reflete no feed público
5. Em Planos & Limites, admin cria/edita/desativa plano e edita limites de gating, com log de antes/depois
6. Em Assinaturas, admin lista assinaturas com filtro por status, vê detalhe e histórico de pagamentos
7. Em Moderação, admin lista denúncias, toma ação e a ação reflete no conteúdo denunciado
8. Em Métricas, o painel existente continua acessível só a admin, agora dentro do layout do painel e ainda com guarda 404
9. Todo endpoint `api/admin/*` responde 404 para usuário autenticado não-admin (não 403) e exige autenticação para não-autenticado

## Riscos identificados
| Risco | Impacto | Mitigação |
|---|---|---|
| Vazar existência do painel via 403/mensagem | alto | Backend 404 disfarçado + frontend notFound() para não-admin |
| Quebrar RBAC existente (metricas/moderacao) | alto | Reaproveitar checagem `papel=admin`; testes de regressão |
| Listagens sem paginação causarem carga | médio | Paginação padrão DRF em todos os endpoints admin |
| Auditoria incompleta de alterações sensíveis | médio | Log explícito (quem/quando/antes/depois) em papel/plano/limite |

## Dependências
- Auth por Token (`identidade`) e campo `User.papel` já existentes
- Apps `assinatura`, `gating`, `catalogo_noticias`, `moderacao`, `comunidade`, `metricas` já existentes — sem dependência externa nova
