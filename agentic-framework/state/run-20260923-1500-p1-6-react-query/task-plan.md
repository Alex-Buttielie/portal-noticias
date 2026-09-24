# Task Plan — 20260923-1500-p1-6-react-query

## Metadados
- **run_id:** 20260923-1500-p1-6-react-query
- **Data de abertura:** 2026-09-23 15:00 (America/Sao_Paulo)
- **Solicitado por:** sessão pai (subagent executor) — item P1-6 de `ANALISE_CUSTO_PERFORMANCE.md`
- **Spec de origem:** `ANALISE_CUSTO_PERFORMANCE.md`, seção 5, item F1 (seção 7, prioridade P1-6)

## Objetivo
Eliminar a camada de cache de cliente morta e as dependências órfãs, sem introduzir uma migração parcial que altere loading, erro, fallback, estados vazios ou hidratação. A decisão será baseada no inventário real dos fluxos de dados; a implementação deverá deixar o frontend coerente, compilável e com o lockfile atualizado.

## Escopo
### Dentro do escopo
- Confirmar por inventário quantos efeitos/fluxos carregam dados do backend e quantos hooks de leitura existem em `frontend/lib/queries.ts`, incluindo a cobertura de endpoints.
- Escolher entre migrar para `useQuery`/`useInfiniteQuery` ou remover a camada morta, com números, risco de regressão e evidência reproduzível.
- Remover `@tanstack/react-table` e `embla-carousel-react` sempre que a busca confirmar que não há importação/uso.
- Se a alternativa B for escolhida, remover `lib/queries.ts`, `lib/query-client.ts`, `@tanstack/react-query` e o `QueryClientProvider` órfão; atualizar `package.json` e `package-lock.json`.
- Avaliar a troca de `import * as api` por imports nomeados nos dois módulos montados no root (`lib/auth-context.tsx` e `lib/cookie-consent.ts`), medindo o efeito no bundle; não reescrever os demais pontos sem ganho demonstrável.
- Preservar o comportamento dos fluxos existentes e validar com `tsc --noEmit`, `npm run build` e verificação manual/estática dos fluxos tocados.

### Fora do escopo (explicitamente)
- Backend, Django, `infra/nginx`, `.github/workflows` e qualquer outra mudança de API ou cache do servidor.
- Migrar todos os `useEffect` para React Query ou criar um novo cache de cliente; caso a decisão seja B, a migração fica explicitamente como follow-up.
- Alterar o polling, filtros, payloads, estados de UI, autenticação, permissões ou conteúdo das páginas.
- Reescrever indiscriminadamente os 24 imports namespace de `api`; só mudanças nos pontos quentes com medição favorable.
- Adicionar dependências, suíte de testes ou ferramentas de bundle; o frontend não possui suíte automatizada configurada.

## Suposições assumidas
- O diretório de trabalho pode conter alterações de outras runs (notadamente backend/infra); elas serão preservadas e não atribuídas a esta execução — motivo: o pedido proíbe tocar esses arquivos e o `git status` já mostra alterações pré-existentes.
- A ausência de uma suíte frontend significa que a validação mínima e a verificação manual/estática são aceitáveis para esta run — motivo: `frontend/package.json` não define script de teste e não há arquivos de teste no escopo;registrar a limitação em vez de inventar cobertura.
- A alternativa B é preferível se a migração exigir reescrever os fluxos complexos sem cache compartilhado já ativo — motivo: o inventário inicial mostra muitas mutações, fallbacks e dependências de hidratação, enquanto nenhum hook de `lib/queries.ts` é importado; registrar a decisão no histórico.

## Restrições
- Não fazer commit.
- Não alterar backend, `.github/workflows` nem `infra/nginx`.
- Preservar compatibilidade de tipos, SSR/hidratação e comportamento visível; qualquer mudança deve ser segura para rotas estáticas e client components.
- Não aceitar cache de cliente que sirva dados além do TTL sem revalidação; a alternativa A, se considerada, precisaria de `staleTime` de 60 s no feed e política explícita de revalidação contra o cache de backend de 45 s.
- Não usar estimativas sem evidência: contagens, bundle e comandos devem ser registrados em `implementation-history.md`.

## Divisão de trabalho
| Etapa | Agente responsável | Entrada esperada | Saída esperada |
|---|---|---|---|
| 1 | executor | implementation-contract.md | decisão + código + `implementation-history.md` |
| 2 | tester | implementation-contract.md | veredito passed/failed/blocked; `tsc` e build |
| 3 | reviewer (**obrigatório**: diff >~300 linhas, mesmo sendo remoção de código morto) | diff do executor | `code-review-contract.md` |
| 4 | remediator (se necessário) | code-review-contract.md | correções + revalidação |
| 5 | documenter | implementation-history.md | `documentation-update.md` + docs atualizadas |
| 6 | historian | todos os artefatos acima | `report.md` + entrada em `HISTORY.md` |

## Critérios de aceite (nível de negócio/produto)
1. O frontend deixa de pagar por uma camada de cache de cliente que nenhuma tela usa, sem remover a fonte de dados atualmente usada pelas telas.
2. As dependências `@tanstack/react-query`, `@tanstack/react-table` e `embla-carousel-react` não permanecem instaladas sem uso; o lockfile reproduz `package.json`.
3. Os fluxos de home, comunidade, perfil e demais páginas que já fazem chamadas de backend continuam compilando e preservam seus estados de carregamento, erro, fallback e vazio; a execução manual dos fluxos tocados não observa mudança de conteúdo.
4. O bundle compartilhado é medido antes/depois; imports nomeados só são mantidos nos pontos quentes se houver ganho real ou se a mudança for comprovadamente neutra e segura.
5. `tsc --noEmit` e `npm run build` passam, e a ausência de suíte frontend automatizada fica explicitamente registrada como limitação.

## Riscos identificados
| Risco | Impacto | Mitigação |
|---|---|---|
| Remover uma dependência que tenha uso indireto não encontrado por grep | alto | Confirmar imports, referências em lockfile e bundle; executar `tsc` e `next build`; revisar o diff |
| Migrar parcialmente comunidade/admin e criar estados divergentes de loading/erro/fallback | alto | Preferir B salvo prova de que uma migração pontual é segura; não misturar estratégias sem contrato |
| Remover namespace imports e quebrar SSR ou tipagem | médio | Alterar somente imports estáticos; preservar tipos com `import type`; compilar em modo produção |
| Cache de backend de 45 s e dado do cliente ficarem divergentes | alto se A; não aplicável em B | Em B, não introduzir cache cliente; deixar a política de 45 s exclusivamente no servidor e registrar follow-up para uma futura migração |
| Alterações preexistentes de outras runs serem sobrescritas | alto | Editar somente `frontend/` e os artefatos desta run; conferir `git diff` e status antes/depois |

## Dependências
- `ANALISE_CUSTO_PERFORMANCE.md` e o estado atual do working tree.
- `frontend/package-lock.json` precisa ser regenerado de forma coerente após a remoção das dependências.
- Validação de produção depende de `NEXT_PUBLIC_API_BASE_URL`/`.env.local` já presente no ambiente; não será feito deploy nem chamada externa.
- Não há dependência de backend ou de nova biblioteca.
