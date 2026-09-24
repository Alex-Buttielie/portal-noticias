# Implementation History — 20260924-1000-p2-5-frontend

## Escopo e estado inicial

Run executor para os quatro itens de frontend da tabela P2-5 de `ANALISE_CUSTO_PERFORMANCE.md` (seção 5, “Outros (🟢)” e seção 7). A working tree já continha alterações de P1-6 e de outras runs; elas foram preservadas. Nenhum arquivo backend, workflow, Nginx ou Compose foi editado nesta run, e nenhum commit foi criado.

## Decisões e implementação

### 1. Colunistas no servidor/ISR

**Escolha:** opção (d), mover a carga para o Server Component/ISR da Home. Foi escolhida por ser a menor mudança que elimina a cascata por visitante sem criar endpoint agregado nem alterar contrato de API.

- `frontend/app/page.tsx:5,34-39,51-69`: `getData()` agora carrega `carregarColunistas(4)` em paralelo com os demais dados server-side e passa `colunistas` para `HomeClient`; o fallback de erro também retorna lista vazia, sem mocks de pessoas.
- `frontend/components/HomeClient.tsx:10,44-53,282`: nova prop `colunistas` e passagem para a seção.
- `frontend/components/SecaoColunistas.tsx:2-17,59-155`: removidos `useState`/`useEffect` e a chamada client-side a `carregarColunistas`; o componente virou apresentacional, mantendo cards, agrupamento já realizado no helper, foto/iniciais, perfil, selo, datas, links e empty state.
- `frontend/lib/colunistas.ts:68-75`: comentário/documentação ajustada para explicitar que a carga ocorre no servidor/ISR.

**Resultado:** a cada visita client-side à Home, `SecaoColunistas` não executa mais `obterPublicacoes({destaque:true})` → fallback `obterPublicacoes({})` → quatro `obterPerfilAutor`. As requisições restantes ficam no ciclo de revalidação do servidor (o helper continua best-effort e pode fazer 1–5 chamadas server-side conforme os dados). Não foi criado endpoint agregado, conforme a restrição.

### 2. Polling de `Últimas notícias`

**Escolha:** aumentar o intervalo padrão de 90 s para 180 s, mantendo polling e botão manual.

- `frontend/lib/editorial.ts:50,63-76`: `HOME_CONFIG_PADRAO.refreshUltimasSegundos` passou a 180; valores positivos persistidos são normalizados para pelo menos 180 s e no máximo 600 s. Assim, uma configuração antiga de 90 s não reintroduz o polling anterior.
- `frontend/components/home/UltimasNoticias.tsx:18-20,55-63`: documentação atualizada; a guarda existente `document.visibilityState === "visible"` foi mantida, portanto nenhuma requisição periódica é iniciada com a aba oculta. O botão “Atualizar” e a busca de filtro continuam usando o mesmo `obterFeed`/callback.

**Justificativa:** a Home já é ISR de 60 s (`app/page.tsx:13`) e o backend tem cache de 45 s; 180 s reduz tráfego por visitante sem remover a atualização automática nem depender de `router.refresh()`. A atualização manual continua disponível para frescor imediato.

### 3. AdSense com consentimento

**Escolha:** `personalizacao` como categoria para publicidade de terceiros; o default de `permiteCategoria` é negar.

- `frontend/components/AdsScript.tsx:4,11-33`: importou `permiteCategoria` e `EVENTO_CONSENTIMENTO_ALTERADO`; o estado inicia em `false`, é atualizado no cliente e reage ao evento de preferência; só renderiza `Script` com publisher ID e permissão; estratégia alterada de `afterInteractive` para `lazyOnload`.
- `frontend/components/AdsSlot.tsx:3,44-65`: o slot também observa a permissão, não faz `adsbygoogle.push({})` antes dela e só renderiza o `<ins>` real quando `personalizacao` está autorizado. Sem ID/slot/permissão, o placeholder visual original continua sendo retornado.

**Resultado:** não há script nem URL externa de AdSense antes do consentimento. Sem `NEXT_PUBLIC_ADSENSE_CLIENT_ID`, o comportamento de placeholder e ausência de chamada externa foi preservado.

### 4. Fonte única de `news_view`

**Escolha:** manter `NoticiaReporter` como fonte única, pois ele conhece `entryTipo`, `entryId`, `categoria`, tempo de leitura e scroll.

- `frontend/components/AnalyticsTracker.tsx:6-10,67-70`: removida a descrição de `news_view` derivado do pathname e adicionada declaração explícita de que a fonte é `NoticiaReporter`; nenhuma chamada `track({tipo:"news_view"})` existia no ramo de rotas do tracker.
- `frontend/components/Reporters.tsx:1-6,25-30`: comentários explicitam a fonte única; o evento inicial e o evento de saída com `tempo_leitura_seg`/`scroll_max_pct` foram preservados.

**Resultado:** não há duplicação entre tracker global e reporter; `news_click`, `page_view`, categoria, autor, radar, comunidade, busca, save/share e demais telemetria permanecem intactos.

## Evidências e validação

- `node` estrutural para `run-state.json`: JSON válido; `run_id`, `status`, `current_phase`, campos obrigatórios e contadores conferidos contra `agentic-framework/schemas/run-state.schema.json`.
- Check de placeholders dos contratos: `task-plan.md` e `implementation-contract.md` sem marcadores de template.
- Checklist `agentic-framework/prompts/contract-checklist.md`: escopo dentro/fora explícito, suposições motivadas, critérios de negócio no task plan, critérios dado/quando/então no implementation contract, não-objetivos/restrições preenchidos e `run_id`/deriva rastreáveis.
- `git diff --check`: exit 0.
- `frontend/npx tsc --noEmit`: exit 0, sem saída de erro.
- `frontend/npm run build`: exit 0; Next 14.2.15 compilou e gerou 59/59 páginas; First Load JS compartilhado reportado em 87,2 kB.
- Smoke do servidor standalone em `127.0.0.1:44924` após o build: `/` → HTTP 200; `/noticia/1` → HTTP 200; `/comunidade` → HTTP 200. As respostas verificadas não continham `Application error`, `Module not found`, `Cannot find module` nem a URL `pagead2.googlesyndication.com`/script AdSense.
- Inventário estático: `SecaoColunistas` é o único uso de `SecaoColunistas`, e a única ocorrência de `obterPerfilAutor` no fluxo da Home está no helper server-side; não há `afterInteractive` no componente de AdSense; `news_view` só aparece em `Reporters.tsx`/`lib/analytics.ts` e nos comentários/documentação de fonte única, não no tracker global.

## Limitações e pendências

- Não há suíte de testes frontend nem script `test` no `frontend/package.json`; a validação foi `tsc`, build, smoke HTTP e inspeção estática. Não foi criada suíte artificial nem nova dependência.
- O smoke não validou a resposta real da API de comunidade nem a renderização de um AdSense consentido com `NEXT_PUBLIC_ADSENSE_CLIENT_ID`/slots, porque o build local usa a configuração disponível e o escopo proíbe adicionar credenciais; o caminho de consentimento foi verificado por código e o caminho sem ID por HTTP.
- A revisão formal, documentação/histórico do pipeline e a linha em `agentic-framework/state/HISTORY.md` pertencem ao orquestrador/historian; esta pasta contém os contratos, estado e histórico de implementação solicitados.
- Nenhuma pendência funcional conhecida dentro dos quatro itens. Follow-up opcional: validar em CI com `NEXT_PUBLIC_ADSENSE_CLIENT_ID` e slots reais, e confirmar visualmente a troca de placeholder para `<ins>` após aceitar `personalizacao`.

## Remediação (iteração 1) — 2026-09-24 — remediator

### Finding 1 — `major` — data de colunista dependente do fuso

- **Correção:** a busca por `toLocaleDateString`/`Intl.DateTimeFormat` não encontrou helper existente com fuso explícito; por isso o helper `formatarDataConteudo` foi reutilizado em `frontend/lib/colunistas.ts:4,150-164` com `Intl.DateTimeFormat("pt-BR", ...)` e `timeZone: FUSO_EDITORIAL`, com `FUSO_EDITORIAL = "America/Sao_Paulo"`. A chamada de `frontend/components/SecaoColunistas.tsx:119-121` continua usando o mesmo helper, mas agora recebe uma string determinística no SSR e na hidratação.
- **Evidência:** o componente `SecaoColunistas` foi renderizado com uma publicação em `2026-09-24T00:30:00Z` sob `TZ=America/Sao_Paulo` e `TZ=America/New_York`; ambos os renders produziram `23/09/2026` (não `24/09/2026`). Isso confirma que o fuso do runtime não altera o texto.

### Finding 2 — `minor` — categoria de consentimento sem explicitar publicidade

- **Correção:** `frontend/components/BannerConsentimentoCookies.tsx:24,47` recebeu copy curta em pt-BR: a mensagem geral e a descrição de **Personalização** agora dizem explicitamente “publicidade de terceiros, como AdSense”. Nenhum estado, gate ou handler foi alterado.
- **Evidência:** o diff do componente contém somente as duas alterações de texto; o gate continua usando `personalizacao` e o build/smoke não encontrou URL de AdSense sem permissão.

### Finding 3 — `minor` — payload e espera da carga server-side

- **Correção:** `frontend/lib/api.ts:691-720` adicionou `page_size` opcional e normaliza a resposta paginada (`results`) contra o array legado, sem mudar o contrato de retorno `Promise<Publicacao[]>`. `frontend/lib/colunistas.ts:79-94` envia `page_size=6` para destaques e fallback; `frontend/lib/colunistas.ts:82-83,121-147` aplica um `AbortController` com deadline de 2 s a toda a operação server-side. Os grupos são limitados a `quantidade` (4 na Home), então há no máximo quatro perfis por carga; quando o perfil responde, sua lista completa preserva a contagem/especialidade apesar da listagem paginada (`frontend/lib/colunistas.ts:127-143`).
- **Evidência:** a verificação do helper real registrou `page_size=6`, quatro chamadas de perfil e o mesmo `AbortSignal`; uma simulação de resposta pendente abortou em `2003 ms` e retornou `[]` sem travar a revalidação. `frontend/app/page.tsx:34-40` continua aguardando `carregarColunistas(4)` em paralelo com o restante da Home, mas agora a falha lenta é abortada. A API não oferece `fields`/projeção para publicações ou perfis; não foi criado endpoint nem alterado backend. O payload do endpoint de perfil ainda pode incluir a lista pública do autor, por isso fica como limitação residual de uma futura API de projeção.

### Validação da remediação

- `frontend/npx tsc --noEmit`: exit 0.
- `frontend/npm run build`: exit 0; Next 14.2.15 gerou 59/59 páginas.
- Render determinístico de `SecaoColunistas`: `23/09/2026` em `TZ=America/Sao_Paulo` e `TZ=America/New_York`.
- Smoke standalone final em `127.0.0.1:44932`: `/` → HTTP 200, `/noticia/1` → HTTP 200 e `/comunidade` → HTTP 200; nenhuma resposta continha `Application error`, `Module not found`, `Cannot find module` ou URL do AdSense.
- `git diff --check`: exit 0.

**Estado da iteração:** os 3 findings do contrato foram tratados (1 major e 2 minor); a run retorna à fase `review` para a re-revisão independente. Nenhum commit foi criado e nenhum arquivo backend, workflow, Nginx ou Compose foi alterado nesta remediação.

## Remediação (iteração 2) — 2026-09-24 — remediator

### Finding 4 — `major` — formatadores de data/hora ainda dependiam do fuso

- **Inventário:** a busca exaustiva em `frontend/`, excluindo `node_modules/` e `.next/`, encontrou 33 ocorrências de `toLocaleDateString`/`toLocaleTimeString`/`toLocaleString` (29 de datas/horas e 4 numéricas) e 5 construtores `Intl.DateTimeFormat` (4 sem a zona editorial; o de `colunistas.ts` já estava fixado na iteração 1). Foram migrados 20 arquivos com formatador temporal direto; a busca adicional encontrou o formatador manual de dia que existia em `RadarClient` e o ano editorial de `Rodape`, também centralizados. `NewsCard` foi religado ao helper. Isso totaliza **23 arquivos de apresentação de data/hora**; `app/admin/metricas/page.tsx` foi o único arquivo adicional migrado para a locale explícita dos números.
- **Correção:** `frontend/lib/datas.ts:9-108` é agora a única implementação de data/hora do frontend. Todas as funções temporais usam `LOCALE_EDITORIAL = "pt-BR"` e `timeZone: FUSO_EDITORIAL = "America/Sao_Paulo"`, o mesmo fuso de `backend/config/settings.py:271`. `frontend/lib/editorial.ts:5,147-165` apenas reexporta os formatadores e mantém as funções relativas; `frontend/lib/colunistas.ts:3,170-174` faz `formatarDataConteudo` delegar a `formatarDataCurta`.
- **Consumidores migrados:** `frontend/components/home/NewsCard.tsx:9-17,63-65`, `frontend/components/home/UltimasNoticias.tsx:3-7,101-102`, `frontend/components/CoberturaCompleta.tsx:8-9,58`, `frontend/components/ui/calendar.tsx:4-5,18`, `frontend/app/ao-vivo/page.tsx:7,26`, `frontend/app/arquivo/page.tsx:7,26`, `frontend/app/noticia/LeituraPremium.tsx:17,109`, `frontend/app/paginas/[slug]/page.tsx:5,11`, `frontend/app/termos/page.tsx:4,9`, `frontend/app/comunidade/page.tsx:18,252,546`, `frontend/app/comunidade/[id]/page.tsx:16,234,274`, `frontend/app/jornalista/status/page.tsx:9,19`, `frontend/app/admin/assinaturas/page.tsx:9,16`, `frontend/app/admin/usuarios/page.tsx:9,18`, `frontend/app/admin/fila/page.tsx:14,226`, `frontend/app/admin/limites/page.tsx:14,95,168,191`, `frontend/app/admin/planos/page.tsx:14,83,102,114`, `frontend/app/admin/robos/page.tsx:18,193,200,205,244,326,364,442`, `frontend/app/admin/page.tsx:12,222,380`, `frontend/app/radar/RadarClient.tsx:11,189` e `frontend/components/Rodape.tsx:2,43`. Os usos numéricos de `app/admin/metricas/page.tsx:26,39,56,383` foram centralizados em `formatarNumeroPtBR` (`Intl.NumberFormat`, sem dependência de fuso).
- **Formatos preservados:** `DD/MM/AAAA`, `DD/MM • HH:MM`, `DD/MM/AAAA, HH:MM`, `DD/MM/AAAA, HH:MM:SS`, data por extenso, data por extenso com hora, mês/ano, ano e números pt-BR. A busca final não encontrou chamadas diretas fora de `frontend/lib/datas.ts` (o único `Intl.DateTimeFormat` restante é o formatador central). O rótulo secundário `RadarClient` que ainda usa `p.dia.slice(5)` foi mantido: é uma data-only string em `MM-DD`, sem `Date`/fuso, e trocá-lo por `DD/MM` alteraria o texto.

### Relativas (`timeAgo`, `rel` e `Date.now()`)

- **Avaliação:** não foram “corrigidas” com `timeZone`, conforme solicitado. `frontend/lib/editorial.ts:147-165` e os helpers relativos de `HomeClient`, `SecaoRegiao`, `app/admin/robos` e `app/admin/fila` continuam calculando elapsed time a partir de `Date.now()`. O mesmo relógio participa dos scores/seleções em `editorial.ts:221,287-303`; essa é uma dependência temporal de ranking, não um fuso de formatação.
- **Risco residual:** se o servidor e o browser atravessarem uma fronteira de minuto/hora/dia entre a renderização e a hidratação, um relativo pode mudar de bucket (`1min` → `2min`, por exemplo). Isso é uma condição temporal, não uma divergência de fuso; aplicar `America/Sao_Paulo` à string relativa não seria correção. A decisão foi documentar e preservar o comportamento existente, sem introduzir um segundo timestamp ou uma correção artificial.

### Finding 3 — `minor` — timeout e isolamento dos colunistas

- **Correção:** `frontend/lib/colunistas.ts:5-10,83-168` elevou o deadline de publicações de 2 s para **5 s** (`TIMEOUT_PUBLICACOES_COLUNISTAS_MS`) para tolerar a latência normal do backend/ISR. As requisições de publicações mantêm um signal dedicado. Cada perfil recebe um controller independente de 2 s (`TIMEOUT_PERFIL_COLUNISTA_MS` em `:128-149`); um perfil lento/abortado perde apenas seus campos opcionais e não cancela os demais.
- **Fallback:** falha/abort das publicações continua retornando `[]`, o que foi confirmado aceitável: a seção opcional é ocultada e a Home continua utilizável sem inventar dados. Falha de perfil degrada somente o card correspondente para campos opcionais vazios. Nenhum endpoint, contrato de backend ou projeção foi adicionado; o endpoint de perfil ainda pode retornar uma lista pública maior, como limitação residual de payload.
- **Justificativa:** 5 s continua limitado para o ISR, enquanto o orçamento separado de 2 s por perfil impede que um perfil lento consuma/cancele toda a carga da Home. O signal compartilhado e o deadline global original de 2 s não são mais usados.

### Evidência de determinismo por fuso

Foi adicionado `frontend/scripts/verificar-datas-tz.mjs`, que importa o helper real. Executado com Node 24 usando `--experimental-strip-types` nos três processos abaixo, cada um produziu exatamente a mesma linha:

| `TZ` do processo | saída JSON |
|---|---|
| `UTC` | `{"dataCurta":"23/09/2026","dataHora":"23/09 • 21:30","dataHoraCompleta":"23/09/2026, 21:30:05","dataHoraCompacta":"23/09/2026, 21:30","dataPorExtenso":"quarta-feira, 23 de setembro de 2026","dataHoraPorExtenso":"23 de setembro de 2026 às 21:30","horaComSegundos":"21:30:05","mesAno":"setembro de 2026","ano":"2026","numero":"1.234.567,89"}` |
| `Asia/Tokyo` | `{"dataCurta":"23/09/2026","dataHora":"23/09 • 21:30","dataHoraCompleta":"23/09/2026, 21:30:05","dataHoraCompacta":"23/09/2026, 21:30","dataPorExtenso":"quarta-feira, 23 de setembro de 2026","dataHoraPorExtenso":"23 de setembro de 2026 às 21:30","horaComSegundos":"21:30:05","mesAno":"setembro de 2026","ano":"2026","numero":"1.234.567,89"}` |
| `America/Sao_Paulo` | `{"dataCurta":"23/09/2026","dataHora":"23/09 • 21:30","dataHoraCompleta":"23/09/2026, 21:30:05","dataHoraCompacta":"23/09/2026, 21:30","dataPorExtenso":"quarta-feira, 23 de setembro de 2026","dataHoraPorExtenso":"23 de setembro de 2026 às 21:30","horaComSegundos":"21:30:05","mesAno":"setembro de 2026","ano":"2026","numero":"1.234.567,89"}` |

Comandos usados: `TZ=UTC node --no-warnings --experimental-strip-types scripts/verificar-datas-tz.mjs`, e o mesmo comando com `TZ=Asia/Tokyo` e `TZ=America/Sao_Paulo`. Um `cmp` entre os três arquivos de saída retornou `IDÊNTICA nos três TZ`. A igualdade das três saídas demonstrou que o texto depende do instante, não do `TZ` do processo.

### Validação final da iteração 2

- `frontend/npx tsc --noEmit`: exit 0.
- `frontend/npm run build`: exit 0; Next 14.2.15 gerou 59/59 páginas.
- `git diff --check -- frontend`: exit 0.
- Inventário final: nenhum `toLocaleDateString`, `toLocaleTimeString`, `toLocaleString` ou `Intl.DateTimeFormat` direto fora de `frontend/lib/datas.ts`.
- Nenhum commit foi criado; nenhum backend, workflow, `infra/` ou `docker-compose.yml` foi alterado.

**Estado da iteração 2:** Finding 4 (major) resolvido; a parte de timeout/abort do Finding 3 foi corrigida e o fallback `[]` foi confirmado aceitável. A run retorna a `current_phase: review` para a re-revisão independente, com o risco de payload/projeção do endpoint de perfil e os relativos dependentes do instante mantidos como limitações documentadas.

