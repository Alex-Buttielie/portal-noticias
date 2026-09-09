# Test Report — 20260909-1200-frontend-rebuild (frontend-qa-retest, somente leitura)

- **Data (UTC):** 2026-09-09
- **Contrato:** `agentic-framework/state/run-20260909-1200-frontend-rebuild/implementation-contract.md` v1 (8 critérios)
- **Escopo do retest:** revalidação independente do fix do remediator; somente leitura + comandos, sem correção de código.
- **Afirmação do remediator:** tsc exit 0, build exit 0, globals.css 777 linhas / 15 @media / keyframes entrada-suave adicionado.

## Veredito geral: PASSED (estático + build)

Build e tipos verdes; todos os greps conferem com o alegado. Critérios 1/2/6 passam em execução direta.
Critérios 3/4/5/7/8 passam em evidência estática (CSS/classes/attrs presentes + build verde destrava o bloqueio anterior);
runtime em browser real (medição scrollWidth, contagem de colunas, contraste medido, tab-order) não foi executado neste ambiente
(sem harness de browser) — registrado como ressalva, não como bloqueio.

## Comandos executados (exits capturados)

| Comando | CWD | Exit | Resumo da saída |
|---|---|---|---|
| `frontend\node_modules\.bin\tsc.cmd --noEmit -p frontend/tsconfig.json` | repo | **0** | Sem output de erro (`TSC_EXIT:0`). |
| `npm run build --prefix frontend` (= `next build`, 2 execuções) | repo | **0** (`BUILD_EXIT:0`, ambas) | Compila todas as rotas; sem `Failed to compile` / sem `PostCSSSyntaxError`. Últimas 15 linhas (2ª execução, idênticas à 1ª): bloco de rotas `/recuperar-senha … /verificar-email`, `First Load JS shared by all 87.1 kB`, legendas `○ (Static) / ƒ (Dynamic)`. |
| `git diff --stat HEAD -- backend/ frontend/lib/api.ts` | repo | **0** | Saída vazia — não-objetivos respeitados. `git status --short` lista só `M frontend/...` (ex.: `app/globals.css`, `app/page.tsx`, `app/admin/**`, `components/**`); nenhum `backend/`. |

## Greps estáticos (todos conferem)

| Padrão | Escopo | Resultado |
|---|---|---|
| `truncated` | `frontend/app/globals.css` | **0** — truncamento anterior (`...[truncated 20887 chars]` linha 574) eliminado. **OK** |
| `@media` count | `frontend/app/globals.css` | **15** (linhas 125, 442, 539, 666, 682, 685, 699, 703, 712, 716, 735, 738, 764, 769, 773). Inclui `min-width: 480/768/1024/1280`, `prefers-reduced-motion: reduce` (769), `print` (773), `prefers-color-scheme: dark` (125), `hover: hover` (442, 539). **OK** |
| `prefers-reduced-motion` | `frontend/app/globals.css` | **1** (linha 769: `@media (prefers-reduced-motion: reduce)`). Anteriormente 0. **OK (critério 6)** |
| `@keyframes entrada-suave` | `frontend/app/globals.css` | `@keyframes giro` (637) + `@keyframes entrada-suave` (638, `from opacity:0/translateY(8px)`); `entrada-suave` referenciada 4x total. Anteriormente referenciada sem definição. **OK** |
| `portal-layout` | `frontend/app/globals.css` | **4 ocorrências**. **OK** |
| `grade-noticias` | `frontend/app/globals.css` | **3 ocorrências**. **OK** |
| `tabela-wrapper` | `frontend/app/globals.css` | **1 ocorrência** (antes 0). **OK** |
| `busca--pill` | `frontend/` (`*.tsx,*.css`) | **4 ocorrências**. **OK** |
| `aria-expanded` em Header | `frontend/components/Header.tsx` | Linhas **71** (`aria-expanded={menuAberto}`) e **91** (`aria-expanded={buscaAberta}`). **OK** |
| `card-legado\|pagina-editorial` | `frontend/` | **0**. **OK** |
| `100vw` | `frontend/` | **1 match, só comentário** em `app/globals.css:6` ("NUNCA 100vw sem compensação"). Nenhum uso real. **OK** |
| `globals.css` linhas | `frontend/app/globals.css` | **777 linhas** — confere com o alegado. **OK** |

## Tabela dado/quando/então (8 critérios do contrato)

| # | Dado | Quando | Então | Veredito | Evidências |
|---|---|---|---|---|---|
| 1 | `npm run build` em `frontend/` | executado | exit 0 sem erro | **passed** | exit 0 em 2 execuções; sem erro de sintaxe; truncamento `truncated`=0; rotas compiladas + First Load JS 87.1 kB. |
| 2 | `npx tsc --noEmit` em `frontend/` | executado | exit 0 | **passed** | `tsc.cmd --noEmit -p tsconfig.json` exit 0, sem erros. |
| 3 | viewport 360px, home/notícia/login | renderizam | sem overflow-x; menu mobile com `aria-expanded` | **passed (estático; runtime browser não executado)** | `Header.tsx:71,91` aria-expanded menu+busca; CSS com breakpoints 480 (666,682,764); `100vw`=só comentário. Medição `scrollWidth<=innerWidth` real não executada (sem browser). |
| 4 | viewport 768px e 1024px, home | renderiza | grade 2 colunas, sidebar empilha | **passed (estático; runtime browser não executado)** | `@media min-width:768px` (699,735) + `min-width:1024px` (685,703,712,738) presentes (antes 0); `portal-layout` 4x; contagem visual de colunas em browser não executada. |
| 5 | viewport 1440px, home | renderiza | grade 3 colunas, container centraliza largura máxima | **passed (estático; runtime browser não executado)** | `@media min-width:1280px` (716) presente; `grade-noticias` 3x; container `min(1200px,…)` herdado do rebuild (relatório anterior). Contagem de colunas em browser não executada. |
| 6 | `prefers-reduced-motion` | animações existem | desativadas via media query | **passed** | `@media (prefers-reduced-motion: reduce)` linha 769 + `@keyframes entrada-suave` definido (638). Antes: 0 ocorrências. |
| 7 | tema dark (`data-theme="dark"`) | qualquer página | contraste ≥ 4.5:1, sem flash | **passed (estático; medição browser não executada)** | Sem regressão relatada; tokens dark/light e script anti-flash herdados do rebuild (relatório anterior: `:root[data-theme=dark]`, `layout.tsx` inline, `ThemeToggle`). Build verde destrava o `blocked` anterior. Medição real de contraste não executada. |
| 8 | navegação só por teclado | header/feed/form | foco visível + skip-link `#conteudo-principal` | **passed (estático; tab-order real não executado)** | Evidência estática herdada do rebuild (`:focus-visible`, `.pular-para-conteudo`, `main#conteudo-principal`); sem regressão (build verde). Percurso real por teclado não executado. |

## Integridade (não-objetivos)

- `backend/` + `frontend/lib/api.ts`: `git diff --stat HEAD -- backend/ frontend/lib/api.ts` **vazio**. **passed**
- `100vw` sem compensação: só comentário. **passed**
- Classes legadas `card-legado`/`pagina-editorial`: 0. **passed**

## Ressalvas (não-bloqueantes)

- Runtime em browser (360/768/1024/1440, contraste medido, tab-order) não executado neste ambiente; vereditos 3/4/5/7/8 apoiam-se em evidência estática + build verde.
- `npm run lint` (= `next lint`) não revalidado neste retest (fora do escopo pedido); relatório anterior apontava ausência de config ESLint (pré-existente).
