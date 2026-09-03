<!--
CONTRACT: implementation-contract
DONO: orchestrator (preenche) / executor, tester, reviewer (leem)
QUANDO É CRIADO: logo após o task-plan.md ser aceito.
PARA ONDE VAI A INSTÂNCIA: agentic-framework/state/run-<run_id>/implementation-contract.md
-->

# Implementation Contract — 20260903-1134-seo-lgpd-design-system

## Metadados
- **run_id:** 20260903-1134-seo-lgpd-design-system
- **Deriva de:** task-plan.md (20260903-1134-seo-lgpd-design-system)
- **Versão do contrato:** 1

## O que deve ser construído

### A. SEO técnico + dados estruturados
- Next.js Metadata API (`generateMetadata`) nas rotas de artigo (`frontend/app/noticia/item/[...]`), autor (`frontend/app/autor/[id]`) e home, gerando `<title>`, `<meta description>`, Open Graph (`og:title`, `og:description`, `og:image`, `og:type=article`) e Twitter Card.
- JSON-LD injetado via `<script type="application/ld+json">`: `NewsArticle`/`Article` na página de artigo, `Person` na página de autor, `Organization` na home/layout raiz, `BreadcrumbList` em páginas com navegação hierárquica (artigo, editoria), `ImageObject` embutido no `NewsArticle.image`.
- `frontend/app/sitemap.ts` (sitemap dinâmico nativo do Next.js) listando notícias publicadas + páginas estáticas; `frontend/app/robots.ts`.
- Feed RSS: endpoint backend (`catalogo_noticias`) ou route handler Next.js servindo XML RSS 2.0 das últimas N notícias publicadas.
- `<link rel="canonical">` em todas as páginas de conteúdo.

### B. Privacidade / LGPD
- Componente `frontend/components/BannerConsentimentoCookies.tsx`: aparece para visitantes sem escolha registrada, oferece "Aceitar todos", "Recusar não essenciais" e "Gerenciar preferências" (categorias: essenciais — sempre ativos, analytics, personalização/marketing).
- Persistência da escolha: `localStorage` para visitante anônimo; se o usuário estiver autenticado, persistir também no backend via novo endpoint em `identidade` (ou app mais apropriado após inspeção) passando por `services.py`.
- Nenhum script/cookie de analytics ou personalização não essencial deve ser carregado antes do consentimento (gate condicional no código que os inicializa).
- Página `frontend/app/privacidade/preferencias-cookies/page.tsx` para revisitar/alterar a escolha a qualquer momento, com link no rodapé.
- Página ou seção de política de privacidade referenciando LGPD (rascunho, sinalizado como tal no próprio texto).

### C. Rate limiting
- Configurar DRF throttling (`DEFAULT_THROTTLE_CLASSES`/`DEFAULT_THROTTLE_RATES` em `backend/config/settings.py`) com uma classe `AnonRateThrottle` conservadora para endpoints públicos de escrita (cadastro em `identidade`, criação de post em `comunidade`, lista de espera em `landing`). Confirmar em `backend/config/settings.py` que não há throttling configurado antes de assumir que é greenfield.

### D. Design system
- `frontend/app/globals.css`: consolidar tokens já existentes (cores de tema claro/escuro, já presentes) e adicionar os que faltarem — espaçamento (escala), tipografia (escala + line-height), raio de borda, sombra, z-index — todos como CSS custom properties documentadas com comentário curto de uso.
- Componentes novos em `frontend/components/`: `Badge.tsx`, `Chip.tsx`, `Tooltip.tsx`, `Dropdown.tsx`, `Modal.tsx`, `Tabs.tsx`, `Accordion.tsx`. Cada um: usa os tokens (nenhuma cor/espaçamento literal fora dos tokens), suporta estado `disabled`/`loading` onde fizer sentido, é acessível por teclado (foco visível, `Escape` fecha Modal/Dropdown, `role`/`aria-*` corretos).

## Áreas/arquivos esperados
- `frontend/app/sitemap.ts`, `frontend/app/robots.ts` (novos)
- `frontend/app/noticia/**`, `frontend/app/autor/[id]/**`, `frontend/app/layout.tsx`, `frontend/app/page.tsx` (metadata + JSON-LD)
- `frontend/components/BannerConsentimentoCookies.tsx`, `frontend/components/Badge.tsx`, `Chip.tsx`, `Tooltip.tsx`, `Dropdown.tsx`, `Modal.tsx`, `Tabs.tsx`, `Accordion.tsx` (novos)
- `frontend/app/privacidade/preferencias-cookies/page.tsx` (novo)
- `frontend/app/globals.css` (extensão dos tokens existentes)
- `backend/config/settings.py` (throttling)
- `backend/identidade/` (endpoint + service de preferências de cookies, se usuário autenticado)
- `backend/catalogo_noticias/` (endpoint RSS, se implementado no backend em vez de route handler Next.js)

## Interfaces afetadas
- Novo(s) endpoint(s) REST: preferências de cookies do usuário autenticado (GET/PUT) e, se aplicável, feed RSS.
- Nenhuma migração deve remover ou renomear campo existente — apenas adição.

## Critérios de aceite (técnicos, testáveis)
1. Dado um artigo publicado, quando a página é renderizada, então o HTML contém `<script type="application/ld+json">` com `"@type": "NewsArticle"` incluindo `headline`, `datePublished`, `author`, `image`.
2. Dado `GET /sitemap.xml`, quando a request é feita, então a resposta é XML válido e contém a URL de ao menos uma notícia publicada existente no banco de teste.
3. Dado um visitante sem cookie de consentimento prévio, quando a home carrega, então o banner de consentimento é exibido e nenhum cookie de categoria "analytics"/"personalização" é gravado até uma escolha ser feita.
4. Dado um visitante que clicou "Recusar não essenciais", quando ele navega para outra página, então o banner não reaparece e nenhum cookie não essencial é gravado.
5. Dado mais de N requisições anônimas ao endpoint de cadastro/lista de espera em um intervalo curto, quando o limite configurado é excedido, então a API responde HTTP 429.
6. Dado o componente `Modal`, quando aberto e o usuário pressiona `Escape` ou clica fora, então ele fecha e o foco retorna ao elemento que o abriu.
7. Dado qualquer um dos 7 componentes novos, quando inspecionado, então nenhuma cor ou valor de espaçamento está hardcoded fora dos tokens definidos em `globals.css`.

## Não-objetivos
- Não implementar login social nesta run.
- Não implementar o pipeline de coleta/IA (radar/crawlers) nesta run.
- Não adicionar biblioteca de terceiros de UI (ex: Radix, MUI) — componentes são hand-written, consistente com o restante do projeto.
- Não escrever a versão final/jurídica da política de privacidade — apenas um rascunho funcional e sinalizado como tal.
- Não implementar geolocalização real para "personalização por localização" (isso fica para run de personalização) — esta run só prepara os tokens/componentes que ela vai usar.

## Restrições técnicas
- **Performance:** JSON-LD e metadata não podem degradar o SSR existente (gerar server-side, sem novo round-trip de rede além do já necessário para renderizar a página).
- **Segurança/privacidade:** LGPD — nenhum cookie não essencial antes de consentimento explícito; dado de preferência de cookies de usuário autenticado passa por `services.py` do app responsável (DDD).
- **Dependências permitidas:** nenhuma nova dependência de terceiros sem justificar aqui antes — se o executor identificar necessidade real (ex: geração de XML), preferir solução nativa do Next.js/stdlib do Python antes de propor pacote novo, e registrar a decisão em `implementation-history.md`.
- **Estilo/convenções:** seguir o padrão já estabelecido em `frontend/components/ThemeToggle.tsx`/`CartaoEsqueleto.tsx` (CSS puro + variáveis, sem Tailwind/UI kit).

## Definição de pronto (Definition of Done)
- [ ] Critérios de aceite implementados
- [ ] Testes escritos e passando (tester)
- [ ] Revisão de código aprovada (reviewer — gatilho: dado pessoal/privacidade LGPD)
- [ ] Documentação atualizada (documenter)
- [ ] `implementation-history.md` completo e coerente
