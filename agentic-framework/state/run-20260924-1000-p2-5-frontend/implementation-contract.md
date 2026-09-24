<!--
CONTRACT: implementation-contract
DONO: orchestrator (preenche) / executor, tester, reviewer (leem)
QUANDO É CRIADO: logo após o task-plan.md ser aceito.
-->

# Implementation Contract — 20260924-1000-p2-5-frontend

## Metadados
- **run_id:** 20260924-1000-p2-5-frontend
- **Deriva de:** `task-plan.md` (20260924-1000-p2-5-frontend)
- **Versão do contrato:** 1

## O que deve ser construído

Aplicar quatro alterações frontend independentes, sem backend novo e sem React Query:

1. **Colunistas no servidor/ISR:** carregar a lista de colunistas no `app/page.tsx` (ou wrapper server-side equivalente) usando o helper existente, com limite 4, e entregá-la ao componente de apresentação `SecaoColunistas` por props. O componente deixa de iniciar o efeito que chama `carregarColunistas`; a busca client-side em cascata (`obterPublicacoes` destaque → fallback → quatro perfis) deixa de ocorrer por visita. Manter agrupamento, ordenação, perfil, foto/iniciais, selo, contagem, empty state e links existentes. A falha de rede deve resultar em lista vazia, sem dados inventados.

2. **Polling de últimas:** manter `obterFeed` e o botão de atualização. Como o polling já verifica `document.visibilityState`, aumentar o intervalo padrão para **180 s** (e normalizing persisted values to at least 180 s) para manter frescor sem duplicar a cadência de 60/90 s. Não permitir que a alteração quebre a atualização de “últimas notícias”.

3. **AdSense consentido:** `AdsScript` deve ler `permiteCategoria("personalizacao")` apenas no cliente, manter o script ausente enquanto a permissão for falsa, assinar `EVENTO_CONSENTIMENTO_ALTERADO`, e renderizar `next/script` com `strategy="lazyOnload"` quando permissão for verdadeira e `ADSENSE_CLIENT_ID` não vazio. `AdsSlot` deve continuar degrading para placeholder visual sem ID/slot e não deve inicializar `adsbygoogle` antes da permissão.

4. **Fonte única de `news_view`:** remover do `AnalyticsTracker` a derivação de `news_view` baseada no pathname, mantendo `NoticiaReporter` como fonte única para o evento inicial e o evento de leitura com `tempo_leitura_seg`/`scroll_max_pct`. Atualizar comentários para que não indiquem uma segunda instrumentação. Não remover `track`, `trackNewsClick`, `page_view`, categorias, autores, radar ou comunidade.

## Áreas/arquivos esperados
- `frontend/app/page.tsx` — carregamento server-side dos colunistas e passagem dos dados para a Home.
- `frontend/components/HomeClient.tsx` — nova prop de dados e passagem para `SecaoColunistas`, sem_effect de busca client-side.
- `frontend/components/SecaoColunistas.tsx` — tornar o componente apresentacional, remover `useEffect`/`useState` de carga e preservar o visual/empty state.
- `frontend/lib/colunistas.ts` — somente ajustes necessários para separar dados server-side de apresentação, se a assinatura atual exigir; não alterar o contrato público da API.
- `frontend/components/home/UltimasNoticias.tsx` — polling/visibilidade e comentários do intervalo.
- `frontend/lib/editorial.ts` — valor padrão do intervalo, se a configuração continuar sendo a fonte do polling.
- `frontend/components/AdsScript.tsx` — consentimento, evento de alteração e `lazyOnload`.
- `frontend/components/AdsSlot.tsx` — evitar push/inicialização de slot antes do consentimento, se necessário para que o script consentido não seja violado.
- `frontend/components/AnalyticsTracker.tsx` — retirar somente a derivação de `news_view`; preservar os demais eventos.
- `frontend/components/Reporters.tsx` — somente comentários/ajustes de fonte única, sem remover `track` ou métricas de leitura.
- `agentic-framework/state/run-20260924-1000-p2-5-frontend/` — `task-plan.md`, `implementation-contract.md`, `run-state.json` e `implementation-history.md`.

Qualquer arquivo fora dessa lista deve ser justificado no histórico. Não tocar `backend/**`, `.github/workflows/**`, `infra/nginx/**`, `docker-compose.yml` ou dependências.

## Interfaces afetadas
- Nenhuma API, schema, rota ou payload backend é alterado.
- `HomeClient` ganha uma prop interna `colunistas` (ou nome equivalente) e `SecaoColunistas` deixa de fazer fetching próprio; os consumidores existentes de `SecaoColunistas` devem continuar compilando, com a única chamada de produção atualizada no fluxo da Home.
- `lib/colunistas.ts` continua expondo `Colunista`, `carregarColunistas`, `seloPublicacao`, `iniciais` e `formatarDataConteudo`; a função de carga continua server-safe e best-effort.
- O valor de `refreshUltimasSegundos` é configuração local de UI, não uma API; o intervalo efetivo deve ficar documentado e continuar respeitando valores válidos.
- O contrato de consentimento existente (`analytics`, `personalizacao`, `EVENTO_CONSENTIMENTO_ALTERADO`) não muda. `AdsScript` passa a depender de `personalizacao`; `analytics` continua sendo usado por `lib/analytics.ts`.
- O backend continua recebendo um `news_view` por visita instrumentada pela reporter, com os mesmos campos; a mudança é apenas de fonte no frontend.

## Critérios de aceite (técnicos, testáveis)
1. Dado um build sem `NEXT_PUBLIC_ADSENSE_CLIENT_ID`, quando o layout é renderizado, então não há `<Script>` de AdSense, não há URL externa de AdSense e os slots continuam sendo placeholders; dado um build com ID e consentimento ausente, então também não há `<Script>`.
2. Dado um build com publisher ID e `personalizacao: true` no consentimento local, quando `AdsScript` monta, então ele renderiza o script com `strategy="lazyOnload"`; após um evento `portal_noticias:consentimento-cookies-alterado`, o estado reavalia a permissão.
3. Dado `UltimasNoticias` com uma aba oculta, quando decorre o intervalo, então nenhuma nova chamada a `obterFeed` é iniciada; dado uma aba visível, quando o ciclo termina, então a atualização continua ocorre, e o botão manual continua chamando o mesmo loader.
4. Dado uma página `/noticia/...`, quando o reporter monta e a rota muda, então existe apenas uma fonte de `track({ tipo: "news_view", ... })` no código de runtime; o tracker global não deriva `news_view` do pathname, enquanto a reporter preserva `entry_tipo`, `entry_id`, `categoria`, tempo de leitura e scroll.
5. Dado `SecaoColunistas` renderizado pela Home, quando a busca server-side retorna até quatro autores, então os cards são exibidos sem `useEffect` de rede no componente; quando retorna vazio, a seção é omitida; a busca client-side `carregarColunistas` não é disparada pela visita.
6. Dado `npx tsc --noEmit` e `npm run build` no frontend, quando executados após a implementação, então ambos terminam com exit code 0 e o build não apresenta erro de hidratação/import.
7. Dado o servidor standalone iniciado após o build, quando `/` e uma rota de notícia forem consultadas por HTTP, então ambas respondem 200 (ou a limitação de backend/API fica explicitamente registrada se o smoke não puder ser executado).

## Não-objetivos
- Não adicionar `@tanstack/react-query` nem qualquer cache de cliente; não tocar a remoção feita por P1-6.
- Não criar endpoint agregado, paginar community, mudar `obterPublicacoes`/`obterPerfilAutor` ou alterar backend/cache.
- Não remover a atualização automática sem uma prova de que a UX continua válida; não transformar `router.refresh()` em polling de backend sem necessidade.
- Não alterar a categoria de consentimento usada por `lib/analytics.ts`, nem adicionar uma terceira categoria.
- Não remover `NoticiaReporter`, `trackNewsClick`, `page_view` com permanência/scroll, busca, categoria, autor, radar ou comunidade.
- Não alterar o layout, conteúdo, filtros, fallback de `MOCK` da Home, persistência de preferências ou AdsSlot sem necessidade para consentimento.

## Restrições técnicas
- **Performance:** zero requisições de colunistas no cliente por visita; no máximo uma requisição de feed por ciclo de polling visível; o polling não deve iniciar requisição quando a aba está oculta.
- **Segurança/privacidade:** AdSense só pode ser inicializado após `permiteCategoria("personalizacao")`; não enviar ID/URL de terceiro antes disso; não alterar os checks de analytics.
- **Dependências permitidas:** nenhuma; usar apenas React/Next e módulos já existentes.
- **Estilo/convenções:** TypeScript strict, Server/Client Component boundaries válidas, imports ES modules, comentários em português quando adicionados.
- **SSR/hidratação:** a primeira renderização da Home deve continuar usando os mesmos dados server-side; a prop de colunistas deve ser serializável e não criar hydration mismatch.
- **Revisão:** não há gatilho obrigatório de API/schema/auth; o executor deve registrar se o diff permanecer pequeno. Se a validação exige smoke, ela é evidência, não substitui `tsc`/build.

## Definição de pronto (Definition of Done)
- [x] Escopo e decisões documentados neste contrato.
- [ ] Critérios de aceite implementados.
- [ ] `npx tsc --noEmit` executado e passando.
- [ ] `npm run build` executado e passando.
- [ ] Smoke HTTP das páginas tocadas executado ou limitação registrada.
- [ ] `implementation-history.md` completo com arquivos:linha, decisões e evidências.
- [ ] Revisão/documentação/histórico finalizeados pelo pipeline, se exigidos pelo orquestrador.
