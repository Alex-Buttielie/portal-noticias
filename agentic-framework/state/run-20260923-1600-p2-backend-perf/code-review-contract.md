<!--
CONTRACT: code-review-contract
DONO: reviewer
QUANDO E CRIADO: revisão formal da run 20260923-1600-p2-backend-perf
-->

# Code Review Contract — 20260923-1600-p2-backend-perf

## Metadados

- **run_id:** `20260923-1600-p2-backend-perf`
- **escopo revisado:** somente o diff dos arquivos de `backend/comunidade/`, `backend/feed/`, `backend/catalogo_noticias/`, `backend/config/settings.py`, `backend/config/settings_test.py` e `backend/.env.example`; `frontend/` foi lido apenas como contrato do consumidor, sem tratar suas mudanças (inexistentes nesta run) como parte do escopo.
- **contrato de referência:** `implementation-contract.md` da própria run.
- **histórico lido:** `implementation-history.md` da própria run.
- **gatilhos aplicados:** duas migrations de schema; alteração de API pública; alteração de pipeline/ingestão e tarefas de background; risco jurídico de direitos autorais/compliance (BRD §18); diff acima de 300 linhas.
- **mudanças de outras runs:** ignoradas (`frontend`, nginx/gunicorn, `robos_views` e demais arquivos fora da lista explícita).

## Findings

### Finding 1 — major — `correctness / API pública`: a compatibilidade de formato oculta uma perda de conteúdo

- **Arquivos/linhas:** `backend/comunidade/views.py:35-50, 66-98, 192-202`; contrato do consumidor em `frontend/lib/api.ts:691-708, 756-764` e `frontend/app/comunidade/page.tsx:103-115` (somente leitura, fora do escopo de mudanças).
- **Evidência concreta:** `_paginar_comunidade()` sempre aplica `PageNumberPagination`; sem `page`/`page_size` devolve `Response(dados)` com no máximo 20 itens, mas sem `next`/`count`. Os dois clientes atuais ainda declaram `Promise<Publicacao[]>`/`Promise<Comentario[]>`, não enviam parâmetros de página e renderizam todos os itens recebidos; o detalhe também carrega comentarios com uma chamada sem paginação. Com mais de 20 publicações ou comentários, o restante desaparece silenciosamente e os contadores da tela passam a subnotificar o acervo.
- **Cenário de impacto:** o formato JSON continua sendo lista, portanto a migração pode parecer compatível, mas a API pública mudou de “todos os resultados” para “primeira página” para os consumidores que não conhecem o novo contrato; a própria página principal mostra somente os 20 primeiros e não há como avançar.
- **Correção sugerida:** coordenar a implantação com os consumidores: adicionar `page`/`page_size`, tratar `results`/`next` e o controle de páginas, ou oferecer uma API versionada/explicitamente paginada antes de truncar o contrato legado; adicionar teste de contrato contra o cliente real e teste de UI para mais de 20 itens.

### Finding 2 — major — `data integrity / ingestão`: um `304` é tratado como prova de que o acervo local está completo

- **Arquivos/linhas:** `backend/catalogo_noticias/providers/news_source.py:283-301, 366-370`; `backend/catalogo_noticias/services/ingestao.py:641-654, 818-831`.
- **Evidência concreta:** qualquer resposta `304` retorna `[]` antes de parse e o pipeline trata a fonte como fetch bem-sucedido; não existe digest da representação, marca de execução completa por fonte nem reconciliação local que possa detectar um `304` falso. Se o feed mudar o XML mas reutilizar um ETag/`Last-Modified`, ou se as linhas locais tiverem sido restauradas/apagadas enquanto o validator permaneceu no `FonteRobo`, as próximas execuções continuarão recebendo `304` e nunca tentarão preencher o acervo.
- **Distinção importante:** a janela específica de worker morto entre fetch e persistência **está** coberta: o header só é capturado em memória após parse e `confirmar_validadores()` só grava depois de todos os grupos e do `RegistroExecucaoIngestao`; o Finding não afirma que essa janela ainda esteja aberta.
- **Correção sugerida:** tratar validators como otimização, não como prova de integridade: executar uma busca incondicional periódica (ou outra reconciliação independente), persistir um digest/marcador de representação concluída e validar esse marcador antes de aceitar `304`; adicionar teste com servidor que devolve `304` apesar de conteúdo local ausente e com feed que muda mantendo o mesmo validator.

### Finding 3 — major — `data integrity / validators`: a identidade do URL não é verificada ao confirmar o ETag

- **Arquivos/linhas:** `backend/catalogo_noticias/providers/news_source.py:256-281`; `backend/catalogo_noticias/models.py:189-197`; `backend/catalogo_noticias/robos_serializers.py:24-30`; `backend/catalogo_noticias/management/commands/sincronizar_fontes_padrao.py:51-57`; `backend/catalogo_noticias/admin.py:6-10`.
- **Evidência concreta:** serializer e comando limpam validators em dois caminhos específicos, mas `FonteRobo` não tem `save()` centralizado e o admin nativo permite editar URL e os novos campos. `confirmar_validadores()` faz `fonte.save(update_fields=["etag", "last_modified"])` sem exigir `fonte.url == self.url_feed`; se a URL for trocada enquanto o LLM/ingestão está em andamento, o validator do feed antigo pode ser gravado na linha que já aponta para o feed novo, e a próxima requisição pode receber `304` para o recurso errado.
- **Correção sugerida:** centralizar a invalidação em `FonteRobo.save()`/serviço de domínio, marcar `etag`/`last_modified` como read-only no admin e confirmar com update condicional `filter(pk=..., url=self.url_feed)`; se zero linhas forem atualizadas, descartar o resultado e forçar nova leitura; testar mudança de URL via API, admin e corrida concorrente.

### Finding 4 — major — `correctness / Celery`: `acks_late` e `reject_on_worker_lost` são globais, não apenas da ingestão

- **Arquivo/linhas:** `backend/config/settings.py:516-525`.
- **Evidência concreta:** o `Celery` carrega essas settings como defaults para todas as tasks; a verificação independente no processo mostrou `task_acks_late=True` e `task_reject_on_worker_lost=True` também em `newsletter.tasks.enviar_newsletters*`, `b2b.tasks.verificar_alertas_task` e `assinatura.tasks.processar_vencimentos`, embora essas operações enviem e-mail/efeitos externos e não tenham idempotência por execução. Se o worker morre depois do envio e antes do ack/marcador, a reentrega pode enviar o mesmo e-mail ou alerta novamente.
- **Correção sugerida:** limitar `acks_late`/rejeição à task de ingestão (e à task de evento quando realmente idempotente), ou explicitamente proteger todas as demais tasks com opt-out e idempotência durável; adicionar teste de worker perdido para os efeitos externos.

### Finding 5 — major — `custo/idempotência`: a chamada ao LLM pode ser repetida e seu custo não fica registrado antes da persistência

- **Arquivos/linhas:** `backend/catalogo_noticias/services/ingestao.py:670-803, 807-816`; `backend/catalogo_noticias/tasks.py:26-29`.
- **Evidência concreta:** o provider é chamado em `ingestao.py:764` antes de qualquer `NewsItem` ser persistido; se o worker cair depois da resposta do LLM e antes de `_persistir_grupo`, a reexecução filtra somente URLs já commitadas e chama o LLM novamente para os mesmos itens. Não há chave/resultado de lote durável nem registro de uso intermediário; `RegistroExecucaoIngestao` só é criado no fim, então o custo de uma chamada perdida não entra no cálculo do teto diário nem no painel.
- **Correção sugerida:** persistir resultado/uso por chave idempotente de lote antes do ack, ou reservar e registrar custo imediatamente por chamada; se o custo duplicado for aceito como semântica at-least-once, documentar o risco, o limite máximo de repetição e a métrica de custo real, em vez de afirmar apenas “idempotente por URL”.

### Finding 6 — major — `data integrity / concorrência`: a idempotência por URL é check-then-insert e pode abortar a execução

- **Arquivos/linhas:** `backend/catalogo_noticias/services/ingestao.py:61-75, 318-332, 646-654`; teste de reentrega `backend/catalogo_noticias/tests/test_p2_ingestao_performance.py:327-342`.
- **Evidência concreta:** `_urls_ja_ingeridas()` é consultado por fonte antes de qualquer insert do lote; URLs repetidas dentro do mesmo feed ou presentes em duas fontes permanecem na lista, e duas execuções concorrentes podem ambas passar pelo SELECT. Em ambos os casos o `UNIQUE(url_fonte_original)` faz `bulk_create()` lançar `IntegrityError`; não há `INSERT ... ON CONFLICT`, requery ou catch que permita continuar, e o registro/validators da execução não são concluídos. O teste existente cobre apenas duas execuções sequenciais depois do commit.
- **Correção sugerida:** canonicalizar/deduplicar URLs antes do agrupamento e usar um protocolo de insert atômico com tratamento de conflitos/requery (ou lock distribuído por fonte/URL); testar duplicatas no mesmo lote e duas execuções realmente paralelas, verificando que a task termina sem perder os demais grupos.

### Finding 7 — minor — `validação`: `bulk_create` preserva `clean()`, mas não executa `full_clean()`

- **Arquivos/linhas:** `backend/catalogo_noticias/services/ingestao.py:318-332`; `backend/catalogo_noticias/models.py:165-182`.
- **Evidência concreta:** o helper chama `item.clean()` e a busca por signals não encontrou `pre_save`/`post_save`; portanto não há lógica `save()`-only sendo perdida e a exigência de URL/nome vazio continua coberta. Porém `NewsItem.save()` também só chamava `clean()`, e `clean()` aceita por exemplo `url_fonte_original="nao-e-url"`, enquanto `full_clean()` o rejeita; choices, formato de URL e limites de campo não são validados no caminho de lote. É uma lacuna residual (o `objects.create()` anterior tinha a mesma lacuna), não um bypass novo do `save()`.
- **Correção sugerida:** chamar `full_clean()` com estratégia explícita para unicidade/banco ou validar os campos relevantes em memória antes do lote e adicionar testes de URL/choices/tamanho; se a compatibilidade legado for intencional, registrar o risco residual em vez de afirmar validação completa.

### Finding 8 — minor — `cache`: o snapshot de títulos pode perder correspondências antigas e não é invalidado na ingestão

- **Arquivos/linhas:** `backend/feed/busca.py:264-288, 326-342`; `backend/config/settings.py:527-532`.
- **Evidência concreta:** a implementação anterior filtrava `titulo__istartswith` no banco antes do limite; a nova carrega somente os 500 títulos mais recentes e filtra em Python, então mais de 500 títulos recentes não relacionados podem esconder um título antigo que começa com o prefixo. Além disso, a ingestão não invalida as chaves `feed:autocomplete:v2:*`; um item novo, aprovado ou reprovado pode levar até 300 segundos para aparecer/desaparecer. O TTL e a degradação em caso de falha do cache são deliberados e funcionando, mas não tornam a troca do recorte sem perda.
- **Correção sugerida:** cachear um vocabulário completo/particionado por prefixo (ou invalidar/versionar na escrita) e testar título antigo + TTL; manter a limitagem apenas como orçamento explicitamente refletido no contrato.

### Finding 9 — nit — `métricas`: o sentinel `-` fora de request é aceito como `request_id` real

- **Arquivos/linhas:** `backend/feed/busca.py:402-409`; `backend/feed/tasks.py:41-71`.
- **Evidência concreta:** `get_current_request_id()` retorna `"-"` como default fora do middleware, mas `registrar_busca()` transforma esse valor em um ID não nulo; chamadas diretas/management podem, portanto, colidir no índice único e ser silenciosamente descartadas depois da primeira. A truncagem em 64 caracteres também permite colisões entre IDs externos com prefixo comum; o caminho HTTP atual passa um UUID real e não é afetado.
- **Correção sugerida:** tratar `"-"`/vazio como `None`, validar o formato/tamanho do ID ou usar um hash interno sem colisão; manter `NULL` para eventos sem request ID.

## Avaliação dos três pontos críticos

### 1. ETag/If-Modified-Since e perda de notícias

- **Janela de crash entre fetch e persistência:** aprovada no código. `RSSNewsSourceProvider` só chama `_capturar_validadores()` depois de parse e extração (`:366-370`); parse/requests failure não deixa validator novo; `executar_ingestao()` só chama `confirmar_validadores()` depois de `_persistir_grupo*` e `RegistroExecucaoIngestao.objects.create()` (`:818-831`). Um `304` também não faz parse e não substitui os validators existentes.
- **Caminho ainda perigoso:** um `304` falso do upstream, uma restauração/exclusão de linhas locais ou uma troca concorrente de URL não tem como ser detectado pelo cliente; por isso o risco de perder notícias permanece como Findings 2 e 3.

### 2. Integridade do `bulk_create`

- Não encontrei signal nem cálculo dependente de `save()`; `NewsItem.save()` delega apenas a `clean()`, e o helper chama explicitamente `clean()` para cada objeto antes do `bulk_create`, dentro de transações por grupo. Portanto não há regressão nova para a validação customizada de fonte obrigatória.
- A afirmação “validação completa” seria exagerada: `full_clean()` não é chamado (Finding 7), e a corrida de URLs (Finding 6) continua sendo uma falha de integridade ao nível do lote, não apenas performance.

### 3. Breaking change da paginação de comunidade

- A paginação e o `select_related("autor")` estão implementados e o backend limita as duas listagens, mas o modo de compatibilidade só preserva o **shape** (`array`), não a completude: os consumidores atuais nunca pedem `page`/`page_size` e renderizam a lista como array. O resultado é uma quebra silenciosa para mais de 20 itens (Finding 1), inclusive no contador e nas respostas de comentários.

## Verificações positivas e notas de escopo

### Migrations

- `catalogo_noticias/0012_fonterobo_http_validators.py:19-28` e `feed/0003_eventobusca_request_id.py:13-17` são `AddField` Django padrão, sem `RunSQL`, tipo/índice PostgreSQL específico ou outra SQL dependente de vendor; por isso não precisam de uma segunda guarda como a `0011` (que realmente usa `pg_trgm`/GIN).
- Defaults são seguros: validators começam como `""` (primeira requisição incondicional) e `request_id` começa `NULL`; múltiplos `NULL` são aceitos pelo índice único. O rollback remove apenas metadados de cache/idempotência, não `NewsItem` nem eventos de busca; rollback coordenado com o código é necessário.
- `makemigrations --check --dry-run` retornou `No changes detected`; `manage.py check` não apontou problemas. Não havia PostgreSQL disponível no sandbox, então a aplicação real no PostgreSQL continua uma verificação de CI, embora as operações sejam ORM padrão.

### ETag, 304 e fontes

- Fontes seed sem `FonteRobo` continuam funcionando: o provider recebe `fonte_robo=None` e apenas não persiste validators.
- Headers são extraídos de `CaseInsensitiveDict`/dicionários simples e 304 não chama `raise_for_status()` nem `feedparser.parse()`.
- A confirmação de validator é pós-persistência e falha de gravação é engolida com warning, deixando o valor antigo e permitindo uma próxima leitura completa; esse fallback é seguro para integridade.

### Bulk, snapshot e cache

- Não há signals registrados de `NewsItem`; os testes de lote confirmam PKs e uma única instrução INSERT para o caminho normal. `@transaction.atomic` continua envolvendo cada grupo.
- O snapshot de `ConfiguracaoRobo` é resetado em `finally`, inclusive em exceção, e a suíte confirma uma consulta por execução e leitura de configuração alterada na execução seguinte.
- O cache é versionado, TTL é configurável, não inclui payload por usuário e captura falhas de backend; a ausência de invalidação imediata é consistência eventual conhecida, não queda de leitura.

### `registrar_busca`/Celery

- `registrar_busca()` envolve `.delay()` em `try/except`, loga a falha e não cai para `EventoBusca.objects.create`; portanto broker fora não quebra a resposta da busca (a métrica é perdida, comportamento best-effort intencional).
- A task resolve `user_id` no worker, aceita apenas primitivos, limita query/ID e usa `get_or_create(request_id=...)` com constraint única; a mesma requisição reentregue não duplica quando o ID é válido. Eventos sem ID continuam deliberadamente não idempotentes.

### BRD §18 — direitos autorais

- Esta run não adiciona um novo caminho de reprodução de texto integral: `url_fonte_original`/`nome_fonte` continuam obrigatórios no `clean()`, as checagens anti-cópia e a atribuição/link no detalhe permanecem, e o lote não compartilha resumo entre itens. Não há, portanto, uma nova violação direta de direitos autorais introduzida pelo diff.
- A validação jurídica de termos/licenças das fontes RSS e a política de expiração/remoção continuam sendo pré-requisitos de produto; esta revisão de código não substitui a validação jurídica especial exigida pelo BRD. A lacuna de `full_clean` e as falhas de completude/validator devem ser corrigidas para não fragilizar rastreabilidade.

## Testes e verificações executados

```text
DJANGO_DEBUG=true DJANGO_DB_ENGINE=sqlite3 DJANGO_CACHE_BACKEND=locmem \
  .venv/bin/python -m pytest -q -p no:cacheprovider
# 453 passed, 196 warnings

DJANGO_DEBUG=true DJANGO_DB_ENGINE=sqlite3 DJANGO_CACHE_BACKEND=locmem \
  .venv/bin/python manage.py check
# System check identified no issues (0 silenced).

DJANGO_DEBUG=true DJANGO_DB_ENGINE=sqlite3 DJANGO_CACHE_BACKEND=locmem \
  .venv/bin/python manage.py makemigrations --check --dry-run
# No changes detected.

git diff --check -- <escopo da run>
# sem saída
```

## Resumo quantitativo

| Severidade | Quantidade |
|---|---:|
| blocker | 0 |
| major | 6 |
| minor | 2 |
| nit | 1 |

## Veredito

**changes_requested**

A ordem de confirmação pós-persistência do ETag, as migrations padrão, o `select_related`, o graceful degradation do broker e a idempotência básica por request ID estão bem implementados e a suíte está verde; porém a API pública ainda mostra apenas 20 itens para os clientes atuais sem sinalizar a truncagem, e a ingestão tem caminhos concretos de perda/completude, corrida de URL e custo LLM duplicado sob reentrega. Corrigir ou bloquear explicitamente os Findings 1–6 antes de considerar a run pronta para deploy; os Findings 7–9 são hardening/observabilidade recomendados.

Não foi feito commit nem alteração de código; este arquivo é o único artefato escrito pela revisão.

## Re-revisão iteração 1 — 2026-09-24

**Escopo e método:** verificação independente do working tree, isolada com `git diff -- backend/`; migrations e testes novos, por serem arquivos ainda não rastreados, também foram lidos diretamente. O frontend foi consultado apenas como contrato do consumidor. Não houve alteração de código nem commit.

### Status por finding

| Finding | Status na re-revisão | Evidência independente |
|---|---|---|
| **1 — major / paginação** | **Resolvido** | `comunidade/views.py:46-55` preserva a lista legada quando não há `page`/`page_size` e usa `PageNumberPagination` quando qualquer um é enviado. O smoke independente criou 25 publicações e respondeu `legacy_count=25`; com `page_size=10`, respondeu 10 resultados e `count=25`. `frontend/lib/api.ts:691-707,756-764` continua consumindo arrays e não envia paginação, portanto não há truncamento silencioso. |
| **2 — major / revalidação completa** | **Resolvido** | `FonteRobo.ultima_revalidacao_completa` e a migration `0013` existem; `news_source.py:254-275` omite ambos os headers quando o marcador é `NULL`/vencido, com TTL padrão de 6 h em `settings.py:536-541`. `news_source.py:342-372` invalida ETag, Last-Modified e marcador em erro, e `services/ingestao.py:762-782` executa essa invalidação para toda fonte que falhou. Os testes de TTL, 304 falso, erro e confirmação pós-persistência passaram. |
| **3 — major / corrida do validator** | **Resolvido** | `news_source.py:289-340` confirma por `filter(pk=..., url=...).update(...)`, sem `save()` da instância antiga; `models.py:227-253` centraliza a invalidação quando a URL muda e amplia `update_fields` quando necessário. Serializer, comando e admin também preservam a invalidação; o teste de URL alterada entre fetch e confirmação passou. |
| **4 — major / escopo Celery** | **Resolvido** | Não há atribuição das settings globais `CELERY_TASK_ACKS_LATE` e `CELERY_TASK_REJECT_ON_WORKER_LOST` no backend. `catalogo_noticias.tasks.ingerir_noticias` e `feed.tasks.registrar_evento_busca` declaram `True/True`; as três newsletters, B2B e assinatura declaram `False/False`. A introspecção no teste de processo confirmou os valores. |
| **5 — major / custo LLM na reentrega** | **Resolvido com residual documentado** | `services/ingestao.py:873-940` cria o `RegistroExecucaoIngestao` e salva a reserva em `custo_estimado_summarization_usd` antes de `resumir_e_classificar_em_lote`; o teste observa o valor no banco de dentro do provider e prova que ele sobrevive a uma exceção posterior à resposta. A ausência de staging/resultado durável, a possibilidade de nova chamada e a reserva aproximada/zero para providers sem estimador estão registradas em `implementation-history.md:205-223`. |
| **6 — major / `IntegrityError` por URL** | **Resolvido** | `services/ingestao.py:79-96,794-803` elimina duplicatas no feed e entre fontes antes do agrupamento; o helper em `:382-463` mantém o insert normal e, em `IntegrityError`, requery + retry com `ignore_conflicts=True`. Os testes de duplicata no mesmo lote, reentrega e conflito direto contra a unique passaram sem exceção ou duplicidade. |
| **7 — minor / `full_clean`** | **Aceito com justificativa** | O caminho de lote chama `NewsItem.clean()` e o banco mantém a check constraint da fonte e a unique da URL, preservando as validações críticas de rastreabilidade que o `save()` legado validava. O benchmark e as 52 regressões concretas por URLs históricas tornam plausível preservar o contrato legado; formato, choices e limites não validados permanecem documentados como residual. |
| **8 — minor / autocomplete** | **Parcialmente resolvido** | A ingestão chama `invalidar_cache_autocomplete()` e o teste comprova a remoção das três chaves. Porém a invalidação ocorre dentro da transação e não nos dois actions do admin que mudam `NewsItem` para aprovado/rejeitado; o snapshot continua limitado aos 500 títulos recentes, que ainda pode esconder um título antigo que casava com o prefixo. O TTL continua sendo a garantia eventual para esses caminhos. |
| **9 — nit / `request_id`** | **Resolvido no caminho sem request; residual nos IDs externos** | `registrar_busca()` trata `"-"`/vazio e gera `uuid.uuid4()` antes do dispatch; a task também normaliza o sentinel para `NULL`, e o teste validou UUIDs distintos. Continua havendo truncagem em 64 caracteres para `X-Request-ID` arbitrário, de modo que dois IDs externos com o mesmo prefixo de 64 caracteres ainda podem colidir. |

### Confirmação dos majors

**6 de 6 majors (1–6) confirmados como resolvidos.** Não identifiquei regressão de código nos mecanismos de paginação legada, revalidação HTTP, confirmação condicional, opt-in/opt-out de Celery, reserva de custo ou contenção de duplicatas.

### Testes e verificações da re-revisão

```text
DJANGO_DEBUG=true DJANGO_DB_ENGINE=sqlite3 DJANGO_CACHE_BACKEND=locmem \
  .venv/bin/python -m pytest -q -p no:cacheprovider \
  comunidade/tests/test_p2_performance.py \
  feed/tests/test_p2_performance.py \
  catalogo_noticias/tests/test_p2_ingestao_performance.py
# 27 passed, 17 warnings

DJANGO_DEBUG=true DJANGO_DB_ENGINE=sqlite3 DJANGO_CACHE_BACKEND=locmem \
  .venv/bin/python -m pytest -q -p no:cacheprovider
# 462 passed, 202 warnings

DJANGO_DEBUG=true DJANGO_DB_ENGINE=sqlite3 DJANGO_CACHE_BACKEND=locmem \
  .venv/bin/python manage.py check
# System check identified no issues (0 silenced).

DJANGO_DEBUG=true DJANGO_DB_ENGINE=sqlite3 DJANGO_CACHE_BACKEND=locmem \
  .venv/bin/python manage.py makemigrations --check --dry-run
# No changes detected.

git diff --check -- backend/
# sem saída
```

O smoke específico de comunidade respondeu `legacy_type=ReturnList legacy_count=25 page_size_results=10 envelope_count=25`.

### Veredito da re-revisão

**approve_with_comments**

Os seis majors que motivaram `changes_requested` foram corrigidos e verificados independentemente; a minor 7 foi adequadamente aceita com residual explícito. Permanecem apenas a cobertura parcial da Finding 8 (invalidação fora da ingestão e limite de 500 títulos) e o residual de colisão do Finding 9 para IDs externos longos; são melhorias de consistência eventual/observabilidade, não bloqueiam esta iteração nem reabrem os seis majors. Nenhum commit foi feito e nenhum código foi alterado.
