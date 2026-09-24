# Implementation History — 20260923-0943-p0-correcoes-criticas

Executor: subagente (run 20260923-0943-p0-correcoes-criticas). Contrato v1 + task-plan.md lidos integralmente antes de qualquer edição. Sem commit git (só working tree).

## PARTE A — P0-1: preço estimado do LLM (0.15 → 0.0003 USD/1k)

### O que mudou (arquivo:linha)
1. `backend/config/settings.py:855-868` — default de `CATALOGO_NOTICIAS_LLM_PRECO_USD_POR_1K_TOKENS` de `0.15` para `0.0003`; comentário reescrito com a derivação exigida pelo contrato (gpt-4o-mini: entrada $0.15/1M = $0.00015/1k; saída $0.60/1M = $0.0006/1k; lote típico de 10 itens ≈ 5000 in + 2200 out ≈ $0.00029/1k → `0.0003` conservador; revisar quando o provedor de produção for escolhido). Nome da variável, unidade, leitura via env e fórmula em `providers/summarization.py:248-250,369-370` intactos.
2. `backend/.env.example` (novo bloco após `CATALOGO_NOTICIAS_LLM_MAX_TOKENS_POR_ITEM`) — documenta `CATALOGO_NOTICIAS_LLM_PRECO_USD_POR_1K_TOKENS=0.0003` (+ `CATALOGO_NOTICIAS_LLM_TETO_GASTO_DIARIO_USD=5.0`, par da mesma seção; o arquivo não citava nenhuma das duas vars).
3. `README.md` (seção "Teto de gasto diário com o provedor de LLM") — padrão `0.15` → `0.0003` com derivação resumida + volume suportado (~16M tokens/dia com o teto de $5).
4. `backend/catalogo_noticias/tests/test_summarization_provider.py:271-300` — `test_preco_configuravel_via_env_var...` fixava o valor antigo via `@override_settings(...=0.15)` + `approx(0.15)`; reescrito para travar o default corrigido (1000 tokens → `approx(0.0003)`) e cobrir o critério de aceite 2 (10000 tokens → `approx(0.003)`). Segunda metade (override `1.0` → `1.0`, configurabilidade) preservada. Outros testes da classe usam overrides próprios (0.20/0.30/1.0) — independentes do default, intocados.
5. `frontend/app/admin/robos/page.tsx:405` — dica de exemplo `Ex: 0.15.` → `Ex: 0.0003.` (fora da lista do contrato; mudança cosmética de 1 palavra, justificada: manter o exemplo consistente com o default corrigido).

### Por que NÃO mexi (decisões de escopo)
- `backend/catalogo_noticias/models.py:195` (`llm_preco_por_1k_tokens`, default 0.15) + `migrations/0003_*`: contrato veda mudança de schema ("Nenhuma mudança de schema de banco"); alterar o default do model exigiria migration. Leitura em `providers/summarization.py:136-149` e `services/config_robo.py:14-22`: sem linha `ConfiguracaoRobo` (pk=1) o provider usa o settings corrigido; com linha existente, vale o valor do banco (comportamento "quem definiu valor próprio não é afetado"). **Pendente:** deploy existente com linha preenchida pelo default antigo mantém 0.15 até ajuste manual via admin/env — ver Pendências.
- `ingestao-service/` (`app/config.py:40`, `app/schemas.py:96`, `app/pipeline/summarizer.py:149`, `.env.example:12`, `README.md:37`, `tests/test_pipeline.py:36,252`): repete o default 0.15, mas está fora do escopo (instrução: grep em `backend/`; áreas esperadas do contrato não listam o microserviço, desligado por padrão). Registrado como follow-up.
- Pesos `0.15` em `deduplicacao.py` e `0.15rem` em docs/CSS: não relacionados a preço de LLM.

### Evidências (pytest, `DJANGO_DB_ENGINE=sqlite3 DJANGO_CACHE_BACKEND=locmem`)
- Alvo: `pytest catalogo_noticias/tests/test_summarization_provider.py catalogo_noticias/tests/test_orcamento.py metricas/tests/test_custo_llm.py` → **32 passed**.
- Módulos afetados: `pytest catalogo_noticias metricas` → **142 passed**.
- Suíte completa: `pytest` resto (`--ignore=catalogo_noticias --ignore=metricas`) → **271 passed**. Total **413 passed, 0 failed** (só warnings pré-existentes de `staticfiles/` ausente). Nenhum teste exige Postgres de verdade.

### Critérios de aceite (contrato, Parte A)
1. ✅ Default sem env = `0.0003` (travado pelo teste reescrito).
2. ✅ 10000 tokens → `0.003`, não `1.5` (assert novo no mesmo teste).
3. ✅ Teto $5/dia ≈ 16M tokens/dia (documentado no README; 5/0.0003×1000 ≈ 16,7M).
4. ✅ pytest passa nos módulos afetados + suíte completa (acima). Cobertura mínima do CI (`--cov-fail-under=80`): não re-executada aqui — flag do CI, não do `pytest.ini` local; sem mudança de lógica, só de constante + teste. Complemento do historian (fonte: `run-state.json`, fase `testing`): o tester verificou de forma independente — veredito `passed` (5/5 critérios), suíte completa **413 passed**, cobertura **87.27%** (gate 80 OK).

## PARTE B — P0-4: ISR vs SSR (diagnóstico + correção)

### Evidência pré-correção (`npm run build`, Next 14 — `node_modules/` já presente, sem `npm ci`)
Todas as rotas ƒ (Dynamic), incluindo páginas 100% estáticas (`/sobre`, `/empresa`, `/termos` — sem `searchParams`/`headers`/`cookies` próprios). Único `headers()` em `app/`: `frontend/app/layout.tsx:50`. Conclusão: o `headers()` no root layout forçava o app inteiro para renderização por request, anulando o `revalidate` (`/` com `revalidate = 60` aparecia como ƒ). Exceções já-●: `/noticia/item/[id]`, `/noticia/cluster/[id]`, `/categoria/[slug]`, `/noticia/[id]`, `/autor/[id]`, `/paginas/[slug]` (pré-render dos params de `generateStaticParams`).

### O que mudou
- `frontend/app/layout.tsx:1-53` — removidos import `headers` (`next/headers`), import `perfilPorUserAgent` e o bloco try/catch; `<Providers>` sem `perfilInicial`. Comentário (português, com motivo + ref à run) explica o porquê. Detecção de UA preservada no cliente: `DeviceProvider` (`frontend/lib/dispositivos/DeviceProvider.tsx:30-34`) parte de `PERFIL_PADRAO_DESKTOP` e corrige pós-hidratação via `observarDispositivo` (matchMedia + touch + orientação — mais preciso que o palpite SSR por UA). `providers.tsx` intocado (prop `perfilInicial?` continua opcional). Nenhum fetch bloqueante adicionado; nenhuma dependência nova.

### Evidência pós-correção (rebuild limpo, exit 0, type-check do Next ok)
| Rota | Antes | Depois |
|---|---|---|
| `/` (revalidate 60) | ƒ | ○ Static (ISR: prerender + revalida a cada 60s) |
| `/ao-vivo` (revalidate 30) | ƒ | ○ Static (ISR) |
| `/noticia/item/[id]`, `/noticia/cluster/[id]`, `/categoria/[slug]` (revalidate 60 + static params) | ● | ● (inalterados) |
| `/buscar` (revalidate 0 + `searchParams.q`) | ƒ | ƒ — dinâmico legítimo, não causado pelo layout |
| `/arquivo` (`searchParams.page`) | ƒ | ƒ — dinâmico legítimo |
| `/api/[...path]` (`force-dynamic`) | ƒ | ƒ — intencional (proxy) |
| `/comunidade/[id]` (`"use client"`) | ƒ | ƒ — client component, não prerenderizável |
| Demais institucionais (`/sobre`, `/empresa`, ...) | ƒ | ○ |

Nota de nomenclatura: neste build o Next usa ○ para ISR sem params (`/`+revalidate) e ● para SSG com params; o contrato pedia "● (ISR, revalidate respectivo)" — a substância (estático + revalidação) está confirmada pelo ○ + `revalidate` declarado em cada page.

### Critério de aceite 5
✅ Evidência de `next build` acima (antes/depois); rotas de conteúdo estáticas; UA preservada no cliente via `DeviceProvider`. Trade-off consciente: primeira pintura em mobile usa o perfil desktop até a hidratação corrigir (antes, o SSR por UA acertava de primeira) — custo aceito pelo contrato em troca do ISR.

## Pendências / follow-ups (fora desta run)
1. `ingestao-service/` ainda tem default `0.15` (6 arquivos, item 2 de "Por que NÃO mexi") — mesmo bug, outro serviço; sugerir run dedicada.
2. Deploy com linha `ConfiguracaoRobo` (pk=1) já persistida carrega `llm_preco_por_1k_tokens=0.15` do banco, ignorando o settings corrigido — ajustar via tela admin de robôs ou env no deploy (one-liner manual, sem código).
3. `review-triggers.md`: diff final ≈ 50 inserções/21 deleções em 6 arquivos (7º arquivo modificado, `ARCHITECTURE.md`, é alteração preexistente de 2026-09-22 alheia a esta run — não tocado aqui), sem auth/billing/dados pessoais/migração/API pública/dependência nova → nenhum gatilho obrigatório; revisão formal dispensada.
4. Cobertura `--cov-fail-under=80` fica para o CI/tester (ver nota no item 4 da Parte A).
