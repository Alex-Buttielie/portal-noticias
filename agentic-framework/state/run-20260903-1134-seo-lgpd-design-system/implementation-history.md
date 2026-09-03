# Implementation History — 20260903-1134-seo-lgpd-design-system

## Iteração 1 — 2026-09-03 — executor (implementação inicial)

**O que foi feito:**

Escopo A (SEO técnico + dados estruturados):
- `frontend/lib/site.ts` (novo): constantes de identidade do site (`SITE_NAME`, `SITE_URL`, `SITE_DESCRIPTION`, `IMAGEM_OG_PADRAO`).
- `frontend/lib/schema.ts` (novo): construtores de JSON-LD (`organizationJsonLd`, `breadcrumbListJsonLd`, `imageObjectJsonLd`, `newsArticleJsonLd`, `personJsonLd`).
- `frontend/components/JsonLd.tsx` (novo): server component que renderiza `<script type="application/ld+json">` com escaping de `</script>`.
- `frontend/app/layout.tsx`: `metadataBase`, `title.template`, `openGraph`/`twitter` default, `alternates.canonical="/"` + `alternates.types["application/rss+xml"]`, injeta `JsonLd(organizationJsonLd())` no `<body>` (aplica a toda página, inclusive a home — a home usa `page.tsx` "use client", que não pode exportar `metadata`/JSON-LD próprio).
- `frontend/app/noticia/item/[id]/page.tsx` e `frontend/app/noticia/cluster/[id]/page.tsx`: viraram Server Components assíncronos com `generateMetadata` (title, description, canonical, OG `type=article`, Twitter Card) + JSON-LD `NewsArticle` e `BreadcrumbList` renderizados server-side. O corpo visível continua delegado ao `DetalheNoticia` client component pré-existente (comportamento client-side inalterado).
- `frontend/app/autor/[id]/page.tsx`: convertido em Server Component com `generateMetadata` (Person) + JSON-LD `Person`. Conteúdo interativo (seguir/deixar de seguir, lista de publicações) extraído para `frontend/app/autor/[id]/PerfilAutorConteudo.tsx` (Client Component) — mesmo padrão já usado no projeto em `VerificarEmailConteudo.tsx`/`RedefinirSenhaConteudo.tsx`, porque `generateMetadata` não pode ser exportado por um Client Component.
- `frontend/app/sitemap.ts` (novo): sitemap dinâmico nativo do Next.js, combina páginas estáticas públicas + notícias publicadas (via `/api/feed/?page_size=100`), com fallback gracioso (lista vazia) se o backend estiver indisponível.
- `frontend/app/robots.ts` (novo): libera conteúdo editorial público, bloqueia rotas de conta/sessão/admin.
- `frontend/app/rss.xml/route.ts` (novo): feed RSS 2.0 gerado via template string nativo (sem biblioteca de terceiros — decisão registrada abaixo), consumindo `/api/feed/`.
- `frontend/lib/api.ts`: exportado `API_BASE_URL` (antes privado) para reuso em `sitemap.ts`/`rss.xml/route.ts`.
- `frontend/.env.local` / `.env.local.example`: nova variável `NEXT_PUBLIC_SITE_URL`.
- `frontend/public/og-padrao.svg` (novo): imagem Open Graph/Twitter Card padrão (RASCUNHO, ver nota de limitação abaixo).

Escopo B (Privacidade/LGPD):
- `frontend/lib/cookie-consent.ts` (novo): categorias essenciais (sempre ativa)/analytics/personalização; persistência em `localStorage`; `permiteCategoria()` nega por padrão sem resposta registrada (bloqueio real antes de consentimento); evento customizado para reatividade entre componentes; sincronização best-effort com o backend quando autenticado.
- `frontend/components/BannerConsentimentoCookies.tsx` (novo): aparece para visitante sem escolha registrada; "Aceitar todos" / "Recusar não essenciais" / "Gerenciar preferências" (painel com toggle por categoria, essenciais sempre ativa e não editável); `Escape` fecha o painel de gerenciamento.
- `frontend/app/privacidade/preferencias-cookies/page.tsx` + `PreferenciasCookiesConteudo.tsx` (novos): página persistente para revisitar/alterar a escolha a qualquer momento.
- `frontend/app/privacidade/politica/page.tsx` (novo): rascunho funcional de política de privacidade referenciando a LGPD, com aviso explícito de rascunho não revisado juridicamente no topo da própria página.
- `frontend/components/Rodape.tsx` (novo): rodapé global com link para política de privacidade e preferências de cookies (e RSS); adicionado ao `layout.tsx`. (Nota: em edição concorrente de outra sessão/run neste mesmo repositório, o rodapé ganhou também links para `/paginas/termos-de-uso` e `/paginas/politica-editorial` — fora do escopo desta run, não revertido, ver "Notas fora do escopo".)
- Backend `identidade/` — **lacuna de backend encontrada e corrigida nesta run**: não existia nenhum campo/endpoint para persistir preferência de cookies de usuário autenticado.
  - `identidade/models.py`: novos campos `User.preferencias_cookies` (JSONField) e `User.preferencias_cookies_atualizado_em` (DateTimeField) — só adição, nenhum campo removido/renomeado.
  - `identidade/migrations/0002_user_preferencias_cookies_and_more.py` (gerada via `makemigrations`).
  - `identidade/services.py` (novo arquivo — não existia service layer neste app antes): `atualizar_preferencias_cookies(user, categorias)` — único ponto de mutação para esta funcionalidade (DDD).
  - `identidade/serializers.py`: `PreferenciasCookiesSerializer`.
  - `identidade/views.py`: `PreferenciasCookiesView` (GET/PUT, `IsAuthenticated`), mutação delegada a `services.atualizar_preferencias_cookies` (view não escreve direto no model).
  - `identidade/urls.py`: `path("preferencias-cookies/", ...)` → `GET/PUT /api/preferencias-cookies/`.
  - `frontend/lib/api.ts`: `obterPreferenciasCookies`, `atualizarPreferenciasCookies`.

Escopo C (Rate limiting):
- Confirmado por leitura direta de `backend/config/settings.py` (antes das mudanças): `REST_FRAMEWORK` não tinha `DEFAULT_THROTTLE_CLASSES`/`DEFAULT_THROTTLE_RATES` — greenfield, não havia nada para preservar/migrar.
- `backend/config/throttling.py` (novo): `EscritaPublicaAnonThrottle(AnonRateThrottle)`, `scope="escrita_publica"`.
- `backend/config/settings.py`: `REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"] = {"escrita_publica": <env THROTTLE_ESCRITA_PUBLICA_RATE, default "20/min">}`. Decisão de NÃO configurar `DEFAULT_THROTTLE_CLASSES` global (evita throttlar leituras públicas como `feed/`, fora do escopo desta run).
- `identidade/views.py` (`CadastroView`) e `landing/views.py` (`ListaEsperaView`): `throttle_classes = [EscritaPublicaAnonThrottle]` (view só tem POST).
- `comunidade/views.py` (`PublicacoesListCreateView`): `get_throttles()` sobrescrito para aplicar o throttle só em POST (GET é a listagem pública, não deve ser limitada por esta regra).

Escopo D (Design system):
- `frontend/app/globals.css`: tokens adicionados — espaçamento (`--espaco-7`, `--espaco-8`), `--raio-completo`, `--sombra-3`, escala tipográfica (`--fonte-tamanho-*`, `--fonte-peso-*`, `--linha-altura-*`), escala de z-index nomeada por papel (`--z-cabecalho`, `--z-painel-flutuante`, `--z-banner`, `--z-modal-fundo`, `--z-modal`, `--z-toast`, `--z-cookies`, `--z-conteudo-elevado`). Números mágicos pré-existentes (`z-index: 40/30/20/1000`, `border-radius: 999px`) foram trocados pelas variáveis correspondentes nos seletores já existentes (`.cabecalho`, `.explicacao-ia-painel`, `.banner-atualizacao`, `.toast-container`, `.pular-para-conteudo`, `.botao-tema`, `.selo-premium`, `.selo-free`, `.explicacao-ia-gatilho`, `.banner-atualizacao button`, `.botao-salvar`).
- 7 componentes novos em `frontend/components/`: `Badge.tsx`, `Chip.tsx`, `Tooltip.tsx`, `Dropdown.tsx`, `Modal.tsx`, `Tabs.tsx`, `Accordion.tsx` — todos usam só os tokens de `globals.css` (nenhuma cor/espaçamento literal), acessíveis por teclado:
  - `Modal`: `Escape`/clique fora fecham; foco preso dentro enquanto aberto (Tab/Shift+Tab); foco retorna ao elemento que abriu (capturado automaticamente via `document.activeElement`); `carregando` desabilita fechamento.
  - `Dropdown`: `aria-haspopup`/`aria-expanded`, `Escape` fecha e devolve foco ao gatilho, setas navegam entre itens, item `disabled` suportado, `carregando` mostra placeholder.
  - `Tabs`: padrão WAI-ARIA tabs com roving tabindex (setas/Home/End), aba `disabled` suportada.
  - `Accordion`: cabeçalho é `<button aria-expanded>` nativo, item `disabled` suportado, modo `permitirMultiplos`.
  - `Chip`: `disabled`, seleção (`aria-pressed`) e remoção como controles irmãos (não aninha `<button>` dentro de `<button>`).
  - `Tooltip`: aparece em hover E foco (não só mouse), `Escape` fecha.
  - `Badge`: rótulo não interativo, variantes cobrem os estados visuais (sem `disabled`/`loading` — não interativo, "onde fizer sentido" não se aplica).

**Por quê:**
Ver `implementation-contract.md` desta run — base transversal (SEO/LGPD/design system) que runs futuras do backlog vão consumir.

**Arquivos tocados:** (lista não exaustiva de exemplos representativos; ver diff completo do working tree)
- Backend: `backend/config/throttling.py` (novo), `backend/config/settings.py`, `backend/identidade/{models,services(novo),serializers,views,urls}.py`, `backend/identidade/migrations/0002_user_preferencias_cookies_and_more.py` (novo), `backend/comunidade/views.py`, `backend/landing/views.py`.
- Frontend: `frontend/lib/{site,schema,cookie-consent}.ts` (novos), `frontend/lib/api.ts`, `frontend/components/{JsonLd,BannerConsentimentoCookies,Rodape,Badge,Chip,Tooltip,Dropdown,Modal,Tabs,Accordion}.tsx` (novos), `frontend/app/layout.tsx`, `frontend/app/{sitemap.ts,robots.ts}` (novos), `frontend/app/rss.xml/route.ts` (novo), `frontend/app/noticia/item/[id]/page.tsx`, `frontend/app/noticia/cluster/[id]/page.tsx`, `frontend/app/autor/[id]/page.tsx` + `PerfilAutorConteudo.tsx` (novo), `frontend/app/privacidade/preferencias-cookies/{page.tsx,PreferenciasCookiesConteudo.tsx}` (novos), `frontend/app/privacidade/politica/page.tsx` (novo), `frontend/app/globals.css`, `frontend/public/og-padrao.svg` (novo), `frontend/.env.local`, `frontend/.env.local.example`.

**Comandos executados / evidência:**
```
# Backend
cd backend && DJANGO_DB_ENGINE=sqlite3 python manage.py makemigrations identidade
  → Migrations for 'identidade': 0002_user_preferencias_cookies_and_more.py (2 campos adicionados)
cd backend && DJANGO_DB_ENGINE=sqlite3 python manage.py check
  → System check identified no issues (0 silenced).
cd backend && DJANGO_DB_ENGINE=sqlite3 python manage.py makemigrations --check --dry-run
  → No changes detected
cd backend && DJANGO_DB_ENGINE=sqlite3 python -m pytest identidade comunidade landing -q
  → 54 passed (primeira rodada, antes de edições concorrentes de outra sessão nestes mesmos apps)
  → 57 passed in 212.13s (segunda rodada, após as edições concorrentes de terceiros — 3 testes a mais,
    adicionados por essa outra sessão; nenhuma falha, sem regressão causada pelas mudanças desta run)

# Frontend
cd frontend && npx tsc --noEmit
  → sem erros (exit code 0)
cd frontend && npx next build (em cópia isolada do projeto, ver nota abaixo)
  → build de produção concluído com sucesso, 25 rotas geradas, incluindo /sitemap.xml, /robots.txt,
    /rss.xml, /privacidade/politica, /privacidade/preferencias-cookies, /autor/[id],
    /noticia/item/[id], /noticia/cluster/[id]
Verificação funcional (next start na build isolada, backend real rodando em SQLite local):
  GET /sitemap.xml → 200, XML válido, lista notícias publicadas reais do banco (ex.: /noticia/item/672)
  GET /robots.txt → 200, referencia Sitemap
  GET /rss.xml → 200, RSS 2.0 válido com itens reais
  GET /noticia/item/672 → 200, HTML contém <script type="application/ld+json"> com
    "@type":"NewsArticle" incluindo headline, datePublished, author, image; também Organization e
    BreadcrumbList; <link rel="canonical">; <meta property="og:title">
  GET /autor/1 → 200, HTML contém "@type":"Person"
  GET / → 200, contém <footer class="rodape">
```

**Nota sobre o ambiente de build:** havia um servidor `next dev` de OUTRA sessão de chat rodando
simultaneamente na mesma pasta `frontend/` (avisado pelo próprio ambiente) — `next build` diretamente em
`frontend/.next` colidia com esse processo (erros aleatórios `PageNotFoundError: Cannot find module for
page: /_document`, `/comunidade` etc., diferentes a cada tentativa — sintoma clássico de dois processos
escrevendo no mesmo `.next` ao mesmo tempo). Para obter um resultado de build confiável, o código-fonte
(sem `node_modules`/`.next`) foi copiado para um diretório temporário isolado, com `node_modules` linkado
via junction do Windows (sem reinstalar dependências), e o build/`next start` rodou lá. O resultado
reportado acima é de um build real, não estimado — só isolado do processo concorrente para não ser
corrompido por ele. O código em `frontend/` no repositório é o mesmo testado (a cópia era só para a
execução do build, não uma versão alternativa do código).

**Resultado:** sucesso — critérios de aceite técnicos 1, 2, 3 (parcial — banner testado só client-side
por inspeção de código, não com browser automation), 4 (N/A — não há teste automatizado de rate limit
nesta iteração, ver notas), 6 e 7 verificados por leitura de código + build/tsc. Critério 5 (429 após N
requisições) implementado mas não exercitado nesta iteração (throttle depende de cache em memória por
processo — validação de fato é responsabilidade do tester). Backend: `check` e `makemigrations --check`
limpos; suíte de testes dos 3 apps tocados rodada com sucesso duas vezes (54 passed antes, 57 passed
depois de edições concorrentes de terceiros nesses mesmos arquivos) — sem regressão.

**Notas fora do escopo (se houver):**
- **Limitação de dados conhecida e documentada (não corrigida nesta run — fora do escopo "não
  multimídia"):** `catalogo_noticias.models.NewsItem`/`NewsCluster` não têm campo de imagem própria nem
  autor jornalista individual — são conteúdo agregado de fontes externas, não peças autorais. Por isso
  `NewsArticle.image`/`og:image` usam uma imagem padrão (`frontend/public/og-padrao.svg`, RASCUNHO — SVG,
  não uma peça de design finalizada; idealmente seria um PNG/JPG desenhado) e `NewsArticle.author` é a
  `Organization` do portal (não uma `Person`), com o(s) nome(s) da(s) fonte(s) original(is) preservados em
  `citation`. Uma run futura de "multimídia"/enriquecimento editorial deveria adicionar um campo de imagem
  real ao modelo.
- **Texto de política de privacidade** é rascunho não revisado juridicamente, sinalizado como tal na
  própria página — consistente com o Não-objetivo do contrato.
- **DetalheNoticia (corpo visível de artigo) continua sendo renderizado client-side** (fetch em
  `useEffect`, comportamento pré-existente, não alterado nesta run) — só a metadata/JSON-LD foi movida
  para o servidor. Uma run futura de performance/SSR completo poderia migrar o corpo visível também para
  renderização server-side.
- **Rodapé (`Rodape.tsx`) foi editado por outra sessão/run concorrente** durante esta execução, adicionando
  links para `/paginas/termos-de-uso` e `/paginas/politica-editorial` (rota `/paginas/[slug]` de outra run,
  fora do escopo deste contrato) — mantido como está, não revertido (ver instrução operacional do ambiente:
  mudança concorrente deliberada de outro processo não deve ser desfeita unilateralmente).
- **Rate limiting não foi validado com um teste real de 21+ requisições** nesta iteração — a implementação
  (throttle configurado, `scope="escrita_publica"`, `AnonRateThrottle` só afeta requisições não
  autenticadas) foi verificada por leitura de código e `manage.py check`, mas não por um teste de carga.
  Recomenda-se ao `tester` escrever esse teste explicitamente.
- **`identidade/views.py` tem outras views pré-existentes (ex.: `OnboardingSerializer.update`,
  `VerificarEmailView`) que escrevem diretamente no model sem passar por `services.py`** — não é uma
  violação introduzida por esta run (o app não tinha `services.py` antes desta run), mas fica registrado
  como observação para uma futura run de "débito técnico"/DDD cleanup; não foi corrigido aqui por estar
  fora do escopo deste contrato (que só pede DDD para a NOVA funcionalidade de preferências de cookies).

---

## Iteração 2 — 2026-09-03 — tester (verificação)

**Escopo desta verificação:** critérios de aceite 3, 4, 5, 6, 7 do
`implementation-contract.md` (critérios 1 e 2 — JSON-LD/sitemap — já
verificados por execução real pelo executor na iteração 1 e não repetidos
aqui, conforme instrução do orquestrador).

### Critério 5 — Rate limiting (429 após exceder o limite)

**Achado prévio importante:** o ambiente local não tem Redis rodando
(confirmado testando a conexão diretamente — `Error 10061 connecting to
localhost:6379`). O cache "default" do projeto (`config/settings.py`) usa
Redis com `IGNORE_EXCEPTIONS=True` quando `DJANGO_CACHE_BACKEND` não é
`locmem` — ou seja, **sem essa variável de ambiente, o throttle nunca
dispara de verdade** (toda tentativa de leitura/escrita no cache falha
silenciosamente e é tratada como "sem histórico", liberando a requisição
sempre). A suíte "57 passed" da iteração 1 rodou sem `DJANGO_CACHE_BACKEND`
definida, então não exercitou o throttling de fato, só validou que o código
não quebra. **`.github/workflows/ci.yml` já define
`DJANGO_CACHE_BACKEND: locmem` para todo o job `backend-tests`** — ou seja,
em CI o throttle já está (e sempre esteve, desde que a rate foi configurada)
genuinamente ativo para toda a suíte, não só para um teste isolado.

**Teste escrito:** `backend/config/tests/test_throttling.py` (novo, 3
testes) — local escolhido por ser o app onde `config.throttling` vive e por
cobrir um comportamento compartilhado por 3 apps (`identidade`, `landing`,
`comunidade`), seguindo a convenção já usada no projeto de `tests/` como
subpacote com `test_*.py`. Usa a fixture `settings` do pytest-django (não
`@override_settings` de classe, que só funciona em `unittest.TestCase`) para
trocar `CACHES` para `LocMemCache` **isolado por teste** (limpo antes/depois
via `cache.clear()`), evitando dois problemas: (a) rodar sem cache
funcional (falso positivo, ver acima) e (b) vazar contagem de throttle de
um teste para outro dentro da mesma suíte.

- `TestAC5RateLimitingListaEspera` — faz `limite` (lido dinamicamente de
  `DEFAULT_THROTTLE_RATES["escrita_publica"]`, hoje 20) requisições
  anônimas a `POST /api/landing/lista-espera/` com e-mails distintos,
  confirma que nenhuma delas foi barrada, depois confirma que a
  requisição `limite+1` retorna `429` com header `Retry-After`, e que o
  registro correspondente **não** foi persistido no banco (throttle bloqueia
  antes do handler rodar).
- `TestAC5RateLimitingCadastro` — mesmo padrão para `POST /api/auth/cadastro/`
  (o outro endpoint citado explicitamente no critério 5 — "cadastro/lista
  de espera").
- `TestAC5RateLimitingNaoAfetaUsuarioAutenticado` — esgota o balde anônimo
  em `lista-espera/` (confirma 429), depois confirma que um usuário
  autenticado com token continua conseguindo bater em
  `POST /api/comunidade/publicacoes/` (mesmo throttle, `EscritaPublicaAnonThrottle`)
  sem ser bloqueado — comprova que `AnonRateThrottle` de fato usa uma chave
  de cache diferente para requisições autenticadas, como documentado em
  `config/throttling.py`.

**Comando executado / evidência:**
```
cd backend && DJANGO_DB_ENGINE=sqlite3 .venv/Scripts/python.exe -m pytest config/tests/test_throttling.py -q
  → 3 passed in 19.11s
```

**Veredito critério 5: PASSOU** — comportamento de 429 real, exercitado com
requisições de verdade contra um cache funcional, não apenas leitura de
código.

### Critérios 3 e 4 — Banner de cookies (LGPD)

**Confirmação prévia:** `frontend/package.json` não tem nenhuma dependência
de teste (`jest`, `@testing-library/*`, `vitest`) nem script `"test"` — não
há framework de teste de componente/unitário configurado no frontend deste
projeto. Adicionar um agora seria uma mudança de escopo maior que a desta
verificação (nova dependência de build/CI não pedida pelo contrato). Por
isso, esta verificação foi feita por **inspeção de código**, não por teste
automatizado executado — documentado explicitamente aqui, conforme pedido.

Verificação (`frontend/lib/cookie-consent.ts`,
`frontend/components/BannerConsentimentoCookies.tsx`,
`frontend/app/layout.tsx`):

- `permiteCategoria()` retorna `false` por padrão quando não há
  `ConsentimentoCookies` salvo em `localStorage` (nega por padrão) —
  implementa corretamente o gate exigido pelo critério 3.
- Busquei em todo `frontend/` (exceto `node_modules`) por qualquer inicializador
  de analytics/tracking (`gtag`, `dataLayer`, `analytics`, `_ga`) ou uso de
  `document.cookie` — **não existe nenhum script desse tipo implementado no
  projeto hoje** (os únicos resultados são o próprio módulo
  `cookie-consent.ts`, `BannerConsentimentoCookies.tsx`,
  `PreferenciasCookiesConteudo.tsx` e `lib/api.ts`, todos referenciando a
  palavra "analytics" só como nome de categoria/campo, não como script
  real). Isso confirma a nota do executor ("hoje não há nenhum desses
  scripts implementados ainda").
  **Ressalva importante:** por não existir NENHUM script de
  analytics/personalização ainda, os critérios 3 e 4 são satisfeitos hoje de
  forma "vazia" (não há nada que possa violar o gate) — a verificação real
  que pude fazer é da **corretude do mecanismo de bloqueio em si**
  (`permiteCategoria`, ponto único que qualquer script futuro deve
  consultar), não uma prova empírica de que um cookie de analytics real não
  é gravado (não há como testar empiricamente a ausência de um efeito que
  não existe no código). Isso não é uma falha, mas é uma limitação de
  cobertura que deve ser reavaliada quando um script de analytics real for
  adicionado em run futura.
- `BannerConsentimentoCookies` é montado uma única vez em `app/layout.tsx`
  (nível raiz, dentro de `AuthProvider`, fora de qualquer rota) — permanece
  montado durante navegação client-side entre páginas. Sua visibilidade é
  `!consentimento.consentimentoRespondido()`, que lê `localStorage`
  (persistente entre navegações e recarregamentos completos de página, ao
  contrário de `sessionStorage`).
  `recusarNaoEssenciais()` grava `{analytics: false, personalizacao: false}`
  em `localStorage` — depois disso, `consentimentoRespondido()` passa a
  retornar `true` em qualquer página/recarregamento subsequente, então o
  banner não reaparece. Confirma o critério 4.

**Veredito critérios 3 e 4: PASSOU (por inspeção de código, sem framework de
teste frontend disponível)** — mecanismo de gate/persistência correto; sem
cobertura empírica de "nenhum cookie real é gravado" por não existir ainda
nenhum script real de analytics no projeto (ressalva documentada acima, não
é bloqueio).

### Critério 6 — Modal (Escape/clique fora fecham, foco retorna)

**Confirmação prévia:** mesma ausência de framework de teste de componente
React já documentada acima — verificação por inspeção de código de
`frontend/components/Modal.tsx`.

- `Escape`: handler de `keydown` chama `aoFechar()` quando `aberto &&
  !carregando` e a tecla é `Escape`.
- Clique fora: `onClick` no elemento `.modal-fundo` (overlay) só dispara
  `aoFechar()` quando `evento.target === evento.currentTarget` (ou seja,
  clique no overlay, não propagado de dentro do `.modal`) e `!carregando`.
- Foco retorna ao elemento que abriu: `elementoQueAbriuRef` captura
  `document.activeElement` no instante em que `aberto` vira `true`; o
  `useEffect` com dependência `[aberto]` executa
  `elementoQueAbriuRef.current?.focus()` sempre que `aberto` vira `false`
  (via corpo do próprio efeito, ramo `else`) — como o componente é
  controlado (`aberto`/`aoFechar` vêm do pai), isso cobre Escape, clique
  fora e fechamento programático de forma uniforme.
- Foco preso dentro do modal enquanto aberto: handler de `Tab`/`Shift+Tab`
  calcula primeiro/último elemento focável dentro de `modalRef` e força o
  wrap-around.
- `carregando` desabilita fechamento por Escape, clique fora e pelo botão
  "✕" (`disabled={carregando}`).

**Veredito critério 6: PASSOU (por inspeção de código)** — implementação
consistente com o padrão WAI-ARIA de diálogo modal controlado.

### Critério 7 — Nenhuma cor/espaçamento hardcoded fora dos tokens (7 componentes novos)

**Confirmação prévia:** mesma ausência de framework de teste de componente —
verificação por inspeção de código dos 7 arquivos `.tsx`
(`Badge`, `Chip`, `Tooltip`, `Dropdown`, `Modal`, `Tabs`, `Accordion`) e das
respectivas regras CSS em `frontend/app/globals.css`.

**Resultado: FALHOU — este critério, lido literalmente ("nenhuma cor ou
valor de espaçamento hardcoded fora dos tokens"), não é atendido.** Encontrei
valores hardcoded reais (não triviais) nas regras CSS que estilizam os 7
componentes novos:

- **Cor hardcoded (mais relevante):** `.modal-fundo { background: rgba(0, 0,
  0, 0.5); ... }` (`frontend/app/globals.css`, bloco do Modal) — o projeto
  já tem um token dedicado exatamente para esse padrão,
  `--cor-sombra` (RGB puro, usado como `rgba(var(--cor-sombra), opacidade)`
  em `--sombra-1/2/3`), que **muda entre tema claro (`15, 23, 42`) e escuro
  (`0, 0, 0`)** — mas o overlay do Modal usa `rgba(0, 0, 0, 0.5)` fixo, sem
  passar pelo token, ficando fora do sistema de tema.
- **Valores de espaçamento/tamanho fora da escala de tokens
  (`--espaco-1`..`--espaco-8` = 0.25rem..4rem, `--fonte-tamanho-*`)**, todos
  em `globals.css`, blocos dos 7 componentes: `.badge` padding `0.15rem`;
  `.chip` padding `0.3rem`; `.chip-remover` `font-size: 0.85em`;
  `.tooltip-balao` padding `0.3rem 0.6rem`, `max-width: 240px`,
  `bottom: calc(100% + 6px)`; `.tooltip-balao--baixo` `top: calc(100% + 6px)`;
  `.dropdown-menu` `min-width: 200px`, `gap: 2px`, `top: calc(100% + 6px)`;
  `.dropdown-item` padding `0.5rem 0.6rem`, `min-height: 36px`; `.modal`
  `max-width: min(520px, 100%)`, `max-height: min(80vh, 700px)`;
  `.modal-fechar` `font-size: 1.1rem`, `width: 28px`, `height: 28px`;
  `.tabs-aba` padding `0.6rem ...`. Nenhum desses valores usa uma variável
  `var(--espaco-N)`/`var(--fonte-tamanho-*)` nem tem token equivalente
  definido — são literais novos, específicos desses componentes.
- **Ressalva (não conto como violação):** dois `style=` inline em TSX —
  `Accordion.tsx` (`style={{ margin: 0 }}`, reset do `<h3>` nativo) e
  `Chip.tsx` (`style={{ all: "unset", cursor: ... }}`, reset do `<button>`
  nativo) — são resets a zero/`unset`, não decisões de design de
  cor/espaçamento, e `.tabs-aba { margin-bottom: -1px; }` é o truque padrão
  de alinhamento de borda ativa sobre a borda do container (compensa a
  borda de 1px já usada em `.tabs-lista`), não um valor de espaçamento de
  design arbitrário. Não bloqueiam por si só.

Isso não impede o funcionamento dos componentes (visualmente corretos), mas
é uma lacuna real e mensurável frente ao critério de aceite tal como
escrito no contrato — a escala de tokens atual (`--espaco-1`..`8`, em
incrementos de 0.25rem/0.5rem/0.75rem/1rem/1.5rem/2rem/3rem/4rem) também não
tem granularidade para alguns desses casos (ex.: 6px, 0.15rem, 0.3rem —
menores que `--espaco-1`), sugerindo que a escala pode precisar de um ou
mais tokens menores (ex.: `--espaco-0` / `--espaco-micro`), não só que os
valores existentes deveriam ter sido reutilizados.

**Veredito critério 7: FALHOU** — correção é responsabilidade do
`executor`/`remediator` (extrair os valores listados acima para tokens
novos ou existentes em `globals.css` e trocar os literais pelas
`var(--...)` correspondentes).

### Item 4 — Suíte de testes backend completa (regressão)

Rodada com `DJANGO_CACHE_BACKEND=locmem` (mesma variável que
`.github/workflows/ci.yml` já define para o job `backend-tests` — ou seja,
esta é a configuração que efetivamente roda em CI, com o throttle
genuinamente ativo para toda a suíte, não a configuração "cache Redis
inerte" usada na iteração 1) e `DJANGO_DB_ENGINE=sqlite3` (sem PostgreSQL
disponível neste ambiente, mesma convenção já usada pelo executor).

```
cd backend && DJANGO_DB_ENGINE=sqlite3 DJANGO_CACHE_BACKEND=locmem .venv/Scripts/python.exe manage.py check
  → System check identified no issues (0 silenced).

cd backend && DJANGO_DB_ENGINE=sqlite3 DJANGO_CACHE_BACKEND=locmem .venv/Scripts/python.exe -m pytest -q
  → 221 passed, 7 warnings in 202.35s (0:03:22)
```

221 testes (toda a suíte, todos os apps — não só `identidade`/`comunidade`/
`landing`) passaram, incluindo os 3 novos testes de throttling. Nenhuma
regressão: nenhum teste pré-existente foi barrado por 429 espúrio mesmo com
o throttle genuinamente ativo em todo o processo de teste (confirma que o
volume de requisições dos testes pré-existentes aos 3 endpoints throttled
está bem abaixo do limite configurado, 20/min).

### Veredito final desta verificação

- Critério 1 (JSON-LD `NewsArticle`) — já verificado (iteração 1, execução
  real). Não repetido.
- Critério 2 (`sitemap.xml`/`robots.txt`) — já verificado (iteração 1,
  execução real). Não repetido.
- Critério 3 (banner antes de cookie não essencial) — **PASSOU** (inspeção
  de código, sem framework de teste frontend; ressalva de cobertura vazia
  documentada acima).
- Critério 4 (banner não reaparece após recusar) — **PASSOU** (idem).
- Critério 5 (429 após exceder limite) — **PASSOU** (teste automatizado
  novo, execução real, `backend/config/tests/test_throttling.py`, 3
  passed).
- Critério 6 (Modal Escape/clique fora/foco) — **PASSOU** (inspeção de
  código).
- Critério 7 (nenhuma cor/espaçamento hardcoded fora dos tokens) —
  **FALHOU** (achado concreto, ver acima — `rgba(0,0,0,0.5)` no overlay do
  Modal e ~12 valores de espaçamento/tamanho fora da escala de tokens nos 7
  componentes novos).
- Suíte completa do backend (221 testes, incluindo os 3 novos) — **passou**,
  sem regressão, com o throttle genuinamente ativo (`DJANGO_CACHE_BACKEND=locmem`,
  igual ao CI).

**Veredito geral: `failed`** — bloqueado no critério de aceite 7. Recomendo
devolver para `executor`/`remediator` corrigir os valores hardcoded listados
acima (extrair para tokens em `globals.css`) antes de seguir para
`reviewer`/`documenter`. Os critérios 3, 4, 5 e 6 estão prontos para seguir.

---

## Iteração 3 — 2026-09-03 — remediator (correção do critério de aceite 7)

**Escopo desta correção:** único achado pendente da Iteração 2 (tester) —
critério de aceite 7, "nenhuma cor/espaçamento hardcoded fora dos tokens" nos
7 componentes novos. Nenhum outro arquivo/critério foi tocado.

**O que foi feito — `frontend/app/globals.css`:**

1. Li o arquivo inteiro antes de decidir qualquer valor, para não inventar
   uma escala nova por cima da existente. A escala de espaçamento
   (`--espaco-1`..`--espaco-8`, 0.25rem..4rem) genuinamente não tinha
   degraus abaixo de `--espaco-1` nem entre alguns degraus — confirmado
   pela própria observação do tester na Iteração 2. Por isso, em vez de
   arredondar os valores existentes dos componentes (o que alteraria o
   visual já implementado, fora do escopo desta correção), estendi a escala
   com 3 tokens novos, mesma unidade/família:
   - `--espaco-0: 0.15rem` (abaixo de `--espaco-1`)
   - `--espaco-1-5: 0.3rem` (entre `--espaco-1` e `--espaco-2`)
   - `--espaco-2-5: 0.6rem` (entre `--espaco-2` e `--espaco-3`) — reutilizado
     em 3 lugares diferentes (Tooltip, Dropdown item, Tabs aba), o que
     confirma que era um degrau genuinamente faltante, não ruído de um
     componente isolado.

2. Adicionei um segundo grupo de tokens para dimensões fixas específicas de
   componente (não são padding/gap incremental, então não fazem sentido na
   escala `--espaco-*`, mas precisavam de nome em vez de literal solto):
   `--deslocamento-flutuante: 6px` (distância âncora→painel flutuante,
   reaproveitado em Tooltip e Dropdown), `--espaco-minimo: 2px` (gap do
   Dropdown), `--tamanho-botao-icone: 28px` (botão fechar do Modal),
   `--altura-min-item-menu: 36px`, `--largura-min-menu: 200px`,
   `--largura-max-tooltip: 240px`, `--largura-max-modal: 520px`,
   `--altura-max-modal: 700px`. Todos preservam o valor visual exato já
   implementado (zero mudança de layout).

3. `.modal-fundo { background: rgba(0, 0, 0, 0.5); }` → `rgba(var(--cor-sombra),
   0.5)` — agora usa o token que já muda entre tema claro (`15, 23, 42`) e
   escuro (`0, 0, 0`), como o resto do sistema de sombra/overlay do projeto.

4. Duas exceções deliberadas onde o literal foi trocado por um token
   levemente diferente (não idêntico), por serem diferenças imperceptíveis
   (~0.5px) em glifos de ícone, e para não criar tokens de uso único:
   - `.chip-remover { font-size: 0.85em }` (relativo ao chip, renderizava
     ~0.7225rem) → `var(--fonte-tamanho-xs)` (0.75rem, diferença de
     ~0.44px no glifo "×" do botão de remover).
   - `.modal-fechar { font-size: 1.1rem }` → `var(--fonte-tamanho-lg)`
     (1.15rem, diferença de ~0.8px no glifo "✕" do botão de fechar).

5. `.dropdown-item { padding: 0.5rem 0.6rem }` → `0.5rem` já era exatamente
   `--espaco-2`, só trocado o literal pelo token existente (sem novo token).

6. Todos os demais valores listados pelo tester (`.badge`, `.chip`,
   `.tooltip-balao`, `.dropdown-menu`, `.modal`, `.modal-fechar`,
   `.tabs-aba`) foram trocados pelos tokens (novos ou existentes)
   correspondentes, ponto a ponto, sem alterar nenhum valor numérico visual.

**Não alterado (confirmado, não são violação):** `style={{ margin: 0 }}` em
`Accordion.tsx`, `style={{ all: "unset", cursor: ... }}` em `Chip.tsx`
(resets a zero/`unset`, não decisões de design) e `.tabs-aba { margin-bottom:
-1px }` (truque de alinhamento de borda, não valor de espaçamento) — mesma
avaliação do tester na Iteração 2, não mexido.

**Revalidação:**
```
cd frontend && npx tsc --noEmit
  → sem erros (exit limpo, sem output)

# npx next build direto em frontend/ foi evitado: havia processos node.exe
# rodando na pasta (mesma colisão de "next dev" concorrente já documentada
# pelo executor na Iteração 1). Repeti a mesma estratégia: código-fonte
# (sem node_modules/.next) copiado para diretório isolado no scratchpad,
# node_modules linkado via junction do Windows (mklink /J, sem reinstalar
# dependências), build rodado lá.
cd <cópia isolada> && npx next build
  → "Compiled successfully", tipos válidos, 25 rotas geradas (mesma
    contagem da Iteração 1) — nenhuma rota quebrada, nenhum erro de
    compilação/tipo. Único warning: EPERM ao tentar criar symlink de
    node_modules para o modo `standalone` (o projeto não usa
    `output: "standalone"` em next.config.js — warning inofensivo, próprio
    da limitação de symlink do ambiente isolado, não relacionado a este CSS).
  → diretório isolado e junction removidos após a validação.
```

Revisão manual: reli o bloco inteiro dos 7 componentes em `globals.css`
(linhas ~1065-1386 pós-edição) e confirmei por leitura direta que não resta
nenhum literal de cor/espaçamento fora dos dois casos já excusados pelo
tester. Também confirmei via grep (`style=\{\{`) que os `style=` inline em
`Accordion.tsx`/`Chip.tsx` permanecem exatamente como estavam.

**Resultado:** critério de aceite 7 corrigido — cor do overlay do Modal
agora usa `--cor-sombra` (reage a tema claro/escuro) e todos os ~12 valores
de espaçamento/tamanho apontados pelo tester agora referenciam tokens de
`globals.css` (3 tokens novos na escala de espaçamento + 8 tokens novos de
tamanho/deslocamento de componente + reuso de tokens já existentes onde o
valor batia exatamente). `tsc --noEmit` e `next build` (em cópia isolada,
mesma técnica já validada pelo executor) confirmam que nada quebrou.

**Arquivos tocados:** `frontend/app/globals.css` (único arquivo alterado
nesta iteração).

---

## Iteração 4 — 2026-09-03 — remediator (findings do reviewer)

**Escopo desta correção:** os 3 findings `major` de `code-review-contract.md`
(veredito `changes_requested`, 0 blocker/3 major). Nenhum outro arquivo/
achado foi tocado. Todas as correções foram aplicadas diretamente pelo
`remediator` (fixes pontuais e de baixo risco) — nenhuma delegação ao
`executor` foi necessária.

### Finding 1 — throttle Redis silencioso (major) → RESOLVIDO

**Arquivo:** `backend/config/settings.py` (bloco `CACHES`, ramo Redis).

**O que foi feito:** adicionada `DJANGO_REDIS_LOG_IGNORED_EXCEPTIONS = True`
logo após `CACHES["default"]["OPTIONS"]["IGNORE_EXCEPTIONS"] = True`. Esta é
a flag nativa do `django-redis` (confirmada por leitura direta de
`django_redis/cache.py` na `.venv` instalada, versão 5.4.0) que faz
`RedisCache` chamar `self.logger.exception("Exception ignored")` (nível
`ERROR`, logger `"django_redis.cache"`) toda vez que uma exceção de conexão
é engolida por `IGNORE_EXCEPTIONS`. Não criei um cache separado nem desliguei
`IGNORE_EXCEPTIONS` (mudariam o comportamento de degradação gracil já
decidido e documentado no arquivo) — só parei de mascarar a falha em
silêncio total, conforme pedido pelo finding ("não precisa resolver
observabilidade completa, só parar de falhar em silêncio"). O `LOGGING`
já configurado em `settings.py` (root logger, handler `"console"` →
stdout do container) não tem entrada própria para `"django_redis.cache"` e
`disable_existing_loggers=False`, então o log propaga normalmente para o
handler já existente — nenhuma mudança adicional de `LOGGING` foi
necessária.

**Por que não foi mais longe:** o finding explicitamente aceita essa
correção mínima ("ou substitua por uma abordagem que não mascare o erro
silenciosamente... não precisa resolver observabilidade completa"). Alerta
ativo (ex.: Sentry/e-mail) ficaria fora de escopo e é mencionado só como
melhoria futura no próprio `report.md`/observações, não como parte deste
finding.

**Revalidação (execução real, não leitura de código):**
```
cd backend && DJANGO_DB_ENGINE=sqlite3 .venv/Scripts/python.exe manage.py check
  → System check identified no issues (0 silenced).   # settings carrega OK com o ramo Redis (backend padrão)

# Prova direta de que o log agora dispara quando o Redis está inacessível:
cd backend && DJANGO_DB_ENGINE=sqlite3 DJANGO_CACHE_REDIS_URL=redis://localhost:1/0 \
  .venv/Scripts/python.exe -c "
import django, os, logging
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()
logging.basicConfig(level=logging.INFO)
from django.core.cache import cache
print('IGNORE_EXCEPTIONS:', cache._ignore_exceptions)
print('LOG_IGNORED_EXCEPTIONS:', cache._log_ignored_exceptions)
print('resultado:', cache.get('chave-teste-inexistente'))
"
  → IGNORE_EXCEPTIONS: True
  → LOG_IGNORED_EXCEPTIONS: True
  → ERROR django_redis.cache [cache] Exception ignored
    (traceback completo de ConnectionRefusedError/ConnectionInterrupted)
  → resultado: None   # requisição continua degradando graciosamente, sem 500 —
    só passou a deixar rastro no log em vez de desaparecer.
```
Confirmado com Redis de fato inacessível (porta 1, `localhost:1`), não
apenas por leitura do código-fonte do `django-redis`.

### Finding 2 — sincronização de preferências de cookies nunca chamada (major) → RESOLVIDO

**Arquivos:** `frontend/lib/auth-context.tsx` (único arquivo alterado para
este finding; `frontend/lib/cookie-consent.ts` não precisou mudar — a
função já existia e estava correta, só não era invocada).

**O que foi feito:** importei `importarPreferenciasDoBackendSeNecessario` de
`./cookie-consent` em `auth-context.tsx` e chamei em dois pontos (mais
completo que só o sugerido pelo reviewer — cobre também o caso de sessão já
autenticada restaurada do `localStorage` ao carregar o app, não só o login
explícito):
1. Em `fazerLogin`, logo após `persistirSessao(resposta.token,
   resposta.usuario)` — cobre o cenário exato descrito no finding (login em
   dispositivo novo).
2. No `useEffect` de inicialização, logo após `setToken(tokenSalvo)` quando
   já existe um token persistido em `localStorage` — cobre o caso de sessão
   já autenticada sendo carregada (ex.: usuário já logado antes desta
   correção existir, ou preferência de cookies limpa manualmente sem limpar
   o token).

Ambas as chamadas são `void <chamada>` (fire-and-forget, consistente com o
padrão já usado no resto do arquivo/projeto para `sincronizarComBackendSeAutenticado`
em `BannerConsentimentoCookies.tsx`/`PreferenciasCookiesConteudo.tsx`) — a
própria função `importarPreferenciasDoBackendSeNecessario` já é no-op
silencioso se `consentimentoRespondido()` já for `true` localmente ou se a
chamada ao backend falhar, então não há risco de travar/atrasar login nem
de sobrescrever uma escolha local já feita neste navegador.

**Revalidação:**
```
cd frontend && npx tsc --noEmit
  → sem erros (exit limpo, sem output)

# next build isolado (mesma técnica das iterações 1 e 3 — processos node.exe
# de outra sessão detectados rodando na pasta frontend/ real; código-fonte
# sem node_modules/.next copiado via tar para diretório isolado no
# scratchpad, node_modules linkado via junction — desta vez criada com
# PowerShell `New-Item -ItemType Junction`, já que `cmd.exe /c mklink /J`
# não produziu efeito neste ambiente/sessão específica; junction e cópia
# removidos ao final):
cd <cópia isolada> && npx next build
  → "Compiled successfully", tipos válidos, 25 rotas geradas (mesma
    contagem das iterações 1 e 3) — nenhuma rota quebrada, nenhum erro de
    tipo/compilação. Único warning: EPERM ao criar symlink de node_modules
    para modo `standalone` (mesmo warning inofensivo já documentado na
    Iteração 3, não relacionado a esta mudança).
```
Nenhum teste automatizado de componente existe no frontend deste projeto
(confirmado pelo `tester` na Iteração 2 — sem `jest`/`@testing-library`/
`vitest` no `package.json`), então a revalidação funcional deste finding é
por `tsc`/`build` real + leitura do código alterado — mesma limitação já
documentada e aceita nas iterações anteriores desta run, não uma lacuna
nova introduzida agora.

### Finding 3 — zero testes para o endpoint de preferências de cookies (major) → RESOLVIDO

**Arquivo novo:** `backend/identidade/tests/test_preferencias_cookies.py`
(9 testes), seguindo a convenção já usada em
`identidade/tests/test_acceptance_criteria.py` (pytest-django, `APIClient`,
`force_authenticate`). Cobre, além do pedido mínimo do
`orchestrator`/finding, também as duas verificações extras sugeridas pelo
próprio `reviewer` no finding (cross-user e allow-list):

- `TestPreferenciasCookiesAutenticacao` — GET e PUT sem autenticação
  retornam `401`/`403` (2 testes).
- `TestPreferenciasCookiesGet` — GET autenticado sem preferência salva
  retorna `analytics=False`/`personalizacao=False`/`atualizado_em=None`;
  GET autenticado reflete preferência já persistida via
  `services.atualizar_preferencias_cookies` (2 testes).
- `TestPreferenciasCookiesPut` — PUT autenticado persiste de fato no banco
  (não só na resposta HTTP, `user.refresh_from_db()`); PUT sucessivo
  atualiza `preferencias_cookies_atualizado_em`; PUT autenticado como
  usuário A nunca afeta as preferências de usuário B mesmo injetando
  `id`/`user_id` de B no payload (a view sempre opera sobre `request.user`,
  nunca sobre um identificador do corpo/URL); PUT só grava as chaves do
  allow-list `services.CATEGORIAS_OPCIONAIS` mesmo com `"essenciais"` e um
  campo arbitrário injetados no payload (4 testes).
- `TestServiceAtualizarPreferenciasCookies` — cobertura direta do service
  layer: chave ausente no dict de entrada vira `False` (não erro); o
  timestamp de atualização é sempre definido (2 testes).

**Revalidação (execução real):**
```
cd backend && DJANGO_DB_ENGINE=sqlite3 DJANGO_CACHE_BACKEND=locmem \
  .venv/Scripts/python.exe -m pytest identidade -q
  → 54 passed in 33.23s   # inclui os 9 testes novos deste finding, sem falhas

cd backend && DJANGO_DB_ENGINE=sqlite3 .venv/Scripts/python.exe manage.py check
  → System check identified no issues (0 silenced).
```

### Regressão — suíte completa do backend

```
cd backend && DJANGO_DB_ENGINE=sqlite3 DJANGO_CACHE_BACKEND=locmem \
  .venv/Scripts/python.exe -m pytest -q
  → 255 passed, 7 warnings in 130.48s
```
255 testes (toda a suíte, todos os apps) passaram com o throttle
genuinamente ativo (`DJANGO_CACHE_BACKEND=locmem`, mesma configuração do
`.github/workflows/ci.yml`) — nenhuma regressão introduzida pelas 3
correções desta iteração (a mudança de `settings.py` do Finding 1 é só no
ramo Redis, não afeta o ramo `locmem` usado pela suíte de testes; os 8
testes de `config/tests/test_throttling.py` da Iteração 2 continuam
passando).

**Resultado final:** os 3 findings `major` do `code-review-contract.md`
estão corrigidos e revalidados com execução real (não leitura de código):
Finding 1 com prova de log disparando contra Redis genuinamente
inacessível; Finding 2 com `tsc --noEmit` limpo + `next build` real (25
rotas) confirmando que a nova chamada não quebra tipos nem o build; Finding
3 com 9 testes novos executados com sucesso (54 passed em `identidade`,
255 passed na suíte completa, sem regressão).

**Arquivos tocados nesta iteração:**
- `backend/config/settings.py` (Finding 1).
- `frontend/lib/auth-context.tsx` (Finding 2).
- `backend/identidade/tests/test_preferencias_cookies.py` (novo, Finding 3).

---
