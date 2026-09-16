# Task Plan — 20260915-2142-frontend-tailwind-100

## Metadados
- **run_id:** 20260915-2142-frontend-tailwind-100
- **Data de abertura:** 2026-09-15
- **Solicitado por:** Alex — "as cinco skills sejam 100% estudadas e aproveitadas", migração Tailwind+shadcn autorizada explicitamente
- **Spec de origem:** `.claude/skills/frontend-portal/SKILL.md` (consolida 5) + contratos das 5 origens cruas

## Objetivo
Refazer o frontend 100% com as 5 skills em runtime real: migrar `frontend/` para Tailwind CSS + shadcn/ui v4 (Radix/Base UI) com 21st como catálogo, aplicar `frontend-design` em 2-pass com identidade editorial, auditar com `web-design-guidelines/command.md` fresco, e validar em browser real via `chrome-devtools-mcp` — mantendo 100% dos fluxos/rotas/contratos Django.

## Escopo
### Dentro do escopo
- Estudo 100% das 5 skills (fetch cru + docs + src, sem cache GitHub HTML)
- Setup Tailwind v4: `tailwindcss`/`postcss`/`autoprefixer`, `tailwind.config.*`, `postcss.config.*`, `globals.css` com `@tailwind` + tokens `--cor-*` mapeados ao `theme.extend.colors` (AA preservado), `next/font` mantido
- Setup shadcn: `class-variance-authority`/`clsx`/`tailwind-merge` + `lib/utils.ts` (`cn`), `lucide-react`, `@radix-ui/*` necessários, `components.json` se útil; `Button/Card/Dialog/Dropdown/Tabs/Tooltip/Accordion/Toast` via shadcn com demos/metadados do MCP quando disponível
- Catálogo 21st: `search`/`get_component`/`search_logo` com `API_KEY_21ST` (ou fallback estático documentado se sem chave), `generate` só com `aiGenerationEnabled`
- Rebuild visual das 26 rotas + shell + 25 componentes sobre Tailwind/shadcn, seguindo `design-spec.md` v2 (paleta 6 hex, 3 ritmos, wireframes)
- Verificação: `tsc --noEmit` + `next build` 32/32 + checklist `command.md` por arquivo + `chrome-devtools-mcp --slim --headless` em 360/768/1024/1440 + dark/light + tab-order + screenshots quando disponível (fallback documentado se sem MCP)
- Atualizar `frontend-portal` SKILL para marcar MCPs como runtime, não só referência

### Fora do escopo
- `backend/` (diff vazio), `frontend/lib/api.ts` (contrato), URLs/rotas, SEO (`sitemap`/`rss`/`JsonLd`), LGPD — só visual
- `generate` com IA sem crédito (respeitar `get_usage.aiGenerationEnabled`)

## Suposições assumidas
- Tailwind v4 compatível com Next.js 14 App Router (PostCSS); `globals.css` vira `@tailwind base/components/utilities` + camadas — reversível via git
- Shadcn defaults (Radix) são adequados; Base UI só se `UI_LIBRARY=base` for pedido — usar Radix (padrão)
- 21st sem chave = catálogo portado manualmente (free tier 2 installs/dia) — não bloqueia build

## Restrições
- Nova dependência autorizada mas revisada obrigatoriamente (`review-triggers.md`: introdução de dependência externa + diff >300)
- LGPD/SEO/anti-flash/`data-theme`/skip-link intactos; `backend/lib` sem diff; sem renames
- `prefers-reduced-motion` global, foco `:focus-visible` com `ring`, AA ≥4.5:1

## Divisão de trabalho
| Etapa | Agente | Entrada | Saída |
|---|---|---|---|
| 1 | executor (5 frentes Task-general paralelas) | implementation-contract.md + design-spec v2 | código + implementation-history.md |
| 2 | tester | contract + MCPs | test-report.md (passed/failed + screenshots se houver browser) |
| 3 | reviewer (obrigatório) | diff | code-review-contract.md |
| 4 | remediator | code-review | correções + revalidação |
| 5 | documenter | history | documentation-update.md + README/ARCHITECTURE |
| 6 | historian | todos | report.md + HISTORY.md |

## Critérios de aceite
1. 5 skills evidenciadas em uso runtime (MCP ou fallback documentado com prova de fetch + instalação)
2. Tailwind+shadcn instalados, `cn` helper, componentes shadcn em uso, 26 rotas reestilizadas sobre eles
3. `tsc` 0 + `build` 32/32 exit 0
4. Checklist `command.md` zero blocker/major (evidência por arquivo) + screenshots/tab-order quando browser disponível
5. `backend`/`lib/api.ts` vazios, sem renames, LGPD/SEO intactos
6. Revisão `approve`/`approve_with_comments`

## Riscos
| Risco | Impacto | Mitigação |
|---|---|---|
| Regressão visual por migração Tailwind (segundo revert) | alto | Mapear tokens `--cor-*` ao theme, aliases legados, build revalidado a cada frente |
| Conflito de arquivos entre frentes | alto | Partição exclusiva por arquivo; `globals.css` dono único (FRENTE A) |
| 21st sem chave / sem créditos IA | médio | Fallback catálogo portado + `generate` só com enabled |
| Chrome MCP indisponível no CI | médio | `--slim --headless` local + fallback estático documentado |
