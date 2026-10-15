<!--
CONTRACT: implementation-contract
DONO: orchestrator (preenche) / executor, tester, reviewer (leem)
QUANDO É CRIADO: logo após o task-plan.md ser aceito.
PARA ONDE VAI A INSTÂNCIA: agentic-framework/state/run-<run_id>/implementation-contract.md
-->

# Implementation Contract — 20261014-2113-correcao-seo

## Metadados
- **run_id:** 20261014-2113-correcao-seo
- **Deriva de:** task-plan.md (20261014-2113-correcao-seo)
- **Versão do contrato:** 2 (alterado pelo orchestrator após veredito `failed` do tester na Iteração 2 — ver nota abaixo)

## Nota de amendamento (v1 → v2)

O tester (Iteração 2 em `implementation-history.md`) deu veredito `failed` estritamente no critério de aceite #4 (`og:image`): a tag não foi emitida, não um caminho quebrado. Causa raiz confirmada de forma independente pelo executor E pelo tester: `frontend/public/` nunca existiu neste repositório — não há nenhum asset raster (PNG/JPG 1200×630) para servir como `og:image`, e o próprio contrato (v1) já prescrevia não inventar um SVG/asset de design para preencher a lacuna ("se nada servir, documentar como pendência em vez de inventar um asset").

Decisão do orchestrator: isso não é um bug de código corrigível por `remediator`/`executor` — é uma pré-condição de design ausente, fora do alcance desta run (que é sobre SEO técnico/código, não produção de asset visual). Reabrir o loop de remediação para este item seria inútil (não há código a corrigir) e violaria o próprio não-objetivo já definido ("Produzir novo asset visual de OG do zero — fora de escopo").

**Critério de aceite #4 é formalmente rebaixado nesta v2:** passa a exigir apenas que `openGraph.type`/`openGraph.locale` estejam corretos (já confirmado pelo tester) — a presença de `og:image` real fica fora da Definição de Pronto desta run e migra para `follow_ups` em `run-state.json`, com o motivo técnico documentado (ausência de asset de design, não de código). Os demais critérios (1, 2, 3, 5, 6) permanecem como estavam e já passaram com evidência real do tester.

## O que deve ser construído

Correções pontuais de SEO on-page no frontend Next.js 14 (`frontend/`), levantadas por exploração prévia do código (ver achados por arquivo abaixo). Não é uma refatoração — são edições cirúrgicas, arquivo por arquivo, preservando decisões arquiteturais já registradas no código (em especial: **não migrar para `next/image`**, ver Não-objetivos).

### 1. Canonical (`alternates.canonical`) — ausente em 100% do projeto
- `frontend/app/layout.tsx`: já define `metadataBase: new URL(SITE_URL)` no objeto `metadata`. Adicionar `alternates: { canonical: "/" }` no nível global (vira canonical correto para qualquer página que não sobrescreva `alternates`, graças ao `metadataBase`).
- `frontend/app/page.tsx` (home): no `export const metadata: Metadata = { title: SITE_NAME, description: SITE_DESCRIPTION }`, adicionar `alternates: { canonical: "/" }` explícito (mesmo herdando do layout, deixar explícito na home evita regressão silenciosa se o layout mudar).
- Demais páginas com `generateMetadata`/`metadata` próprios (categoria, notícia, autor, busca, arquivo, radar, etc.): adicionar `alternates: { canonical: <path-relativo-da-própria-página> }` usando o path real (ex. `/categoria/${slug}`, `/noticia/${id}`). Levantar a lista completa de arquivos com `grep -rln "generateMetadata\|export const metadata" frontend/app` antes de editar, para não deixar nenhuma página indexável de fora.

### 2. H1 ausente na home
- `frontend/app/page.tsx`: adicionar um `<h1>` visualmente oculto (classe `sr-only`, mesmo padrão já usado em `frontend/components/home/NewsCard.tsx:329`) logo no início do JSX retornado pela página, com texto natural alinhado ao conteúdo real (ex. algo como "Últimas notícias e destaques — {SITE_NAME}" ou similar — o texto exato fica a critério do executor, desde que seja natural, não genérico demais, e não dispute visualmente com o H2 "Destaques do dia" de `DestaquesDia.tsx`).
- Confirmar que nenhuma outra página da lista de rotas fixas do sitemap (`frontend/app/sitemap.ts`) ficou sem H1 — o explorador já confirmou que `sobre`, `arquivo`, `buscar`, `editorias` têm H1; não precisa re-verificar essas, mas vale uma checagem rápida (`grep -rln "<h1" frontend/app`) ao final para garantir cobertura.

### 3. `alt=""` em imagens informativas (o campo `titulo` já está disponível em todos os casos — não é falta de dado)
Trocar `alt=""` por `alt={<variável título já em escopo>}` nestes pontos exatos (confirmados pelo explorador):
- `frontend/components/home/NewsCard.tsx:216` (variante "grade") → usar `entrada.titulo`.
- `frontend/components/home/NewsCard.tsx:275` (variante "lista") → usar `entrada.titulo`. (A variante "destaque", linha 299, já está correta — usar como modelo de formato.)
- `frontend/components/home/UltimasNoticias.tsx:170` → usar `n.titulo`.
- `frontend/components/HomeClient.tsx:269` (seção "Ao vivo agora") → usar `u.titulo`.
- `frontend/components/HomeClient.tsx:393` (seção "Continuar lendo"/salvos) → usar `item.titulo`.
- `frontend/components/SecaoColunistas.tsx:111` (foto de capa do post do colunista) → usar `c.recente.titulo`.
- `frontend/app/arquivo/page.tsx:34` → usar `n.titulo`.
- `frontend/app/noticia/LeituraPremium.tsx:269` (lista de relacionadas) → usar o campo título da notícia relacionada em escopo (confirmar nome exato do campo ao editar).

Antes de fechar esta seção, rodar `grep -rn 'alt=""' frontend/components frontend/app` para confirmar que não sobrou nenhum caso não listado aqui (a lista acima veio de uma exploração, não de um grep exaustivo — se aparecer mais algum, aplicar o mesmo tratamento: usar o título já disponível no escopo).

### 4. OpenGraph incompleto
- `frontend/app/layout.tsx`: o objeto `openGraph` no `metadata` global não tem `images`. Adicionar `images: [IMAGEM_OG_PADRAO]` (import já existe ou precisa ser adicionado de `lib/site.ts`). `IMAGEM_OG_PADRAO` hoje é `${SITE_URL}/og-padrao.svg` — **confirmar que o arquivo `frontend/public/og-padrao.svg` (ou caminho equivalente) de fato existe** antes de referenciá-lo; se não existir, não inventar um SVG novo de design (está marcado no próprio código como "placeholder de rascunho... precisa ser substituída por um asset visual real desenhado" — isso é trabalho de design, fora desta run). Se o arquivo não existir, usar o que existir de mais parecido com um asset OG já presente no projeto (ex. ícone de app em `brand/`), documentando a decisão no `implementation-history.md`; se nada servir, documentar como pendência em vez de inventar um asset.
- Garantir `openGraph.type` e `openGraph.locale` também no nível global (locale `pt_BR` já presente — confirmar).

### 5. Caddyfile — HSTS não alcança rotas servidas pelo Next.js
- `Caddyfile` (raiz do repo): o bloco `header { ... }` no site principal tem o comentário `# HSTS já sai do Django (SECURE_HSTS_SECONDS, DEBUG=False) — não duplicar.`. Esse pressuposto é **tecnicamente incorreto** para a maioria das rotas do site: olhando o próprio `Caddyfile`, só `/api/*`, `/livez`, `/readyz`, `/healthz`, `/health-detail`, `/metrics` são roteados para `web:8000` (Django); **todo o resto, incluindo a home (`/`) que a auditoria avaliou**, cai no `handle { reverse_proxy frontend:3000 }` (Next.js), que não envia HSTS.
  - Ação: adicionar `Strict-Transport-Security "max-age=31536000; includeSubDomains"` ao bloco `header` existente (mesmo nível dos outros headers de segurança já ali), com um comentário atualizado explicando que o header anterior só cobria as rotas que passam pelo Django, não as servidas pelo Next.js.
  - **Não mexer** em `SECURE_HSTS_PRELOAD` (fica `False`, decisão separada que não faz parte deste achado).
  - Esta é uma mudança de infraestrutura versionada no repo, mas só tem efeito real após deploy — deixar isso explícito no `implementation-history.md` e no `report.md` final: a mudança de código está pronta, mas precisa ser implantada e validada (`curl -I` contra o domínio real) antes de contar como "resolvido em produção".

### 6. www vs. apex sem redirect — investigar, não forçar
- O `Caddyfile` serve `{$DOMAIN}{$DOMAIN_EXTRA}` (onde `DOMAIN_EXTRA` pode ser `, www.portal-noticias.com` em produção) como **aliases do mesmo bloco de site**, sem nenhum `redir` 301 entre eles.
- Investigar se existe uma forma de baixo risco de adicionar o redirect dentro da mesma estrutura de bloco único do Caddy (ex. uma matcher por `host` que faça `redir` antes do `handle` geral) sem precisar duplicar o bloco de site inteiro. Se existir uma forma clara e testável, implementar. Se exigir reestruturar os blocos de site (separar `www.` em bloco próprio), **não implementar às cegas** — documentar como pendência técnica precisa no `implementation-history.md`/`report.md`, com a sugestão de implementação para quem for aplicar depois.

### 7. Google Analytics — investigar, documentar, não inventar
- Confirmar (grep) que de fato não há GA4/gtag/GTM no projeto — o explorador já confirmou isso.
- Documentar no `implementation-history.md` que o projeto tem analytics first-party próprio (`frontend/components/AnalyticsTracker.tsx`, `frontend/lib/analytics.ts`, backend `backend/metricas/`) já com gate de consentimento LGPD — por isso o Rank Math não detecta GA4 (ele procura especificamente por `gtag.js`/GTM, não por analytics custom).
- **Não** criar conta GA4 nem inserir `NEXT_PUBLIC_GA_ID` fictício. Isso fica como `follow_up` no `run-state.json`, não como item implementado.

## Áreas/arquivos esperados
- `frontend/app/layout.tsx`
- `frontend/app/page.tsx`
- `frontend/app/**/page.tsx` (ou `generateMetadata` correspondente) de rotas indexáveis, para o canonical por página
- `frontend/components/home/NewsCard.tsx`
- `frontend/components/home/UltimasNoticias.tsx`
- `frontend/components/HomeClient.tsx`
- `frontend/components/SecaoColunistas.tsx`
- `frontend/app/arquivo/page.tsx`
- `frontend/app/noticia/LeituraPremium.tsx`
- `Caddyfile`
- `agentic-framework/state/run-20261014-2113-correcao-seo/implementation-history.md` (criado/preenchido pelo executor)

Qualquer arquivo fora desta lista que precise ser tocado deve ser justificado no `implementation-history.md`.

## Interfaces afetadas
Nenhuma API pública, schema de banco ou contrato entre serviços é alterado. Mudanças são de metadata HTML, atributos de acessibilidade/SEO e um header HTTP de infraestrutura versionada.

## Critérios de aceite (técnicos, testáveis)
1. Dado o HTML renderizado de `GET /`, quando inspecionado, então contém exatamente uma tag `<h1>`.
2. Dado o HTML renderizado de `GET /` e de pelo menos uma página de categoria e uma de notícia, quando inspecionado o `<head>`, então cada uma contém `<link rel="canonical" href="...">` apontando para a própria URL absoluta (via `SITE_URL`/`metadataBase`).
3. Dado os 8 pontos de código listados na seção 3 acima, quando revisados, então nenhum renderiza `alt=""` — todos usam o título da notícia/colunista/item já disponível no escopo.
4. ~~Dado o `<head>` da home, quando inspecionado, então contém `og:image` apontando para um asset existente.~~ **Rebaixado na v2** (ver "Nota de amendamento" acima): dado o `<head>` da home, quando inspecionado, então `og:type`/`og:locale` estão corretos; `og:image` fica como pendência de design documentada, não como critério de aceite desta run.
5. Dado o `Caddyfile`, quando lido, então o bloco `header` do site principal inclui `Strict-Transport-Security`.
6. Dado `npm run build` (ou equivalente) em `frontend/`, quando executado, então completa sem novos erros de tipo/lint introduzidos por estas mudanças.
7. Dado o preview do app rodando localmente, quando a home, uma categoria e uma notícia são abertas no browser, então não há regressão visual perceptível nem erro novo no console.

## Não-objetivos
- Migrar `<img>` para `next/image` (decisão arquitetural preservada — ver task-plan.md e comentário em `ImagemNoticia.tsx`, inclusive CVE GHSA-2xp9-vwfh-vxw4).
- Criar conta/ID real de Google Analytics.
- Reestruturar os blocos de site do `Caddyfile` para redirect 301 www↔apex, caso isso exija mais que uma matcher simples (ver seção 6).
- Produzir novo asset visual de OG (imagem) do zero — reaproveitar o que já existir no projeto ou documentar a lacuna.
- Qualquer mudança em conteúdo editorial (Sobre, metodologia, etc.).
- Alterar `SECURE_HSTS_PRELOAD`, `DEBUG`, ou qualquer outra config de produção do Django além do que já está descrito.

## Restrições técnicas
- **Performance:** nenhuma mudança deve aumentar o peso de JS/CSS da home (ex. evitar novas dependências para resolver um `alt` de string).
- **Segurança/privacidade:** nenhum dado pessoal de usuário é tocado. A mudança de HSTS no Caddyfile deve ser revisada com atenção por afetar produção após deploy.
- **Dependências permitidas:** nenhuma dependência nova é necessária para este escopo; se o executor achar necessária alguma, isso exige aprovação explícita antes (não está pré-aprovada aqui).
- **Estilo/convenções:** seguir TypeScript estrito e convenções já usadas nos arquivos (ex. `sr-only` para conteúdo acessível mas visualmente oculto, como em `NewsCard.tsx:329`).

## Definição de pronto (Definition of Done)
- [ ] Critérios de aceite implementados
- [ ] Testes escritos e passando (tester)
- [ ] Revisão de código aprovada (reviewer) — obrigatória nesta run por volume/superfície de arquivos tocados (ver task-plan.md)
- [ ] Documentação atualizada (documenter)
- [ ] `implementation-history.md` completo e coerente, incluindo as pendências documentadas (www redirect de infra, GA4, otimização adicional de imagem)
