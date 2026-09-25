<!--
NOTAS DE EXECUÇÃO — Bloco B2 (frontend: Sentry real, cliente do token de consentimento, testes)
DONO: subagente executor (bloco B2) da run 20260925-1020-observabilidade
ESCOPO: somente `frontend/` + este arquivo de notas
-->

# Notas do Bloco B2 — Sentry real, cliente do token de consentimento e suíte de testes

Run `20260925-1020-observabilidade`. Branch `observability-20260925-1020`
mantida. Execução isolada: `git add`/`commit` só no fim e só com os paths
explícitos dos meus arquivos.

Critérios do `implementation-contract.md` cobertos: **5, 6, 20, 24 (apoio),
25, 26, 27, 39** — e **4** como consequência (o error boundary agora realmente
reporta).

---

## 0. Resumo em uma tela

| O que | Onde | Critério |
|---|---|---|
| `@sentry/nextjs@10.75.3` instalado e **ligado** de verdade | `package.json`, `next.config.js`, `sentry.{client,server}.config.ts`, `instrumentation.ts` | 6, 20 |
| Redação de evento + portão de consentimento (puro, testável) | `lib/sentry-opcoes.ts` (novo) | 5, 6, 27 |
| Casca de runtime do browser | `lib/sentry-cliente.ts` (novo) | 4, 5, 27 |
| Error boundaries reportam de verdade | `app/error.tsx`, `app/global-error.tsx` | 4 |
| **Cliente do token de consentimento** (fecha pendência do A2) | `lib/consent-token.ts` (novo), `lib/analytics.ts`, `lib/api.ts` | 25, 26 |
| Suíte de testes (não existia nenhuma) | `testes/*.test.ts` (7 arquivos), `vitest.config.ts` | 39 |
| Canal de release/ambiente documentado | `Dockerfile`, ambos os configs | 6, 20 |

**O ganho mais importante deste bloco:** a coleta de analytics do portal,
que estava **parada** desde o Bloco A2, voltou a funcionar — e isso está
provado com o backend real rodando (seção 5).

---

## 1. Sentry de verdade (critérios 6 e 20)

### 1.1 Por que 10.75.3 e não a "última"

| Opção | Peer `next` | `engines.node` | Decisão |
|---|---|---|---|
| 8.x/9.x | `^13.2 \|\| ^14 \|\| ^15-rc` | `>=14.18` / `>=18` | possível |
| **10.75.3** | `^13.2 \|\| ^14 \|\| ^15-rc \|\| ^16-0` | **`>=18`** | **escolhida** |
| 11.0.0 | `^14 \|\| ^15-rc \|\| ^16-0` | `>=20.19.0 <22 \|\| >=22.12` | **descartada** |

A 11 exigiria Node `>=20.19` (ou `>=22.12`) e a imagem do projeto é
`node:20-alpine`, onde a versão de patch do Node 20 é uma variável que
ninguém controla. Versão **fixada exata** (`"@sentry/nextjs": "10.75.3"`, sem
`^`), como manda a restrição técnica do contrato.

A 10.75.3 também é a que **corrige o advisory que este bloco é sobre**:
`GHSA-6465-jgvq-jhgp` ("Sentry's sensitive headers are leaked when
`sendDefaultPii` is set to `true`") afeta `@sentry/node-core` `10.11.0-10.26.0`.
A primeira versão que instalei foi a 10.17.0 e o `npm audit` acusou esse
advisory **e** `GHSA-8988-4f7v-96qf` (`@opentelemetry/core` < 2.8.0). Subir
para 10.75.3 zerou os dois. Licença: **MIT**.

Estado do `npm audit` antes e depois (evidência, não promessa):

```
antes (só @sentry/nextjs 10.17.0):  9 vulnerabilidades (7 moderate, 1 high, 1 critical)
depois (10.75.3 + vitest 3.2.4):     2 vulnerabilidades (1 high, 1 critical)
```

As 2 restantes são **`next@14.2.15` e o `postcss` aninhado dentro dele**,
**pré-existentes** e fora do escopo deste bloco. O Sentry **não adicionou
nenhuma**.

### 1.2 `allowScripts` — o detalhe que quase passou

`@sentry/cli` (dependência do `@sentry/webpack-plugin`) tem `postinstall` que
baixa o binário. O npm 11.19 **não roda** script de dependência sem
aprovação, e sem o binário o upload de source map falha. O `package.json`
ganhou:

```json
"allowScripts": { "@sentry/cli": true, "esbuild": true }
```

Sem versão (só o nome), de propósito: `npm approve-scripts` grava
`pkg@versão` por padrão, e um dia em que o `@sentry/cli` mudar de versão faria
o upload parar de funcionar **em silêncio** numa instalação limpa. Nome puro
sobrevive à troca.

### 1.3 `next.config.js` — `withSentryConfig` por fora, `output: "standalone"` intacto

```js
module.exports = withSentryConfig(nextConfig, {
  silent: true,
  telemetry: false,
  sourcemaps: { deleteSourcemapsAfterUpload: false },
});
```

- `output: "standalone"` e `skipTrailingSlashRedirect` preservados: o
  `Dockerfile` e o `infra/standalone/run-standalone.sh` (Bloco C1) dependem
  dos dois, e ambos foram **executados** contra este build (seção 6).
- `sourcemaps.deleteSourcemapsAfterUpload: false` — o **default do SDK é
  apagar** os `.map` depois do upload. Num `standalone`, `.next/server` é
  copiado para a imagem final e o smoke do C1 valida a release; apagar
  arquivos do artefato criaria uma diferença entre "build local" e "build com
  credencial" que ninguém procura depois. O custo é uma imagem com source map
  dentro (o `--deleteSourcemapsAfterUpload` manual no CI resolve).
- `telemetry: false` — o `sentry-cli` manda telemetria de uso anônimo durante
  o build. Build não é o lugar para isso.
- `experimental.instrumentationHook: true` declarado **explícito** no
  `nextConfig` (o `withSentryConfig` já ligaria): o arquivo que depende dele
  (`instrumentation.ts`) precisa ser legível sem saber do efeito colateral.
- `org`/`project` **não** foram hardcoded: são lidos de `SENTRY_ORG`/
  `SENTRY_PROJECT` no ambiente de build, e fixar aqui criaria uma segunda
  fonte de verdade. Sem `SENTRY_AUTH_TOKEN` o upload é pulado com aviso.

### 1.4 O mecanismo real de inicialização (e o que o SDK 10 mudou)

Investiguei o pacote instalado em vez de seguir o tutorial. O que mudou no
Sentry 10 e **não** é o que a documentação antiga diz:

1. `sentry.server.config.ts` **não é mais carregado sozinho**. O SDK detecta o
   arquivo e emite aviso: *"put this file's content into the `register()`
   function of a Next.js instrumentation file"*. Por isso criei
   **`frontend/instrumentation.ts`** com `register()` importando
   `./sentry.server.config` no runtime `nodejs`, e `onRequestError` exportado
   (convenção do Next 15; o Next 14.2 ignora, e é retrocompatibilidade grátis).
2. `sentry.client.config.ts` **continua funcionando** (é injetado no entry
   `main-app`), mas emite aviso de depreciação em favor de
   `instrumentation-client.ts` — que é convenção **Next 15.3+** e **nunca seria
   carregada** aqui. Mantive `sentry.client.config.ts` e **documentei o aviso**
   como aceito: migrar junto com o upgrade do Next, não antes.
3. `Next 14.2` só tem o hook de instrumentação com
   `experimental.instrumentationHook` (confirmei em
   `next/dist/build/index.js`, não na documentação).

O único aviso do build é esse, e ele está escrito no arquivo:

```
[@sentry/nextjs] DEPRECATION WARNING: It is recommended renaming your
`sentry.client.config.ts` file, or moving its content to
`instrumentation-client.ts`. ...
```

**Nenhum outro aviso ou erro no build.**

---

## 2. A decisão de canal de release/ambiente

O problema: `NEXT_PUBLIC_*` é **substituído por literal no bundle** (e no
`output: "standalone"` isso é irreversível — o mesmo arquivo serve dev,
homolog e prod na mesma VPS), enquanto `SENTRY_RELEASE` é de runtime e **não
chega ao browser**.

**Decisão: canais opostos, de propósito, nos dois lados.**

| Lado | Ambiente | Release | Por quê |
|---|---|---|---|
| **Browser** | `NEXT_PUBLIC_SENTRY_ENVIRONMENT` (build) | `NEXT_PUBLIC_SENTRY_RELEASE` (build) | o release que o browser reporta **é**, por construção, o SHA do código que ele executa. Um release por variável de runtime seria mentiroso dentro do bundle. |
| **Servidor** | `SENTRY_ENVIRONMENT` (runtime) | `SENTRY_RELEASE` → `RELEASE_SHA` → `GIT_SHA` (runtime), com fallback para o `NEXT_PUBLIC_*` embutido | o artefato standalone é o **mesmo** nos três ambientes; só runtime distingue dev/homolog/prod. Congelar no build faria os três se reportarem com o mesmo nome — que é o erro que quebra alerta por ambiente. |

O **fallback cruzado** (servidor cai no valor embutido) é o que dá uma
resposta útil em build local e em qualquer deploy que não passe a variável de
runtime, em vez da string `local`.

**Preço declarado:** trocar de release no browser **exige rebuild**, e o mesmo
SHA precisa ser passado ao build da API para que `X-Release` (do Django) e
`release` (do Sentry) casem na correlação. Isso está escrito no cabeçalho de
`lib/sentry-cliente.ts` e de `sentry.server.config.ts`.

Detalhe de implementação que é armadilha: as leituras de `process.env` estão
escritas **por extenso** (`process.env.NEXT_PUBLIC_SENTRY_DSN`), nunca por
índice (`process.env[nome]`), porque o Next só substitui a forma literal —
leitura por índice passaria ilesa para o bundle e viraria `undefined` em
produção.

---

## 3. Fail-closed: como está montado (e por que em duas camadas)

`ClientOptions.enabled` do Sentry 10 é **`boolean`, não função** — li
`node_modules/@sentry/core/build/cjs/client.js:492`
(`getOptions().enabled !== false`) e
`build/types/types/options.d.ts:166`. Passar um predicado ali seria
silenciosamente ignorado: `enabled !== false` seria `true` para uma função, ou
 seja, **fail-open**. Por isso:

1. **Camada 1 — carregamento.** Sem `NEXT_PUBLIC_SENTRY_DSN` **ou** sem a
   categoria `tecnico` concedida, `iniciarSentryCliente()` retorna sem
   carregar o pacote. O SDK vira um **chunk separado** e nunca é baixado.
   Evidência do build: o chunk do SDK é
   `.next/static/chunks/node_modules_sentry_nextjs_build_esm_index_client_js.js`
   e ele **não aparece** em nenhum `<script src>` do HTML inicial.
2. **Camada 2 — por evento.** Com o SDK carregado, `beforeSend` e
   `beforeSendTransaction` **reavaliam** o consentimento a cada envio e
   devolvem `null` (o SDK descarta o envelope). É o que faz a **revogação
   valer no instante** em que a pessoa desliga a categoria, sem reinstalar
   nada, e é a mesma forma do backend
   (`config/observability.py::sentry_before_send`).
3. `Sentry.init` é chamado **no máximo uma vez** por sessão de browser. O SDK
   10 avisa no console quando `init` é chamado duas vezes, e esse aviso
   apareceria **justamente no instante em que a pessoa aceita o diagnóstico**.
   O caminho é: na carga, consentimento já concedido → `init`; sem
   consentimento → escuta `EVENTO_CONSENTIMENTO_ALTERADO` e chama `init` na
   primeira concessão. Na revogação, o `beforeSend` já recusa tudo e o
   `close()` do transporte garante que nada em voo saia depois.

**Servidor:** o Next **não tem como saber** o consentimento de um visitante (a
categoria `tecnico` não é sincronizada com o backend — é o "Limite conhecido"
de `lib/cookie-consent.ts`). Então o portão é
`SENTRY_TECHNICAL_CONSENT_DEFAULT`, **mesmo nome e mesmo default (`false`) do
backend**, e a consequência é dita sem eufemismo: **com o default, erros de
SSR não são reportados** até alguém decidir ligar, com a consequência jurídica
assumida. Não inventei header nem cookie para fingir um controle que não
existe.

Fato operacional descoberto no caminho: o `init` do **servidor** é de uso
único por processo (`if (sdkAlreadyInitialized()) return`, e
`sdkAlreadyInitialized()` é `!!getClient()`). Logo, **mudar
`SENTRY_TECHNICAL_CONSENT_DEFAULT` exige reiniciar o processo** — não é
reconfiguração a quente. Isso está no teste e vale para o runbook.

---

## 4. Prova de que o token do `localStorage` não chega ao Sentry

### 4.1 O risco

`frontend/lib/auth-context.tsx` guarda o token DRF em
`localStorage["portal_noticias_token"]` e o manda como `Authorization: Token
<valor>` em toda chamada autenticada. Com o Sentry ligado, ele tem caminhos
plausíveis para dentro de um evento. **Enumerados um a um**, e cada um
tratado:

| # | Vetor | Tratamento | Onde |
|---|---|---|---|
| 1 | `event.user` | removido; `dataCollection.userInfo: false` | `eventoParaEnvio`, `dataCollection` |
| 2 | breadcrumb de `fetch`/`xhr` (`data.url`, `data.body`, `data.headers`) | `url` → `caminhoSeguro`; `body`/`headers`/`request`/`response`/`request_body` removidos | `sanearBreadcrumbs` |
| 3 | `request.headers` / `cookies` / `query_string` / `data` | removidos | `CAMPOS_REQUEST_REMOVIDOS` |
| 3b | `request.env` (no standalone, é o environment do processo: DSN, `API_INTERNAL_URL`...) | removido — **estrito em relação ao backend** | idem |
| 4 | `extra` / `contexts` | `redigirPayload` recursivo | `eventoParaEnvio` |
| 5 | `stacktrace.frames[].vars` — **a variável local `tokenSalvo`/`novoToken` do `AuthProvider` é literalmente o token** | `vars` e `previews` **descartados por inteiro**; `dataCollection.stackFrameVariables: false` | `sanearStacktrace` |
| 6 | `message` / `logentry` / `exception.values[].value` com `token=` embutido | `redigirTexto` | `eventoParaEnvio` |
| 7 | `request.url` com query (`/convinte?token=...`) | `caminhoSeguro` (sem query/fragmento/userinfo) | `sanearRequest` |
| 8 | tag com chave sensível (`Authorization`) | tag **removida**, não redigida | `sanearTags` |
| 9 | token **solto**, com a forma do DRF, em campo cujo nome não diz nada | regex de **40 hex** (formato exato do `rest_framework.authtoken`) | `observabilidade.ts` |

Sobre o #9: `descarta vars` inteiro, em vez de redactar por nome, é mais forte
porque **o nome da variável muda a cada build** (minificação) e a lista de
nomes sensíveis não muda junto.

### 4.2 Como testei

`frontend/testes/sentry-redacao.test.ts`, 26 casos. O método é **negativo por
inspeção do resultado**, não por confiança no SDK: monta-se um evento sintético
com o token **em todas as posições da tabela ao mesmo tempo** e confere-se que
a string do token não aparece em **nenhum byte** de `JSON.stringify(evento)`.
Isso pega também o caminho oblíquo (token dentro de chave desconhecida, dentro
de array aninhado, dentro de breadcrumb).

```
✓ beforeSend: o token do localStorage nao chega ao Sentry
  ✓ nao deixa o token em NENHUM campo do evento serializado
  ✓ nao deixa e-mail, IP completo nem user
  ✓ nao deixa query string nem fragmento na URL do request
  ✓ remove cookies, headers, corpo e env do request inteiro
  ✓ redige a URL e o corpo dos breadcrumbs de fetch/xhr
  ✓ descarta vars e previews dos frames de stacktrace
  ✓ redige a mensagem do evento e o valor da excecao
  ✓ redige tags e remove tag de chave sensivel
  ✓ forca ambiente e release efetivos, ignorando os do proprio evento
  ✓ nao reenvia o sdkProcessingMetadata (chave publica do DSN)
  ✓ aguenta um evento com nesting profundo e listas grandes
  ✓ ignora evento que nao e objeto
✓ fail-closed de consentimento
  ✓ devolve null sem consentimento tecnico — nada e enviado
  ✓ falha ao LER o consentimento tambem e falha fechada
  ✓ reavalia o consentimento a CADA evento (revogacao vale na hora)
```

E `frontend/testes/sentry-servidor.test.ts`, 6 casos, que **importam o
`sentry.server.config.ts` de verdade** e inspecionam as opções com que o
cliente ficou — provando que o arquivo deixou de ser scaffolding inerte:

```
✓ sentry.server.config.ts
  ✓ inicializa de verdade quando ha DSN e consentimento do operador
  ✓ mantem a politica de privacidade do browser no servidor
  ✓ FAIL-CLOSED: sem SENTRY_TECHNICAL_CONSENT_DEFAULT nao inicializa nada
  ✓ FAIL-CLOSED: `false` explicito e o mesmo que ausente
  ✓ sem DSN nao ha cliente nenhum (e o build nao quebra)
  ✓ o beforeSend do servidor redige o mesmo que o do browser
```

### 4.3 Bug herdado que o teste encontrou (e que é do backend também)

O teste de redação pegou um furo **já existente** em
`redact_text`/`redigirTexto`: o padrão
`(authorization|...)[:=]\s*[^\s,;&]+` casa até o primeiro espaço, então

```
"Authorization: Token abc123"  ->  "Authorization=[REDACTED] abc123"
```

**o valor do token ficava no texto.** É exatamente o formato que o
`api.ts` monta em toda chamada autenticada. Corrigi no frontend (regra
`CABECALHO_AUTORIZACAO` + `Token <valor>` + 40-hex solto).

**Achado para o dono do backend (A2) — `backend/config/observability.py` tem o
mesmo furo.** `redact_text` tem `_BEARER` (cobre `Bearer`) mas **não tem regra
para o esquema `Token` do DRF**, e `_SECRET_ASSIGNMENT` para no espaço. Um log
com `Authorization: Token <drf-token>` vaza o valor. Não toquei em `backend/`
(escopo do bloco), então fica registrado aqui e para o
`implementation-history.md`.

Também corrigi, no mesmo teste: `caminhoSeguro` devolvia `limite + 1`
caracteres (o `…` contava fora do teto) e `semControle` não removia o bloco
C1 (`0x80`-`0x9f`), que `normalizarRequestId` já tratava como inválido.

---

## 5. Cliente do token de consentimento (critérios 25 e 26) — fecha a pendência

O A2 deixou o backend exigindo token assinado e **ninguém emitindo**: cada
evento era recusado com `consent_ausente` e a analytics estava parada. Entregue
em `lib/consent-token.ts` (+ `lib/api.ts::pedirTokenConsentimento` e o
`track()` em `lib/analytics.ts`).

Decisões que valem:

- **O cliente não assina e não decodifica.** O envelope
  `v1.<payload_b64url>.<assinatura_b64url>` é tratado como string opaca. O
  `exp` de que precisamos vem no **corpo da resposta do emissor**
  (`{token, categoria, sub, exp, ttl_segundos}`), e não de "decodificar sem
  verificar": sem a chave, a assinatura é indetectável, e um cliente que
  decodifica está a um passo de achar que pode validar. Quem verifica é o
  backend, sempre.
- **`sessionStorage`, não `localStorage`.** A claim `sub` do token é a sessão e
  o backend rejeita (`sujeito_invalido`) reaproveitamento em outra; guardar por
  mais tempo seria manter um segredo vivo sem uso.
- **Validação do envelope no cliente**: três partes, versão `v1`, sem
  espaçamento, dentro de `MAX_TOKEN_BYTES`. Reprovar aqui evita um
  `consent_malformado` em produção, que é muito mais difícil de diagnosticar.
- **Renovação antecipada, sem polling.** Janela de 5 min
  (`JANELA_RENOVACAO_SEGUNDOS`): o token dentro da janela **ainda é usado** (o
  backend aceita até `exp`) e a reemissão dispara em paralelo. Não há timer de
  fundo, o que respeita a restrição de performance do contrato; e a troca de
  chave de assinatura — a revogação de que a run precisa — passa a ter janela
  de 5 min em vez de 24 h.
- **Deduplicação de emissão**: um `page_view` + três cliques no primeiro
  segundo não disparam quatro pedidos ao emissor (que é rate-limitado a
  `30/min`).
- **Fila com teto de 50.** O primeiro evento da sessão vai para a fila e só é
  despachado quando o token chega. Teto porque um visitante sem consentimento
  de analytics não pode acumular memória com eventos que jamais sairão.
- **Revogação apaga o token na hora** (`observarConsentimentoAnalytics`). O
  backend continuaria aceitando aquele token até o `exp`, porque a assinatura
  é válida — continuar usando depois da revogação seria um vazamento que
  ninguém perceberia.
- **Header em vez de corpo.** `X-Consent-Token` é o caminho preferido (o token
  não entra no corpo, e corpo é o que um log de proxy poderia guardar).
  `anexarTokenAoCorpo`/`cabecalhoConsentimento` existem para o caminho do
  `sendBeacon`, que não permite header — e o beacon ficou como **último
  recurso sem token** (perder um evento é melhor que enviar um pedido
  recusado).

### 5.1 Prova com o backend real (não simulada)

O Django de dev estava no ar em `localhost:8000`. `testes/integracao-backend.test.ts`
roda **7 casos reais** e é opt-in por variável de ambiente, para `npm test` na
CI não tocar em nada:

```
B2_INTEGRACAO=1 B2_API_BASE=http://localhost:8000 npx vitest run
```

```
✓ o cliente aceita o envelope que o emissor real devolve
✓ SEM token o backend recusa e nao persiste (criterio 26)      -> 202 {"registrado": false, "motivo": "consent_ausente"}
✓ COM token o backend persiste o evento (criterios 25 e 26)     -> 201 {"registrado": true}
✓ token de outra sessao e recusado (o token nao e bem publico) -> 202 {"motivo": "consent_sujeito_invalido"}
✓ token adulterado e recusado (a assinatura e verificada no servidor) -> 202 consent_assinatura_invalida
✓ o track() do analytics ANEXA o token ao evento (o caminho real do portal)
✓ o evento com token e aceito de verdade pelo backend
```

O caso do `track()` intercepta o `fetch` e inspeciona **o que saiu de fato**:
o header `X-Consent-Token` presente, com três partes, e **o corpo sem o token**.

Confirmação no banco (Django, `EventoSite`):

```
eventos persistidos com o token do cliente B2: 2
  tipo=page_view path=/ dispositivo=desktop origem=direto
```

**A primeira execução deste teste pegou uma divergência minha:** eu assumi
HTTP 202 para o caso de sucesso e o backend devolve **201** (conferido em
`EventoIngestaoView.post`). A suíte pura não pegaria isso; a de integração
pegou. É exatamente para isso que ela existe.

### 5.2 Web Vitals e telemetria técnica

**Vão pelo caminho de consentimento técnico, separado do analytics**, e sem
dependência nova: `browserTracingIntegration` (default do
`@sentry/nextjs` no browser) registra Web Vitals como spans da transação de
pageload, e a transação só sai se passar por `beforeSendTransaction` (que é o
mesmo portão de consentimento técnico) e por `tracesSampleRate: 0.1`.
**Não** importei `webVitalsIntegration` de `@sentry/browser`: ele não é
reexportado pelo `@sentry/nextjs` e seria depender de uma transitiva. Não
criei endpoint técnico novo.

---

## 6. Dependências adicionadas (versão e justificativa)

| Pacote | Versão | Tipo | Licença | Justificativa |
|---|---|---|---|---|
| `@sentry/nextjs` | `10.75.3` (exata) | produção | MIT | Critérios 6 e 20. Peer `next` aceita `^14`; **evita** o advisory `GHSA-6465-jgvq-jhgp` (vazamento de header sensível com `sendDefaultPii: true`) e o `GHSA-8988-4f7v-96qf` (`@opentelemetry/core`), ambos presentes na 10.17.0. A 11 foi descartada por `engines.node >=20.19`, incompatível com o `node:20-alpine` do `Dockerfile` sem travar a versão de patch. |
| `vitest` | `3.2.4` (exata) | dev | MIT | Critério 39. **Autorização explícita do orchestrator.** `environment: "node"` (lógica pura), sem `jsdom` e sem Testing Library. |

Nada mais foi adicionado. `eslint` **não** foi adicionado (ver seção 8).

---

## 7. Validação — saída REAL

Ambiente: Node `v24.21.0`, npm `11.19.0`, Next `14.2.15`, Django de dev no ar
em `localhost:8000`.

### 7.1 Typecheck

```console
$ npx tsc --noEmit
(sem saída)
exit=0

$ npm run typecheck
> tsc --noEmit
exit=0
```

### 7.2 Testes

```console
$ npm test
 ↓ testes/integracao-backend.test.ts (7 tests | 7 skipped)
 ✓ testes/janela-stale.test.ts (7 tests) 35ms
 ✓ testes/request-id.test.ts (14 tests) 89ms
 ✓ testes/sentry-redacao.test.ts (26 tests) 76ms
 ✓ testes/consent-token.test.ts (20 tests) 28ms
 ✓ testes/consentimento-e-payload.test.ts (9 tests) 32ms
 ✓ testes/sentry-servidor.test.ts (6 tests) 1016ms

 Test Files  6 passed | 1 skipped (7)
      Tests  82 passed | 7 skipped (89)

$ B2_INTEGRACAO=1 B2_API_BASE=http://localhost:8000 npm test
 Test Files  7 passed (7)
      Tests  89 passed (89)
```

### 7.3 Build

```console
$ npm run build
  ▲ Next.js 14.2.15
  - Environments: .env.local
  - Experiments (use with caution):
    · instrumentationHook
   Creating an optimized production build ...
[@sentry/nextjs] DEPRECATION WARNING: It is recommended renaming your
`sentry.client.config.ts` file, or moving its content to
`instrumentation-client.ts`. ...       <-- único aviso; aceito e documentado
 ✓ Compiled successfully
   Linting and checking validity of types ...
   Generating static pages (56/56)
BUILD_EXIT=0
```

Artefatos conferidos depois do build:

```
$ find .next -name "*.map" | wc -l
254                              # source maps gerados (base do upload)

$ find .next/standalone -name "instrumentation*"
.next/standalone/.next/server/instrumentation.js         # hook presente
.next/standalone/.next/server/instrumentation.js.map

$ ls .next/standalone/
node_modules  package.json  public  server.js            # standalone intacto

# o chunk do SDK é separado e NÃO está no HTML inicial:
$ grep -o 'src="[^"]*chunks[^"]*"' .next/server/app/index.html
src="/_next/static/chunks/fd9d1056-...js" ... src="/_next/static/chunks/1841-...js"
   (nenhum deles é o chunk do @sentry/nextjs)
```

### 7.4 Standalone real (compatibilidade com o Bloco C1)

```console
$ bash infra/standalone/run-standalone.sh prepare
[standalone] .next/static copiado de .../frontend/.next/static
[standalone] prepare concluído
exit=0

$ bash infra/standalone/run-standalone.sh smoke
[standalone] subindo o servidor em 127.0.0.1:37587 (timeout 60s)
[standalone] GET /robots.txt -> 200
[standalone] GET /_next/static/chunks/13-9e3e520d88a77c9b.js -> 200
[standalone] GET / -> 200
[standalone] smoke aprovado: a release serve /robots.txt, assets de .next/static e a Home (200)
exit=0
```

Servidor standalone em pé, com o proxy de API real:

```console
$ PORT=3998 API_INTERNAL_URL=http://127.0.0.1:8000 node .next/standalone/server.js
 ✓ Ready in 949ms
$ curl -o /dev/null -w "%{http_code}" http://127.0.0.1:3998/            -> 200
$ curl -o /dev/null -w "%{http_code}" http://127.0.0.1:3998/api/gating/status/ -> 200
```

### 7.5 Scripts de verificação existentes (nenhum regrediu)

```console
$ npm run test:conteudo-ficticio
[OK] frontend/lib/**: sem array/objeto de demonstração — 41 arquivo(s) de fonte varridos
[OK] lib/recomendacao.ts: carregarHome existe e propaga falha ...
[OK] app/page.tsx: falha real é tratada (janela de stale + honestidade) ...
[OK] app/api/[...path]/route.ts: timeout, teto de body e correlação ...
Nenhum fallback fictício encontrado nas páginas de produção.
exit=0

$ npm run test:query-client
[OK] queries.ts: hooks de leitura usam queryKeys.* — 27 hook(s) ...
[OK] queries.ts: nenhuma queryKey recebe token como argumento ...
[OK] telas de decisão: hooks com staleTime 0 são permitidos ...
[OK] frontend/app/**: sem persistQueryClient/createAsyncStoragePersister — 67 arquivo(s) varridos
Política de cache do query client OK.
exit=0

$ npm run test:datas-tz
{"tz":"(não definido)","dataCivil":"23/09/2026",...}
exit=0
```

### 7.6 `npm run lint` — **NÃO RODOU**, e por quê

```console
$ npm run lint
> next lint
? How would you like to configure ESLint? https://nextjs.org/docs/basic-features/eslint
 ❯ Strict (recommended)
   Base
   Cancel ⚠ If you set up ESLint yourself, we recommend adding the Next.js ESLint plugin.
LINT_EXIT=1
```

`next lint` **não tem o que rodar**: não existe `.eslintrc*` no projeto e
`eslint`/`eslint-config-next` **não estão instalados**. Ele abre o assistente
interativo e sai com 1. Instalar ESLint **não** estava na autorização deste
bloco (que foi explícita e apenas para `vitest`), e criar um `.eslintrc` sem
o plugin seria um gate vazio — pior que nenhum: a CI passaria "rodando lint" sem
nenhuma regra aplicada.

Pendência aberta, com o caminho: instalar `eslint` + `eslint-config-next`
fixados, criar `frontend/.eslintrc.json` com `{"extends": "next/core-web-vitals"}`
e rodar uma vez para ver o passivo. **Isso é decisão do orchestrator**, porque
introduz uma dependência nova e um gate que pode reprovar build por estilo.

### 7.7 O que NÃO foi executado

1. **Browser** — não há navegador conectado nesta sessão, então o caminho
   "banner → aceitar → SDK carrega → evento sai" **não** foi verificado no
   navegador. O que cobre esse caminho foi coberto por outras vias: a política
   em `sentry-servidor.test.ts` (importando o módulo de verdade) e o
   `track()` real no teste de integração com o backend. O que **não** está
   coberto é a camada de DOM (`localStorage` real, listener do
   `CustomEvent`, `dynamic import` do chunk sob demanda).
2. **Upload de source map de verdade** — exige `SENTRY_AUTH_TOKEN` de uma conta
   Sentry real (credencial que não tenho e que não deve estar em repositório).
   O que foi verificado: os 254 `.map` são gerados, o plugin roda sem quebrar
   o build sem token, e a ausência de token não é um verde silencioso (o aviso
   aparece). O upload em si é o item C2.4.
3. **Entrega de evento no Sentry** — mesma razão: nenhum evento foi de fato
   entregue a um projeto Sentry.
4. **Comportamento de DOM** (error boundary renderizando, banner de
   consentimento) — sem `jsdom`/Testing Library, por decisão de escopo.

---

## 8. Pendências

### 8.1 Para o Bloco C2 (`.github/` está bloqueado para mim)

1. **Rodar `npm test` e `npm run typecheck` na CI** (critério 39). Os scripts
   já existem e `npm run verificar` encadeia typecheck + testes + os três
   `verificar-*.mjs`.
2. **C2.4 — source maps**: passar `SENTRY_AUTH_TOKEN` como secret, mais
   `SENTRY_ORG`/`SENTRY_PROJECT`/`SENTRY_RELEASE`, no job de build. Com
   `NEXT_PUBLIC_SENTRY_*` também preenchidas (o `Dockerfile` já tem os `ARG`).
   **Recomendação minha**: o job **tem que falhar** se `SENTRY_AUTH_TOKEN`
   estiver ausente no build de produção. Do jeito que está, upload sem token é
   um aviso no log e um build verde — ou seja, um "verde" que significa
   "sem source map". Um `if [ -z "$SENTRY_AUTH_TOKEN" ] && [ "$AMBIENTE" = producao ]; then exit 1; fi`
   é uma linha e fecha o buraco.
3. **Não quebrar a CI com o aviso de depreciação**: ele é
   `console.warn` durante o build e não falha nada. Se algum passo da CI tratar
   stderr como erro, precisa filtrar essa linha.
4. **`lint`**: se o orchestrator autorizar ESLint, o passo de lint passa a
   existir na CI. Enquanto isso, **não** anunciar "lint passa" — ele não roda.

### 8.2 Pendências humanas (credencial/decisão)

1. **Criar o projeto no Sentry** e preencher `NEXT_PUBLIC_SENTRY_DSN` +
   `SENTRY_ORG` + `SENTRY_PROJECT`. O DSN é público por definição (vai no
   bundle); o `SENTRY_AUTH_TOKEN` é segredo e só vai no build.
2. **Decidir `SENTRY_TECHNICAL_CONSENT_DEFAULT` em produção.** Com `false`
   (default), erros de SSR **não** são reportados. Isso é a escolha honesta e
   fail-closed, mas precisa ser uma decisão registrada, não um esquecimento.
   Note que a categoria `tecnico` **não** é sincronizada com o backend
   (achado herdado do B1), então o servidor do Next não tem como saber o
   consentimento de um visitante.
3. **`PROD_DECISOES.md` / `CI-CD.md` / `infra/DEPLOY.md`** estão bloqueados
   para este bloco: o canal de release (build para o browser, runtime para o
   servidor) e a lista de `ARG`/`ENV` novos precisam entrar na documentação de
   deploy. O conteúdo está pronto aqui e nos cabeçalhos do `Dockerfile`.
4. **Textos legais de privacidade**: a coleta de analytics voltou a acontecer.
   A política e o banner **não mudaram** (o texto já era o do Bloco A1/A2), mas
   a validação humana dos textos é exigida pelo contrato e continua pendente.

### 8.3 Variáveis que faltam em `frontend/.env.local.example`

**Não toquei no arquivo** (outro agente está nele). O bloco "Telemetria do
frontend" que o C1 deixou lá precisa ser substituído por este conteúdo, com
placeholders obviamente falsos:

```bash
# --- Sentry: canal BUILD -> browser (criterios 6 e 20) ---------------------
# Estas tres sao EMBUTIDAS no bundle no BUILD. Em `output: "standalone"` isso
# e irreversivel: o mesmo artefato roda em dev/homolog/prod. Rebuildar para
# trocar o release.
# O DSN NAO e segredo (vai no bundle e a chave publica esta dentro dele).
NEXT_PUBLIC_SENTRY_DSN=
NEXT_PUBLIC_SENTRY_ENVIRONMENT=development
NEXT_PUBLIC_SENTRY_RELEASE=

# --- Sentry: canal BUILD (upload de source map) ----------------------------
# SENTRY_ORG/SENTRY_PROJECT sao metadados publicos. SENTRY_AUTH_TOKEN e
# SEGREDO: so no build, nunca no runtime, nunca no repositorio.
SENTRY_ORG=
SENTRY_PROJECT=
SENTRY_AUTH_TOKEN=
# Release do upload. Sem SENTRY_AUTH_TOKEN o upload e pulado com aviso e o
# build continua (comportamento correto em dev).
SENTRY_RELEASE=

# --- Sentry: canal RUNTIME (servidor standalone) --------------------------
# O MESMO artefato roda nos tres ambientes, so o runtime distingue. Precedencia:
# SENTRY_* > NEXT_PUBLIC_* (embutido no build).
# SENTRY_TECHNICAL_CONSENT_DEFAULT: mesmo nome e mesmo default (false) do
# backend. Com false, erros de SSR NAO sao. Mudar exige REINICIAR o processo
# (o init do Sentry e de uso unico por processo).
SENTRY_ENVIRONMENT=
SENTRY_RELEASE=
SENTRY_DSN=
SENTRY_TECHNICAL_CONSENT_DEFAULT=false
```

O texto atual do arquivo ("Nenhuma variável nova é declarada aqui de
propósito... pertencem ao bloco de frontend") está agora **desatualizado**:
o bloco de frontend existe e as variáveis são estas.

### 8.4 Achado residual para o dono do backend — verificado no codigo em voo

O furo que o teste encontrou **ja foi corrigido no backend por outro agente,
em voo** (`_AUTH_SCHEME` com `Bearer|Basic|Token` e uma regra que consome o
valor inteiro de `Authorization`/`Proxy-Authorization`). Conferi o comportamento
atual rodando o redator do backend de verdade:

```
$ cd backend && .venv/bin/python -c "... redact_text ..."
ok      | Authorization=[REDACTED]
ok      | Token [REDACTED]
ok      | falha com token=[REDACTED]
VAZOU   | a1b2c3d4e5f60718293a4b5c6d7e8f9012345678        <-- token SOLTO
ok      | Authorization: Basic ZGV2OnNlcmV0YQ==  ->  [REDACTED]
ok      | /api/x?token=[REDACTED]
ok      | [REDACTED_EMAIL]
```

**O que ainda falta no backend:** o token **solto**, sem rotulo, com a forma do
DRF (40 hex minusculos, `rest_framework.authtoken`). Nenhuma regra do
`redact_text` pega, e `redact_payload({"sessao": <token>})` devolve o valor
intacto — porque a chave `sessao` nao e sensivel por nome. No frontend isso
esta coberto pela regra de 40 hex (`observabilidade.ts::TOKEN_DRF`); no
backend, nao.

Por que importa: um frame de excecao, um breadcrumb ou um `extra` de Django
que carregue o token por outro caminho (uma variavel interpolada, um
`logger.info("%s", token)`) vaza o valor sem que nenhuma regra por nome ou por
rotulo o alcance. Como sempre em telemetria, o teste e o que prova — e
`backend/config/tests/test_observability_redaction.py` e o lugar natural para a
regra nova. Nao toquei em `backend/` (escopo do bloco).

### 8.5 Outras pendências menores

- **Teste de DOM**: `error boundary` renderizando e `banner de cookies`
  continua sem suíte automatizada. Precisa de `jsdom` + Testing Library (ou
  Playwright), que é dependência nova e escopo maior.
- **Migrar `sentry.client.config.ts` → `instrumentation-client.ts`**: só junto
  com o upgrade do Next para 15.3+. Anotado no próprio arquivo.
- **`sentry.edge.config.ts`**: não existe porque o projeto não usa runtime
  `edge` (não há `middleware.ts`). Se alguém introduzir edge, o `register()`
  precisa de um segundo ramo — está comentado lá para não virar substituição
  silenciosa.
- **A categoria `tecnico` ainda não é sincronizada com o backend** (achado do
  B1, `PreferenciasCookiesSerializer` só aceita `analytics` e
  `personalizacao`). É o que mantém o Sentry do servidor dependente de uma
  variável de operador.

---

## 9. Arquivos tocados

Novos:

```text
frontend/instrumentation.ts              hook de instrumentação (Next 14.2)
frontend/lib/sentry-opcoes.ts            política do Sentry (puro, sem SDK)
frontend/lib/sentry-cliente.ts           casca de runtime do browser
frontend/lib/consent-token.ts            cliente do token de consentimento
frontend/vitest.config.ts
frontend/testes/request-id.test.ts               14 casos
frontend/testes/sentry-redacao.test.ts           26 casos
frontend/testes/sentry-servidor.test.ts           6 casos
frontend/testes/consent-token.test.ts            20 casos
frontend/testes/consentimento-e-payload.test.ts   9 casos
frontend/testes/janela-stale.test.ts              7 casos
frontend/testes/integracao-backend.test.ts        7 casos (opt-in)
```

Modificados:

```text
frontend/package.json           +@sentry/nextjs, +vitest, +allowScripts, +scripts
frontend/package-lock.json      (gerado)
frontend/next.config.js         withSentryConfig
frontend/sentry.client.config.ts
frontend/sentry.server.config.ts
frontend/Dockerfile             ARG/ENV de build e de runtime
frontend/lib/observabilidade.ts redigirPayload/chaveSensivel/redigirJson + correções
frontend/lib/api.ts             pedirTokenConsentimento
frontend/lib/analytics.ts       fila, token e fail-closed
frontend/app/error.tsx          captura no Sentry
frontend/app/global-error.tsx   captura no Sentry
```

**Não tocados** (bloqueados por instrução): `.github/`, `infra/`,
`docker-compose*.yml`, `backend/`, `CI-CD.md`, `PROD_DECISOES.md`,
`infra/DEPLOY.md`, `scripts/release/`, `frontend/.env.local.example`,
`run-state.json` desta run, e as runs `20260924-*` /
`20260925-1433-go-live-producao`.
