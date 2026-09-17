# Code Review Contract — 20260915-2246-mobile-app-nav

## Metadados
- **run_id:** 20260915-2246-mobile-app-nav
- **Escopo revisado:** `git diff HEAD --stat` (68 files, 7214 ins / 2606 del) — foco M1 shell-nav: `frontend/components/BottomNav.tsx` (novo, untracked), `frontend/components/Header.tsx`, `frontend/app/layout.tsx`, `frontend/app/globals.css`, `frontend/lib/hooks/useIsMobile.ts` (novo), `frontend/lib/nav-itens.ts` (novo), `frontend/lib/utils.ts` (novo), `frontend/components/PularParaConteudo.tsx`, `frontend/components/Rodape.tsx`, `frontend/components/ui/SearchBar.tsx`, `frontend/package.json`/`package-lock.json`/`tailwind.config.ts`/`postcss.config.js` + 35 `frontend/app/**/*`
- **Contrato de referência:** `agentic-framework/state/run-20260915-2246-mobile-app-nav/implementation-contract.md` v1 + `task-plan.md`; `test-report.md` 2026-09-15 23:00 UTC (PASSED c/ ressalvas)
- **Gatilhos aplicados (de `agentic-framework/prompts/review-triggers.md`):**
  1. **Auth/nav** — `frontend/components/BottomNav.tsx:6-15` usa `useAuth`/`usePathname` e alterna `NAV_ITEM_CONTA`/`NAV_ITEM_LOGIN`; `frontend/components/Header.tsx:68-110` também consome `useAuth` + `aria-expanded`/`aria-controls="mobile-nav-sheet"` + `Sheet` com foco preso — obrigatório.
  2. **Nova dependência externa** — `frontend/package.json:12-26` adiciona 11× `@radix-ui/*` + `tailwindcss`/`autoprefixer`/`postcss` + `class-variance-authority`/`clsx`/`tailwind-merge`/`lucide-react`/`tailwindcss-animate` (~3150 linhas em `package-lock.json`) — obrigatório (licença/superfície).
  3. **Volume >300 linhas** — 68 arquivos, 7214 inserções — obrigatório por volume.

## Findings

### Finding 1
- **Arquivo:** `frontend/app/layout.tsx`
- **Linha:** 99-105
- **Categoria:** correctness
- **Severidade:** major
- **Resumo:** `BottomNav` fixo cobre `Rodape`/`BannerConsentimentoCookies`; `main` tem `pb-[calc(4rem+env(safe-area-inset-bottom))]` mas `Rodape` está fora do `main` e sem compensação.
- **Cenário de falha:** Em viewport ≤640px, scroll até o fim da página → `BottomNav` (`frontend/components/BottomNav.tsx:27` `fixed bottom-0 inset-x-0 z-[var(--z-cabecalho)] sm:hidden`) sobrepõe ~4rem do `Rodape` (`frontend/components/Rodape.tsx:1` `mt-16 py-10`). Links "Termos/Privacidade/Cookies/RSS" no grid 4→1 e seu `focus-visible:ring` ficam ocultos atrás da barra; critério 2 do implementation-contract ("não cobre `:focus-visible`") é violado fora do `main`. Validado estático: `layout.tsx:101` só protege `main`, não irmãos posteriores.
- **Sugestão:** Dar ao wrapper que contém `Rodape` (ou ao `body`) `pb-[calc(4rem+env(safe-area-inset-bottom))] sm:pb-0` ou mover `BottomNav` antes do `</body>` com `pointer-events` e compensar com `main+footer` padding; adicionar `@supports` left/right safe-area se full-bleed.

### Finding 2
- **Arquivo:** `frontend/components/BottomNav.tsx`
- **Linha:** 11-16
- **Categoria:** correctness
- **Severidade:** major
- **Resumo:** `BottomNav` lê `usuario` direto de `useAuth` sem `carregando`, causando flicker/mismatch Conta↔Entrar entre SSR e hidratação.
- **Cenário de falha:** Usuário autenticado acessa `"/"` → SSR renderiza `NAV_ITEM_LOGIN` (`/login`); após hidratação `useAuth` resolve `usuario` → troca para `NAV_ITEM_CONTA` (`/minha-conta`), layout shift 20% (5 tabs) e `aria-current` muda sem navegação; `Header.tsx:68` (`const {usuario, carregando}`) já guarda `carregando`, mas `BottomNav` não. Também afeta `isActive`/`aria-current="page"` se pathname for `null` no primeiro render.
- **Sugestão:** Replicar guarda `if (carregando) return null` ou skeleton, ou estabilizar `itemConta` com `useMemo` + placeholder; considerar `suppressHydrationWarning` se intencional, ou renderizar `BottomNav` apenas client com `dynamic`.

### Finding 3
- **Arquivo:** `backend/ensure_local_admin.py`
- **Linha:** 1-87 (arquivo untracked, aparece em `git status --short`)
- **Categoria:** security
- **Severidade:** minor
- **Resumo:** Script de seed local com senha default `Admin123!` está untracked em `backend/` e não está em `.gitignore`; critério 6 (`git diff --stat -- backend/` vazio) passa mas polui repo e arrisca commit acidental de credencial.
- **Cenário de falha:** `git add .` em run futura inclui `backend/ensure_local_admin.py` com default password e `LOCAL_ADMIN_PASSWORD` em código; se mergeado, expõe credencial de seed e cria superfície para criação de superuser local em CI.
- **Sugestão:** Remover do worktree ou adicionar a `.gitignore` (`backend/ensure_local_admin.py`, `frontend-dev.log`, `temp_tsc.log`, `subir-localhost.bat` também untracked); se necessário manter, mover para `scripts/` e ler senha apenas de env sem default.

### Finding 4
- **Arquivo:** `frontend/package.json`
- **Linha:** 12-26
- **Categoria:** maintainability
- **Severidade:** minor
- **Resumo:** 11 dependências Radix adicionadas mas apenas `react-dialog`/`accordion`/`dropdown-menu`/`tabs`/`toast`/`tooltip` são importadas; 5 ficam sem uso (`@radix-ui/react-avatar:1.1.1`, `react-label:2.1.15`, `react-select:2.3.7`, `react-separator:1.1.0`, `react-slot:1.3.3`) inflando `package-lock.json` (+3150 linhas).
- **Cenário de falha:** `npm install` traz ~5 pacotes mortos; auditoria de licença/manutenção válida (todas MIT, ativas) mas superfície aumenta sem benefício e `build` mede 87.1kB shared — bundle não penalizado agora, mas futuras atualizações exigem churn desnecessário.
- **Sugestão:** Remover deps não importadas ou justificar em `implementation-history.md`; pinar versões com `overrides` se necessário.

### Finding 5
- **Arquivo:** `frontend/components/Header.tsx`
- **Linha:** 260-272
- **Categoria:** correctness
- **Severidade:** minor
- **Resumo:** `DialogPrimitive.Overlay` com `role="button"` + `tabIndex={-1}` + `aria-label="Fechar menu"` sem handler de teclado.
- **Cenário de falha:** Leitor de tela anuncia "button Fechar menu" mas elemento é `tabIndex=-1` (não focável) e sem `onKeyDown`; `test-report.md:138` marcou OK, mas `role=button` exige `Enter`/`Space`; Radix já fecha em click/`Escape` (`Header.tsx:87-94` + `Dialog onOpenChange`), então `role` é redundante e valida como `aria` misuse em axe.
- **Sugestão:** Remover `role="button"`/`tabIndex` e manter apenas `aria-hidden` ou `aria-label` no overlay, ou trocar por `DialogPrimitive.Close` cobrindo overlay; manter `style overscrollBehavior:contain`/`touchAction:manipulation`.

### Finding 6
- **Arquivo:** `frontend/components/Header.tsx`
- **Linha:** 399-406
- **Categoria:** style
- **Severidade:** minor
- **Resumo:** Lógica de visibilidade de `TrilhasNavegacao` mistura `hidden sm:flex` com `max-lg:hidden` / `max-lg:!flex` contraditória para breakpoint 640–1024.
- **Cenário de falha:** Em 768px (`sm`≥640, `lg` 1024): `hidden sm:flex` → flex, mas `max-lg:hidden` → hidden; `menuAberto && max-lg:!flex` reexibe ao abrir menu, mas estado fechado esconde trilhas em tablet onde deveriam aparecer (desktop preservado). Comportamento observado em diff: `TrilhasNavegacao` some em tablet sem menu aberto, divergindo de `Header top nav hidden sm:flex`.
- **Sugestão:** Simplificar para `hidden sm:flex` (ou `hidden lg:flex`) consistente com `Header` M1, sem `!important`; validar em 360/768/1024.

### Finding 7
- **Arquivo:** `frontend/lib/hooks/useIsMobile.ts`
- **Linha:** 5-25
- **Categoria:** maintainability
- **Severidade:** nit
- **Resumo:** Hook `useIsMobile` (contrato M1) nunca importado — CSS-first via `sm:hidden` já cobre caso; código morto.
- **Cenário de falha:** Bundle inclui ~28 linhas não usadas; `Select-String useIsMobile` só retorna o próprio arquivo; risco baixo, mas viola `Restrições técnicas: nenhuma nova além de useIsMobile (hook puro)` — hook existe mas não é consumido, contradiz "só onde precisa".
- **Sugestão:** Consumir em `BottomNav`/`Header` se necessário ou remover e documentar CSS-first como decisão; manter `matchMedia` com guard SSR + `addEventListener("change")` já correto.

### Finding 8
- **Arquivo:** `frontend/components/BottomNav.tsx`
- **Linha:** 33-54 / `frontend/components/Header.tsx:136,301,328,351`
- **Categoria:** style
- **Severidade:** nit
- **Resumo:** `style={{touchAction:"manipulation", overscrollBehavior:"contain"}}` inline duplica classes Tailwind `touch-manipulation`/`overscroll-contain` em todos os interativos móveis.
- **Cenário de falha:** Redundância intencional para fallback Safari antigo, mas polui 5+ nós; `test-report.md:184` já marcou como redundante não-blocker; sem impacto funcional.
- **Sugestão:** Manter apenas classe ou apenas `style` após validar `overscroll-contain` em iOS 16+; remover duplicata se Tailwind já cobre.

### Finding 9
- **Arquivo:** `frontend/components/Header.tsx`
- **Linha:** 273-287
- **Categoria:** correctness
- **Severidade:** nit
- **Resumo:** `DialogPrimitive.Content` com `aria-label="Menu"` + `DialogPrimitive.Title className="sr-only"` gera nome acessível duplicado.
- **Cenário de falha:** `aria-label` em `role=dialog` sobrepõe `aria-labelledby` implícito do `Title`; leitores anunciam "Menu" duas vezes ou ignoram `Title`. Radix recomenda apenas `Title` sem `aria-label` no `Content`.
- **Sugestão:** Remover `aria-label="Menu"` de `Content` e manter `Title` ("Menu de navegação") como única fonte; ou usar `aria-labelledby`.

## Resumo quantitativo
| Severidade | Quantidade |
|---|---|
| blocker | 0 |
| major | 2 |
| minor | 4 |
| nit | 3 |

## Veredito
**changes_requested**

2 majors exigem correção antes do merge: (1) `BottomNav` fixo cobre `Rodape` e `:focus-visible` do footer fora do `main` — compensar padding/safe-area no wrapper do footer; (2) `BottomNav` sem guarda `carregando` causa mismatch Conta/Entrar na hidratação. 4 minors (script untracked com senha default, deps Radix ociosas, overlay `role=button` sem teclado, trilhas com breakpoint conflitante) e 3 nits (hook morto, duplicação `touch-manipulation`, `aria-label` duplicado no Sheet) não bloqueiam isoladamente mas devem ser endereçados junto aos majors. Backend preservado (`git diff HEAD -- backend/ frontend/lib/api.ts` vazio) e `tsc 0`/`build 32/32` confirmados (test-report §1.1-1.3); validação browser 360/768/1024/1440 permanece pendente (ressalva test-report §1.5/§5.5) — executar antes do `approve`.
