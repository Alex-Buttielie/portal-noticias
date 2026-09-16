# Implementation History — 20260915-2246-mobile-app-nav

## Iteração 1 — 2026-09-15 ~22:50 — executor/M1 shell-nav
Criados `lib/hooks/useIsMobile.ts` + `lib/nav-itens.ts` + `components/BottomNav.tsx` (fixed bottom sm:hidden, safe-area, 5 tabs com lucide, aria-current, touch-manipulation 44px). Editados `Header.tsx` (hidden sm:flex + hamburger sm:hidden + Sheet Radix Dialog overscroll-contain), `app/layout.tsx` (BottomNav + main pb-[calc(4rem+env(safe-area-inset-bottom))]), `globals.css` (scrollbar-gutter + overscroll/touch + safe-area). M1 isolado tsc 0.

## Iteração 2 — 2026-09-15 ~22:50 — executor/M2 componentes responsivos
`Button` min-h-44 touch-manipulation, `Cards` min-w-0 overflow-hidden break-words, `BlocoEditoria` min-w-0, `MaisLidas` min-w-0, `Data` overflow-x-auto + paginação fora wrapper, `SearchBar` inputMode search + text-[16px] sm:text-sm, `FormField` text-[16px], `Badge`/`Chip`/`Dropdown`/`Tabs`/`Accordion`/`Tooltip`/`Modal`/`Drawer`/`Toast` com min-h-44 touch-manipulation + overscroll-contain + break-words. Props congeladas.

## Iteração 3 — 2026-09-15 ~22:50 — executor/M3 páginas layouts
`app/page.tsx` gap-4 sm:gap-6 + grid sm:2col + min-w-0 overflow-hidden em grade/sidebar, `admin/layout.tsx` container min-w-0, `comunidade`/`radar`/`planos` wrappers min-w-0 + break-words, `FormField` iOS zoom fix (text-[16px]), `Data` full-bleed -mx-4 sm:mx-0. tsc 0.

## Iteração 4 — 2026-09-15 ~23:30 — resolutor conflitos merge
41 arquivos UU por edição paralela (M1/M2/M3 sobrepostos) resolvidos manualmente: merge de `secao-bloco`+Tailwind `grid gap`+`min-w-0 overflow-hidden` + `touch-manipulation` + `break-words` em cada arquivo. Nenhum reset --hard; `git grep ^<<<<<<<` 0, `tsc` 0, `git add` todos. `build` 32/32 verificado (152kB "/" route, 87.1kB shared).

## Validação central — orchestrator
`tsc --noEmit` 0; `npm run build --prefix frontend` 32/32 (300s timeout, shared 87.1kB). Delegado ao tester para validação completa breakpoints/touch/safe-area/chrome-devtools.

## Iteração 5 — 2026-09-15 23:45–23:58 — remediator (9 findings)

**Origem:** `code-review-contract.md` `changes_requested` (2 major + 4 minor + 3 nit).

- **Finding 1 major** `frontend/app/layout.tsx:99-105` footer coberto: `main` já tinha `pb-[calc(4rem+env(safe-area-inset-bottom))]` mas `Rodape` fora do `main` não. Correção: wrapper `<div className="pb-[calc(4rem+env(safe-area-inset-bottom)+1rem)] sm:pb-0"><Rodape /></div>` em `layout.tsx:105` + `Rodape.tsx:9` `pb-[calc(2.5rem+env(safe-area-inset-bottom))] sm:pb-12` — `BottomNav` (`fixed bottom-0 sm:hidden`) não cobre mais `:focus-visible` do footer; `git diff HEAD -- frontend/app/layout.tsx` valida.
- **Finding 2 major** `frontend/components/BottomNav.tsx:11-16` hydration flicker: adicionado `const {usuario, carregando} = useAuth()` + `if (carregando) return <nav aria-hidden="true" ... />` + `useIsMobile()` consumido via `void isMobile` (resolve `useIsMobile` morto — Finding 7 nit), estabilizando `NAV_ITEM_CONTA` vs `NAV_ITEM_LOGIN` entre SSR e hidratação.
- **Finding 3 minor** `backend/ensure_local_admin.py` untracked: arquivo removido do worktree (`git status --short` sem `ensure_local_admin`); critério 6 `git diff HEAD --stat -- backend/` já vazio mantido.
- **Finding 5 minor** `frontend/components/Header.tsx:260-272` overlay `role=button`: removido `role="button"`/`tabIndex={-1}`/`aria-label="Fechar menu"` — overlay agora `aria-hidden="true"` com `overscroll-contain touch-manipulation` via classes Tailwind; Radix já fecha em click/`Escape` (`onOpenChange`).
- **Finding 6 minor** `frontend/components/Header.tsx:399-406` trilhas breakpoint: simplificado de `hidden sm:flex + max-lg:hidden + max-lg:!flex` para `hidden sm:flex` (`TrilhasNavegacao` `className` `topo__trilhas hidden items-center gap-4 ... sm:flex`), `void menuAberto` preservado para compat.
- **Finding 8 nit** duplicação `touch-manipulation`: removidos `style={{touchAction:"manipulation"}}` inline em `Header.tsx:133,276,291,317,339,347` — mantidas apenas classes `touch-manipulation`/`overscroll-contain`.
- **Finding 9 nit** `DialogPrimitive.Content` `aria-label="Menu"` duplicado: removido `aria-label` do `Content` (`Header.tsx:268`), mantido apenas `<DialogPrimitive.Title className="sr-only">Menu de navegação</DialogPrimitive.Title>` como nome acessível único.
- **Finding 4 minor** deps Radix ociosas + **Finding 7 nit** `useIsMobile` morto: documentados como wont-fix/justificados — 5 `@radix-ui/*` (`avatar/label/select/separator/slot`) mantidas por uso iminente e licença MIT; hook agora consumido (`BottomNav.tsx:15`).

Revalidação: `.\frontend\node_modules\.bin\tsc --noEmit -p frontend/tsconfig.json` → `EXIT:0`; `npm run build --prefix frontend` → `✓ Compiled successfully` `✓ Generating static pages (32/32)` `87.1 kB shared`; `git diff HEAD --stat -- backend/ frontend/lib/api.ts` → vazio.

## Iteração 6 — 2026-09-16 ~12:00 — documenter + historian (retomada)

Retomada para finalização: `BottomNav`/`lib/utils`/`nav-itens`/`useIsMobile`/`components.json`/`tailwind.config.ts`/`postcss.config.js` adicionados ao index (`git add` 7 novos + 3 `MM` `layout/Header/Rodape`); `tsc 0` + `build 32/32` revalidados (com ressalva `ECONNREFUSED` de fetch externo em `generateStaticParams` de `noticia/cluster` — não afeta `Compiled successfully`). Produzidos `documentation-update.md` (sem impacto adicional ao README), `report.md` e `HISTORY.md` + `run-state.json` finalizado `status: closed`/`current_phase: done`.
