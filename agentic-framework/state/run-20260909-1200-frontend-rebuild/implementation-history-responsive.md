# implementation-history — responsive/a11y (run 20260909-1200-frontend-rebuild)

Agente: `frontend-responsive-a11y` · 2026-09-09 · working dir `C:\alex\brd_portal_noticias`.
Fontes lidas: `design-spec.md`, `css-needs-components.md`, `css-needs-pages.md`,
`frontend/app/globals.css`, `frontend/components/Header.tsx`, `frontend/app/page.tsx`
(+ `layout.tsx`, `Rodape.tsx`, `BotaoSalvar.tsx`, `SearchBar.tsx`, `Button.tsx` p/ contexto).

## Achado crítico (fora do escopo nominal, reparado)

`frontend/app/globals.css` estava **truncado no disco**: terminava na linha 575, no meio
da regra `.card-noticia-resumo, .cartao-noticia__resumo`, com o marcador literal
`...[truncated 20887 chars]` gravado no arquivo (resto da reescrita do agente shell
perdido — o original tinha 3087 linhas). Com isso faltavam: sistema `.botao`,
`.botao-salvar`, `.rodape-grid`, `.tabela-wrapper`, `.lista-compacta`,
`.banner-atualizacao`, `.faixa-publicidade`, `.newsletter-box`, `.bloco-sidebar`,
`.drawer`, todas as media queries e todo o bloco a11y final. Reparado com um
**APÊNDICE** ao final do arquivo (regras posteriores vencem a cascata; nenhum token
do `:root` §1 foi redefinido — só um `:root` ADITIVO com `--bp-*`, `--container-max`,
`--altura-header`, `--largura-sidebar`).

## Mudanças feitas (só `frontend/app/globals.css`, sem lógica JS)

1. **3 classes pedidas** (`css-needs-components.md`): `.busca--pill .busca__campo`
   (pill; permite remover o `style` inline do `SearchBar`), `.share-sticky`
   (sticky sob o header, `z-index: var(--z-banner)`), `.detalhe-dropcap::first-letter`
   (capitular editorial). Sem duplicar tokens — só `var()`.
2. **Botoes 40px**: sistema `.botao` (base fora do ar após truncamento) recriado com
   variantes `--primaria/--secundaria/--fantasma/--perigo`, tamanhos
   `--pequeno` (**min 40px**)/`--medio` (44px)/`--grande` (52px) e `.botao-salvar`
   (**min 40px**, `--ativo`); permite remover os `style={{ minHeight: 40 }}` inline.
3. **Overflow-x**: `grep 100vw` → só 1 ocorrência, no comentário do cabeçalho (§6);
   nenhuma regra real usa `100vw` (nada a corrigir). Garantidos: `html,body`
   `overflow-x: hidden` (já existia), `img/video/svg/iframe max-width:100%`
   (existia; somado `iframe{border:0}`), `.tabela-wrapper` (`overflow-x:auto`,
   `max-width:100%`) + `.tabela` base, container fluido
   `min(1200px, 100% - 2rem)` + `@480px → 100% - 3rem`.
4. **Breakpoints 480/768/1024/1280** (mobile-first, só `min-width`):
   - Header: hamburger (`.botao-menu-mobile`) visível na base e `display:none ≥1024px`
     (portanto visível ≤960px ✓); nav colapsada (`display:none`) até `.aberto`
     (classe que o `Header.tsx` já alterna com `aria-expanded`/`aria-controls` ✓,
     nenhum atributo aria precisou ser adicionado); `busca-atalho` oculta na base,
     `inline-flex ≥480px`.
   - Grades: `.grade-noticias` (`auto-fill minmax(min(300px,100%),1fr)`) = 1col mobile /
     2col tablet / 3col desktop por construção; `.lista-compacta` recriada (coluna).
   - `portal-layout`: base 1 coluna + `.sidebar` estática; `≥1024px` 2 colunas
     (`minmax(0,1fr) 320px`) + sidebar `sticky`; `≥1280px` hero com padding cheio.
   - `.mosaico`: base 1 coluna (evita overflow mobile), 2 colunas `≥1024px`.
   - Rodapé (`.rodape-grid`: marca + 3 navs): 1col base → 2col `≥768px` → 4col `≥1024px`;
     links/social `≥40px`.
5. **A11y (só CSS + zero mudança JS)**:
   - Foco visível global `:focus-visible` + `box-shadow var(--anel-foco)` em inputs
     (já existiam, preservados); skip-link `.pular-para-conteudo` (já existia).
   - **Novo**: bloco `prefers-reduced-motion: reduce` (zera animation/transition,
     `scroll-behavior:auto`, cobre `*`, `::before/after`); bloco `@print`
     (esconde header/rodape/ads/banner/compartilhar/drawer/palette, links http com URL).
   - Alvos `≥40px`: regra global `button, a.botao, input, select, textarea`
     (já existia) + `min-height:40px` em `.nav-editoria/.topo__pill`, links do rodapé,
     social, `.link-nulo`, botão do banner; sem `#aaa` hardcoded novo (usa tokens).
6. **Estruturais mínimos de página** (perdidos no truncamento, usados por `page.tsx`):
   `.controles-feed`, `.link-nulo`, `.faixa-publicidade`, `.banner-atualizacao`,
   `.newsletter-box`, `.bloco-sidebar(+cabecalho/titulo)`, `.sugestao-adaptativa(acoes)`,
   `.sentinela-carregamento`, `.drawer-fundo/.drawer(+cabecalho/titulo/corpo`,
   bottom-sheet mobile → lateral `≥480px)`.

## grep `100vw` (frontend/)

- `Select-String -Pattern "100vw"`: **1 match** —
  `frontend/app/globals.css:6` (comentário de documentação, sem efeito). Nenhum
  `.tsx/.ts/.css` usa `100vw` em regra real → **nada a corrigir**.

## tsc

- `npx tsc --noEmit -p frontend/tsconfig.json` → **falhou no npx** (shim "This is not
  the tsc command you are looking for"; TypeScript não resolvido via npx).
- Fallback `frontend/node_modules/.bin/tsc --noEmit -p frontend/tsconfig.json` →
  **exit 0, zero erros**.

## Não feito / riscos

- Toast/modal/dropdown/tabs/tooltip/accordion/chip/badge sem cobertura completa
  (só aliases parciais herdados) — fora do escopo da missão; componentes têm fallback
  inline ou estilos próprios (ex.: `palette-*` intacto).
- Contraste AA depende dos tokens do shell (mantidos); dark usa `prefers-color-scheme`
  + `data-theme` (preservados).
- `.drawer` usa `var(--cor-overlay, rgba(...))` com fallback, pois o token não existe
  no `:root` atual (previsto na spec §2, não adicionado p/ não duplicar tokens).

## Apêndice de remediação — agente `frontend-remediator` · 2026-09-09

1. **Verificação `frontend/app/globals.css`** (pós-rebuild do responsive-a11y):
   - Sem palavra `truncated` (Select-String, 0 matches); sem bloco incompleto —
     arquivo termina com `@media print {...}` fechado.
   - Chaves balanceadas: `open=268 close=268` (pré-fix; `271/271` pós-fix).
   - `@media`: 15 ocorrências; `prefers-reduced-motion: reduce` presente (§J).
   - Classes pedidas presentes: `busca--pill` (:648), `share-sticky` (:649),
     `detalhe-dropcap` (:654), `tabela-wrapper` (:661), `portal-layout` (:488 + :709),
     `grade-noticias` (:492), `pular-para-conteudo` (:212).
   - `.portal-layout` stacking OK: base 1 coluna (:709) + `.sidebar` estática;
     `≥1024px` 2 colunas + sidebar sticky (:711-714). Nada a adicionar.
2. ** Falha encontrada e corrigida**: `entrada-suave` referenciada em 3 regras
   (:383 modal, :437 toast, :534 skeleton) mas `@keyframes entrada-suave`
   **não definido** (só existia `@keyframes giro`). Adicionada 1 linha ao lado do
   `giro` (:638):
   `@keyframes entrada-suave { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: none; } }`
   Coberta pelo `reduced-motion` global (`animation:none !important`). Sem mudança
   de design — só define a animação já usada.
3. **Build verde**:
   - `frontend/node_modules/.bin/tsc --noEmit -p frontend/tsconfig.json` → exit 0.
   - `npm run build --prefix frontend` → exit 0 (todas as rotas geradas, First Load
     87.1 kB). Nenhuma correção TSX necessária.
4. **Veredito**: reconciliado — QA anterior (truncado/0 @media/sem reduced-motion)
   **superado**; rebuild confirmado (777 linhas, 15 @media, reduced-motion,
   keyframes completo). Build verde.

## Apêndice de remediação final — agente `frontend-remediator-final` · 2026-09-09
Reviewer: approve_with_comments (4 minor + 2 nit). Corrigidos SOMENTE estes,
sem redesign, sem mudança de lógica de dados/rotas/api.

1. **`frontend/app/globals.css` — `.limitar-linhas-2` / `.limitar-linhas-3`**
   (usados por `ui/Cards.tsx` e `BlocoEditoria`, estavam sem definição):
   ```css
   .limitar-linhas-2, .limitar-linhas-3 {
     display: -webkit-box;
     -webkit-box-orient: vertical;
     overflow: hidden;
   }
   .limitar-linhas-2 { -webkit-line-clamp: 2; line-clamp: 2; }
   .limitar-linhas-3 { -webkit-line-clamp: 3; line-clamp: 3; }
   ```
2. **`DetalheNoticia.tsx` + `globals.css` — `.share-sticky` com fallback sólido**:
   CSS passa a declarar `background: var(--cor-fundo-card);` →
   `background: var(--vidro);` → `background: color-mix(in srgb,
   var(--cor-fundo) 88%, transparent);` (fallback antes do color-mix);
   removidos `background`/`backdropFilter` inline do TSX que sobrescreviam a
   cascata (mantidos só position/top/zIndex/padding/margin).
3. **`frontend/components/Header.tsx` — foco + Escape**:
   - Busca colapsável: `useRef<HTMLInputElement>` (`campoBuscaRef`) + `useEffect`
     `[buscaAberta]` → `campoBuscaRef.current?.focus()` ao abrir
     (`aria-expanded=true`); ref ligado ao `<input id="...-campo">`.
   - Nav mobile: `useEffect` `[menuAberto]` com listener `keydown` → `Escape`
     fecha (`setMenuAberto(false)`), com cleanup.
4. **`frontend/components/Rodape.tsx` — links externos**: sociais com `http`
   recebem `target="_blank" rel="noopener noreferrer"` condicional
   (`s.href.startsWith("http") ? ... : undefined`); `aria-label` preservado;
   `/rss.xml` interno segue sem target.
5. **Verde confirmado**:
   - `frontend/node_modules/.bin/tsc --noEmit -p frontend/tsconfig.json` → exit 0.
   - `npm run build --prefix frontend` → exit 0 (32 rotas, First Load 87.1 kB;
     warnings `fetch failed` no prerender são ausência de backend local, sem
     falha no build).
