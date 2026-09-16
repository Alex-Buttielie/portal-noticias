# Task Plan — 20260915-1956-frontend-portal-skills

## Metadados
- **run_id:** 20260915-1956-frontend-portal-skills
- **Data de abertura:** 2026-09-15
- **Solicitado por:** Alex (humano)
- **Spec de origem:** skill própria `.claude/skills/frontend-portal/SKILL.md` (consolida shadcn-ui-mcp-server, 21st/magic-mcp, frontend-design, web-design-guidelines, chrome-devtools-mcp) + precedente revertido `git show a1d37d8:...report.md` (run 20260909-1200, revert `2d8063c`)

## Objetivo
Reconstruir todo o visual do `frontend/` (Next.js 14) com identidade distintiva de portal de notícias, componentes acessíveis no padrão shadcn/21st portados aos tokens do projeto e conformidade com o checklist web-design-guidelines — mantendo 100% das rotas, fluxos e do contrato com o backend Django.

## Escopo
### Dentro do escopo
- Reescrita do design system em `frontend/app/globals.css` (tokens, tipografia, dark mode, reduced-motion, responsivo 360/768/1024/1440, print)
- Rebuild do shell: `Header`, `Rodape`, `layout.tsx` (SEO/LGPD/skip-link/anti-flash preservados)
- Rebuild de `frontend/components/*` e `frontend/components/ui/*` (Button, Cards, Estados, SearchBar, FormField, Data, Drawer, ShareButtons, ReadingProgress + Accordion/Badge/Chip/Dropdown/Tabs/Tooltip/Modal/Toast)
- Rebuild visual das 26 rotas em `frontend/app/*` sem mudar lógica de dados
- Verificação: `tsc --noEmit` + `next build` + checklist web-design-guidelines por arquivo

### Fora do escopo (explicitamente)
- `backend/` (diff deve ser vazio)
- `frontend/lib/api.ts` e contratos de dados com o Django
- Mudança de URLs/rotas, SEO (`sitemap`, `rss.xml`, `JsonLd`), fluxo LGPD/cookies
- Novas features de produto; só rebuild visual

## Suposições assumidas
- **Stack mantida sem Tailwind runtime** — motivo: pedido não especificou migração; introduzir Tailwind+Radix em 26 rotas multiplica o risco de um segundo revert; as skills entram como direção de design + checklist + catálogo portado aos tokens CSS. Reversível em run futura.
- **Identidade: evolução editorial da atual** (serifa nos títulos, rio + sidebar) em vez de ruptura total — motivo: revert anterior sinaliza apego ao layout atual; ruptura total sem brief seria chute. Reversível via design-spec.
- **Validação de browser real em modo fallback** (build + checagem estática) — motivo: `chrome-devtools-mcp` não configurado neste ambiente; registrar ressalva no test-report.

## Restrições
- Manter `frontend/package.json` sem novas dependências (qualquer exceção exige aprovação e revisão obrigatória por `review-triggers.md`)
- LGPD, direitos autorais (link à fonte original), acessibilidade AA, `prefers-reduced-motion`, dark mode sem flash
- Diff esperado >300 linhas → revisão obrigatória

## Divisão de trabalho
| Etapa | Agente responsável | Entrada esperada | Saída esperada |
|---|---|---|---|
| 1 | executor (4 frentes Task-general paralelas) | implementation-contract.md + design-spec.md | código + implementation-history.md |
| 2 | tester | implementation-contract.md | test-report.md (passed/failed) |
| 3 | reviewer (obrigatório) | diff do executor | code-review-contract.md |
| 4 | remediator (se necessário) | code-review-contract.md | correções + revalidação |
| 5 | documenter | implementation-history.md | documentation-update.md + docs atualizadas |
| 6 | historian | todos os artefatos acima | report.md + entrada em HISTORY.md |

## Critérios de aceite (nível de negócio/produto)
1. Todas as rotas existentes renderizam com a nova identidade, sem fluxo quebrado (login, cadastro, onboarding, feed, notícia, comunidade, radar, planos, minha-conta, admin, autor, empresa, privacidade, lista-de-espera, recuperar/redefinir-senha, verificar-email)
2. Site usável e sem overflow em 360/768/1024/1440px, light + dark, teclado (skip-link, foco visível) e `prefers-reduced-motion`
3. `tsc --noEmit` e `next build` com exit 0
4. Zero findings blocker/major no checklist web-design-guidelines; revisão com veredito approve/approve_with_comments
5. `backend/` e `frontend/lib/api.ts` sem diff; nenhuma rota renomeada

## Riscos identificados
| Risco | Impacto | Mitigação |
|---|---|---|
| Segundo revert (como em 20260909-1200) | alto | Preservar layout/UX atual como evolução, aliases de classes legadas, nada de ruptura sem evidência |
| Conflito de escrita entre frentes paralelas | alto | Partição exclusiva de arquivos por frente; `globals.css` com dono único |
| Regressão de acessibilidade/LGPD/SEO | médio | Checklist por arquivo + tester dedicado + reviewer com foco nesses eixos |
| Estouro de contexto (26 rotas) | médio | Frentes paralelas + design-spec compartilhado; páginas seguem padrão, sem reinventar por rota |

## Dependências
- Decisão humana pendente (não bloqueante, registrada como suposição): migração futura p/ Tailwind+shadcn runtime; validação visual em browser real e push p/ develop após fechamento
