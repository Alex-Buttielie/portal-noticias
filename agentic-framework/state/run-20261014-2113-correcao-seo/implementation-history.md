<!--
CONTRACT: implementation-history
DONO: executor (cria e adiciona entradas) / tester, remediator, historian (adicionam entradas)
QUANDO É CRIADO: junto com a primeira ação do executor sobre o implementation-contract.md.
PARA ONDE VAI A INSTÂNCIA: agentic-framework/state/run-<run_id>/implementation-history.md
NATUREZA: append-only durante a execução — cada entrada é uma iteração, nunca se edita uma entrada anterior.
-->

# Implementation History — 20261014-2113-correcao-seo

## Iteração 1 — 2026-10-14 — executor (implementação inicial)

**O que foi feito:**

1. **Canonical global** (`frontend/app/layout.tsx`): adicionado `alternates: { canonical: "/" }` no `metadata` do root layout, combinado com o `metadataBase` já existente.
2. **Canonical por página** — adicionado `alternates.canonical` em todas as páginas indexáveis que têm `metadata`/`generateMetadata` próprio, usando o path real de cada rota:
   - Estáticas: `app/page.tsx` ("/"), `app/privacidade`, `app/contato`, `app/sobre`, `app/lista-de-espera`, `app/radar`, `app/empresa`, `app/cookies`, `app/arquivo`, `app/newsletter`, `app/ao-vivo`, `app/termos`, `app/buscar` (canonical fixo em `/buscar`, sem querystring — decisão: evitar duplicar sinal de indexação entre diferentes `?q=`), `app/editorias`.
   - Dinâmicas (`generateMetadata`): `app/categoria/[slug]` (`/categoria/${slug}`), `app/autor/[id]` (`/autor/${id}`), `app/noticia/[id]` (`/noticia/${id}`), `app/noticia/cluster/[id]` (`/noticia/cluster/${id}`), `app/noticia/item/[id]` (`/noticia/item/${id}`), `app/paginas/[slug]` (`/paginas/${slug}`).
   - **Decisão/exclusão explícita:** `app/admin/configuracoes/page.tsx` e `app/admin/layout.tsx` (metadata tipada como `any`, painel interno autenticado) ficaram de fora — não são páginas indexáveis (sem valor de SEO, atrás de autenticação), e o contrato fala de "páginas indexáveis". Se o orchestrator/reviewer discordar, é um ajuste de uma linha cada.
3. **H1 na home** (`frontend/app/page.tsx`): adicionado `<h1 className="sr-only">Capa do {SITE_NAME} — últimas notícias e destaques do dia</h1>` nos DOIS caminhos de retorno da página (feed vazio e feed normal), para garantir exatamente um H1 em qualquer resposta de `GET /`. Texto não disputa com o H2 "Destaques do dia" de `DestaquesDia.tsx`.
4. **`alt=""` → `alt={titulo}`** nos 8 pontos exatos do contrato:
   - `frontend/components/home/NewsCard.tsx:216` (variante "grade") → `entrada.titulo`
   - `frontend/components/home/NewsCard.tsx:275` (variante "lista") → `entrada.titulo`
   - `frontend/components/home/UltimasNoticias.tsx:170` → `n.titulo`
   - `frontend/components/HomeClient.tsx:269` ("Ao vivo agora") → `u.titulo`
   - `frontend/components/HomeClient.tsx:393` ("Continuar lendo") → `item.titulo`
   - `frontend/components/SecaoColunistas.tsx:111` → `c.recente.titulo`
   - `frontend/app/arquivo/page.tsx:34` → `n.titulo`
   - `frontend/app/noticia/LeituraPremium.tsx:269` → `r.titulo`
   - Confirmado por `grep -rn 'alt=""' frontend/components frontend/app` ANTES e DEPOIS da edição: só esses 8 apareceram antes, zero depois.
5. **OpenGraph (`frontend/app/layout.tsx`)** — **NÃO implementado** (ver "Notas fora do escopo" abaixo: `og:image` ficou documentado como pendência, não implementado, porque o asset não existe).
   - Confirmado que `openGraph.type: "website"` e `openGraph.locale: "pt_BR"` já estavam presentes no global — nenhuma mudança necessária para essa subparte.
6. **Caddyfile — HSTS** (`Caddyfile`, bloco `header` do site principal): adicionado `Strict-Transport-Security "max-age=31536000; includeSubDomains"`, substituindo o comentário incorreto ("HSTS já sai do Django — não duplicar") por um comentário explicando que o Django só cobre `/api/*` e as rotas de observabilidade proxiadas para `web:8000`; tudo o mais (incluindo a home) cai no `handle` catch-all para `frontend:3000`, que nunca enviava HSTS. `SECURE_HSTS_PRELOAD` não foi tocado.
7. **Caddyfile — redirect www → apex**: IMPLEMENTADO (não apenas documentado como pendência — a investigação encontrou uma forma de baixo risco). Adicionado, dentro do mesmo bloco de site único:
   ```
   @www host www.{$DOMAIN}
   redir @www https://{$DOMAIN}{uri} permanent
   ```
   Este é o padrão oficial do Caddy para "www to non-www" sem duplicar blocos de site inteiros (matcher por `host` + `redir`, que o Caddy ordena antes do `handle` catch-all independentemente de onde a diretiva aparece no arquivo). Validado via `caddy validate`/`caddy adapt` (ver evidência abaixo) nos dois cenários: produção (`DOMAIN_EXTRA=", www.portal-noticias.com"`) e dev (`DOMAIN_EXTRA` vazio — o matcher nunca casa, sem efeito).
8. **GA4**: confirmado via grep que não há `gtag(`, script de `googletagmanager.com/gtag`, nem `NEXT_PUBLIC_GA_ID` em lugar nenhum do frontend. O projeto já documenta isso explicitamente em `frontend/lib/anuncios.ts:78-96` (`HOSTS_MEDICAO`/`GA4_NAO_IMPLEMENTADO = true`, com comentário dizendo que é uma pendência de conta, não de código) — analytics first-party próprio vive em `frontend/components/AnalyticsTracker.tsx`/`frontend/lib/analytics.ts` (+ `backend/metricas/`), com gate de consentimento LGPD. Nenhuma conta GA4 criada, nenhum ID inserido — conforme não-objetivo do contrato.

**Por quê:**
Implementação do `implementation-contract.md` (run 20261014-2113-correcao-seo), que corrige lacunas de SEO on-page levantadas por dois relatórios de auditoria externos (Rank Math + leitura consolidada), preservando decisões arquiteturais já registradas (não migrar para `next/image`, não criar GA4 real).

**Arquivos tocados:**
- `frontend/app/layout.tsx`
- `frontend/app/page.tsx`
- `frontend/app/privacidade/page.tsx`
- `frontend/app/contato/page.tsx`
- `frontend/app/sobre/page.tsx`
- `frontend/app/lista-de-espera/page.tsx`
- `frontend/app/radar/page.tsx`
- `frontend/app/empresa/page.tsx`
- `frontend/app/cookies/page.tsx`
- `frontend/app/arquivo/page.tsx` (canonical + `alt`)
- `frontend/app/newsletter/page.tsx`
- `frontend/app/ao-vivo/page.tsx`
- `frontend/app/termos/page.tsx`
- `frontend/app/buscar/page.tsx`
- `frontend/app/editorias/page.tsx`
- `frontend/app/categoria/[slug]/page.tsx`
- `frontend/app/autor/[id]/page.tsx`
- `frontend/app/noticia/[id]/page.tsx`
- `frontend/app/noticia/cluster/[id]/page.tsx`
- `frontend/app/noticia/item/[id]/page.tsx`
- `frontend/app/paginas/[slug]/page.tsx`
- `frontend/components/home/NewsCard.tsx`
- `frontend/components/home/UltimasNoticias.tsx`
- `frontend/components/HomeClient.tsx`
- `frontend/components/SecaoColunistas.tsx`
- `frontend/app/noticia/LeituraPremium.tsx`
- `Caddyfile`
- `agentic-framework/state/run-20261014-2113-correcao-seo/implementation-history.md` (este arquivo)

**Comandos executados / evidência:**
```
# Confirmação de que frontend/public NUNCA existiu neste repo (asset OG referenciado não existe)
$ ls frontend/public/
ls: cannot access 'frontend/public/': No such file or directory
$ git log --all --oneline -- frontend/public
(sem saída — nunca existiu nenhum commit tocando esse diretório)
$ find . -iname "*og-padrao*"
(sem saída)
# brand/*.svg existem na raiz do repo, mas são logos (não um asset OG
# 1200x630 em raster) e não são copiados/servidos por nenhum código do
# frontend hoje (grep por "brand/" em frontend/ não retornou nada).

# grep final do alt="" (critério de aceite 3)
$ grep -rn 'alt=""' frontend/components frontend/app
(sem saída — zero ocorrências após as 8 edições)

# grep de H1 por rota (cobertura, achado 2)
$ grep -rln "<h1" frontend/app
(inclui app/page.tsx agora — antes não aparecia na lista)

# typecheck
$ npx tsc --noEmit
(sem saída — sem erros)

# lint nos arquivos tocados
$ npx eslint app/layout.tsx app/page.tsx ... (lista completa dos 25 arquivos .ts/.tsx tocados)
ESLint: No issues found

# build completo
$ npm run build
... (ECONNREFUSED 127.0.0.1:8001 esperado — build roda sem backend vivo,
     mesmo padrão P0-08 de não fabricar conteúdo; todas as 60 páginas
     geradas com sucesso)
✓ Generating static pages (60/60)
Route (app) ... / 17.4 kB ... ○/●/ƒ conforme esperado, nenhuma rota falhou.

# verificação do HTML gerado (critérios de aceite 1 e 2)
$ grep -o '<h1' .next/server/app/index.html | wc -l
1
$ grep -o '<link rel="canonical"[^>]*>' .next/server/app/index.html
<link rel="canonical" href="http://localhost:3000"/>
$ grep -o '<link rel="canonical"[^>]*>' .next/server/app/categoria/politica.html
<link rel="canonical" href="http://localhost:3000/categoria/politica"/>
$ grep -o '<link rel="canonical"[^>]*>' .next/server/app/noticia/1.html
<link rel="canonical" href="http://localhost:3000/noticia/1"/>
$ grep -o '<h1[^>]*>.\{0,80\}' .next/server/app/index.html
<h1 class="sr-only">Capa do <!-- -->Portal de Notícias<!-- --> — últimas notícias e destaques do dia

# validação do Caddyfile (achados 5 e 6) via `caddy validate`/`caddy adapt`
# em container oficial (docker run --rm -i caddy:2-alpine), substituindo
# {$DOMAIN}/{$DOMAIN_EXTRA}/{$OBSERVABILITY_METRICS_TOKEN} manualmente
# (envsubst não serve — colide com a própria sintaxe de placeholder do
# Caddy `{$VAR}` e corrompe o arquivo; usado sed com os literais exatos).

# Cenário produção (DOMAIN_EXTRA = ", www.portal-noticias.com"):
$ caddy validate --config /tmp/Caddyfile --adapter caddyfile
Valid configuration

# Inspeção das rotas adaptadas (JSON) confirma ordem correta:
#   rota 0: handler "headers" (inclui Strict-Transport-Security) — aplica a TODAS as respostas
#   rota 1: match host=www.portal-noticias.com → static_response 301 Location
#           "https://portal-noticias.com{http.request.uri}"
#   rota 16 (última): catch-all → reverse_proxy frontend:3000
# ou seja, o redirect www->apex roda ANTES do catch-all do Next.js, como esperado.

# Cenário dev (DOMAIN_EXTRA vazio):
$ caddy validate --config /tmp/Caddyfile --adapter caddyfile
Valid configuration
# (o matcher @www nunca casa nesse cenário — sem efeito, como projetado)
```

**Resultado:**
Sucesso. Todos os critérios de aceite testáveis do `implementation-contract.md` foram verificados objetivamente nesta iteração, exceto o `og:image` (item 4, parcial — ver abaixo) e a validação *em produção* do HSTS (que por definição só pode ser confirmada após deploy, conforme o próprio contrato já previa). O redirect www↔apex (achado 6), que o contrato tratava como "investigar, implementar só se de baixo risco", ACABOU SENDO IMPLEMENTADO (não ficou como pendência) — a investigação encontrou e validou uma forma de baixo risco (matcher + `redir` dentro do bloco único existente, sem reestruturar blocos de site), dentro do que o contrato permitia.

**Notas fora do escopo (se houver):**

1. **`openGraph.images` (achado 4, parcial) — NÃO implementado, documentado como pendência real.**
   `frontend/lib/site.ts` define `IMAGEM_OG_PADRAO = ${SITE_URL}/og-padrao.svg`, mas **`frontend/public/` não existe no repositório** (confirmado por `ls`, por `git log --all -- frontend/public`, e pelo próprio `Dockerfile` que faz `mkdir -p ./public` justamente "porque o projeto não tem assets estáticos em public/"). O arquivo `og-padrao.svg` nunca existiu.
   Avaliei usar um dos logos existentes em `brand/*.svg` (sugestão explícita do contrato: "ex. ícone de app em brand/") como substituto, mas decidi NÃO fazer isso por dois motivos técnicos, não por preguiça:
   - Nenhum dos arquivos em `brand/` é um asset dimensionado para preview social (1200×630 ou proporção equivalente) — são logos de marca (horizontal/empilhado, claro/escuro), não thumbnails de OG.
   - **SVG não é um formato suportado como `og:image` pelos principais consumidores** (Facebook, LinkedIn, WhatsApp exigem raster — PNG/JPG — para gerar preview; a própria documentação do Open Graph recomenda JPG/PNG). Mesmo que eu copiasse um `brand/*.svg` para dentro de um novo `frontend/public/`, o link não ficaria "quebrado" (critério de aceite 4 fala em "não ser um caminho quebrado"), mas a funcionalidade real (preview de link em redes sociais) continuaria falhando silenciosamente — mesmo resultado prático de um asset ausente, só que mascarado.
   Isso bate com a cláusula do próprio contrato: "se nada servir, documentar como pendência em vez de inventar um asset". Pendência registrada: **é necessário que alguém de design produza um asset OG raster (PNG/JPG, 1200×630) e o publique em `frontend/public/`**; depois disso, basta adicionar uma linha `images: [IMAGEM_OG_PADRAO]` em `frontend/app/layout.tsx` (o import de `IMAGEM_OG_PADRAO` de `lib/site.ts` já existe pronto para ser usado, só não foi adicionado nesta run). Isso deve ir para `follow_up` no `run-state.json`.
2. **Canonical em páginas de admin não adicionado** (`app/admin/configuracoes/page.tsx`, `app/admin/layout.tsx`) — decisão registrada acima (não são páginas indexáveis). Se o reviewer/orchestrator entender que o contrato exigia cobertura literal de "toda página com `metadata`/`generateMetadata`" sem exceção, é um ajuste trivial de duas linhas, mas preferi não expandir canonical para rotas administrativas sem sinalizar — não é uma mudança "cirúrgica" óbvia e pode ser vista como ruído.
3. **HSTS e redirect www→apex: código pronto, mas sem efeito até deploy.** Ambos foram implementados e validados estruturalmente (syntaxe/ordem de rotas via `caddy validate`/`caddy adapt`), mas, como o próprio contrato exige deixar explícito: **isso só vale como "resolvido em produção" depois de implantado e confirmado com `curl -I` contra o domínio real** (ex. confirmar header `Strict-Transport-Security` na resposta de `/` e confirmar `curl -I https://www.portal-noticias.com` devolve 301 para `https://portal-noticias.com`). Nenhum teste contra produção foi ou poderia ser feito aqui.
4. **GA4**: nenhuma ação de código necessária além da confirmação por grep (achado 7) — decisão de criar conta real continua sendo humana, fora desta run, conforme não-objetivo explícito do contrato.

---

## Iteração 2 — 2026-10-14 — tester (validação independente)

**Metodologia:** nenhuma afirmação do executor foi aceita sem reexecução. Todos os comandos abaixo foram rodados de novo por este agente, a partir do estado real do working tree (branch `fix/home-desktop-reorganizacao`), não copiados da Iteração 1.

### Escopo (critério implícito do task do orchestrator)

```
$ git status --short | head -50
 M Caddyfile
 M frontend/app/ao-vivo/page.tsx ... (26 arquivos .tsx/.ts modificados)
?? agentic-framework/state/run-20261014-2113-correcao-seo/
$ git diff --stat
 27 files changed, 71 insertions(+), 27 deletions(-)
```
Lista de arquivos tocados bate 1:1 com a seção "Áreas/arquivos esperados" do `implementation-contract.md` (layout.tsx, page.tsx, as ~19 rotas de página, os 4 componentes, `arquivo/page.tsx`, `LeituraPremium.tsx`, `Caddyfile`, este `implementation-history.md`). Nenhum arquivo fora da lista esperada foi tocado. **Veredito: passou.**

### Critério de aceite 3 — `alt=""` eliminado

```
$ grep -rn 'alt=""' frontend/components frontend/app
(sem saída, exit code 1)
```
Confirmado de forma independente: zero ocorrências. **Veredito: passou.**

### Critério de aceite 1 — exatamente um `<h1>` em `GET /`

Build de produção rodado do zero (`cd frontend && npm run build`), completou gerando 60/60 páginas estáticas (erros `ECONNREFUSED 127.0.0.1:8001` são esperados — backend Django não está rodando neste ambiente de teste; não impediu a geração das páginas).

```
$ grep -o '<h1' .next/server/app/index.html | wc -l
1
$ grep -o '<h1[^>]*>[^<]*' .next/server/app/index.html | head -3
<h1 class="sr-only">Capa do
```
Exatamente 1 `<h1>`, sr-only, não disputa com H2 "Destaques do dia". **Veredito: passou.**

### Critério de aceite 2 — canonical self-referencing em `<head>`

Verificado no HTML estático gerado pelo build para 4 rotas (home, categoria, notícia, sobre — `/buscar` é rota dinâmica `ƒ`, sem HTML estático gerado no build; canonical dela foi confirmado por leitura de código-fonte, ver abaixo):

```
$ grep -o '<link rel="canonical"[^>]*>' .next/server/app/index.html
<link rel="canonical" href="http://localhost:3000"/>
$ grep -o '<link rel="canonical"[^>]*>' .next/server/app/categoria/politica.html
<link rel="canonical" href="http://localhost:3000/categoria/politica"/>
$ grep -o '<link rel="canonical"[^>]*>' .next/server/app/noticia/1.html
<link rel="canonical" href="http://localhost:3000/noticia/1"/>
$ grep -o '<link rel="canonical"[^>]*>' .next/server/app/sobre.html
<link rel="canonical" href="http://localhost:3000/sobre"/>
```
Todos auto-referentes (apontam para a própria URL da página, não um valor genérico repetido), URL absoluta via `NEXT_PUBLIC_SITE_URL=http://localhost:3000` (`.env.example`) + `metadataBase`. `/buscar`:
```
$ grep -n "alternates" frontend/app/buscar/page.tsx
export const metadata: Metadata = { ..., alternates: { canonical: "/buscar" } };
```
Cobertura adicional — todas as páginas com `metadata`/`generateMetadata` (exceto as 2 de `/admin`, deliberadamente excluídas e documentadas pelo executor; confirmado que `/admin/*` não consta em `frontend/app/sitemap.ts`, logo não é página indexável) têm `alternates`:
```
$ for f in $(grep -rln "generateMetadata\|export const metadata" app); do echo "$f: $(grep -c alternates "$f")"; done
(22 arquivos com contagem >=1; apenas app/admin/layout.tsx e app/admin/configuracoes/page.tsx com 0 — esperado)
```
**Veredito: passou.**

### Critério de aceite 4 — `og:image` existente e não quebrado

```
$ grep -o '<meta property="og:[^>]*>' .next/server/app/index.html
<meta property="og:title" .../>
<meta property="og:description" .../>
<meta property="og:url" .../>
<meta property="og:site_name" .../>
<meta property="og:locale" content="pt_BR"/>
<meta property="og:type" content="website"/>
```
Não há **nenhuma** tag `og:image` no `<head>` da home. O critério de aceite 4 do contrato ("o `<head>` da home... contém `og:image` apontando para um asset existente") **não é satisfeito literalmente** — não é um caminho quebrado, é ausência total. Isto é consistente com o que o executor documentou (decisão deliberada de não implementar por falta de asset raster real, já que SVG não é aceito como `og:image` pelos principais consumidores, e não quis mascarar o problema usando um `brand/*.svg` incorreto). **Veredito: falhou** (quanto à letra do critério de aceite), mas é uma falha conhecida, documentada e com causa raiz legítima (ausência de asset de design, fora do escopo de código) — não é um bug introduzido pela implementação, é um gap de pré-condição (ausência de asset) que o próprio contrato previa como possível ("se nada servir, documentar como pendência"). Fica como pendência de design, não como defeito de código a corrigir pelo remediator.

### Critério de aceite 5 — Caddyfile com `Strict-Transport-Security`

```
$ git diff Caddyfile
 (diff de 24 inserções, 1 deleção — escopo limitado ao bloco `header` +
  bloco de redirect www->apex; nada mais no arquivo foi tocado)
```
Leitura do arquivo confirma `Strict-Transport-Security "max-age=31536000; includeSubDomains"` dentro do bloco `header` existente do site principal, e `SECURE_HSTS_PRELOAD` não foi tocado (não está nem mencionado no Caddyfile — correto, é config do Django).

Validação de sintaxe com Docker real (não apenas leitura):
```
$ docker run --rm -e DOMAIN="portal-noticias.com" -e DOMAIN_EXTRA=", www.portal-noticias.com" \
    -e OBSERVABILITY_METRICS_TOKEN="dummy-token" \
    -v "$(pwd)/Caddyfile:/etc/caddy/Caddyfile:ro" \
    caddy:2-alpine caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile
Valid configuration
```
(Nota: a primeira tentativa, sem passar `-e DOMAIN=...`/`-e DOMAIN_EXTRA=...`/`-e OBSERVABILITY_METRICS_TOKEN=...`, falhou com `unrecognized global option: header` porque os placeholders `{$DOMAIN}{$DOMAIN_EXTRA}` não resolvem para um endereço de site válido sem as env vars presentes no ambiente do `caddy`; não é um bug do Caddyfile, é uma particularidade de como testar fora do Compose. Corrigido passando as env vars reais ao container.)

Inspeção do JSON adaptado (`caddy adapt`) confirma estrutura real das rotas dentro do bloco do site:
- rota 0 (`headers`, sem `match` — aplica a toda resposta): inclui `Strict-Transport-Security` no `response.set`.
- rota 1 (`static_response`, `match: host=www.portal-noticias.com`): `status_code: 301`, `Location: https://portal-noticias.com{http.request.uri}`.
- rota 16 (última, `match: none`, catch-all): `reverse_proxy` → `frontend:3000`.

Ou seja, o redirect www→apex (rota 1) roda **antes** do catch-all do Next.js (rota 16), confirmando a ordem correta de forma estrutural (não apenas por inspeção visual do arquivo-fonte). Repetido também com `DOMAIN_EXTRA=""` (cenário dev) — `Valid configuration`, sem erro. **Veredito: passou** (quanto ao item 5 do contrato — header presente). O item 6 (redirect www→apex, que não é um dos 7 critérios de aceite numerados, mas faz parte de "O que deve ser construído" seção 6) também passou nesta validação estrutural adicional.

**Ressalva explícita (já prevista no próprio contrato, item 5):** esta validação é de sintaxe/estrutura de configuração, não de produção real. Confirmar com `curl -I` contra o domínio real após deploy (HSTS na resposta de `/`, 301 de `www.` para apex) continua pendente e não é testável por este agente.

### Critério de aceite 6 — build sem novos erros de tipo/lint

```
$ cd frontend && npx tsc --noEmit
TypeScript: No errors found
EXIT:0

$ npx eslint <26 arquivos tocados, listados via git diff --name-only>
ESLint: No issues found
EXIT:0

$ npm run build
... (ECONNREFUSED 127.0.0.1:8001 esperado, backend não está de pé)
✓ Generating static pages (60/60)
EXIT:0
```
Build completo, typecheck limpo, lint limpo nos 26 arquivos `.tsx`/`.ts` tocados (Caddyfile não é alvo de tsc/eslint). **Veredito: passou.**

### Critério de aceite 7 — regressão visual em browser (home, categoria, notícia)

**Não testável por este agente.** As ferramentas disponíveis (`Read`, `Write`, `Edit`, `Bash`, `Glob`, `Grep`) não incluem um browser/renderizador visual para capturar screenshot ou interagir com a página e inspecionar o console do navegador. A verificação feita aqui (grep/inspeção de HTML gerado, tsc, eslint, build) cobre estrutura e ausência de erro de build, mas não cobre "regressão visual perceptível" nem "erro novo no console do browser" como o critério exige literalmente. **Fica explicitamente para verificação manual/browser por outra camada** (humano ou um agente com ferramenta de browser/Playwright), antes de considerar a run 100% fechada quanto a este item específico.

### Resumo por critério de aceite (1–7, conforme numeração do `implementation-contract.md`)

| # | Critério | Veredito |
|---|----------|----------|
| 1 | Exatamente um `<h1>` em `GET /` | **passou** |
| 2 | Canonical self-referencing em head (home/categoria/notícia) | **passou** |
| 3 | Nenhum dos 8 pontos renderiza `alt=""` | **passou** |
| 4 | `og:image` existente, não quebrado | **falhou** (ausente — pendência de design documentada, não bug de código) |
| 5 | Caddyfile com `Strict-Transport-Security` no bloco `header` | **passou** |
| 6 | Build sem novos erros de tipo/lint | **passou** |
| 7 | Sem regressão visual/erro de console no browser | **não testável por este agente** (ferramentas sem browser; fica para verificação manual) |

**Veredito objetivo final: `failed`** — por rigor ao critério de aceite 4, que é descumprido na letra do contrato (ausência total de `og:image`, não apenas um placeholder). A causa raiz é uma lacuna de pré-condição (asset de design inexistente) corretamente identificada e documentada pelo executor como não-implementável sem inventar um asset (o que o próprio contrato proíbe), não um bug a corrigir por remediação de código — cabe ao orchestrator decidir se aceita esse item como pendência fora da run (ajustando a Definição de Pronto) ou se devolve para o executor buscar um asset alternativo/aprovação para gerar um. Todos os demais critérios testáveis (1, 2, 3, 5, 6) passaram com evidência real de comando executado nesta iteração; o critério 7 permanece não testável pelas ferramentas deste agente.

---

## Iteração 3 — 2026-10-14 — orchestrator (validação visual do critério de aceite 7)

**O que foi feito:**
Nenhum agente deste framework tem ferramenta de browser (`tester` e `reviewer` são `Read/Write/Edit/Bash/Glob/Grep` apenas). O critério de aceite 7 ("sem regressão visual perceptível nem erro novo no console") ficou explicitamente não testável pela Iteração 2. O orchestrator (esta sessão, que tem acesso a um browser pane) abriu o preview local do frontend (`npm run dev`, servido em `http://localhost:3000`, já em execução por outra sessão no mesmo host — reaproveitado via `navigate`, refletindo o working tree atual com HMR) e inspecionou duas rotas: a home (`/`) e uma página estática com conteúdo real (`/sobre`).

**Por quê:**
Cobrir o único critério de aceite do contrato sem veredito de nenhum agente (tester marcou "não testável"), antes de considerar a Definição de Pronto satisfeita.

**Arquivos tocados:**
Nenhum (verificação somente-leitura no browser).

**Comandos executados / evidência:**
```
# Home (http://localhost:3000) — console
[error] Failed to load resource: 404 (x2) → GET /api/gating/status/, POST /api/metricas/eventos/
(Esperado: backend Django não está rodando neste ambiente; mesmas chamadas
 que já existiam antes desta run, não relacionadas às mudanças de SEO.)

# Home — JS no document real renderizado
> document.querySelectorAll('h1').length
1
> document.querySelector('h1').textContent
"Capa do Portal de Notícias — últimas notícias e destaques do dia"
> document.querySelector('link[rel="canonical"]').href
"http://localhost:3000/"
> document.querySelector('meta[property="og:image"]')
null   // confirma o gap já documentado — og:image de fato ausente também no runtime real do browser, não só no HTML estático do build

# read_page (acessibilidade) confirma layout normal: header, navegação,
# busca, estado "Nenhuma notícia disponível agora" (fallback P0-08 sem
# backend — não é uma regressão, é o comportamento esperado sem dados),
# rodapé com links institucionais/categorias/legal intactos.

# /sobre — navegação + JS
> document.querySelectorAll('h1').length
1
> document.querySelector('h1').textContent
"Sobre"
> document.querySelector('link[rel="canonical"]').href
"http://localhost:3000/sobre"
# get_page_text confirma conteúdo da página ("Sobre", "Leitura confortável",
# "Em destaque", "Rastreabilidade") renderizado normalmente.
# Console: mesmos 404 de API (esperados, sem backend), nenhum erro novo.
```

**Resultado:**
Sucesso. Critério de aceite 7 considerado satisfeito para o que é observável sem backend ativo: H1 único e correto, canonical correto, sem regressão visual perceptível, sem erro de console novo além dos 404 de API já esperados (pré-existentes, não introduzidos por esta run). `og:image` ausente também confirmado no DOM real do browser, consistente com o que a Iteração 2 já havia encontrado no HTML estático — não é uma descoberta nova, é confirmação cruzada.

**Notas fora do escopo (se houver):**
Esta verificação não cobriu uma página de notícia/categoria com dados reais (o backend não está rodando neste ambiente, então essas rotas mostram o mesmo fallback "sem dados" da home) nem um teste em produção. Suficiente para o escopo desta run (detectar regressão introduzida pelas mudanças de SEO), não substitui um smoke test pós-deploy com backend real.

---
