# Análise de custo e performance (2026-09-22)

Análise disparada pelo pedido do responsável do projeto para revisar o
projeto inteiro visando **menor custo e mais performance**. Método: três
explorações paralelas profundas (backend Django, frontend Next.js,
infraestrutura/deploy), com os achados críticos **verificados
pessoalmente no código** (arquivo e linha citados abaixo). Onde algo
depende do estado da VPS (sem acesso nesta sessão), está marcado como
`[verificar na VPS]`.

Convenção: cada achado tem gravidade (🔴 crítico / 🟡 alto / 🟢 médio),
o estado atual com referência exata e a proposta. O plano de ação
priorizado está na seção 7. Gatilhos de "quando reconsiderar" seguem o
padrão da seção 9 do `ARCHITECTURE.md` (simplicidade deliberada, sem
overengineering).

## 1. Resumo executivo

| # | Achado | Gravidade | Eixo |
|---|---|---|---|
| A1 | Estimativa de custo de LLM **~1000x acima do preço real** (`summarization.py:249`, `settings.py:864`) — o teto de $5/dia se esgotaria em poucos lotes e o painel de métricas mostra custo inflado | 🔴 | Custo IA |
| B1 | Backup diário **provavelmente quebrado na topologia ativa** (`pg_backup.sh:36` usa `docker compose exec`; a VPS roda PM2 sem compose) — RPO de 24h comprometido | 🔴 | Confiabilidade |
| C1 | Feed público **sem cache nenhum + materializa o acervo inteiro em memória por request** (`feed/views.py:61`) + N+1 de `numero_fontes_distintas` — Redis instalado e ocioso | 🔴 | Performance |
| D1 | `headers()` no root layout (`app/layout.tsx:50`) pode converter **todo o ISR em SSR por request** | 🔴 | Performance |
| E1 | PROD em **HTTP puro sem TLS** (`portal-prod.conf:6`); Cloudflare (CDN/WAF grátis) possivelmente inativo `[verificar na VPS]` | 🟡 | Segurança/custo |
| F1 | React Query montado mas **zero `useQuery` usado**; `@tanstack/react-table` e `embla` são dependências órfãs | 🟡 | Performance |
| G1 | Gunicorn sync com **2 workers e `--timeout 180`** — 3 requisições presas derrubam a API | 🟡 | Performance |
| H1 | Nginx ativo **sem gzip/cache/keepalive**; estático e mídia passam pelo Gunicorn | 🟡 | Performance |
| I1 | **90 feeds RSS re-baixados por completo a cada 15 min** sem ETag/If-Modified-Since; `create` item a item sem `bulk_create` | 🟢 | Custo/perf |
| J1 | `catalogo_noticias` (o app mais consultado) é o **único sem nenhum `Meta.indexes`**; busca `icontains` em 9 campos sem `pg_trgm` | 🟡 | Performance |
| K1 | **3 stacks completas 24/7 na mesma VPS** (dev+homolog+prod) `[verificar na VPS]` | 🟢 | Custo |
| L1 | **Build do frontend roda na VPS a cada deploy**, sem cache — risco de OOM | 🟢 | Custo |
| M1 | Celery sem `acks_late`/`prefetch` — task perdida se o worker cair no meio da ingestão | 🟢 | Confiabilidade |

## 2. Custo de IA

### A1. Unidade de preço do LLM errada por ~1000x (🔴)

- **Estado atual.** `custo_estimado_usd = (tokens_utilizados / 1000) * preco_usd_por_1k_tokens`
  (`backend/catalogo_noticias/providers/summarization.py:248-250`), com
  default `CATALOGO_NOTICIAS_LLM_PRECO_USD_POR_1K_TOKENS = 0.15`
  (`backend/config/settings.py:864-866`). O comentário em
  `settings.py:860-863` afirma que 0.15 está "na mesma faixa de mercado
  de um modelo economico tipo `gpt-4o-mini`" — **incorreto por 3 ordens
  de magnitude** (provável confusão USD/1M vs USD/1k): o gpt-4o-mini
  (default de `CATALOGO_NOTICIAS_LLM_MODEL`) custa ~$0.15/**1M** tokens
  de entrada ($0.00015/1k) e ~$0.60/**1M** de saída ($0.0006/1k);
  blended real ~$0.0002–0.0006/1k. A estimativa atual é **~250–1000x
  acima do preço real**.
- **Consequências.** (a) O teto de $5/dia
  (`CATALOGO_NOTICIAS_LLM_TETO_GASTO_DIARIO_USD`) se esgotaria após
  **~33 mil tokens** — 2–3 lotes de 10 itens: em produção, a sumarização
  automática cairia para revisão humana quase imediatamente, não por
  economia real, mas por erro de unidade. (b) O painel de métricas
  (`GET /api/metricas/painel/`, campos `custo_llm_hoje_usd`) exibe custo
  ~1000x inflado — qualquer decisão de orçamento tomada sobre esses
  números estará errada.
- **Proposta.** Corrigir o default para o preço real do provedor
  escolhido **na mesma unidade declarada (USD/1k tokens)** — ex.:
  gpt-4o-mini blended ~`0.0003`; Groq Llama 3.1 8B ~`0.00005–0.00008`;
  Gemini Flash ~`0.0003` — ou redefinir a variável para USD/1M com o
  nome ajustado. Com o preço real, o **mesmo teto de $5/dia passa a
  cobrir ~16M+ tokens/dia em vez de 33k**. Esforço: baixo (1 default +
  `.env.example` + docs + ajuste de teste que fixe o valor antigo).
- **Alavancas adicionais (sem mudar provedor).** A interface
  `SummarizationProvider` já aceita qualquer endpoint compatível com
  Chat Completions: **Groq tem tier gratuito generoso** (caminho de
  menor custo imediato); Ollama local = custo zero, mas a VPS
  (4GB compartilhada com Postgres/Redis/3 stacks) provavelmente não tem
  RAM para um modelo quantizado + todo o resto — **não recomendado sem
  medir antes `[verificar na VPS]`**. Outras alavancas: intervalo de
  ingestão (15 min × 90 feeds ≈ 8,6k HTTP calls/dia) e resumir apenas o
  que será publicado.

## 3. Confiabilidade (custo de não ter)

### B1. Backup diário quebrado na topologia ativa (🔴)

- **Estado atual.** `infra/backup/pg_backup.sh:36-38,44-49,62-64`
  executa `docker compose exec -T db pg_dump` e `docker compose exec -T
  web tar`. Mas o deploy ativo na VPS é **PM2 + Nginx, sem Docker
  Compose** (`CI-CD.md:3-7`; nota de drift em `infra/DEPLOY.md:10-12` e
  `Caddyfile:8-9`). O cron diário (`0 3 * * *`, `pg_backup.sh:5`)
  **falha todos os dias** nessa topologia — ou nunca foi instalado nela.
  Agravantes: `BACKUP_S3_BUCKET` vazio = backup só na própria VPS
  (`pg_backup.sh:76-78`); sem remoto, **nada é limpo localmente**
  (`pg_backup.sh:90`) — risco de encher o disco.
- **Proposta.** (1) `[verificar na VPS]` se existe backup funcional
  hoje. (2) Criar caminho de backup nativo para a topologia PM2
  (`pg_dump` direto no host + `tar` de `/home/apps/portal-prod/media`)
  ou unificar a topologia (seção 6). (3) Configurar
  `BACKUP_S3_BUCKET` (R2/B2, tier gratuito cobre o volume inicial) +
  lifecycle rule de 90 dias no bucket. Esforço: médio.

### M1. Celery sem `acks_late` (🟢)

- **Estado atual.** `backend/config/celery.py:15-17` não define
  `worker_concurrency`, `worker_prefetch_multiplier`,
  `task_acks_late` nem `worker_max_tasks_per_child` — valem os defaults
  (`acks_late=False`: task perdida se o worker cair no meio da
  ingestão; a idempotência por URL protege contra reprocessar, mas o
  trabalho em progresso se perde).
- **Proposta.** `task_acks_late=True` +
  `worker_prefetch_multiplier=1` para a ingestão (tarefa longa).
  Esforço: baixo.

## 4. Performance do backend

### C1. Feed sem cache + materialização total + N+1 (🔴)

- **Estado atual.**
  - `backend/feed/views.py:61`: `itens =
    list(services.itens_publicaveis(...))` carrega **todos** os
    `NewsItem` publicáveis — **todas as colunas, incluindo
    `conteudo_bruto` e `conteudo_completo` (até 8KB cada)** — para a
    memória **antes** de paginar 20. Repetido em `feed/views.py:216`
    (seções), `feed/views.py:235` (destaques) e
    `radar/services.py:166`. `MaisLidasView` carrega 120 itens e
    reordena em Python (`feed/services.py:231`).
  - N+1: `backend/feed/services.py:71` acessa
    `item.cluster.numero_fontes_distintas`, uma property que executa
    **1 COUNT DISTINCT por cluster-entrada, por request**
    (`catalogo_noticias/models.py:27-29`). O `select_related("cluster")`
    não ajuda (joina a FK, não o related manager).
  - **Zero** `cache_page` no backend inteiro; nenhum `Cache-Control` ou
    `ETag` em nenhuma view. O comentário em
    `config/settings.py:405-407` afirma que `feed/` usa cache — **não
    usa** (drift documentação × código).
  - Custo por request adicional: `ConfiguracaoSistema` sem cache
    (`gating/services.py:27`, 1 query por response do feed);
    `RegraCuradoria` materializada por request
    (`painel_admin/services_regras.py:30-31`); `MeusRecursosView` com
    ~3N queries (`gating/views.py:21-35`); `EventoBusca.objects.create`
    síncrono no caminho de leitura (`feed/busca.py:278-289`).
- **Proposta (ordem de ROI).**
  1. **Denormalizar `numero_fontes_distintas` como coluna de
     `NewsCluster`**, atualizada na ingestão — elimina o N+1 de vez
     (migração + ajuste em `ingestao.py:523`).
  2. **Corte no SQL + `.only()`/defer**: janela de 48–72h e exclusão
     das colunas de texto (`conteudo_bruto`, `conteudo_completo`) nas
     listagens — o payload do feed (`FeedEntrySerializer`,
     `feed/serializers.py:4-31`) já **não** envia `conteudo_bruto`
     (✔), mas o banco o transfere para a memória do worker a cada
     request.
  3. **Cache de listagens públicas** (TTL 30–60s, chave por querystring
     normalizada) — o Redis já está instalado e praticamente ocioso.
     Atenção arquitetural: a resposta do feed inclui
     `exibir_publicidade`, que depende do usuário — para permitir cache
     (inclusive de borda, seção 6), **mover essa flag para
     `/api/gating/status`** (endpoint que já existe e o frontend já
     chama em toda página via `lib/premium.ts:75-99`).
  4. Corrigir o comentário de `settings.py:405-407` (ou implementar o
     que ele descreve).

### J1. Índices ausentes no app mais consultado (🟡)

- **Estado atual.** `catalogo_noticias/models.py`: **nenhum
  `Meta.indexes`** em `NewsItem`, `NewsCluster`, `FonteRobo`,
  `ConfiguracaoRobo` ou `RegistroExecucaoIngestao` (só `unique=True` em
  `url_fonte_original`). Filtros frequentes sem índice:
  `status_revisao` + ordem por `timestamp_ingestao`, `categoria`,
  `urgente`, localidade. Busca: `icontains` sobre **9 campos**
  (`feed/busca.py:84-100`) = seq scan por busca, sem `pg_trgm`.
- **Proposta.** Migração com índice composto
  `(status_revisao, -timestamp_ingestao)` + índices em
  `categoria`/`urgente`/localidade; extensão `pg_trgm` + índice GIN
  para a busca (ou FTS dedicado quando o volume justificar).
  Esforço: baixo.

### I1. Ingestão: re-download total + `create` unitário (🟢)

- **Estado atual.** ~90 fontes (`settings.py:599-691`), fetch paralelo
  (ThreadPoolExecutor, 8 workers) a cada 15 min — mas **sem
  ETag/If-Modified-Since**: `requests.get` baixa o XML inteiro sempre
  (`providers/news_source.py:223-241`), mesmo sem mudança. Persistência:
  `NewsItem.objects.create` item a item, sem `bulk_create`
  (`ingestao.py:358-375,500-513`); `cfg_valor` dispara ~8 queries por
  execução sem cache; 1 query SUM de gasto **por lote de LLM**
  (`orcamento.py:55-58` — o acumulado já está em memória).
- **Proposta.** ETag/If-Modified-Since por fonte (persistir
  validators); `bulk_create` para itens; consolidar `cfg_valor` em 1
  leitura por execução; cache do gasto do dia. Esforço: médio.

### Outros (🟢)

- **Gunicorn (G1):** `backend/Dockerfile:37` (`--workers 3 --timeout
  180`, sync sem threads); ativo usa `--workers 2`
  (`.github/workflows/deploy.yml:186`). Proposta: `--worker-class
  gthread --threads 2-4` (I/O-bound; `CONN_MAX_AGE=60` já configurado)
  + timeout 30–60s; mover `migrate` do entrypoint para job separado.
- **Comunidade sem paginação + N+1 de autor**
  (`comunidade/views.py:61,165`; `autor_nome` sem
  `select_related("autor")`) — paginar + `select_related`.
- **`EventoBusca.objects.create` síncrono** por busca pública
  (`feed/busca.py:278-289`) — mover para Celery ou amostrar.
- **Busca autocomplete** (`feed/busca.py:220`): `DISTINCT` sobre a
  tabela inteira por keystroke — cachear a lista de categorias.

## 5. Performance do frontend

### D1. `headers()` no root layout pode anular todo o ISR (🔴)

- **Estado atual.** `frontend/app/layout.tsx:48-53` lê
  `headers().get("user-agent")` no **root layout** (parte de todas as
  rotas) para detecção mobile/desktop. No Next 14, esse é o caso
  clássico de opt-in a renderização dinâmica: se o build marcar as
  rotas como dinâmicas, **todo `revalidate=60` vira SSR por request** e
  os `fetch()` passam a `no-store` — **cada visita bate no Django**.
  Não há `.next/` no repo para confirmar o comportamento efetivo.
- **Proposta.** Rodar `next build` e conferir os marcadores de rota
  (`●` ISR vs `ƒ` Dynamic). Se dinâmico: mover a detecção de UA para um
  client component isolado (`DeviceProvider` já corrige pós-hidratação)
  e deixar o root layout 100% estático. Esforço: baixo (diagnóstico) a
  médio (refatoração).

### F1. React Query morto + dependências órfãs (🟡)

- **Estado atual.** `QueryClient` montado globalmente
  (`app/providers.tsx:22`, `staleTime: 60s`) mas **nenhum componente
  importa `@/lib/queries`** (779 linhas, ~40 hooks — código morto);
  todo fetching real é `fetch` cru em `useEffect`, sem cache
  compartilhado entre rotas. `@tanstack/react-table` e
  `embla-carousel-react` nunca são importados (órfãs, mas instaladas e
  pesando no `npm ci`/build).
- **Proposta.** Decidir um dos dois: (a) migrar os `fetch` em
  `useEffect` para os hooks de `lib/queries.ts` (ganha cache entre
  navegações); ou (b) remover `lib/queries.ts` e as dependências órfãs
  do `package.json`. Esforço: médio (a) / baixo (b).

### Outros (🟢)

- **Imagens sem `next/image`** (`components/ImagemNoticia.tsx:77-85`,
  `<img>` puro; zero usos de `next/image` no projeto): sem WebP/AVIF,
  sem resize; `srcSet` só para URLs picsum (`lib/imagens.ts:74`) —
  imagens reais de RSS sem redimensionamento no mobile. Proposta: loader
  próprio ou `next/image` + `remotePatterns` (e `unoptimized` para
  domínios desconhecidos) + preconnect para `picsum.photos`.
- **SecaoColunistas: até 6 requisições client-side por visita à Home**
  (`SecaoColunistas.tsx:63-72` + `lib/colunistas.ts:73-126`) — mover
  para server component (entra no ISR da Home) ou endpoint agregado.
- **Polling duplicado do feed** (`UltimasNoticias.tsx:55-61`, a cada
  90s sobre ISR de 60s) — `router.refresh()` ou intervalo maior.
- **AdSense sem consentimento** (`AdsScript.tsx:13-23`,
  `strategy="afterInteractive"` em todas as páginas, sem consultar
  `permiteCategoria`) — LGPD + `lazyOnload`.
- **`import * as api` em 23 arquivos**, incluindo `lib/auth-context.tsx`
  no root layout — `lib/api.ts` (~1.373 linhas) entra no chunk
  compartilhado do cliente; preferir imports nomeados.
- **Dupla instrumentação de `news_view`** (`AnalyticsTracker` derivado
  de URL + `NoticiaReporter` explícito em `Reporters.tsx:26`).

## 6. Infraestrutura e custo recorrente

### E1. PROD em HTTP puro; Cloudflare possivelmente inativo (🟡)

- **Estado atual.** `infra/nginx/portal-prod.conf:6`: `listen 80`
  apenas — sem 443/TLS/HTTP2; `deploy.yml:160` gera `.env` com
  `DJANGO_SECURE_SSL_REDIRECT=false` e cookies sem `Secure`. O plano
  Cloudflare (CDN/WAF/DDoS grátis + Brotli, `infra/DEPLOY.md:63-76`) não
  tem evidência de ativação `[verificar na VPS]`.
- **Proposta.** Certificado de origem Cloudflare (grátis, longa
  duração, sem renovação manual) ou certbot + proxy laranja + SSL
  "Full (strict)". Ganho triplo a custo zero: TLS, **CDN/WAF/DDoS** e
  base para **cache de borda do feed público** (o feed é majoritariamente
  leitura; ver item C1.3 sobre mover `exibir_publicidade` para fora da
  resposta cacheável).

### H1. Nginx sem otimizações básicas (🟡)

- **Estado atual.** Zero `gzip`/`proxy_cache`/`expires`/`keepalive` nos
  `infra/nginx/*.conf`; `/api/*` sem `proxy_http_version 1.1` + keepalive
  (TCP novo por request); `proxy_read_timeout 180s`; `/static/` e
  `/media/` passam pelo WhiteNoise/Gunicorn (CPU); `limit_req`
  comentado. (A variante Docker/Caddy já tem `encode zstd gzip` e
  `file_server` para estático/mídia — `Caddyfile:31,55,37-44` — mas não
  é a topologia ativa.)
- **Proposta.** gzip (ou brotli via Cloudflare), `proxy_cache` para
  `/api/feed/` + `/api/radar/tendencias`, bloco `upstream` com
  `keepalive 32`, servir `/static/` e `/media/` direto do Nginx,
  `limit_req` ativo. Esforço: baixo.

### K1. Três stacks 24/7 numa VPS (🟢)

- **Estado atual.** DEV + HOMOLOG + PROD na mesma VPS (6 processos PM2
  + Postgres + Redis + Nginx, 24/7); Next single-process por ambiente;
  build do frontend **na VPS a cada deploy** (`deploy.yml:163-165`,
  `npm ci` + `npm run build` sem cache — pesado, risco de OOM);
  `guard` do deploy duplica o CI sem cache (`deploy.yml:102-117`); sem
  `concurrency:` group (deploys simultâneos colidem no `pm2
  delete/start`).
- **Proposta.** (1) DEV/HOMOLOG on-demand (`pm2 stop` fora do horário
  via cron) ou mesclar dev+homolog. (2) **Build no runner do GitHub
  Actions + rsync do artefato** (elimina OOM e acelera deploy); ou, no
  mínimo, swap + cache npm na VPS. (3) Remover o `guard` redundante (o
  CI já valida) e adicionar `concurrency:` group por ambiente.
  Esforço: médio.

### Outros (🟢)

- **Postgres sem tuning** (`shared_buffers`/`work_mem` defaults) + log
  de backup em append sem rotação (`DEPLOY.md:114`) + sem `logging:
  max-size` no compose — aplicar tuning conservador para 4GB e rotação.
- **Drift Docker × PM2**: duas topologias paralelas (compose + Caddy na
  raiz vs PM2 + Nginx ativos). Decidir a canônica e arquivar a outra
  como variante local — o Caddyfile já se declara "variante Docker
  alternativa" (`Caddyfile:8-9`); registrar a decisão em
  `PROD_DECISOES.md`.
- **Achado histórico — resolvido em 2026-09-24:** o diretório
  `ingestao-service/` duplicava o pipeline Django (FastAPI + MongoDB, 43 testes
  fora do CI e exposição anterior de Mongo em `0.0.0.0:27017`). A decisão
  humana foi arquivá-lo definitivamente; o código, o adaptador do portal e as
  flags foram removidos. Django/PostgreSQL/Celery permanece como única fonte de
  verdade. Contêineres e volumes externos existentes exigem desligamento e
  eventual remoção manual após backup; esta decisão de repositório não
  declara que esses dados foram apagados.
- **`requirements-lock.txt` desatualizado** (nota no próprio
  `requirements.txt:69-73`); `pytest`/`pytest-cov` na imagem de
  runtime — separar requirements de dev.

## 7. Plano de ação

Ordem = impacto por esforço. Itens de código seguem o processo do
projeto (skill `agentic-run`); itens `[VPS]` exigem acesso humano à
máquina e ficam como runbook + verificação.

### P0 — risco/custo crítico

| # | Item | Achado | Esforço |
|---|---|---|---|
| P0-1 | Corrigir unidade/preço estimado do LLM (default + `.env.example` + docs + testes) | A1 | Baixo |
| P0-2 | Backup funcional na topologia PM2 (script nativo + runbook + `BACKUP_S3_BUCKET`) `[VPS]` | B1 | Médio |
| P0-3 | TLS em PROD via Cloudflare (origin cert + proxy laranja + Full strict) `[VPS]` | E1 | Médio |
| P0-4 | `next build` para confirmar ISR vs Dynamic; corrigir `headers()` se dinâmico | D1 | Baixo→médio |

### P1 — performance (maior ROI)

| # | Item | Achado | Esforço |
|---|---|---|---|
| P1-1 | Feed: denormalizar `numero_fontes_distintas` + corte SQL/`.only()` + cache 30–60s + mover `exibir_publicidade` para `/api/gating/status` | C1 | Médio |
| P1-2 | Índices `catalogo_noticias` + `pg_trgm` para busca | J1 | Baixo |
| P1-3 | Gunicorn `gthread` + threads + timeout 30–60s | G1 | Baixo |
| P1-4 | Nginx: gzip + `proxy_cache` feed/radar + keepalive + static/media direto + `limit_req` | H1 | Baixo |
| P1-5 | Build do frontend no runner do CI + `concurrency` + remover `guard` redundante | K1/L1 | Médio |
| P1-6 | React Query: migrar `fetch` em `useEffect` para hooks **ou** remover código/deps mortas | F1 | Médio/baixo |

### P2 — custo e limpeza

| # | Item | Achado | Esforço |
|---|---|---|---|
| P2-1 | DEV/HOMOLOG on-demand (cron `pm2 stop/start`) `[VPS]` | K1 | Baixo |
| P2-2 | Ingestão: ETag/If-Modified-Since + `bulk_create` + consolidar `cfg_valor`/gasto | I1 | Médio |
| P2-3 | Comunidade: paginação + `select_related("autor")`; `EventoBusca` async/amostrado; autocomplete cacheado | C1/J1 | Baixo |
| P2-4 | Celery `acks_late` + `prefetch_multiplier=1` | M1 | Baixo |
| P2-5 | Colunistas server-side; polling 90s → `router.refresh()`; AdSense com consentimento + `lazyOnload`; imports nomeados de `lib/api` | §5 | Médio |
| P2-6 | Postgres tuning + rotação de logs | §6 | Baixo |
| P2-7 | Arquivamento do segundo pipeline **concluído em 2026-09-24**; follow-up: `requirements-lock` regenerado e requirements de dev separadas | §6 | Baixo |

### Gatilhos para reconsiderar (não fazer agora)

- **Mídia em object storage (R2):** quando uploads se aproximarem do disco da VPS.
- **Multi-nó / pgbouncer dedicado:** quando o tráfego não couber em 2–4 vCPU/4GB mesmo com P1 aplicado.
- **FTS dedicado (Elastic/Typesense):** quando `pg_trgm` não sustentar a busca.
- **`next/image` com otimizador próprio:** quando o volume de imagens RSS justificar o custo de CPU/disco do resize.
- **Ollama local para resumos:** somente após medir RAM livre real na VPS `[VPS]`.
