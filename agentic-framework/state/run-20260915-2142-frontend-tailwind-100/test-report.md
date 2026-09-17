# Test Report — 20260915-2142-frontend-tailwind-100

**Data:** 2026-09-15 ~22:05 (America/Sao_Paulo)
**Tester:** TESTER run 20260915-2142-frontend-tailwind-100 (Muse Spark)
**Workspace:** `C:\alex\brd_portal_noticias` — frontend `C:\alex\brd_portal_noticias\frontend`
**Fontes lidas:** `implementation-contract.md` (critérios 1-7), `design-spec-v2.md`, `.claude/skills/frontend-portal/SKILL.md` §3, `command.md` fresco (https://raw.githubusercontent.com/vercel-labs/web-interface-guidelines/main/command.md @2026-09-15)

---

## Veredito: **PASSED** (com 2 minors tipográficos; fallback browser documentado)

Build e tipos verdes, 32/32 rotas, Tailwind+shadcn 100% conforme contrato, isolamento de `backend/`/`lib/api` preservado, `frontend/app` só `M`, e auditoria `command.md` sem blocker/major. Pendência única é verificação runtime em browser real (sem MCP conectado) — coberto por fallback estático.

---

## 1) Evidências por passo (ordem solicitada)

### 1. `tsc --noEmit -p frontend/tsconfig.json`
- **Comando:** `.\frontend\node_modules\.bin\tsc --noEmit -p frontend/tsconfig.json`
- **Exit:** `0`
- **Erros:** *(nenhum — stdout/stderr vazios)*
- **Versão:** `5.5.4` (`.\frontend\node_modules\.bin\tsc --version`)

### 2. `npm run build --prefix frontend`
- **Exit:** `0`
- **Rotas:** `32/32` — `Generating static pages (32/32) ✓`
- **Warnings:** nenhum `warning`/`warn` no output (apenas `✓ Compiled successfully`)
- **Resumo rotas:**
```
Route (app)                              Size     First Load JS
┌ ○ /                                    16.5 kB         152 kB
├ ○ /_not-found                          142 B          87.3 kB
├ ○ /admin                               1.2 kB          118 kB
├ ○ /admin/assinaturas                   1.31 kB         139 kB
├ ○ /admin/fila                          1.25 kB         139 kB
├ ○ /admin/metricas                      8.5 kB          144 kB
├ ○ /admin/moderacao                     1.45 kB         139 kB
├ ○ /admin/planos                        2.06 kB         140 kB
├ ○ /admin/robos                         3.57 kB         142 kB
├ ○ /admin/usuarios                      1.47 kB         139 kB
├ ƒ /autor/[id]                          2.25 kB         137 kB
├ ○ /cadastro                            3.25 kB         138 kB
├ ○ /comunidade                          1.85 kB         137 kB
├ ƒ /comunidade/[id]                     4.34 kB         139 kB
├ ○ /comunidade/nova                     3.15 kB         138 kB
├ ○ /empresa                             2.89 kB         141 kB
├ ○ /jornalista/solicitar                3.54 kB         139 kB
├ ○ /jornalista/status                   3.65 kB         139 kB
├ ○ /lista-de-espera                     3.47 kB         139 kB
├ ○ /login                               5.04 kB         125 kB
├ ○ /minha-conta                         2.83 kB         141 kB
├ ƒ /noticia/cluster/[id]                166 B           139 kB
├ ƒ /noticia/item/[id]                   166 B           139 kB
├ ○ /onboarding                          3.47 kB         139 kB
├ ƒ /paginas/[slug]                      2.17 kB         122 kB
├ ○ /planos                              2.52 kB         138 kB
├ ○ /privacidade/politica                181 B          94.1 kB
├ ○ /privacidade/preferencias-cookies    3.44 kB         123 kB
├ ○ /radar                               2.6 kB          141 kB
├ ○ /recuperar-senha                     4.03 kB         124 kB
├ ○ /redefinir-senha                     4.31 kB         124 kB
├ ○ /robots.txt                          0 B                0 B
├ ○ /rss.xml                             0 B                0 B
├ ○ /sitemap.xml                         0 B                0 B
└ ○ /verificar-email                     3.29 kB         123 kB
+ First Load JS shared by all            87.1 kB
```
- **Warnings capturados:** `0` linhas com `warning` (grep case-insensitive vazio)

### 3. Git diff isolamento
- `git diff HEAD --stat -- backend/ frontend/lib/api.ts` → **vazio** (exit 0, sem linhas) — `backend/` intocado, `lib/api.ts` intocado
- `git diff HEAD --stat -- backend/` → vazio; `git diff HEAD --stat -- frontend/lib/` → vazio
- `git diff HEAD --stat -- frontend/package.json` → `1 file changed, 20 insertions(+), 1 deletion(-)` — esperado (deps Tailwind/shadcn autorizadas)
- `git diff HEAD --name-status -- frontend/app` → **33 × `M` apenas**, zero `A`/`D`/`R`:
  ```
  M  frontend/app/admin/assinaturas/page.tsx
  M  frontend/app/admin/fila/page.tsx
  M  frontend/app/admin/layout.tsx
  M  frontend/app/admin/metricas/page.tsx
  M  frontend/app/admin/moderacao/page.tsx
  M  frontend/app/admin/page.tsx
  M  frontend/app/admin/planos/page.tsx
  M  frontend/app/admin/robos/page.tsx
  M  frontend/app/admin/usuarios/page.tsx
  M  frontend/app/autor/[id]/PerfilAutorConteudo.tsx
  M  frontend/app/cadastro/page.tsx
  M  frontend/app/comunidade/[id]/page.tsx
  M  frontend/app/comunidade/nova/page.tsx
  M  frontend/app/comunidade/page.tsx
  M  frontend/app/empresa/page.tsx
  M  frontend/app/globals.css
  M  frontend/app/jornalista/solicitar/page.tsx
  M  frontend/app/jornalista/status/page.tsx
  M  frontend/app/layout.tsx
  M  frontend/app/lista-de-espera/page.tsx
  M  frontend/app/login/page.tsx
  M  frontend/app/minha-conta/page.tsx
  M  frontend/app/not-found.tsx
  M  frontend/app/noticia/cluster/[id]/page.tsx
  M  frontend/app/noticia/item/[id]/page.tsx
  M  frontend/app/onboarding/page.tsx
  M  frontend/app/page.tsx
  M  frontend/app/paginas/[slug]/page.tsx
  M  frontend/app/planos/page.tsx
  M  frontend/app/privacidade/preferencias-cookies/PreferenciasCookiesConteudo.tsx
  M  frontend/app/radar/page.tsx
  M  frontend/app/recuperar-senha/page.tsx
  M  frontend/app/redefinir-senha/RedefinirSenhaConteudo.tsx
  M  frontend/app/verificar-email/VerificarEmailConteudo.tsx
  ```
- `git diff HEAD --shortstat` → `64 files changed, 7036 insertions(+), 2598 deletions(-)` (60+ em `frontend/components/*` + `frontend/app/*` + configs)

### 4. Tailwind
- `grep @tailwind frontend/app/globals.css`:
  ```
  1:@tailwind base;
  2:@tailwind components;
  3:@tailwind utilities;
  ```
- `cat frontend/tailwind.config.ts` — **PASS**:
  - `darkMode: ["class", '[data-theme="dark"]']` (casa com `layout.tsx:77` anti-flash) ✓
  - `content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"]` cobre `app`+`components` ✓
  - `theme.extend.colors` mapeia `var(--cor-*)` (border/background/foreground/primary/destaque/destructive/sucesso/premium/muted/card/popover/secondary/accent + aliases `fundo/texto/borda/foco/erro`) ✓
  - `borderRadius`/`spacing`/`boxShadow`/`zIndex`/`fontFamily`/`fontSize`/`maxWidth` todos em `var(--*)` ✓
  - `plugins: [require("tailwindcss-animate")]` ✓
- `cat frontend/lib/utils.ts`:
  ```ts
  import { clsx, type ClassValue } from "clsx";
  import { twMerge } from "tailwind-merge";
  export function cn(...inputs: ClassValue[]) { return twMerge(clsx(inputs)); }
  ```
  ✓ `cn` exportado `clsx`+`twMerge`
- `cat frontend/components.json`:
  ```json
  { "$schema":"https://ui.shadcn.com/schema.json","style":"default","rsc":false,"tsx":true,
    "tailwind":{"config":"tailwind.config.ts","css":"app/globals.css","baseColor":"slate","cssVariables":true},
    "aliases":{"components":"@/components","utils":"@/lib/utils"} }
  ```
- `cat frontend/postcss.config.js`: `tailwindcss: {}, autoprefixer: {}` ✓
- `frontend/app/globals.css` `@layer base` preserva tokens `--cor-*`/`--espaco-*`/`--raio-*`/`--sombra-*`/`--z-*`, `:root` + `[data-theme="dark"]`, `prefers-reduced-motion` (4 ocorrências), `scroll-margin-top`/`scroll-mt-24` em layout, `focus-visible:ring` e `text-wrap: balance` mantidos.

### 5. shadcn
- `grep -R "cn(" frontend/components/ui | head` (20):
  ```
  frontend/components/ui/Button.tsx:87: className={cn(buttonVariants(...))}
  frontend/components/ui/Cards.tsx:13: className={cn(...
  frontend/components/ui/Data.tsx:8:  className={cn("w-full caption-bottom text-sm", ...
  frontend/components/ui/Drawer.tsx:23: className={cn(...
  ... (15+ hits)
  ```
- `grep -R "radix\|cva\|lucide" frontend/components | head` (20):
  ```
  frontend/components/Accordion.tsx:4: @radix-ui/react-accordion + lucide-react ChevronDown
  frontend/components/Badge.tsx:2: cva + VariantProps
  frontend/components/Chip.tsx:4: cva + lucide X
  frontend/components/Dropdown.tsx:4: @radix-ui/react-dropdown-menu
  frontend/components/Header.tsx:7: cva + lucide Menu/X/Search
  frontend/components/Modal.tsx:4: @radix-ui/react-dialog + lucide X/Loader2
  frontend/components/Tabs.tsx:4: @radix-ui/react-tabs
  frontend/components/ThemeToggle.tsx:4: lucide Moon/Sun
  frontend/components/ToastProvider.tsx:4: @radix-ui/react-toast
  frontend/components/Tooltip.tsx:4: @radix-ui/react-tooltip
  ```
- `ls frontend/components/ui`:
  ```
  Button.tsx, Cards.tsx, Data.tsx, Drawer.tsx, Estados.tsx, FormField.tsx, ReadingProgress.tsx, SearchBar.tsx, ShareButtons.tsx
  ```
- `frontend/package.json` deps shadcn/Tailwind:
  ```
  tailwindcss@3.4.17, autoprefixer@10.4.20, postcss@8.4.49, tailwindcss-animate@1.0.7,
  class-variance-authority@0.7.1, clsx@2.1.1, tailwind-merge@2.6.1, lucide-react@0.460.0,
  @radix-ui/react-accordion@1.2.20, @radix-ui/react-avatar@1.1.1, @radix-ui/react-dialog@1.1.23,
  @radix-ui/react-dropdown-menu@2.1.24, @radix-ui/react-label@2.1.15, @radix-ui/react-select@2.3.7,
  @radix-ui/react-separator@1.1.0, @radix-ui/react-slot@1.3.3, @radix-ui/react-tabs@1.1.21,
  @radix-ui/react-toast@1.2.23, @radix-ui/react-tooltip@1.2.16
  ```
- 23 componentes com `cva` variantes preservando props congeladas (`variante`/`tamanho`) — ver `Header.tsx:20 buttonVariants = cva(...)`, `Badge.tsx:5`, `Chip.tsx:8`, `ui/Button.tsx:8`

### 6. chrome-devtools MCP
- `npx -y chrome-devtools-mcp@latest --help` → **ok**, `chrome-devtools-mcp@latest` listado, `--version` → `1.9.0`
- `Test-Path "C:\Program Files\Google\Chrome\Application\chrome.exe"` → `True` (Chrome instalado)
- **MCP conectado?** Não — ambiente sem servidor MCP ativo (`opencode` sem `mcpServers.chrome-devtools` configurado; `SKILL.md` §4 confirma "sem MCP configurado por padrão"). Tentativa `new_page http://localhost:3000` não aplicável sem pipe `--browserUrl`/`--wsEndpoint` e sem `npm run dev` em background.
- **Fallback aplicado** (precedente `run 20260909-1200`, revert `2d8063c`): evidência estática via `tsc`+`build`+grep de `aria-*`/`focus-visible`/`prefers-reduced-motion` + checagem manual de breakpoints nos utilitários Tailwind (`container`, `lg:grid-cols-[minmax(0,1fr)_330px]`, `lg:sticky`, `sm:py-8`). Ressalva registrada abaixo.

### 7. Checklist web-guidelines (`command.md` fresco) — varredura `file:line` terse

Auditoria cobriu `frontend/app/**/*.{ts,tsx}` + `frontend/components/**/*.{ts,tsx}` + `frontend/app/globals.css` contra regras `Accessibility/Focus/Forms/Animation/Typography/Images/Performance/Navigation/Touch/Anti-patterns`.

**Resultado: 0 blocker / 0 major / 2 minor / 1 info**

```text
## frontend/app/redefinir-senha/page.tsx
frontend/app/redefinir-senha/page.tsx:6 - "..." → "…" (Typography: Suspense fallback "Carregando...")

## frontend/app/verificar-email/page.tsx
frontend/app/verificar-email/page.tsx:6 - "..." → "…" (Typography: Suspense fallback "Carregando...")

## frontend/app/globals.css
frontend/app/globals.css:279 - main:focus { outline: none; } sem anel substituto no seletor global (Focus: ok para tabIndex=-1 skip-target, mas divergente de :focus-visible; informativo)
frontend/app/globals.css:2987 - .botao:focus-visible { outline:none; box-shadow: var(--anel-foco); } ✓ pass (substituto presente)
frontend/app/globals.css:3078/3111/3230 - :focus { outline:none; box-shadow: var(--anel-foco); } ✓ pass (substituto presente)

## frontend/components/* — pass
frontend/components/Accordion.tsx:32 ✓ focus-visible:ring-2 presente
frontend/components/Badge.tsx:6 ✓ transition-colors + motion-reduce:transition-none + focus-visible:ring
frontend/components/CommandPalette.tsx:68 - <div role="dialog" onClick={e=>e.stopPropagation()}> ✓ pass (não é div-onClick navegacional; botão fecha é <button aria-label="Fechar busca rápida">)
frontend/components/Header.tsx:129/145/192/213 ✓ aria-label em botões só-ícone, <button> para ação, <Link> para navegação
frontend/components/ThemeToggle.tsx:53 ✓ aria-label dinâmico claro/escuro
frontend/components/ui/Button.tsx:8 ✓ focus-visible:outline-none focus-visible:ring-2 + motion-reduce:transition-none, hover: presente
frontend/components/ui/Drawer.tsx:33 ✓ motion-reduce:animate-none

## Anti-patterns — varredura negativa (ausentes = pass)
frontend: 0× transition: all
frontend: 0× user-scalable=no / maximum-scale=1 bloqueando zoom (viewport maximumScale=5 ✓)
frontend: 0× onPaste+preventDefault
frontend: 0× <div onClick> navegacional (só stopPropagation em dialog)
frontend: 0× <img> sem alt/dimensões (uso é Next Image / backgrounds; nenhum <img> cru encontrado)
frontend: 0× input sem label (FormField usa <Label htmlFor> + Radix Label)
frontend: 0× icon button sem aria-label (todos com aria-label: Header menu, ThemeToggle, ShareButtons, Chip remover, Drawer fechar, etc.)
frontend: 0× outline-none sem substituto em componentes shadcn (todos pareiam focus-visible:ring)
```

**Detalhe tipográfico:** placeholders com `…` corretos em 20+ locais (`placeholder="Buscar notícias, editorias…"` `Header.tsx:183`, `placeholder="Premium mensal…"` `planos/page.tsx:102`, etc.). Apenas os 2 Suspense fallbacks usam `...` ASCII — copiar-colar legado, severidade **minor**.

**Animação:** `prefers-reduced-motion` em 4 blocos (`* { animation-duration:0.001ms }`, `.esqueleto`, `.cartao-noticia/.botao`); animações só `transform`/`opacity`; nenhum `transition: all`; `motion-reduce:transition-none` em 10+ componentes.

**Foco:** `focus-visible:ring-[var(--cor-foco)]` em 25+ ocorrências (`Button`, `Cards`, `FormField`, `SearchBar`, `ShareButtons`, `Data`, etc.); `focus-visible:outline-none` sempre pareado com `ring`.

**Viewport:** `frontend/app/layout.tsx:37 viewport = { width:"device-width", initialScale:1, maximumScale:5, colorScheme:"light dark" }` — sem `user-scalable=no` ✓

---

## Tabela critérios 1–7

| # | Critério (implementation-contract.md) | Evidência | Veredito |
|---|----------------------------------------|-----------|----------|
| 1 | `npm run build` + `tsc --noEmit` exit 0, 32/32 rotas | `tsc EXIT:0` (v5.5.4), `build EXIT:0`, `32/32` geradas, `87.1 kB` shared, sem warnings | **PASS** |
| 2 | `grep @tailwind` + `tailwind.config.*` com `content` app+components e `theme.extend.colors` → `var(--cor-*)` | `@tailwind` 1-3 em `globals.css`; `content` 3 globs; `darkMode ["class",'[data-theme="dark"]']`; `colors` 15+ mapeados em `var(--cor-*)`; `borderRadius/spacing/boxShadow/zIndex/fontFamily` em `var(--*)` | **PASS** |
| 3 | `cat frontend/lib/utils.ts` → `cn` (`clsx`+`twMerge`) | `cn(...ClassValue[]) => twMerge(clsx(inputs))` presente | **PASS** |
| 4 | `grep radix\|cva\|lucide` ou `ls components/ui` → shadcn em uso | `ui/` 9 arquivos; 23 componentes com `cva`/`@radix-ui`/`lucide-react`; `cn()` em todos; `tailwindcss-animate` plugin | **PASS** |
| 5 | `git diff HEAD --stat -- backend/ frontend/lib/api.ts` vazio; `frontend/app` só `M` | `backend/` vazio, `lib/api.ts` vazio, `frontend/lib/` vazio; `frontend/app` 33×M zero A/D/R; `package.json` diff isolado (deps autorizadas) | **PASS** |
| 6 | `chrome-devtools-mcp` screenshots/tab-order/contraste 360/768/1024/1440 + dark/light ou fallback documentado | `chrome-devtools-mcp@1.9.0` disponível, Chrome em `Program Files` existe, mas sem MCP conectado/dev server; fallback estático aplicado e documentado (precedente 20260909-1200) | **PASS c/ ressalva** |
| 7 | Auditoria `command.md` fresco → zero blocker/major | 0 blocker, 0 major; 2 minor Tipografia (`...`→`…`), 1 info `main:focus` | **PASS** |

---

## Findings (por severidade)

### Blocker — 0
—

### Major — 0
—

### Minor — 2
- **M-1 — Typography `…`:** `frontend/app/redefinir-senha/page.tsx:6` e `frontend/app/verificar-email/page.tsx:6` — `fallback={<p>Carregando...</p>}` usa `...` ASCII. Regra `command.md` Typography exige `…` (U+2026). Correção trivial: `"Carregando…"` (não bloqueia critério 7, mas deve ser corrigido antes do merge).
- **M-2 — Placeholder já corrigido, mas confirmar escala:** `frontend/app/admin/planos/page.tsx:103 placeholder="30.00…"` e `:104 "180…"` terminam em `…` corretamente per `SKILL.md` §3 Forms; mantidos como **pass**, mas auditoria registrou `PLACEHOLDER_ASCII` falso-positivo do script por `...` em spread JS na mesma linha — não é defeito.

### Info — 1
- **I-1 — `globals.css:279 main:focus { outline: none; }`:** container `#conteudo-principal` com `tabIndex={-1}` em `layout.tsx:99` recebe `focus:outline-none focus-visible:outline-none` via Tailwind. O reset global `main:focus` é redundante mas inofensivo para skip-link (target programático). Recomendação: migrar para `main:focus-visible { box-shadow: var(--anel-foco) }` ou remover regra global.

---

## Ressalvas — Verificação em browser (critério 6)

- **Sem MCP conectado** nesta sessão `opencode` (sem `mcpServers.chrome-devtools` em config). Chrome `C:\Program Files\Google\Chrome\Application\chrome.exe` existe e `chrome-devtools-mcp@1.9.0` responde a `--help`/`--version`, mas não houve `navigate_page`/`take_snapshot`/`take_screenshot` runtime.
- **Mitigação estática realizada:**
  - `tsc` + `build` verdes garantem render SSR sem erro.
  - Grep de `aria-label` (25+), `aria-live="polite"` (4), `role="dialog"`/`navigation`/`region`, `focus-visible:ring` (25+), `prefers-reduced-motion` (4), `scroll-mt-24`/`scroll-margin-top` presentes.
  - Breakpoints 360/768/1024/1440 inferidos via classes Tailwind: `container`, `lg:grid-cols-[minmax(0,1fr)_330px]` (`page.tsx`), `lg:sticky`, `sm:py-8`, `hidden lg:flex` (Header), `grid 4→2→1` (Rodape). Nenhum `overflow-x-hidden` faltante detectado.
  - Dark/light via `data-theme` + `darkMode: '[data-theme="dark"]'` + `colorScheme: "light dark"` + `themeColor` light/dark em `layout.tsx:37`.
- **Recomendação para reviewer:** rodar `npm run dev` + `npx -y chrome-devtools-mcp@latest --headless --viewport 360x800` e repetir `new_page http://localhost:3000` com `take_snapshot`/`take_screenshot` nos 4 breakpoints + tab-order + contraste AA (precedente exigido em `SKILL.md` §4). Este report serve como evidência estática até lá.

---

## Conformidade design-spec-v2.md (resumo)

- Paleta 6 hex via tokens `var(--cor-*)` preservada; Tailwind `theme.extend.colors` espelha sem hardcode ✓
- Tipos `Inter`/`Source_Serif_4` via `next/font` + `fontFamily: {corpo: var(--fonte-corpo)}` ✓
- 3 ritmos (`grade-noticias`, `lista-compacta`, `editoria-grade` filete) mantidos em `page.tsx` ✓
- Anti-genérico 5 sinais respeitado; ousadia só em `topo__orbe` ✓
- Motion só `transform`/`opacity`, `150ms`, `motion-reduce:` ✓

---

## Reprodução

```powershell
.\frontend\node_modules\.bin\tsc --noEmit -p frontend/tsconfig.json; echo "EXIT:$LASTEXITCODE"
npm run build --prefix frontend
git diff HEAD --stat -- backend/ frontend/lib/api.ts frontend/package.json
git diff HEAD --name-status -- frontend/app
Select-String -Pattern "@tailwind" -Path "frontend/app/globals.css"
Get-Content frontend/tailwind.config.ts
Get-Content frontend/lib/utils.ts
Get-Content frontend/components.json
Select-String -Pattern "cn\(" -Path "frontend/components/ui/*"
Select-String -Pattern "radix|cva|lucide" -Path "frontend/components/*"
npx -y chrome-devtools-mcp@latest --version
Test-Path "C:\Program Files\Google\Chrome\Application\chrome.exe"
```

---

**Assinatura:** TESTER 20260915-2142-frontend-tailwind-100 — `test-report.md` único artefato escrito; código-fonte não editado.
