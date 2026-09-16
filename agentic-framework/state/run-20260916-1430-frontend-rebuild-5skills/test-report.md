# Test Report — 20260916-1430-frontend-rebuild-5skills

- **run:** 20260916-1430-frontend-rebuild-5skills
- **data:** 2026-09-16
- **papel:** tester (somente leitura + este relatório; nenhum fonte editado)
- **refs:** `agentic-framework/state/run-20260916-1430-frontend-rebuild-5skills/implementation-contract.md` (critérios 1–6), `.claude/skills/frontend-portal/SKILL.md` §3–§4, `command.md` fresco transcrito no brief (vercel-labs/web-interface-guidelines, 2026-09-16)
- **veredito global:** PASSED-c-ressalvas

## §1 — Comandos + evidências

| comando | resultado |
|---|---|
| `tsc --noEmit -p frontend/tsconfig.json` | EXIT 0 (evidência apurada pela run) |
| `npm run build --prefix frontend` | Compiled successfully, 32/32 rotas, shared 87.1kB, BUILD_EXIT 0; dois `[TypeError: fetch failed] ECONNREFUSED` em prerender de `generateStaticParams` — backend offline no CI, pré-existente, não quebra o build (evidência apurada pela run) |
| `git diff HEAD --stat -- backend/ frontend/lib/api.ts` | vazio — confirmado nesta auditoria (saída `---DIFF-BACKEND-API---` / `---END---` sem linhas) |
| `git diff HEAD --stat` (auditoria) | 56 arquivos changed, 5880+/3351-; só `frontend/` + `.gitignore`; nenhum `backend/` |
| `git status --short` (auditoria) | modificados = `frontend/**` + `.gitignore`; novos untracked = `frontend/components/ui/*` (shadcn port), `frontend/components/Hero|HomeHero|HomeSidebar.tsx`, `frontend/lib/hooks/use-toast.ts`, `frontend/components/ui/pricing-table|sparkline|carousel|command|data-table.tsx` (21st); deletado = `frontend/components/ui/Drawer.tsx` (substituído por `sheet.tsx` vaul/shadcn) |
| correção pós-build `frontend/components/ui/button.tsx` | verificada em leitura: bloco `asChild` (L94–105) repassa só `children` ao Radix `Slot` + `aria-busy`, spinner condicional só no path `<button>` (L114–136) — elimina "Slot failed to slot onto its children" em `/` e `/_not-found` |

## §2 — Critérios 1–6 do implementation-contract

| # | critério | veredito | evidência |
|---|---|---|---|
| 1 | `tsc --noEmit` exit 0 | PASS | evidência da run (EXIT 0); código auditado sem novos erros de tipo visíveis |
| 2 | `npm run build` exit 0, 32/32 rotas | PASS | evidência da run (32/32, shared 87.1kB); ECONNREFUSED é backend-offline pré-existente, não regressão do diff |
| 3 | diff `backend/` + `frontend/lib/api.ts` vazio | PASS | `git diff HEAD --stat -- backend/ frontend/lib/api.ts` → vazio (reconfirmado §1) |
| 4 | `command.md` fresco → 0 blocker/major | PASS | §3: só 2 findings minor (M1, M2) + 1 nota browser (N1); nenhum anti-pattern bloqueante |
| 5 | chrome-devtools (ou fallback documentado) | PASS-c-ressalva | sem MCP neste ambiente → fallback estático executado (§3 + greps); browser real pendente (§4) |
| 6 | 5 skills runtime evidenciadas | PASS | shadcn: `frontend/components/ui/{button,card,dialog,form,input,tabs,accordion,skeleton,…}.tsx` (untracked, tokens `var(--cor-*)`); 21st: `ui/pricing-table.tsx`, `ui/carousel.tsx`, `ui/command.tsx`, `ui/sparkline.tsx`; frontend-design 2-pass: `agentic-framework/state/run-20260916-1430-frontend-rebuild-5skills/design-spec.md`; command.md: transcrito no brief; chrome-devtools: workflow substituído por fallback (§4) |

## §3 — Checklist command.md (terse, `arquivo:linha`)

- ✓ icon-only c/ `aria-label`: `components/ThemeToggle.tsx:23,37` · `components/Header.tsx:109` (hamburger `topo__menu` c/ aria) · `components/ui/carousel.tsx:139,181`
- ✓ labels: `components/ui/FormField.tsx:91` (`<Label htmlFor>`) · `app/login/page.tsx:77-100` · `app/cadastro/page.tsx:128,140,153` · `app/radar/page.tsx:127-136` · `components/Header.tsx:165,287` (sr-only) · `components/ui/data-table.tsx:122,139,248` (sr-only)
- ✓ button-ação / Link-navegação, zero `div onClick`: grep `div[^>]*onClick|<div[^>]*onKey|onClick.*router.push` → 0 matches; destrutivas via `window.confirm`: `app/comunidade/[id]/page.tsx:125,136` · `app/planos/page.tsx:61` · `app/radar/page.tsx:86` · `app/admin/robos/page.tsx:130`
- ✓ img alt+dimensão: `components/Hero.tsx:38-45` (`alt=""` decorativa, `width={1200} height={630}`, `priority` acima da dobra) · `components/ui/Cards.tsx:102-109,142-149` (`alt=""` + `aria-hidden`, width/height explícitos)
- ✓ decorativos `aria-hidden`: `components/CartaoEsqueleto.tsx:10,25,36` · `components/ThemeToggle.tsx:25-26,39-47` · `components/DetalheNoticia.tsx:115,122,135,149-157`
- ✓ `aria-live="polite"`: `components/CartaoEsqueleto.tsx:53` · `app/comunidade/page.tsx:193` (+`aria-busy`) · `app/radar/page.tsx:148,295` · `app/planos/page.tsx:90` · `app/login` erro via `Alert` + foco 1º erro `app/login/page.tsx:45`
- ✓ headings + skip link: `components/PularParaConteudo.tsx:7-12` (`href="#conteudo-principal"`, `focus:not-sr-only`, ring) · `app/layout.tsx:101` (`scroll-mt-24`, `main#conteudo-principal` preservado)
- ✓ foco visível sempre: `focus-visible:ring-2 ring-[var(--cor-foco)]` ubíquo (`ui/button.tsx:9`, `Header.tsx:126,149,201,227,271,352,367`, `DetalheNoticia.tsx:112,118,200,225,242`); `outline:none` só com substituto (`app/globals.css:2988,3079,3112,3231` → `box-shadow: var(--anel-foco)`; demais `focus-visible:outline-none` sempre acompanhados de `ring-2`)
- ✓ forms: `autocomplete`+`name`+`type` corretos (`app/login/page.tsx:81,83,93,95`; `app/cadastro/page.tsx:128,138-153`; `app/radar/page.tsx:128-136`); `autoComplete="off"` em não-auth (`Header.tsx:172,294`, `CommandPalette.tsx:91`, `app/comunidade/nova/page.tsx:154,175`); submit habilitado + spinner (`ui/button.tsx:110-111` `disabled||loading` + `aria-busy`, `app/login/page.tsx:101`); erro inline + foco 1º erro (`app/login/page.tsx:28-47`, `app/comunidade/nova/page.tsx:67-69`, `app/cadastro/page.tsx:54`); paste nunca bloqueado (grep `onPaste|preventDefault.*paste` → 0)
- ✓ animação: `prefers-reduced-motion` global (`app/globals.css:295,1089,3155,3489`) + `motion-reduce:transition-none|animate-none` por componente (`ui/button.tsx:9`, `Hero.tsx:82-83`); só transform/opacity (`transition-colors|opacity|transform`); spinner `motion-reduce:animate-none` (`ui/button.tsx:116`)
- ✓ texto: `…` em todos placeholders (grep `"[^"]*\.\.\.` → 0; `…` em `nova/page.tsx:138,157,178,199`, `login/page.tsx:84,96`, `radar/page.tsx:128-136`, `data-table.tsx:147`); `text-wrap-balance` em headings (`Hero.tsx:65,132`, `DetalheNoticia.tsx:143,176,250`, `comunidade/page.tsx:47,148,166,182`); `truncate/line-clamp/break-words` + `min-w-0` em flex (`comunidade/page.tsx:29,96`, `Cards.tsx:35,113,123,153`, `Hero.tsx:74`)
- ✓ datas/moeda via Intl: `BlocoEditoria.tsx:9`, `DetalheNoticia.tsx:21`, `comunidade/page.tsx:17`, `comunidade/[id]/page.tsx:23`, `minha-conta/page.tsx:66,72`, `planos/page.tsx:20,23`, `Rodape.tsx:52` — zero data hardcoded
- ✓ performance/estado: query-string deep-link (`comunidade/page.tsx:5,63,71-75` `router.replace` + `useSearchParams`; `radar/page.tsx:5,25`, `Header.tsx:5,332`); `text-[16px]` mobile anti-zoom (`ui/FormField.tsx:25,44`, `radar/page.tsx:128-136`, `comunidade/nova/page.tsx:137,160`, `ui/data-table.tsx:133,150`); inputs de filtro não-controlados (`radar/page.tsx:128` `defaultValue` + `key=`)
- ✓ touch/safe-area/overscroll: `touch-manipulation` + `min-h-[44px]` ubíquo (`ui/button.tsx:9`, `BottomNav.tsx:41-43,59`, `ThemeToggle.tsx:22,35`); `env(safe-area-inset-bottom)` (`BottomNav.tsx:20,41`, `layout.tsx:101,105`, `Rodape.tsx:58`, `BannerConsentimentoCookies.tsx:85`); `overscroll-contain/[overscroll-behavior:contain]` em modais/drawers/listas (`ui/dialog.tsx:20`, `Modal.tsx:20,37`, `Tabs.tsx:16`, `ToastProvider.tsx:28,96`, `ui/Data.tsx:7,102`)
- ✓ dark/hidratação: `color-scheme: light dark` (`globals.css:177`) + `theme-color` (`layout.tsx:43-44`) + `data-theme` toggle (`ThemeToggle.tsx:36`); `mounted` guard SSR (`ThemeToggle.tsx:17-29`); BottomNav SSR/hidratação (`BottomNav.tsx:17-20`)
- M1 (minor) `transition-all` (checklist: nunca `transition:all`): `components/Tabs.tsx:31` · `components/ToastProvider.tsx:96` · `components/ui/Cards.tsx:93,133` — trocar por `transition-colors,shadow,opacity` conforme propriedade animada
- M2 (minor) placeholder sem `…`: `components/Header.tsx:173,295` (`placeholder="Buscar"`) — padronizar para `Buscar…` (`CommandPalette.tsx:93` já usa `…`)
- N1 (nota, exige browser) `components/CommandPalette.tsx:98` (`focus-visible:ring-0` no input) — aceitável se o container (`command.tsx:37`, ring no wrapper) for o indicador visível; confirmar tab-order em browser real (§4)

## §4 — Ressalvas

- R1: browser real (chrome-devtools MCP) **não executado** — sem MCP neste ambiente; verificação = `tsc`+`build` (evidências da run) + auditoria estática por grep/leitura (§3). Pendente em browser: screenshots 360/768/1024/1440, dark/light, tab-order (incl. N1), contraste AA instrumental. Precedente: run `20260909-1200`, revertida em `2d8063c` — mesmo fallback aceito.
- R2: ECONNREFUSED em prerender (`generateStaticParams`) é backend-offline no CI, pré-existente e fora do escopo do diff (critério 3 vazio confirma); não mascara regressão de rota — 32/32 compilaram.
- R3: `Drawer.tsx` deletado vs contrato FRENTE C que lista `Drawer` (vaul) — coberto por `ui/sheet.tsx`; sem quebra de build/rotas; registrar decisão no `implementation-history.md`.
- R4: M1/M2 são minor, sem bloqueio; sugerir correção em follow-up, sem reabrir DoD.
