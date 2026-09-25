<!--
CONTRACT: implementation-contract
DONO: orchestrator (preenche) / executor, tester, reviewer (leem)
PARA ONDE VAI A INSTÂNCIA: agentic-framework/state/run-20260924-1721-react-query-migracao/
-->

# Implementation Contract — 20260924-1721-react-query-migracao

## Metadados
- **run_id:** 20260924-1721-react-query-migracao
- **Deriva de:** `task-plan.md` (20260924-1721-react-query-migracao)
- **Versão do contrato:** 1

## O que deve ser construído

### A. Runtime e provider seguros
1. Adicionar `@tanstack/react-query` na versão compatível já usada pelo projeto (`^5.102.8`) e atualizar `package-lock.json` de forma reproduzível; não adicionar `@tanstack/react-table` nem `embla-carousel-react`.
2. Criar um construtor de `QueryClient` em `frontend/lib/query-client.ts` com defaults: público 60 s, gc 5 min, retry 1, `refetchOnWindowFocus: false`, reconnect controlado e sem persistência. O cliente deve ser instanciado por árvore cliente, não por módulo global compartilhado entre SSR requests.
3. Montar `QueryClientProvider` em `frontend/app/providers.tsx` sem alterar a ordem dos providers existentes nem headers/ISR do root.
4. Adicionar um boundary/session guard que limpe queries privadas (ou todo o cache) quando a identidade sair/entrar/trocar; nunca colocar token em query key ou storage.

### B. Query keys e hooks
1. Criar uma camada de queries focada, sem restaurar cegamente os 64 hooks mortos: query keys estáveis com filtros, ambiente e `usuario.id` para dados privados; token apenas closure do `queryFn`.
2. Criar hooks para as leituras dos 22 sites, incluindo:
   - feed/últimas notícias, planos e premium;
   - Radar tendências/evolução/localidades, com polling e fallback;
   - Community publications/publicação/comentários/perfil e dados de filtros;
   - status de jornalista;
   - Admin: métricas, fila, planos, limites, robôs, fontes, config premium;
   - demais leituras backend que o inventário final confirmar, incluindo `CoberturaCompleta` se for uma das 22.
3. Queries autenticadas usam `enabled: Boolean(token)`, staleTime 15 s (ou 0 em decisões) e query key com identidade. Queries públicas usam 60 s. Dados que já chegam por Server Component/ISR não são convertidos em client hooks.
4. Mutations ou handlers existentes devem chamar `setQueryData`/`invalidateQueries` para as chaves relacionadas após sucesso; remover `setTimeout`/recarregamentos que existiam só para compensar cache manual quando a query resolver o estado.
5. Preservar mocks e mensagens de fallback: o componente escolhe `data ?? fallback` e continua exibindo `error` quando a API falhar, em vez de esconder a falha.

### C. Migração dos 22 sites
Migrar os sites de carregamento nos 15 arquivos inventariados, mantendo os efeitos não-backend:

- `app/admin/configuracoes/FontesIsland.tsx`
- `app/admin/configuracoes/PremiumFlagIsland.tsx`
- `app/admin/page.tsx`
- `app/admin/fila/page.tsx`
- `app/admin/limites/page.tsx`
- `app/admin/metricas/page.tsx`
- `app/admin/planos/page.tsx`
- `app/admin/robos/page.tsx`
- `app/comunidade/[id]/page.tsx`
- `app/comunidade/page.tsx`
- `app/jornalista/status/page.tsx`
- `app/planos/page.tsx`
- `app/radar/RadarClient.tsx`
- `components/home/UltimasNoticias.tsx`
- `lib/premium.ts`

Auditar `components/CoberturaCompleta.tsx` e qualquer loader adicional; se for um 22º site de backend, incluí-lo e registrar a contagem, sem migrar efeitos locais.

### D. Política e compatibilidade
1. Radars: `refetchInterval` 60 s, pausado fora da aba, mantendo filtros e mocks; localidades salvas por mutation invalidam a query.
2. Últimas notícias: polling manual de 180 s, botão de recarregar e pausa em aba oculta preservados; query não deve disparar duas requisições concorrentes.
3. Admin/fila: polling de 30 s somente quando auto-refresh ligado, decision data sem staleTime; mutations invalidam fila.
4. `usePremiumAtivo`: remover cache local em localStorage conforme política sem persistência, preservar `ativo=null`/fail-open na primeira renderização e `recarregar` via invalidação; não quebrar SSR/hidratação.
5. Community/Admin: loading, error, fallback e mensagens de fallback permanecem; debounce de busca continua no efeito local, mas a query só executa com o valor debounced.

## Áreas/arquivos esperados
- `frontend/package.json`, `frontend/package-lock.json`
- `frontend/app/providers.tsx`
- `frontend/lib/query-client.ts` (novo)
- `frontend/lib/queries.ts` ou módulos query focados (novo)
- `frontend/lib/query-session.tsx` ou boundary equivalente (novo)
- `frontend/lib/premium.ts`
- os 15 arquivos da lista C e `components/CoberturaCompleta.tsx` se confirmado
- `frontend/scripts/verificar-query-client.mjs` e o step correspondente em `.github/workflows/ci.yml` para a checagem determinística
- artefatos da run
- Alterações fora da lista precisam ser justificadas no histórico; não tocar backend, migrations ou `ingestao-service`.

## Interfaces afetadas
- Client-side data lifecycle e número/timing de requests; não muda o contrato HTTP.
- Query cache em memória, sem persistência; dados privados isolados por usuário e limpos no logout.
- Mutations agora invalidam/settam queries, alterando apenas consistência de UI.
- Polling pode passar de `setInterval` para React Query, mantendo a cadência e a pausa.
- Dependência de runtime `@tanstack/react-query` e bundle podem crescer; deve ser medido.

## Critérios de aceite (técnicos, testáveis)
1. Dado `npm ls @tanstack/react-query` e o lockfile, quando `npm ci` é executado, então a dependência está instalada de forma reprodutível e `@tanstack/react-table`/`embla-carousel-react` não aparecem.
2. Dado o root layout e `Providers`, quando o build SSR é renderizado, então há um `QueryClientProvider` por árvore cliente, sem singleton SSR e sem alterar headers/ISR; não há hydration warning.
3. Dado o construtor do QueryClient, quando inspecionado, então defaults de stale/gc/retry/reconnect são explícitos, não persistem em storage e não mantêm token/usuário completo em keys.
4. Dado login de dois usuários em sequência e logout, quando as queries privadas são observadas, então o cache anterior é limpo/isolado e a segunda identidade não recebe payload da primeira.
5. Dado cada um dos 22 sites inventariados, quando a tela monta/recebe filtro, então o loader backend é executado por `useQuery`/`useInfiniteQuery` ou helper query, e não por um `useEffect` que chama `api.*` diretamente; o inventário final deve listar cada site.
6. Dado uma query pública com `staleTime` 60 s, quando duas telas/clientes naveguam dentro da janela, então há no máximo uma requisição por key; ao ultrapassar a janela há uma revalidação, sem polling duplicado.
7. Dado dados autenticados, quando staleTime é 15 s/0 s conforme a tela, então uma decisão/ação não mostra o payload anterior após mutation; a key inclui `usuario.id` e parâmetros normalizados, nunca token.
8. Dado Radar, últimas notícias e Admin/fila, quando headless/aba oculta/auto-refresh desligado, então a cadência existente é preservada e não há intervalo órfão duplicado.
9. Dado falha de API nos sites com mock, quando a query rejeita, então o fallback continua renderizado e a mensagem de erro/empty state continua coerente; uma falha não vira tela vazia silenciosa.
10. Dado uma mutation de Community, planos, Admin, Robôs, Radar ou jornalista, quando ela resolve com sucesso, então a(s) query(s) afetada(s) é invalidated/setada e a UI não precisa de reload manual.
11. Dado `lib/premium.ts`, quando o app monta no servidor/cliente, então `ativo` começa null, a API só é consultada no cliente, falha é fail-open e não há leitura de localStorage no render.
12. Dado `npm run build`, quando executado, então 59/59 páginas são geradas, `npx tsc --noEmit` passa e o smoke HTTP das rotas principais retorna 200 sem Application error.
13. Dado a checagem determinística de query client/keys, quando executada em Node suportado, então ela valida defaults, ausência de persistência e chaves sem token; o CI executa o mesmo check.
14. Dado o inventário final, quando `rg` procura os 22 loaders antigos, então cada um tem uma query/hook correspondente documentado e nenhum Effect de backend ficou sem migração; diferenças de contagem são justificadas no histórico.
15. Dado o diff, quando `git diff --check` e smoke são executados, então não há erro de whitespace e o build não introduz erro de runtime nas rotas tocadas.

## Não-objetivos
- Não criar persistência de QueryClient, service worker ou cache offline.
- Não migrar Server Components nem substituir ISR/SEO por client fetch.
- Não alterar API, backend, banco, autenticação, autorização, payloads, filtros de negócio ou polling de backend.
- Não restaurar os 64 hooks apagados só por compatibilidade; só hooks com consumidor e testes/uso reais.
- Não adicionar React Table, Embla, Vitest, Playwright ou outra suíte pesada.
- Não reescrever commits externos ou文档ar o Lote B como parte desta run.

## Restrições técnicas
- **Performance:** preservar o backend cache 45 s; o client cache não deve elevar polling nem duplicar requests; medir raw/gzip e First Load contra baseline.
- **Segurança/privacidade:** sem token/PII desnecessária em keys, sem localStorage para cache, cleanup no logout, queries privadas por identidade.
- **Dependências permitidas:** apenas `@tanstack/react-query` versão compatível já documentada; nenhuma outra.
- **Estilo/SSR:** TypeScript strict, `use client` apenas onde necessário, null inicial/hidratação preservada, imports ES modules.
- **Revisão:** obrigatória por dependência nova, dados autenticados/pessoais, mudança de polling/API client e volume dos 15 arquivos.

## Definição de pronto (Definition of Done)
- [x] Escopo e política aprovados
- [ ] Runtime/query core e 22 sites implementados
- [ ] Tester independente com tsc/build/smoke/check passou
- [ ] Reviewer aprovou após revisão de segurança/polling
- [ ] Documentação e relatório atualizados
- [ ] `implementation-history.md` e `HISTORY.md` completos
