# Code Review Contract — 20260916-1430-frontend-rebuild-5skills

## 1. Metadados

- **run_id:** 20260916-1430-frontend-rebuild-5skills
- **Contrato de referência:** `agentic-framework/state/run-20260916-1430-frontend-rebuild-5skills/implementation-contract.md` (v1)
- **Skill de referência:** `.claude/skills/frontend-portal/SKILL.md` ( §§0–4 ) + `agentic-framework/prompts/review-triggers.md`
- **Escopo auditado (working tree vs HEAD):**
  - `git diff HEAD --stat`: **56 arquivos rastreados alterados — 5880 inserções / 3351 deleções**
    - `frontend/app/**` (26 rotas/páginas + `layout.tsx`), `frontend/components/**` (Header, Rodape, BottomNav, Banner, ThemeToggle, ui/Button, ui/ReadingProgress, ui/SearchBar, ui/ShareButtons), `frontend/components.json`, `frontend/lib/utils.ts`, `frontend/tailwind.config.ts`, `frontend/postcss.config.js`, `frontend/package.json`, `frontend/package-lock.json`, `.gitignore`
    - `D frontend/components/ui/Drawer.tsx` (removido)
  - `git status --porcelain`: 112 linhas — além do diff acima, **~45 arquivos novos não-rastreados** (`frontend/components/ui/*.tsx` em minúsculas: accordion, alert, avatar, badge, breadcrumb, calendar, card, carousel, checkbox, command, context-menu, data-table, datatable, datepicker, dialog, dropdown-menu, form, hover-card, input, label, menubar, navigation-menu, pagination, popover, pricing-table, progress, prose, radio-group, resizable, scroll-area, select, separator, sheet, skeleton, sonner, sparkline, switch, tabs, textarea, toast, toaster, tooltip; `Hero.tsx`, `HomeHero.tsx`, `HomeSidebar.tsx`; `lib/hooks/use-toast.ts`) + ruído de processo (`agentic-framework/state/run-…`, `frontend/task-plan.md`, `frontend/write-homemain.js`, `subir-localhost.bat`)
  - `git diff HEAD --stat -- backend frontend/lib/api.ts`: **vazio** (contrato com Django preservado)
  - `git log --oneline -5`: HEAD em `9dd4b2a` (checkpoint pré-rebuild); rebuild ainda não commitado
- **Evidências declaradas pela run (não re-executadas neste review):** `tsc --noEmit` exit 0, `npm run build` 32/32 exit 0 (ambiente Windows local)
- **Método:** leitura direta de `Header.tsx`, `BottomNav.tsx`, `layout.tsx`, `Rodape.tsx`, `JsonLd.tsx`, `ThemeToggle.tsx`, `PularParaConteudo.tsx`, `ui/button.tsx`, `ui/data-table.tsx`, `ui/datatable.tsx`, `tailwind.config.ts`, `app/globals.css` (:root + dark), `package.json`, `providers.tsx`; `grep` de imports/exports/tokens/placeholders/hex; `git ls-files --stage`; inspeção de `node_modules/@tanstack/react-table` (v9.2.4, subpath `./legacy` válido)

## 2. Gatilhos de revisão aplicáveis (review-triggers.md + contexto)

| Gatilho | Aplica? | Foco auditado |
|---|---|---|
| Diff > ~300 linhas (5880+/3351-, 56 arquivos + ~45 novos) | SIM | correctness geral, duplicatas, regressões visuais |
| Nova dependência externa (`package.json`: +alert-dialog, checkbox, context-menu, form, hover-card, menubar, navigation-menu, popover, progress, radio-group, scroll-area, switch, tanstack-table, embla, next-themes, RHF, sonner, vaul) | SIM | uso real vs dependência morta, licença/risco, version drift |
| Auth/nav (`Header`/`BottomNav` usam `useAuth`) | SIM | guarda `carregando`, flicker SSR→hidratação, aria |
| a11y/LGPD/SEO (rebuild visual total) | SIM | foco, labels, contraste, skip-link, banner LGPD, JsonLd/XSS, metadata |

## 3. Findings

### 3.1 MAJOR

- **frontend/components/ui/button.tsx:14,16,25 — tokens — `text-[var(--cor-texto-invertido)]` referencia token inexistente.** Cenário de falha: `grep` em `app/globals.css` inteiro confirma que `--cor-texto-invertido` **nunca é definido** (`:root`, bloco dark e `[data-theme]`). Todo botão `default`/`destructive`/`premium` herda a cor de texto do body (`#0b0d12`) sobre fundo `--cor-primaria` (`#4338ca`) — contraste ~2,5:1, quebra AA e regressão visual direta contra o `text-white` anterior. O mesmo token fantasma aparece em `ui/badge.tsx:13,17,20,22`, `ui/tabs.tsx:34`, `ui/pagination.tsx:45`, `ui/calendar.tsx:126`, `ui/switch.tsx:24` (knob invisível sobre track claro), `ui/checkbox.tsx:25`, `ui/navigation-menu.tsx:101`, `ui/ShareButtons.tsx:48`. Sugestão: definir `--cor-texto-invertido: #FFFFFF` em `:root` + equivalente no tema escuro (ou remapear para token existente) **antes** do merge; validar contraste AA nos CTAs primários.
- **frontend/components/ui/Button.tsx (índice git) vs `ui/button` (imports) — casing — quebra de build em filesystem case-sensitive.** Cenário de falha: `git ls-files --stage` registra `frontend/components/ui/Button.tsx` (PascalCase), mas **30+ arquivos importam `@/components/ui/button`** (minúsculas). Em Windows o `tsc`/`build` passa (FS case-insensitive); em Linux (VPS/CI/Docker — alvo do deploy) a resolução falha e o build quebra. O disco local mostra uma únicaentry (`button.tsx`) justamente pelo colapso de case. Sugestão: `git mv frontend/components/ui/Button.tsx frontend/components/ui/button.tsx` (com `core.ignorecase=false` conferido) e auditar todo par rastreado-vs-import (`Cards`/`Data`/`Estados`/`FormField`/`ReadingProgress`/`SearchBar`/`ShareButtons` estão consistentes hoje — manter).
- **frontend/tailwind.config.ts:24-52 + frontend/components/ui/badge.tsx:22 — tokens — config referencia `--cor-*` sem definição.** Cenário de falha: `secondary` (`--cor-secundaria*`), `destructive.hover/soft` (`--cor-erro-hover/suave`), `success.hover/soft`, `warning.*` (`--cor-alerta*`), `premium.hover/soft` e todos os `foreground: var(--cor-texto-invertido)` não existem em `globals.css`; `bg-[var(--cor-alerta)]` (badge warning) resolve para fundo transparente. Qualquer uso das classes semânticas (`bg-secondary`, `bg-warning`, `text-*-foreground`) rende CSS inválido silencioso. Hoje o impacto é contido porque os componentes usam valores arbitrários `bg-[var(...)]`, mas o badge `warning` já está quebrado. Sugestão: definir os tokens ausentes em `globals.css` (light + dark) **ou** remapear o config para tokens existentes (`secundaria→primaria`, `alerta→destaque`, etc.) e documentar em `design-spec.md`.
- **Cobertura de contrato — 5 módulos novos sem nenhum consumidor + dependência morta.** Cenário de falha: `ui/form.tsx`, `ui/datatable.tsx`, `ui/sonner.tsx`, `ui/toaster.tsx` (+ `ui/toast.tsx` usado só pelo próprio toaster, `lib/hooks/use-toast.ts`) têm **zero importadores** — as páginas continuam em `ui/FormField` (legado), `ui/Data` (legado, 8 páginas vs 1 em `data-table`) e `ToastProvider` legado (montado em `providers.tsx`, funcional). `vaul@^1.1.2` foi adicionado ao `package.json` mas o `Drawer.tsx` foi **deletado** e não há nenhum `import` de `vaul` no projeto. Resultado: dois sistemas de UI em paralelo + bundle com peso morto + Frentes C/D1/D2 do contrato (Form RHF+Zod, DataTable com deep-link, Sonner, Drawer) formalmente não cumpridas nas páginas. Sugestão: ou migrar ≥1 consumidor real por módulo (e remover os legados correspondentes) ou remover os módulos/`vaul` do escopo desta run e registrar a dívida em `implementation-history.md`.

### 3.2 MINOR

- **frontend/components/Rodape.tsx:39 — rota inexistente — link `Newsletter → /newsletter` sem rota.** Cenário de falha: `glob app/newsletter/**` retorna vazio; usuário cai em `not-found`. Sugestão: criar a rota (ou redirecionar para `/lista-de-espera`/seção de newsletter da sidebar) ou remover o link. Verificar também `Legal/LGPD → /privacidade/lgpd` (Rodape.tsx:~35): `app/privacidade/*` contém só `politica` + `preferencias-cookies` — se a rota não existir, mesmo tratamento.
- **frontend/components/Header.tsx:173,295 — forms — `placeholder="Buscar"` sem `…`.** Cenário de falha: viola a guideline vigente (`placeholder` terminado em `…`); `data-table.tsx:57` e `SearchBar` já usam `Buscar…`. Sugestão: `placeholder="Buscar…"`.
- **frontend/components/ui/SearchBar.tsx — código morto.** Cenário de falha: arquivo rastreado e **modificado** nesta run, mas com zero importadores (Header usa `CommandPalette` + `ui/input`). Sugestão: remover ou adotar na busca do Header/Sheet.
- **frontend/components/ThemeToggle.tsx:17-29 — a11y — botão pré-mount sem ação.** Cenário de falha: antes da hidratação renderiza um `Button` focável com `aria-label="Alternar tema"` e **sem `onClick`** — controle morto no tab-order durante SSR. Sugestão: `disabled` + `aria-hidden`/`tabIndex={-1}` no ramo `!mounted`, ou esqueleto não-interativo.
- **frontend/components/ui/button.tsx:94-104 — correctness — ramo `asChild` descarta `disabled` e não propaga loading.** Cenário de falha: chamador com `asChild + disabled` ou `asChild + loading` gera filho (ex.: `<Link>`) plenamente navegável sem spinner e sem `aria-disabled` — estado de loading apenas em `aria-busy`. (O fix do crash `Slot` single-child está correto e **não** é finding.) Sugestão: documentar a limitação no componente ou propagar `aria-disabled` + bloqueio de navegação no filho.
- **frontend/components/BottomNav.tsx:25 — higiene — `void isMobile` executa hook só para "cumprir contrato".** Cenário de falha: `useIsMobile()` roda a cada render sem efeito; a renderização já é CSS-first (`sm:hidden`). Sugestão: remover import/call ou usar de verdade (`if (!isMobile) return null`) para tirar a nav fixa da árvore a11y no desktop.
- **frontend/components/ui/data-table.tsx:36-46,94-109 — roteamento — deep-link via `window.history.replaceState`.** Cenário de falha: funciona, mas contorna o App Router — consumidores via `useSearchParams` e navegação back/forward não reagem ao estado da tabela. Sugestão: migrar para `useRouter`/`useSearchParams` (`next/navigation`) com `replace`.

### 3.3 NIT

- **frontend/package.json — drift de versão — `sonner@^2.0.8` vs contrato (`1.4.0`).** Build passa, mas a API v2 diverge da v1; travar/documentar a versão adotada.
- **frontend/components/Header.tsx — dropdown da conta com dois links para o mesmo `/minha-conta`** ("Minha conta" + "Assinatura e perfil"). Diferenciar destinos (ex.: `?aba=assinatura`) ou deduplicar.
- **Ruído não-rastreado com risco de commit acidental:** `frontend/task-plan.md`, `frontend/write-homemain.js`, `subir-localhost.bat`, `agentic-framework/state/run-*/`, `.claude/skills/frontend-portal/`. Não commitar; considerar `.gitignore`.
- **Nomenclatura duplicada:** `ui/datatable.tsx` (adapter) vs `ui/data-table.tsx` (canônico), `ui/Cards.tsx` (legado, 1 consumidor) vs `ui/card.tsx` (novo, 30+ consumidores). Manter um nome canônico por conceito.
- **frontend/components/PularParaConteudo.tsx:9 — `text-white` hardcoded.** Consistente com o padrão antigo; migrar para o token quando `--cor-texto-invertido` for definido (ver MAJOR 1).

## 4. Verificado e conforme (não-findings — o que já foi corrigido não é finding)

- `ui/button.tsx` asChild/spinner: spinner condicional removido do ramo `Slot` — crash de prerender eliminado, com comentário explicativo correto.
- Guardas de hidratação: `Header.tsx` (`{!carregando && …}`, sem flicker Entrar→Conta), `BottomNav.tsx:18-22` (esqueleto `aria-hidden` durante `carregando`), `ThemeToggle` (`mounted`).
- Rodapé coberto por `BottomNav` fixa: **resolvido** — `layout.tsx:101` (`main` com `pb-[calc(4rem+…)]`) + `layout.tsx:105-107` (wrapper do `Rodape` com `pb-[calc(4rem+…)]` no mobile).
- `JsonLd.tsx:15` escapa `<` (`\u003c`) — sem XSS via `</script>` em títulos.
- `backend/` + `lib/api.ts`: diff vazio; `useAuth`, `site.ts`, `schema.ts`, `cookie-consent.ts` preservados; `ToastProvider` montado e usado (toasts legados funcionam).
- SEO/LGPD/contratos preservados em `layout.tsx`: `metadata`/`viewport`/`JsonLd`+`organizationJsonLd`, `BannerConsentimentoCookies`, script anti-flash, skip-link `#conteudo-principal` (`main#conteudo-principal` + `tabIndex={-1}` + `scroll-mt-24`).
- Migração default→named exports consistente (`ThemeToggle`, `BannerConsentimentoCookies` — sem importadores quebrados).
- `Drawer.tsx` deletado sem importadores restantes; `Sheet` cobre a nav mobile (foco preso, Escape, backdrop).
- `data-table.tsx`: deep-link lido **e** escrito na query (`pagina`, filtros), `aria-sort`, labels `sr-only`, `text-[16px] sm:text-sm` anti-zoom iOS, `autocomplete`/`type`/`name` corretos na maioria dos forms.
- Tokens como fonte da verdade: `globals.css` **intocado** (correto per skill §0 — o contrato pedia paleta nova `#1E3A8A…`, mas preservar os tokens existentes evita regressão; registrar a decisão em `design-spec.md`).
- Sem hex hardcoded em `.tsx` (só `themeColor` legítimo em `layout.tsx:43-44`); `darkMode: ['class','[data-theme="dark"]']`, `content` globs, `tailwindcss-animate` e mapeamentos `spacing`/`radius`/`shadow`/`zIndex` conformes.
- `@tanstack/react-table@9.2.4` instalado **possui** o subpath `./legacy` — imports de `data-table.tsx`/`datatable.tsx` resolvem (checagem direta em `node_modules`).
- `.gitignore` (+6 entradas de logs/runtime) adequado.

## 5. Resumo quantitativo

| Severidade | Qtd |
|---|---|
| blocker | 0 |
| major | 4 |
| minor | 7 |
| nit | 5 |
| **total** | **16** |

## 6. Veredito

**`changes_requested`**

Justificativa: os MAJOR 1–3 são impeditivos de merge — texto de CTA primário com contraste quebrado por token inexistente (visual + AA), quebra de build no alvo Linux por divergência de case `Button.tsx` vs `ui/button`, e tokens/semânticas Tailwind sem definição (badge `warning` já afetado). O MAJOR 4 (módulos novos sem consumidor + `vaul` morto) exige decisão de escopo antes do merge. Nenhum blocker de segurança/integridade (sem credenciais, sem XSS, sem diff em backend/contrato Django). Re-review focado após: (a) definir `--cor-texto-invertido` (+ famílias `secundaria/alerta/erro-hover/suave/sucesso-hover/suave/premium-hover/suave` ou remapear o config), (b) normalizar o case de `ui/Button` via `git mv`, (c) remover ou adotar `form/datatable/sonner/toaster/use-toast/vaul/SearchBar`, (d) tratar links `/newsletter` (e confirmar `/privacidade/lgpd`).
