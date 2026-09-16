# Implementation History — 20260916-1430-frontend-rebuild-5skills

## Iteração 1 — 2026-09-16 ~14:30 — orchestrator/planning
Criados `task-plan.md` (6 frentes paralelas, 5 skills runtime), `implementation-contract.md` (escopo técnico detalhado), `design-spec.md` (Pass 1 plano + Pass 2 revisão anti-genérica). Run-state inicializado `status: in_progress`, `current_phase: implementation`.

## Iteração 2 — 2026-09-16 ~15:00 — executor/Frente A (Tailwind Setup)
**Arquivos criados/atualizados:**
- `frontend/tailwind.config.ts` — `content` app/components/lib, `darkMode: ['class', '[data-theme="dark"]']`, `theme.extend.colors` mapeando **todos** tokens `var(--cor-*)` (18 cores semânticas), `spacing` `--espaco-*`, `borderRadius` `--raio-*`, `boxShadow` `--sombra-*`, `zIndex` `--z-*`, `fontSize`/`fontWeight`/`lineHeight` tipografia, `transitionDuration`/`timingFunction`, `keyframes`/`animation` shadcn, `plugins: [tailwindcss-animate]`
- `frontend/postcss.config.js` — `tailwindcss` + `autoprefixer`
- `frontend/components.json` — shadcn schema `new-york`, `rsc: true`, `cssVariables: true`, aliases `@/components`, `@/lib/utils`, `@/components/ui`, `@/lib`, `@/lib/hooks`
- `frontend/lib/utils.ts` — `cn = twMerge(clsx(inputs))`
- `frontend/app/globals.css` — **mantido** tokens `--cor-*`/`--espaco-*`/`--raio-*`/`--sombra-*`/`--z-*`/`--fonte-*`/`--linha-altura-*`/`--duracao-*`/`--curva-*` + `@tailwind base/components/utilities` + `@layer base` (tokens preservados como fonte da verdade)
- `frontend/package.json` — dependências já presentes: `tailwindcss@3.4.17`, `postcss@8.4.49`, `autoprefixer@10.4.20`, `tailwindcss-animate@1.0.7`, `class-variance-authority@0.7.1`, `clsx@2.1.1`, `tailwind-merge@2.6.1`, `lucide-react@0.460.0`, `@radix-ui/*` (accordion, avatar, dialog, dropdown-menu, label, select, separator, slot, tabs, toast, tooltip), `@tanstack/react-query@5.102.8`, `next@14.2.15`, `react@18.3.1`

**Validação:**
- `.\frontend\node_modules\.bin\tsc --noEmit -p frontend/tsconfig.json` → `EXIT:0`
- `npm run build --prefix frontend` → `✓ Compiled successfully` + `✓ Generating static pages (32/32)` + `87.1 kB shared`

**Evidência skills runtime:**
- **frontend-design** Pass 1+2 → `design-spec.md`
- **shadcn-ui-mcp-server** — configuração `components.json` + `tailwind.config.ts` `cssVariables: true` pronta para MCP
- **21st-dev/magic-mcp** — `components.json` aliases prontos para `get_component`
- **web-design-guidelines** — `command.md` será fetchado fresco na validação
- **chrome-devtools-mcp** — validação agendada para fase final

## Iteração 3 — 2026-09-16 ~15:30 — executor/Frente E (Design Spec)
Produzido `design-spec.md` completo com:
- **Pass 1:** Paleta 18 tokens (6 base + variações), tipografia 2 famílias (`Source_Serif_4` + `Inter`), layout concept + wireframe ASCII 360/1440, 6 princípios
- **Pass 2:** Revisão anti-genérica tabelada contra 10 defaults §1.2, decisões documentadas
- **Evidência 5 skills** mapeada por seção

## Próximos passos (planejados)
| Frente | Status | Arquivos alvo |
|---|---|---|
| B — Shell | ⏳ Pendente | `Header.tsx`, `Rodape.tsx`, `BottomNav.tsx`, `app/layout.tsx`, `ThemeToggle.tsx`, `BannerConsentimentoCookies.tsx`, `PularParaConteudo.tsx` |
| C — UI Primitives | ⏳ Pendente | `components/ui/*` (25+ shadcn components) |
| D1 — Páginas Núcleo | ⏳ Pendente | `app/page.tsx`, `app/comunidade/*`, `app/radar/*`, `app/planos/*`, `app/noticia/*` |
| D2 — Páginas Auth/Admin | ⏳ Pendente | `app/cadastro`, `app/login`, `app/onboarding`, `app/minha-conta`, `app/lista-de-espera`, `app/jornalista/*`, `app/admin/*`, `app/autor/*`, `app/empresa`, `app/paginas/[slug]`, `app/privacidade/*`, `app/recuperar-senha`, `app/redefinir-senha`, `app/verificar-email`, `app/not-found` |
| Validação | ⏳ Pendente | `tsc 0`, `build 32/32`, `command.md` fresco 0 blocker/major, `chrome-devtools-mcp` screenshots |

## Iteração 4 — 2026-09-16 — executor/5 frentes paralelas (subagentes)
- **Frente B (shell):** `Header.tsx` rebuild (~380 linhas, NavigationMenu+Sheet+DropdownMenu shadcn, cva local removido); `Rodape.tsx` grid 4→2→1 + safe-area + foco 44px; `ThemeToggle.tsx` sem transition-all; `BannerConsentimentoCookies.tsx` migrado p/ Dialog shadcn + `lib/cookie-consent.ts`; `PularParaConteudo.tsx` polido. `layout.tsx`/`BottomNav.tsx` verificados conformes. 21st: nenhum bloco (decisão consciente).
- **Frente C1 (core):** 19 primitives normalizados (aliases PT `variante/tamanho/carregando`, `text-white`→tokens, `transition-all`→colors, anti-zoom `text-base sm:text-sm`); bug `variantMap/sizeMap` corrigido. 5 duplicatas PascalCase NÃO excluídas (~30 importadores fora do escopo — reportados).
- **Frente C2 (avançada):** 28 arquivos + exclusão `Drawer.tsx`; `data-table.tsx` TanStack v9 legacy + deep-link query string; `datatable.tsx` adaptador fino; `drawer.tsx` vaul; `form.tsx` RHF+Slot; sonner vs Radix coexistentes; `SearchBar/ReadingProgress/ShareButtons/sparkline` portados.
- **Frente D1 (núcleo):** 16 arquivos; `page.tsx` sem `HomeMain` inexistente + grid assimétrico + sidebar sticky; comunidade DataTable + deep-link; nova Form+validação inline; radar Cards+Sparkline+Tabs na query string; planos Pricing 21st adaptado; notícia JsonLd preservado.
- **Frente D2 (auth/admin):** 25 arquivos; auth com validação inline + foco 1º erro + spinner; onboarding steps 1/2/3; minha-conta Tabs + Dialog cancelar; admin sidebar+Sheet + DataTables + Dialogs; `paginas/[slug]` Server Component; privacidade Accordion; not-found Card. tsc EXIT 0.

## Iteração 5 — 2026-09-16 — correção crítica pós-build (orquestrador)
`next build` falhava no prerender de `/` e `/_not-found`: `ui/button.tsx` rendia `{loading && <svg>}` como segundo filho do Radix Slot no modo `asChild` ("Slot failed to slot onto its children"). Corrigido: ramo `asChild` repassa só `children` + `aria-busy`. Revalidação: tsc 0, build 32/32 (shared 87.1 kB; 2 ECONNREFUSED pré-existentes de prerender com backend offline).

## Iteração 6 — 2026-09-16 — tester + reviewer paralelos
- **Tester:** `test-report.md` PASSED-c-ressalvas (critérios 1–6: 4 PASS + 2 PASS-c-ressalva; command.md fresco 0 blocker/major, 2 minor + 1 nota; browser real sem MCP — precedente `2d8063c`).
- **Reviewer:** `code-review-contract.md` changes_requested (0 blocker, 4 major, 7 minor, 5 nit): tokens inexistentes, case-sensitivity git (`Button.tsx` vs `button`), deps não usadas.

## Iteração 7 — 2026-09-16 — remediator
14 tokens adicionados em `globals.css` (light+dark) + `--z-popover/--z-tooltip`; `git mv Button.tsx→button.tsx`; `<Toaster/>` montado em `layout.tsx`; `vaul` removido (`npm uninstall`); `transition-all` zerado; ajustes Rodape/ThemeToggle/Button/BottomNav/Pular/Header. tsc 0, backend/api diff vazio.

## Iteração 8 — 2026-09-16 — documenter + historian (fechamento)
`documentation-update.md` + README (1 linha stack) + SKILL §0 (Tailwind runtime); `report.md` + HISTORY append + `run-state.json` closed/done. Revalidação final: tsc 0, build 32/32, contratos intactos.

## Notas de arquitetura
- **Particionamento exclusivo:** Cada frente tem arquivos próprios; `globals.css` dono único (Frente A)
- **Tokens intocáveis:** `--cor-*` etc. permanecem em `globals.css`; Tailwind lê via `var(--cor-*)`
- **Intocáveis preservados:** `backend/` vazio, `frontend/lib/api.ts` vazio, rotas/SEO/LGPD/skip-link/anti-flash
- **Migração incremental:** Componentes existentes em `frontend/components/` serão reescritos shadcn/21st por frente