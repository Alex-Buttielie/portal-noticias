# Implementation Contract — 20260915-2142-frontend-tailwind-100

## Metadados
- **run_id:** 20260915-2142-frontend-tailwind-100
- **Deriva de:** task-plan.md (mesmo id)
- **Versão:** 1

## O que deve ser construído
Migrar `frontend/` para Tailwind + shadcn 100% e reconstruir o visual sobre os 5 skills em runtime:

- **FRENTE A — tailwind-setup (dono exclusivo de `frontend/app/globals.css`, `frontend/tailwind.config.*`, `frontend/postcss.config.*`, `frontend/lib/utils.ts`, `frontend/components.json` se usado):** instalar `tailwindcss`/`postcss`/`autoprefixer` compatíveis com Next 14, `class-variance-authority`/`clsx`/`tailwind-merge`/`lucide-react` + `@radix-ui/*` mínimos; `tailwind.config` com `content` cobrindo `app/**/*` + `components/**/*` e `theme.extend.colors` mapeando `var(--cor-*)` (preserva AA e `data-theme` dark); `globals.css` com `@tailwind base; @tailwind components; @tailwind utilities` + `@layer base` para tokens/foco/reduced-motion/print; `lib/utils.ts` com `cn`; `components.json` se o CLI shadcn for usado.
- **FRENTE B — shell shadcn:** `components/Header.tsx`, `Rodape.tsx`, `PularParaConteudo.tsx`, `ThemeToggle.tsx`, `CommandPalette.tsx`, `app/layout.tsx`, `app/not-found.tsx` sobre Tailwind/shadcn (Button/Input/Dialog/Command). SEO/JsonLd/skip-link/anti-flash intactos.
- **FRENTE C — componentes shadcn (dono de `components/ui/*` + `components/*` compartilhados):** `Button`, `Cards`, `Estados`, `SearchBar`/`Command`, `FormField` (`Label`/`Input`/`Textarea`/`Select`), `Data` (`Table`), `Drawer`/`Sheet`, `ShareButtons`, `ReadingProgress` + `Accordion`, `Badge`, `Chip`, `Dropdown` (`DropdownMenu`), `Modal` (`Dialog`), `Tabs`, `Tooltip`, `Toast` (`Sonner`/`Toast`), `PorQueEstouVendoIsso`, `MaisLidas`, `BlocoEditoria`, `BotaoSalvar`, `CartaoEsqueleto` — props congeladas, só visual via shadcn + Tailwind, `cn()` para variantes.
- **FRENTE D1/D2 — páginas `app/*` sobre Tailwind:** `page.tsx` (feed/rio), `noticia/*`, `comunidade/*`, `radar`, `planos`, `login`/`cadastro`/`onboarding`/`minha-conta`, `admin/*`, `autor`, `empresa`, `jornalista`, `lista-de-espera`, `paginas/[slug]`, `privacidade/*`, `recuperar/redefinir-senha`, `verificar-email` — só classes Tailwind/shadcn + tokens; zero mudança em `lib/api`/`queries`/`router`/`FormData`/`localStorage`.
- **Estudo 100%:** cada frente deve fetch cru das 5 origens (raw SKILL.md + docs `src/` quando relevante) e registrar no history o que foi incorporado (shadcn demos, 21st search/get_component, frontend-design 2-pass, command.md regras, chrome-devtools workflow).

## Áreas/arquivos esperados
- `frontend/tailwind.config.*`, `postcss.config.*`, `lib/utils.ts`, `components.json` (A)
- `frontend/app/globals.css` (A exclusivo)
- `frontend/components/*`, `frontend/components/ui/*` (B/C exclusivos por arquivo)
- `frontend/app/**/*` (D1/D2 subdividido; `lib/*`, `robots.ts`, `sitemap.ts` só leitura)
- `agentic-framework/state/run-20260915-2142-frontend-tailwind-100/design-spec-v2.md` (2-pass, paleta 6 hex, wireframes)

## Interfaces afetadas
- Build: PostCSS/Tailwind adicionados; `cn` helper como contrato visual. Nenhuma API/schema de dados.

## Critérios de aceite (técnicos, testáveis)
1. Quando `npm run build --prefix frontend` e `tsc --noEmit -p frontend/tsconfig.json`, então exit 0, 32/32 rotas.
2. Quando `grep -R "@tailwind" frontend/app/globals.css` e `cat frontend/tailwind.config.*`, então Tailwind configurado com `content` cobrindo `app`+`components` e `theme.extend.colors` mapeando `--cor-*`.
3. Quando `cat frontend/lib/utils.ts`, então `cn` exportado (`clsx`+`twMerge`).
4. Quando `grep -R "from.*shadcn\|shadcn\|radix\|class-variance" frontend/components` ou `ls frontend/components/ui`, então componentes shadcn em uso (Button/Card/Dialog/etc. com variantes via `cva` quando aplicável).
5. Quando `git diff HEAD --stat -- backend/ frontend/lib/api.ts`, então vazio; sem renames (`git diff HEAD --name-status -- frontend/app` só `M`).
6. Quando `chrome-devtools-mcp` disponível, então `test-report.md` contém screenshots/tab-order/contraste em 360/768/1024/1440 + dark/light; quando indisponível, então fallback documentado com evidência estática.
7. Quando cada arquivo do diff é auditado contra `command.md` fresco, então zero blocker/major.

## Não-objetivos
- Alterar lógica de dados/queries/mutations/auth/gating/pagamentos; mudar URLs/SEO/LGPD; `generate` sem crédito.

## Restrições técnicas
- Dependências autorizadas: `tailwindcss`/`postcss`/`autoprefixer`, `class-variance-authority`/`clsx`/`tailwind-merge`, `lucide-react`, `@radix-ui/*` mínimos, `sharp` se já usado por Next — justificar no history se adicionar outra
- Performance: só `transform`/`opacity`, `content-visibility` onde útil, skeletons espelhando cards
- A11y: `focus-visible:ring`, `prefers-reduced-motion`, `scroll-margin-top` em `[id]`

## Definição de pronto
- [ ] Critérios 1–7 implementados
- [ ] Testes passando (tester)
- [ ] Revisão aprovada (reviewer, obrigatória por nova dependência)
- [ ] Docs atualizadas (documenter)
- [ ] History coerente
