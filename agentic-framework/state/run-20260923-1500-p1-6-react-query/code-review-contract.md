# Code Review Contract — 20260923-1500-p1-6-react-query

## Metadados

- **run_id:** `20260923-1500-p1-6-react-query`
- **Escopo revisado:** `git diff -- frontend/app/providers.tsx frontend/lib/queries.ts frontend/lib/query-client.ts frontend/components/ui/carousel.tsx frontend/package.json frontend/package-lock.json`; 7 inserções e 987 remoções em 6 arquivos.
- **Contrato de referência:** `implementation-contract.md`, `implementation-history.md` e `task-plan.md` da própria run.
- **Artefato adicional:** `documentation-update.md` não existe nesta pasta.
- **Gatilho aplicado:** diff acima de ~300 linhas, previsto em `agentic-framework/prompts/review-triggers.md:15`.
- **Método:** leitura do diff isolado; busca exaustiva em fontes/configurações do frontend; comparação do `HEAD` em diretório temporário; `npm ci`, `npm ls`, `npx tsc --noEmit` e build limpo do Next.js; comparação de chunks JS.
- **Escopo de outras runs:** ignorado; arquivos frontend inalterados foram lidos somente como evidência de referências/providers, e nenhum diff fora dos seis caminhos foi revisado.

## Findings

### Finding 1 — nit (follow-up/documentação): a futura migração deve explicitar a reintrodução da camada removida

- **Arquivo/linha:** `agentic-framework/state/run-20260923-1500-p1-6-react-query/implementation-history.md:86-87` e `run-state.json:73-75`.
- **Evidência:** o follow-up registra a migração dos 22 sites, `staleTime`, dehydration/hydration e revalidação, mas não diz explicitamente que `@tanstack/react-query`, `QueryClientProvider` e o arquivo removido `queries.ts` serão reconstruídos/reavaliados caso a alternativa A seja aprovada.
- **Impacto:** não há regressão no código atual; há apenas risco de uma run futura tentar reutilizar hooks já apagados sem planejar a dependência, o provider e as query keys novamente.
- **Correção sugerida:** ao abrir a run de migração, explicitar no contrato que a reintrodução da dependência/provider é parte do desenho e que os 64 hooks antigos não são contrato de API; não é necessário reter código morto nesta run.

## Verificações de risco de regressão

### 1. Prova de código morto

- Varredura exaustiva de todos os arquivos presentes sob `frontend`, versionados ou não (incluindo `app/admin`, `app/comunidade`, `components/*` e `lib/*`, excluindo apenas `.next` e `node_modules`) encontrou **zero** referências a `@/lib/queries`, `lib/queries`, `queries.ts`, `query-client`, `QueryClient`, `obterQueryClient`, `@tanstack/react-query`, `@tanstack/react-table`, `useQuery` ou `useInfiniteQuery`.
- No `HEAD` anterior, o parser encontrou **64 exports** de hooks em `frontend/lib/queries.ts`; a busca de cada nome fora do próprio arquivo encontrou **zero** consumidores. A busca de imports/requires do módulo fora dele também foi vazia.
- Portanto, a afirmação de 0 imports e 64 hooks exportados sem uso é reproduzível; `tsc` e o build não estão apenas escondendo um consumidor estático.

### 2. `carousel.tsx`, `components.json` e registry

- No `HEAD`, `embla-carousel-react` e os símbolos `Carousel*` apareciam somente no próprio `frontend/components/ui/carousel.tsx` e no lockfile; não havia importador de componente.
- `frontend/components.json:1-18` é configuração do CLI shadcn (schema, estilo e aliases), não um manifesto/registry de componentes, e não contém `carousel`; não foi encontrado arquivo de registry no frontend.
- A remoção é reversível (histórico do arquivo e registry do shadcn) e não há consumidor de runtime quebrado. A decisão de apagar o wrapper foi documentada em `implementation-history.md:17-25`.

### 3. Providers e Suspense

- `frontend/app/providers.tsx:18-27` preserva a ordem e todos os providers relevantes: `ThemeProvider` → `TooltipProvider` → `ToastProvider` → `DeviceProvider` → `AuthProvider`; somente `QueryClientProvider` e seu singleton foram removidos.
- `frontend/components/ToastProvider.tsx:4-9` continua renderizando `<Toaster />`; o provider não foi confundido com o ToastProvider.
- `frontend/app/layout.tsx:59-71` mantém `Providers` e o `<Suspense>` ao redor de `AnalyticsTracker`; `AnalyticsTracker.tsx:22-30,53-79` usa `useSearchParams`/`useEffect` normalmente.
- Não existe `useSuspenseQuery`/`useSuspense` no código; os hooks de navegação do Next não dependem do `QueryClientProvider`. O build limpo gerou 59/59 páginas sem erro de hidratação/prerender.

### 4. Lockfile e dependências

- `npm ci` a partir do diretório frontend terminou com exit 0 e instalou 176 pacotes; `npm ls --depth=0` e `npm ls --all` terminaram com exit 0, sem `invalid`, `missing` ou `extraneous`.
- A raiz de `package-lock.json` coincide com `package.json` (37 dependências e 4 devDependencies, mesmos conjuntos e versões); as três dependências removidas e seus pacotes transitivos exclusivos não aparecem no lock.
- `npm explain` não encontrou dependência atual para `use-sync-external-store`, `@tanstack/store`, `@tanstack/react-store`, `@tanstack/table-core`, `embla-carousel` ou `@tanstack/query-core`; o build confirma que nenhuma dessas remoções foi necessária por outro consumidor.
- `npx tsc --noEmit` e `npm run build` limpo passaram. O aviso de vulnerabilidade do Next e o warning de versão são pré-existentes e não foram tratados como regressão desta run.

### 5. Ganho real e decisão A-vs-B

- A comparação independente de builds limpos (mesmo `HEAD` contra a working tree) reduziu o total de chunks de **1.921.881 para 1.890.892 bytes** e o gzip de **584.148 para 574.620 bytes**; o chunk de 43.746 bytes que continha a implementação do React Query desapareceu. O First Load JS compartilhado arredondado permaneceu em 87,2 kB, coerente com o histórico: o ganho é principalmente no total de chunks, não no First Load compartilhado.
- A alternativa A não é uma troca mecânica: os 22 sites de carregamento aparecem em 15 arquivos e combinam filtros, polling, mutations, fallbacks, token e hidratação. Uma migração parcial criaria duas políticas de loading/erro e exigiria decidir invalidação, query keys, SSR e revalidação contra o cache de backend de 45 s.
- A alternativa B é tecnicamente sólida para o escopo desta run: remove um provider sem consumidores, 64 hooks sem importadores e dependências órfãs, sem tocar nas chamadas atuais a `lib/api.ts`; a única perda real é o blueprint de queries, que é reutilizável apenas hipoteticamente e está coberto pelo follow-up de migração.

## Escopo e qualidade do diff

- `git diff --name-only -- frontend` retornou exatamente os seis caminhos autorizados; não há outro arquivo frontend modificado pela working tree que pudesse ser atribuído à run.
- O diff de `providers.tsx` altera somente imports e o wrapper do `QueryClientProvider`; o lockfile contém somente as remoções esperadas; `git diff --check` passou.
- Não há finding de blocker, major ou minor. O nit acima é não bloqueante e não exige alterar o código desta run.

## Resumo quantitativo

| Severidade | Quantidade |
|---|---:|
| blocker | 0 |
| major | 0 |
| minor | 0 |
| nit | 1 |

## Veredito

**approve_with_comments**

A run pode ser aprovada: não há consumidor esquecido, dependência transitiva necessária, provider acidentalmente removido ou corrupção do lockfile; `npm ci`, TypeScript e build de produção passaram. O único comentário é tornar explícita, na run futura de cache, a reconstrução da dependência/provider e a revisão dos hooks apagados; a decisão B é a de menor risco para o estado atual.
