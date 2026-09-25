<!--
CONTRACT: report
DONO: historian
QUANDO É CRIADO: no fechamento de cada execução (run).
PARA ONDE VAI A INSTÂNCIA: agentic-framework/state/run-<run_id>/report.md
-->

# Report — 20260924-1721-react-query-migracao

## Metadados
- **run_id:** 20260924-1721-react-query-migracao
- **Período:** 2026-09-24 17:21 → 2026-09-25 00:20
- **Tarefa:** Migrar os 22 sites de backend para cache de cliente com TanStack Query
- **Resultado final:** entregue

## Resumo executivo
O solicitante pediu a reintrodução de cache de cliente real com TanStack Query (alternativa A da run `20260923-1500-p1-6-react-query`), migrando os 22 sites de carregamento de backend inventariados em 15 arquivos, com política conservadora aprovada: memória-only, público staleTime 60 s, autenticado 15 s, telas de decisão 0 s, sem persistência, chaves sem token/PII e limpeza de cache privado no logout. Foi entregue o núcleo completo (query-client, provider, session guard, 16+ hooks de leitura, invalidações de mutations) e a migração das telas públicas/Community (Etapa 1) e Admin (Etapa 2). O plano original previa dois executores isolados (núcleo+público, depois Admin); nesta sessão ambas as etapas foram executadas em paralelo por subagentes com escopos de arquivos disjuntos, com validação central do orquestrador.

## Métricas
| Métrica | Valor |
|---|---|
| Iterações (implementação ↔ revisão/remediação) | 2 |
| Findings de revisão — abertos | 0 |
| Findings de revisão — resolvidos | 0 |
| Arquivos alterados | 22 da migração (17 frontend modificados + 4 novos em lib/ + 1 script de check) + artefatos de state; 1 correção adicional durante o review (comunidade/[id]) |
| Testes adicionados | 0 novos testes de unidade; 1 check de CI (verificar-query-client.mjs, 8 verificações) |
| Veredito final do tester | passed — 15/15 critérios de aceite validados com evidência (npm ls, inspeção de código, check 8/8, build 59/59, smoke 25/25, git diff --check) |
| Veredito final do reviewer | N-A — fase de reviewer pendente (revisão obrigatória por dependência externa, autenticação/dados privados, polling e volume) |

## Escopo entregue

### A. Runtime e provider seguros
- `@tanstack/react-query` ^5.102.8 reintroduzido (sem react-table/embla-carousel); `package-lock.json` atualizado.
- `frontend/lib/query-client.ts`: `criarQueryClient()` por árvore cliente (useState no provider, sem singleton de módulo), staleTime 60 s, gc 5 min, retry 1, `refetchOnWindowFocus: false`, `refetchOnReconnect: true`, sem persistência.
- `frontend/app/providers.tsx`: `QueryClientProvider` montado preservando a ordem dos providers e a renderização do root.
- `frontend/lib/query-session.tsx`: `QuerySessionBoundary` — cancela queries privadas e limpa o cache no logout/troca de usuário; token nunca em query key.

### B. Query keys e hooks
- `frontend/lib/query-keys.ts`: fábricas explícitas (público/privado), ambiente derivado de `NEXT_PUBLIC_API_BASE_URL`, `usuario.id` apenas em chaves privadas, token somente no closure do `queryFn`.
- `frontend/lib/queries.ts`: 16+ hooks de leitura (feed/últimas notícias, planos, cobertura, radar tendências/evolução/localidades, community publicações/publicação/comentários/perfil, jornalista solicitação/perfil, Admin métricas/fila/limites/robôs/fontes/planos) + invalidações (`invalidarQueriesComunidade`, `invalidarQueriesRadarLocalidades`) + `usePremiumAtivo` migrado de localStorage para query (fail-open).

### C. Migração das telas
- **Etapa 1 (público/Community):** `comunidade/page.tsx` (query com filtros dinâmicos na query key, refetch no botão Atualizar, fallback mock filtrado client-side em erro, invalidação nas mutations), `comunidade/[id]/page.tsx`, `planos/page.tsx`, `radar/RadarClient.tsx`, `components/home/UltimasNoticias.tsx` (polling via refetchInterval), `lib/premium.ts`, `jornalista/status/page.tsx` (404 = dado nulo, decisão aprovada pelo solicitante).
- **Etapa 2 (Admin):** admin/page.tsx (stats via 7 hooks Admin, cache compartilhado com detalhes), admin/fila/page.tsx, admin/limites/page.tsx, admin/metricas/page.tsx (Central/destaques/regras, fallback silencioso preservado), admin/planos/page.tsx, admin/robos/page.tsx (sincronização query → estado local, updates otimistas e fallback mock preservados), admin/assinaturas/page.tsx, admin/usuarios/page.tsx, admin/moderacao/page.tsx, admin/configuracoes/FontesIsland.tsx, admin/configuracoes/PremiumFlagIsland.tsx (invalidação de queryKeys.premium.status)

### D. Check de CI
- `frontend/scripts/verificar-query-client.mjs`: valida staleTimes da política, ausência de persistência, chaves sem token; exit 1 em violação. 8/8 verificações OK, exit 0 (65 arquivos varridos; caminho negativo testado com persistQueryClient → VIOLAÇÃO + exit 1)

## Validações finais
| Validação | Resultado |
|---|---|
| `npx tsc --noEmit` | passou, zero erros |
| `npm run build` (páginas) | compilou e gerou 59/59 páginas (incluindo as 10 rotas Admin), sem erro |
| Smoke HTTP | 25/25 rotas com HTTP 200 contra o servidor standalone do build de produção (home, comunidade, comunidade/[id], planos, radar, jornalista/status, 10 rotas Admin e demais rotas principais) |

## Linha do tempo resumida
- 2026-09-24 17:21 — abertura do run; política conservadora aprovada pelo solicitante.
- 2026-09-24 17:25 — início da implementação (Etapa 1: núcleo + telas públicas/Community).
- 2026-09-24/25 — núcleo entregue: query-client, provider, session guard, queries.ts/query-keys.ts, premium.ts.
- 2026-09-24/25 — telas migradas: planos, Radar, UltimasNoticias, comunidade (lista + detalhe).
- 2026-09-24/25 — fix de tipos em `invalidarQueriesComunidade` (arrays readonly de query-keys).
- 2026-09-24/25 — decisão do solicitante: executar Etapa 1 + Etapa 2 nesta sessão; 404 = dado nulo; criar check de CI.
- 2026-09-24/25 — subagentes em paralelo: Etapa 1 (jornalista/status + verificar-query-client.mjs) e Etapa 2 (hooks Admin + telas Admin).
- 2026-09-25 00:20 — validações centrais e fechamento.

## Desvios do plano original
- O task-plan previa dois executores isolados sequenciais (Etapa 1 depois Etapa 2); nesta sessão, a pedido do solicitante, ambas as etapas rodaram em paralelo por subagentes com escopos disjuntos, validadas centralmente.
- O script `verificar-query-client.mjs` não existia; foi criado nesta sessão (decisão do solicitante).
- `next start` não funciona com a configuração `output: standalone` do projeto — o smoke de produção usou `node .next/standalone/server.js` com static/public copiados para o standalone. O smoke inicial contra `next dev` stale retornou 404/500 por cache `.next` compartilhado entre dev e produção (`Cannot find module './vendor-chunks/tailwind-merge.js'`), resolvido com limpeza de `.next` e rebuild — não era problema de código.

## Follow-ups / pendências
- 1) Fase de tester independente do run (suíte completa, coverage 88.86% baseline). 2) Fase de reviewer (gatilhos: dependência externa, autenticação/dados privados, polling, volume). 3) Incluir verificar-query-client.mjs no pipeline de CI. 4) Commit da migração. 5) Documentação viva (ARCHITECTURE/PROD_DECISOES) com a política de cache final.

## Artefatos desta execução
- task-plan.md
- implementation-contract.md
- implementation-history.md
- code-review-contract.md (se aplicável)
- documentation-update.md (se aplicável)
