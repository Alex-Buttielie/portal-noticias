# Documentation Update — 20260923-1600-p2-backend-perf

Documenter da run `20260923-1600-p2-backend-perf`. Esta etapa verificou e ajustou somente documentação de produto e o artefato de atualização; nenhum arquivo de código-fonte foi alterado.

## Documentos verificados e alterações

1. **`README.md:119-125` — paginação de comunidade**
   - **Antes:** os dois endpoints de listagem eram descritos apenas como “lista”; não havia informação sobre `page`, `page_size` ou o envelope.
   - **Depois:** publicações e comentários documentam `page`/`page_size`, padrão 20, máximo 100 e o envelope `count`/`next`/`previous`/`results` quando a paginação é explicitamente solicitada. A documentação deixa explícito que o formato legado continua disponível sem esses parâmetros.
   - **Linhas alteradas:** `README.md:119` e `README.md:122` contêm a descrição operacional da paginação.

2. **`README.md:178-180` — ingestão RSS condicional**
   - **Antes:** a seção de ingestão explicava busca, deduplicação e idempotência por URL, mas não os validators HTTP.
   - **Depois:** adiciona-se que `FonteRobo` persiste `ETag`/`Last-Modified`, envia `If-None-Match`/`If-Modified-Since`, trata `304` sem baixar nem parsear XML, confirma os validators somente após persistência segura e executa reconciliação periódica sem headers. O texto relaciona a economia de banda/tempo à distinção entre validator e prova de completude.

3. **`README.md:196` — Celery**
   - **Antes:** a execução periódica era associada ao Celery Beat, sem registrar a política por task.
   - **Depois:** informa que ingestão e registro de `EventoBusca` têm reentrega segura configurada por task, enquanto tasks com efeitos externos mantêm o comportamento padrão.

4. **`README.md:226-230` — `EventoBusca` assíncrono e rate limiting**
   - **Antes:** não havia uma seção própria ligando a busca pública, a métrica e o rate limiting.
   - **Depois:** documenta-se que `registrar_busca` despacha `feed.tasks.registrar_evento_busca` com payload JSON primitivo, preserva os dados de correlação, é idempotente por `request_id` quando disponível e nunca faz fallback para INSERT síncrono. Também se explicita que o throttle de escrita anônima não limita GETs de leitura e depende do Redis.

5. **`backend/.env.example:59-71, 146-148` — settings de P2**
   - **Verificado:** `CELERY_WORKER_MAX_TASKS_PER_CHILD=100`, `CATALOGO_NOTICIAS_REVALIDACAO_COMPLETA_HORAS=6` e `FEED_AUTOCOMPLETE_CACHE_TTL_SEGUNDOS=300` já estavam presentes, com comentários que explicam o default e o motivo.
   - **Resultado:** nenhuma alteração necessária; os três valores correspondem a `backend/config/settings.py` (300 s para autocomplete, 6 h para reconciliação e 100 tarefas por child).

6. **`ARCHITECTURE.md:12, 78, 132` — arquitetura transversal**
   - **Antes:** a stack de jobs não mencionava o registro assíncrono de `EventoBusca`; a seção de custo de IA e a tabela de performance não registravam validators HTTP/revalidação.
   - **Depois:** a stack cita o registro assíncrono de `EventoBusca`; a seção de custo de IA distingue economia de banda de custo de tokens e documenta `ETag`/`Last-Modified`, `If-None-Match`/`If-Modified-Since`, 304 e a reconciliação de 6 h; a tabela de performance registra a mesma proteção contra 304 falso ou perda local.

## Não alterado + motivo

- **`backend/.env.example`:** já documentava as novas settings com defaults e razão; não foi criado comentário redundante.
- **`README.md` demais:** as seções de stack, setup, frontend e segurança não continham afirmações incompatíveis com P2-2/P2-3/P2-4; a atualização foi limitada aos tópicos de ingestão, Celery, comunidade, busca e rate limiting.
- **`ANALISE_CUSTO_PERFORMANCE.md`, specs e históricos de outras runs:** são backlog, requisitos ou registros históricos, não documentação do estado atual; não foram reescritos.
- **Código, migrations, testes, frontend e infraestrutura:** fora do escopo do documenter; permaneceram intocados nesta etapa.

## Resultado

A documentação do produto agora explica a economia de banda por validators RSS, a reconciliação periódica, a paginação explícita da comunidade, o registro assíncrono/idempotente de `EventoBusca` e a política Celery por task. As settings novas já estavam suficientemente documentadas em `.env.example`; a evidência detalhada de linhas, decisões e limitações está neste artefato.
