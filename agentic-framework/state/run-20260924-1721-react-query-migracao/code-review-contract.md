<!--
CONTRACT: code-review-contract
DONO: reviewer
QUANDO É CRIADO: sempre que review-triggers.md indicar revisão obrigatória, ou sob demanda (skill agentic-review).
PARA ONDE VAI A INSTÂNCIA: agentic-framework/state/run-<run_id>/code-review-contract.md
-->

# Code Review Contract — 20260924-1721-react-query-migracao

## Metadados
- **run_id:** 20260924-1721-react-query-migracao
- **Escopo revisado:** diff HEAD de frontend/ (19 arquivos modificados) + 5 arquivos novos não versionados (lib/queries.ts, lib/query-client.ts, lib/query-keys.ts, lib/query-session.tsx, scripts/verificar-query-client.mjs). Excluídos do escopo: backend/, docs vivos, agentic-framework/state/ e subir-localhost.sh (runs anteriores).
- **Contrato de referência:** implementation-contract.md (20260924-1721-react-query-migracao)
- **Gatilhos aplicados (de review-triggers.md):** nova dependência externa (@tanstack/react-query ^5.102.8); volume (>300 linhas — 1175 insertions); autenticação/sessão (QuerySessionBoundary); cobrança/assinatura (planos público + admin/planos); dados pessoais (usuario.id em chaves privadas)
- **Observação de execução:** revisão executada pelo orquestrador (subagentes indisponíveis por instabilidade de rede do provedor de modelo); o finding major foi remediatado durante o review, com revalidação (tsc + smoke) após a correção.

## Findings

### Finding 1
- **Arquivo:** frontend/app/comunidade/[id]/page.tsx
- **Linha:** 84 (antes da correção)
- **Categoria:** correctness
- **Severidade:** major → **corrigido durante o review**
- **Resumo:** a função `recarregar` (botão "Tentar de novo") invalidava a query com chave crua `["publicacao", safeId]`, que não prefixa a key real da query (`["privado"|"publico", AMBIENTE, "comunidade", "publicacao", {usuarioId, id}]`) — invalidação no-op: o botão não recarregava nada.
- **Cenário de falha:** API falha na carga da publicação → usuário clica "Tentar de novo" → nenhuma requisição é feita, a tela permanece na cópia local até um reload manual.
- **Sugestão (aplicada):** substituir por `pubQuery.refetch()`, que refetch a query correta independente de key; `loading` zerado no `finally` e o `useEffect` de sincronização atualiza o estado local com o dado fresco. Revalidado: tsc 0 erros, smoke 200 em /comunidade e /comunidade/1. Variável `queryClient` e import `useQueryClient` ficaram órfãos e foram removidos.

### Finding 2
- **Arquivo:** frontend/app/comunidade/page.tsx e frontend/app/comunidade/[id]/page.tsx
- **Linha:** múltiplas (ex.: `MOCK_PUBS: any[]`, `pub as any`, `params: any`)
- **Categoria:** maintainability
- **Severidade:** minor
- **Resumo:** tipos `any` remanescentes nos mocks e no estado local da comunidade — o padrão era pré-existente no códigobase e a migração o preservou, mas tipar com `api.Publicacao`/`api.FeedEntrada` daria autocompletar e checagem nas mutações.
- **Cenário de falha:** renomear um campo de `Publicacao` na API não quebra o build dos mocks `any`; erro silencioso em runtime na tela.
- **Sugestão:** substituir gradualmente `any` por `api.Publicacao`/`api.FeedEntrada` em um follow-up de dívida técnica; não bloqueia.

## Resumo quantitativo
| Severidade | Quantidade |
|---|---|
| blocker | 0 |
| major | 0 (1 encontrada e corrigida durante o review) |
| minor | 1 |
| nit | 0 |

## Veredito
**approve_with_comments**

A migração está correta e segura: nenhuma key contém token/PII (verificado por word-boundary em todos os hooks e no check determinístico 8/8), o client é por árvore sem singleton SSR, o logout cancela e limpa o cache privado, as cadências de polling são preservadas com `refetchIntervalInBackground: false` e nenhum intervalo órfão, as mutations invalidam as queries afetadas e os fallbacks/mock são mantidos. O único finding major (invalidação no-op com chave crua) foi corrigido durante o review com revalidação completa. O finding minor de tipos `any` remanescentes é dívida pré-existente, registrada como follow-up.
