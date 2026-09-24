# Implementation History — 20260923-1500-p1-6-react-query

## Decisão executada

**Alternativa B — remover a camada de cache de cliente morta.** Não houve migração parcial para `useQuery`/`useInfiniteQuery` nesta run.

A decisão não foi uma suposição:

- Inventário AST dos fontes: **77 chamadas a `useEffect`**; **22 sites de carregamento de backend em 15 arquivos**. Esses sites usam funções auxiliares (`useCallback`) e efeitos de polling, não apenas `fetch` literal. Os 15 arquivos são: `app/admin/configuracoes/FontesIsland.tsx`, `PremiumFlagIsland.tsx`, `app/admin/page.tsx`, `fila/page.tsx`, `limites/page.tsx`, `metricas/page.tsx`, `planos/page.tsx`, `robos/page.tsx`, `app/comunidade/[id]/page.tsx`, `app/comunidade/page.tsx`, `app/jornalista/status/page.tsx`, `app/planos/page.tsx`, `app/radar/RadarClient.tsx`, `components/home/UltimasNoticias.tsx` e `lib/premium.ts`.
- **0 chamadas `fetch(...)` literais dentro de `useEffect`**. O `fetch` de backend está centralizado em `frontend/lib/api.ts:74`; os efeitos chamam wrappers `api.*`/funções nomeadas.
- `frontend/lib/queries.ts` tem **779 linhas e 64 hooks exportados**: 28 de leitura (27 `useQuery` + 1 `useInfiniteQuery`) e 36 de mutation. Nenhum arquivo importa `@/lib/queries`; portanto, **zero hooks estão em uso**.
- Há **18 dos 22 sites**, em **12 arquivos**, com algum endpoint coberto por um hook de leitura existente; os 28 hooks de leitura cobrem 32 funções de API no total, mas essa cobertura não cobre o estado completo dos efeitos. Os 4 sites restantes e as mutations/fallbacks continuam sem uma migração mecânica. A home recebe dados no servidor e mantém polling local; `app/autor/[id]/page.tsx` é server component; comunidade combina filtros, debounce, fallback mockado, mutations e radar. Uma migração parcial criaria duas políticas de loading/erro e exigiria decidir invalidação, hidratação e staleTime sem eliminar o restante do trabalho.
- Como o backend agora tem cache de 45 s (P1-A), a alternativa A exigiria uma política explícita para não servir dado do cliente além desse horizonte. Nesta run, o cache de servidor permanece intocado e **não foi introduzido cache de cliente**.

A alternativa B é, portanto, a menor mudança que elimina custo e complexidade sem fingir que o cache compartilhado já está ativo. A migração completa fica como follow-up de uma run própria.

## O que mudou

- `frontend/app/providers.tsx`: removidos `QueryClientProvider`, `obterQueryClient` e o wrapper correspondente. A ordem dos providers restantes (`Theme`, `Tooltip`, `Toast`, `Device`, `Auth`) foi preservada; `QueryClientProvider` era apenas contexto sem markup, portanto não há mudança de SSR/hidratação; nenhuma chamada de dados ou estado de UI foi alterada.
- `frontend/lib/queries.ts` (779 linhas): removido. O grep final não encontrou importador nem referência de código.
- `frontend/lib/query-client.ts` (21 linhas): removido. O singleton existia somente para o provider removido.
- `frontend/components/ui/carousel.tsx` (43 linhas): removido após confirmar que o único import de `embla-carousel-react` era o próprio wrapper shadcn e que **nenhuma página/componente importava esse wrapper**. A confirmação corrige a premissa de que o pacote era literalmente órfão: o wrapper é que era código morto, e sua remoção permite remover o pacote pedido sem afetar um carrossel em uso.
- `frontend/package.json`: removidos `@tanstack/react-query`, `@tanstack/react-table` e `embla-carousel-react`.
- `frontend/package-lock.json`: regenerado com `npm uninstall`/`npm ci`; 10 entradas de pacotes (diretos e transitivas exclusivas) removidas, sem alterações de versão não relacionadas.
- `frontend/lib/auth-context.tsx` e `frontend/lib/cookie-consent.ts`: foram avaliados em uma variante de imports nomeados, mas o resultado foi medido e revertido (veja bundle abaixo); o diff final desses arquivos é zero. Não houve reescrita dos 23 imports namespace vivos.

Nenhum arquivo backend, `.github/workflows`, `infra/nginx`, schema, API ou fluxo de conteúdo foi alterado. Nenhum commit foi criado.

## Otimização de namespace imports — medição

Para responder ao ponto do bundle do root sem assumir ganho, foi feito um build limpo baseline em worktree separado e um build final limpo no diretório de trabalho. O baseline tinha:

- **1.921.891 bytes** de JS em `.next/static/chunks` (**584.149 bytes gzip**, 92 chunks);
- chunk `1030-54b3d7dc6f9b9720.js` de **43.746 bytes** (**13.769 bytes gzip**) contendo a implementação do React Query;
- First Load JS compartilhado: **87,2 kB**.

O build final, após a limpeza, tem:

- **1.891.180 bytes** de JS (**574.687 bytes gzip**, 92 chunks);
- **0** chunks contendo `QueryClient`, `queryKey`, `useQuery`, `react-query` ou `infiniteQuery`;
- First Load JS compartilhado: **87,2 kB** (o chunk React Query não fazia parte do shared-by-all; a redução de ~30,7 kB raw/~9,5 kB gzip aparece no total de chunks, não no First Load arredondado).

Os hashes podem variar entre worktrees por identificação do build; por isso o delta de bytes é tratado como aproximação de bundle, enquanto a ausência do chunk React Query e o First Load de 87,2 kB são as evidências estáveis.

A variante controlada com `auth-context.tsx` e `cookie-consent.ts` usando imports nomeados foi compilada no mesmo diretório antes do revert e produziu os mesmos **1.891.180 / 574.687** bytes e o mesmo First Load **87,2 kB** da versão namespace. Conclusão: não há ganho mensurável; os dois arquivos foram mantidos como estavam, evitando um diff sem benefício. Os 23 imports namespace restantes ficam para uma otimização futura com perfil de bundle por rota.

## Evidências de implementação e validação

### Dependências e referências

- `npm ci` → exit 0; instalou 176 pacotes após a limpeza.
- `npm ls --depth=0` → nenhum dos três pacotes removidos aparece.
- Grep final em `frontend/**/*.ts(x)` → zero referências a `@tanstack/react-query`, `@tanstack/react-table`, `embla-carousel-react`, `QueryClientProvider`, `obterQueryClient`, `@/lib/queries` ou `lib/queries`.
- `git diff --check` → exit 0.
- Checklist `agentic-framework/prompts/contract-checklist.md` → aprovado: os contratos preenchidos não têm placeholders; task-plan tem escopo dentro/fora, suposições, responsáveis e critérios de negócio; implementation-contract tem critérios dado/quando/então, não-objetivos e restrições; `run_id` e derivação estão rastreáveis.

### TypeScript e build

- Baseline: `npx tsc --noEmit` → exit 0.
- Final: `npx tsc --noEmit` → exit 0.
- Final: `npm run build` → exit 0, `next build` compilou e gerou **59/59** páginas.
- O build final manteve as rotas com os mesmos estados de renderização (estático/SSG/dinâmico) e não emitiu erro de módulo após a remoção.

### Verificação manual dos fluxos tocados

Foi iniciado o servidor standalone de produção (`PORT=44890 HOSTNAME=127.0.0.1 node .next/standalone/server.js`) e verificado por `curl` que as rotas carregam sem erro de aplicação:

- `/` → **200**;
- `/comunidade` → **200**;
- `/autor/1` → **200**;
- `/planos` → **200**;
- `/radar` → **200**;
- `/noticia/1` → **200**.

As respostas não continham `Application error`, `Module not found` ou `Cannot find module`. A API de backend pode não estar disponível neste ambiente; isso não altera a validação da remoção, que é estrutural/runtime de bundle. Como não foi feita alteração de fetching, os branches existentes de loading, erro, fallback, empty state e polling permanecem os mesmos.

## Testes

O frontend **não tem suíte de testes frontend**: `frontend/package.json` não possui script `test`, e a busca por `**/*.{test,spec}.{ts,tsx,js,jsx}` em `frontend` não encontrou arquivos. Não foi criada uma suíte artificial para esta limpeza; a validação contratada é `tsc --noEmit`, `npm run build`, verificações de grep/lockfile e a verificação manual das rotas acima. O tester registrou essa limitação no relatório da run.

## Run state e pendências

- Run: `20260923-1500-p1-6-react-query`.
- Contratos/task plan preenchidos e validados contra `agentic-framework/prompts/contract-checklist.md`; `run-state.json` validado contra `agentic-framework/schemas/run-state.schema.json`; o fechamento foi registrado em `status: closed`, `current_phase: done` (ver `run-state.json` e `report.md`).
- **Revisão obrigatória executada:** o diff remove 987 linhas (`queries.ts`, carousel e lockfile) e ultrapassa o gatilho de ~300 linhas, mesmo sendo código morto. O reviewer verificou referências indiretas, providers e lockfile e registrou `approve_with_comments`; o único nit foi resolvido no follow-up abaixo.
- **Follow-up 1:** se o negócio decidir adotar a alternativa A (migrar para cache compartilhado no cliente), abrir run separada para os 22 sites; a alternativa A precisará **reintroduzir `@tanstack/react-query`**, reconstruir/reintroduzir o `QueryClientProvider` (e o cliente correspondente) e **reavaliar os 64 hooks apagados** de `frontend/lib/queries.ts` — eles não são contrato de API —, além de definir `staleTime` de 60 s, dehydration/hidratação SSR, revalidação após o cache de backend de 45 s e testes de loading/error/empty/fallback.
- **Follow-up 2:** reavaliar os 23 imports namespace de `api` com profiling por rota; a variante de imports nomeados não demonstrou ganho.
- `npm ci` reportou 2 vulnerabilidades (1 high, 1 critical) e um warning de Next 14.2.15; são pré-existentes e fora do escopo desta limpeza.
- Nenhum commit realizado, conforme solicitado.
