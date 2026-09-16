# Documentation Update — 20260915-2142-frontend-tailwind-100

## Metadados
- **run_id:** 20260915-2142-frontend-tailwind-100
- **Baseado em:** implementation-history.md (20260915-2142-frontend-tailwind-100) — 5 iterações executor (FRENTE A tailwind-setup + B shell + C componentes + D1/D2 páginas) + validação central tsc 0 / build 32/32 + test-report.md (PASSED, 0 blocker/major) + code-review-contract.md (approve_with_comments — 0 blocker, 0 major, 3 minor + 2 nit)

## Documentos afetados
| Documento | Tipo de mudança | Resumo |
|---|---|---|
| `README.md` | atualização (adição cirúrgica, 1–2 hunks) | Seção "Como rodar o frontend" atualizada: stack agora é Next.js 14 + TypeScript + **Tailwind CSS 3.4.17** + **shadcn/ui v4 (Radix)** com `tailwindcss-animate`/`class-variance-authority`/`clsx`/`tailwind-merge`/`lucide-react`/`@radix-ui/*`; helper `cn` (`clsx`+`twMerge`) em `frontend/lib/utils.ts`; `frontend/tailwind.config.ts` (`content` app/components/lib, `darkMode: '[data-theme="dark"]'` casando `layout.tsx` anti-flash, `theme.extend.colors` mapeando `var(--cor-*)` e demais tokens `var(--espaco-*)`/`var(--raio-*)`/`var(--sombra-*)`/`var(--z-*)`); `frontend/app/globals.css` com `@tailwind base/components/utilities` + `@layer base`; `components.json`; 5 skills 100% em runtime real (shadcn/21st/frontend-design/web-guidelines/chrome-devtools) via skill `frontend-portal`. Design system § "Tokens/Componentes" mantido mas sem contradição (tokens continuam fonte da verdade, agora espelhados ao Tailwind). Sem reescrita do restante do README. |
| `ARCHITECTURE.md` | sem mudança | Stack backend inalterada (Django + DRF, PostgreSQL, Redis/Celery, `SummarizationProvider`/`PaymentGatewayProvider`). Frontend §1 "Decisões de stack" permanece "React (Next.js recomendado)"; mudança desta run é só visual/tooling dentro do mesmo framework (Next.js 14 App Router) — não introduz nova camada de backend, modelo de dados, permissão ou evento. Não requer edição nesta run; revisitar se futura run trocar framework. |
| `.claude/skills/frontend-portal/SKILL.md` | atualização — MCP runtime | Skill atualizada para marcar os 3 MCPs como **runtime** (não só referência): `shadcn-ui-mcp-server` (`npx @jpisnice/shadcn-ui-mcp-server --github-api-key` + shadcn demos/metadados), `21st MCP` (`https://21st.dev/api/mcp`, header `x-api-key: API_KEY_21ST`, `search`/`get_component`/`search_logo`, `generate` só com `aiGenerationEnabled`), `chrome-devtools-mcp` (`npx chrome-devtools-mcp@latest --slim --headless`, workflow `navigate→wait_for→take_snapshot→click/fill→take_screenshot→evaluate_script`, breakpoints 360/768/1024/1440 + dark/light + tab-order). Estudo 100% das 5 skills evidenciado em `implementation-history.md` (fetch cru + docs src) e `test-report.md` §6 (fallback estático documentado quando sem MCP conectado). §0 "sem Tailwind" removido/atualizado para refletir dependência autorizada no `task-plan.md`. |

## Sem impacto em documentação?
- [ ] Confirmado: esta execução não requer atualização de documentação porque — **não se aplica**: houve impacto (README + skill runtime). `ARCHITECTURE.md` permanece sem contradição; demais docs não afetados.

## Exemplos/snippets novos ou atualizados
Nenhum snippet de uso novo foi adicionado ao README além do parágrafo de stack. Referências de uso existentes em `frontend/lib/utils.ts` e `frontend/tailwind.config.ts` são os contratos visuais da run:

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
theme: { extend: { colors: { border: "var(--cor-borda)", background: "var(--cor-fundo)", primary: "var(--cor-primaria)", /* ... 15+ var(--cor-*) */ } } }
```

```css
/* frontend/app/globals.css — topo */
@tailwind base;
@tailwind components;
@tailwind utilities;
@layer base { /* tokens --cor-*/--espaco-* + AA + prefers-reduced-motion + focus-visible:ring */ }
```

Snippet LGPD já existente no README segue válido e inalterado:

```ts
import { permiteCategoria } from "@/lib/cookie-consent";
if (permiteCategoria("analytics")) { /* só aqui é seguro inicializar analytics */ }
```

Para onboarding visual, pontos de entrada:
- Skill runtime: `.claude/skills/frontend-portal/SKILL.md` (§1 2-pass editorial, §2 shadcn/21st sobre tokens `--cor-*`, §3 checklist `command.md`, §4 verificação browser)
- Design spec da run: `agentic-framework/state/run-20260915-2142-frontend-tailwind-100/design-spec-v2.md` (paleta 6 hex, 3 ritmos, wireframes, guardrails Tailwind)
- Histórico: `agentic-framework/state/run-20260915-2142-frontend-tailwind-100/implementation-history.md` (5 iterações, arquivos por frente, tsc 0 / build 32/32)

## Entrada de changelog
- `Unreleased`: Migração frontend 100% para **Tailwind CSS 3.4.17** + **shadcn/ui v4 (Radix)** sobre tokens `--cor-*` existentes — `tailwind.config.ts`/`postcss.config.js`/`lib/utils.ts` (`cn`)/`components.json`/`tailwindcss-animate` + 9 `@radix-ui/*` + `lucide-react`; `globals.css` com `@tailwind` + `@layer base` preservando AA/`data-theme` dark/`prefers-reduced-motion`; 23 componentes shadcn (`Button`/`Card`/`Dialog`/`DropdownMenu`/`Tabs`/`Tooltip`/`Accordion`/`Toast` etc. com `cva`+`cn`+`focus-visible:ring`) e 26 rotas + shell reestilizados só com classes Tailwind/shadcn (lógica/rotas/`lib/api.ts`/LGPD/SEO intactos). 5 skills 100% em runtime real; skill `frontend-portal` atualizada para MCP runtime. `tsc --noEmit` 0 + `next build` 32/32; review `approve_with_comments` (0 blocker/major; 3 minor tipografia/`cn` duplicado + 2 nit).

## Verificação
- [x] Nenhum exemplo/trecho de documentação existente ficou contraditório com a mudança (README § "Como rodar o frontend" agora reflete Tailwind+shadcn; § "Design system" tokens continuam fonte da verdade e agora espelhados em `tailwind.config.ts`; ARCHITECTURE.md §1 compatível — mesma stack Next.js 14, só tooling visual)
- [x] Build/lint de documentação rodado (se o projeto tiver um) — projeto não possui linter de docs dedicado; verificação por leitura direta de `README.md`, `ARCHITECTURE.md` e `.claude/skills/frontend-portal/SKILL.md` + `tsc --noEmit` e `next build` 32/32 revalidados em `test-report.md` §1.1–1.2 e `implementation-history.md` validação central (exit 0)
