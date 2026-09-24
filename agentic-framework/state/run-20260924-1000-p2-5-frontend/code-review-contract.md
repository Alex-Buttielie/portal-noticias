# Code Review Contract — 20260924-1000-p2-5-frontend

## Metadados

- **run_id:** 20260924-1000-p2-5-frontend
- **Escopo revisado:** `frontend/app/page.tsx`, `frontend/components/HomeClient.tsx`, `frontend/components/SecaoColunistas.tsx`, `frontend/components/home/UltimasNoticias.tsx`, `frontend/components/AdsScript.tsx`, `frontend/components/AdsSlot.tsx`, `frontend/components/AnalyticsTracker.tsx`, `frontend/components/Reporters.tsx`, `frontend/lib/colunistas.ts` e `frontend/lib/editorial.ts`, incluindo as referências de runtime necessárias para confirmar as rotas de notícia, consentimento e o limite do componente de colunistas.
- **Contrato de referência:** `implementation-contract.md`, `implementation-history.md` e `task-plan.md` desta run.
- **Artefato de documentação:** `documentation-update.md` não existe nesta pasta.
- **Gatilhos aplicados:** `agentic-framework/prompts/review-triggers.md:15` (diff acima do volume de referência); a revisão também foi solicitada explicitamente para risco de UX/LGPD.
- **Fora do escopo:** mudanças de backend, Nginx/Gunicorn e remoção de React Query da working tree; nenhum finding dessas áreas foi incluído.

## Findings

### Finding 1 — `major` — data de colunista depende do fuso do processo e quebra a hidratação

- **Arquivo/linha:** `frontend/lib/colunistas.ts:130-136`, chamada em `frontend/components/SecaoColunistas.tsx:119-121`.
- **Categoria:** correctness / UX / hydration.
- **Resumo:** ao mover os dados para o servidor, `formatarDataConteudo()` passou a ser avaliado no HTML inicial, mas usa `toLocaleDateString()` sem `timeZone`, tornando o texto dependente do fuso do servidor e do navegador.
- **Cenário de falha:** com a Home renderizada em `America/Sao_Paulo`, o HTML do colunista contém `24/09/2026`; a mesma página aberta em Chrome com `TZ=America/New_York` chega ao DOM hidratado com `23/09/2026` e registra React `#418/#423/#425`. A data do colunista é um caminho novo desta run: antes a lista real só aparecia depois do `useEffect`; agora é SSR + hidratação. A Home já possui outros formatadores dependentes de horário, mas este é o mismatch introduzido pelo novo payload server-side.
- **Correção sugerida:** fixar `timeZone: "America/Sao_Paulo"` (ou outra zona editorial explicitamente definida) no formatador, ou formatar uma data determinística no servidor; revisar os demais formatadores compartilhados para que a primeira renderização seja realmente igual entre servidor e cliente.

### Finding 2 — `minor` — a copy de consentimento não informa que a categoria cobre publicidade de terceiros

- **Arquivo/linha:** `frontend/components/AdsScript.tsx:20-31` e `frontend/components/BannerConsentimentoCookies.tsx:24,47-48`.
- **Categoria:** security / LGPD / consentimento.
- **Resumo:** o gate técnico está coerente com o modelo atual — `CategoriaOpcional` só possui `analytics` e `personalizacao`, não existe categoria `ads` — mas o banner descreve a segunda categoria apenas como “Recomendações e feed personalizado”, enquanto ela agora libera o Google AdSense.
- **Cenário de falha:** um visitante pode entender que autorizou apenas personalização do feed, sem saber que a escolha também autoriza script, cookies e publicidade de terceiros; o código não carrega o AdSense antes da permissão, mas a transparência do consentimento fica incompleta.
- **Correção sugerida:** alinhar banner, política de cookies e documentação para declarar explicitamente publicidade/marketing de terceiros nessa categoria, sem introduzir uma terceira categoria fora do contrato; se o produto quiser separar publicidade, fazer uma decisão de consentimento própria em run posterior.

### Finding 3 — `minor` — a carga server-side preserva payloads de comunidade ilimitados e pode bloquear a revalidação da Home

- **Arquivo/linha:** `frontend/app/page.tsx:34-40` e `frontend/lib/colunistas.ts:73-111`.
- **Categoria:** performance / resiliência.
- **Resumo:** `carregarColunistas(4)` continua chamando `obterPublicacoes` sem paginação/projeção e é aguardado no `Promise.all` que monta a Home, embora o componente precise somente de quatro registros de apresentação.
- **Cenário de falha:** uma comunidade grande ou um endpoint lento faz a revalidação ISR de 60 s carregar/serializar mais dados do que o necessário e aguardar a resposta sem timeout; isso troca tráfego por servidor, latência de SSR e custo de memória sem melhorar a lista mostrada ao usuário. O helper continua best-effort para erro, mas não para demora.
- **Correção sugerida:** medir o custo e, em follow-up de API, oferecer consulta limitada/projeção para os campos usados; no frontend, pelo menos aplicar timeout/isolamento para que a falha de comunidade não atrase a Home. Não é necessário alterar o comportamento público nesta run se o risco for aceito e registrado.

## Verificações de não-regressão

### Colunistas

- `app/page.tsx` é Server Component e chama `carregarColunistas(4)` no servidor (`page.tsx:34-40`).
- `HomeClient` recebe `colunistas?: Colunista[]` e o repassa para `SecaoColunistas` (`HomeClient.tsx:43-53,282`).
- `SecaoColunistas` não contém mais `useEffect`/`useState` nem chamada a `carregarColunistas`; a única chamada de produção está no Server Component.
- Lista vazia retorna `null`, sem mock; agrupamento, ordenação por data mais recente, perfil público, foto/iniciais, selo, contagem, datas e links foram preservados em `lib/colunistas.ts`/`SecaoColunistas.tsx`.
- O ISR de 60 s é um cache de dados públicos, sem varia por usuário; a eventual defasagem de até 60 s é compatível com a frescor já aceito da Home e não foi introduzido um cache client-side.

### AdsScript / AdsSlot e LGPD

- `permiteCategoria("personalizacao")` é a única categoria de gate existente no modelo atual; não há categoria `ads` separada no `lib/cookie-consent.ts` nem no banner.
- O estado inicia falso, só é lido no cliente e reage a `EVENTO_CONSENTIMENTO_ALTERADO`; o `<Script>` só aparece com publisher ID e permissão, com `strategy="lazyOnload"`.
- `AdsSlot` não faz `adsbygoogle.push({})` nem renderiza `<ins>` antes da permissão e continua retornando placeholder sem ID/slot.
- No build local sem `NEXT_PUBLIC_ADSENSE_CLIENT_ID`, o smoke não encontrou URL/script de AdSense. `lazyOnload` pode deixar slots sem preenchimento em sessões muito curtas, mas isso é um tradeoff explícito de performance e não uma violação do gate; deve ser monitorado como risco de monetização, não tratado como falha de consentimento.
- A cópia do banner é o comentário de LGPD do Finding 2. Também permanece o risco usual de que um script já executado não pode ser completamente “descarregado” ao revogar a preferência; o código evita nova renderização/push após revogação.

### Analytics / notícias

- A busca final encontrou uma única chamada executável de `track({ tipo: "news_view", ... })`, em `Reporters.tsx:29`; `AnalyticsTracker.tsx` não deriva mais o evento da URL.
- `NoticiaReporter` está montado nas três rotas de notícia: `/noticia/[id]`, `/noticia/item/[id]` e `/noticia/cluster/[id]`, com `entry_tipo`, `entry_id` e `categoria`; o heartbeat e o envio de `tempo_leitura_seg`/`scroll_max_pct` no `pagehide` foram preservados.
- O listener delegado de `news_click` continua em `AnalyticsTracker.tsx:121-139` e o smoke de rotas não indicou quebra de import. Links genéricos `/noticia/:id` continuam sendo interpretados como `item` pelo parser preexistente; isso não foi alterado nesta run.

### Polling

- `HOME_CONFIG_PADRAO.refreshUltimasSegundos` é 180 s; persistidos válidos são normalizados para a faixa 180–600 s, como definido no contrato.
- A guarda `document.visibilityState === "visible"` permanece no ciclo; o botão manual chama o mesmo `atualizar`/`obterFeed` e não depende do polling.
- 180 s é razoável para reduzir tráfego sem remover a atualização automática; a normalização altera deliberadamente preferências antigas abaixo de 180 s, mas não quebra a persistência das demais chaves.

### TypeScript, build, smoke e hidratação

- `frontend/npx tsc --noEmit`: exit 0.
- `frontend/npm run build`: exit 0, 59/59 páginas geradas, sem erro de import/prerender.
- Smoke standalone em `127.0.0.1:44927`: `/` → 200, `/noticia/1` → 200, `/comunidade` → 200; as respostas não continham `Application error`, `Module not found`, `Cannot find module` nem URL do AdSense.
- O `Suspense` ao redor de `AnalyticsTracker` continua no layout; os outros usos de `useSearchParams` também estão sob Suspense.
- Em Chrome headless no mesmo fuso do servidor, as três rotas não registraram erro React. Em fuso diferente, `/` reproduziu o mismatch de data do Finding 1; `/noticia/1` também possui timestamps preexistentes dependentes de fuso, mas não foi Runtime alterado por esta run e não foi contado como finding separado.

## Resumo quantitativo

| Severidade | Quantidade |
|---|---:|
| blocker | 0 |
| major | 1 |
| minor | 2 |
| nit | 0 |

## Veredito

**changes_requested**

A implementação atende o objetivo principal de mover colunistas para o servidor/ISR, remover a cascata client-side, preservar polling/clique/`news_view` e bloquear AdSense antes da permissão; porém o novo SSR dos cards introduz um mismatch de hidratação reproduzível por fuso, o que viola o critério de não-regressão e requer correção antes do merge. Os dois minors são riscos residuais de payload/latência e transparência do consentimento, sem bloquear isoladamente o restante da run.

## Re-revisão iteração 1 — 2026-09-24

**Escopo e método.** Reinspeção independente do working tree, isolada com `git diff -- frontend/`; mudanças de backend e as remoções de outras runs foram ignoradas. Li os arquivos de produção atuais, renderizei o componente real sob `TZ=UTC` e `TZ=Asia/Tokyo`, exercitei o helper com respostas paginada/legada e sinais de abort, iniciei um backend Django novo em `127.0.0.1:8001` para confirmar o contrato atual e usei Chrome/CDP com `America/Sao_Paulo`, `UTC` e `Asia/Tokyo` na Home. Nenhum arquivo de código foi alterado e nenhum commit foi criado; este é o único artefato atualizado nesta re-revisão.

### Status dos findings originais

| Finding | Status na re-revisão | Evidência independente |
|---|---|---|
| **1 — major / data de colunista** | **Resolvido** | `frontend/lib/colunistas.ts:4,162-167` usa `Intl.DateTimeFormat(\"pt-BR\", …, timeZone: \"America/Sao_Paulo\")`. O mesmo `SecaoColunistas` real, com `2026-09-24T00:30:00Z`, produziu `23/09/2026` tanto com `TZ=UTC` quanto com `TZ=Asia/Tokyo`; a comparação foi idêntica. No smoke com Chrome, o `<time>` do colunista permaneceu `24/09/2026` sob os três fusos testados. |
| **2 — minor / copy do consentimento** | **Resolvido** | `BannerConsentimentoCookies.tsx:24,47` explicita “publicidade de terceiros, como AdSense” na mensagem geral e em **Personalização**. O diff do componente contém somente essas duas alterações de texto; gate, handlers e estado não mudaram. |
| **3 — minor / payload e latência** | **Parcialmente resolvido; residual minor** | `page_size=6`, máximo de quatro autores e o mesmo `AbortSignal` foram observados; a normalização array/`results` foi exercitada com as duas formas. Porém o endpoint de perfil ainda devolve a lista completa de publicações (incluindo o conteúdo) e o deadline global de 2 s pode apagar a seção quando a listagem inicial demora; ver Finding 3 detalhado abaixo. |

### Finding 4 — `major` — formatadores de data compartilhados ainda quebram a hidratação da Home

- **Arquivos/linhas:** `frontend/lib/editorial.ts:147-167`, `frontend/components/home/NewsCard.tsx:63-65` e `frontend/components/home/UltimasNoticias.tsx:154-157`; `HomeClient.tsx:31-41,248`, `EmAlta.tsx:84` e `SecaoRegiao.tsx:23-29,163-184` usam o mesmo padrão de tempo relativo.
- **Cenário reproduzido:** o HTML server-side da Home continha `21/09 • 20:17` nos cards e `20:17` em **Últimas notícias** (fuso editorial do build). Com Chrome em `America/Sao_Paulo` os valores permaneciam iguais e não havia erro React; com o cliente em `UTC` eles passaram a `21/09 • 23:17`/`23:17`, e com `Asia/Tokyo` a `22/09 • 08:17`/`08:17`. A hidratação registrou os erros minificados React `#418`, `#423` e `#425` nos dois clientes. A data do colunista, já corrigida, permaneceu igual.
- **Impacto:** o Finding 1 original está fechado somente para `formatarDataConteudo`; a primeira renderização da Home ainda não é determinística entre servidor e qualquer fuso do visitante. Este residual é preexistente nos formatadores compartilhados, mas está no caminho SSR/hidratação explicitamente exigido pelo contrato e deve ser tratado como finding novo/major, não como aprovação silenciosa.
- **Correção sugerida:** definir a mesma zona editorial explícita em todos os formatadores de data/hora usados no HTML inicial (ou renderizar deterministicamente no servidor), e proteger/reavaliar qualquer cálculo baseado em `Date.now()` antes de uma futura aprovação.

### Revisão detalhada do Finding 3

- **Payload e limite:** o helper envia `...?destaque=1&page_size=6` e, no fallback, `...?page_size=6`; agrupa e corta os grupos em quatro, e todas as requisições da operação recebem o mesmo `AbortSignal`. Seis linhas ainda podem representar menos de quatro autores distintos quando um autor domina o recorte, e o endpoint de perfil continua sem paginação, serializando também o `conteudo` completo de cada publicação.
- **(a) timeout de 2 s:** não há evidência de que o backend saudável local exceda o limite, mas 2 s é um deadline rígido para uma etapa opcional. Se a listagem de destaques (ou o fallback) exceder 2 s, `carregarColunistas` retorna `[]`; `app/page.tsx` ainda aguarda o helper, portanto a revalidação pode gastar até 2 s e a seção desaparece, sem stale cache. É um risco minor residual, não uma garantia de que a seção fique vazia em operação normal.
- **(b) abort compartilhado:** um controller global não cancela uma listagem que já terminou. Perfil lento queima o deadline e aborta todos os perfis ainda pendentes; cada `catch` local ainda devolve o card com campos de perfil vazios. O teste independente preservou o perfil rápido e degradou apenas o lento, portanto o comportamento é aceitável como best-effort, mas acopla a qualidade de vários perfis ao mesmo orçamento.
- **(c) fallback `[]`:** retornar `[]` no abort é coerente com o contrato existente de “ocultar, nunca inventar” e mantém o restante da Home utilizável. O custo de UX é a perda da seção opcional; um orçamento maior ou fallback de dado antigo seria decisão de produto.
- **(d) normalização:** `frontend/lib/api.ts:712-719` está correto para o envelope DRF atual `{count, next, previous, results}` e para o array legado. Um backend novo na porta 8001 devolveu os dois formatos, e o helper com mock retornou a publicação esperada de cada um.

### Verificações de não-regressão da re-revisão

- `frontend/npx tsc --noEmit`: exit 0.
- `frontend/npm run build`: exit 0; Next 14.2.15 gerou 59/59 páginas.
- Standalone smoke: `/` → 200, `/noticia/1` → 200 e `/comunidade` → 200; as respostas não continham `Application error`, `Module not found` nem `Cannot find module`.
- `git diff --check -- frontend/`: exit 0.
- O smoke HTTP está verde, mas a verificação de hidratação em fuso alternativo continua vermelha para os formatadores de data compartilhados da Home.

### Novo veredito

**changes_requested**

O major original da data do colunista e o minor da copy foram corrigidos, e as salvaguardas de paginação, normalização e limite estão presentes. A aprovação continua bloqueada pelo major de hidratação recém-confirmado nos outros formatadores de data renderizados pela Home; o problema residual de payload/timeout é minor e deve ser corrigido ou explicitamente aceito. Este veredito substitui o `changes_requested` original para o fechamento da iteração 1. Nenhuma alteração de código ou commit foi feito nesta re-revisão.

## Re-revisão iteração 2 — 2026-09-24

**Escopo e método.** Reinspeção independente do working tree, isolada com `git diff -- frontend/`; mudanças de backend, Nginx e workflows foram ignoradas. Li o helper e os consumidores migrados, comparei as funções antigas com `git show HEAD:<arquivo>`, examinei os limites de SSR e rodei as verificações de fuso, TypeScript, build e smoke HTTP. Não alterei código nem criei commit; este artefato é a única atualização desta re-revisão.

### Finding 4 — `major` — data/hora dependente do fuso

**Status: RESOLVIDO; o problema sistêmico de datas está RESOLVIDO.**

- A busca exaustiva em `frontend/`, excluindo `node_modules/` e `.next/`, não encontrou `toLocaleDateString`, `toLocaleTimeString`, `toLocaleString` nem construtor `Intl.DateTimeFormat` fora de `frontend/lib/datas.ts` (o tipo `Intl.DateTimeFormatOptions` e o construtor central são as duas ocorrências do helper).
- `frontend/lib/datas.ts:9,27-30` define `FUSO_EDITORIAL = "America/Sao_Paulo"` e aplica `timeZone: FUSO_EDITORIAL` a todos os formatadores temporais; `LOCALE_EDITORIAL = "pt-BR"` é explícito. `formatarNumeroPtBR` usa `Intl.NumberFormat` e, corretamente, não tem fuso.
- Comparações representativas com o HEAD preservaram os padrões visuais: o `formatarDataHora` antigo de `frontend/lib/editorial.ts` produziu o mesmo `DD/MM • HH:MM` que o helper; o `fmt` antigo de `frontend/app/noticia/LeituraPremium.tsx` produziu o mesmo `data por extenso às HH:MM`; e os `toLocaleDateString("pt-BR")` de `frontend/app/comunidade/page.tsx` produziram o mesmo `DD/MM/AAAA`. Para `2026-09-24T00:30:05Z` no fuso editorial, os exemplos resultaram em `23/09 • 21:30`, `23 de setembro de 2026 às 21:30` e `23/09/2026`; a diferença fora de `America/Sao_Paulo` é a correção intencional, não uma alteração de formato.
- Os três comandos exigidos (`TZ=UTC`, `TZ=Asia/Tokyo` e `TZ=America/Sao_Paulo`) produziram a mesma linha JSON; o `cmp` entre os três arquivos retornou `IDÊNTICA nos três TZ`.
- A única mudança de fronteira que passou a renderizar dados reais no servidor nesta run foi `SecaoColunistas`: ela recebe a lista de `app/page.tsx`, mas sua data usa o helper determinístico. Os formatadores de `NewsCard`/`UltimasNoticias`, que já eram incluídos no SSR do Client Component, foram corrigidos em vez de criar uma nova divergência. Um smoke standalone adicional com HTML da Home sob `TZ=UTC` e `TZ=Asia/Tokyo` produziu o mesmo conjunto de datas (`21/09 • 19:21` e `21/09 • 20:17`). Não foi encontrada nova renderização de data no servidor que dependa do fuso do visitante; os helpers relativos por `Date.now()` permanecem dependentes do instante, como risco preexistente e não relacionado ao fuso.
- **Finding 5 — `minor` — data civil em `RadarClient`:** `frontend/app/radar/RadarClient.tsx:189` passa `p.dia` (`YYYY-MM-DD`, produzido por `TruncDate` no backend) para `formatarDataSemAno`; `new Date("2026-09-24")` representa meia-noite UTC e, ao ser convertido para o fuso editorial, mostra `23/09`. A comparação independente deu `24/09` no `fmtDia` antigo sob UTC/Tokyo e `23/09` no helper; portanto o formato `DD/MM` foi preservado, mas o valor de uma data-only pode estar um dia atrás. Renderizar esse caso por componentes/uma data ao meio-dia UTC, ou não usar um formatador de instante para `YYYY-MM-DD`.
- **Artefato de verificação:** `frontend/scripts/verificar-datas-tz.mjs` é útil como smoke manual real do helper e deve ser mantido/documentado; ele não é lixo. A saída e o comando de comparação foram documentados neste contrato: `cd frontend && TZ=UTC node --no-warnings --experimental-strip-types scripts/verificar-datas-tz.mjs` (idem para `TZ=Asia/Tokyo` e `TZ=America/Sao_Paulo`, seguido de `cmp`). Limitação: atualmente depende do `--experimental-strip-types` do Node 24, não é gate de npm/CI e apenas imprime JSON; transformá-lo em check portátil e assertivo é follow-up, não bloqueia esta run.

### Finding 3 — `minor` — timeout e payload dos colunistas

- O deadline de 5 s para a listagem é razoável como guardrail de uma etapa opcional e evita o antigo risco de espera indefinida; cada perfil tem controller/sinal dedicado e 2 s individual. Como os perfis são lançados em `Promise.all`, o custo adicional é o máximo de um perfil lento, não a soma de quatro timeouts.
- Falha/abort da listagem retornando `[]` é aceitável para a seção opcional: a Home continua utilizável e nenhum dado é inventado. Um perfil lento degrada somente seus campos opcionais. O payload do endpoint de perfil continua retornando a lista pública completa; fica como residual minor de projeção follow-up, sem bloquear esta run.
- A pior latência teórica é aproximadamente 5 s da listagem + 2 s dos perfis; deve ser monitorada como tradeoff de ISR, mas não encontrei motivo para rejeitar o desenho.

### Não-regressão da iteração 2

- `frontend/npx tsc --noEmit`: exit 0.
- `frontend/npm run build`: exit 0; Next 14.2.15 gerou 59/59 páginas.
- Smoke standalone: `/` → HTTP 200 e `/noticia/1` → HTTP 200; as respostas não continham `Application error`, `Module not found` nem `Cannot find module`.
- `git diff --check -- frontend/`: exit 0.

### Resumo da re-revisão

| Severidade | Quantidade |
|---|---:|
| blocker | 0 |
| major | 0 aberto (1 resolvido) |
| minor | 2 (Finding 5 e residual de Finding 3) |
| nit | 0 |

### Novo veredito

**approve_with_comments**

O finding major sistêmico de datas foi corrigido: não há chamada temporal direta restante fora do helper, a zona editorial é explícita, os três TZ produzem saídas idênticas e não foi encontrada nova divergência de SSR/hidratação. Os testes de não-regressão passam e o desenho de timeout/fallback é razoável. A aprovação fica com comentário não-bloqueante para corrigir o tratamento de `YYYY-MM-DD` no Radar e, futuramente, tornar o script de TZ um check portátil/assertivo; o payload de perfil e os relativos por instante permanecem limitações documentadas. Nenhuma alteração de código ou commit foi feito nesta re-revisão.
