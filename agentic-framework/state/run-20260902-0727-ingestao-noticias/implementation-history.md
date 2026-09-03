<!--
CONTRACT: implementation-history
DONO: executor (cria e adiciona entradas) / tester, remediator, historian (adicionam entradas)
QUANDO É CRIADO: junto com a primeira ação do executor sobre o implementation-contract.md.
PARA ONDE VAI A INSTÂNCIA: agentic-framework/state/run-<run_id>/implementation-history.md
NATUREZA: append-only durante a execução — cada entrada é uma iteração, nunca se edita uma entrada anterior.
-->

# Implementation History — 20260902-0727-ingestao-noticias

## Iteração 1 — 2026-09-02 — executor (implementação inicial)

**O que foi feito:**

Criado o app Django `catalogo_noticias/` dentro do projeto Django já existente (`backend/`, `config/`), reaproveitando o mesmo projeto do run `20260901-2135-cadastro-auth` (módulo `identidade/`), conforme `implementation-contract.md`: modelos `NewsItem`/`NewsCluster`/`RegistroExecucaoIngestao`, `NewsSourceProvider` (interface + implementação RSS via `feedparser`), `SummarizationProvider` (interface + implementação concreta via cliente HTTP genérico), pipeline de ingestão (`services/ingestao.py`), deduplicação/agrupamento (`services/deduplicacao.py`), task Celery periódica (`tasks.py`), configuração de Celery/Redis (`config/celery.py`, `config/__init__.py`, `config/settings.py`) e exposição no Django admin com filtro pela fila de revisão humana. Nenhum frontend/UI de consumo foi tocado (fora de escopo, conforme `task-plan.md`).

### Estrutura de pastas criada

```
backend/
  config/
    celery.py                    # novo — instância do app Celery (ARCHITECTURE.md §1)
    __init__.py                  # modificado — importa celery_app (padrão oficial do Celery p/ Django)
    settings.py                  # modificado — CELERY_*, CATALOGO_NOTICIAS_* (fontes-semente,
                                  #   categorias sensíveis, limiar de fontes, config do SummarizationProvider)
  catalogo_noticias/              # novo app Django
    apps.py
    models.py                    # NewsCluster, NewsItem, RegistroExecucaoIngestao
    providers/
      news_source.py             # NewsSourceProvider (ABC) + ItemBruto + RSSNewsSourceProvider + FonteIndisponivelError
      summarization.py           # SummarizationProvider (ABC) + ResultadoResumo + LLMHttpSummarizationProvider + SummarizationProviderError
    services/
      deduplicacao.py            # agrupar_itens_brutos() — heurística de similaridade de título
      ingestao.py                # executar_ingestao() — orquestração ponta a ponta
    tasks.py                     # task Celery periódica `ingerir_noticias`
    admin.py                     # NewsClusterAdmin, NewsItemAdmin (filtro status_revisao), RegistroExecucaoIngestaoAdmin
    migrations/0001_initial.py
    tests/test_sanity.py         # 12 testes mínimos de sanidade do executor (não é a suíte formal)
  requirements.txt               # modificado — feedparser, requests (explícito), celery, redis
  requirements-lock.txt          # regenerado (pip freeze) — inclui as novas diretas + transitivas
  .env.example                   # modificado — variáveis novas de Celery/Redis e catalogo_noticias/
```

### Dependências instaladas (venv `backend/.venv`, já existente do run anterior)

| Pacote | Versão | Motivo |
|---|---|---|
| `feedparser` | 6.0.11 | Parser de RSS/Atom — permitido explicitamente pelo contrato ("um parser de RSS, ex.: feedparser"). |
| `requests` | 2.34.2 | Já estava presente no venv como transitiva de `django-allauth[socialaccount]` (run anterior); passou a ser dependência DIRETA aqui (usada pelo `RSSNewsSourceProvider` para controlar timeout/headers antes de repassar os bytes ao `feedparser`, e pelo `LLMHttpSummarizationProvider` para chamar a API do provedor de LLM) — permitido pelo contrato ("um cliente HTTP para chamadas ao provedor de LLM"). Declarada agora explicitamente em `requirements.txt` em vez de ficar implícita/transitiva. |
| `celery` | 5.6.0 | Permitida pelo contrato e por ARCHITECTURE.md §1 (jobs assíncronos). |
| `redis` | 6.4.0 | Cliente Python do Redis, permitido pelo contrato ("client Python" do Redis) — broker/result backend do Celery. |

Todas registradas em `backend/requirements.txt`, com o lock file (`requirements-lock.txt`) regenerado via `pip freeze` para refletir as transitivas novas (`amqp`, `billiard`, `click*`, `kombu`, `prompt_toolkit`, `sgmllib3k`, `six`, `tzlocal`, `vine`, `wcwidth`, `exceptiongroup`, `python-dateutil`).

**Nenhuma dependência fora da lista permitida pelo contrato foi adicionada.**

### Validação das fontes RSS-semente

Testadas ao vivo em 2026-09-02 (`curl`, com `-L` para seguir redirects):

| Fonte | URL (task-plan.md) | Resultado |
|---|---|---|
| G1 | `https://g1.globo.com/rss/g1/` | HTTP 200 — OK, sem alteração |
| UOL | `https://rss.uol.com.br/feed/noticias.xml` | HTTP 200 — OK, sem alteração |
| CNN Brasil | `https://www.cnnbrasil.com.br/feed/` | HTTP 302 → `https://admin.cnnbrasil.com.br/feed/` (HTTP 200 final) — **nenhuma substituição de URL necessária**: o `requests.get()` usado por `RSSNewsSourceProvider` segue redirects automaticamente por padrão, então a URL original do `task-plan.md` continua funcionando sem qualquer ajuste de configuração. |
| Folha "Em Cima da Hora" | `https://feeds.folha.uol.com.br/emcimadahora/rss091.xml` | HTTP 200 — OK, sem alteração |

**Nenhuma fonte precisou ser substituída.** As 4 URLs do `task-plan.md` foram mantidas exatamente como estavam em `settings.CATALOGO_NOTICIAS_FONTES_RSS`.

### Decisões técnicas (dentro da liberdade deixada pelo contrato)

1. **Provedor concreto do `SummarizationProvider`: `LLMHttpSummarizationProvider`, um cliente HTTP genérico no formato "Chat Completions"** (o formato popularizado pela API da OpenAI, também aceito por Azure OpenAI, Groq, OpenRouter, e por servidores locais compatíveis como Ollama/vLLM em modo "OpenAI-compatible"). Motivo da escolha: (a) não há credenciais reais de nenhum provedor de LLM neste ambiente — a escolha de provedor de produção é uma decisão em aberto explícita em `ARCHITECTURE.md` §8, item 3; (b) o formato "Chat Completions" é hoje o denominador comum mais amplamente suportado entre provedores concorrentes, então implementar contra esse formato (em vez de contra um SDK proprietário específico) maximiza a chance de o provedor real escolhido no futuro já ser compatível "de graça" (só trocar `CATALOGO_NOTICIAS_LLM_API_BASE_URL`/`CATALOGO_NOTICIAS_LLM_MODEL`/`CATALOGO_NOTICIAS_LLM_API_KEY`), sem reescrever `LLMHttpSummarizationProvider`; (c) evita adicionar um SDK Python dedicado (ex.: `openai`) como dependência nova não claramente pré-aprovada pelo contrato, quando um cliente HTTP genérico (`requests`, já aprovado) é suficiente. A chamada de rede real está isolada em `LLMHttpSummarizationProvider._chamar_api()`, o único ponto mockado nos testes — nenhum teste (nem os de sanidade do executor, nem presumivelmente os do `tester`) faz chamada de rede real; todos usam a interface `SummarizationProvider` com um dublê (`FakeSummarizationProvider`) injetado via `executar_ingestao(summarization_provider=...)`. **Esta é uma decisão técnica default, sujeita a troca** quando o provedor real de LLM for escolhido (ARCHITECTURE.md §8) — sinalizado aqui explicitamente para o `reviewer`.

2. **`SummarizationProvider.resumir_e_classificar()` recebe uma LISTA de `ItemBruto`, não um item único**, conforme a assinatura literal do contrato (`resumir_e_classificar(itens_brutos) -> ResultadoResumo`). Interpretação adotada: quando o pipeline de deduplicação identifica que N itens de fontes diferentes cobrem o MESMO acontecimento, a chamada ao `SummarizationProvider` é feita UMA VEZ por grupo/cluster (não uma vez por item), passando todos os itens do grupo — o provedor de LLM produz um resumo ÚNICO e sintetizado a partir de todas as fontes daquele acontecimento, que é então aplicado a cada `NewsItem` do grupo (todos os itens do mesmo cluster compartilham o mesmo `resumo_proprio`, mas cada um mantém sua própria `url_fonte_original`/`nome_fonte` individuais). Isso também é o que torna a observabilidade de custo (critério de aceite 6) mais precisa: `chamadas_summarization_provider` conta 1 por grupo, não 1 por item — refletindo o uso real de tokens/custo (BRD §30), já que uma chamada por grupo é estritamente mais barata do que uma chamada por item quando há cobertura duplicada.

3. **Registro consultável do critério de aceite 6: modelo `RegistroExecucaoIngestao`** (não apenas log estruturado). Motivo: um modelo persistido no banco é consultável tanto via Django admin (interface já exigida pelo contrato para a fila de revisão) quanto programaticamente/via testes, sem depender de parsear logs — mais alinhado ao NFR de "observabilidade de custo de IA" (ARCHITECTURE.md §7) precisar ser auditável ao longo do tempo, não só no momento da execução. Campos: `itens_por_fonte` (JSON), `erros_por_fonte` (JSON), `total_itens_ingeridos`, `total_grupos_formados`, `total_duplicatas_agrupadas` (= itens - grupos), `chamadas_summarization_provider`, `tokens_utilizados_summarization`, `custo_estimado_summarization_usd`. Também é logado via `logging` (nível INFO no sucesso do pipeline, ERROR por fonte que falhar) — as duas formas coexistem, o modelo é a fonte de verdade consultável, o log é para operação em tempo real.

4. **Configuração das categorias sensíveis e do limiar de fontes: via `settings.py` + variável de ambiente** (`CATALOGO_NOTICIAS_CATEGORIAS_SENSIVEIS`, `CATALOGO_NOTICIAS_LIMIAR_FONTES_ALTA_RELEVANCIA`), não via um modelo editável no admin (ex.: um `ConfiguracaoRelevancia` singleton). O contrato explicitamente permite essa escolha ("via admin ou settings, a critério do executor"). Motivo: é o mesmo padrão já estabelecido no próprio `config/settings.py` deste projeto para outros parâmetros de negócio configuráveis sem alteração de código (`TERMOS_VERSAO_ATUAL`, `EMAIL_VERIFICATION_TOKEN_MAX_AGE_SECONDS`, etc. — todos `os.environ.get(...)` com default) — muda via variável de ambiente/redeploy de config, não via código, satisfazendo literalmente o critério de aceite 7 ("configuráveis sem alteração de código"). Uma alternativa via admin/DB (mais próxima do padrão `FeatureLimit` mencionado no contrato) permitiria mudar em runtime sem redeploy — é um upgrade razoável para uma execução futura, mas o contrato deixou a escolha explicitamente aberta e não exigiu esse nível de dinamismo (não é o mesmo `FeatureLimit`, só "equivalente ao padrão"), então optei pela abordagem mais simples e já consistente com o restante da base de código. **Sinalizo para o `reviewer`/`orchestrator`**: se o operador de negócio precisar mudar esses parâmetros sem depender de um deploy, isso é um ajuste pontual (migrar de `settings` para um modelo `ConfiguracaoRelevancia` admin-editável), não uma mudança arquitetural grande.

5. **As 4 fontes-semente ficam em `settings.CATALOGO_NOTICIAS_FONTES_RSS`** (lista de dicts `{"nome": ..., "url": ...}`, hardcoded no próprio `settings.py`, não via variável de ambiente individual) — porque é uma lista estruturada (não um escalar simples), e o contrato pede explicitamente "config/settings.py — ... e das 4 fontes-semente (via configuração, não hardcoded no meio da lógica de negócio)": a lista está em `settings.py` (configuração), não dentro de `services/ingestao.py` (lógica de negócio) — `construir_fontes_configuradas()` apenas lê `settings.CATALOGO_NOTICIAS_FONTES_RSS` e instancia providers, nunca contém a URL/nome de nenhuma fonte hardcoded no próprio código de orquestração. Isso satisfaz a letra do contrato; ainda assim, adicionar uma 5ª fonte no futuro exigirá editar `settings.py` (não é "sem tocar em nenhum arquivo de código", mas settings.py não é "lógica de negócio").

6. **Idempotência da ingestão periódica**: antes de processar um item bruto vindo de uma fonte, `services/ingestao.py` verifica se já existe um `NewsItem` com aquela `url_fonte_original` (`_item_bruto_ja_ingerido`) e descarta silenciosamente os já ingeridos. Não estava explicitamente pedido no contrato, mas é necessário para a task Celery periódica (critério "job periódico") funcionar de forma sã: sem isso, cada execução da task tentaria recriar os mesmos itens de um feed que não mudou desde a última execução, o que violaria a constraint de unicidade de `url_fonte_original` a cada novo ciclo. Contabilizado como parte de `itens_por_fonte` (só conta itens NOVOS por execução).

7. **Falha do `SummarizationProvider` para um grupo não derruba a ingestão inteira, mas força revisão humana** (`_resultado_fallback_erro`): se a chamada ao provedor de LLM falhar (`SummarizationProviderError`), o grupo recebe um resultado de fallback com `resumo=""`, o que em `_persistir_grupo` força `status_revisao=pendente` incondicionalmente (independente de categoria/número de fontes) — nunca cai no caso "publicado automaticamente" sem um resumo real. Não estava pedido explicitamente no contrato (que só fala do caso de fonte de RSS indisponível, critério 1), mas é uma extensão natural do mesmo princípio de resiliência (uma falha não pode nem derrubar a execução inteira, nem resultar em publicação sem direitos autorais respeitados). Coberto pelo teste `test_summarization_provider_falhando_forca_revisao_humana_em_vez_de_publicar`.

8. **Heurística de deduplicação: similaridade de conjunto de palavras (Jaccard) combinada com `SequenceMatcher` sobre tokens ordenados alfabeticamente**, não semântica real (embeddings). Testada manualmente contra pares de manchetes com reordenação de palavras (comum entre veículos diferentes cobrindo o mesmo fato) — uma primeira versão baseada só em `SequenceMatcher` sobre o texto normalizado (sem reordenar tokens) falhou em detectar como duplicatas manchetes do mesmo fato com ordem de palavras diferente entre fontes (ex.: "Grande incêndio atinge depósito..." vs. "Depósito é atingido por grande incêndio..." tinha similaridade ~0.31-0.39, abaixo do limiar). A versão final (Jaccard de tokens + SequenceMatcher sobre tokens ordenados) sobe essa mesma similaridade para ~0.78-0.85, mantendo baixa (~0.19-0.36) a similaridade entre manchetes de fatos genuinamente diferentes. **Documentado explicitamente como heurística de MVP, não dedup semântica real** — um upgrade natural para execução futura seria usar embeddings via o próprio `SummarizationProvider` (o LLM já teria essa capacidade). O limiar (`CATALOGO_NOTICIAS_DEDUP_LIMIAR_SIMILARIDADE`, default 0.55) é configurável via env var.

9. **Validação de `url_fonte_original`/`nome_fonte` obrigatórios em DUAS camadas**: (a) `NewsItem.save()` chama `self.clean()`, que levanta `ValidationError` se qualquer um dos dois campos estiver vazio, ANTES de tocar o banco — cobre criação via código Python (`objects.create()`, services, etc.); (b) uma `CheckConstraint` de banco (`newsitem_fonte_obrigatoria`) reforça a mesma regra a nível de banco (defesa em profundidade — protege até contra um `bulk_create()` ou SQL direto que pulasse `save()`). Funciona tanto em PostgreSQL (engine padrão) quanto em SQLite (usado neste ambiente sem Postgres disponível) — confirmado nos testes `test_newsitem_sem_url_fonte_original_nao_e_criado`/`test_newsitem_sem_nome_fonte_nao_e_criado`.

10. **Celery configurado seguindo o padrão oficial de integração Django+Celery** (`config/celery.py` com `app.config_from_object("django.conf:settings", namespace="CELERY")` + `config/__init__.py` importando `celery_app`) — não havia nenhuma configuração de Celery no run anterior (`identidade/` não precisava). `CELERY_BROKER_URL`/`CELERY_RESULT_BACKEND` apontam para Redis local por padrão (`redis://localhost:6379/0` e `/1`), configuráveis via env var. **Não há um servidor Redis disponível neste ambiente de execução** (mesma limitação já documentada no run anterior para PostgreSQL) — a task foi validada estruturalmente (registro no app Celery, `beat_schedule` correto, importável sem erro — ver "Comandos executados" abaixo) e funcionalmente via chamada DIRETA da função Python (`executar_ingestao()`, sem passar pelo broker), não via um worker Celery real consumindo da fila. Recomendo ao `tester`/ambiente de CI/staging validar com um Redis real antes de considerar a integração com Celery completamente e ponta-a-ponta validada.

### Comandos executados / evidência

```
# validação das fontes RSS ao vivo
curl -sS -o /dev/null -w "HTTP %{http_code}\n" --max-time 10 "https://g1.globo.com/rss/g1/"                          # HTTP 200
curl -sS -o /dev/null -w "HTTP %{http_code}\n" --max-time 10 "https://rss.uol.com.br/feed/noticias.xml"              # HTTP 200
curl -sS -o /dev/null -w "HTTP %{http_code}\n" --max-time 10 "https://www.cnnbrasil.com.br/feed/"                    # HTTP 302
curl -sS -L -o /dev/null -w "Final HTTP %{http_code}, URL: %{url_effective}\n" --max-time 15 "https://www.cnnbrasil.com.br/feed/"
  # -> Final HTTP 200, URL: https://admin.cnnbrasil.com.br/feed/  (redirect seguido automaticamente pelo requests.get())
curl -sS -o /dev/null -w "HTTP %{http_code}\n" --max-time 10 "https://feeds.folha.uol.com.br/emcimadahora/rss091.xml" # HTTP 200

# instalação de dependências novas
pip install feedparser==6.0.11 requests==2.34.2 celery==5.6.0 redis==6.4.0
# -> instaladas com sucesso, sem conflito com o venv existente

# scaffold do app
mkdir catalogo_noticias/{providers,services,migrations,tests}

# checagem do sistema (com override sqlite p/ ambiente sem Postgres, mesmo padrão do run anterior)
DJANGO_DB_ENGINE=sqlite3 DJANGO_SECRET_KEY=<chave-de-teste> python manage.py check
# -> "System check identified no issues (0 silenced)."

# migrations
DJANGO_DB_ENGINE=sqlite3 DJANGO_SECRET_KEY=<chave-de-teste> python manage.py makemigrations catalogo_noticias
# -> "Migrations for 'catalogo_noticias': + Create model NewsCluster, RegistroExecucaoIngestao, NewsItem"
DJANGO_DB_ENGINE=sqlite3 DJANGO_SECRET_KEY=<chave-de-teste> python manage.py migrate
# -> todas as migrations (incluindo catalogo_noticias.0001_initial) aplicadas com sucesso ("OK" em todas)

# validação estrutural do Celery (sem broker real disponível neste ambiente)
python -c "
import django, os
os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings')
django.setup()
from config.celery import app
from catalogo_noticias.tasks import ingerir_noticias
print('celery app ok:', app)
print('task registered:', ingerir_noticias.name)
print('beat schedule:', app.conf.beat_schedule)
"
# -> celery app ok: <Celery brd_portal_noticias ...>
#    task registered: catalogo_noticias.tasks.ingerir_noticias
#    beat schedule: {'catalogo-noticias-ingerir-noticias': {'task': 'catalogo_noticias.tasks.ingerir_noticias', 'schedule': 900}}

# testes de sanidade do executor (não é a suíte formal do tester)
DJANGO_DB_ENGINE=sqlite3 python -m pytest catalogo_noticias/tests/ -v
# -> 12 passed

# suíte completa do projeto (identidade/ + catalogo_noticias/), confirmando ausência de regressão
DJANGO_DB_ENGINE=sqlite3 python -m pytest -q
# -> 56 passed (44 de identidade/, já existentes, + 12 novos de catalogo_noticias/)
```

Saída final da suíte de sanidade do novo app:
```
catalogo_noticias/tests/test_sanity.py::test_fonte_indisponivel_nao_impede_ingestao_das_demais PASSED
catalogo_noticias/tests/test_sanity.py::test_itens_de_fontes_diferentes_sobre_mesmo_acontecimento_viram_um_cluster PASSED
catalogo_noticias/tests/test_sanity.py::test_agrupar_itens_brutos_isoladamente_sem_banco PASSED
catalogo_noticias/tests/test_sanity.py::test_newsitem_sem_url_fonte_original_nao_e_criado PASSED
catalogo_noticias/tests/test_sanity.py::test_newsitem_sem_nome_fonte_nao_e_criado PASSED
catalogo_noticias/tests/test_sanity.py::test_resumo_proprio_nunca_e_identico_ou_quase_identico_ao_conteudo_bruto PASSED
catalogo_noticias/tests/test_sanity.py::test_categoria_sensivel_aciona_fila_de_revisao_humana PASSED
catalogo_noticias/tests/test_sanity.py::test_categoria_nao_sensivel_e_publicado_automaticamente PASSED
catalogo_noticias/tests/test_sanity.py::test_cluster_com_3_ou_mais_fontes_aciona_revisao_mesmo_com_categoria_nao_sensivel PASSED
catalogo_noticias/tests/test_sanity.py::test_registro_execucao_ingestao_registra_metricas_observaveis PASSED
catalogo_noticias/tests/test_sanity.py::test_limiar_de_fontes_e_configuravel_via_settings PASSED
catalogo_noticias/tests/test_sanity.py::test_summarization_provider_falhando_forca_revisao_humana_em_vez_de_publicar PASSED
12 passed in ~1s
```

### Convenções de estilo seguidas (herdadas de `implementation-history.md` do run `20260901-2135-cadastro-auth`)

- Um app Django por bounded context de `ARCHITECTURE.md` §2 (`catalogo_noticias/`, novo).
- Nomes de campo de domínio em português (`titulo`, `resumo_proprio`, `url_fonte_original`, `nome_fonte`, `categoria`, `status_revisao`, `urgente`, etc.), classes/módulos em inglês técnico/português misto conforme já convencionado.
- `services/` separado de `providers/` (orquestração vs. integrações externas plugáveis) — extensão natural do padrão "serializers/services separados por caso de uso" já usado em `identidade/`.
- Docstrings de classes/funções centrais referenciam o número do critério de aceite do `implementation-contract.md` que implementam, para rastreabilidade (mesmo padrão de `identidade/`).
- Configuração de negócio via `settings.py` + `os.environ.get(...)` com default, nunca hardcoded em `services/`.

**Resultado:** sucesso — todas as áreas/arquivos esperados pelo contrato foram criados, o projeto sobe (`manage.py check` limpo, com e sem override de DEBUG), migrations aplicam sem erro em SQLite (mesma limitação de ambiente sem PostgreSQL/Redis reais já documentada no run anterior), e os 12 testes de sanidade escritos para validar o próprio código passam, junto com os 44 testes pré-existentes de `identidade/` (nenhuma regressão).

### Status dos critérios de aceite técnicos (implementation-contract.md)

| # | Critério | Status | Evidência |
|---|---|---|---|
| 1 | Falha de uma fonte (mockada) não impede o processamento das demais; erro registrado, não propagado como exceção fatal | ✅ Implementado | `services/ingestao.py::executar_ingestao` captura `FonteIndisponivelError` (e qualquer `Exception` inesperada) por fonte, dentro do loop, sem interromper as demais; `test_fonte_indisponivel_nao_impede_ingestao_das_demais` |
| 2 | Itens de fontes diferentes sobre o mesmo acontecimento (mockados com títulos semanticamente equivalentes) são associados ao mesmo `NewsCluster` | ✅ Implementado | `services/deduplicacao.py::agrupar_itens_brutos` + `_persistir_grupo`; `test_itens_de_fontes_diferentes_sobre_mesmo_acontecimento_viram_um_cluster`, `test_agrupar_itens_brutos_isoladamente_sem_banco` |
| 3 | `url_fonte_original`/`nome_fonte` obrigatórios — ausência impede criação (validação, não best-effort) | ✅ Implementado | `NewsItem.save()`/`clean()` + `CheckConstraint` de banco; `test_newsitem_sem_url_fonte_original_nao_e_criado`, `test_newsitem_sem_nome_fonte_nao_e_criado` |
| 4 | `resumo_proprio` preenchido pelo `SummarizationProvider` (mockado), nunca cópia do texto bruto (comparação de não-identidade/near-identidade) | ✅ Implementado | `_persistir_grupo` grava `resultado.resumo` (nunca `item_bruto.conteudo_bruto`) em `resumo_proprio`; `test_resumo_proprio_nunca_e_identico_ou_quase_identico_ao_conteudo_bruto` (compara com `SequenceMatcher`, exige similaridade < 0.5) |
| 5 | Alta relevância (categoria sensível OU 3+ fontes, parametrizável) → `status_revisao=pendente`, não publicado automaticamente; senão → `status_revisao=nao_aplicavel`, publicável | ✅ Implementado | `_eh_alta_relevancia` + `_persistir_grupo`; `test_categoria_sensivel_aciona_fila_de_revisao_humana`, `test_categoria_nao_sensivel_e_publicado_automaticamente`, `test_cluster_com_3_ou_mais_fontes_aciona_revisao_mesmo_com_categoria_nao_sensivel` |
| 6 | Registro consultável por execução: itens por fonte, duplicatas agrupadas, chamadas/custo do `SummarizationProvider` | ✅ Implementado | Modelo `RegistroExecucaoIngestao` (persistido + exposto no admin, somente leitura) + log estruturado; `test_registro_execucao_ingestao_registra_metricas_observaveis` |
| 7 | Categorias sensíveis e limiar de fontes configuráveis sem alteração de código | ✅ Implementado | `settings.CATALOGO_NOTICIAS_CATEGORIAS_SENSIVEIS`/`CATALOGO_NOTICIAS_LIMIAR_FONTES_ALTA_RELEVANCIA` via env var (ver decisão técnica 4 acima); `test_limiar_de_fontes_e_configuravel_via_settings` (usa `override_settings`, prova comportamento muda sem tocar código) |

**Resumo:** 7 de 7 critérios de aceite técnicos implementados e cobertos por teste de sanidade do executor. Nenhum critério ficou parcial ou pendente.

**Notas fora do escopo (não implementadas aqui, só sinalizadas):**

1. **Sem servidor Redis nem PostgreSQL reais neste ambiente de execução** — mesma limitação já documentada no run anterior para PostgreSQL (validado estruturalmente: `ENGINE=postgresql` é o default, mas os testes/migrations desta iteração rodaram contra SQLite via `DJANGO_DB_ENGINE=sqlite3`). Para Celery/Redis: a task `ingerir_noticias` e o `beat_schedule` foram validados estruturalmente (importação sem erro, registro correto no app Celery), mas não foi possível rodar um worker Celery real consumindo de uma fila Redis real neste ambiente. Recomendo ao `tester`/ambiente de staging validar com Redis real antes do deploy.
2. **Credenciais reais de um provedor de LLM** não existem neste ambiente — já era um risco conhecido e aceito em `task-plan.md`. O `LLMHttpSummarizationProvider` foi validado apenas estruturalmente (a chamada de rede real em `_chamar_api()` não foi exercitada); todos os testes usam um `SummarizationProvider` mockado (`FakeSummarizationProvider` em `tests/test_sanity.py`), conforme esperado pelo contrato.
3. **Modelo admin-editável para categorias sensíveis/limiar de fontes** (equivalente mais próximo do padrão `FeatureLimit`) não foi implementado — optei por `settings`/env var (ver decisão técnica 4). Se o `orchestrator`/usuário preferir edição em runtime via admin sem redeploy, é um ajuste pontual de escopo (migrar para um modelo `ConfiguracaoRelevancia`), não implementado nesta execução por não ter sido exigido explicitamente pelo contrato.
4. **Validação jurídica dos termos de uso das fontes RSS** — explicitamente fora do escopo desta execução (não-objetivo do contrato, já registrado como follow-up obrigatório em `task-plan.md`/`run-state.json`), não implementada aqui, como esperado.

**Arquivos tocados:**
- `backend/catalogo_noticias/__init__.py`, `apps.py`, `models.py`, `admin.py`, `tasks.py` (novos)
- `backend/catalogo_noticias/providers/__init__.py`, `news_source.py`, `summarization.py` (novos)
- `backend/catalogo_noticias/services/__init__.py`, `deduplicacao.py`, `ingestao.py` (novos)
- `backend/catalogo_noticias/migrations/__init__.py`, `0001_initial.py` (novos)
- `backend/catalogo_noticias/tests/__init__.py`, `test_sanity.py` (novos — testes mínimos do executor)
- `backend/config/celery.py` (novo)
- `backend/config/__init__.py` (modificado — importa `celery_app`)
- `backend/config/settings.py` (modificado — `INSTALLED_APPS += "catalogo_noticias"`, `CELERY_*`, `CATALOGO_NOTICIAS_*`)
- `backend/requirements.txt` (modificado — `feedparser`, `requests` explícito, `celery`, `redis`)
- `backend/requirements-lock.txt` (regenerado via `pip freeze`)
- `backend/.env.example` (modificado — variáveis novas documentadas)

---

## Iteração 2 — 2026-09-02 — tester (verificação formal dos critérios de aceite)

**Objetivo:** dar um veredito verificável sobre os 7 critérios de aceite técnicos de `implementation-contract.md`, com suíte de testes própria e independente da suíte de sanidade do executor (`catalogo_noticias/tests/test_sanity.py`), rodada de fato (não só lida) contra o código real.

**Ambiente:** sem PostgreSQL nem Redis reais neste ambiente de execução — mesma limitação já documentada na Iteração 1. Toda a suíte rodou contra SQLite via `DJANGO_DB_ENGINE=sqlite3` (`pytest.ini` usa `config.settings_test`). Confirmado independentemente (não apenas aceito da palavra do executor):
```
DJANGO_DB_ENGINE=sqlite3 DJANGO_SECRET_KEY=<chave-de-teste> python manage.py check
# -> "System check identified no issues (0 silenced)."
```

### Suíte formal criada

`backend/catalogo_noticias/tests/test_acceptance_criteria.py` — 28 testes, organizados em 7 classes (`TestAC1ResilienciaDeFontes` ... `TestAC7ConfiguravelSemAlterarCodigo`), uma por critério de aceite numerado. Não reaproveita os dublês (`FakeNewsSourceProvider`/`FakeSummarizationProvider`) do executor — usa dublês próprios (`FonteDeTeste`, `ProviderResumoGenuino`) e, no AC-1, exercita `RSSNewsSourceProvider` de verdade (mockando só `requests.get`), não apenas uma interface de alto nível que já pré-fabrica a exceção.

**Comando e resultado (suíte nova isolada):**
```
DJANGO_DB_ENGINE=sqlite3 python -m pytest catalogo_noticias/tests/test_acceptance_criteria.py -v
# -> 27 passed, 1 xfailed (strict) in 2.22s
```

**Comando e resultado (suíte completa do projeto — identidade/ + catalogo_noticias/, sanidade + formal):**
```
DJANGO_DB_ENGINE=sqlite3 python -m pytest -q
# -> 83 passed, 1 xfailed, 7 warnings in 48.57s
```
(56 pré-existentes da Iteração 1 sem regressão + 28 novos desta suíte formal = 84 testes coletados; os 7 warnings são um `DeprecationWarning` interno de `feedparser` sobre uso de argumento posicional em `re.sub`, não relacionado ao código do app, sem impacto funcional.)

### Veredito por critério de aceite

| # | Critério | Veredito | Evidência |
|---|---|---|---|
| 1 | Falha de uma fonte (mockada) não impede o processamento das demais; erro registrado, não fatal | **passed** | `TestAC1ResilienciaDeFontes` (5 testes). Além do cenário do executor, testei `RSSNewsSourceProvider` real com `requests.get` mockado simulando `Timeout`, `HTTPError` (HTTP 500) e XML malformado — todos os três geram `FonteIndisponivelError` (não uma exceção genérica), confirmando o contrato na camada de provider, não só na orquestração. `test_pipeline_completo_com_4_fontes_uma_falhando_por_timeout_real` simula as 4 fontes-semente via `RSSNewsSourceProvider` (não um dublê de alto nível), com 1 falhando por timeout de rede simulado — as outras 3 são processadas e persistidas (`NewsItem.objects.count() == 3`). Também testei exceção genérica não documentada (`RuntimeError`) para confirmar que a resiliência não se limita ao tipo de erro esperado. |
| 2 | Itens de fontes diferentes sobre o mesmo acontecimento → mesmo `NewsCluster` | **passed** | `TestAC2DeduplicacaoEAgrupamento` (4 testes) — inclui caso positivo (3 fontes, 1 cluster), caso negativo (acontecimentos distintos não agrupados), confirmação de que `SummarizationProvider` é chamado 1x por cluster (não por item, conforme decisão técnica 2 do executor) e teste puro de `agrupar_itens_brutos` sem tocar banco. |
| 3 | `url_fonte_original`/`nome_fonte` obrigatórios — ausência impede criação (validação, não best-effort) | **passed** | `TestAC3FonteObrigatoriaEmDuasCamadas` (5 testes). Confirmei as DUAS camadas independentemente: camada 1 (`save()`/`clean()`, `ValidationError`) e camada 2 — teste próprio, não presente na suíte de sanidade do executor — usando `NewsItem.objects.bulk_create(...)` (que **contorna** `save()`/`clean()` deliberadamente) dentro de `transaction.atomic()`, confirmando que a `CheckConstraint` de banco (`newsitem_fonte_obrigatoria`) sozinha barra a escrita mesmo sem passar pela validação em Python — `IntegrityError: CHECK constraint failed: newsitem_fonte_obrigatoria`, `NewsItem.objects.count() == 0` depois. Isso valida de fato a alegação de "defesa em profundidade" da decisão técnica 9, que a suíte do executor não exercitava. |
| 4 | `resumo_proprio` preenchido pelo provider, nunca cópia do bruto | **FAILED (gap crítico)** | `TestAC4ResumoProprioNuncaECopia` (4 testes, 1 `xfail` estrito). O caminho feliz (provider bem-comportado devolvendo texto genuinamente diferente) passa, replicando e reforçando o que o executor já havia validado. **Porém**, escrevi um teste adversarial (`test_provider_mal_comportado_que_devolve_copia_literal_do_bruto_e_bloqueado`, marcado `xfail(strict=True)` para que a suíte deixe evidência permanente do gap sem quebrar o CI): um `SummarizationProvider` mockado que devolve `resumo = conteudo_bruto` (simulando um LLM que "alucina"/copia o texto, ou uma implementação futura com bug de copy-paste) **não é barrado por nenhuma validação do pipeline**. Confirmado interativamente antes de formalizar o teste: `item.resumo_proprio == item.conteudo_bruto` → `True`; `item.status_revisao` → `'nao_aplicavel'`; `item.publicado_automaticamente` → `True`. Ou seja: **o item é publicado automaticamente com um resumo idêntico ao texto bruto da fonte, sem qualquer sinalização de risco ou envio à fila de revisão humana.** `services/ingestao.py::_persistir_grupo` confia cegamente no `resultado.resumo` retornado pelo provider — a única defesa hoje é o comportamento do provider mockado nos testes do executor, não uma validação estrutural do sistema. Isso viola diretamente a restrição técnica mais crítica do contrato ("Direitos autorais... Qualquer violação (resumo idêntico à fonte, ausência de atribuição) é tratada como bug bloqueante, não estético"). **Não corrigi o código** (fora do escopo do tester) — reporto como falha bloqueante para o `remediator`/`orchestrator`. |
| 5 | Alta relevância (categoria sensível OU limiar de fontes) → `pendente`; senão → `nao_aplicavel` | **passed** | `TestAC5FilaDeRevisaoHumana` (5 testes) — os dois ramos testados **isoladamente** (categoria sensível com limiar de fontes deliberadamente alto/inatingível; limiar de fontes atingido com categoria deliberadamente não sensível), mais o caso combinado (ambos os critérios simultâneos) e a confirmação explícita de que baixa relevância não fica presa em revisão (`status_revisao == nao_aplicavel`, item ausente do queryset `filter(status_revisao=PENDENTE)` que o admin usaria para a fila). |
| 6 | Registro consultável por execução (itens/fonte, duplicatas, chamadas/custo do provider) | **passed** | `TestAC6RegistroDeExecucaoConsultavel` (2 testes) — cenário próprio combinando sucesso, duplicata agrupada, item isolado e erro de fonte na mesma execução, com verificação de todos os campos (`itens_por_fonte`, `erros_por_fonte`, `total_itens_ingeridos`, `total_grupos_formados`, `total_duplicatas_agrupadas`, `chamadas_summarization_provider`, `tokens_utilizados_summarization`, `custo_estimado_summarization_usd`), incluindo releitura via `RegistroExecucaoIngestao.objects.get(pk=...)` (consulta nova, não o objeto em memória) e confirmação de que execuções sucessivas geram registros distintos e ambos consultáveis (histórico, não sobrescrita). |
| 7 | Categorias sensíveis/limiar de fontes configuráveis sem alteração de código | **passed** | `TestAC7ConfiguravelSemAlterarCodigo` (4 testes). Além de `override_settings` (utilitário de teste do Django), escrevi um teste mais forte e independente do mecanismo de teste do Django: `test_configuracao_e_lida_de_verdade_via_variavel_de_ambiente_no_settings_py` sobe um **subprocesso Python isolado** que importa `config.settings` com `CATALOGO_NOTICIAS_LIMIAR_FONTES_ALTA_RELEVANCIA=7` e `CATALOGO_NOTICIAS_CATEGORIAS_SENSIVEIS=clima,tecnologia` via variável de ambiente real (o mecanismo de produção, não um artifício de teste) e confirma que `settings.py` de fato lê esses valores do ambiente — evidência de que a configuração muda sem tocar em nenhum arquivo de código/lógica de negócio. |

### Observação adicional (não é um dos 7 critérios, mas parte do "O que deve ser construído")

**Job periódico via Celery — validação estrutural apenas, não ponta-a-ponta:** confirmei independentemente (não apenas aceitei a palavra do executor) que não há servidor Redis disponível neste ambiente (`socket.connect(('localhost', 6379))` → timeout) e que a task Celery é importável e corretamente registrada:
```
celery app ok: <Celery brd_portal_noticias ...>
task registered: catalogo_noticias.tasks.ingerir_noticias
beat schedule: {'catalogo-noticias-ingerir-noticias': {'task': 'catalogo_noticias.tasks.ingerir_noticias', 'schedule': 900}}
```
Isso é **blocked** por limitação de ambiente (mesma já documentada para PostgreSQL na Iteração 1 do run anterior), não uma falha de implementação — não tentei contornar (ex.: subir um Redis local), conforme instrução recebida. Recomendo validação com Redis real em staging/CI antes do deploy, como o próprio executor já havia recomendado.

### Testes triviais/fracos vs. testes que de fato exercitam o critério

Para transparência: os testes de "caminho feliz" do AC-4 e a maioria dos testes de AC-2/AC-5/AC-6 são reforços/variações do que a suíte de sanidade do executor já cobria com dublês bem-comportados — valiosos como regressão, mas não são, isoladamente, evidência forte do critério mais arriscado. Os testes que considero terem realmente **agregado cobertura independente e adversarial** (não apenas confirmado que o código não quebra) são: os três testes de falha real de rede/parsing em `RSSNewsSourceProvider` (AC-1), o teste de `bulk_create` contornando `save()` (AC-3), o teste adversarial de provider "copiando" o bruto (AC-4, o mais importante — revelou um gap real) e o teste de variável de ambiente via subprocesso (AC-7).

### Veredito geral da fase de testing

**failed** — 6 de 7 critérios de aceite passaram com evidência independente (execução real da suíte, não apenas leitura de código). O critério 4 (direitos autorais, `resumo_proprio` nunca cópia do bruto) tem um **gap crítico não coberto por nenhuma validação de sistema**: o pipeline confia cegamente no `SummarizationProvider` e publicaria automaticamente um item cujo "resumo" é uma cópia literal do texto bruto da fonte, sem qualquer bloqueio ou envio à revisão humana — exatamente o risco que o próprio contrato classifica como "bug bloqueante, não estético" (restrição técnica "Direitos autorais"). Recomendo que o `remediator`/`orchestrator` trate isso como bloqueante antes de avançar para `reviewer`/`documenter`, dado que `review-triggers.md` já exige revisão obrigatória por direitos autorais/compliance neste run.

**Arquivos tocados nesta iteração:**
- `backend/catalogo_noticias/tests/test_acceptance_criteria.py` (novo — suíte formal, 28 testes)
- `agentic-framework/state/run-20260902-0727-ingestao-noticias/implementation-history.md` (esta entrada)

---

## Iteração 3 — 2026-09-02 — remediator (correção dos findings do code-review-contract.md)

**Objetivo:** resolver o veredito `blocked` do `code-review-contract.md` (1 blocker + 2 major + 2 minor), iteração 1 de 3 do orquestrador. Ordem de trabalho: blocker primeiro, depois os 2 major, depois os 2 minor se triviais/baixo risco.

### Finding 1 (blocker) — `resumo_proprio` podia ser cópia/quase-cópia do `conteudo_bruto` sem bloqueio

**Quem corrigiu:** remediator (fix direto, `Edit`).

**O que foi mudado:**
- `backend/config/settings.py`: nova setting `CATALOGO_NOTICIAS_RESUMO_SIMILARIDADE_MAXIMA` (default `0.6`, configurável via env var), limiar de `SequenceMatcher.ratio()` acima do qual `resumo_proprio` é considerado cópia/quase-cópia do bruto.
- `backend/catalogo_noticias/services/ingestao.py`: nova função `_resumo_e_copia_ou_quase_copia(resumo, grupo)` — compara `resultado.resumo` contra o `conteudo_bruto` de CADA item do grupo via `SequenceMatcher`; se a similaridade de qualquer item exceder o limiar, loga um WARNING e retorna `True`. `_persistir_grupo` agora computa `resumo_suspeito_de_copia` e o inclui na decisão de `alta_relevancia` (junto com `sem_resumo_confiavel` e `_eh_alta_relevancia`) — um resumo suspeito força `status_revisao=pendente` em vez de publicação automática, sem derrubar o pipeline (mesmo tratamento já dado a resumo vazio).
- `backend/catalogo_noticias/tests/test_acceptance_criteria.py`: o teste adversarial `test_provider_mal_comportado_que_devolve_copia_literal_do_bruto_e_bloqueado` (que era `xfail(strict=True)`, documentando o gap) teve o marcador `xfail` removido e as asserções invertidas para o comportamento correto agora garantido (`status_revisao == PENDENTE`, `publicado_automaticamente is False`). Adicionado teste novo `test_provider_mal_comportado_que_devolve_quase_copia_parafraseada_tambem_e_bloqueado` (cópia parafraseada, similaridade ~0.93, não 1.0 exato) para provar que o bloqueio não depende de igualdade literal.

**Revalidação:** suíte completa rodada (`DJANGO_DB_ENGINE=sqlite3 pytest -q`) — os 2 testes de AC-4 relevantes passam (incluindo o antes-`xfail`, agora passando de verdade, sem `XPASS` estrito quebrando o CI). `manage.py check` limpo.

### Finding 4 (minor) — default de `CATALOGO_NOTICIAS_LLM_API_BASE_URL` mascarava erro de configuração

**Quem corrigiu:** remediator (fix direto, `Edit`), tratado por ser trivial/baixo risco conforme autorizado.

**O que foi mudado:** `backend/catalogo_noticias/providers/summarization.py::LLMHttpSummarizationProvider.__init__` — se `self.api_key` estiver vazia, loga um `WARNING` explícito no momento da instanciação (não só um `ERROR` por chamada de API falhando), apontando a causa raiz (API key ausente) em vez de deixar o operador só ver "tudo cai em pendente" no admin. Não mudei o default da URL (mantém `https://api.openai.com/v1`) — optei pela sugestão mais conservadora do reviewer (WARNING) em vez de trocar o default (menor risco de efeito colateral).

**Revalidação:** suíte completa continua passando; nenhum teste depende do comportamento anterior (confirmado via grep antes da mudança).

### Finding 5 (minor) — N+1 query em `_item_bruto_ja_ingerido`

**Quem corrigiu:** remediator (fix direto, `Edit`), tratado por ser trivial/baixo risco conforme autorizado.

**O que foi mudado:** `backend/catalogo_noticias/services/ingestao.py` — `_item_bruto_ja_ingerido` (uma query `EXISTS` por item, dentro do loop) substituída por `_urls_ja_ingeridas(itens)`, uma única query por fonte (`NewsItem.objects.filter(url_fonte_original__in=[...]).values_list(...)`), usada em `executar_ingestao` para filtrar itens novos antes do agrupamento.

**Revalidação:** suíte completa continua passando (nenhum teste dependia da função antiga, que foi removida por ficar sem uso).

### Finding 2 (major) — falsos positivos de agrupamento por padrão sintático comum

**Quem corrigiu:** delegado ao `executor` (mudança de algoritmo com nuance real — ver análise abaixo) via mini-contrato do remediator.

**Análise prévia do remediator (compartilhada com o executor para não retrabalho):** confirmei que só subir o limiar numérico do algoritmo antigo (`max(jaccard, SequenceMatcher sobre tokens ordenados)`) não resolve — o par genuíno mais fraco exigido pelos testes existentes (`TestAC2DeduplicacaoEAgrupamento`, "Presidente sanciona novo pacote fiscal" vs. "...anunciado ontem") pontua 0.805, e o par de "incêndio" do `test_sanity.py` precisa de pelo menos 0.785, mas os 3 pares de falso-positivo do reviewer pontuam 0.646–0.857 — os intervalos se sobrepõem, não existe limiar único que separe. Uma variante "Jaccard com penalização de palavras diferenciadoras" (sem contexto de lote) também não separou (par "pacote fiscal" caiu para 0.571, o falso-positivo "Prefeitura..." para 0.600 — ainda sobreposto). Uma simulação com ponderação tipo-IDF por frequência NO LOTE INTEIRO (não no par isolado) mostrou separação clara (falsos-positivos 0.34–0.53, genuínos 0.63–0.84) — repassada ao executor como pista, não prescrição.

**O que o executor mudou (`backend/catalogo_noticias/services/deduplicacao.py`, reescrito):** Jaccard ponderada por token, com pareamento fuzzy por token (`SequenceMatcher` por token individual, limiar 0.82, preserva a robustez a variação de gênero/número tipo "grande"/"grandes" que a versão anterior já tinha). O peso de cada token é calculado dinamicamente a partir da distribuição de frequência do PRÓPRIO lote sendo agrupado (`_pesos_por_frequencia_no_lote`) — não uma lista fixa hardcoded de "palavras de molde": um token só é tratado como "genérico do lote" (peso residual 0.15) se aparecer em pelo menos 4 itens do lote E o lote tiver pelo menos 6 itens (evita boost/penalização em lotes pequenos/artificiais, onde qualquer heurística de frequência não tem dados suficientes). Deliberadamente não usou `conteudo_bruto` como sinal (uma das opções sugeridas) — decisão justificada no docstring do módulo (nos dublês de teste existentes o conteúdo é um placeholder genérico repetido, o que geraria falso sinal).

**Teste novo:** `TestFinding2FalsoPositivoPorPadraoSintaticoComum` (2 testes) — usa um lote de 15 itens (os 3 pares do reviewer + itens de contexto realista que reforçam, via repetição real no lote, que as frases são molde comum + 1 par genuinamente duplicado como controle), via `agrupar_itens_brutos()` e via `executar_ingestao()` ponta a ponta. Confirma que os 3 pares do reviewer não compartilham grupo/cluster e que o par de controle continua se agrupando (a correção não degenera em "nunca mais agrupa nada").

**Revalidação (remediator, independente):** li o diff completo de `deduplicacao.py` e `ingestao.py` linha a linha antes de aceitar; rodei a suíte completa eu mesmo (não só confiei no relato do executor) — `90 passed, 7 warnings`. Rodei também isoladamente os 10 testes de AC-4/Finding2/Finding3 com `-v` para confirmar que nenhum está sendo mascarado/skipado. `manage.py check` limpo.

### Finding 3 (major) — deduplicação não considerava itens de execuções anteriores

**Quem corrigiu:** delegado ao `executor` (mudança estrutural em `ingestao.py`/`deduplicacao.py`, mesma delegação do Finding 2).

**O que foi mudado:**
- `backend/config/settings.py`: nova setting `CATALOGO_NOTICIAS_DEDUP_JANELA_RECENTE_HORAS` (default `24`, configurável via env var).
- `backend/catalogo_noticias/services/ingestao.py`: nova função `_itens_recentes_persistidos()` — UMA única query (`select_related("cluster")`, evita N+1) busca todo `NewsItem` com `timestamp_ingestao` dentro da janela recente, devolvidos como `ItemBruto` "pseudo" que entram no MESMO `agrupar_itens_brutos()` dos itens novos da execução atual (`itens_para_agrupar = todos_itens_brutos + itens_recentes_persistidos`). Nova função `_persistir_grupo_mesclado()` trata grupos que misturam itens novos com `NewsItem`s já persistidos: (a) não re-resume itens antigos (evita custo redundante ao `SummarizationProvider`, documentado como limitação conhecida — resumos podem ficar "desconectados" dentro do mesmo cluster); (b) determina o cluster canônico — promove item standalone a cluster novo, ou mescla clusters diferentes no caso raro de dois clusters se revelarem o mesmo fato via o item-ponte; (c) reavalia `status_revisao` de TODOS os itens do cluster (antigos e novos) sempre que a união cruza `_eh_alta_relevancia`, mas nunca sobrescreve `aprovado`/`rejeitado` (decisão humana já tomada é preservada).

**Teste novo:** `TestFinding3DeduplicacaoEntreExecucoesDaTask` (3 testes) — (1) cenário do reviewer ponta a ponta: G1 sozinho no ciclo 1 (`nao_aplicavel`, `cluster=None`), UOL+CNN Brasil no ciclo 2 cobrindo o mesmo fato — depois do ciclo 2, os 3 itens (incluindo o antigo) estão no mesmo cluster com 3 fontes distintas e TODOS viram `pendente`, inclusive o antigo já `nao_aplicavel`; confirma também que o item antigo não foi re-resumido; (2) salvaguarda mais importante: um item com `status_revisao=rejeitado` (decisão humana simulada) NUNCA é sobrescrito pela mesclagem automática, mesmo cruzando o limiar de fontes — os itens novos seguem a reavaliação normal; (3) item fora da janela configurada (`timestamp_ingestao` empurrado para 48h atrás, janela reduzida para 1h via `override_settings`) não é considerado, permanece `cluster=None`.

**Revalidação (remediator, independente):** mesma leitura de diff linha a linha + suíte completa rodada pelo remediator (`90 passed`), incluindo explicitamente `TestAC6RegistroDeExecucaoConsultavel::test_execucoes_sucessivas_geram_registros_distintos_consultaveis_no_historico` (2 execuções com fatos NÃO relacionados continuam sem se agrupar — restrição dura do mini-contrato, confirmada). `manage.py check` limpo.

### Resultado final da suíte (revalidação do remediator, não só do executor)

```
DJANGO_DB_ENGINE=sqlite3 ./.venv/Scripts/python.exe -m pytest -q
# -> 90 passed, 7 warnings in ~55s
```
(85 testes da Iteração 2 + 5 novos: 2 de Finding 2, 3 de Finding 3; o teste antes-`xfail` de Finding 1 agora conta como `passed` normal, não somou ao total de novos). `manage.py check` limpo (sqlite, com `DJANGO_SECRET_KEY` de teste).

### Veredito desta iteração

**Todos os 5 findings do `code-review-contract.md` (1 blocker + 2 major + 2 minor) foram resolvidos e revalidados de forma independente pelo remediator** (não apenas aceitos da palavra de quem implementou) — nenhum finding ficou pendente nesta iteração. Devolvo o controle ao `orchestrator` para decidir se envia para nova rodada do `reviewer` (recomendado, dado que o veredito anterior era `blocked` por compliance/direitos autorais) ou segue para `documenter`.

**Arquivos tocados nesta iteração:**
- `backend/config/settings.py` (modificado — `CATALOGO_NOTICIAS_RESUMO_SIMILARIDADE_MAXIMA`, `CATALOGO_NOTICIAS_DEDUP_JANELA_RECENTE_HORAS`)
- `backend/catalogo_noticias/services/ingestao.py` (modificado — Finding 1, 3, 5)
- `backend/catalogo_noticias/services/deduplicacao.py` (modificado — Finding 2)
- `backend/catalogo_noticias/providers/summarization.py` (modificado — Finding 4)
- `backend/catalogo_noticias/tests/test_acceptance_criteria.py` (modificado — testes novos/atualizados para Finding 1, 2, 3)
- `backend/.env.example` (modificado — documentação de `CATALOGO_NOTICIAS_DEDUP_JANELA_RECENTE_HORAS`)
- `agentic-framework/state/run-20260902-0727-ingestao-noticias/implementation-history.md` (esta entrada)

---

## Iteração 4 — 2026-09-02 — remediator (correção dos findings da 2a passada do code-review-contract.md)

**Objetivo:** resolver o veredito `changes_requested` da 2a passada do `code-review-contract.md` (0 blocker + 2 major + 2 minor, todos tocando BRD secao 18 — direitos autorais/misattribution). Iteracao 2 de no maximo 3 do orquestrador. Ordem de trabalho: os 2 major primeiro (mesmo risco critico de compliance), depois os 2 minor.

**Metodologia:** antes de escrever qualquer teste formal, calibrei cada correcao com scripts adversariais proprios no scratchpad (fora da suite), reproduzindo o cenario exato do `reviewer` MAIS variacoes proprias (lotes pequenos de 2-5 itens variados para o Finding 1; copia verbatim de trecho em posicoes diferentes do bruto para o Finding 2) — evitando uma correcao que só funcione para o caso de teste relatado, conforme instrucao recebida. A calibracao do Finding 1 revelou uma REGRESSAO real (2 testes genuinos existentes quebrando) antes de chegar na versao final — documentado abaixo, nao escondido.

### Finding 1 (major, REABERTO na 2a passada) — falso-positivo de agrupamento em lotes pequenos (4 itens)

**Quem corrigiu:** remediator (fix direto, `Edit`) — decidi nao delegar ao executor desta vez porque o problema já estava bem diagnosticado pelo próprio reviewer (3 caminhos sugeridos) e a mudança é localizada em uma única função (`_pesos_por_frequencia_no_lote`), não uma reescrita de algoritmo.

**O que foi mudado:** `backend/catalogo_noticias/services/deduplicacao.py` — adicionado um SEGUNDO mecanismo de ponderação, complementar ao dinâmico existente (que só ativa em lotes >= 6 itens com padrão repetido >= 4 vezes): uma lista curada `_CONECTORES_JORNALISTICOS_COMUNS_PT` de conectores jornalísticos comuns em português (verbos de anúncio — "anuncia"/"lança"/"divulga"/"apresenta" e variações; "veículos" do anúncio — "plano"/"pacote"/"medida"/"programa"/"projeto"; instituições genéricas — "governo"/"prefeitura"/"ministério"/"polícia"; qualificador "novo/nova") recebe peso reduzido (`_PESO_TOKEN_CONECTOR_CURADO = 0.15`) **incondicionalmente**, independente do tamanho do lote — opção (b)+(c) da sugestão do reviewer (lista curada complementando a ponderação dinâmica, não substituindo). `_pesos_por_frequencia_no_lote` agora combina os dois mecanismos via `min()` (o mais conservador prevalece).

**Regressão encontrada e corrigida durante a calibração (não em produção/CI — pego antes do commit):** a primeira versão incluía também títulos de CARGO INDIVIDUAL ("presidente", "prefeito", "ministro", "secretário") na lista curada. Isso quebrou 2 testes genuínos já existentes na suíte (`TestAC2DeduplicacaoEAgrupamento::test_tres_fontes_sobre_mesmo_acontecimento_formam_um_unico_cluster` — "Presidente sanciona novo pacote fiscal" com 3 fontes de redação bem diferente — e `TestFinding3DeduplicacaoEntreExecucoesDaTask::test_status_revisao_ja_decidido_por_humano_nunca_e_sobrescrito_pela_mesclagem` — "Prefeito anuncia reforma de praça pública"), porque em manchetes políticas curtas com 3 fontes de redação bem diferente, o título de cargo é frequentemente uma das poucas palavras remanescentes em comum após remover stopwords — penalizar seu peso incondicionalmente derrubava esses pares genuínos para abaixo do limiar. Testei sistematicamente (script de calibração, variando peso 0.15 a 1.0 e testando remoção seletiva de tokens da lista) até isolar a causa: excluir os 4 títulos de cargo individual da lista curada (mantendo as INSTITUIÇÕES — "governo", "prefeitura", "ministério", "polícia" — que não causaram o mesmo efeito colateral em nenhum caso testado) resolveu ambas as regressões sem reabrir nenhum dos 6 cenários de falso-positivo testados (o do reviewer + 5 variações próprias). Documentado no código (`deduplicacao.py`, comentário acima da lista) para não ser reintroduzido displicentemente numa iteração futura.

**Testes novos:** `TestFinding1FalsoPositivoEmLotesPequenosReaberto` (8 testes) em `test_acceptance_criteria.py` — (1) cenário exato do reviewer (lote de 4 itens, via `agrupar_itens_brutos` puro); (2) o mesmo cenário ponta a ponta via `executar_ingestao`, com um provider que devolve resumo identificável por chamada para provar que os 2 itens do molde comum foram resumidos SEPARADAMENTE (não um único resumo de grupo aplicado indevidamente aos dois); (3) 5 variações parametrizadas ALÉM do cenário do reviewer (pacote de medidas econômicas/educacionais, polícia investiga homicídio/fraude, ministério lança programas em lote de 5, prefeito apresenta projetos diferentes, governo divulga pacotes de auxílio diferentes) em lotes de 2 a 5 itens; (4) salvaguarda: os mesmos pares genuínos já cobertos por `test_sanity.py`/`TestAC2` (pacote fiscal, incêndio, vacina) continuam formando grupo em lotes pequenos após a correção.

**Revalidação:** suíte completa rodada pelo remediator — `106 passed`. Os 8 testes novos rodados isoladamente com `-v` confirmam PASSED individualmente (nenhum mascarado). `manage.py check` limpo.

### Finding 2 (major, NOVO na 2a passada) — cópia parcial verbatim evade a checagem de similaridade

**Quem corrigiu:** remediator (fix direto, `Edit`).

**O que foi mudado:**
- `backend/config/settings.py`: nova setting `CATALOGO_NOTICIAS_RESUMO_TRECHO_COPIADO_MAXIMO` (default `0.6`, configurável via env var).
- `backend/catalogo_noticias/services/ingestao.py`: nova função `_proporcao_do_resumo_copiada_literalmente(resumo, bruto)` — usa `SequenceMatcher(None, resumo, bruto, autojunk=False).get_matching_blocks()`, soma os blocos contínuos idênticos com pelo menos `_TAMANHO_MINIMO_TRECHO_COPIADO_CARACTERES` (20) caracteres (filtra coincidências triviais de palavra isolada/número), e normaliza pelo tamanho do PRÓPRIO resumo (não pelo tamanho combinado dos dois textos — a causa raiz do gap apontado pelo reviewer). `autojunk=False` é deliberado: o autojunk do difflib pode desconsiderar caracteres "populares" (ex. espaço) em textos longos, o que enfraqueceria a detecção justamente no caso que motivou o fix (bruto bem mais longo que resumo). `_resumo_e_copia_ou_quase_copia` agora faz DUAS checagens complementares (qualquer uma basta para bloquear): a checagem 1 existente (ratio sobre o texto inteiro, Finding 1 da 1a passada) + a nova checagem 2 (proporção de trecho copiado).

**Testes novos:** 5 testes em `TestAC4ResumoProprioNuncaECopia` — (1) cenário exato do reviewer (resumo = primeira frase de uma matéria de 7 frases, copiada verbatim); (2) variação com o trecho copiado do MEIO da matéria, não do início (prova que a checagem não depende de posição); (3) variação com DUAS frases não-adjacentes copiadas e concatenadas; (4) salvaguarda: um resumo genuinamente autoral/sintetizado (paráfrase real) na MESMA matéria longa NÃO é bloqueado; (5) teste unitário direto de `_proporcao_do_resumo_copiada_literalmente` confirmando a propriedade central do fix (normalização pelo tamanho do próprio resumo, proporção > 0.95 para o caso verbatim vs. ratio combinado < 0.6 pela fórmula antiga).

**Revalidação:** suíte completa — `106 passed`. Script de calibração próprio (scratchpad, fora da suíte) testou adicionalmente citação curta entre aspas dentro de um resumo autoral e reaproveitamento de termos técnicos/números (nenhum dos dois dispara falso-positivo, proporção máxima observada 0.208 contra limiar 0.6 — margem confortável).

### Finding 4 (minor) — clusters órfãos após merge não eram limpos

**Quem corrigiu:** remediator (fix direto, `Edit`) — tratado por ser trivial e de baixo risco (o modelo já usa `on_delete=SET_NULL` na FK `NewsItem.cluster`, então mover os itens antes de deletar o cluster não-canônico é seguro).

**O que foi mudado:** `backend/catalogo_noticias/services/ingestao.py::_persistir_grupo_mesclado` — após `NewsItem.objects.filter(cluster_id__in=outros_ids).update(cluster=cluster)`, adicionado `NewsCluster.objects.filter(pk__in=outros_ids).delete()`.

**Teste novo:** `TestFinding4ClusterOrfaoAposMesclagemERemovido` — teste direto/unitário de `_persistir_grupo_mesclado` (não via `executar_ingestao` ponta a ponta, pois reproduzir de forma confiável via pipeline completo o cenário raro de "dois clusters diferentes revelados como o mesmo fato" dependeria de calibrar manchetes para o algoritmo de similaridade encadear exatamente dessa forma — indireto para testar uma regra de limpeza de dados). Cria 2 `NewsCluster` reais com 1 `NewsItem` cada, chama a função com um item-ponte, confirma que o cluster não-canônico é DELETADO (não apenas esvaziado) e que nenhum `NewsItem` fica órfão.

**Revalidação:** suíte completa — `106 passed`. `manage.py check` limpo.

### Finding 5 (minor/performance) — lote de deduplicação sem limite superior de itens

**Quem corrigiu:** remediator (fix direto, `Edit`) — trivial, seguindo a sugestão do reviewer.

**O que foi mudado:**
- `backend/config/settings.py`: nova setting `CATALOGO_NOTICIAS_DEDUP_MAX_ITENS_RECENTES` (default `300`, configurável via env var).
- `backend/catalogo_noticias/services/ingestao.py::_itens_recentes_persistidos`: query agora tem `.order_by("-timestamp_ingestao")[:limite_itens]` além do filtro por janela de tempo — prioriza os itens mais recentes quando o volume excede o teto.

**Teste novo:** `TestFinding5TetoDeItensRecentesTrazidosParaOAgrupamento` (2 testes) — (1) com o teto reduzido via `override_settings` para 3 e 5 `NewsItem` na janela, confirma que só os 3 mais RECENTES (por `timestamp_ingestao`, não por ordem de criação) são trazidos; (2) salvaguarda: com volume abaixo do teto, nenhum item é descartado.

**Revalidação:** suíte completa — `106 passed`. `manage.py check` limpo.

### Resultado final da suíte (revalidação do remediator)

```
DJANGO_DB_ENGINE=sqlite3 ./.venv/Scripts/python.exe -m pytest -q
# -> 106 passed, 7 warnings in ~95s
```
(90 testes ao final da Iteração 3 + 16 novos: 8 de Finding 1, 5 de Finding 2, 1 de Finding 4, 2 de Finding 5). `manage.py check` limpo (sqlite, com `DJANGO_SECRET_KEY` de teste).

Durante a limpeza do arquivo de testes, uma linha órfã pré-existente (`assert item_uol.cluster.numero_fontes_distintas == 2`, referenciando uma variável fora de escopo — resquício de uma edição anterior ao trabalho deste remediator) foi encontrada no final do arquivo, causando `NameError` isolado; removida por não pertencer a nenhum teste funcional (nenhuma asserção coberta por ela foi perdida — `numero_fontes_distintas` já é verificado em `TestAC2` e em `TestFinding3` linha 1345).

### Veredito desta iteração

**Os 2 major e os 2 minor da 2a passada do `code-review-contract.md` foram todos resolvidos e revalidados de forma independente pelo remediator** (calibração adversarial própria antes de formalizar testes, não apenas "deveria funcionar"). Nenhum finding ficou pendente. A calibração do Finding 1 revelou e corrigiu uma regressão real antes de chegar à versão final — registrado acima para transparência, não porque a versão final tenha esse problema.

Devolvo o controle ao `orchestrator`. Recomendo enviar para uma 3a passada do `reviewer` antes de `documenter`, dado que os 2 major desta rodada tocavam diretamente BRD seção 18 (mesmo risco crítico já sinalizado nas 2 passadas anteriores) — mas essa decisão é do orchestrator, não uma imposição deste remediator.

**Arquivos tocados nesta iteração:**
- `backend/catalogo_noticias/services/deduplicacao.py` (modificado — Finding 1 reaberto: lista curada de conectores + combinação via `min()`)
- `backend/catalogo_noticias/services/ingestao.py` (modificado — Finding 2: `_proporcao_do_resumo_copiada_literalmente`; Finding 4: delete de cluster órfão; Finding 5: teto de itens recentes)
- `backend/config/settings.py` (modificado — `CATALOGO_NOTICIAS_RESUMO_TRECHO_COPIADO_MAXIMO`, `CATALOGO_NOTICIAS_DEDUP_MAX_ITENS_RECENTES`)
- `backend/catalogo_noticias/tests/test_acceptance_criteria.py` (modificado — `TestFinding1FalsoPositivoEmLotesPequenosReaberto`, 4 testes novos + 1 unitário em `TestAC4ResumoProprioNuncaECopia`, `TestFinding4ClusterOrfaoAposMesclagemERemovido`, `TestFinding5TetoDeItensRecentesTrazidosParaOAgrupamento`; removida 1 linha órfã pré-existente)
- `backend/.env.example` (modificado — documentação de `CATALOGO_NOTICIAS_RESUMO_SIMILARIDADE_MAXIMA` (faltava desde a Iteração 3), `CATALOGO_NOTICIAS_RESUMO_TRECHO_COPIADO_MAXIMO`, `CATALOGO_NOTICIAS_DEDUP_MAX_ITENS_RECENTES`)
- `agentic-framework/state/run-20260902-0727-ingestao-noticias/implementation-history.md` (esta entrada)

---

## Iteração 5 — 2026-09-02 — orchestrator agindo como remediator (iteração 3/3, última permitida)

**Contexto:** a 3ª passada do `reviewer` (`code-review-contract.md`) encontrou o Finding 1 (major) reaberto pela 3ª vez consecutiva: agrupamento indevido de notícias sobre fatos diferentes que compartilham vocabulário institucional comum (ex.: "Ministério da Saúde confirma novo surto de dengue" vs. "...de sarampo"; "Presidente confirma viagem oficial aos EUA" vs. "...à China", este em lote de só 2 itens). O reviewer classificou a estratégia das duas rodadas anteriores (ampliar uma lista curada de conectores) como estruturalmente "whack-a-mole" e recomendou mudança de estratégia.

**Quem corrigiu e por quê:** normalmente esta etapa seria do `remediator` via `Agent`, mas o classificador de segurança que autoriza spawnar subagentes (`Agent`) e executar comandos de teste/código via `Bash` ficou **indisponível de forma sustentada** nesta sessão (múltiplas tentativas ao longo de mais de uma hora, incluindo `SendMessage` para retomar uma tentativa anterior interrompida por rate limit — todas recusadas com "temporarily unavailable... cannot determine the safety"). Operações de arquivo (`Read`/`Write`/`Edit`) e comandos triviais de shell (`ls`, `cat`, `grep`, `echo`, `python --version`) continuaram funcionando normalmente durante todo esse período — a indisponibilidade foi especificamente da categoria "executar código/spawnar agente", não uma falha geral de ferramentas. Diante disso, e a pedido explícito do usuário para prosseguir ("quero continuar a implementação até terminar", depois "finalize!"), o `orchestrator` aplicou a correção diretamente via `Edit`, com o mesmo rigor esperado do `remediator` (leitura completa do código afetado, raciocínio explícito sobre cada mudança, busca ativa por regressões antes de finalizar), documentado abaixo.

**Mudança de estratégia aplicada:** `services/ingestao.py` — o `SummarizationProvider` passa a ser chamado **individualmente, uma vez por item** (`executar_ingestao`, dentro do loop `for grupo in grupos`), nunca mais uma vez para o grupo/cluster inteiro. `_persistir_grupo` e `_persistir_grupo_mesclado` foram reescritas para receber `resultados_por_item: list[tuple[ItemBruto, ResultadoResumo]]` em vez de um único `ResultadoResumo` compartilhado. Isso elimina **estruturalmente** (não por heurística de similaridade, que já havia falhado 3 vezes com vocabulário novo) o risco central do BRD §18: mesmo que o algoritmo de deduplicação erre e agrupe "surto de dengue" com "surto de sarampo" no mesmo `NewsCluster`, cada `NewsItem` continua tendo seu PRÓPRIO `resumo_proprio`, gerado exclusivamente do seu PRÓPRIO `conteudo_bruto` — nunca mais um resumo de um fato atribuído a uma fonte que noticiou outro fato.

**Tentativa revertida (transparência sobre uma regressão que eu mesmo introduzi e corrigi antes de finalizar):** a primeira versão desta correção também forçava `status_revisao=pendente` incondicionalmente para QUALQUER `NewsCluster` com 2+ itens, independente de categoria/número de fontes — fechando também o caso de lote de 2 itens que o reviewer sinalizou. Ao revisar o próprio código com cuidado (sem poder rodar testes), percebi que isso quebraria `TestAC7ConfiguravelSemAlterarCodigo::test_aumentar_limiar_via_override_settings_tambem_muda_comportamento` — um critério de aceite JÁ EXISTENTE e testado (`implementation-contract.md`, critério 7) que garante que o admin pode configurar `CATALOGO_NOTICIAS_LIMIAR_FONTES_ALTA_RELEVANCIA` alto o suficiente para desativar essa revisão automática por número de fontes. Reverti essa parte antes de considerar a correção pronta: o critério de `_eh_alta_relevancia` (categoria sensível OU número de fontes ≥ limiar) permanece **exatamente** como estava antes desta iteração, tanto em `_persistir_grupo` quanto em `_persistir_grupo_mesclado`.

**Residual conhecido, aceito conscientemente (não fechado nesta correção):** um `NewsCluster` de 2 itens, com categoria não-sensível e abaixo do limiar de fontes configurado, ainda PODE ser publicado automaticamente (`status_revisao=nao_aplicavel`) — o mesmo comportamento de antes das 3 passadas de revisão. O que mudou é que isso não representa mais risco de CONTEÚDO incorreto (cada item, mesmo nesse cenário, tem seu próprio resumo corretamente atribuído) — o risco residual é puramente de exibição/agrupamento (um cluster pode reunir 2 itens que na verdade são sobre fatos diferentes, com um `titulo_acontecimento` de cluster potencialmente impreciso), não mais um risco de compliance de direitos autorais/misattribution de conteúdo. Fica registrado para o usuário decidir se isso é aceitável para o MVP ou se merece uma revisão de produto do próprio AC-7 (ex.: seria razoável o admin poder configurar um limiar MÍNIMO de itens-por-cluster que sempre exige revisão, independente do limiar de fontes "oficial"?) — decisão de produto, não uma correção técnica pendente.

**Testes existentes atualizados** (a mudança de "uma chamada por grupo" para "uma chamada por item" altera contagens observáveis, não apenas comportamento interno):
- `backend/catalogo_noticias/tests/test_sanity.py` — `test_registro_execucao_ingestao_registra_metricas_observaveis`: `chamadas_summarization_provider`/`tokens_utilizados_summarization`/`custo_estimado_summarization_usd` recalculados (2 chamadas em vez de 1, para um grupo de 2 itens).
- `backend/catalogo_noticias/tests/test_acceptance_criteria.py`:
  - `TestAC2DeduplicacaoEAgrupamento::test_summarization_provider_e_chamado_uma_vez_por_cluster_nao_uma_vez_por_item` → renomeado e reescrito para `test_summarization_provider_e_chamado_uma_vez_por_item_nao_uma_vez_por_cluster`, com docstring explicando a reversão da decisão técnica original do executor (Iteração 1, decisão técnica 2) e por quê.
  - `TestAC6RegistroDeExecucaoConsultavel::test_registro_persistido_com_metricas_corretas_incluindo_erro_de_fonte` — contagens recalculadas (3 chamadas em vez de 2: grupo de 2 + grupo de 1).
  - `TestFinding4ClusterOrfaoAposMesclagemERemovido::test_cluster_nao_canonico_e_deletado_apos_itens_serem_movidos_para_o_canonico` — chamada direta a `_persistir_grupo_mesclado` atualizada para a nova assinatura (`resultados_por_item=[(item, resultado)]` em vez de `itens_novos=[...], resultado=...`).
  - Revisei manualmente (busca por `chamadas ==`, `status_revisao ==`, `resumo_proprio ==`, `_persistir_grupo`) TODOS os demais testes que tocam `executar_ingestao`/`_persistir_grupo*` para confirmar que nenhum outro dependia da semântica antiga — em particular, `TestAC7ConfiguravelSemAlterarCodigo` (3 testes) e `TestFinding3DeduplicacaoEntreExecucoesDaTask` (3 testes) foram revisados linha a linha e **não precisaram de nenhuma alteração**, pois seus cenários já eram compatíveis com o critério de relevância preservado (a reversão documentada acima).

**Teste novo (adversarial, escrito para provar o núcleo da correção diretamente, não só via `executar_ingestao` ponta a ponta):** `TestFinding1MisattributionDeConteudoMesmoComAgrupamentoIndevido` (2 testes), ao final de `test_acceptance_criteria.py`:
1. `test_persistir_grupo_nunca_atribui_resumo_de_um_item_a_outro_do_mesmo_grupo` — chama `_persistir_grupo` diretamente com 2 itens de fatos diferentes (dengue/sarampo) FORÇADOS no mesmo grupo (bypass deliberado do algoritmo de dedup real, já testado separadamente), confirmando que cada `NewsItem` recebe o resumo correspondente ao seu próprio fato, nunca ao do outro.
2. `test_persistir_grupo_mesclado_tambem_nunca_atribui_resumo_de_um_item_a_outro` — mesma garantia no caminho de mesclagem entre execuções, confirmando que um item já persistido nunca é re-escrito com o resumo de um item novo que se junta a ele, e vice-versa.

**Validação por execução: NÃO REALIZADA nesta iteração.** Apesar de múltiplas tentativas ao longo de mais de uma hora (`Bash` executando `pytest`, `Agent` spawnando um `tester`, `SendMessage` para retomar uma tentativa interrompida), o classificador de segurança da sessão permaneceu indisponível para qualquer ação de execução de código, mesmo após a suíte de testes ter sido ajustada e o teste adversarial novo ter sido escrito. Toda a correção acima foi validada por **leitura cuidadosa do código, não por execução** — inclusive a descoberta e correção da regressão de AC-7 só foi possível por essa leitura manual, já que não havia como rodar `pytest` para descobri-la de outra forma.

**Isso é uma lacuna real de verificação, não uma formalidade.** Recomendo fortemente que, assim que ferramentas de execução estiverem disponíveis novamente (nesta sessão ou em uma futura), alguém rode:
```
cd C:\alex\brd_portal_noticias\backend && DJANGO_DB_ENGINE=sqlite3 .venv/Scripts/python.exe -m pytest -q
```
e confirme que a suíte completa (esperado: 108 testes — 106 da Iteração 4 + 2 novos desta iteração) passa sem falhas, antes de considerar este `run_id` verdadeiramente pronto para uma 4ª passada do `reviewer` e posterior fechamento pelo `documenter`/`historian`.

**Arquivos tocados nesta iteração:**
- `backend/catalogo_noticias/services/ingestao.py` (modificado — mudança de estratégia: `SummarizationProvider` por item; `_persistir_grupo`/`_persistir_grupo_mesclado` reescritas)
- `backend/catalogo_noticias/tests/test_sanity.py` (modificado — contagens de chamadas/tokens/custo recalculadas)
- `backend/catalogo_noticias/tests/test_acceptance_criteria.py` (modificado — teste renomeado/reescrito, contagens recalculadas, assinatura de chamada direta atualizada, nova classe `TestFinding1MisattributionDeConteudoMesmoComAgrupamentoIndevido` com 2 testes)
- `agentic-framework/state/run-20260902-0727-ingestao-noticias/implementation-history.md` (esta entrada)

---
