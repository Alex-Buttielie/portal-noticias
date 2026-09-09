# Documentation Update — run 20260909-1200-frontend-rebuild

- **run_id:** 20260909-1200-frontend-rebuild
- **Data (UTC):** 2026-09-09
- **Fontes:** `implementation-history-shell.md`, `implementation-history-components.md`, `implementation-history-pages.md`, `implementation-history-responsive.md`, `test-report.md` (veredito PASSED), `code-review-contract.md` (veredito `approve_with_comments`), `design-spec.md`, `css-needs-*.md`, `implementation-contract.md` v1.
- **Estado final verificado:** `frontend/app/globals.css` 788 linhas, 15 `@media`, `tsc --noEmit` exit 0, `npm run build --prefix frontend` exit 0 (32 rotas, First Load 87.1 kB). Sem alteração em `backend/` nem `frontend/lib/api.ts`. Sem dependência nova.

## 1. O que mudou no visual

### 1.1 Shell (`globals.css` + `Header.tsx` + `Rodape.tsx`)
- `frontend/app/globals.css` reescrito (mobile-first, CSS puro, sem `@import` remoto). Cabeçalho do arquivo declara: container fluido `min(1200px, 100% - 2rem)`, `html,body { overflow-x: hidden }`, aliases legados preservados.
- Container: `width: min(1200px, 100% - 2rem); margin-inline: auto` (em `≥480px` vira `100% - 3rem`). Nada de padding lateral fixo.
- Overflow-x: eliminados os dois culpados do CSS antigo — `.ticker` com `margin: 0 calc(50% - 50vw); width: 100vw` virou faixa contida `width: 100%`; `.drawer` com `min(420px, 100vw)` virou `100%`. Grep final: 1 ocorrência de `100vw`, só em comentário (linha 6). Regras reais: zero.
- Grade: `.grade-noticias` (e `.grade-cartoes`/`.editoria-grade`) agora `repeat(auto-fill, minmax(min(300px, 100%), 1fr))` — 1 col mobile / 2 col tablet / 3 col desktop por construção, sem media query por nº de colunas.
- Portal: `.portal-layout` base 1 coluna + `.sidebar` estática; em `≥1024px` vira `minmax(0, 1fr) 320px` (`var(--largura-sidebar)`) + sidebar `position: sticky; top: 132px`.
- `Header.tsx` rebuild: logo, busca colapsável (botão `aria-expanded`/`aria-controls` + form expansível; em `≤1024px` vira linha full-width), hamburger `.botao-menu-mobile` (`aria-expanded`/`aria-controls`, fecha ao trocar de rota, fecha com `Escape`, foco vai para o campo ao abrir a busca), nav editorias uppercase com `aria-current="page"` + secundária (Últimas/Comunidade/Radar/Premium + Jornalista/Empresa/Admin condicional), `ThemeToggle`, avatar inicial + Sair / Entrar + Assine, palette Ctrl+K mantido.
- `Rodape.tsx` rebuild: `footer.rodape.rodape--dark`, grid marca + Seções + Institucional (Termos/Privacidade/Preferências cookies/Política editorial) + Conta; social com `aria-labels`; links `http` com `target="_blank" rel="noopener noreferrer"` (`/rss.xml` interno sem target); barra copyright + links rápidos.
- `layout.tsx`: SEM ALTERAÇÃO (metadata/SEO/fonts/JsonLd/Providers/skip-link `main#conteudo-principal`/script anti-flash preservados).
- Dark mode: `:root[data-theme="dark"]` explícito (precedência) + `prefers-color-scheme` só quando sem `data-theme="light"`.

### 1.2 Componentes (`components/ui/*`, `BlocoEditoria`, `MaisLidas`, `DetalheNoticia`)
Lógica/dados/props/rotas intactas — só JSX estrutural, classes e a11y:
- `Button`: sobre `.botao/.botao--*`; `carregando` renderiza `.spinner` + texto com `aria-busy`/`aria-disabled` (remove classe inexistente `botao--carregando`).
- `Cards`: faixa 16/9 + gradiente/emoji, título serifado com clamp inline, resumo 2 linhas (`.limitar-linhas-2`), meta com `<time dateTime>`.
- `Estados`: `SkeletonCard` espelha o cartão real (faixa 16/9 + 3 linhas); `Empty`/`Error` com marca decorativa; "Tentar novamente" 40px.
- `SearchBar`: pílula (`busca--pill` + fallback inline), botão envio ≥44px com `aria-label`, `id` único via `useId` (antes fixo `busca-global`).
- `FormField`: `aria-describedby` também em `CampoAreaTexto`/`CampoSelecao`.
- `Data`: paginação fora de `.tabela-wrapper` (não corta junto da tabela), botões 40px.
- `Drawer`: fechar com `aria-label` específico + 40px (Escape/clique-fora/trava-scroll/foco idênticos).
- `ShareButtons`: `aria-label` por ação, `aria-live` no "Copiar link", 40px.
- `ReadingProgress`: `aria-valuetext` pt-BR.
- `BlocoEditoria`: migrado de `.editoria-*` para `.secao-bloco/cabecalho/titulo/eyebrow/ver-tudo` + `.grade-noticias` + `.card-noticia` (imagem 16/9, categoria colorida, clamp, resumo 2 linhas, `<time>`).
- `MaisLidas`: ranking numerado; loading com `SkeletonLista` + `aria-busy`; `aria-labelledby`; `<time dateTime>`.
- `DetalheNoticia`: cabeçalho editorial (badges + `<time>` + h1 clamp), share sticky, corpo `.artigo-corpo` (68ch) com capitular no 1º parágrafo, fontes como `.cartao-noticia` com `aria-label`, "Voltar ao feed" ≥44px.
- `Chip`: removido `all: unset` (matava foco/altura); `Dropdown`: gatilho `botao botao-secundario` → `botao botao--secundaria botao--medio`; `BotaoSalvar`: `aria-label`/`title` com título + 40px; `CartaoEsqueleto`: migrado para `.cartao-noticia` + faixa 16/9.
- Verificados sem alteração (já conformes): `Accordion`, `Badge`, `Modal`, `Tabs`, `Tooltip`, `ThemeToggle`, `CommandPalette`, `PorQueEstouVendoIsso`.

### 1.3 Páginas (`app/page.tsx` + `app/*/page.tsx`)
- Achado: `app/page.tsx` já tinha o layout do contrato (hero "Seu rio", grade + sidebar sticky com `MaisLidas`/`newsletter-box`/salvos, "Para você", "Últimas" em `lista-compacta` + `HorizontalNewsCard`, `BlocoEditoria`, teaser comunidade). Trabalho foi remover classes inexistentes + normalizar cabeçalhos.
- `page.tsx`: removido `card-legado` (2×); wrappers viraram `<article>` sem classe.
- Demais rotas: header interno padronizado em `secao-bloco` (+ `eyebrow`/`titulo`/`cabecalho`); planos em `grade-cartoes`; destaques/listas em `grade-noticias`; `admin/*` com topo `secao-bloco` (+ fix `&` → `&amp;`); `paginas/[slug]`: `pagina-editorial` (inexistente) → `article.secao-bloco`; `jornalista/status`: h2 inline → `cartao-titulo`.
- Sem alteração (já conformes): `login`, `cadastro`, `recuperar-senha`, `redefinir-senha/*`, `verificar-email/*`, `onboarding`, `jornalista/solicitar`, `comunidade/nova`, `noticia/item/[id]`, `noticia/cluster/[id]`.
- Nenhuma classe CSS nova pedida pelas páginas (`css-needs-pages.md` = zero).

### 1.4 Responsive/a11y (apêndice ao `globals.css`, sem JS)
- Reparado truncamento intermediário do CSS (arquivo terminava na linha 575 com marcador literal `...[truncated 20887 chars]`); apêndice ao final (cascata vence; nenhum token `:root` redefinido, só `:root` aditivo com `--bp-*`, `--container-max`, `--altura-header`, `--largura-sidebar`). Verificação final: sem palavra `truncated`, chaves balanceadas (271/271), termina com `@media print` fechado.
- Sistema `.botao` recriado (perdido no truncamento): variantes `--primaria/--secundaria/--fantasma/--perigo`, tamanhos `--pequeno` (min 40px) / `--medio` (44px) / `--grande` (52px); `.botao-salvar` min 40px.
- A11y CSS: `:focus-visible` global + `box-shadow var(--anel-foco)` preservados; **novo** bloco `prefers-reduced-motion: reduce` (zera animation/transition, `scroll-behavior:auto`, cobre `*`/`::before`/`::after`); bloco `@print` (esconde header/rodape/ads/banner/share/drawer/palette, links http com URL); skip-link `.pular-para-conteudo` preservado; alvos ≥40px (`button`, `a.botao`, inputs, nav pills, links/social do rodapé, `.link-nulo`, banner).
- Estruturais recriados (usados por `page.tsx`): `.controles-feed`, `.link-nulo`, `.faixa-publicidade`, `.banner-atualizacao`, `.newsletter-box`, `.bloco-sidebar(+cabecalho/titulo)`, `.sugestao-adaptativa(acoes)`, `.sentinela-carregamento`, `.drawer-fundo/.drawer` (bottom-sheet mobile → lateral `≥480px)`, `.lista-compacta`, `.tabela-wrapper` (`overflow-x:auto`, `max-width:100%`) + `.tabela` base.
- Remediações finais (reviewer `approve_with_comments`, 4 minor + 2 nit — só estes corrigidos): (1) definidos `.limitar-linhas-2/3` (`-webkit-line-clamp` + `line-clamp` padrão); (2) `.share-sticky` com fallback em cascata (`var(--cor-fundo-card)` → `var(--vidro)` → `color-mix(...)`), removidos `background`/`backdropFilter` inline que sobrescreviam a cascata; (3) `Header`: foco no campo ao abrir busca + `Escape` fecha nav mobile; (4) `Rodape`: `target="_blank"` condicional p/ externos. Nit `Button {...resto}` documentado como pré-existente, não alterado.

## 2. Breakpoints (mobile-first, só `min-width`)

Base = 360px sem media query. Tokens aditivos: `--bp-sm: 480px`, `--bp-md: 768px`, `--bp-lg: 1024px`, `--bp-xl: 1280px`, `--container-max: 1200px`, `--altura-header: 64px` (sticky offset real `132px` no portal), `--largura-sidebar: 320px`.

| Breakpoint | O que muda (arquivo final, 15 `@media`) |
|---|---|
| base (0–479) | 1 coluna; hamburger visível; nav colapsada (`display:none` até `.aberto`); `busca-atalho` oculta; `.mosaico` 1 col; `.rodape-grid` 1 col; `.drawer` bottom-sheet; tabelas com scroll |
| `≥480px` (linhas 677, 693, 775) | container `100% - 3rem`; `busca-atalho` vira `inline-flex`; botões full-width liberados p/ inline; drawer vira lateral |
| `≥768px` (linhas 710, 746) | `.grade-noticias` por construção 2 col; `secao-titulo` sobe; newsletter lado a lado; `.rodape-grid` 2 col |
| `≥1024px` (linhas 696, 714, 723, 749) | `portal-layout` 2 col `minmax(0,1fr) 320px` + sidebar sticky; header nav completa, hamburger `display:none`; `.mosaico` 2 col; `.rodape-grid` 4 col (`1.4fr 1fr 1fr 1fr`); `.grade-noticias` 3 col conforme largura |
| `≥1280px` (linha 727) | container trava 1200px centralizado; hero padding cheio; grade 3 col estáveis |
| `prefers-reduced-motion: reduce` (780) | `animation:none`, `transition:none`, `scroll-behavior:auto` |
| `print` (784) | esconde `.cabecalho/.topo/.rodape/.base/.faixa-publicidade/.banner-atualizacao/.sugestao-adaptativa/.share-sticky/.drawer*/.palette-fundo`; texto preto/branco; links http com URL |
| `prefers-color-scheme: dark` (125) + `hover: hover` (442, 539) | fallback dark sem `data-theme="light"`; hover `translateY(-2/-3px)` + sombra só com mouse |

Proibido (contrato, respeitado): `@media (max-width)` novo, `width: 100vw` em regra real, breakpoints fora da lista (720/900/960 legados → 768/1024).

## 3. Classes novas / aliases legados

### 3.1 Novas (todas em `globals.css`, linhas ~649–666)
| Classe | Uso | Fallback se remover |
|---|---|---|
| `.busca--pill .busca__campo` | `SearchBar` em pílula (`class="busca busca--pill"`) — `border-radius: var(--raio-completo)` | `style borderRadius` inline no TSX |
| `.share-sticky` | faixa de compartilhar no detalhe — `position: sticky; top: 72px; z-index: var(--z-banner)` + fundo em cascata com blur | props inline `position/top/zIndex/padding/margin` mantidas no TSX |
| `.detalhe-dropcap::first-letter` | capitular editorial no 1º parágrafo — **única sem fallback inline possível** | sem fallback; depende do CSS |
| `.limitar-linhas-2` / `.limitar-linhas-3` | clamp 2/3 linhas (`-webkit-box` + `-webkit-line-clamp` + `line-clamp` padrão) — usadas por `Cards`/`BlocoEditoria` | cai no clamp base 3 linhas (desalinha grade) |
| Sistema `.botao` recriado + `.botao-salvar` (min 40px) | permite remover `style={{ minHeight: 40 }}` inline em Data/Drawer/ShareButtons/BotaoSalvar | inline ainda presente, inofensivo |

### 3.2 Aliases legados preservados (não quebrar consumidores de outras runs)
Canônicos novos: `.cabecalho*` (Header), `.rodape*` (Rodapé). Aliases mantidos no CSS: `.topo*`/`.base*` (ex.: `ui/Cards`, `CommandPalette`), `.cartao*` (`cartao`, `cartao-titulo/meta`, `cartao-noticia*`), `.grade-noticias`, `.grade-cartoes`, `.editoria-grade`, `.portal-layout`, `.sidebar`, `.bloco-sidebar*`, `.secao-*`, `.hero*`, `.seu-rio*`, `.container`, `.botao*`, `.badge`, `.chip`, `.toast`, `.modal`, `.dropdown`, `.tooltip`, `.tabs`, `.accordion`, `.esqueleto`, `.banner-cookies`, `.banner-atualizacao`, `.tabela-wrapper` (+ `.tabela`, `.paginacao`), `.campo*`, `.busca*`, `.drawer*`, `.estado-*`, `.faixa-publicidade`, `.sugestao-adaptativa`, `.newsletter-box`, `.link-nulo`, `.texto-suave`, `.pular-para-conteudo`, `.plano-*`, `.kpi`, `.admin-*`, `.palette*`, `.explicacao-ia*`.
Removidas (não recriar): `card-legado` (page.tsx), `pagina-editorial` (paginas/[slug]), `botao--carregando`, `cartao-noticia--esqueleto`. `100vw` real: zero.

## 4. Como testar em DEV (4 viewports + dark mode)

Pré-requisitos: backend em `http://localhost:8000` + frontend em `http://localhost:3000` (ver `README.md` "Como rodar o backend/frontend"). Nenhum `backend/.env` novo exigido; feed pode usar dados reais via `manage.py ingerir_noticias` ou fallback local.

```powershell
cd backend; .\.venv\Scripts\activate; python manage.py runserver   # :8000
cd frontend; npm run dev                                            # :3000
```

### 4.1 Viewports (DevTools → Dimensions, ou janelas reais)
| Viewport | Onde olhar | Esperado |
|---|---|---|
| 360×800 | `/`, `/noticia/item/[id]` ou `/noticia/cluster/[id]`, `/login` | sem scroll horizontal (`scrollWidth <= innerWidth`); hamburger abre/fecha com `aria-expanded=true/false`; busca colapsável vira linha full-width; grade 1 col; rodapé 1 col; tabelas com scroll interno (`.tabela-wrapper`); drawer como bottom-sheet |
| 768×1024 | `/` | grade 2 col; sidebar empilha (estática, sem sobreposição); rodapé 2 col; `secao-titulo` maior; newsletter lado a lado |
| 1024×768 | `/` | `portal-layout` 2 col (conteúdo + sidebar 320px sticky); header nav completa, hamburger some; grade 2→3 col; rodapé 4 col; `.mosaico` 2 col |
| 1440×900 | `/` | grade 3 col estáveis; container centralizado max 1200px; hero padding cheio |

Cheque rápido no console (qualquer viewport):
```js
document.documentElement.scrollWidth <= window.innerWidth // true esperado
document.querySelector('[aria-expanded]') // hamburger + busca têm o atributo
getComputedStyle(document.querySelector('.portal-layout')).gridTemplateColumns
```

### 4.2 Dark mode
1. Header → `ThemeToggle`: alternar claro/escuro; recarregar — tema persiste sem flash (script anti-flash em `layout.tsx`).
2. Alternativa manual: DevTools → `document.documentElement.dataset.theme = "dark"` (ou `"light"`); sem atributo, vale `prefers-color-scheme` do SO.
3. Esperado: todos os textos usam `var(--cor-texto/suave)`, links `var(--cor-primaria)` (`#818cf8` no dark); contraste principal ≥ 4.5:1 nos dois temas (tokens do `design-spec.md` §2; medição instrumental em browser real ficou como ressalva no `test-report.md` — não bloqueante, build verde).
4. Rodapé deve ficar `rodape--dark` elegante nos dois temas.

### 4.3 Teclado / motion / print (bônus, critérios 6 e 8)
- Só teclado: `Tab` até hamburger/busca → `Enter` abre, `Escape` fecha; foco sempre visível (`:focus-visible` + anel); skip-link "Pular para o conteúdo" leva a `main#conteudo-principal`.
- `prefers-reduced-motion`: DevTools → Rendering → Emulate → `reduce` → shimmer/hover/transições desligam.
- Print (`Ctrl+P` numa notícia): header/rodape/ads/share/drawer somem; texto preto/branco; links http mostram URL.

### 4.4 Veredito herdado (não re-executar sem motivo)
`test-report.md`: PASSED (tsc exit 0, build exit 0 ×2, 15 `@media`, `truncated`=0, `100vw` só comentário, `card-legado/pagina-editorial`=0, `backend/`+`api.ts` diff vazio). Ressalva: runtime em browser real (contagem de colunas, contraste medido, tab-order) não executado no harness — coberto acima pelo roteiro manual.
`code-review-contract.md`: `approve_with_comments` (0 blocker, 0 major, 4 minor, 2 nit) — todos os minor + nit externo corrigidos pelo remediator-final; nit `Button {...resto}` pré-existente mantido por decisão.

## 5. Docs tocados nesta tarefa
- ESTE arquivo (novo).
- `README.md`: seção "Design system" — nota mínima do rebuild v2 (breakpoints, classes novas, aliases). Sem reescrever docs.
- `ARCHITECTURE.md`: não tocado (sem seção frontend desatualizada — só stack/módulos/infra).
