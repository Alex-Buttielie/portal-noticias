<!--
NOTAS DE EXECUÇÃO — Bloco B1 (frontend)
DONO: executor (subagente delegado) — registro de trabalho, findings e pendências
RUN: 20260925-1020-observabilidade
-->

# Bloco B1 — notas de execução (frontend)

Escopo: **somente `frontend/`**. Nada em `backend/`, `.github/`, `infra/`,
`docker-compose*`, `.env*`, `scripts/release/`, `CI-CD.md`, `PROD_DECISOES.md`
ou `subir-localhost.sh` foi tocado. Nenhum `git add`/`git commit` foi executado.

Critérios do `implementation-contract.md` cobertos por este bloco:
**1, 2, 3, 4, 5, 10, 11, 12, 27, 28** (e suporte dos critérios 6, 17, 20 e
39, estos últimos com execução pendente no Bloco B2/C2 — ver "Ficou para o
B2").

---

## 1. Correlação ponta a ponta no cliente (critérios 1, 2, 3, 28)

### Arquivos

| Arquivo | Papel |
| --- | --- |
| `frontend/lib/observabilidade.ts` (novo) | Primitivas: `gerarRequestId`, `normalizarRequestId`, `caminhoSeguro`, `redigirTexto`, `semControle`, `ehVerdadeiro`, `registrarFalhaApi` |
| `frontend/lib/consento-local.ts` (novo) | Leitura do consentimento técnico sem nenhuma importação (quebra ciclo) |
| `frontend/lib/api.ts` | `X-Request-ID` gerado e enviado, propagação do header de resposta, `ApiError` com id completo, timeout, log redigido |
| `frontend/lib/cookie-consent.ts` | Categoria `tecnico`, versão 2 do registro, fail-closed |
| `frontend/lib/analytics.ts` | Query string fora do `payload.path` |

### `ApiError` agora carrega o `requestId` completo e normalizado

O `id` vinha **só do corpo** (`corpo.request_id`) e era **truncado em 8
caracteres** (`String(objeto.request_id).slice(0, 8)`). O corpo só tem
`request_id` no 500 custom do `RequestIdMiddleware` — portanto
400/401/403/404/429/502 ficavam **sem código de suporte**, que é exatamente o
caso em que o usuário precisa falar com o suporte.

Agora a fonte autoritativa é o **header de resposta** (o
`RequestIdMiddleware` o preenche em *toda* resposta, não só no 500), com o
corpo como último recurso. O valor é normalizado com as mesmas regras do
backend (`normalizar_request_id`): imprimível, ≤ 64 caracteres, sentinel `-`
vira UUID novo. `ApiError` ganhou também `motivo`
(`http|timeout|conexao|abort`) e `operacional` (`ok|degraded` do
`X-Operational-State`).

### Geração do `X-Request-ID`: por que o fallback é `getRandomValues`

Ordem: `crypto.randomUUID()` → `crypto.getRandomValues()` (montagem manual de
UUID v4) → contador monotônico por processo.

`crypto.randomUUID` **só existe em contexto seguro** (HTTPS/localhost). O
portal é HTTPS nos três ambientes, mas o mesmo bundle roda em
`http://<ip>:3000` durante diagnóstico — foi exatamente assim que o incidente
2026-09-18/19 foi diagnosticado — e ali `randomUUID` não existe. O degrau
intermediário usa `getRandomValues`, que está disponível também em contexto
não seguro: é ele, e **não** `Math.random()`, que garante entropia real. O
degrau final (sem WebCrypto) é `Date.now()` + contador, nunca `Math.random()`.

O espelhamento do contrato do backend foi intencional: id gerado e id aceito
têm a **mesma forma**, então o mesmo valor aparece no navegador, no log do
proxy e no log do Django.

### Timeout

`TIMEOUT_PADRAO_MS = 15_000`, sobrescrevivel por chamada via
`{ timeoutMs }`. Antes **não havia prazo nenhum**: uma requisição pendurada no
SSR segurava a revalidação da Home até o watchdog do orquestrador matar o
processo.

O `AbortSignal` externo é **composto** à mão com o interno
(`AbortSignal.any` não existe nas versões de runtime em uso e
`AbortSignal.timeout` tem semântica própria). Os dois call sites que já
passavam `signal` (`obterPublicacoes`, `obterPerfilAutor`, via TanStack Query e
`carregarColunistas`) continuam funcionando — abortar o sinal externo aborta a
requisição. `OpcoesRequisicao.signal` aceita `null` porque
`RequestInit["signal"]` aceita, e as duas funções declaram o objeto de opções
como `RequestInit` (erro de tipo real do `tsc`, corrigido assim em vez de
forçar `as`).

`ApiError` distingue os três desfechos: `timeout` (504), `conexao` (status 0,
mensagem de conexão) e `abort` (cancelamento, status 0).

### Log estruturado e redigido

`registrarFalhaApi` registra **um objeto**, não o erro cru: origem, request id,
método, **rota sem query string**, status, motivo e duração. `console.error`
anterior despejava o erro cru e a query string completa. `redigirTexto` cobre
Bearer, JWT sem rótulo, e-mail, atribuição de segredo e query string dentro de
URL; `caminhoSeguro` remove query, fragment e userinfo de `http(s)://user:pass@`.

Saída real durante o build (backend de desenvolvimento rodando):

```console
[api] falha de requisição {
  origem: 'cliente',
  requestId: 'a42df9d4-d383-456f-94fa-e8f9a29725c8',
  metodo: 'GET',
  rota: '/api/moderacao/paginas/termos/',
  status: 404,
  motivo: 'http',
  duracaoMs: 99
}
```

### Ciclo de importações

`lib/cookie-consent.ts` importa `lib/api.ts` (sincroniza preferências), então
`lib/api.ts` **não** pode importar `cookie-consent`. Daí `lib/consento-local.ts`
: só a chave e a leitura booleana, zero imports. `cookie-consent.ts` reexporta
a chave. O Bloco B2 (Sentry/Web Vitals) vai precisar do mesmo cuidado.

---

## 2. Proxy com timeout, limite e log (critério 1) — `app/api/[...path]/route.ts`

- `X-Request-ID`: gerado quando ausente/inválido, propagado para o Django, e o
  que **voltou** no header é devolvido ao browser.
- **Timeout** com `AbortController`: `API_PROXY_TIMEOUT_MS` (default 20 s).
  Timeout → **504**; erro de conexão → **502**. Distinguished, não genérico.
- **Teto de body** (`MAX_BODY_BYTES`, 16 MB, `API_PROXY_MAX_BODY_BYTES`):
  conferido em `content-length` **e** no `arrayBuffer` (chunked sem o header não
  escapa). O envio de credenciamento carrega foto + PDF e antes segurava o
  upload inteiro na memória do processo por rota. 413 com o id de correlação.
- `X-Technical-Consent` **preservado como veio**; normalizado para `1` quando
  verdadeiro, removido quando não. O proxy não amplia consentimento.
- Log estruturado com request id, desfecho e duração, **só em erro** (um log
  por requisição de sucesso é ruído sem valor diagnóstico).

**Evidência real** (servidor Next de pé, backend Django real em `:8000`):

```console
$ curl -D- -H "X-Request-ID: b1-proxy-check-1" http://127.0.0.1:3999/api/gating/status/
HTTP/1.1 200 OK
x-operational-state: degraded
x-request-id: b1-proxy-check-1

$ curl -D- http://127.0.0.1:3999/api/gating/status/          # sem id do cliente
HTTP/1.1 200 OK
x-request-id: be0f7203-f2a3-4d2c-8b1b-5109231cf8e1

$ head -c 20000000 /dev/zero | curl -X POST --data-binary @- .../api/auth/login/
HTTP/1.1 413 Payload Too Large
x-request-id: b00c5013-2491-4885-9079-8d010267a001

# upstream que aceita e nunca responde (API_PROXY_TIMEOUT_MS=3000)
STATUS=504 DURACAO=3.060637
{"detail":"O servidor demorou demais para responder...","request_id":"b1-timeout-check"}

# upstream com porta fechada
STATUS=502
{"detail":"Não foi possível conectar ao servidor...","request_id":"7d5dbabe-..."}
```

**Contra o Django real** (critérios 2 e 3):

```console
$ curl -D- -H "X-Request-ID: teste-frontend-b1-123" "http://localhost:8000/api/feed/?page_size=1"
HTTP/1.1 200 OK
X-Request-ID: teste-frontend-b1-123
X-Service: portal-api
X-Environment: development
X-Release: local
X-Operational-State: degraded

# id de 90 caracteres (excede MAX_REQUEST_ID_LENGTH)
X-Request-ID: 4da289fc-8a8a-41de-b56b-e25c091bea62
```

---

## 3. Error boundaries (critério 4) — `app/error.tsx` e `app/global-error.tsx`

**Não existiam em nenhuma rota.** Criados os dois, com `reset()`.

- `app/error.tsx`: reaproveita `Card`/`Button` do design system, `role="alert"`,
  mostra o **código de suporte** quando existe, com a origem rotulada
  ("requisição" quando é `ApiError.requestId`; "servidor" quando é o `digest`).
  Título e descrição no singular, foco no que o leitor faz.
- `app/global-error.tsx`: desenha `<html>/<body>` em estilo inline porque a
  falha é **no layout raiz** — usar `Link`, `Card` ou qualquer coisa que
  dependa de `Providers` reentraria em loop. Aceito como trade-off: sem
  `next/link` e sem os componentes do design system aqui.

**Honestidade do texto** (critérios 5 e 27): a tela só diz que o erro "pode ser
analisado pela equipe" se `consentimentoTecnico()` for verdadeiro; caso
contrário, diz explicitamente que **nada** é registrado e aponta as preferências.
Prometer "já avisamos a equipe" sem que exista envio seria exatamente o tipo de
promessa que a telemetria não sustenta. E o Sentry nem está instalado ainda
(Bloco B2) — o texto não pode fingir o contrário.

---

## 4. Remoção de conteúdo fictício (critérios 11, 12) — **prioridade do bloco**

### O inventário real: 18 arquivos, não 13

O pedido citava 13 (contando as 7 páginas + 7 admin, que davam 14). A varredura
encontrou mais **quatro** fora da lista, todos com o mesmo defeito:

| Arquivo | Fictício encontrado |
| --- | --- |
| `app/noticia/[id]/page.tsx` | artigo "Notícia #N — conteúdo de demonstração" com `newsArticleJsonLd` — **o Google recebia NewsArticle de notícia inventada** |
| `app/noticia/cluster/[id]/page.tsx` | `nome_fonte: "Fonte Exemplo"`, `url_fonte_original: "https://example.com"`, também no Json-Ld |
| `app/noticia/item/[id]/page.tsx` | idem |
| `app/admin/page.tsx` | timeline "Atividade recente" com **seis eventos inventados**: uma manchete aprovada "por admin@brd.com há 12 min", `marina.oliveira@exemplo.com`, renovação de assinatura com R$ 59,80, robôs com "14 itens ingeridos" |
| `app/comunidade/page.tsx` | além de `MOCK_PUBS`: `membrosMock = 80 + g.slug.length * 37 + countPubs * 7` — contagem de membros calculada a partir do slug |

### Por que isso era **pior** do que "conteúdo de demonstração"

Os botões de ação continuavam ligados sobre o array de exemplo, e os `id` do
exemplo são ids **reais** de produção:

- `app/admin/moderacao`: "Remover" chamava `POST .../denuncias/1/acao/`
  — decisão de moderação sobre o registro de id 1, que é uma denúncia real de
  alguém.
- `app/admin/fila`: "Aprovar"/"Rejeitar" chamavam `.../fila/1/decisao/` e
  `/2/`, `/3/`. Rejeitar uma notícia que não existe apaga conteúdo de alguém.
- `app/admin/robos`: "Remover" chamava `DELETE .../robos/fontes/1/`. Desativar a
  fonte errada **para a coleta de um veículo real** sem decisão de ninguém.
- `app/admin/usuarios`: "Alternar papel" fazia `PATCH .../usuarios/1/` —
  promoção/depromoção de permissão real a partir de um erro de rede.
- `app/ao-vivo`: fabricava uma manchete **selada LIVE** apontando para
  `/noticia/11` e `/noticia/12`, que não existem.

### A causa raiz: `lib/recomendacao.ts`

```ts
// ANTES — nunca lançava
} catch {
  return { secoes: null, feed: [], destaques: [] };
}
```

`carregarHome` nunca lançava, então **todo** o tratamento de erro das páginas
que a consomem era código morto, e a única forma de "não quebrar" a Home era
substituir o feed por um `MOCK` local. Corrigido na raiz: `carregarHome` agora
propaga a falha; `destaques` continua degradando de forma independente
(opcional editorialmente, e isso é dito no código). O script de guarda tem uma
verificação específica para essa assinatura de função.

### Estados honestos por camada

| Camada | Falha | Estado vazio |
| --- | --- | --- |
| Home (`/`) | último conteúdo real ≤ 5 min, com banner de idade; sem histórico → `throw` em runtime / painel honesto em build | painel "Sem notícias no momento" |
| `categoria/[slug]` | último real ≤ 5 min ou painel de erro com código de suporte | "Nenhuma notícia publicada nesta editoria" |
| `noticia/[id]`, `noticia/cluster/[id]`, `noticia/item/[id]` | `NoticiaIndisponivel` com código de suporte | — |
| `ao-vivo` | painel de erro com código de suporte | "Nenhuma matéria urgente agora" (é informação real) |
| `arquivo` | painel de erro com código de suporte | "Fim do arquivo" |
| `buscar` | "A busca está indisponível" + código | contagem real de 0 resultados |
| `comunidade` | "Feed indisponível" + código + tentar de novo | vazio real |
| `radar` | erro explícito nas duas abas + código | "Nenhum assunto em alta" |
| admin (7 telas) | "API indisponível — nenhuma ação foi executada" | estado legítimo, **separado** do erro |

### `app/admin/planos` e `app/admin/limites`: a LÓGICA, não o texto

O defeito era `isError ? MOCK : (vazia ? MOCK : lista)`: os dois casos caíam no
array de exemplo, e a mensagem `"API offline — exibindo dados de exemplo"`
aparecia **inclusive quando a API respondia 200 com zero itens** — acusando a
API de estar fora do ar num estado perfeitamente saudável. Agora `vazia` e
`isError` são estados distintos com textos distintos, e nenhum dos dois mostra
plano/limite de exemplo (com os botões "Editar"/"Excluir" apontando para os ids
do exemplo).

### `generateStaticParams` deixa de "assar" fictício

`app/categoria/[slug]`, `app/noticia/[id]`, `app/noticia/cluster/[id]` e
`app/noticia/item/[id]` são pré-renderizados no build. Uma falha de fetch
durante o build servia o array de exemplo no HTML estático, e ele continuava no
ar **mesmo com a API de pé depois**. Os três `[id]` passaram a
`generateStaticParams() { return [] }` (geração por demanda, ainda com ISR, e
sem depender de dado externo no build); `categoria/[slug]` mantém os 5 slugs
(ninguém consulta a API em build quebra nada ali, porque a página não lança) e
agora também usa a janela de último conteúdo real.

---

## 5. Home: stale real, degradação sinalizada e 503 (critérios 10, 11)

### Decisão de camada (a pergunta explícita do bloco)

**Onde a janela de stale foi implementada e por quê.** Ela é do **Next (App
Router / ISR)**, não do backend, por três razões:

1. **A janela pertence à página, não ao dado.** "Até 5 minutos do último
   conteúdo real" é uma propriedade de *renderização* da Home. O backend tem
   cache de feed com TTL próprio e não conhece a janela de revalidação da Home
   nem a noção de "última renderização boa" do portal.
2. **A Home já tem stale-while-error do próprio Next.** Com `revalidate = 60`,
   uma falha na revalidação não apaga o que já foi servido. Construir em cima
   disso é usar o mecanismo correto em vez de inventar um segundo.
3. **O backend é quem sabe se o feed está de pé; o frontend é quem decide o que
   mostrar quando não sabe.** A degradação chega por header
   (`X-Operational-State: degraded`, já emitido pelo `RequestIdMiddleware` do
   Bloco A) e é lida em `lib/api.ts` via `onResposta`, sem polling.

Implementação: `frontend/lib/ultimo-conteudo-real.ts` (janela de 5 min,
gravado em `globalThis`), `registrarConteudoReal` no caminho feliz e
`lerConteudoReal` no `catch` de `app/page.tsx`. `origem: "stale"` renderiza
banner com a idade ("Mostramos a última atualização bem-sucedida há 3
minutos"), com o código de correlação.

**Limitação assumida:** a janela é por **processo**. Um restart, ou um segundo
worker, começa sem histórico e cai no caminho honesto. Produção roda processo
único (PM2 + `output: standalone`) e 5 min é curto o bastante para que "sem
histórico" seja o estado normal logo após um deploy. Uma janela compartilhada
exigiria backend ou Redis — e o `cache` do Next seria a opção natural, com o
custo de serializar a página inteira.

### 503: o que foi entregue e o que NÃO foi, e por quê

**Entregue:** nenhum `MOCK` em nenhuma hipótese; sinalização de degradação com
origem (`stale`, `sem-dado-real`, `indisponivel`, degradado pelo backend); 503
real no **caminho de dados** (`/api/*` responde 504/502/413 com
`request_id`).

**Não entregue: o status HTTP 503 no *documento HTML* da Home.** Isso não é
possível em um Server Component do App Router — a API pública do Next 14 não
permite a um Server Component fixar o status da resposta (só Route Handlers e
`middleware` têm `NextResponse`). Um `throw` produz 5xx pela.Error Boundary, não
503. E um `middleware` que fizesse probe do feed para decidir 503 adicionaria
uma chamada de rede na rota mais quente, em todos os deploys, com risco de 503
falso quando o feed fica lento — trocar "500 honesto" por "503 errado" é
pior. Registrado como follow-up, com a divisão de camada:

- **backend**: header de idade/`cached_at` no feed (hoje o frontend não sabe
  quantos anos o dado tem, e por isso **não pode rotular o stale com precisão** —
  a idade que exibimos é a idade do último render bem-sucedido, não do item mais
  antigo); e 503 no endpoint de feed quando não há cache válido.
- **infra**: isentar a resposta degradada do `proxy_cache` do nginx, senão o
  `503`/aviso do backend fica cacheado e served como se fosse normal.

`backend/feed/views.py` **não foi tocado** (WIP da run
`20260924-2136-ingestao-noticias`).

### Uma armadilha de build encontrada e resolvida (importante para o CI)

Com a Home passando a lançar quando não há conteúdo real, `next build` **falha
inteiro** ("Export encountered errors on following paths: /page: /") sempre que
a API não está disponível durante a geração estática. O job `frontend-build` do
CI roda `npm run build` **sem nenhum serviço de backend**
(`.github/workflows/ci.yml:74-104`), então isso quebraria o CI com um falso
alarme.

Resolvido em duas frentes, ambas verificadas empiricamente:

1. `app/page.tsx` distingue a fase de build (`process.env.NEXT_PHASE ===
   "phase-production-build"`, o mesmo sinal que o próprio Next usa internamente
   em `next-server.js`): durante o build o mesmo estado é renderizado honestamente
   (painel "Sem notícias no momento"); **em runtime a falha continua
   repropagando**, e o `error.tsx` mostra a recuperação com código de suporte.
   O valor do default é defensivo: se o Next mudar a fase, o default (não é
   build) mantém o comportamento correto em produção.
2. As três rotas `/noticia/*` deixaram de pré-gerar `[{ id: "1" }]`. Prerender um
   id arbitrário obrigava o build a consultar a API e não tem valor de SEO
   (notícias reais entram pelo feed). `generateStaticParams() { return [] }` as
   torna por demanda com ISR.

O build de **produção** roda na própria VPS com o Django no ar
(`.github/workflows/deploy.yml:302-312`), então é lá que a degradação fica
evidenciada com conteúdo real.

**Evidência** (build com upstream 503, condição do CI):

```console
$ NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:4023 npm run build
BUILD_503_EXIT=0
# e o HTML pré-gerado de / contém:
#   "Sem notícias no momento" / "Nenhuma notícia real disponível"
# sem nenhuma ocorrência de conteúdo fictício em .next/server e .next/static
```

Em runtime com o mesmo upstream 503:

```console
/                    => 200  "Sem notícias no momento" + código de suporte
/ao-vivo             => 200  "Não foi possível carregar a cobertura urgente" + código
/buscar?q=energia    => 200  "A busca está indisponível" + código
/categoria/politica  => 200  "Não foi possível carregar esta editoria" + código
/noticia/1           => 200  "Não conseguimos carregar esta notícia" + código
/noticia/cluster/1   => 200  idem
/noticia/item/1      => 200  idem
```

E com o backend real (`:8000`), a Home mostra 30 manchetes reais e o banner
"Serviço parcialmente indisponível" — que é o estado verdadeiro do sandbox
(Redis/Celery fora, `X-Operational-State: degraded`).

### Um achado sobre `/noticia/[id]`

A primeira versão lancei a exceção de indisponibilidade para o error boundary.
Testando em runtime com o upstream 503, a resposta foi a **página de erro
genérica do Next** (a do Pages Router, com `pages/_error`), sem `reset()` e sem
código de suporte: quando a **primeira** geração ISR de uma rota por demanda
falha, não existe página em cache e o error boundary não é usado. Daí a
`components/NoticiaIndisponivel.tsx`: indisponibilidade é estado **da página**,
não exceção. O `error.tsx` continua cobrindo exceção de render e erro de cliente,
que é o que o critério 4 pede.

---

## 6. Categoria de consentimento técnico (critérios 27, 5)

`CategoriaOpcional` passou a ser `"analytics" | "personalizacao" | "tecnico"`;
registro na versão **2** do formato, com fail-closed:

- registro `versao: 1` (anterior a esta run) não conhece `tecnico` → entra como
  `false`. Quem apagou o dado precisa consentir de novo; o diagnóstico não é
  ligado por omissão;
- sem registro, JSON inválido, `localStorage` bloqueado, SSR → `false`;
- `lib/api.ts` envia `X-Technical-Consent: 1` **só** no navegador e só quando
  concedido. O proxy repassa como veio.

Banner e preferências distinguish as três categorias com switch próprio, e o
texto do banner nomeia as três explicitamente (analytics, personalização,
diagnóstico técnico) e diz que **rejeitar não essenciais também desliga o
diagnóstico** — nada de sneaky-ware. `app/privacidade/page.tsx` e
`app/cookies/page.tsx` agora têm seção própria dizendo que a telemetria
técnica é separada, o que ela não mede e o que nunca leva.

### Limitação conhecida e não contornável aqui

`PreferenciasCookiesSerializer` (`backend/identidade/serializers.py:165`)
aceita e devolve **apenas** `analytics` e `personalizacao`. Como `backend/` está
fora do escopo, a categoria `tecnico` **não é enviada** na sincronização (enviar
seria ignorado em silêncio pelo DRF e criaria a impressão de sincronização do
que não foi sincronizado) e volta como `false` ao importar de outro
dispositivo — fail-closed. Registrado como follow-up.

### `lib/analytics.ts`

`payload.path` era `location.pathname + location.search`: a **query string
completa** ia para um evento de produto a cada `page_view`, colocando o que o
usuário digitou (termo de busca, e-mail, token de convite) dentro de um evento
analítico com retenção de 12 meses. Agora o `path` é só o pathname, e
`caminhoSeguro` é aplicado **também** ao `path` explícito — nenhum chamador
reintroduz dado sensível passando `path` à mão. O termo da busca continua no
campo `termo`/`query` do evento de busca, que é o contrato de produto já
existente e é redigido no backend.

---

## 7. Guarda de regressão para conteúdo fictício

`frontend/scripts/verificar-conteudo-ficticio.mjs` — Node puro, ESM, sem
dependência, **exit 1 em violação**, no mesmo padrão de
`verificar-query-client.mjs` / `verificar-datas-tz.mjs` (removedor de
comentários próprio, porque os PRÓPRIOS arquivos descrevem o problema em
comentário). Adicionado em `frontend/package.json` como
`test:conteudo-ficticio` (os outros dois scripts também entraram, por
simetria, mas sem mudança de comportamento).

Seis verificações:

1. as 18 páginas nomeadas existem;
2. `frontend/app/**` sem array/objeto/texto de demonstração (10 padrões;
   comentários ignorados);
3. `frontend/lib/**` sem array/gerador de demonstração;
4. **causa raiz**: `carregarHome` não pode ter `catch` devolvendo seção/lista
   vazia;
5. a Home precisa de tratamento de falha de verdade (`catch` + janela de
   último conteúdo real);
6. a rota de proxy precisa de timeout, teto de body e `X-Request-ID`.

Dois detalhes deliberados do desenho:

- **Negação honesta é permitida.** As telas precisam poder dizer "não exibimos
  conteúdo de exemplo"; o padrão usa lookbehind negativo para os verbos de
  negação. Um verificador que obriga apagar a explicação honesta é um
  verificador que se contorna.
- **`placeholder="voce@exemplo.com"` é dica de preenchimento, não dado
  fictício** — o usuário digita o próprio endereço ali. O padrão de e-mail
  isenta a linha quando o `@exemplo.com` só aparece dentro de `placeholder`.
  O que é proibido é o endereço aparecer como **dado** de pessoa que não
  existe.

**Caminho negativo testado (exit 1)**, com mutação real em
`app/ao-vivo/page.tsx`:

```console
[VIOLAÇÃO] frontend/app/**: sem array/objeto/texto de demonstração — 2 achado(s):
      - app/ao-vivo/page.tsx:9 — array de demonstração (MOCK*) ("MOCK")
      - app/ao-vivo/page.tsx:10 — aleatoriedade em página de produção ("Math.random(")
EXIT_MUTADO=1
EXIT_RESTAURADO=0
```

E com o `catch` de `carregarHome` reintroduzido:

```console
[VIOLAÇÃO] lib/recomendacao.ts: carregarHome existe e propaga falha — carregarHome
tem `catch` devolvendo seção/lista vazia — todo tratamento de erro das páginas que a
consomem vira código morto e o fallback fictício volta
EXIT_MUTADO=1
EXIT_RESTAURADO=0
```

A execução na CI é do Bloco C2 (`.github/` está bloqueado neste bloco).
**Pendência concreta:** adicionar `node scripts/verificar-conteudo-ficticio.mjs`
ao job `frontend-build`, antes do `tsc` (mesma posição dos outros dois checks).

---

## Arquivos tocados

Novos:

```text
frontend/lib/observabilidade.ts
frontend/lib/consento-local.ts
frontend/lib/ultimo-conteudo-real.ts
frontend/app/error.tsx
frontend/app/global-error.tsx
frontend/components/NoticiaIndisponivel.tsx
frontend/scripts/verificar-conteudo-ficticio.mjs
```

Modificados:

```text
frontend/lib/api.ts
frontend/lib/analytics.ts
frontend/lib/cookie-consent.ts
frontend/lib/recomendacao.ts
frontend/app/api/[...path]/route.ts
frontend/app/page.tsx
frontend/app/ao-vivo/page.tsx
frontend/app/arquivo/page.tsx
frontend/app/buscar/page.tsx
frontend/app/categoria/[slug]/page.tsx
frontend/app/comunidade/page.tsx
frontend/app/radar/RadarClient.tsx
frontend/app/noticia/[id]/page.tsx
frontend/app/noticia/cluster/[id]/page.tsx
frontend/app/noticia/item/[id]/page.tsx
frontend/app/admin/page.tsx
frontend/app/admin/usuarios/page.tsx
frontend/app/admin/moderacao/page.tsx
frontend/app/admin/fila/page.tsx
frontend/app/admin/planos/page.tsx
frontend/app/admin/limites/page.tsx
frontend/app/admin/assinaturas/page.tsx
frontend/app/admin/robos/page.tsx
frontend/app/privacidade/page.tsx
frontend/app/privacidade/preferencias-cookies/page.tsx
frontend/app/cookies/page.tsx
frontend/components/BannerConsentimentoCookies.tsx
frontend/package.json
```

**Nenhuma dependência nova.** `crypto.randomUUID`/`getRandomValues`,
`AbortController`, `console.error` e `fetch` são plataforma. Zero pacote novo
em `package.json`.

---

## Validações — saída real

Ambiente: `frontend/`, Node do workspace, backend Django de desenvolvimento
rodando em `127.0.0.1:8000` (com Redis/Celery fora, daí
`X-Operational-State: degraded`).

```console
$ npx tsc --noEmit
(sem saída)
exit 0
```

```console
$ npm run build
 ✓ Compiled successfully
 Linting and checking validity of types ...
 ✓ Generating static pages (59/59)
exit 0
```

```console
$ node scripts/verificar-conteudo-ficticio.mjs
Vigiliando 18 páginas conhecidas + toda a árvore app/ e lib/.
[OK] páginas vigiadas existem — 18 arquivo(s) encontrado(s)
[OK] frontend/app/**: sem array/objeto/texto de demonstração — 67 arquivo(s) de fonte varridos (comentários ignorados)
[OK] frontend/lib/**: sem array/objeto de demonstração — 38 arquivo(s) de fonte varridos (comentários ignorados)
[OK] lib/recomendacao.ts: carregarHome existe e propaga falha — sem `catch` que converta falha em lista/seção vazia
[OK] app/page.tsx: falha real é tratada (janela de stale + honestidade) — `catch` presente com janela de último conteúdo real de 5 min
[OK] app/api/[...path]/route.ts: timeout, teto de body e correlação — timeout, teto de body e X-Request-ID presentes
Nenhum fallback fictício encontrado nas páginas de produção.
exit 0
```

Sem regressão nos checks que já existiam:

```console
$ node scripts/verificar-query-client.mjs   → exit 0 (8/8 OK)
$ TZ=UTC       node scripts/verificar-datas-tz.mjs → exit 0
$ TZ=Asia/Tokyo node scripts/verificar-datas-tz.mjs → exit 0
```

`grep -rIl` por "Conteúdo de exemplo", "manchete demonstrativa", "Conteúdo de
demonstração", "ao vivo: atualização contínua", "Mercados reagem a novo ciclo de
juros" e "Fonte Exemplo" em `.next/server` e `.next/static`: **nenhuma
ocorrência**, com o backend real e com o upstream 503.

**O build passou em todas as condições testadas:** backend real (exit 0), upstream
503 (exit 0, condição do CI), e nenhum conteúdo fictício no artefato em nenhuma
delas. Não houve build que não rodasse.

---

## Decisões e trade-offs (resumo)

1. **Componente novo `lib/observabilidade.ts` em vez de tudo em `lib/api.ts`.**
   O proxy (`app/api/[...path]/route.ts`, runtime Node) e o cliente
   (`lib/api.ts`, browser e SSR) precisam das mesmas primitivas, e `lib/api.ts`
   não pode ser importado pelo route handler sem arrastar o cliente inteiro. Um
   módulo sem imports resolve.
2. **`getRandomValues` como fallback, não `Math.random()`.** `randomUUID` só
   existe em contexto seguro e o bundle roda em HTTP por IP durante
   diagnóstico.
3. **Timeout de 15 s no cliente, 20 s no proxy.** Os dois são sobrescrevivíveis
   por ambiente/chamada. Antes não havia prazo.
4. **`X-Technical-Consent` não é persistido no backend.** O serializer não aceita
   o campo; enviar seria ignorado em silêncio. Fail-closed e documentado.
5. **`versao: 2` do registro de consentimento, com `versao: 1` normalizado para
   `tecnico: false`.** Quem já respondeu precisa responder de novo para o
   diagnóstico; o inverso (ligar por omissão) seria sneaky-ware.
6. **Stale por processo, em `globalThis`.** Sem backend/Redis, e 5 min é curto
   para o custo de serializar a página inteira. O banner diz a idade do último
   *render* bom, não do item mais antigo — o backend ainda não expõe idade de
   cache (follow-up), e mentir sobre isso seria pior que omitir.
7. **Sem 503 no documento HTML.** Documentado acima com a razão de camada e os
   dois follow-ups que fecham o critério.
8. **Falha de build por API fora.** Duas mitigações verificadas
   empiricamente (guarda de fase em `/` e `generateStaticParams() → []` nas
   rotas `/noticia/*`) em vez de enfraquecer o tratamento de erro.
9. **Disponibilidade de `/noticia/*` é estado da página, não exceção.** Medido:
   `throw` na primeira geração ISR produz a página de erro genérica do Next,
   sem `reset()` e sem código de suporte.
10. **O verificador permite a negação honesta** ("não exibimos conteúdo de
    exemplo") e o `placeholder` de e-mail, e proíbe o dado fictício. Um guarda
    que obriga apagar a verdade é um guarda que se contorna.
11. **`Math.random()` proibido em `app/**` e permitido em `lib/`.** Em `lib/` ele
    é legítimo (`analytics.ts` deriva um id de sessão que nunca sai do
    navegador; `ImagemNoticia` deriva gradiente). Proibi-lo lá geraria falso
    positivo e ruído.

---

## Follow-ups

### Destinadas ao backend (owner a definir; `backend/` fora deste bloco)

1. **Idade de cache no feed**: header (ex.: `X-Cache-Age`/`Age` ou
   `cached_at` no payload) e/ou 503 no endpoint de feed quando não há cache
   válido. Sem isso o frontend **não consegue rotular o stale com precisão** e
   não pode devolver 503 no documento. Arquivo sugerido:
   `backend/feed/views.py` — **WIP da run `20260924-2136-ingestao-noticias`,
   reconciliar antes de tocar**.
2. **Persistir a categoria `tecnico`**: `PreferenciasCookiesSerializer`
   (`backend/identidade/serializers.py:165`) aceita apenas `analytics` e
   `personalizacao`.
3. **Isentar a resposta degradada do `proxy_cache` do nginx** (bloco de
   infra), senão o 503/aviso do backend fica cacheado e servido como se fosse
   normal.
4. Já registrado pelo Bloco A e ainda aberto: `/healthz` legado vaza
   `str(exc)`; token de consentimento de analytics não é validado no endpoint
   público; heartbeat do beat não existe.

### Destinadas ao Bloco B2 (frontend/Sentry/testes)

1. `@sentry/nextjs` + `instrumentation.ts`/plugin de source map, com
   `beforeSend` que:
   - **não envia nada** sem `permiteCategoria("tecnico")` (critérios 5, 27) —
     ler via `lib/consento-local.ts` para não criar ciclo;
   - redige token, e-mail, IP completo e query string;
   - carrega ambiente/release (critério 6);
   - inclui o request id como tag quando o erro é `ApiError`.
2. Web Vitals / `Reporters`, com o mesmo portão de consentimento.
3. `X-Release`/`X-Environment` do build expostos ao browser como
   `NEXT_PUBLIC_*` (hoje o header existe no proxy, mas o bundle do cliente não
   o lê).
4. Suíte de testes de comportamento de erro/consentimento (critério 39). Nota
   prática: o `frontend/` **não tem** runner de teste; o padrão do projeto para
   verificação determinística é script Node com `exit 1` — seguir esse padrão
   evita introduzir dependência.
5. Reprovar erro de boundary quando o consentimento técnico está desligado é o
   comportamento atual e desejado; ao adicionar o Sentry, manter o texto de
   `app/error.tsx` coerente com o que está de fato instalado.

### Destinadas ao Bloco C2 (CI — `.github/` bloqueado neste bloco)

1. `node scripts/verificar-conteudo-ficticio.mjs` no job `frontend-build`,
   antes do `npx tsc --noEmit` (mesma posição dos outros dois checks).
2. Upload de source maps (critério 20).

### Reconciliação com outras runs

- `run 20260924-2136-ingestao-noticias`: dono de `backend/feed/views.py` e dos
  testes de feed. **Não tocado.** O follow-up de idade de cache/503 no feed
  precisa ser combinado com essa run para não EDITAR-A CONFLITANDO.
- `run 20260925-1433-go-live-producao`: não tocada. Ela altera
  `CI-CD.md`/`PROD_DECISOES.md`/`infra/DEPLOY.md`, que este bloco não modifica.
  **Atenção de coordenação:** o build de produção roda na VPS com o Django no ar;
  se aquela run passar a construir o frontend **na CI** (sem backend), a guarda
  de fase de `app/page.tsx` mantém o build verde, mas as páginas
  pré-renderizadas de `/categoria/*` e `/` sairão do artefato com o painel
  honesto de indisponibilidade até a primeira revalidação (≤ 60 s). Se isso for
  indesejado, o caminho certo é dar serviço de backend ao job de build ou
  Remover a pré-geração dessas rotas.
- `run 20260924-1721-react-query-migracao` (dona de `verificar-query-client.mjs`):
  o novo script segue o mesmo padrão e não altera o existente. Regressão
  verificada (exit 0).

---

## Riscos abertos

1. **503 no documento HTML da Home continua em aberto** (critério 11 parcialmente
   satisfeito). Depende dos follow-ups de backend/infra. Omitido em vez de
  aking por um `middleware` com probe, que trocaria falha honesta por 503 falso
   na rota mais quente.
2. **A idade exibida no banner de stale é a do último render bom, não a do
   conteúdo mais antigo.** Aceito, e é por isso que a follow-up de idade de cache
   importa: sem ela, um dado de 3 dias servido como stale de 40 s seria
   enganoso.
3. **Janela de stale por processo.** Com mais de um processo do Next, cada um
   tem a sua janela. Produção é processo único; se mudar, o comportamento
   degrada para "cada processo tem até 5 min do seu próprio último bom" —
   mais honesto do que pior, mas precisa ser reavaliado.
4. **`process.env.NEXT_PHASE`** é um detalhe interno do Next. O default é
   defensivo (ausência = runtime = comportamento correto em produção), e o
   comportamento foi verificado empiricamente nesta versão (14.2.15). Um upgrade
   do Next merece re-testar o build com a API fora.
5. **`categoria/[slug]` continua pré-renderizada no build.** Não quebra o build
   (a página não lança), mas um artefato construído sem API carrega o painel de
   erro por até 60 s. Ver o item de reconciliação acima.
6. **Ação operacional continua sem confirmação em tela de API indisponível nas 7
   telas de admin.** O que interessa — que nenhuma decisão ocorre sobre dado
   fictício — está garantido. Desabilitar os botões quando `isError` seria
   melhoria de UX, não correção; não foi feito para manter o diff focado.
