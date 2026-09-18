# Serviço de Ingestão — Frente A (esqueleto)

Microserviço **independente** do portal (`backend/` não é importado nem
dependido aqui). Stack: FastAPI + uvicorn, pymongo (MongoDB 7 via compose),
feedparser, requests, pydantic v2, pytest + httpx.

## Como rodar

```bash
cd ingestao-service
cp .env.example .env        # ajuste INGESTAO_API_TOKEN!
pip install -r requirements.txt
uvicorn app.main:app --port 8001
# Swagger: http://localhost:8001/docs
# Health:  http://localhost:8001/healthz
```

Via Docker Compose (sobe API + MongoDB 7):

```bash
docker compose up --build
```

## Envs

| Var | Default | Descrição |
|---|---|---|
| `MONGO_URL` | `mongodb://localhost:27017` | Conexão Mongo (no compose: `mongodb://mongo:27017`) |
| `DB_NAME` | `ingestao` | Nome do banco |
| `INGESTAO_API_TOKEN` | `dev-token-trocar` | Token exigido no header `X-API-Token` |
| `PORT` | `8001` | Porta da API |
| `LLM_MODEL` | `gpt-4o-mini` | Modelo de resumo/clusterização |
| `LLM_BASE_URL` / `LLM_API_KEY` | `` | Endpoint/chave do provedor |
| `LLM_LOTE` | `10` | Itens por chamada LLM |
| `LLM_MAX_TOKENS` | `220` | Teto de tokens por resumo |
| `LLM_TETO_USD` | `5.0` | Teto de gasto LLM por dia (USD) |
| `LLM_PRECO_1K` | `0.15` | Preço por 1k tokens (USD) |
| `LLM_TIMEOUT` | `30` | Timeout por chamada (s) |

## Auth

Todas as rotas sob `/api/v1` exigem header `X-API-Token: <INGESTAO_API_TOKEN>`.
Exceção: `GET /healthz` (raiz) é público. `GET /metrics` raiz é público;
`GET /api/v1/metrics` exige token.

## Regras de negócio vindas do portal (defaults no schema `Config`)

- **Dedup:** similaridade ≥ `dedup_limiar=0.55`, janela `dedup_janela_horas=24h`,
  teto `dedup_max_itens=300` itens recentes comparados por execução.
- **Alta relevância:** categoria em `categorias_sensiveis` **e**
  `numero_fontes >= limiar_fontes_alta_relevancia=3` → `urgente=true`.
- **Revisão obrigatória de clusters:** `cluster_sempre_revisao=true` (default) —
  todo `tipo=cluster` entra na fila com `status_revisao=pendente`.
- **Anti-cópia de resumo:** bloqueia resumo com `ratio > resumo_sim_max=0.6`
  ou trecho literal > `resumo_trecho_max=0.6` da fonte original.
- **LLM:** lote `llm_lote=10`, `llm_max_tokens=220`, teto `llm_teto_usd=5.0/dia`,
  preço `llm_preco_1k=0.15 USD`, `llm_timeout=30s`.
- **Agendamento:** `intervalo_minutos=15`, flag `ativo` (pausa total).
- **Pertinentes (acrescentadas pela Frente A):**
  - `backoff por fonte`: falha consecutiva dobra o intervalo dessa fonte
    (máx. 2h) sem pausar as demais; registrado em `erros_por_fonte`.
  - `teto de itens por execução`: máx. 500 itens brutos por
    `POST /ingestao/executar` (excedente fica para o próximo ciclo).
  - `retenção de execuções`: manter últimas 100 `Execucao` no Mongo,
    apagar as mais antigas a cada ciclo.

## Rotas (prefixo `/api/v1`, contratos congelados)

Fontes: `GET/POST /fontes`, `PATCH/DELETE /fontes/{id}`,
`POST /fontes/sincronizar` · Ingestão: `POST /ingestao/executar`,
`GET /ingestao/execucoes` · Fila: `GET /fila`, `POST /fila/{id}/decisao` ·
Config: `GET/PATCH /config` · Feed: `GET /feed`, `GET /feed/urgentes`,
`GET /feed/cluster/{id}`, `GET /feed/item/{id}` · Sistema: `GET /healthz`,
`GET /metrics`. Stubs retornam `501 + TODO` até as Frentes B/C implementarem.
