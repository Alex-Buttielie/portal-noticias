# Documentation Update — 20260915-2246-mobile-app-nav

## Metadados
- **run_id:** 20260915-2246-mobile-app-nav
- **Baseado em:** implementation-history.md (20260915-2246-mobile-app-nav) — 4 iterações (M1 shell-nav + M2 componentes + M3 páginas + Iteração 4 merge) + remediação 6 findings + test-report.md (PASSED c/ ressalvas) + code-review-contract.md (changes_requested → remediado)

## Documentos afetados
| Documento | Tipo de mudança | Resumo |
|---|---|---|
| `README.md` | sem mudança adicional nesta run | Stack Tailwind+shadcn já refletida no staged diff herdado de `20260915-2142` (`## Como rodar o frontend` e `## Design system` atualizados para `Tailwind 3.4.17` + `shadcn/ui v4`). Esta run (modo móvel app-like) não altera stack nem endpoints — apenas shell responsivo (`BottomNav`, `Sheet`, `useIsMobile`, `safe-area`, `touch-manipulation 44px`). Documentação de uso móvel é código/autoevidente (navegação `sm:hidden` + `hidden sm:flex`); não requer nova seção no README. `git diff --cached -- README.md` já cobre o necessário. |
| `ARCHITECTURE.md` | sem mudança | Sem alteração de backend, modelo de dados, permissões ou eventos. Frontend segue Next.js 14 App Router (mesma decisão §1). Modo móvel é só camada visual/CSS-first + hook `useIsMobile` (client) — não introduz nova rota, provider ou contrato de API. |
| `.claude/skills/frontend-portal/SKILL.md` | sem mudança nesta run | MCPs runtime já marcados na run `20260915-2142` (shadcn/21st/chrome-devtools). Esta run respeita §0 (tema/anti-flash/LGPD/skip-link intactos) e §4 (fallback estático quando sem browser real, precedente `2d8063c`). |

## Sem impacto em documentação?
- [x] Confirmado: esta execução não requer atualização adicional de documentação porque o impacto é exclusivamente visual/responsivo (CSS-first Tailwind breakpoints + `BottomNav`/`Sheet`) sem novo contrato de uso, endpoint ou variável de ambiente. O staged `README.md` já traz a base Tailwind+shadcn necessária para onboarding; comportamento móvel é descrito em `implementation-history.md` e verificável em `test-report.md` §4.

## Exemplos/snippets novos ou atualizados
Nenhum snippet novo no README. Referências de uso da run são os próprios artefatos já auditados:

```tsx
// frontend/components/BottomNav.tsx — Bottom tab bar app-like (sm:hidden)
<nav aria-label="Navegação principal móvel"
  className="fixed bottom-0 inset-x-0 z-[var(--z-cabecalho)] sm:hidden border-t border-[var(--cor-borda)] bg-[var(--cor-fundo)]/95 pb-[env(safe-area-inset-bottom)] overscroll-contain touch-manipulation">
  <Link aria-current={ativo ? "page" : undefined} className="min-h-[44px] touch-manipulation focus-visible:ring-2" />
</nav>
```

```tsx
// frontend/lib/hooks/useIsMobile.ts — hook leve CSS-first
export function useIsMobile(breakpoint = 768): boolean {
  const [isMobile, setIsMobile] = useState(() => window.matchMedia(`(max-width: ${breakpoint}px)`).matches);
  useEffect(() => { const mql = window.matchMedia(`(max-width: ${breakpoint}px)`); mql.addEventListener("change", e => setIsMobile(e.matches)); return () => mql.removeEventListener("change", e); }, [breakpoint]);
  return isMobile;
}
```

```tsx
// frontend/app/layout.tsx — proteção contra cobertura do Rodapé
<main className="container pb-[calc(4rem+env(safe-area-inset-bottom))] sm:pb-6">{children}</main>
<div className="pb-[calc(4rem+env(safe-area-inset-bottom)+1rem)] sm:pb-0"><Rodape /></div>
<BottomNav />
```

Pontos de entrada para onboarding visual:
- Skill: `.claude/skills/frontend-portal/SKILL.md` (§ responsivo 360/768/1024/1440 + touch + safe-area)
- Contrato: `agentic-framework/state/run-20260915-2246-mobile-app-nav/implementation-contract.md`
- Histórico: `agentic-framework/state/run-20260915-2246-mobile-app-nav/implementation-history.md`
- Testes: `agentic-framework/state/run-20260915-2246-mobile-app-nav/test-report.md`

## Entrada de changelog
- `Unreleased`: Modo móvel app-like adaptativo — navegação primária vira `BottomNav` fixo `sm:hidden` com `safe-area` + `Sheet` (Radix Dialog) via hamburger `sm:hidden`/`hidden sm:flex`, `useIsMobile` hook (`matchMedia max-width:768` com guard SSR), `touch-action: manipulation`/`overscroll-behavior: contain`/`min-h-[44px]` em interativos, `text-[16px]` em inputs (evita zoom iOS) e `min-w-0`/`break-words` em Cards/Tabs/Tables; `layout.tsx` com `BottomNav` + padding `pb-[calc(4rem+env(safe-area-inset-bottom))]` para não cobrir `Rodape`/`focus-visible`. Sem mudança de rotas/contratos/`backend`/`lib/api.ts`. `tsc 0` + `build 32/32` (87.1 kB shared); review `changes_requested` → remediado.

## Verificação
- [x] Nenhum exemplo/trecho de documentação existente ficou contraditório com a mudança (README Tailwind+shadcn já staged permanece válido; ARCHITECTURE §1 "React (Next.js)" compatível; SKILL §0/§4 respeitados)
- [x] Build/lint de documentação rodado (sem linter dedicado; verificado por leitura direta de `README.md`, `ARCHITECTURE.md`, `SKILL.md` + `tsc --noEmit` 0 e `next build` 32/32 revalidados em test-report §1.1–1.2 e após remediação)
