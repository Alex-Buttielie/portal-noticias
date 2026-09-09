# History — components (run 20260909-1200-frontend-rebuild)

Agente: `frontend-ui-executor-components`. Escopo: `frontend/components/ui/*`,
`BlocoEditoria.tsx`, `MaisLidas.tsx`, `DetalheNoticia.tsx` e visuais
`components/*.tsx`. Não tocados (outro agente): `globals.css`, `Header`,
`Rodape`, `app/page.tsx`. `lib/api.ts` lido, não editado.

## O que foi feito

- `ui/Button.tsx` — reescrito sobre `.botao/.botao--*`: remove classe
  inexistente `botao--carregando`; `carregando` agora renderiza `.spinner` +
  texto, com `aria-busy`/`aria-disabled`. API (variante/tamanho/carregando) intacta.
- `ui/Cards.tsx` — faixa 16/9 (`aspectRatio` inline, gradiente+emoji da
  editoria), título serifado com clamp inline, resumo em 2 linhas
  (`.limitar-linhas-2`), meta unificada com `<time dateTime>`. Rotas e
  `BotaoSalvar` mantidos.
- `ui/Estados.tsx` — `SkeletonCard` passa a espelhar o cartão real (faixa 16/9
  + 3 linhas, sem classe inexistente `cartao-noticia--esqueleto`); `Empty`/`Error`
  ganham marca decorativa; botão "Tentar novamente" com 40px. APIs intactas.
- `ui/SearchBar.tsx` — pílula (`busca--pill` + fallback `borderRadius`),
  botão de envio visível ≥44px com `aria-label`, `id` único via `useId`
  (antes fixo `busca-global`). Debounce/lógica idênticos.
- `ui/FormField.tsx` — `aria-describedby` agora também em `CampoAreaTexto` e
  `CampoSelecao` (antes só no input); rótulos/props intactos.
- `ui/Data.tsx` — paginação movida para fora de `.tabela-wrapper` (evita
  corte/rolagem junto da tabela), botões com 40px. API intacta.
- `ui/Drawer.tsx` — botão fechar com `aria-label` específico + 40px. Lógica
  (Escape, clique fora, trava de scroll, foco inicial) idêntica.
- `ui/ShareButtons.tsx` — rótulos `aria-label` por ação, `aria-live` no
  "Copiar link", ícones decorativos, 40px. Lógica (Web Share/clipboard/WhatsApp) idêntica.
- `ui/ReadingProgress.tsx` — adicionado `aria-valuetext` em pt-BR. Lógica idêntica.
- `BlocoEditoria.tsx` — migrado de `.editoria-*` para o sistema de seção
  (`.secao-bloco/cabecalho/titulo/eyebrow/ver-tudo` + `.grade-noticias` 3→2→1 +
  `.card-noticia` com imagem 16/9, categoria colorida, título clamp, resumo 2
  linhas, meta com `<time>`). Props (`categoria/itens/onVerTodas`) e rotas intactas.
- `MaisLidas.tsx` — ranking numerado mantido; loading agora usa
  `SkeletonLista` com `aria-busy`; seção com `aria-labelledby`; datas com
  `<time dateTime>`. Hook `useMaisLidas(limite)` e rotas intactos.
- `DetalheNoticia.tsx` — cabeçalho editorial (badges + `<time>` + h1 com
  clamp), faixa de share sticky (classe + fallback inline), parágrafos em
  `.artigo-corpo` (68ch) com `detalhe-dropcap` no 1º, fontes como
  `.cartao-noticia` com `aria-label`, "Voltar ao feed" ≥44px. Hooks, fetch,
  relacionados e registro de leitura idênticos.
- `Chip.tsx` — removido `all: unset` (matava anel de foco e altura mínima);
  reset visual preservado via inline sem zerar `outline`. API intacta.
- `Dropdown.tsx` — gatilho `botao botao-secundario` (legado) →
  `botao botao--secundaria botao--medio`. API intacta.
- `BotaoSalvar.tsx` — `aria-label`/`title` com título da notícia + 40px. Lógica intacta.
- `CartaoEsqueleto.tsx` — migrado para `.cartao-noticia` + faixa 16/9 (sem props, sem consumidores quebrados).

## Verificados, sem alteração (já conformes ao design system)

`Accordion`, `Badge`, `Modal`, `Tabs`, `Tooltip`, `ThemeToggle`,
`CommandPalette`, `PorQueEstouVendoIsso` — classes, foco visível (global),
`aria-*` e reduced-motion (global) já atendem ao contrato.

## Classes CSS novas necessárias

Ver `agentic-framework/state/run-20260909-1200-frontend-rebuild/css-needs-components.md`:
`busca--pill`, `share-sticky`, `detalhe-dropcap::first-letter` (única sem
fallback) + sugestões de `min-height: 40px` em `.botao--pequeno`/`.botao-salvar`
e clamp em `.cartao-noticia__titulo`. Todas com fallback inline aplicado.

## Resultado tsc

`node_modules/.bin/tsc --noEmit -p tsconfig.json` em `frontend/` → exit 0,
sem saída (npx direto falhou por tentar buscar no registry; usado o binário local).

## Pendências

- Agente shell: incluir (ou não) as 3 classes de `css-needs-components.md` —
  visual funciona sem elas via fallbacks, exceto a capitular (`detalhe-dropcap`).
- Sem dependências novas; sem mudanças em dados/props/rotas.
