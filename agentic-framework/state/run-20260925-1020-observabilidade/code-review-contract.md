# Code Review — Contrato (revisão completa) — run 20260925-1020-observabilidade

<!--
CONTRACT: code-review (COMPLETO — remediacao + frontend + infra/deploy)
DONO: reviewer independente
RUN: 20260925-1020-observabilidade
-->

## Escopo e commits

Revisão **somente-leitura** do diff `7715dae..HEAD` (10 commits) na branch
`observability-20260925-1020`. **Nenhum arquivo do projeto foi editado, criado ou
commitado**; este relatório é o único artefato escrito. `code-review-backend.md` e
`run-state.json` não foram tocados.

| commit | conteúdo | revisado aqui |
|---|---|---|
| `672ffba` | baseline de telemetria do backend | não (veredito em `code-review-backend.md`) |
| `1b97836` | Bloco A: `/livez`, `/readyz`, `/health-detail`, `/metrics`, expurgo | não (idem) |
| `ca3ae4d` | Bloco A2: consentimento assinado + `/healthz` genérico | não (idem) |
| `2bf82c0` | histórico (doc) | não (idem) |
| `b0e196b` | contenção de ownership entre runs | sim (escopo) |
| `a340b17` | B1: correlação ponta a ponta, error boundaries, fim do conteúdo fictício | **sim** |
| `f7880a7` | B2: Sentry real, cliente do token, suíte de testes | **sim** |
| `0c45cf0` | C1: collector Alloy, systemd, backup fail-closed, watchdog, alertas | **sim** |
| `337ce37` | C2: release atômica com smoke, PM2 no standalone, gate de infra na CI | **sim** |
| `a2e7334` | D1: heartbeat do beat, gates de frontend na CI, lint e source map fail-closed | **sim** |
| `29e96b1` | estado da fase (doc) | não |
| `5e7fe90` | **remediação dos 4 majors do backend** + minors | **sim (integral)** |
| `4b968da` | **D2**: XFF no nginx instalado, canal de job nas duas pontas, 3 alertas novos | **sim (integral)** |

**Fora do escopo por instrução e por pertencer a outra run (nenhum achado abaixo
se refere a eles):** o diff aberto da run `20260925-1433-go-live-producao`
(`scripts/release/verificar-proveniencia.sh` **não versionado**, modificações em
`.github/workflows/deploy*.yml`, `CI-CD.md`, `PROD_DECISOES.md`, `infra/DEPLOY.md`)
e o WIP de `backend/feed/views.py`, `catalogo_noticias/services/deduplicacao.py`,
`backend/identidade/management/commands/criar_usuario_carga.py`, `subir-localhost.sh`.
Consequência de escopo que registro: **a parte versionada desta run contém o
*mecanismo* de release atômica (`infra/standalone/run-standalone.sh`, o bloco de
release em `deploy.yml`, `infra/DEPLOY.md` 9.1) mas nenhum script de release
próprio** — o que hamperou a verificação de atomicidade está no diff aberto de
outra run e não pôde ser julgado aqui.

## Como foi verificado

- Leitura integral dos módulos de produção e dos testes do diff (backend,
  frontend, infra, workflows).
- `cd backend && pytest config metricas -q` → **353 passed** (confere com o
  declarado no commit).
- `cd frontend && B2_INTEGRACAO="" npm test` → **82 passed, 7 skipped**
  (confere); `scripts/verificar-conteudo-ficticio.mjs` → 0 violações;
  `bash scripts/observability/validar-infra.sh` → **57 OK, 0 AVISO, 1 PENDENTE
  DECLARADA, 1 PULADO, 0 FALHOU**, exit 0.
- Testes adversariais **descartáveis**, criados **fora do repositório** em
  `/tmp/opencode/rev2/` (throttle em 5 topologias, presença das métricas de fila
  no scrape, semântica/custo do histograma, allowlists de rótulo). Nenhum arquivo
  do projeto foi escrito; usei `PYTHONDONTWRITEBYTECODE=1` e
  `-p no:cacheprovider` para não deixar cache no repositório.
- Cópia da guarda de conteúdo fictício + árvore sintética em `/tmp/opencode/guarda/`
  para testar se a guarda barra conteúdo fictício com outro vocabulário.

---

## Veredito

**`request_changes`**

Não há **blocker**: não achei caminho de corrupção de dados, vazamento de PII,
indisponibilidade de produção nem irreversibilidade. Os **4 majors da revisão de
backend foram corrigidos de verdade** — confirmei por execução, não por leitura
(§ "O que está certo"), e a suíte do backend segue verde sem regressão. O frontend
é, no ponto que mais importa, **honesto**: o conteúdo fictício saiu e nenhum dos
caminhos que restaram transforma falha em estado vazio silencioso.

O veredito fica em `request_changes` por **três majors**, todos do mesmo tipo —
**promessa de observabilidade que não tem dado por trás**:

1. os **dois painéis de job e quatro regras de alerta** (2 warning, 2 critical)
   são construídos sobre métricas que **não existem em nenhum scrape**
   (medido); o critério 14 fica sem o que promete e o critério 22 sem o que
   entregou;
2. o **monitoramento e o gate de deploy codificam um `503` na Home que a Home
   não produz** (ela é uma página ISR estática), e a justificativa escrita nos
   dois arquivos é factualmente errada;
3. a **guarda de conteúdo fictício é lexical** — provei que uma lista falsa com
   outro vocabulário passa (limitação inerente, mas o nome e a organização do
   artefato prometem mais do que entregam).

Fora disso, a lista é de **minors e nits**, quase todos de operação, e vários
deles são a mesma classe de defeito que a run já corrigiu uma vez (variável que
chega a um lado do canal e não ao outro).

---

## Achados

### Major

#### MAJOR-1 — Dois painéis e quatro regras de alerta dependem de métricas que não aparecem em nenhum scrape

- **Arquivos/linhas:**
  - `portal_celery_tasks_total` e `portal_celery_task_duration_seconds*` são
    gravados por `record_celery` no **processo worker** (`backend/config/celery.py:69-70`,
    `backend/config/metrics.py:539`), que não serve `/metrics`
    (`backend/config/celery.py:1-11` do próprio módulo assume o registro por processo);
  - `portal_celery_queue_depth` é gravado **dentro de `check_filas()`**
    (`backend/config/health.py:276`, gauge em `:309`), e `check_filas()` só é
    chamado de `snapshot(include_queues=True)` (`health.py:414-415`), cujo único
    chamador é a **view privada** `health_detail_view`
    (`backend/config/observability_views.py:169`);
  - o coletor raspa **só** `/metrics` (`infra/observability/alloy/config.alloy:64`);
  - o registry é por processo e o gunicorn tem **2 workers**
    (`backend/gunicorn.conf.py:48`).
- **Consumidores afetados:** regras `PortalFilaAcumulada` (warning,
  `regras-operacao.yaml:26`), `PortalFilaCritica` (critical, `:43`),
  `PortalCelerySemExecucao` (critical, `:65`) e `PortalCeleryTaskFalha`
  (warning, `:83`); painéis `portal-filas-celery.json` e `portal-ingestao.json`
  (todas as `expr` dos dois painéis usam `portal_celery_tasks_total`,
  `portal_celery_task_duration_seconds_bucket` ou `portal_celery_queue_depth`).
- **Reprodução (executada, `/tmp/opencode/rev2/test_fila_alerta.py`):**
  `METRICS.clear()`; `GET /metrics` → `portal_celery_queue_depth` **ausente**;
  só depois de um `GET /health-detail` a série aparece. Como o coletor nunca
  chama `/health-detail` e o gunicorn sorteia o worker, em produção a série
  está ausente em ~100% dos scrapes (e, quando presente, em metade deles).
  Em Prometheus/Mimir, `absent(series)` → vetor vazio → **a regra nunca dispara**.
- **O próprio run já sabia e deixou as regras antigas como se funcionassem:**
  o comentário de `regras-operacao.yaml:104-107` (do commit D2) diz que
  `portal_celery_tasks_total` "vive no registro POR PROCESSO do worker, que não
  serve `/metrics`; nesta topologia ele não aparece em nenhum scrape" — e as
  duas regras que o consomem continuaram no arquivo, com anotação descrevendo
  comportamento ("A task de ingestão não executou nenhuma vez em 45 minutos").
  O mesmo vale para a justificativa invertida de `PortalFilaAcumulada:22-25`
  ("o alerta usa a métrica — e não o check — porque o check só é consultado por
  alguém que abriu o endpoint privado"): a métrica é escrita **naquele mesmo
  endpoint privado**.
- **Impacto:** acúmulo de fila, Celery parado e task falhando **não geram
  alerta**, e os dois painéis de job abrem vazios — sem erro, sem painel
  vermelho, sem sintoma. É o pior tipo de falha de observabilidade (o painel
  que "existe" é o que dá confiança). Critérios **14** ("métricas de fila,
  atraso, retry, falha e duração consultáveis no Grafana") e **22** ficam
 arderidos sem a entrega prometida. Note que o **substituto** criado em D2
  (`PortalJobAtrasado`, via canal durável) **funciona** e cobre o atraso da
  ingestão — o que falta é fila e resultado por task.
- **Correção:** (a) publicar `check_filas()` no caminho do scrape
  (`metrics_view`, com o timeout de 0,35 s que o próprio check já usa) ou num
  `systemd` timer, para que `portal_celery_queue_depth` exista sem ninguém abrir
  `/health-detail`; (b) reescrever `PortalCeleryTaskFalha` sobre a série do canal
  durável (`portal_job_tasks_recorded{result!="success"}`, que existe) e remover
  ou re rotular `PortalCelerySemExecucao` como duplicata de `PortalJobAtrasado`;
  (c) reescrever os dois painéis sobre `portal_job_*`; (d) **fechar a cegagem do
  validador**: `validar-infra.sh:275-306` confere nome de métrica contra o
  inventário de `metrics.py` — que é justamente onde ficam os nomes
  inalcançáveis. Um predicado do tipo "produtor alcançável a partir de
  `/metrics`" (ou simply: rejeitar `portal_celery_tasks_total` e
  `portal_celery_queue_depth` em painel/alerta, como já é feito com
  `portal_ingestion_executions_total`) teria pegado isto.

#### MAJOR-2 — Monitoramento e gate de deploy tratam um `503` na Home que a Home não produz

- **Arquivos/linhas:** `infra/observability/better-stack/checks.json:67`
  (`home-producao`, `expected_status: "200,301,302,503"`) e `:75`
  (`"503 na Home é a resposta DOCUMENTADA para feed indisponível sem cache
  válido (critério 11)"`); `infra/standalone/run-standalone.sh:266-277`
  (smoke aceita `2*|3*|503` e registra que o 503 é "o estado documentado").
- **O que a Home faz (`frontend/app/page.tsx`):** `export const revalidate = 60`
  (`:30`) e nenhum `force-dynamic` → a rota é **gerada estaticamente** no build
  (que em produção roda na VPS com o Django no ar) e passa por ISR. Consequências:
  1. com a página em cache, uma falha de revalidação **não** muda o status: o
     Next serve o HTML anterior com **200**;
  2. quando `getData()` roda e não há conteúdo real em memória, o caminho é
     `throw erro` (`:182`) → o App Router responde **5xx**, não 503;
  3. durante o build, `emFaseDeBuild()` (`:49-51`) devolve o estado
     `sem-dado-real` **com 200** — e esse HTML é assado na release.
  Não existe no frontend nenhum caminho que produza 503 em `/`
  (`grep -rn 503 frontend/app frontend/lib` → só comentários).
- **Impacto:** (a) o ramo `503` é **código morto** nos dois arquivos, e a
  justificativa escrita neles é falsa; (b) o check externo da Home **não
  consegue enxergar indisponibilidade de feed**, que é exatamente o motivo
  declarado dele ("`/readyz` verde com Home em 500 é exatamente o incidente que
  os endpoints de saúde não enxergam") — com ISR, a Home raramente dá 500 e
  quando dá é por cache frio; (c) o critério **23** ("o check e o alerta
  correspondente são acionados") herda essa crença. O sinal **real** de feed
  parado é o `PortalJobAtrasado` (que existe e funciona).
- **Correção:** decidir o comportamento e propagá-lo: (i) aceitar `5xx` no
  `expected_status` do check e no smoke, com a ressalva "5xx aqui = dependência
  ou bug, siga o `request_id`" — e reescrever os dois `meta`; **ou** (ii) fazer o
  endpoint de feed devolver 503 e servir a Home por um caminho que consiga fixar
  status; em qualquer caso, corrigir `checks.json:75,94` e
  `run-standalone.sh:158-160,262-270`, que hoje descrevem um comportamento
  inexistente. (Efeito colateral do item (i): o smoke deixa de reprovar uma
  release boa por causa de feed fora do ar.)

#### MAJOR-3 — A guarda de conteúdo fictício é lexical, e o nome do artefato promete mais do que ela entrega

- **Arquivo/linha:** `frontend/scripts/verificar-conteudo-ficticio.mjs:136-153`
  (`PADROES_FICCAO`), `:165-184` (`ARQUIVOS_VIGIADOS`).
- **O que está certo (e era a minha hipótese principal, que se mostrou errada):**
  a guarda **não** é uma lista que pode envelhecer. `varrerApp()` (`:187-211`) e
  `varrerLib()` (`:213-243`) percorrem **recursivamente** toda a árvore
  `app/**` e `lib/**`; `ARQUIVOS_VIGIADOS` é usado só para **afirmar que as
  páginas nomeadas existem** (`:251-266`). Uma página nova é coberta
  automaticamente. *Hipótese descartada.*
- **O que é defeito:** os padrões são um **vocabulário**, não uma propriedade.
  Reprodução executada (`/tmp/opencode/guarda/`, cópia do script + árvore
  sintética): uma página `app/nova/page.tsx` com
  `const FAKE = [{id:1, titulo:"Notícia #1 — conteúdo de teste", resumo:"Resumo de teste do portal."}, ...]`
  e um `lib/qualquer.ts` com `NOTICIAS_EXEMPLO` → **`[OK] frontend/app/**: sem
  array/objeto/texto de demonstração`. Nenhum `MOCK*`, nenhum "dados de exemplo",
  nenhum `@exemplo.com`, nenhum `Math.random()`.
- **Impacto:** o gate de CI que existe para "conteúdo fictício em produção é o
  que os não-objetivos do contrato proíbem" passa por uma lista reescrita com
  outro nome. É a mesma categoria de problema que a run Critica no `lint` sem
  eslint ("verifica local, não verifica o merge") e no `catch` da
  `carregarHome` (achado B1). Não há conteúdo fictício no estado atual (verifiquei
  as ~20 páginas tocadas), então o impacto é **prevenir regressão**, não
  corrigir dano existente.
- **Correção:** manter a guarda lexical (ela é a barreira barata e pega o
  histórico), mas **renomear o que ela promete** (ex.: "vocabulário de
  demonstração") **e acrescentar uma verificação estrutural** que não dependa de
  nome: por exemplo, um teste que exija que nenhuma página de conteúdo
  (`app/page.tsx`, `app/arquivo`, `app/ao-vivo`, `app/buscar`,
  `app/categoria/*`, `app/noticia/*`) contenha um literal de objeto com
  `titulo:`/`resumo:` fora de `testes/`; ou um gate de revisão que exija
  `estado === "erro"` em toda página que consome `lib/api.ts`. Registrar o limite
  no próprio cabeçalho do script.

### Minor

#### MINOR-1 — O BFF repassa o `X-Forwarded-For` do cliente para um peer **loopback**, que o novo leitor trata como proxy confiável

- **Arquivos/linhas:** `frontend/app/api/[...path]/route.ts:126`
  (`const headers = new Headers(req.headers)` — repassa tudo, inclusive
  `X-Forwarded-For` e `X-Real-IP`) com `destino()` em `:48-56`
  (default `http://127.0.0.1:8000`); `backend/config/proxies.py:112-133`
  (`identificar_cliente` — loopback ⇒ lê o **último** elemento do XFF).
- **Por que importa:** toda a correção do MAJOR-1 rests sobre a premissa
  "o último elemento é o que o **proxy** anexou". No caminho browser → Next
  (`:3103`, acesso direto por IP:porta, o cenário do incidente de 2026-09-19
  documentado no próprio arquivo) → `127.0.0.1:8000` **não existe proxy que
  anexe nada**, e o peer é loopback (confiável). O último elemento do XFF é
  então o que o **cliente** escreveu.
- **Reprodução executada:** 40 POSTs em `/api/metricas/consent/` com
  `REMOTE_ADDR=127.0.0.1` e `X-Forwarded-For` girando, **sem** o anexo que o
  nginx faria → **40×201, 0×429** (o bypass original, medido). Com o anexo
  (`10.0.0.i, 203.0.113.77`) → 30×201 + 10×429, como esperado.
- **Impacto:** hoje **teórico/contido** — `3103`/`5103` não são alcançáveis da
  internet (ufw libera 22/80/443, `infra/DEPLOY.md:215-219`) e o nginx anexa o
  XFF antes do Next. Vira real se alguém (a) publicar a porta, (b) criar uma
  location nova para o Next sem a diretiva, ou (c) o `4b968da` não cobrir este
  caminho — e o `4b968da` cobriu **só** o nginx (`validar-infra.sh` falha se a
  diretiva sumir dos `portal-*.conf`), não o BFF.
- **Correção:** no `route.ts`, `headers.delete("X-Forwarded-For")` e
  `headers.set("X-Forwarded-For", req.headers.get("X-Real-IP") ?? "127.0.0.1")`
  (o `X-Real-IP` é definido pelo edge e não é aceito do cliente no nginx
  versionado); ou, mais simples, `API_INTERNAL_URL` com o IP do container e a
  rede declarada em `OBSERVABILITY_TRUSTED_PROXY_NETWORKS`.

#### MINOR-2 — Topologia Docker: todas as requisições caem num único balde de rate limit

- **Arquivos/linhas:** `backend/config/proxies.py:112-133`;
  `docker-compose.yml:63` (`reverse_proxy` do Caddy para `web:8000` na rede
  `internal`); `.env.production.example:83` e `backend/.env.example:180`
  (`OBSERVABILITY_TRUSTED_PROXY_NETWORKS=` **vazio**, o default documentado
  "VAZIO é o certo na topologia PM2").
- **Reprodução executada:** 40 requisições com 40 IPs de cliente distintos e
  `REMOTE_ADDR=172.18.0.3` (o container do Caddy), rede **não** declarada →
  **30×201 + 10×429**, ou seja, um balde só para o site inteiro
  (`consentimento` = 30/min, `escrita_publica` = 20/min, `auth_sensivel` = 10/min).
- **Impacto:** **não afeta a topologia ativa** (nginx na mesma máquina ⇒
  `REMOTE_ADDR` = 127.0.0.1 ⇒ loopback ⇒ XFF lido; confirmei que os três
  `portal-*.conf` têm exatamente 13 `proxy_set_header X-Forwarded-For` para 13
  `proxy_pass` reais, e o `validate` do deploy confere o conf **instalado**).
  Afeta a variante `docker-compose.yml` (local hoje, "migração futura" segundo o
  `Caddyfile:7-12`). O caso análogo (CDN sem `realip`) **está** documentado em
  `infra/DEPLOY.md:1104-1125`; falta a frase para o compose.
- **Correção:** uma linha no `.env.production.example`/`DEPLOY.md` ("na
  topologia Docker, declare a rede do bridge em
  `OBSERVABILITY_TRUSTED_PROXY_NETWORKS`; vazio = um balde para o site todo") ou
  o compose declarar a rede.

#### MINOR-3 — `error.tsx` decide o texto pelo consentimento, não pelo envio

- **Arquivo/linha:** `frontend/app/error.tsx:65,94-96`.
- **O que acontece:** o texto "O diagnóstico técnico está autorizado nas suas
  preferências, então este erro pode ser analisado pela equipe" é derivado de
  `consentimentoTecnico()` (render), enquanto `capturarErroTecnico`
  (`lib/sentry-cliente.ts:176-201`) só envia se `sdk !== null` — e devolve
  `false` justamente no caso "consentido mas SDK ainda não carregado"
  (`:181-187`). O próprio comentário do arquivo (`:55-59`) reconhece que o texto
  não vem do retorno.
- **Impacto:** a frase é suavizada ("pode ser"), mas afirma uma relação causal
  entre consentimento e análise que, nesse caso, é falsa. É a única frase de
  tela da run que não é derivada do que aconteceu — o resto (`NoticiaIndisponivel`,
  Home, `/buscar`, Radar, `admin/planos`) é.
- **Correção:** `const enviado = useRef(false)` + `capturarErroTecnico` no
  `useEffect` e texto em função de `enviado || sentryAtivo()`; ou, sem
  estado: "Com o diagnóstico autorizado, este erro **pode** ser enviado ao
  time — se a tela carregar sem o envio, o diagnóstico está indisponível e vale
  reportar pelo formulário de contato."

#### MINOR-4 — Falha na emissão do token de consentimento é totalmente silenciosa

- **Arquivo/linhas:** `frontend/lib/consent-token.ts:261-286` (o `catch`
  engole rede/429/503 e devolve `null`), `frontend/lib/analytics.ts:210-228`
  (o evento sai da fila sem nada).
- **O que acontece:** emissor fora do ar, sem chave HMAC (`503`) ou
  limitado (`429`) ⇒ **todo evento de produto é descartado sem nenhum sinal**:
  sem contador, sem `console.warn`, sem métrica. `enviarEvento` (`:177-195`)
  também retorna `true` otimista e nunca observa o 202.
- **Impacto:** "emissor quebrado" e "ninguém consentiu" produzem exatamente o
  mesmo silêncio no painel de produto — o mesmo falso-verde que a run existe
  para eliminar, agora no caminho do analytics. Um `429` proveniente do
  MAJOR-1 (bucket colapsado, ver MINOR-2) também cairia aqui sem deixar rastro.
- **Correção:** um contador local (expor (expor em `registrarFalhaApi`/um
  `console.warn` sem PII) e/ou uma tentativa de reemissão com backoff curto
  antes de descartar; documentar que o backend já devolve
  `registrar_recusa` + métricas para o lado do servidor.

#### MINOR-5 — `MAX_SERIES_POR_METRICA = 500` para uma família cujo vocabulário real já é ~109 rotas

- **Arquivo/linhas:** `backend/config/metrics.py:53`,
  `backend/config/metrics.py:156-166` (`_cabe`).
- **O que medi:** o backend declara **109** `path()`/`re_path()` nos `*/urls.py`
  (mais as variações de método/status que o tráfego realmente produz). O teto por
  família é 500 séries de `portal_http_requests_total` (e o mesmo para o
  histograma, que é outra família). Chegou a ~1,6× do vocabulário de rotas.
- **Impacto:** não há risco hoje; o risco é o **modo de falha do MAJOR-2
  deslocado**: quando o teto for estourado por rotas legítimas, séries
  legítimas somem do `/metrics` (o descarte é contado, e
  `PortalMetricasDescartadas` dispara — mas o painel fica incompleto sem erro).
  Vale dimensionar por família (ex.: `portal_http_*` com teto maior) ou
  derivar de `len(URLconf)`.
- **Correção:** subir o teto de `portal_http_requests_total`/`_duration_seconds`
  para ~2000 (mantendo o teto global como rede) e/ou registrar o número de rotas
  no docstring do teto, para o número não ser arbitrário.

#### MINOR-6 — Se as três tentativas de `pm2 start` falharem, o processo fica **deletado** e o web sai do ar

- **Arquivo/linhas:** `.github/workflows/deploy.yml:744-771`
  (`restart_or_start`: `pm2 delete` antes de cada `pm2 start`, e em caso de
  falha **não** há start de recurso), `:812-834` (caminho de volta).
- **O que acontece:** o `delete+start` foi escolhido por um motivo real e
  documentado (`pm2 restart` reaproveita args antigos — observado em
  2026-09-24), mas a consequência é que a **falha** deixa o processo deletado
  até intervenção manual. A mitigação existe e é razoável: 3 tentativas, espera
  de online (10×2 s), saída de erro com o procedimento de
  `rollback.yml`, e `.deployed-sha` **não** promovido.
- **Impacto:** janela de indisponibilidade até o operador agir, sem
  auto-restauração. É pré-existente ao desenho `delete+start` e o critério 30
  não exige auto-recuperação; registro porque o run afirma atomicidade e este
  é o único ponto em que "release" e "ar" divergem.
- **Correção:** no ramo de falha final, tentar `web_runtime: npm`-equivalente
  (`pm2 start ... npm -- start`) como último recurso antes de sair, ou deixar o
  `previous` promovecido e instruir o `rollback` com um comando de uma linha.

#### MINOR-7 — `PortalSentryDescartandoErros` fica permanentemente disparado com os defaults entregues

- **Arquivo/linhas:** `infra/observability/alerts/regras-operacao.yaml:266-286`
  (`rate(portal_sentry_events_dropped_total{reason="no_technical_consent"}[30m]) > 0`,
  `for: 30m`, warning); default em `backend/config/settings.py`
  (`SENTRY_TECHNICAL_CONSENT_DEFAULT=False`).
- **O que acontece:** com o default, **toda** exceção de backend incrementa esse
  contador ⇒ a taxa é > 0 enquanto houver exceções ⇒ o warning fica ligado a
  partir da primeira exceção, para sempre. Não é um bug de regra: é o
  comportamento pretendido ("precisa ser intencional"), mas **ninguém decidiu que
  produção roda sem APM**, e o run registra a decisão como pendência
  (`sentry.server.config.ts:36-44`).
- **Impacto:** um warning eterno (ou seja, ignorado) que ocupa o canal sem
  informar nada novo, enquanto o sinal que ele transporta ("não temos APM") é
  uma **decisão**, não um incidente.
- **Correção:** separar em duas regras: uma **informativa** e persistente
  ("APM desligado por configuração — `SENTRY_TECHNICAL_CONSENT_DEFAULT=false`")
  e outra de warning só para *variação* (subida Unexpecteda da taxa de descarte
  com consentimento ligado). Decidir o default de produção em `PROD_DECISOES.md`.

#### MINOR-8 — O README dos alertas diz que o validador **falha** com `runbook_url` placeholder; ele não falha

- **Arquivos/linhas:** `infra/observability/alerts/README.md:84-85`
  ("`validar-infra.sh` **falha** enquanto o `.invalid` estiver no arquivo") vs
  `scripts/observability/validar-infra.sh:360-368` +
  `scripts/observability/pendencias-ci.txt` (é **pendência declarada**, que não
  reprova; e a lista não pode envelhecer em silêncio — chave que não ocorre mais
  = FALHA).
- **Verificado por execução:** `validar-infra.sh` → `0 FALHOU`, exit 0, com
  `1 PENDENTE DECLARADA`.
- **Impacto:** nenhum risco de configuração (o mecanismo é bom e está explained);
  é o texto do README que descreve um gate mais forte do que o existente — e é
  o **único** ponto do run em que a documentação afirma um fail-closed que não
  acontece. Num arquivo que fala de fail-closed, isso importa.
- **Correção:** trocar "falha" por "reporta como pendência declarada (não
  reprova; ver `pendencias-ci.txt`)" nos dois README que repetem a frase
  (`alertas/README.md:84-85` e `regras-disponibilidade.yaml:23-24`).

#### MINOR-9 — A "prova de regressão" dos 26 casos vive fora do repositório e muta os fontes do projeto in-place

- **Arquivo:** `/tmp/opencode/prova_regressao.py` (lê e **escreve** em
  `backend/config/*.py`, `backend/metricas/*.py`; restaura no `finally`).
- **O que está certo (e era a pergunta que me foi feita):** os 26 casos são
  **mutation tests de verdade**, não testes tautológicos. Li o arquivo: cada caso
  reverte um fix por substituição de string e roda **um** teste nomeado;
  `esperado="quebra"` exige que o teste **falhe** sem o fix, e um caso
  `esperado="aguenta"` (NUM_PROXIES revertido sozinho) documenta a defesa em
  profundidade. Se o trecho não for encontrado, o script aborta com
  `SystemExit` — ou seja, ele não "passa" por não encontrar o fix. A cobertura
  declarada bate com o que existe: MAJOR-1 (3), MAJOR-2 (4), MAJOR-3 (2),
  MAJOR-4 (4), MINOR-1/2(3)/3/4/5/6/9, NIT-1/2/7.
- **O que é defeito:** (a) **não está no repositório** — um terceiro não
  reproduz, a CI não roda, e o commit `5e7fe90` referencia um caminho em `/tmp`;
  (b) **escreve nos arquivos versionados** para provar o ponto: um `kill -9`
  no meio deixa o fix revertido no working tree, e nada detecta isso além de
  alguém rodar `git diff`; (c) a afirmação "cada fix tem teste que depende dele"
  vale para os 26 listados — **não** há caso de mutação para
  `check_celery_jobs` (estados `error`/`degraded`), para `publicar_metricas`
  (sentinela `-1`, soma/contagem de duração) nem para `MAX_SERIES_DESCARTE`
  (esses têm testes, e são reais, mas não foram exercitados por mutação).
- **Correção:** versionar o harness (`scripts/` ou `tests/mutation/`), rodar
  contra uma **cópia** da árvore (ou `git worktree`) em vez dos fontes, e plugá-lo
  na CI como job não-bloqueante. Os testes no repositório — que são o artefato
  durável — já sustentam a qualidade; isso é sobre **reprodutibilidade da
  evidência**.

#### MINOR-10 — `noticia/[id]` faz duas chamadas mesmo quando a primeira falha por transporte

- **Arquivo/linhas:** `frontend/app/noticia/[id]/page.tsx:38-50`
  (`getDetalhe` tenta cluster e, em qualquer falha, tenta item).
- **Impacto:** durante uma indisponibilidade do backend, cada visita a
  `/noticia/<id>` faz **duas** requisições que vão falhar (com o timeout de 15 s
  de `lib/api.ts`), duplicando a latência e o tráfego de erro — e o
  `registrarFalhaApi` conta as duas. Só `404` deveria parar na primeira.
- **Correção:** em `classificar`, distinguir `indisponivel` (transporte) de
  `inexistente` (404) **antes** de tentar o segundo endpoint, ou tentar o item
  apenas em 404.

### Nit

- **NIT-1** — `frontend/app/page.tsx:169-181`: o estado `sem-dado-real`
  (usado só em build) é renderizado com **200** e o texto "Não conseguimos falar
  com a base de notícias". É honesto, mas significa que uma build de produção
  feita com o Django fora do ar **assa** um estado de falha no HTML estático, que
  fica no ar até a primeira revalidação bem-sucedida. O build de produção roda
  na VPS com o Django no ar (`deploy.yml:302-312`) e o validador de infra não
  checa isso; uma linha no `smoke` (`GET /` não pode conter a string
  "Não conseguimos falar com a base de notícias" **quando** a API está de pé)
  fecharia o loophole sem custo.
- **NIT-2** — `backend/config/metrics.py:194-196`: `observe()` descarta valor
  não-finito **sem contar** (nem em `total`, nem em
  `portal_metrics_series_dropped_total`). É pré-existente ao diff, e o descarte
  de NaN é a única escolha defensável; registro porque a contagem de descarte é
  a regra do run.
- **NIT-3** — `run-state.json:25` (fase `implementation`) ainda diz que o
  "critério 29 exige decisão entre migrar o PM2 para standalone ou reescrever o
  critério", mas o `337ce37` **já** migrou (`web_runtime: standalone` é o caminho
  do deploy e o PM2 executa `run-standalone.sh start`). A pendência correta é
  outra: "implementado, não verificado em ambiente real". Arquivo de estado não
  alterado por mim (instrução), apenas sinalizado.
- **NIT-4** — `infra/systemd/celery-beat-heartbeat@.service:20-21` cita
  "`portal_ingestion_executions_total` (alerta `PortalIngestaoParada`)" como a
  cobertura residual do "beat travado com processo vivo". **Nenhum dos dois
  existe**: o validador rejeita explicitamente o uso da métrica
  (`validar-infra.sh:216-220`) e não há regra `PortalIngestaoParada` no
  repositório. Substituição real: `PortalJobAtrasado`.
- **NIT-5** — `frontend/lib/consent-token.ts:238`: com o emissor fora do ar e o
  token dentro da janela de renovação, **cada** evento dispara uma reemissão
  (`garantirToken` → `void renovarToken`); a dedupe (`EM_VOO`) só cobre chamadas
  concorrentes. Com o TTL default de 24 h e janela de 5 min isso é raro na
  prática, mas é o mecanismo de amplificação caso o TTL caia. Um
  `ultimoTentoDeRenovacao` por sessão (com cooldown de ~1 min) resolve.
- **NIT-6** — `infra/observability/grafana/dashboards/portal-disponibilidade.json:894`
  (texto do painel) afirma que "**gauge** é o sinal confiável para estado
  (`portal_ready`, `portal_celery_queue_depth`, `portal_collector_disk_free_ratio`)".
  Para `portal_celery_queue_depth` isso é falso (ver MAJOR-1); para
  `portal_ready` é parcialmente (só `/readyz` e `/health-detail` o escrevem —
  `observability_views.py:153,175` — e o registry é por processo, com 2 workers).
  O texto do painel é o primeiro lugar onde alguém vai procurar para entender
  por que um painel está vazio.

---

## O que está certo (verificado, não presumido)

Estes pontos eu tentei quebrar e **não** consegui; registro porque "se algo está
certo, diga".

**Remediação do backend (`5e7fe90`) — os 4 majors foram corrigidos de verdade:**

1. **MAJOR-1 (throttle).** Reproduzi a linha de base e o depois, com as mesmas
   40 requisições e `X-Forwarded-For` girando, em 5 topologias:
   par externo → **30×201 + 10×429** (antes 40×201); loopback com cadeia +
   anexo do proxy → 30×201 + 10×429; loopback **sem** anexo → 40×201 (veja
   MINOR-1, é o único caminho que sobrou); caddy/rede não declarada → 30×201 +
   10×429 (MINOR-2); CDN → 30×201 + 10×429 (documentado em `DEPLOY.md:1104`).
   `identificar_cliente` é fail-closed em toda entrada: `Host`/
   `X-Forwarded-Host` não entram, `REMOTE_ADDR` inválido cai num balde estável
   (não um balde novo por request), rede malformada é ignorada com **um** aviso
   por valor. `NUM_PROXIES: 0` fecha o DRF por fora e o mixin `_IdentidadePorParReal`
   fecha por dentro — as duas camadas são independentes (e o caso "aguenta" da
   prova de mutação confirma). Confirmei que os três `portal-*.conf` têm 13
   `proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for` para 13
   `proxy_pass` reais, que o `validar-infra.sh` **falha** se a diretiva sumir ou
   virar `$http_x_forwarded_for`, e que o `validate` do deploy confere o conf
   **instalado** (`nginx -T`, 13 × nº de sites).
2. **MAJOR-2 (métricas).** Allowlist de `method` (9 verbos → `other`) e de
   `status` (100..599 → `other`) aplicadas no `record_http`; teto por família
   **antes** do global, com teste que prova que uma família barulhenta não leva
   `portal_ready` junto; e o histograma com **buckets acumulados**:
   medi **200 séries × 2 000 observações → 0,010 s** de render (o baseline
   declarado era 0,89 s em 200 × 10 000), os buckets saem cumulativos e
   monótonos, `+Inf` = `_count`, e `observe` é O(#buckets). Confirmei também que
   o `inc("...", total, model=nome)` do expurgo usa o **valor posicional** (a
   armadilha que o commit descreve está de fato evitada e comentada no código).
3. **MAJOR-3 (beat).** `CHECKS_SEM_SINAL_PROPRIO` + `_e_degradante()` é uma
   **função única** usada tanto por `snapshot()` quanto por `degraded_state()` —
   não há dois caminhos que possam divergir. Confirmei por execução que
   `not_configured` de `celery_beat`/`celery_jobs` vira `degraded` (com
   readiness ainda `200`), que o inverso volta a `ok` quando o heartbeat está
   recente, e que existe a gauge `portal_health_check_not_configured` (o ponto
   cego vira número). `redis`/`collector_disk` ficaram de fora de propósito e o
   motivo está escrito.
4. **MAJOR-4 (canal de job).** O canal é real, atômico (`write` + `os.replace`),
   limitado (`MAX_TASKS`, com corte por `ultimo_fim`), **fail-closed**
   (`sem canal → not_configured → degradação`, nunca "ok"), e a semântica das
   gauges está documentada no ponto onde importa (`max()`/`last()`, nunca `sum()`
   nem `rate()`). Verifiquei ponta a ponta: sinal `task_postrun` do Celery →
   arquivo → `/metrics` do processo web, e que o gating continua negando
   `/metrics` para IP externo. O que **não** foi entregue (histograma por task,
   cross-process) está **declarado** em `job_state.py:23-28` e nas réguas, em vez
   de fingido — e é exatamente a lacuna que virou o MAJOR-1.
5. **Minors.** `Authorization: Basic` e o 2º cookie agora são consumidos até o
   fim da linha (`_HEADER_VALUE`); `\n\r\t` viram escape em `redact_single_line`
   e o formatter `verbose` passou a ser o `RedactingTextFormatter` (com
   `formatException` redigido, que é o caminho onde vive a query string com
   token); o `compare_digest` do bearer virou comparação em **bytes** (o 500 com
   header não-ASCII morre); `any()` virou laço sem curto-circuito (o comentário
   agora descreve o que o código faz); `v` passou a exigir `int`; o `pass` do
   `sentry_sdk.init` virou aviso + `portal_sentry_init_failed_total`. **353
   passed** e **811 passed** na suíte completa (declarado), sem regressão.
6. **Nenhum dos 4 majors criou regressão:** a suíte do backend está verde, a
   cobertura por família não derruba métricas de sistema, e o canal de job não
   abre nenhuma brecha no gating (teste explícito).

**Frontend (B1, B2, D1):**

- **A remoção do conteúdo fictício é honesta.** Percorri as ~20 páginas tocadas e
  o padrão é consistente: **estado de erro ≠ estado vazio**, com texto que diz o
  que aconteceu e código de correlação. `app/buscar` ("A busca está
  indisponível… Não mostramos resultados de exemplo"), `app/ao-vivo` (o pior
  caso anterior — LIVE com manchete falsa ligada a `/noticia/11`), `app/arquivo`,
  `app/categoria/[slug]`, `app/noticia/[id]` (404 real continua 404; indisponível
  **nunca** vira 404, decisão certa), `RadarClient` (erro e vazio separados, com
  "Não exibimos uma série de exemplo"), `admin/planos` ("a lista de planos não
  foi carregada. Nenhum plano foi alterado"). **Não encontrei o inverso do MOCK**
  (falha apresentada como estado vazio) em nenhuma página.
- **A causa raiz foi removida, não a symptoms**:
  `carregarHome` (`lib/recomendacao.ts:81-94`) não tem mais o `catch` que
  devolvia seção vazia — e a guarda `verificar-conteudo-ficticio.mjs:288-304`
  fixa **essa** função como causa raiz, com regex própria.
- **Sentry (browser).** `sendDefaultPii: false` explícito; **replay 0 e 0
  explícito** (não "omitido"); `dataCollection` com nomes **reais** do SDK v10 —
  conferi um a um contra `node_modules/@sentry/core/build/types/types/datacollection.d.ts`
  (`userInfo`, `cookies`, `httpHeaders.request/response`, `httpBodies: []`,
  `urlQueryParams`, `graphQL`, `genAI`, `databaseQueryData`, `stackFrameVariables`,
  `frameContextLines`), então a "primeira barreira estrutural" é mesmo
  estrutural; `beforeSend`/`beforeSendTransaction` reavaliam o consentimento **a
  cada evento**; a revogação **fecha o transporte** (`close(2000)`), o que fecha
  o que já estava em voo; `stacktrace.frames[].vars` e `previews` são removidos
  inteiros (o vetor do token em `localStorage`); breadcrumbs e `request` são
  higienizados; `environment`/`release` são **reescritos** depois, para o evento
  não sobrescrever o valor certo.
- **"Sem consentimento o SDK nem é carregado" é verdade.** Li o plugin do
  `@sentry/nextjs` (`build/cjs/config/webpack.js:275-300`): `withSentryConfig`
  apenas **injeta o arquivo** `sentry.client.config.ts` na entry `main-app` —
  não injeta nenhum `Sentry.init`. O único caminho de init é
  `iniciarSentryCliente()`, que exige DSN **e** `consentimentoTecnico()` antes do
  `import()` dinâmico. Também confirmei que o `instrumentation.ts` exporta
  `onRequestError` e que o `sentry.server.config.ts` é importado por ele (o SDK
  v10 não carrega o config sozinho).
- **Reconsentualização por evento** verificada nos três lugares: o listener
  `EVENTO_CONSENTIMENTO_ALTERADO` (concessão → `init`; revogação → `close`), o
  `beforeSend` por evento, e `consentimentoTecnicoConcedido()` lendo o
  `localStorage` **diretamente** (sem React), com `false` no SSR — o que também
  significa que o header `X-Technical-Consent` nunca é enviado em SSR
  (fail-closed, documentado).
- **Cliente do token.** Fail-closed de ponta a ponta (`tokenParaEnvio` → `null`
  → evento descartado; sem caminho que produza evento sem token); renovação
  **antes** de expirar (janela de 300 s, reemissão **em paralelo**, e o token
  ainda válido **é usado** — a janela não descarta evento, o que seria perda de
  dado sem ganho); validação estrutural da resposta do emissor (envelope de 3
  partes, versão, `sub` amarrado à sessão, `exp` no futuro, teto de 2048 bytes);
  `sessionStorage` e não `localStorage`; revogação **apaga** o token na hora
  (correto: a assinatura continuaria válida até o `exp`); dedupe de emissão em
  voo; fila com teto de 50. O emissor fora do ar → `null` (MINOR-4 é a ressalva,
  não um bug).
- **`app/error.tsx` / `app/global-error.tsx`**: os dois existem, ambos com
  `reset()`, ambos com fail-closed, e o `global-error` desenha `<html>/<body>`
  sem depender de contexto (que é a razão de ele existir). `digest` só é exibido
  quando não há `requestId` melhor, para não sugerir uma correlação que não
  existe.

**Infra e deploy (C1, C2, D2) — a atomicidade é real, e eu interrompi cada passo:**

- **A ordem é a correta:** preparar release → `smoke` na release, em **porta
  livre** (para não testar o processo velho) → *só então* promover. Falha antes
  da promoção: `current`, PM2, `.deployed-sha` e as migrations do backend não são
  tocados, e a release nascent é removida.
- **A troca do symlink é atômica de verdade:** `ln -s` + `mv -T` (rename(2)),
  nunca `ln -sfn`. Não existe janela em que `current` não exista. **A janela que
  você perguntou** (`current` apontando para release que não está no ar) existe
  em um sentido **inofensivo**: entre a promoção e o `pm2 start`, o symlink já é
  novo mas o processo em memória é o velho — quem serve é o processo, não o
  symlink, então nenhum visitante vê um estado misto. E se o `pm2 start` falhar
  **depois** da troca, o script chama `voltar_release_anterior` (que reverte
  `current` e sobe na anterior) e **sai com 1 de propósito**, sem promover o
  marker — a decisão está comentada no código e está certa.
- **`previous` é preservado antes de `current`**, então, em qualquer instante, o
  par é consistente; se a promoção de `previous` falhar, `current` não é tocado.
- **A poda não pode apagar o alvo do rollback:** `podar_releases` resolve
  `readlink -f` de `current` e `previous` e pula os dois, **inclusive** quando a
  anterior ficou fora do recorte (o caso de 4 deploys seguidos, que o comentário
  descreve). Nenhum `rm -rf` em caminho construido por variável sem `${...:?}`.
- **O rollback manual continua funcionando com o layout novo:**
  `rollback.yml` reutiliza o **mesmo** caminho gated do deploy (fetch → reset →
  build → release → smoke → promoção), com `strict_validate: true`; e o
  procedimento manual por symlink está em `DEPLOY.md:925-945` (também com
  `ln -s` + `mv -T`, e com a instrução de "nunca `ln -sfn`").
- **O marker é a fronteira de recuperação:** `.deployed-sha` só é promovido com
  probes verdes **e** checkout igual ao SHA verificado; deploy parcial, job
  cancelado ou checkout divergente preservam o marker anterior.
- **Fail-closed do backup:** sem `BACKUP_S3_BUCKET` → exit **20** (antes: dois
  AVISOs e exit 0, isto é, verde sem destino), com retenção local **suspensa**;
  configuração S3 parcial → exit 12; upload → `head-object` com **comparação de
  tamanho**; o marcador `.ultimo-backup-ok` só é escrito depois de dump + mídia +
  upload + verificação; `BACKUP_HEARTBEAT_URL` ausente → exit 21. Códigos
  distintos para "sem destino" e "backup quebrado", e nenhum segredo sai
  (nem a URL do heartbeat).
- **Watchdog fail-closed e com saídas distintas:** 0 dentro do prazo, 1 atraso,
  2 nunca executou, 3 **configuração ausente** ("não sei" ≠ "está tudo bem"), 4
  alerta não entregue; checagem cruzada (marcador recente + dump mais antigo que
  o limite → "desconfie do marcador"); JSON sempre na stdout, humano no stderr;
  marcador com `remoto=ausente` → `sem-destino`.
- **Systemd fail-closed por construção:** `EnvironmentFile` **sem** o prefixo `-`
  (sem env, a unit não sobe), `ExecStartPre` exigindo binário e tuning
  (concorrência/teto), `StateDirectory` como **fonte única** do diretório do
  heartbeat (o `install -d` do deploy foi removido de propósito, com o motivo
  escrito), e o `ExecCondition` que consulta a unit do beat **antes** de tocar o
  arquivo — que é exatamente a armadilha do "timer que mantém o check verde com o
  beat morto".
- **Coletor fail-closed:** `verificar-env.sh` roda no `ExecStartPre` e no
  validador, exige 13 variáveis com valor real, rejeita 6 famílias de placeholder
  e **não imprime valor nenhum** (só o nome). `alloy validate` executado de
  verdade (imagem oficial) — o `config.alloy` é válido.
- **A integração da remediação com a infra está fechada dos dois lados**
  (`4b968da`): as 13 diretivas de XFF nos três confs + gate no validador +
  `nginx -T` no `validate` do deploy; e o canal de job com a **mesma** variável
  nas duas pontas, com o aviso explícito no `validate` quando elas divergem —
  que é o mesmo defeito ("variável que chega a um lado e não ao outro") que o
  heartbeat já tinha sofrido e que foi corrigido duas vezes, com o padrão
  replicado.

**Validador de infra:** executei. É fail-closed, tem modo `--estrito` na CI, e o
mecanismo de pendências é bem desenhado — uma chave declarada que **não ocorre
mais** é FALHA, então a lista não pode envelhecer escondendo pendência nova
(testei essa lógica por leitura do `sed`+loop). Isso é melhor do que a maioria
dos "gate de infra" que eu já vi.

---

## Hipóteses minhas que foram descartadas (registro, como o reviewer anterior fez)

1. **"A guarda de conteúdo fictício é só uma lista que pode ficar desatualizada"**
   — **falso**: ela varre `app/**` e `lib/**` recursivamente; a lista só verifica
   existência. (O defeito real é outro — MAJOR-3, vocabularial.)
2. **"Com `OBSERVABILITY_TRUSTED_PROXY_NETWORKS` vazio o throttle fica
   inoperante"** — **falso para produção**: nginx na mesma máquina ⇒
   `REMOTE_ADDR` = loopback ⇒ o XFF é lido. Só a topologia Docker colapsa
   (MINOR-2), e o caso do CDN já estava documentado.
3. **"O plugin do Sentry auto-inicializa o SDK no browser, o que furaria o
   fail-closed"** — **falso**: li o `webpack.js` do SDK 10.75.3; ele apenas
   injeta o arquivo de config na entry, sem `init` próprio.
4. **"O smoke do deploy bloqueia deploy durante indisponibilidade de feed"** —
   **falso**: a Home é página ISR estática e o release carrega o HTML do build,
   então o `GET /` do smoke devolve o 200 assado. (O achado MAJOR-2 é o
   inverso: o ramo 503 é código morto e a crença documentada é falsa.)
5. **"O `/readyz` público seria bloqueado pelo `allow/deny` do nginx, e o check
   externo falharia sempre"** — **falso**: o `allow/deny` está só no bloco
   **HTTP:80** (probe local); o bloco **443** não tem restrição, por contrato.
6. **"`portal_ready` também não chegaria a nenhum scrape"** — **parcialmente
   falso**: ele é escrito por `/readyz` e `/health-detail`
   (`observability_views.py:153,175`), e o check externo do Better Stack sonda
   `/readyz` a cada 60 s, então a série chega — por acidente de arquitetura, e
   porque o registry é por processo com 2 workers, metade dos scrapes não a vê.
   O alerta de readiness funciona **no sentido da falha**; o de fila não
   funciona em nenhum sentido (MAJOR-1).

---

## Critérios do contrato: verificados, parciais e não alcançáveis

**Verificados com evidência executada (amostra):** 1, 2, 3 (header ponta a ponta,
geração e normalização), 5, 6 (política do Sentry conferida contra o tipo do
SDK), 7, 8, 9 (com a ressalva do MAJOR-1 para o sinal de fila), 12, 18, 21, 24,
25, 26, 27, 28, 30, 31, 34 (scripts fail-closed; execução real pendente),
38, 39, 40 (gates ligados na CI e executados localmente), 19 (condicional —
ver abaixo).

**Os três que eu já sabia não alcançáveis — julgamento:**

| # | critério | decisão documentada | julgamento |
|---|---|---|---|
| **11** | Home devolve **503** sem cache válido | `run-state.json:25` e `app/page.tsx:161-168`: impossível fixar status HTTP num Server Component do App Router; em runtime a falha **repropa** (5xx) e o `error.tsx` mostra a recuperação com código de suporte | **Defensável no núcleo, e mais profunda do que o run-state diz.** Server Component de página não tem como escolher status — isso é verdade. Mas o motivo real é mais forte: a Home é **ISR estática** (`revalidate = 60`, sem `force-dynamic`), então mesmo um 503 "perfeito" não apareceria no status de uma página em cache, e o caminho de código que hoje lança produziria **5xx**, não 503. O que **não** é defensável é a decisão ter parado no componente: ela não foi propagada para os dois consumidores (monitoramento e gate de deploy), que passaram a prometer um 503 inexistente — **MAJOR-2**. Julgamento: a limitação é real e foi declarada; a falha é de propagação, não de decisão. |
| **10** | feed indisponível com cache real ≤5 min: usa conteúdo real, **sinaliza degradação**, nunca fictício | `lib/ultimo-conteudo-real.ts` + `run-state.json:25`: "idade de cache e 503 do feed no backend dependem de reconciliação com a run 20260924-2136" | **Parcial, e a parte não verificada é a que importa.** O backend **não expõe** idade de cache (nem `cached_at`), e `backend/feed/views.py` está em WIP de outra run — a dependência declarada é real e não podia ser resolvida aqui. Mas o "sinaliza degradação" só acontece na janela em que `getData()` roda de fato: no estado estacionário, o ISR serve a última página boa com **200 e sem nenhum sinal** para o visitante (é stale-while-error legítimo, e está escrito; o que não pode é a revisão contar isso como "sinalizado"). Correção barata: incluir um carimbo de "servido do cache" no HTML/header ou aceitar o limite no texto do critério. **Não é atalho do Presentation** — o run-state diz "dependem de reconciliação", e a nota de `ultimo-conteudo-real.ts` é honesta sobre a janela. |
| **29** | build standalone sob PM2 com `HOSTNAME`, `PORT`, static e public corretos | `run-state.json:25`: "exige decisão entre migrar o PM2 para standalone ou reescrever o critério" | **Implementado e não verificado em ambiente real.** O `337ce37` já **migrou**: `run-standalone.sh` faz `prepare` (copia `public/` e `.next/static`, falha se `.next/static` faltar), `smoke` (sobe em porta livre, valida `/robots.txt`, um asset real de `.next/static` e a Home) e `start` (exporta `PORT`/`HOSTNAME`, `exec node server.js`), e o deploy usa `web_runtime: standalone` por padrão, com o PM2 apontando para o caminho estável `releases/current/standalone`. O que falta é **prova em ambiente real** (não há acesso a VPS nesta run) — e o texto do `run-state` está **desatualizado** ao dizer que a decisão está pendente (NIT-3): o resíduo real é "implementado, não exercitado na VPS". |

**Outros critérios que eu classifico como não verificáveis nesta revisão (e por
 quê), para não inflar severidade — são dependências de ambiente declarado, não
defeito de código:**

- **22 (runbook e destino por alerta)** — as 19 regras têm `severity`,
  `runbook:` e `runbook_url`, mas **todas** apontam para
  `runbooks.portal.exemplo.invalid` (RFC 2606, nunca resolve) e o destino
  (contact points) está explicitamente fora do repositório, com uma tabela de
  `<CP_*>` a criar. Pendência declarada em `pendencias-ci.txt`; o único desvio é
  o texto do README que diz que o validador falha (MINOR-8). **Parcial.**
- **23 e 41 (Better Stack dispara; entrega confirmada nos três canais e
  encerrada)** — `checks.json` é um template com `<DOMINIO_DE_PRODUCAO>`,
  `<TEAM_ID>`, `<CP_*>`; nada foi disparado, confirmado nem *acknowledged*.
  Além disso o MAJOR-2 afeta aentrês checks. **Não verificável aqui.**
- **32, 33, 35, 36, 37 (chave SSH, TLS, restore mensal, mudança de migration,
  runbook com owner/escalonamento)** — todos exigem ambiente real, conta externa
  ou janela aprovada. Os scripts e runbooks existem e são fail-closed; a
  **evidência de execução** não existe no repositório e a run sabe disso
  (`follow_up` nº 1 e 2). **Não verificáveis.**
- **42 (soak de 48 h)** — por definição posterior à revisão; o
  `run-state.json` mantém a fase `closing` como `pending`, o que está correto.
- **13 (registro de execução de ingestão com `queued/running/...`)** — pertence
  ao WIP da run `20260924-2136-ingestao-noticias` (`backend/catalogo_noticias/`),
  explicitamente fora de escopo. Agrava: a métrica que o resto do run cita como
  substituta (`portal_ingestion_executions_total`) é declarada e **nunca
  incrementada** — o próprio validador rejeita o uso dela, e o NIT-4 mostra uma
  unit citando um alerta que não existe. **Fora de escopo, com pendência real.**
- **14 (métricas de fila, atraso, retry, falha e duração consultáveis)** —
  **parcial por MAJOR-1**: "atraso" foi entregue (e funciona) pelo canal durável;
  "fila", "retry", "falha" e "duração" continuam em métricas que não chegam a
  nenhum scrape (o `_sum`/`_count` do canal cobre duração somada, mas os painéis
  e as regras antigas não foram migrados para lá).
- **17 (status/duração/erro sanitizado de dependência externa)** — **parcial**,
  como já registrado no `code-review-backend.md` (MINOR-12): só os probes de
  health, não as chamadas reais (Resend, ViaCEP/IBGE, fetch de feed). Não
  verificável por execução sem instrumentar; o sinal existe para as dependências
  do health, não para as chamadas.
- **19 (Sentry com ambiente/release corretos e PII desligada)** —
  **condicionalmente atendido**: `sendDefaultPii: false` e ambiente/release
  forçados existem e foram conferidos; mas com os defaults entregues
  (`SENTRY_TECHNICAL_CONSENT_DEFAULT=False`, `tecnico` não sincronizada com o
  backend) **nada é enviado**, nem do browser (SDK não carregado sem
  consentimento — que é o comportamento correto) nem do servidor do Next. O
  critério tem a preposição "quando o Sentry está configurado", então é
  literalmente satisfazível; o que o run promete é o **guardar** do critério 27, e
  ele é real. A decisão de rodar produção sem APM é humana e está pendente
  (MINOR-7).
- **42/48h e o resto do Definition of Done** — o `run-state.json` está
  coerente (fases `testing`/`documentation`/`closing` em `pending`, `findings`
  zerado apesar de 4 majors já revisados — **NIT**: `findings` não foi
  atualizado pela remediação; é o arquivo de estado, que não altero).

---

## Resumo objetivo para o orquestrador

- **Blockers: 0.** Não há caminho de corrupção de dados, vazamento de PII,
  indisponibilidade de produção ou irreversibilidade no diff.
- **Majors: 3**, todos "promessa de observabilidade sem dado" (MAJOR-1 painéis e
  alertas vazios; MAJOR-2 o 503 que não existe; MAJOR-3 a guarda que é lexical).
  Nenhum exige redesenho: MAJOR-1 e MAJOR-2 são correções de ~10 linhas cada em
  arquivos que já existem, mais a reescrita de dois painéis.
- **Minors: 10**, dos quais 3 merecem entrar na próxima rodada (MINOR-1 no BFF,
  MINOR-2 na documentação do compose, MINOR-3 no texto do `error.tsx`); os
  demais são de registro.
- **Nits: 6.**
- **A remediação do backend está correta** e não criou regressão: os 4 majors
  foram verificados por execução, os minors corrigidos conferem, e a suíte
  (353/811) segue verde. A prova de mutação de 26 casos é real (não tautológica),
  mas deveria ser versionada e rodar contra uma cópia da árvore.
- **Os três critérios que eu já sabia não alcançáveis:** 11 e 29 são defensáveis
  (o motivo do 11 é até mais profundo do que o declarado; o resíduo do 29 é
  "implementado, não verificado na VPS", e o `run-state` está desatualizado ao
  dizer que a decisão está pendente); 10 é parcial por falta do header de idade
  no backend (dependência declarada de outra run), mas o "sinaliza degradação"
  chega ao usuário só na janela de revalidação do ISR.
- **Nada foi alterado no repositório.** Este arquivo é o único artefato escrito
  por esta revisão; `code-review-backend.md` e `run-state.json` não foram tocados.
