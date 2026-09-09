# Task Plan — 20260909-1200-frontend-rebuild

## Metadados
- **run_id:** 20260909-1200-frontend-rebuild
- **Data de abertura:** 2026-09-09
- **Solicitado por:** usuario
- **Spec de origem:** BRD_portal_noticias_versao_1.docx (fluxos preservados, só visual/layout refeito)

## Objetivo
Jogar fora todo o CSS/componentes visuais atuais do `frontend/` e reconstruir um frontend moderno, bonito e totalmente responsivo, mantendo 100% dos fluxos, rotas e contratos com o backend Django, e publicar em `develop` para testes em DEV.

## Escopo
### Dentro do escopo
- Novo design system em `frontend/app/globals.css` (tokens, tipografia, cores, espaçamentos, sombras, dark mode, breakpoints 360/768/1024/1440)
- Rebuild de `Header.tsx`, `Rodape.tsx`, `components/ui/*` (Button, Cards, Estados, SearchBar, FormField, Data, Drawer, ShareButtons, ReadingProgress), `BlocoEditoria.tsx`, `MaisLidas.tsx`, `DetalheNoticia.tsx` e layouts de `app/page.tsx` + páginas internas (login, cadastro, noticia, comunidade, radar, planos, admin, autor, etc. via estilos globais + ajustes pontuais)
- Responsividade real: mobile-first, grid fluido, header com menu mobile acessível, tabelas com scroll, formulários e feed sem overflow horizontal
- Acessibilidade base: skip-link, foco visível, `prefers-reduced-motion`, contraste AA, alvos de toque >= 40px
- Preservar `lib/api.ts`, `lib/queries.ts`, `lib/auth-context.tsx`, rotas e SEO (`layout.tsx` metadata, sitemap, robots, rss, JsonLd)
- Validar com `tsc --noEmit` + `next build` + `next lint` e subir para `develop`

### Fora do escopo (explicitamente)
- Mudanças no `backend/` (API, modelos, serializers)
- Mudança de rotas/URLs ou de contratos de dados com o backend
- Troca de framework (continua Next.js 14 + React 18) ou adição de dependência pesada (Tailwind, MUI, etc.)
- Deploy em HOMOLOG/PROD (só DEV via push em develop)

## Suposições assumidas
- Manter stack CSS puro com variáveis CSS (sem Tailwind) para não quebrar CI e evitar nova dependência — motivo: pedido é visual/responsivo, não troca de stack
- Preservar nomes de classes consumidas por testes/E2E quando existirem; quando renomear, manter compatibilidade — motivo: evitar regressão silenciosa
- Dark mode via `data-theme` + `prefers-color-scheme` como já existe — motivo: já funciona e é esperado

## Restrições
- Não quebrar nenhuma chamada em `lib/api.ts`; nenhum campo de serializer muda
- `tsc --noEmit` + `next build` devem passar (CI exige)
- LGPD/cookies, SEO etema precisam continuar funcionando
- Branch alvo: `develop` (push dispara Deploy DEV 3101/5101)

## Divisão de trabalho
| Etapa | Agente responsável | Entrada esperada | Saída esperada |
|---|---|---|---|
| 1 | executor (subagentes: design-architect + ui-implementer + responsive-specialist) | implementation-contract.md | código + implementation-history.md |
| 2 | tester (subagente: qa-validator) | implementation-contract.md | veredito passed/failed/blocked |
| 3 | reviewer (se `review-triggers.md` aplicar) | diff do executor | code-review-contract.md |
| 4 | remediator (se necessário) | code-review-contract.md | correções + revalidação |
| 5 | documenter | implementation-history.md | documentation-update.md + docs atualizadas |
| 6 | historian | todos os artefatos acima | report.md + entrada em HISTORY.md |

Agentes especializados criados nesta run:
- `frontend-design-architect` — define linguagem visual, tokens e grid responsivo
- `frontend-ui-executor` — implementa CSS + componentes + páginas
- `frontend-responsive-a11y` — garante breakpoints, toque, contraste, foco, motion
- `frontend-qa-tester` — valida build, tipos, lint e critérios de aceite
- `frontend-reviewer` — revisa diff grande (>300 linhas => review obrigatória)

## Critérios de aceite (nível de negócio/produto)
1. Home, notícia, login/cadastro, comunidade, radar, planos e admin exibem novo layout moderno e coeso
2. Em 360px, 768px, 1024px e 1440px não há overflow horizontal, sobreposição ou texto ilegível; header/menu, grade do feed e sidebar se adaptam
3. Todos os fluxos existentes continuam funcionando (feed, busca, salvar, newsletter, auth, navegação)
4. `tsc`, `lint` e `next build` passam sem erro
5. Código empurrado para `develop` com CI verde para testes em DEV

## Riscos identificados
| Risco | Impacto | Mitigação |
|---|---|---|
| Rebuild quebrar classe usada por teste/E2E | alto | grep por classes antes de renomear; manter aliases legados |
| Diff >300 linhas exigir revisão longa | médio | revisão dedicada por subagente reviewer |
| Regressão visual em dark mode | médio | tokens espelhados light/dark + teste manual nos dois temas |
| Push em develop quebrar DEV | alto | validar build local antes do push; push só com CI verde local |

## Dependências
- Backend Django inalterado; `NEXT_PUBLIC_API_BASE_URL` de DEV inalterado
- VPS/CI inalterados (workflows existentes)
