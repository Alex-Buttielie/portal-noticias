# Report — 20260923-1500-p1-6-react-query

## Objetivo

Remover a camada de cache de cliente morta do frontend e as dependências órfãs, sem introduzir uma migração parcial que alterasse loading, erro, fallback, estados vazios, polling ou hidratação. A run também deveria medir a remoção de imports namespace de `api` e preservar a coerência do manifesto, lockfile e documentação.

## Decisão A-vs-B

A **alternativa B — remover a camada não consumida** foi escolhida com base no inventário reproduzível:

- `frontend/lib/queries.ts` continha **64 hooks sem consumidores** (28 de leitura e 36 de mutation).
- A busca encontrou **0 imports** de `@/lib/queries` fora do próprio arquivo; nenhum hook tinha consumidor.
- O inventário encontrou 22 sites de carregamento de backend em 15 arquivos, com filtros, polling, mutations, fallbacks, token e hidratação. A alternativa A exigiria uma migração não mecânica e criaria uma segunda política de estados, em vez de remover um runtime morto.
- A comparação de builds registrou aproximadamente **24–31 KB removidos** no total de chunks, dependendo da contagem/identificação do build (a medição do executor registrou cerca de 30,7 KB raw; a medição independente do tester, cerca de 24,6 KB). O chunk de implementação do React Query deixou de ser emitido; o First Load JS compartilhado arredondado permaneceu em 87,2 kB.

A alternativa A fica reservada para uma run futura. Ela não pode assumir que a camada removida ainda existe: precisará reintroduzir a dependência, o provider e o desenho de queries antes de migrar os 22 sites.

## Entregas e arquivos

Alterados:

- `frontend/app/providers.tsx` — removidos o `QueryClientProvider`, o import do singleton e o wrapper correspondente; a ordem dos demais providers foi preservada.
- `frontend/package.json` — removidos `@tanstack/react-query`, `@tanstack/react-table` e `embla-carousel-react`.
- `frontend/package-lock.json` — atualizado de forma coerente, com as dependências diretas e transitivas exclusivas removidas.
- `frontend/lib/auth-context.tsx` e `frontend/lib/cookie-consent.ts` foram avaliados em uma variante de imports nomeados; a variante foi revertida por não demonstrar ganho, e ambos terminaram sem diff.

Removidos por não terem consumidor:

- `frontend/lib/queries.ts` (779 linhas, 64 hooks);
- `frontend/lib/query-client.ts` (singleton usado apenas pelo provider);
- `frontend/components/ui/carousel.tsx` (wrapper shadcn sem consumidores, único código que importava Embla).

Nenhum backend, schema, API, fluxo de conteúdo, workflow ou configuração de Nginx foi alterado pela execução desta run; alterações preexistentes de outras runs foram preservadas. Não houve commit.

## Validação

- `npm ci` — exit 0; instalação reproduzível com 176 pacotes.
- `npm ls --depth=0` — os três pacotes removidos não aparecem.
- `npx tsc --noEmit` — exit 0, sem erros de tipos.
- `npm run build` — exit 0; `next build` gerou **59/59** páginas.
- Verificação de referências em `frontend/**/*.ts(x)` — zero referências ativas a `@/lib/queries`, `QueryClientProvider`, `obterQueryClient`, `@tanstack/react-query`, `@tanstack/react-table` ou `embla-carousel-react`.
- Smoke test do servidor standalone — `/`, `/comunidade`, `/autor/1`, `/planos`, `/radar` e `/noticia/1` responderam **HTTP 200**, sem `Application error`, `Module not found` ou `Cannot find module`.
- `git diff --check` — exit 0.

O frontend não possui suíte automatizada nem script `test`; essa limitação foi registrada. Não foi criada uma suíte artificial para esta limpeza. Como as chamadas existentes a `lib/api.ts` não foram alteradas, os branches de loading, erro, fallback, empty state e polling permanecem preservados.

## Documentação

`README.md` e `ARCHITECTURE.md` foram verificados e permaneceram intactos: não listam React Query nem as dependências removidas. O follow-up documental sobre a reconstrução da camada foi corrigido em `implementation-history.md`; os detalhes estão em `documentation-update.md`.

## Revisão

O `code-review-contract.md` registrou **approve_with_comments**, com **0 blockers, 0 majors, 0 minors e 1 nit**. O nit não bloqueante apontava que o follow-up da alternativa A não explicitava a reintrodução de `@tanstack/react-query`, do `QueryClientProvider` e a reavaliação dos hooks apagados. O follow-up foi atualizado e o nit está resolvido; não foi necessária remediação de código.

## Follow-ups

1. **Migração futura dos 22 sites:** abrir run dedicada com `staleTime` de 60 s, dehydration/hidratação SSR, revalidação contra o cache de backend de 45 s e testes de loading/error/empty/fallback. A alternativa A precisará **readicionar `@tanstack/react-query`**, reconstruir o `QueryClientProvider`/cliente e reavaliar os 64 hooks apagados, que não são contrato de API.
2. **Imports namespace de `api`:** reavaliar os **23 imports namespace** restantes com profiling por rota; a variante de imports nomeados medida nesta run não apresentou ganho.
3. **Vulnerabilidades do npm:** `npm ci` reportou 2 vulnerabilidades (1 high e 1 critical) e um warning de Next 14.2.15; são preexistentes e permanecem fora do escopo desta limpeza.

## Artefatos

- `task-plan.md`
- `implementation-contract.md`
- `implementation-history.md`
- `code-review-contract.md`
- `documentation-update.md`
- `report.md` (este)
- `run-state.json` — fechado com `current_phase: done`
