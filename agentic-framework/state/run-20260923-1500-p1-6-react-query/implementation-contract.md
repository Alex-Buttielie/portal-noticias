# Implementation Contract — 20260923-1500-p1-6-react-query

## Metadados
- **run_id:** 20260923-1500-p1-6-react-query
- **Deriva de:** `task-plan.md` (20260923-1500-p1-6-react-query)
- **Versão do contrato:** 1

## O que deve ser construído

Aplicar a alternativa B, após o inventário de evidência: remover a abstração React Query não consumida e as dependências órfãs, sem migrar parcialmente os efeitos para uma segunda camada de estado. A implementação também deve medir e, se a medição justificar, substituir imports namespace de `api` por imports nomeados nos dois módulos que participam do shell do root.

A decisão está baseada no seguinte inventário reproduzível (23/09/2026, antes da edição):

- `frontend/lib/queries.ts` tem 779 linhas, 64 hooks exportados (28 de leitura: 27 `useQuery` + 1 `useInfiniteQuery`; 36 de mutation).
- A busca de imports encontra 24 arquivos com `import * as api` (incluindo `auth-context.tsx`, `cookie-consent.ts` e o próprio `queries.ts`), mas **zero** imports de `@/lib/queries` fora do próprio arquivo.
- A premissa de que o Embla não tinha import foi corrigida pela evidência: `components/ui/carousel.tsx` é o único importador, mas o próprio wrapper shadcn não tem nenhum consumidor no código. Esse wrapper é removido junto com o pacote, sem remover um carrossel em uso.
- A análise AST dos fontes encontra 77 chamadas a `useEffect`; 22 Effect/callback sites, distribuídos em 15 arquivos, invocam carregadores de backend (incluindo funções auxiliares chamadas pelo efeito). Desses, 18 sites em 12 arquivos têm pelo menos um endpoint coberto por um hook de leitura existente. Há 0 chamadas `fetch(...)` literais dentro de `useEffect`; o `fetch` de backend está centralizado em `lib/api.ts`.
- Os 22 pontos não são uma migração mecânica: combinam filtros, polling, mutações, fallbacks mockados, dependência de token e hidratação. Migrar só home/feed ou só comunidade exigiria criar uma segunda política de loading/erro e decidir como invalidar mutations; o perfil público já é server component.
- O build baseline passa (`tsc --noEmit` e `next build`); o relatório do build mostra 87,2 kB de First Load JS compartilhado. O chunk de 43.746 bytes que contém a implementação do React Query é removível quando o provider e os hooks saem.

Não será introduzido `useQuery`/`useInfiniteQuery` nesta run. O cache de backend de 45 s permanece no servidor; a futura migração deve ser uma run separada com dehydration/hydration, staleTime e revalidação testados.

## Áreas/arquivos esperados
- `frontend/package.json` — remover as três dependências órfãs.
- `frontend/package-lock.json` — regenerar/atualizar de forma consistente.
- `frontend/lib/queries.ts` — remover arquivo morto (somente se a busca final continuar sem consumidores).
- `frontend/lib/query-client.ts` — remover o singleton, que existe apenas para o provider.
- `frontend/app/providers.tsx` — remover `QueryClientProvider` e o import do singleton, preservando a ordem dos demais providers.
- `frontend/components/ui/carousel.tsx` — remover o wrapper shadcn não consumido; ele é a única referência de código a `embla-carousel-react` e, portanto, é necessário removê-lo para cumprir a limpeza do pacote.
- `frontend/lib/auth-context.tsx` e `frontend/lib/cookie-consent.ts` — medir uma variante com imports nomeados; se o ganho for marginal/negativo, manter o código original e registrar a medição (a implementação final não os altera).
- Artefatos desta run: `task-plan.md`, `implementation-contract.md`, `run-state.json` e `implementation-history.md`.
- Qualquer arquivo fora dessa lista deve ser justificado no histórico; não tocar backend, workflows ou Nginx.

## Interfaces afetadas
- Nenhuma API, schema, contrato de dados ou comportamento de autenticação é alterado.
- O `QueryClient` deixa de ser uma dependência de runtime; os componentes continuam chamando `lib/api.ts` diretamente.
- Tipos exportados por `lib/api.ts` não mudam. A variante de imports nomeados foi medida, mas revertida; os tipos e assinaturas de `auth-context.tsx` permanecem os mesmos.
- O lockfile deixa de declarar os três pacotes e suas dependências transitivas exclusivas.

## Critérios de aceite (técnicos, testáveis)
1. Dado um grep de `frontend/**/*.ts(x)` para `@/lib/queries`, `QueryClientProvider`, `obterQueryClient`, `@tanstack/react-query`, `@tanstack/react-table` e `embla-carousel-react`, quando a implementação terminar, então não haverá referências de código ativas aos itens removidos (somente comentários/artefatos de build, se houver).
2. Dado `frontend/package.json` e `frontend/package-lock.json`, quando `npm ls --depth=0` for executado após a limpeza, então os três pacotes removidos não estarão instalados nem declarados como dependências diretas.
3. Dado o conjunto atual de telas, quando `npx tsc --noEmit` for executado em `frontend`, então o processo termina com exit code 0 sem erros de tipos.
4. Dado o mesmo código, quando `npm run build` for executado em `frontend`, então `next build` completa a geração das 59 páginas e termina com exit code 0.
5. Dados os loads baseline e pós-mudança do build, quando os chunks compartilhados forem comparados, então o relatório deve registrar o delta e o motivo para manter ou não os imports nomeados no root.
6. Dado os fluxos de home, comunidade, perfil, planos, radar e páginas client-side com API, quando forem inspecionados, então continuam usando `lib/api.ts`/seus helpers e mantêm as mesmas branches de loading, erro, fallback, empty state e polling; esta run não adiciona nem remove chamadas de dados.
7. Dado que o repositório não possui suíte de testes frontend nem script `test`, quando a validação for encerrada, então a limitação deve estar registrada e a validação fica limitada a `tsc`, build e verificação manual/estática dos fluxos tocados.

## Não-objetivos
- Migrar `useEffect` para React Query, adicionar hydration/dehydration, invalidation ou `staleTime` nesta run.
- Alterar o TTL/cache do backend, endpoints, payloads, autenticação, autorização, LGPD, filtros ou UI.
- Reescrever os 23 imports namespace vivos restantes sem medição de ganho; a decisão será tomada por bundle e manutenibilidade.
- Tocar backend, `.github/workflows`, `infra/nginx`, migrations ou deploy.
- Criar uma suíte de testes nova ou adicionar dependências.

## Restrições técnicas
- **Performance:** remover runtime morto; não aumentar o First Load JS. Imports nomeados só permanecem nos pontos quentes se a medição justificar. Não prometer cache cliente nesta alternativa.
- **Segurança/privacidade:** nenhuma mudança em tokens, consentimento, dados pessoais ou chamadas autenticadas; preservar o best-effort de `cookie-consent.ts`.
- **Dependências permitidas:** nenhuma nova; remover apenas as três dependências explicitamente autorizadas.
- **Estilo/convenções:** manter TypeScript strict, imports ES modules e a estrutura de providers existente; comentários em português quando adicionados.
- **SSR/hidratação:** não introduzir estado client-side que renderize diferente no servidor; a remoção do provider não altera a árvore de DOM.
- **Revisão:** **OBRIGATÓRIA** por `review-triggers.md`: embora não haja mudança de API, auth, billing ou schema, a remoção de `queries.ts` e do wrapper de carousel torna o diff superior a ~300 linhas. O reviewer deve verificar especialmente referências indiretas, lockfile e providers.

## Definição de pronto (Definition of Done)
- [x] Decisão A/B baseada em inventário e números documentados.
- [x] Critérios de aceite implementados e validados preliminarmente pelo executor.
- [ ] Testes escritos e passando (tester; não há suíte frontend, portanto registrar `tsc` + build + verificação manual).
- [ ] Revisão de código aprovada (obrigatória por `review-triggers.md`, pois o diff excede ~300 linhas).
- [ ] Documentação atualizada (documenter; esta run entrega o histórico, sem changelog de comportamento).
- [x] `implementation-history.md` completo e coerente.
