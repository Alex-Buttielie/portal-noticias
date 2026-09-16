# Implementation Contract — 20260915-2246-mobile-app-nav

## Metadados
- **run_id:** 20260915-2246-mobile-app-nav
- **Deriva de:** task-plan.md
- **Versão:** 1

## O que deve ser construído
Modo móvel app-like adaptativo (CSS-first + hook leve):

- **FRENTE M1 — shell-nav (dono de `components/Header.tsx`, `components/Rodape.tsx`, `components/BottomNav.tsx` (novo), `app/layout.tsx`, `app/globals.css` (só tokens/overlay/safe-area), `lib/hooks/useIsMobile.ts` (novo), `components/MobileNav.tsx` se preciso):** hamburger `lg:hidden` → `Sheet` (Radix Dialog) com `aria-expanded`/`aria-controls`, foco preso + `Escape` + backdrop `role=button` + `overscroll-behavior: contain`; bottom nav `fixed bottom-0 inset-x-0 z-[var(--z-cabecalho)] sm:hidden` com `pb-[env(safe-area-inset-bottom)]`, 4–5 links (`/`, `/comunidade`, `/radar`, `/planos`, `/minha-conta` ou `/login`), `aria-current`, `touch-action: manipulation`, `min-h-[44px]`, `safe-area`; `Header` top nav `hidden sm:flex`; `layout.tsx` adiciona `BottomNav` + `main pb-[calc(4rem+env(safe-area-inset-bottom))] sm:pb-6` para não cobrir conteúdo; `useIsMobile` via `matchMedia("(max-width: 768px)")` com `useEffect` + guard SSR; `globals.css` adiciona `html { scrollbar-gutter: stable }` se útil e `overscroll-behavior: contain` no `Sheet` overlay.
- **FRENTE M2 — componentes responsivos (dono de `components/ui/*` + `components/*` compartilhados):** garantir `min-w-0`/`truncate`/`break-words` em `Card`/`Table`/`Badge`/`Chip`/`Tabs`/`Accordion`; `Button` `min-h-[44px]` já tem mas confirmar `touch-manipulation`; `Table` já com paginação fora do wrapper — garantir `overflow-x-auto` + `min-w-[640px]` sem quebrar 360; `SearchBar` com `type=search` + `inputMode=search` + `enterKeyHint=search`; `Drawer/Sheet` com `inert` opcional durante transição; tipografia com `text-wrap: balance` em headings; `Images` com `width/height` (já sem `next/image`, placeholder div ok).
- **FRENTE M3 — páginas layouts (dono de `app/**/*`):** ajustar `portal-layout` e grids para 1col <1024 (já `lg:grid-cols-[minmax(0,1fr)_330px]`), garantir `min-w-0` em flex children, `gap` responsivo, `text-[16px]` em `Input`/`Textarea` em mobile para evitar zoom iOS (`max-sm:text-[16px]`), `container` com `px-4` + `env(safe-area-inset-*)` onde full-bleed, sidebar em mobile vira stack (já faz) — sem mudar queries/router.

## Áreas/arquivos
- `components/BottomNav.tsx` (novo, M1), `lib/hooks/useIsMobile.ts` (novo, M1), `components/Header.tsx`, `Rodape.tsx`, `app/layout.tsx`, `app/globals.css` (só overlay/safe-area)
- `components/ui/*`, `components/*` (M2, exclusivos por arquivo)
- `app/**/*` (M3, subdividido)

## Interfaces
- Hook `useIsMobile(): boolean` como contrato interno; sem API nova; `BottomNav` consome `usePathname`/`useAuth`.

## Critérios técnicos
1. Quando viewport 360, então sem overflow-x (360/768/1024/1440 validados estático + screenshots se browser).
2. Quando `sm:hidden` bottom nav, então `aria-current="page"` + `safe-area` + não cobre `:focus-visible` (main com padding-bottom).
3. Quando hamburger clicado ou `Escape`, então `Sheet` abre/fecha com foco preso, `aria-expanded` sincronizado, `overscroll-behavior: contain`, `touch-action: manipulation`, `min-h 44px` em todos os interativos móveis.
4. Quando `tsc --noEmit -p frontend/tsconfig.json` + `npm run build --prefix frontend`, então exit 0, 32/32.
5. Quando auditado por `command.md` fresco, então zero blocker/major.
6. Quando `git diff HEAD --stat -- backend/ frontend/lib/api.ts`, então vazio.

## Não-objetivos
- PWA/manifest, mudar rotas/SEO/LGPD, `user-scalable=no`, bloquear `paste`.

## Restrições técnicas
- `prefers-reduced-motion` global, `focus-visible:ring`, `color-scheme`, `data-theme`, AA
- Dependências: nenhuma nova além de `useIsMobile` (hook puro); se precisar `vaul`/`embla`, justificar

## DoD
- [ ] Critérios 1–6
- [ ] Testes passando
- [ ] Revisão aprovada se gatilho
- [ ] Docs atualizadas
- [ ] History coerente
