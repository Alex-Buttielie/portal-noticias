# Implementation Contract — 20260915-1956-frontend-portal-skills

## Metadados
- **run_id:** 20260915-1956-frontend-portal-skills
- **Deriva de:** task-plan.md (20260915-1956-frontend-portal-skills)
- **Versão do contrato:** 1

## O que deve ser construído
Rebuild visual completo do `frontend/` em 4 frentes paralelas com arquivos exclusivos por frente, todas seguindo `design-spec.md` (a ser produzido na análise: tokens, paleta 4–6 hex, tipos, wireframes ASCII, princípios) e a skill `frontend-portal`:

- **FRENTE A — design-system (dono exclusivo de `frontend/app/globals.css`):** reescrita organizada do CSS: tokens `--cor-*`/`--espaco-*`/`--raio-*`/`--sombra-*`/`--z-*`/tipografia preservados e estendidos só se necessário; sistema de botões, cartões editoriais (manchete, horizontal, compacto), formulários, tabelas, badges/chips, skeletons, toasts, modal/dropdown/tooltip/tabs/accordion, ticker, mais-lidas, newsletter, banner-atualização, salvos, estados vazios/erro; responsivo mobile-first 360/768/1024/1440; dark via `data-theme` + `prefers-color-scheme`; `prefers-reduced-motion`; print; `aliases legados` (`.container`, `.cartao*`, `.botao*`, `.badge*`, etc.) preservados. Nenhuma outra frente edita este arquivo.
- **FRENTE B — shell:** `components/Header.tsx`, `components/Rodape.tsx`, `components/PularParaConteudo.tsx`, `components/ThemeToggle.tsx`, `components/CommandPalette.tsx`, `app/layout.tsx`, `app/providers.tsx` (só visual/a11y; SEO, JsonLd, skip-link, script anti-flash intactos).
- **FRENTE C — componentes:** `components/ui/*` (Button, Cards, Estados, SearchBar, FormField, Data, Drawer, ShareButtons, ReadingProgress) + `components/*` compartilhados (Accordion, Badge, BannerConsentimentoCookies-só-visual, BlocoEditoria, BotaoSalvar, CartaoEsqueleto, Chip, DetalheNoticia, Dropdown, JsonLd-intocado, MaisLidas, Modal, PorQueEstouVendoIsso, Tabs, ToastProvider, Tooltip). Props/APIs públicas inalteradas.
- **FRENTE D — páginas `app/*`:** `page.tsx` (feed/rio), `noticia/`, `comunidade/`, `radar/`, `planos/`, `login/`, `cadastro/`, `onboarding/`, `minha-conta/`, `admin/*`, `autor/`, `empresa/`, `jornalista/`, `lista-de-espera/`, `paginas/`, `privacidade/*`, `recuperar-senha/`, `redefinir-senha/`, `verificar-email/`, `not-found.tsx`, `robots.ts`/`sitemap.ts` (intocados salvo visual). Só classes/estrutura visual; zero mudança em chamadas `lib/api`, `lib/queries`, roteamento e lógica.

## Áreas/arquivos esperados
- `frontend/app/globals.css` (FRENTE A, exclusiva)
- `frontend/components/*`, `frontend/components/ui/*` (FRENTES B/C, arquivos exclusivos por frente)
- `frontend/app/**/*` (FRENTE D, subdividida por rota; `lib/*`, `robots.ts`, `sitemap.ts` só leitura)
- `agentic-framework/state/run-20260915-1956-frontend-portal-skills/design-spec.md` (direção de design 2-pass da skill)

## Interfaces afetadas
- Nenhuma API ou schema de banco. Contrato visual interno: nomes de classes CSS usadas pelas páginas (documentados em `design-spec.md` § classes); props dos componentes `ui/*` congeladas.

## Critérios de aceite (técnicos, testáveis)
1. Dado o repo, quando `frontend/node_modules/.bin/tsc --noEmit -p frontend/tsconfig.json`, então exit 0, zero erros.
2. Dado o repo, quando `npm run build --prefix frontend`, então exit 0 e todas as rotas compilam.
3. Dada largura 360px, quando qualquer rota é renderizada, então sem overflow-x (checagem estática: sem `width:100vw` fora de full-bleed controlado, containers com `minmax(0,1fr)`/`min-width:0` onde há truncamento).
4. Dado `data-theme="dark"`, quando tokens escuros aplicam, então contraste AA nos pares texto/fundo principais (checagem estática dos hex).
5. Dado `prefers-reduced-motion`, quando ativo, então animações/transições desligadas (regra global presente e sem `transition: all`).
6. Dado teclado, quando navegar, então skip-link `#conteudo-principal` funcional, foco `:focus-visible` visível, menu mobile com `aria-expanded` + `Escape`, form com label/erro-inline/foco-no-erro.
7. Dado `git diff --stat`, quando comparado ao HEAD, então `backend/` e `frontend/lib/api.ts` com diff vazio e nenhuma rota renomeada.
8. Dado cada arquivo alterado, quando aplicado o checklist `web-design-guidelines`, então zero blocker/major.

## Não-objetivos
- Migrar para Tailwind/shadcn runtime ou adicionar dependências
- Alterar lógica de dados, queries, mutations, auth, gating, pagamentos, moderação
- Reescrever textos/copy além do necessário ao layout; mudar URLs, SEO, LGPD
- Editar `globals.css` fora da FRENTE A; editar arquivos fora da partição da frente

## Restrições técnicas
- **Performance:** animar só `transform`/`opacity`; skeletons espelham cards reais; lazy abaixo da dobra; sem layout reads no render
- **Segurança/privacidade:** LGPD intacta; sem novo rastreamento; `target="_blank"` sempre com `rel="noreferrer"`
- **Dependências permitidas:** nenhuma nova (package.json congelado)
- **Estilo/convenções:** skill `frontend-portal` + tokens existentes; saída de revisão em formato `arquivo:linha`; `Intl.*` p/ datas/números; `…` e aspas curvas em copy nova

## Definição de pronto (Definition of Done)
- [ ] Critérios de aceite implementados
- [ ] Testes escritos e passando (tester)
- [ ] Revisão de código aprovada, se exigida por `review-triggers.md` (reviewer)
- [ ] Documentação atualizada (documenter)
- [ ] `implementation-history.md` completo e coerente
