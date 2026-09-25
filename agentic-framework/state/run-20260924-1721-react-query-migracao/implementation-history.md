<!--
CONTRACT: implementation-history
DONO: executor (cria e adiciona entradas) / tester, remediator, historian (adicionam entradas)
QUANDO É CRIADO: junto com a primeira ação do executor sobre o implementation-contract.md.
PARA ONDE VAI A INSTÂNCIA: agentic-framework/state/run-20260924-1721-react-query-migracao/
NATUREZA: append-only durante a execução — cada entrada é uma iteração, nunca se edita uma entrada anterior.
-->

# Implementation History — 20260924-1721-react-query-migracao

## Iteração 1 — 2026-09-24T17:30:00-03:00 — executor (núcleo TanStack Query e telas públicas)

**O que foi feito:**

- Núcleo do runtime entregue conforme o contrato (seção A):
  `frontend/lib/query-client.ts` com `criarQueryClient()` por árvore cliente —
  o provider usa `useState`, portanto requisições SSR nunca compartilham
  cache; defaults público 60 s, gc 5 min, retry 1,
  `refetchOnWindowFocus: false`, `refetchOnReconnect: true`, sem dehydrate,
  hydrate nem persistência.
- `frontend/app/providers.tsx` recebeu `QueryClientProvider` preservando a
  ordem dos providers existentes (ThemeProvider → QueryClientProvider →
  TooltipProvider → ToastProvider → DeviceProvider → AuthProvider) e a
  renderização do root, sem alterar headers/ISR.
- `frontend/lib/query-session.tsx`: `QuerySessionBoundary` cancela queries
  privadas e limpa todo o cache em memória no logout/troca de usuário; a
  chave privada contém somente `usuarioId`, nunca o token.
- `frontend/lib/query-keys.ts`: fábricas explícitas de chaves — não existe
  chave genérica que aceite token, e-mail ou o objeto de usuário; ambiente
  derivado de `NEXT_PUBLIC_API_BASE_URL` (permitido); credenciais permanecem
  no closure do `queryFn`.
- `frontend/lib/queries.ts`: hooks de leitura para feed/últimas notícias,
  planos, cobertura, radar (tendências/evolução/localidades com polling),
  community (publicações/publicação/comentários/perfil) e jornalista
  (solicitação/perfil, staleTime privado 15 s), além das invalidações
  `invalidarQueriesComunidade` e `invalidarQueriesRadarLocalidades`.
- `frontend/lib/premium.ts`: cache em módulo/localStorage removido;
  `usePremiumAtivo` passa a usar `useQuery` com `staleTime` 60 s e
  `queryKeys.premium.status()`, falha aberta (API offline = não bloqueia);
  `invalidarCachePremium` mantido como compatibilidade temporária para a
  tela Admin da etapa 2.
- Telas públicas migradas (seção C, Etapa 1): `app/planos/page.tsx`
  (`useQueryPlanos` + invalidação da query após assinatura),
  `app/radar/RadarClient.tsx` (tendências com polling 60 s, evolução e
  localidades salvas com staleTime privado 15 s, invalidação de localidades
  nas mutations),
  `components/home/UltimasNoticias.tsx` (`useQueryFeedUltimasNoticias` com
  `initialData` do SSR, polling via `refetchInterval`, `refetchIntervalInBackground: false`),
  `app/comunidade/page.tsx` (query com filtros dinâmicos na query key —
  tab/categoria/tipo/busca mudam a chave e a query refetch sozinha; botão
  Atualizar usa `refetch`; fallback mock filtrado client-side quando
  `isError`; mutations invalidam via `invalidarQueriesComunidade`;
  localStorage de grupos/seguindo preservado como efeito local) e
  `app/comunidade/[id]/page.tsx` (`useQueryPublicacaoComunidade`; efeitos
  locais de localStorage preservados).
- Correção de tipos em `invalidarQueriesComunidade`: as tuplas readonly
  vindas de query-keys não aceitam `push` em array mutável; o construtor de
  chaves passou a montar o resultado com elementos `unknown[]` por chave e
  cast controlado, preservando o comportamento de invalidação.
- Decisões de negócio confirmadas pelo solicitante nesta sessão: executar
  Etapa 1 + Etapa 2 na mesma sessão; 404 de solicitação de credenciamento =
  dado nulo (estado normal, não erro); criar
  `frontend/scripts/verificar-query-client.mjs` como check de CI.

**Validação:**

- `npx tsc --noEmit` (frontend/) — passou, zero erros.
- `npm run build` (frontend/) — compilou e gerou 59/59 páginas estáticas,
  sem erro; nenhuma dependência órfã reintroduzida (sem
  `@tanstack/react-table`, sem `embla-carousel-react`).

**Observações:**

- `app/comunidade/page.tsx` combinava filtros, debounce, fallback mockado e
  mutations; a migração preservou todos os estados de loading/erro/fallback
  e as mensagens, trocando somente o carregamento manual de
  `api.obterPublicacoes` pela query com filtros dinâmicos.

## Iteração 2 — 2026-09-25T00:00:00-03:00 — executor (Etapa 2 Admin + validação central)

**O que foi feito:**

- Etapa 1 concluída por subagente: `app/jornalista/status/page.tsx` migrado
  para `useQuerySolicitacaoJornalista`/`useQueryPerfilJornalista` com
  `usuarioId = usuario?.id ?? 0`, hooks chamados incondicionalmente antes dos
  returns (rules-of-hooks OK), loading via `isLoading`, 404 convertido em
  null pela api tratado como estado normal ("Nenhuma solicitacao
  encontrada") e erro de rede no parágrafo de falha — decisão de negócio
  aprovada pelo solicitante. Gate e UI preservados.
- `frontend/scripts/verificar-query-client.mjs` criado: Node puro ESM, 8
  verificações ([OK]/[VIOLAÇÃO], exit 1 em violação), caminhos via
  `import.meta.url`, remoção de comentários preservando strings (o
  query-client.ts menciona dehydrate/hydrate em comentário), token detectado
  por word-boundary no código sem comentários, queryKey extraído por bloco
  de useQuery, varredura recursiva de frontend/app/**. Caminho negativo
  testado (persistQueryClient em arquivo temporário → VIOLAÇÃO + exit 1).
- Etapa 2 (Admin) por subagente: hooks Admin adicionados a
  `frontend/lib/queries.ts` com `STALE_TIME_DECISAO_MS = 0` (telas de
  decisão): useQueryAdminFila (polling opcional + placeholderData),
  useQueryAdminUsuarios/Assinaturas/Denuncias (gate por busca submetida),
  useQueryAdminPlanos/Limites/Fontes/RoboConfig/RoboExecucoes,
  useQueryAdminCentralInteligencia, useQueryAdminDestaques/Regras/Sistema —
  todos com `enabled: habilitadoAdmin(token, usuarioId)` e token no closure
  do queryFn. Chaves Admin adicionadas a `frontend/lib/query-keys.ts` (sem
  token/PII). Telas Admin migradas: assinaturas, configuracoes/FontesIsland,
  configuracoes/PremiumFlagIsland, fila, limites, moderacao, planos,
  usuarios. O subagente falhou por erro de conexão (ECONNRESET) antes de
  concluir os 3 últimos arquivos; o trabalho parcial foi validado e
  concluído pelo orquestrador.
- Correção do orquestrador nos 3 arquivos restantes:
  `app/admin/page.tsx` (stats do dashboard derivadas de 7 hooks Admin —
  cache compartilhado com as telas de detalhe/dedupe; useEffect manual
  removido), `app/admin/metricas/page.tsx` (Central/destaques/regras via
  hooks; fallback silencioso `.catch(() => [])` preservado como
  `data ?? []`; mutations invalidam queryKeys.admin.destaques/regras) e
  `app/admin/robos/page.tsx` (fontes/config/execuções via hooks com padrão
  de sincronização query → estado local para updates otimistas; fallback
  mock de fontes em erro preservado; `carregarFontes`/`carregarCfg`/
  `carregarExecs` redefinidos como wrappers de invalidação com os mesmos
  nomes, mantendo mutations e botões inalterados; banner de erro mostra
  erro de mutation ou de carregamento das queries).
- Fix de typo em `app/admin/planos/page.tsx` (`setErr` → `setEErr`).
- Limpeza de 5 arquivos de backup órfãos em frontend/app/ e
  frontend/components/ (artefatos de tentativas de migração desta sessão).
- Smoke HTTP inicial contra `next dev` stale retornou 500 por cache
  inconsistente (`Cannot find module './vendor-chunks/tailwind-merge.js'` —
  `npm run build` sobrescreveu `.next` com o dev ativo); não é problema de
  código. Ambiente reiniciado e smoke reexecutado contra o build de
  produção.

**Validação:**

- `npx tsc --noEmit` (frontend/) — passou, zero erros.
- `node frontend/scripts/verificar-query-client.mjs` — 8/8 OK, exit 0; 27
  hooks de leitura, todos com queryKey de queryKeys.*, sem token.
- `npm run build` — compilou e gerou 59/59 páginas, incluindo as 10 rotas
  Admin; sem dependências órfãs reintroduzidas.
- Smoke HTTP (produção) — 25/25 rotas com HTTP 200 contra o servidor standalone do build de produção (home, comunidade, comunidade/[id], planos, radar, jornalista/status, as 10 rotas Admin e demais rotas principais: ao-vivo, arquivo, buscar, editorias, favoritos, noticia/[id], minha-conta, personalizar, login, cadastro). Os 404/500 do smoke inicial foram causados por cache stale de `.next` compartilhado entre dev e produção, resolvidos com limpeza de `.next` e rebuild.

## Iteração 3 — 2026-09-25T12:20:00-03:00 — executor (follow-up: check na esteira de CI)

**O que foi feito:**

- Follow-up do report endereçado: o check de política do query client não
  estava na esteira de CI (o critério 13 do contrato exige "o CI executa o
  mesmo check"). `.github/workflows/ci.yml` recebeu o step
  "Verificar política de cache do query client (TanStack Query)" no job
  `frontend-build`, seguindo o padrão do `verificar-datas-tz.mjs`
  (checagem estática rápida, fail fast antes do tsc/build). Escopo decidido
  pelo solicitante: apenas o check faltante (sem smoke HTTP no CI e sem
  suíte de unidade no frontend nesta esteira).
- A esteira de CI já cobria o restante: `backend-tests` (PostgreSQL 16 +
  pytest + `--cov-fail-under=80`) e `frontend-build` (`npm ci`,
  verificar-datas-tz em TZ UTC/Tokyo, `tsc --noEmit`, `npm run build`), com
  triggers push/PR em develop+main e `workflow_call` como gate `verify` dos
  deploys.

**Validação:**

- YAML do ci.yml válido (parse python-yaml; step na ordem esperada:
  npm ci → datas-tz → query-client → tsc → build).
- `node frontend/scripts/verificar-query-client.mjs` — exit 0 (8/8),
  simulando o step do runner localmente.
