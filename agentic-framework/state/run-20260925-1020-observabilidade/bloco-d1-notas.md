# Bloco D1 — fechar os gates de frontend na CI

Run `20260925-1020-observabilidade` · branch `observability-20260925-1020` · critério **39**
(*"Dado uma alteração de frontend, quando a CI roda, então typecheck, lint, build e testes de
comportamento de erro/consentimento passam"*) e critério **20** (source maps no Sentry).

## O estado que foi encontrado

`ci.yml`, job `frontend-build`, tinha **2 dos 4** passos do critério 39:

| passo | existia? | como estava |
|---|---|---|
| `npm ci` | sim | — |
| datas em UTC/Tokyo | sim | `verificar-datas-tz.mjs` ×2 |
| cache do query client | sim | `verificar-query-client.mjs` |
| **conteúdo fictício** | **não** | o script existia desde o B1, rodava só local |
| **testes de comportamento** | **não** | `vitest@3.2.4` instalado desde o B2, 89 testes, nenhum na CI |
| typecheck | sim | `npx tsc --noEmit` solto, apesar de existir o script `typecheck` |
| **lint** | **não** | script `lint` = `next lint`, **sem `eslint` e sem `.eslintrc`**: abria o assistente interativo do create-next-app e saía com 1 |
| build | sim | `npm run build` |
| source maps | sim | fail-open em duas camadas (C2.4) |

Ou seja: das três verificações que existem no repositório e não rodavam na CI, duas eram gates
de **segurança de conteúdo** (fictício) e de **comportamento de consentimento** — exatamente o
que o critério 39 nomeia. E o quarto item do critério era um comando que não executava.

## 1. O que foi ligado (e como cada passo se bloqueia)

Sequência final de `frontend-build`:

```
npm ci
→ datas UTC/Tokyo
→ cache do query client
→ test:conteudo-ficticio     (novo)
→ npm test                   (novo)
→ npm run typecheck          (era `npx tsc --noEmit`)
→ npm run lint               (novo)
→ npm run build
→ gate do Sentry → upload
```

**Sobre `if:`** — nenhum passo novo tem `if:`, e essa é a escolha. Sem `if:`, o GitHub Actions
aplica `success()` implícito: teste vermelho **não** gera build, build vermelho **não** gera
upload. `if: always()` em gate seria o oposto do que se quer — o job inteiro continuaria
rodando e o resumo mostraria build verde ao lado de teste quebrado. Ordem de execução diferente
da ordem de enumeração do critério 39 (que lista build antes de testes) porque **construir o que
já falhou no teste só gasta minuto de runner**; a conjunção do critério é a mesma.

**`npm test` sem Django.** A marcação do B2 é `const ATIVO = process.env.B2_INTEGRACAO === "1"`
em `testes/integracao-backend.test.ts:31`, com `describe.skipIf(!ATIVO)`. Ou seja, a flag
**liga** os 7 testes de integração; sem ela eles nem são coletados. O passo da CI declara
`B2_INTEGRACAO: ""` de propósito, e não por acaso:

1. o runner não tem Django no ar, e um teste de integração que falha por ausência de serviço
   mede a máquina, não o código;
2. fixar `""` neutraliza a variável se alguém a exportar no runner — sem isso, um
   `B2_INTEGRACAO=1` vazado transformaria o gate em instável e ele seria desativado "por causa do
   CI", que é como gate morre.

O opt-in continua disponível para quem tem backend no ar:
`B2_INTEGRACAO=1 B2_API_BASE=http://localhost:8000 npx vitest run testes/integracao-backend.test.ts`.

**`typecheck` pelo script.** O `npx tsc --noEmit` solto foi trocado por `npm run typecheck`, que é
o mesmo `tsc --noEmit`. A versão com `npx` permitia que a CI e o script divergissem sem ninguém
perceber (basta alguém editar o script).

## 2. Lint: o número medido e a decisão

### 2.1 Instalação

`eslint@8.57.1` + `eslint-config-next@14.2.15` em `devDependencies` (`--save-exact`).
A versão do config é **igual** à do `next` do `package.json`, e o eslint 8 é o que o
`peerDependency` do `eslint-config-next@14.2.15` aceita (`^7.23.0 || ^8.0.0`).
`frontend/package-lock.json` foi regenerado: **312 pacotes novos, 0 removidos, 0 versões
alteradas** (verificado por diff de nós do `packages` do lock) — a mudança é aditiva.

### 2.2 Baseline medido, ANTES de qualquer correção

| perfil | erros | avisos | arquivos |
|---|---|---|---|
| `next/core-web-vitals` (padrão do Next 14.2) | **0** | **8** | 7 |
| `next/core-web-vitals` + `next/typescript` | **61** | 8 | 35 |

Os 8 avisos do perfil adotado, arquivo:linha:

```
app/admin/fila/page.tsx:72      x2  react-hooks/exhaustive-deps ('itens' conditional)
app/admin/limites/page.tsx:64    x2  react-hooks/exhaustive-deps ('itens' conditional)
app/comunidade/[id]/page.tsx:72      react-hooks/exhaustive-deps (missing dep 'pub')
components/HomeClient.tsx:87        react-hooks/exhaustive-deps (unnecessary dep 'leiturasTick')
components/home/EmAlta.tsx:34        react-hooks/exhaustive-deps (unnecessary dep 'feed')
components/ImagemNoticia.tsx:77      @next/next/no-img-element
```

### 2.3 Decisão: adoto o perfil padrão do Next 14.2 e torno o gate bloqueante

O número que manda na decisão **não** é 61, é **0**: com o perfil que o próprio Next 14.2
escreveria neste projeto (`next/core-web-vitals`), o código **já não tinha nenhum erro**. Os 61
erros do preset `next/typescript` são um **endurecimento que o projeto nunca adotou**, e a
composição deles diz por que não é remediação de uma tarde:

- **27** `@typescript-eslint/no-explicit-any` — em fronteira de API (`lib/api.ts`,
  `lib/consent-token.ts`, `app/api/[...path]/route.ts`), onde o `any` é deliberado;
- **27** `@typescript-eslint/no-unused-vars` — quase todos parâmetros de callback deliberadamente
  ignorados (`(_, x) => ...`), que se resolve com `argsIgnorePattern`, não com mexer em 27
  arquivos;
- **4** `@typescript-eslint/no-empty-object-type` e **2** `prefer-const` (mecânicos).

Os 27 `no-explicit-any` exigiriam inventar tipos em ~30 arquivos de UI e API que **não têm
suíte de comportamento** (o próprio B2 registra que o comportamento de DOM continua sem
automação). Mudar tipagem em produção sem rede de teste é trocar um risco pequeno e conhecido por um
risco que ninguém consegue medir — exatamente a remediação massiva e alheia ao escopo que o D1
pediu para não fazer. Então:

- **Adotado agora:** `next/core-web-vitals`, escopo `--dir .`, `--max-warnings 0`, **gate
  bloqueante**. Baseline medido **0 erros / 0 avisos** depois das correções abaixo.
- **Registrado como decisão pendente** (ver §5): adotar `next/typescript` exigiria 1 run
  própria, começando por `argsIgnorePattern` para os 27 `no-unused-vars` (config, não código) e
  só então decidindo o que fazer dos 27 `any`. Medido **hj**: **60 erros em 31 arquivos**
  (27 `no-explicit-any`, 27 `no-unused-vars`, 4 `no-empty-object-type`, 2 `prefer-const`).

O `--max-warnings 0` é o que faz "0 avisos" valer alguma coisa: sem ele, `next lint` sai 0 com
aviso, e o próximo aviso nasce silencioso.

### 2.4 As 8 correções (por que cada uma é segura)

O gate só pode ser estrito se o baseline for 0/0 — e ele só ficou 0/0 porque os 8 avisos foram
corrigidos de verdade, não silenciados:

1. **`app/admin/fila/page.tsx`** — `const itens = consultaFila.isError ? [] : (...)`. O literal
   `[]` do ternário criava referência nova **a cada render**, e os `useMemo` de `cats`/`filtrados`
   perdiam a memoização a cada render. Virou `useMemo(...)` sobre uma `const VAZIO: Item[]` de
   módulo. Nenhuma mudança de semântica: mesma lista vazia, mesma política fail-closed.
2. **`app/admin/limites/page.tsx`** — mesma causa, mais um agravante: `((...results as unknown as
   Lim[]) || [])` alocava array novo mesmo no caminho de sucesso. `?? VAZIO` + `useMemo`.
3. **`app/comunidade/[id]/page.tsx`** — a condição `!pub` **lê** estado e não estava nas
   dependências. Adicionado. Sem ciclo: `setPub(pubQuery.data)` recebe a mesma referência do
   cache a cada render, e `setEditVals` só corre quando `pubQuery.data` muda de fato.
4. **`components/HomeClient.tsx`** — `leiturasTick` saiu das deps do memo de `leituras`: o único
   lugar que o incrementa é o efeito de montagem logo abaixo, que **também** seta `hidratado`, e é
   esse `hidratado` que já dispara a releitura. Listar os dois só produzia uma dependência que,
   sozinha, nunca mudaria o resultado.
5. **`components/home/EmAlta.tsx`** — `feed` saiu das deps de `sinais`: `lerSinaisLocais` só lê o
   localStorage da **categoria**, e o memo de `ranking` já depende de `feed` diretamente. O
   efeito era reordenar sinais idênticos a cada item novo.
6. **`components/ImagemNoticia.tsx`** — `@next/next/no-img-element` é a **única** exceção, e ela
   é deliberada, com o motivo escrito na linha: a origem é qualquer host de RSS (sem allowlist),
   o `srcSet` de picsum é montado no componente (o `next/image` é dono do srcset) e a cadeia de
   fallback depende de `onError` com fases. Migrar exigiria `images.remotePatterns` aberto —
   trocaria hotlink bloqueado por erro de configuração, que é exatamente o defeito que o
   componente existe para resolver. Uma exceção **de arquivo, com justificativa**, e não um
   `--quiet` global.

### 2.5 Escopo do lint, verificado e não presumido

`--dir .` no script, porque os defaults do `next lint` são `app`, `components`, `lib`, `pages`,
`src` — e deixariam **fora** `instrumentation.ts`, `sentry.client.config.ts`,
`sentry.server.config.ts`, `tailwind.config.ts`, `testes/` e `scripts/`, ou seja, justamente os
arquivos de observabilidade desta run. Verificado com uma **sonda** (arquivo temporário na raiz
com `<img>`, removido depois): detectada por `--dir .`, e o aviso virou `exit 1` sob
`--max-warnings 0`. Baseline idêntico nos dois escopos: os 8 avisos estavam todos em
`app/components`, ou seja, `--dir .` **não** introduz achado novo.

Consequência do eslint passar a existir: **`next build` agora roda o lint internamente** ("Linting
and checking validity of types") e falha o build se o lint falhar. É defesa em profundidade e
custa o linter rodando duas vezes; o default do Next foi mantido em vez de desligado.

## 3. Source maps: fail-open fora de produção, fail-closed em produção

Sem duplicar lógica: **um passo só de shell**, e o que muda é o **input booleano**
`sentry_exigido` (`ci.yml`) repassado por `deploy.yml` e ligado em `deploy-prod.yml`.

| caminho | `sentry_exigido` | sem credencial | sem `.map` | sem binário `sentry-cli` | falha do upload |
|---|---|---|---|---|---|
| PR / fork / `push` develop\|main | `false` (default) | `::notice::`, segue | `::notice::`, segue | `::warning::`, segue | não bloqueia |
| `deploy-prod` (produção) | `true` | **`::error::`, exit 1** | **`::error::`, exit 1** | **`::error::`, exit 1** | não bloqueia |

O **gate** é fail-closed em produção; o **upload** continua `continue-on-error: true` nos dois
caminhos. A linha que separa as duas coisas não é "produção x não produção": é **erro de
configuração, determinístico** (credencial ausente, mapa não gerado, CLI não empacotado — nada
disso se resolve sozinho, e tudo isso tem conserto que não é esperar) **versus
indisponibilidade transitória de terceiro** (rede do Sentry caiu; o argumento do C2.4 continua
valendo: isso não pode virar indisponibilidade de deploy). Os três itens fail-closed foram
reunidos no passo que já decidia o `habilitado`, e a contagem de `.map` foi para lá justamente
para não ter dois `find` able to divergir.

**Testado de verdade.** O `run:` do passo foi extraído do YAML e executado em 7 cenários com um
`.next` e um `node_modules/.bin` falsos — 7/7 passaram com o `exit` e o conteúdo de
`$GITHUB_OUTPUT` esperados (T1 sem token+exigido → 1; T2 sem token+PR → 0; T3 token sem
org/project+exigido → 1; T4 credencial+7 maps+exigido → 0 e `habilitado=true`; T5 sem maps
+exigido → 1; T6 sem maps+PR → 0; T7 sem binário+exigido → 1).

**Precondições do gate verificadas num build real:** `npm run build` produziu **254** arquivos
`.map` em `.next`, e `node_modules/.bin/sentry-cli` existe (transitiva do `@sentry/nextjs`, como
o C2.4 documentou). O fail-closed de produção não vai reprovar um build correto.

**Consequência operacional, deliberada:** o **primeiro deploy por tag depois deste merge vai
reprovar** se `SENTRY_AUTH_TOKEN`/`SENTRY_ORG`/`SENTRY_PROJECT` não estiverem cadastrados no
repositório. Isso é o comportamento pedido, e o conserto é cadastrar o secret — não desligar o
gate. Está escrito no `deploy-prod.yml` para quem for promote releases.

## 4. Evidência de execução (saída real, não resumo)

Ambiente: `frontend/`, Node 24.21.0 local, npm do mesmo. `actionlint` 1.7.7 (o do Bloco C2, em
`/tmp/actionlint`).

| verificação | comando | resultado |
|---|---|---|
| lint | `npm run lint` (`next lint --dir . --max-warnings 0`) | `✔ No ESLint warnings or errors` — **exit 0** |
| typecheck | `npm run typecheck` (`tsc --noEmit`) | sem saída — **exit 0** |
| testes | `B2_INTEGRACAO="" npm test` | `Test Files 6 passed \| 1 skipped (7)` · `Tests 82 passed \| 7 skipped (89)` — **exit 0** |
| conteúdo fictício | `npm run test:conteudo-ficticio` | `[OK]` ×6 · `Nenhum fallback fictício encontrado` — **exit 0** |
| query client | `npm run test:query-client` | `[OK]` ×8 · `Política de cache do query client OK.` — **exit 0** |
| datas TZ | `TZ=UTC` e `TZ=Asia/Tokyo` `verificar-datas-tz.mjs` | ambos JSON com data civil correta — **exit 0** |
| tudo junto | `npm run verificar` (agora inclui `lint`) — **exit 0** |
| build | `NEXT_PUBLIC_API_BASE_URL=... npm run build` | `✓ Compiled successfully` · 254 `.map` — **exit 0** |
| árvore limpa | `npm ci` (o que a CI roda) | `exit 0`; `npm ls eslint eslint-config-next` → `eslint-config-next@14.2.15`, `eslint@8.57.1`; lint e testes repetidos após o `npm ci`, ambos verdes |
| schema dos workflows | `/tmp/actionlint .github/workflows/*.yml` | **exit 0, nenhum achado** (shellcheck integrado) |
| YAML | `python3 -c "import yaml; yaml.safe_load(...)"` em `ci.yml`, `deploy.yml`, `deploy-prod.yml`, `deploy-dev.yml`, `deploy-homolog.yml` | **5/5 OK** |
| gate do Sentry | 7 cenários com o shell extraído do YAML | **7/7 passaram** |

**O que não pôde ser rodado aqui:** o workflow em si no GitHub Actions. `actionlint` valida
esquema, expressões e shell, não executa. Os dois pontos que só o runner comprovará são (a) o
`npm ci` com o lock novo em Node 20 (o runner usa `node-version: "20"`, e validei em Node 24) e
(b) o `if: steps.sentry.outputs.habilitado == 'true'` com o gate reprovando — o efeito é
`habilitado=false` e o passo pula, que é o comportamento testado em T1/T3/T5/T7.

## 5. Decisões que NÃO são deste bloco (pendentes de quem solicitou)

1. **`next/typescript` no lint** — 60 erros em 31 arquivos (27 `no-explicit-any`, 27
   `no-unused-vars`, 4 `no-empty-object-type`, 2 `prefer-const`). Recomendação de ordem: começar
   por `argsIgnorePattern`/`varsIgnorePattern` no `.eslintrc` (resolve boa parte dos
   `no-unused-vars` sem tocar em código), depois decidir o que fazer dos `any` — que é tipagem
   de fronteira de API e merece run própria com suíte.
2. **Falha do upload no caminho de produção.** Hoje `continue-on-error: true` nos dois caminhos:
   com a credencial presente e a rede do Sentry fora, o deploy de produção **passa sem o source
   map** e ninguém é notificado. Argumento para deixar assim: indisponibilidade de terceiro não
   deve virar indisponibilidade de deploy. Argumento para mudar: em produção é o único ambiente em
   que o mapa importa para o plantão. Não decidi porque a instrução foi explícita sobre a
   **ausência** de credencial, e esta é a **falha** do upload.
3. **`CI-CD.md`** descreve o `frontend-build` com os passos antigos. Não editei: o arquivo já
   está modificado nesta run e há risco de conflito de merge com o orchestrator. Quem fechar a
   documentação precisa acrescentar os passos `test:conteudo-ficticio`, `npm test`, `typecheck` e
   `lint`, e a semântica `sentry_exigido` do deploy de produção.
4. **`run-state.json` e `implementation-history.md`** desta run não foram tocados (o orchestrator
   commita com paths explícitos; nada foi adicionado ao índice).

## 6. Arquivos alterados

```
.github/workflows/ci.yml            gate: 3 passos novos + typecheck pelo script + gate do Sentry fail-closed
.github/workflows/deploy.yml        input sentry_exigado repassado ao ci.yml no job verify
.github/workflows/deploy-prod.yml   sentry_exigido: true  (fail-closed em produção)
.github/workflows/deploy-dev.yml    comentário: fail-open segue correto em dev
.github/workflows/deploy-homolog.yml  comentário: idem em homolog
frontend/.eslintrc.json             NOVO — perfil, versões e a decisão sobre next/typescript
frontend/package.json               lint estrito; verificar inclui lint; eslint em devDependencies
frontend/package-lock.json          +312 pacotes (árvore do eslint), 0 remoções
frontend/app/admin/fila/page.tsx    itens memoizado (4 avisos)
frontend/app/admin/limites/page.tsx  idem + ?? VAZIO no caminho de sucesso
frontend/app/comunidade/[id]/page.tsx  pub nas dependências do efeito
frontend/components/HomeClient.tsx  leiturasTick fora das deps redundantes
frontend/components/home/EmAlta.tsx feed fora das deps redundantes
frontend/components/ImagemNoticia.tsx  exceção justificada ao no-img-element
```
