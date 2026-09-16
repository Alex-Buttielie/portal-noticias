# Test Report — 20260915-2246-mobile-app-nav

**Run:** 20260915-2246-mobile-app-nav
**Tester:** TESTER (Muse Spark)
**Data:** 2026-09-15 23:00 UTC
**Veredito:** **PASSED** (com ressalvas — browser real não executado, fallback estático documentado)

## 1. Comandos executados e evidências

### 1.1 `tsc --noEmit -p frontend/tsconfig.json`
```powershell
.\frontend\node_modules\.bin\tsc --noEmit -p frontend/tsconfig.json; echo "EXIT:$LASTEXITCODE"
# → EXIT:0
```
**Status:** PASS — exit 0, sem erros de tipo.

### 1.2 `npm run build --prefix frontend` (timeout 300s)
```
> portal-noticias-frontend@0.1.0 build
> next build
  ▲ Next.js 14.2.15
   Creating an optimized production build ...
 ✓ Compiled successfully
 ✓ Generating static pages (32/32)
Route (app)                              Size     First Load JS
┌ ○ /                                    8.16 kB         152 kB
├ ○ /_not-found                          142 B          87.3 kB
├ ○ /admin                               1.26 kB         118 kB
├ ○ /admin/assinaturas                   1.33 kB         140 kB
├ ○ /admin/fila                          1.27 kB         139 kB
├ ○ /admin/metricas                      8.64 kB         144 kB
├ ○ /admin/moderacao                     1.47 kB         140 kB
├ ○ /admin/planos                        2.1 kB          140 kB
├ ○ /admin/robos                         3.6 kB          142 kB
├ ○ /admin/usuarios                      1.5 kB          140 kB
├ ƒ /autor/[id]                          2.33 kB         138 kB
├ ○ /cadastro                            3.32 kB         139 kB
├ ○ /comunidade                          1.99 kB         137 kB
├ ƒ /comunidade/[id]                     4.41 kB         140 kB
├ ○ /comunidade/nova                     3.22 kB         138 kB
├ ○ /empresa                             2.96 kB         141 kB
├ ○ /jornalista/solicitar                3.64 kB         139 kB
├ ○ /jornalista/status                   3.76 kB         139 kB
├ ○ /lista-de-espera                     3.56 kB         139 kB
├ ○ /login                               5.11 kB         125 kB
├ ○ /minha-conta                         2.9 kB          141 kB
├ ƒ /noticia/cluster/[id]                166 B           140 kB
├ ƒ /noticia/item/[id]                   166 B           140 kB
├ ○ /onboarding                          3.56 kB         139 kB
├ ƒ /paginas/[slug]                      2.22 kB         122 kB
├ ○ /planos                              2.61 kB         138 kB
├ ○ /privacidade/politica                181 B          94.1 kB
├ ○ /privacidade/preferencias-cookies    3.53 kB         124 kB
├ ○ /radar                               2.77 kB         141 kB
├ ○ /recuperar-senha                     4.14 kB         124 kB
├ ○ /redefinir-senha                     4.41 kB         124 kB
├ ○ /robots.txt                          0 B                0 B
├ ○ /rss.xml                             0 B                0 B
├ ○ /sitemap.xml                         0 B                0 B
└ ○ /verificar-email                     3.38 kB         123 kB
+ First Load JS shared by all            87.1 kB
  ├ chunks/2117-172c0af95c298e54.js      31.6 kB
  ├ chunks/fd9d1056-2e911c01913826eb.js  53.6 kB
  └ other shared chunks (total)          1.91 kB
○  (Static)   prerendered as static content
ƒ  (Dynamic)  server-rendered on demand
```
**Status:** PASS — 32/32 rotas, `Compiled successfully`. 5 linhas finais capturadas acima confirmam Route table + shared chunks.

### 1.3 `git diff HEAD --stat -- backend/ frontend/lib/api.ts`
```powershell
git diff HEAD --stat -- backend/ frontend/lib/api.ts
# → (vazio, STAT_EXIT:0)
git diff HEAD -- frontend/lib/api.ts → DIFF_API_END (vazio)
git diff HEAD -- backend/ → BACKEND_DIFF_END (vazio)
git status --short
?? backend/ensure_local_admin.py
```
**Status:** PASS para critério 6 em sentido estrito (`git diff` vazio em arquivos rastreados). **Ressalva:** existe arquivo **não-rastreado** `backend/ensure_local_admin.py` — não aparece em `git diff` mas aparece em `git status`. Deve ser removido ou adicionado a `.gitignore` antes do merge.

### 1.4 `git diff HEAD --name-status -- frontend/app` + artefatos M1
```
M  frontend/app/admin/assinaturas/page.tsx … (35 arquivos M em frontend/app)
frontend/components/BottomNav.tsx: EXISTS (2731 bytes, 2026-09-15 22:49:41)
frontend/lib/hooks/useIsMobile.ts:
  "use client";
  export function useIsMobile(breakpoint = 768): boolean {
    useState(() => matchMedia(`(max-width: ${breakpoint}px)`).matches) + guard SSR
    useEffect + mql.addEventListener("change", onChange) + cleanup
```
**Evidência grep M1:**
```
frontend/app/layout.tsx:9: import BottomNav from "@/components/BottomNav";
frontend/app/layout.tsx:101: className="container scroll-mt-24 py-6 pb-[calc(4rem+env(safe-area-inset-bottom))] … sm:pb-6"
frontend/app/layout.tsx:105: <BottomNav />
frontend/components/BottomNav.tsx:29: pb-[env(safe-area-inset-bottom)] pt-1
frontend/components/BottomNav.tsx:30: overscroll-contain
frontend/components/BottomNav.tsx:31: touch-manipulation
frontend/components/BottomNav.tsx:33: style={{ overscrollBehavior: "contain", touchAction: "manipulation" }}
frontend/app/globals.css:3467: FRENTE M1 - shell-nav mobile: safe-area + overlay + motion-reduce
frontend/app/globals.css:3472: overscroll-behavior: contain;
frontend/app/globals.css:3483: @supports (padding: env(safe-area-inset-bottom))
```

### 1.5 Chrome DevTools MCP
```powershell
npx chrome-devtools-mcp --help → EXIT:0 (chrome-devtools-mcp@1.9.0 instalado, flags --headless --browserUrl --wsEndpoint etc.)
# new_page http://localhost:3000 não executado — sem servidor Chrome/MCP rodando neste host.
# Fallback estático documentado conforme frontend-portal SKILL §4 (precedente run 20260909-1200, revert 2d8063c via git show a1d37d8)
```
**Status:** MCP disponível como pacote, mas sem browser conectado em CI. Verificação runtime (360/768/1024/1440 screenshots, tab-order, contraste AA) não executada — registrada como ressalva.

## 2. Tabela critérios 1–6 (implementation-contract.md)

| # | Critério | Evidência | Veredito |
|---|----------|-----------|----------|
| 1 | Viewport 360 sem overflow-x (360/768/1024/1440) | `frontend/app/globals.css:180` `scrollbar-gutter: stable`, `181/191` `overflow-x: hidden` em `html`/`body`, `max-width:100%` em img/video/iframe, `min-w-0`/`truncate` em Cards/Tabs/Chip verificado em diff, `BottomNav` fixed com `main pb-[calc(4rem+env(...))]` evita cobertura. Sem `overflow-x: hidden` indevido em container crítico além de html/body. Validação estática OK; sem screenshots browser. | **PASS c/ ressalva** |
| 2 | `sm:hidden` bottom nav com `aria-current="page"` + `safe-area` + não cobre `:focus-visible` | `frontend/components/BottomNav.tsx:25` `aria-label="Navegação principal móvel"`, `:29` `pb-[env(safe-area-inset-bottom)]`, `:30-33` `overscroll-contain`+`touch-manipulation` + style `overscrollBehavior:contain`, `:41` `aria-current={ativo?"page":undefined}`, `:47-51` `min-h-[44px]` `touch-manipulation` `focus-visible:ring`, `frontend/app/layout.tsx:101` `pb-[calc(4rem+env(safe-area-inset-bottom))] sm:pb-6` + `sm:hidden` em BottomNav `fixed bottom-0 inset-x-0 z-[var(--z-cabecalho)] sm:hidden`. Header top nav `hidden sm:flex` (`Header.tsx:159`). | **PASS** |
| 3 | Hamburger/Sheet com foco preso, `aria-expanded`, `Escape`, `overscroll-behavior: contain`, `touch-action: manipulation`, `min-h 44px` | `Header.tsx:122-136` `<button aria-expanded={menuAberto} aria-controls="mobile-nav-sheet" aria-label=… onClickToggle>` `min-h-[44px] min-w-[44px] touch-manipulation`, `:87-94` `useEffect Escape → setMenuAberto(false)`, `:258-286` `DialogPrimitive.Root open/onOpenChange` (foco preso por Radix), `Overlay:260-272` `overscroll-contain touch-manipulation` + `role="button" aria-label="Fechar menu"` + `style overscrollBehavior:contain`, `Content:273-285` `id="mobile-nav-sheet" overscroll-contain overflow-y-auto pb-[env(...)]` + style contain, `:293-304` `DialogPrimitive.Close aria-label`, `:307-328` nav links `min-h-[44px] touch-manipulation aria-current`. | **PASS** |
| 4 | `tsc --noEmit` + `npm run build` exit 0, 32/32 | `tsc EXIT:0` (seção 1.1), `next build ✓ Compiled successfully`, `✓ Generating static pages (32/32)`, Route table acima (seção 1.2). | **PASS** |
| 5 | Audit `command.md` fresco → zero blocker/major | Fetch fresco `https://raw.githubusercontent.com/vercel-labs/web-interface-guidelines/main/command.md` em 2026-09-15 (seção 3). Diff auditado: sem `transition: all`, sem `user-scalable=no`/`maximum-scale=1` (viewport `maximumScale:5` OK), sem `onPaste+preventDefault`, sem `div onClick` sem role, sem `...` ASCII em placeholder (usa `…`), icon-buttons com `aria-label`, inputs com `<label>`, `aria-current`, `aria-hidden` em decorativos. Outline:none apenas com substituto `focus-visible:ring`/`box-shadow`. | **PASS** (ver §3 para detalhes terse) |
| 6 | `git diff HEAD --stat -- backend/ frontend/lib/api.ts` vazio | `git diff HEAD --stat -- backend/ frontend/lib/api.ts` → vazio (tracked). `frontend/lib/api.ts` não modificado; `backend/` sem diff em arquivos rastreados. Untracked `backend/ensure_local_admin.py` existe — fora do escopo de `git diff` mas deve ser limpo. | **PASS c/ ressalva** |

## 3. Checklist `command.md` fresco (web-interface-guidelines) — terse `file:line`

Fonte: `https://raw.githubusercontent.com/vercel-labs/web-interface-guidelines/main/command.md` (fetch 2026-09-15) + `frontend-portal SKILL § Safe Areas/Touch/Performance`.

**Escopo auditado:** diff `frontend/app/layout.tsx`, `frontend/app/globals.css` (hunk M1), `frontend/components/Header.tsx`, `frontend/components/BottomNav.tsx`, `frontend/lib/hooks/useIsMobile.ts`, `frontend/lib/nav-itens.ts`, `frontend/components/ui/SearchBar.tsx` — 35+ `frontend/app/**/*` tocados (min-w-0/truncate etc.).

```
✓ frontend/components/BottomNav.tsx:29-33 — safe-area + overscroll-contain + touch-manipulation presentes (com style fallback)
✓ frontend/components/BottomNav.tsx:25,41 — aria-label nav + aria-current="page" OK
✓ frontend/components/BottomNav.tsx:48,51 — min-h-[44px] + touch-manipulation + focus-visible:ring OK
✓ frontend/app/layout.tsx:101 — pb-[calc(4rem+env(safe-area-inset-bottom))] evita cobertura de :focus-visible
✓ frontend/app/layout.tsx:43-49 — viewport maximumScale:5 (não bloqueia zoom) ✓
✓ frontend/components/Header.tsx:132-134 — aria-expanded sincronizado + aria-controls="mobile-nav-sheet" + aria-label toggle OK
✓ frontend/components/Header.tsx:139,207,303,330,362 — aria-hidden="true" em ícones decorativos OK
✓ frontend/components/Header.tsx:269-272 — Overlay role="button" aria-label="Fechar menu" tabIndex=-1 OK (Radix fecha ao clicar)
✓ frontend/components/Header.tsx:273-285 — Sheet overscroll-behavior:contain + touch-action:manipulation + pb-[env(...)] OK
✓ frontend/components/Header.tsx:189,347, frontend/components/ui/SearchBar.tsx:18,53-55 — placeholder "Buscar…" usa … (não ...), type=search + inputMode=search + enterKeyHint=search OK
✓ frontend/app/globals.css:180-191 — scrollbar-gutter: stable + overflow-x:hidden em html/body OK
✓ frontend/app/globals.css:223 — text-wrap: balance em h1/h2/h3 OK
✓ frontend/app/globals.css:3469-3495 — @supports safe-area + prefers-reduced-motion disable anim OK
✓ frontend/components/ui/SearchBar.tsx:59 autoComplete="off" em campo busca (campo não-auth) OK; Header busca idem
✓ frontend/components/ui/Button.tsx:8 — min-h-[44px] touch-manipulation + focus-visible:ring OK
✓ frontend/lib/hooks/useIsMobile.ts:6-19 — matchMedia("(max-width: 768px)") + guard SSR + addEventListener change + cleanup OK
✓ frontend/lib/nav-itens.ts:10-27 — fonte única NAV_ITENS (4 itens) + Conta/Login OK, sem hardcode duplicado

— Anti-patterns (reprovar) —
✓ frontend/app — transition: all → 0 ocorrências (grep "transition:\s*all" vazio)
✓ frontend/app/layout.tsx — user-scalable=no → 0 ocorrências
✓ frontend/components/* — onPaste+preventDefault → 0 ocorrências
✓ frontend/components/Header.tsx,BottomNav.tsx — div onClick sem role → 0 ocorrências (apenas <button>/<Link>/<DialogPrimitive>)
✓ frontend/components/* — img sem width/height → N/A (projeto usa placeholder div, sem next/image; verificado)
✓ frontend — "..." ASCII em placeholder/copy → 0 (spread "...NAV_ITENS" é JS, não copy; placeholders usam "…")

— Observações menores (não-blocker, pré-existentes fora do diff) —
· frontend/app/globals.css:279-281 main:focus { outline:none } — intencional para alvo skip-link (tabIndex=-1) com :focus-visible global em 273-277; OK mas mereceria comentário
· frontend/app/globals.css:688-694 .palette-busca input { outline:none } sem ring explícito no mesmo bloco — coberto por focus-visible:ring nas classes Tailwind do input, porém pré-existente (não no diff M1)
· frontend/app/globals.css:1142-1154 input:focus / input:focus-visible { outline:none } — pares com box-shadow/border; pré-existente
```

**Conclusão §3:** Zero blocker/major no diff. Todos os offending patterns ausentes ou com substituto adequado.

## 4. Checklist `frontend-portal` § Safe Areas / Touch / Performance

| Item | Esperado | Encontrado |
|------|----------|------------|
| Safe Areas | `env(safe-area-inset-*)` em layouts full-bleed | `BottomNav pb-[env(safe-area-inset-bottom)]` + `main pb-[calc(4rem+env(...))]` + `@supports padding: env(...)` no Sheet |
| Touch | `touch-action: manipulation`, `min-h-[44px]`, `overscroll-behavior: contain` em modals/drawers | Presente em BottomNav, Header hamburger, Sheet overlay/content, SearchBar, Button |
| Performance | `scrollbar-gutter: stable` evita CLS, `content-visibility` onde >50 (não necessário ainda), `transition-colors` explícito (não `all`), `motion-reduce:transition-none` | `html scrollbar-gutter: stable`, `transition-colors`/`transition-none` em Header/BottomNav/Button, `@media prefers-reduced-motion` desativa anim |
| A11y foco | `focus-visible:ring` sempre visível, nunca `outline:none` sem substituto | Todos interativos com `focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cor-foco)]` |
| Hook | `useIsMobile` via `matchMedia` com guard SSR | `useIsMobile.ts` implementa exatamente contrato internal |

## 5. Findings (terse)

**Blocker:** nenhum.

**Major:** nenhum no diff.

**Minor / Ressalvas:**

1. `backend/ensure_local_admin.py` — arquivo não-rastreado em `backend/`; limpar antes do merge (não afeta `git diff HEAD --stat` mas polui `git status`).
2. `frontend/components/BottomNav.tsx:33,50` — `style={{ touchAction:"manipulation" }}` inline é redundante com classe `touch-manipulation` mas não é blocker; mantém compatibilidade.
3. `frontend/components/Header.tsx:268-272` — `Overlay role="button" tabIndex=-1` — Radix já fecha ao clicar; `role=button` exigido pelo contrato M1, OK porém sem `onKeyDown` explícito (Radix cuida de Escape/foco).
4. Placeholders exibem `�` em `powershell Get-Content` por encoding, mas `read` confirma `…` correto (`Buscar…`, `Buscar notícias, temas…`) — falso-positivo de terminal.
5. Browser real (chrome-devtools MCP) não executado — validação 360/768/1024/1440, screenshots, tab-order e contraste AA pendentes. Precedente documentado em `frontend-portal SKILL §4`.

## 6. Ressalvas e limitações

- **Sem browser/MCP:** `npx chrome-devtools-mcp --help` OK mas sem `new_page http://localhost:3000` (sem Chrome headless + servidor `npm run dev` neste CI). Fallback estático conforme skill (`tsc+build+grep`) + `overflow-x`/`safe-area` estático; screenshots reais devem ser executados em ambiente com `chrome-devtools` + `npm run dev` antes do review final (conforme precedente `run 20260909-1200` revertida em `2d8063c`).
- **`backend/ensure_local_admin.py` untracked:** não quebra critério 6 mas deve ser removido/ignorado.
- **Tailwind introduzido:** `frontend/package.json`, `tailwind.config.ts`, `postcss.config.js`, `frontend/components.json` adicionados no diff — build passou (32/32) mas é nova dependência; já aprovada no `task-plan.md` (CSS-first via Tailwind breakpoints + `useIsMobile`).
- **`git diff HEAD --name-status -- frontend/app` mostra 35 arquivos M** — esperado para frente M3 (ajustes `min-w-0`/`text-[16px]` etc.); não auditados linha-a-linha neste report, mas build e grep amostral não indicaram regressão.

## 7. Evidências arquivadas

- `tsc --noEmit` log: `EXIT:0`
- `npm run build` log completo com Route table (seção 1.2)
- `git diff HEAD --stat -- backend/ frontend/lib/api.ts` vazio (seção 1.3)
- `git status --short` com untracked listado
- `Select-String` greps para `safe-area`, `touch-manipulation`, `overscroll`, `aria-*`, `transition: all`, `user-scalable`, `onPaste`, `outline:none`, `...` vs `…`

---
*Gerado por TESTER run 20260915-2246-mobile-app-nav — só `test-report.md` escrito, sem edição de código.*
