<!--
CONTRACT: task-plan
DONO: orchestrator
QUANDO FOI CRIADO: início da execução 20260924-1721-react-query-migracao
PARA ONDE VAI A INSTÂNCIA: agentic-framework/state/run-20260924-1721-react-query-migracao/
-->

# Task Plan — 20260924-1721-react-query-migracao

## Metadados
- **run_id:** 20260924-1721-react-query-migracao
- **Data de abertura:** 2026-09-24
- **Solicitado por:** humano (Alex), decisão explícita após a alternativa A da run `20260923-1500-p1-6-react-query`
- **Spec de origem:** `ANALISE_CUSTO_PERFORMANCE.md` P1-6 e follow-up da run `20260923-1500-p1-6-react-query`; política de cache aprovada pelo solicitante nesta sessão

## Objetivo
Reintroduzir um cache de cliente real com TanStack Query e migrar os 22 sites de carregamento de backend inventariados em 15 arquivos, preservando integralmente loading, erro, fallback, filtros, polling, mutations, autenticação, SSR/ISR eVisibility das telas.

## Escopo
### Dentro do escopo
- Reintroduzir `@tanstack/react-query` e um cliente seguro, sem reintroduzir `@tanstack/react-table` ou `embla-carousel-react`.
- Montar o provider no shell preservando a ordem dos providers e a renderização do root.
- Criar query keys/hooks focados para leituras públicas, Community, Gama/premium e Admin; migrar os 22 Effect/callback sites, sem converter efeitos puramente locais (localStorage, geolocation, UI, debounce) em queries.
- Aplicar política conservadora: sem persistência em localStorage/IndexedDB; público `staleTime` 60 s; autenticado 15 s; telas de decisão 0 s; refetch ao reconectar e polling conforme regras atuais.
- Incluir escopo de usuário nas chaves privadas, nunca o token; limpar o cache ao trocar usuário/fazer logout.
- Migrar mutations para invalidar/settar as queries afetadas, sem alterar contratos do backend.
- Preservar mocks/fallbacks e mensagens de erro visíveis; substituir `setInterval` manual apenas quando `refetchInterval` reproduzir o mesmo comportamento.
- Medir bundle/First Load e validar tsc, build, smoke HTTP e uma checagem determinística do cliente de queries.

### Fora do escopo (explicitamente)
- Não alterar backend, migrations, endpoints, payloads, autenticação ou autorização.
- Não mover Server Components (`app/page.tsx`, `app/autor/[id]`, páginas editoriais e de notícia) para hooks client-side; o SSR/ISR continua como está.
- Não persistir dados de usuário no navegador nem armazenar tokens em query keys/devtools.
- Não migrar efeitos que não chamam backend, como tema, consentimento local, device profile, analytics, geolocation ou animações.
- Não adicionar React Table, Embla, outra biblioteca de query ou suíte de testes pesada.
- Não fazer commit/push; commits externos existentes não devem ser reescritos.

## Suposições assumidas
- A política conservadora aprovada pelo solicitante é: QueryClient em memória, sem persistência; queries públicas 60 s, autenticadas 15 s, decisão 0 s; refetch ao focar/reconectar conforme o fluxo; chaves com identidade e sem token.
- O inventário de 22 sites da run anterior é a fonte inicial; qualquer discrepância deve ser medida e registrada, não corrigida por suposição.
- A ausência de suíte frontend será compensada por tsc/build, smoke de rotas e um check determinístico de query client/keys; não será criado um framework de testes apenas para esta run.

## Restrições
- Não usar um singleton de QueryClient que possa compartilhar dados entre requisições SSR; criar cliente por árvore cliente.
- Não colocar `Authorization`, token ou objeto de usuário inteiro em query key/log.
- Queries privadas devem ter `enabled` coerente com token e ser removidas/limpas ao logout.
- Fallbacks mockados de Radar, Community e Admin devem continuar visíveis quando a API falhar; não transformar erro em tela vazia silenciosa.
- `refetchInterval` deve pausar em aba oculta quando o fluxo atual pausa; não aumentar a frequência de polling.
- Preservar as mudanças não frontend ainda presentes na working tree (cache `feed:v2`, docs e run B) e os commits externos `d1e0456`/`f8d8db6`.

## Divisão de trabalho
| Etapa | Agente responsável | Entrada esperada | Saída esperada |
|---|---|---|---|
| 1 | executor — núcleo/público | implementation-contract.md e escopo frontend público/comunidade | dependência, provider, query core, hooks e sites públicos/comunidade |
| 2 | executor — Admin | mesmo contrato e escopo frontend admin isolado | sites Admin e invalidações; não tocar núcleo já entregue sem necessidade |
| 3 | tester | contrato + diff final | veredito independente, tsc/build, smoke e checagem de queries |
| 4 | reviewer | diff completo e gatilhos | code-review-contract.md |
| 5 | remediator (se necessário) | findings | correções + reteste/revisão |
| 6 | documenter | histórico/revisão | documentation-update.md |
| 7 | historian | todos os artefatos | report.md + linha append-only no HISTORY.md |

## Critérios de aceite (nível de negócio/produto)
1. Os 22 sites de carregamento de backend passam a ser gerenciados por queries, sem recriar uma segunda camada de estado manual que produza loading/erro/fallback divergentes.
2. Navegar entre telas reutiliza dados públicos por até 60 s, sem servir dados antigos por mais tempo que a política aprovada; telas autenticadas não compartilham payload entre usuários.
3. Login/logout e troca de usuário limpam ou isolam imediatamente o cache privado; nenhum token aparece em chaves, persistência ou logs do cliente.
4. Mutations de Community, planos, Admin, Robôs, journlista e Radar invalidam ou atualizam as leituras afetadas; a tela não fica permanentemente com dado obsoleto após uma ação.
5. Radar, últimas notícias, Home, Community, planos, Admin, Robôs, métricas e status de jornalista continuam com os mesmos estados de carregamento, erro, fallback, polling e mensagem.
6. O bundle, build e rotas continuam funcionando; a migração não aumenta Requests de API além da política de cache nem quebra SSR/ISR.
7. Nenhuma dependência de table/carousel é reintroduzida e nenhum backend/migration é alterado.

## Riscos identificados
| Risco | Impacto | Mitigação |
|---|---|---|
| Cache privado vazar entre usuários | alto | chaves com `usuario.id`, token fora da key, limpeza no boundary de sessão e teste de logout |
| Query module-global vazar entre SSR requests | alto | `QueryClient` criado por provider/estado, sem singleton server-side |
| Migração alterar loading/fallback | alto | testes de rota/smoke, queries com `data ?? fallback` e revisão de cada Effect migrado |
| Polling duplicar requisições | médio | remover intervals manuais só quando `refetchInterval` substitui exatamente o intervalo; testar contagem |
| Mutations deixarem cache stale | alto | invalidar/settar chaves em sucesso e cobrir ao menos Community/Admin/Robôs |
| Query key crescer com PII | alto | normalizar filtros e usar apenas IDs/valores não sensíveis; 금지 token/email |
| Dependência reintroduzir custo de bundle | médio | medir chunks/First Load antes/depois e comparar com baseline da run 1500 |
| Migrar apenas parte dos 22 sites | médio | inventário final por arquivo/Effect e smoke de cada tela |
|hydration mismatch | alto | preservar `null`/initial states do servidor, não ler localStorage no render e testar build standalone |

## Dependências
- Ambiente Node/npm já instalado; sem serviço externo necessário.
- Mudanças backend/cache `feed:v2` e docs da run B permanecem na working tree e devem ser preservadas.
- A revisão é obrigatória por introduzir dependência externa, alterar clients com autenticação/dados pessoais, mudar polling/requests e ter volume grande.
