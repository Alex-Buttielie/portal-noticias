# Documentation Update — 20260916-1430-frontend-rebuild-5skills

## Metadados
- **run_id:** 20260916-1430-frontend-rebuild-5skills
- **Baseado em:** `implementation-history.md` (Iterações 1–3 + remediação pós-review), `implementation-contract.md` (v1, frentes A/B/C/D1/D2/E), `design-spec.md` (Pass 1 + Pass 2 anti-genérico), `test-report.md` (PASSED-c-ressalvas), `code-review-contract.md` (changes_requested → remediado), `git diff HEAD --stat` (62 arquivos rastreados, 5957+/3389-; só `frontend/` + `.gitignore`; `backend/` + `frontend/lib/api.ts` vazios), `README.md`, `ARCHITECTURE.md`

## Documentos afetados
| Documento | Tipo de mudança | Resumo |
|---|---|---|
| `README.md` | atualização cirúrgica mínima (1 hunk, § "Como rodar o frontend") | Parágrafo de stack atualizado para refletir o rebuild total desta run: Next.js 14 App Router + TypeScript + **Tailwind CSS 3.4.17** + **shadcn/ui v4 (Radix)**; tokens `--cor-*`/`--espaco-*`/`--raio-*`/`--sombra-*`/`--z-*` espelhados em `frontend/tailwind.config.ts` (`theme.extend`, `darkMode: '[data-theme="dark"]'` casando anti-flash de `layout.tsx`); helper `cn` (`clsx`+`tailwind-merge`) em `frontend/lib/utils.ts`; `frontend/app/globals.css` com `@tailwind base/components/utilities` + `@layer base` (tokens como fonte da verdade); `components.json` (`new-york`, `rsc`, `cssVariables`, aliases) + `tailwindcss-animate`/`class-variance-authority`/`lucide-react`/`@radix-ui/*`. Referência de run atualizada de `20260915-2142` para `20260916-1430-frontend-rebuild-5skills` (rebuild A/B/C/D1/D2, 47 arquivos `components/ui/*`). Nenhuma outra seção reescrita. |
| `.claude/skills/frontend-portal/SKILL.md` | atualização §0 (stack + MCP runtime) | Removido "Hoje **sem Tailwind**" — migração Tailwind+shadcn autorizada explicitamente no `task-plan.md` desta run (conforme regra do próprio §0; precedente `20260915-2142`). §0 passa a declarar stack efetiva (Next.js 14 + React 18 + TS + Tailwind 3.4 + shadcn v4: `tailwind.config.ts`, `postcss.config.js`, `components.json`, `lib/utils.ts` `cn`) e marca os 3 MCPs como **runtime quando disponíveis, com fallback documentado** (shadcn via MCP ou `ui.shadcn.com` + portar para tokens; 21st via MCP HTTP ou site; chrome-devtools via MCP ou `tsc`+`build`+checagem estática com ressalva em `test-report.md`; precedente `2d8063c`). Demais seções (§1–§4) intactas. |
| `ARCHITECTURE.md` | sem mudança (justificado abaixo) | §1 "Decisões de stack" declara Frontend "React (Next.js recomendado)" — o rebuild é tooling visual dentro do mesmo framework (Next.js 14 App Router + Radix + Tailwind), sem nova camada de backend, modelo de dados, permissão ou evento. Sem contradição real → sem edição, conforme instrução do documenter. |

## Sem impacto em documentação?
- [ ] Confirmado: esta execução **requer** atualização de documentação — **não se aplica o "sem impacto"**: houve impacto (README § stack + skill §0 runtime). `ARCHITECTURE.md` permanece sem contradição; `backend/`, `frontend/lib/api.ts`, `run-state.json`, `HISTORY.md`, `report.md` não tocados por escopo do documenter.

## Exemplos/snippets novos ou atualizados
Nenhum snippet de uso novo adicionado ao README além do parágrafo de stack atualizado. Contratos visuais da run (já existentes no código, referenciados aqui como prova):

```ts
// frontend/lib/utils.ts — helper único para variantes Tailwind/shadcn
import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";
export function cn(...inputs: ClassValue[]) { return twMerge(clsx(inputs)); }
```

```ts
// frontend/tailwind.config.ts — trecho (darkMode + content + theme.extend)
darkMode: ["class", '[data-theme="dark"]'],
content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],
theme: { extend: { colors: { background: "var(--cor-fundo)", primary: { DEFAULT: "var(--cor-primaria)", foreground: "var(--cor-texto-invertido)" } /* + secondary/destructive/success/warning/premium/muted/accent/card/skeleton */ }, spacing: { /* var(--espaco-*) */ }, borderRadius: { /* var(--raio-*) */ }, boxShadow: { /* var(--sombra-*) */ }, zIndex: { /* var(--z-*) */ } } }
```

```json
// frontend/components.json — shadcn v4 (new-york, rsc, cssVariables)
{ "style": "new-york", "rsc": true, "tsx": true, "tailwind": { "config": "tailwind.config.ts", "css": "app/globals.css", "baseColor": "neutral", "cssVariables": true }, "aliases": { "components": "@/components", "utils": "@/lib/utils", "ui": "@/components/ui", "lib": "@/lib", "hooks": "@/lib/hooks" } }
```

```css
/* frontend/app/globals.css — topo (tokens fonte da verdade + Tailwind) */
@tailwind base;
@tailwind components;
@tailwind utilities;
@layer base { /* :root + [data-theme="dark"] com --cor-* (incl. remediação: --cor-texto-invertido, --cor-erro/sucesso/alerta/secundaria/premium hover/suave, --cor-vidro, --z-popover/tooltip) + prefers-reduced-motion + :focus-visible ring */ }
```

Remediação pós-review (evidência para historian/reviewer, sem snippet novo no README):
- Tokens adicionados em `globals.css` (`--cor-texto-invertido`, famílias `*-hover`/`*-suave`, `--cor-vidro`, `--z-popover`/`--z-tooltip`; light + dark + `[data-theme]`) — resolve MAJOR 1 e 3 do `code-review-contract.md`.
- `git mv Button.tsx → button.tsx` (case fix; `RM` no status) — resolve MAJOR 2 (build Linux).
- `vaul` removido de `package.json` (Drawer deletado, `Sheet` cobre nav mobile) — parte do MAJOR 4.
- `Toaster` (`@/components/ui/sonner`) montado em `app/layout.tsx:111` + `ToastProvider` legado em `providers.tsx` — restante do MAJOR 4 documentado como dívida (módulos `form`/`datatable`/`sonner`/`toaster` sem consumidor migrado; páginas seguem `FormField`/`Data` legados sem quebra).

Snippet LGPD já existente no README segue válido e inalterado:

```ts
import { permiteCategoria } from "@/lib/cookie-consent";
if (permiteCategoria("analytics")) { /* só aqui é seguro inicializar analytics */ }
```

Pontos de entrada para onboarding visual:
- Skill runtime: `.claude/skills/frontend-portal/SKILL.md` (§1 2-pass editorial, §2 shadcn/21st sobre tokens `--cor-*`, §3 checklist `command.md` fresco, §4 browser 360/768/1024/1440 + dark/light + tab-order + AA)
- Design spec da run: `agentic-framework/state/run-20260916-1430-frontend-rebuild-5skills/design-spec.md` (Pass 1 paleta/tipografia/wireframes + Pass 2 anti-genérico)
- Histórico: `agentic-framework/state/run-20260916-1430-frontend-rebuild-5skills/implementation-history.md`
- Validação: `agentic-framework/state/run-20260916-1430-frontend-rebuild-5skills/test-report.md` (PASSED-c-ressalvas: tsc 0, build 32/32, `backend/`+`api.ts` vazio, command.md 0 blocker/major — só M1/M2 minor + N1 tab-order pendente de browser real; R1 fallback sem MCP precedente `2d8063c`)

## Entrada de changelog
- `Unreleased`: Rebuild total do frontend em 5 frentes (A setup Tailwind+tokens, B shell Header/Rodape/BottomNav/layout/ThemeToggle/Cookies/Skip-link, C1/C2 47 arquivos `components/ui/*` shadcn/21st com `cva`+`cn`+`lucide`+`focus-visible:ring`, D1 núcleo rio/comunidade/radar/planos/notícia, D2 auth/onboarding/admin) — `tailwind.config.ts` (`content` app/components/lib, `darkMode '[data-theme="dark"]'`, `theme.extend` espelhando `--cor-*`/`--espaco-*`/`--raio-*`/`--sombra-*`/`--z-*` + tipografia/motion/keyframes shadcn, `tailwindcss-animate`) + `postcss.config.js` + `components.json` + `lib/utils.ts` (`cn`) + `globals.css` `@tailwind` + `@layer base` (tokens fonte da verdade; remediação pós-review adicionou `--cor-texto-invertido`, `*-hover`/`*-suave`, `--cor-vidro`, `--z-popover`/`--z-tooltip` light+dark). Contratos preservados: rotas/SEO (`metadata`/`JsonLd`/`sitemap`/`rss`/`robots`)/LGPD/skip-link/anti-flash/`lib/api.ts`/`backend/` (diff vazio). `tsc --noEmit` 0 + `next build` 32/32 (87.1 kB shared; 2× `ECONNREFUSED` em prerender = backend offline no CI, pré-existente). Review `changes_requested` → remediado (tokens, `git mv button.tsx` case fix, `vaul` removido, `Toaster` montado em `layout.tsx`). Tester PASSED-c-ressalvas (browser real sem MCP neste ambiente; fallback estático + precedente `2d8063c`; pendente screenshots 360/768/1024/1440 + dark/light + tab-order/N1 + AA instrumental). Docs: README § stack + skill `frontend-portal` §0 (MCP runtime com fallback); `ARCHITECTURE.md` sem contradição → intocado.

## Verificação
- [x] Nenhum exemplo/trecho de documentação existente ficou contraditório com a mudança (README § "Como rodar o frontend" agora aponta run `20260916-1430` com Tailwind 3.4 + shadcn v4 + tokens + `cn` + `components.json`; § "Design system" tokens continuam fonte da verdade e agora espelhados em `tailwind.config.ts` incl. remediação; skill §0 sem "sem Tailwind", migração autorizada no `task-plan.md`, MCPs runtime com fallback; `ARCHITECTURE.md` §1 compatível — mesmo Next.js 14, só tooling visual)
- [x] Build/lint de documentação rodado (se o projeto tiver um) — projeto não possui linter de docs dedicado; verificação por leitura direta de `README.md`, `ARCHITECTURE.md` e `.claude/skills/frontend-portal/SKILL.md` + `tsc --noEmit` 0 / `next build` 32/32 / diff `backend/`+`api.ts` vazio reaproveitados de `test-report.md` §1–§2 (tester somente-leitura; documenter não reexecutou build nem tocou `backend/`/`lib/api.ts`/`run-state.json`/`HISTORY.md`/`report.md`)
