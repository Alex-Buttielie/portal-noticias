# Implementation Contract — 20260902-0727-ingestao-noticias

## Metadados
- **run_id:** 20260902-0727-ingestao-noticias
- **Deriva de:** task-plan.md (20260902-0727-ingestao-noticias)
- **Versão do contrato:** 1

## O que deve ser construído
App Django `catalogo_noticias` para o módulo `catalogo-noticias/` do Portal de Notícias: modelos `NewsItem`/`NewsCluster`, ingestão via RSS de 4 fontes-semente através de uma interface `NewsSourceProvider`, deduplicação/agrupamento em clusters, geração de resumo próprio e classificação de relevância/urgência via `SummarizationProvider` (interface abstrata + implementação concreta usando API de LLM de terceiros), fila de revisão humana para itens de alta relevância, e job periódico via Celery. Reaproveita o projeto Django já existente em `backend/` (run anterior `20260901-2135-cadastro-auth`) como um novo app, não um projeto novo.

## Áreas/arquivos esperados
- `backend/catalogo_noticias/` (novo app Django)
  - `models.py` — `NewsItem`, `NewsCluster`
  - `providers/news_source.py` — interface `NewsSourceProvider` + implementação RSS (`RSSNewsSourceProvider` ou nome equivalente)
  - `providers/summarization.py` — interface `SummarizationProvider` + implementação concreta via LLM de terceiros
  - `services/ingestao.py` — orquestração: buscar fontes → normalizar → deduplicar/agrupar → resumir/classificar → decidir publicação direta vs. fila de revisão
  - `services/deduplicacao.py` — lógica de agrupamento em `NewsCluster`
  - `tasks.py` — task Celery periódica de ingestão
  - `admin.py` — expor `NewsItem`/`NewsCluster` no Django admin, incluindo a fila de revisão (filtro por `status_revisao`)
  - `migrations/`
  - `tests/`
- `backend/config/settings.py` — configuração do Celery/Redis (se ainda não existir do run anterior) e das 4 fontes-semente (via configuração, não hardcoded no meio da lógica de negócio)
- `backend/requirements.txt` — novas dependências (parser de RSS, cliente do LLM escolhido, cliente Celery/Redis)

## Interfaces afetadas
Novas interfaces (não há nada pré-existente de `catalogo_noticias` para quebrar):
- Modelo de dados: `NewsItem` (título, resumo_proprio, url_fonte_original, nome_fonte, categoria, timestamp_publicacao_fonte, timestamp_ingestao, urgente: bool, status_revisao: pendente/aprovado/rejeitado/nao_aplicavel, cluster)
- Modelo de dados: `NewsCluster` (acontecimento/título do cluster, categoria_dominante, itens relacionados)
- Configuração parametrizável (via admin ou settings, a critério do executor — documentar a escolha): lista de categorias sensíveis e limiar de fontes que acionam revisão humana
- `NewsSourceProvider.buscar_itens() -> list[ItemBruto]` — contrato que qualquer fonte futura (API licenciada, outro RSS) deve implementar
- `SummarizationProvider.resumir_e_classificar(itens_brutos) -> ResultadoResumo` — contrato que qualquer provedor de LLM futuro deve implementar

## Critérios de aceite (técnicos, testáveis)
1. Dado as 4 fontes RSS configuradas, quando a task de ingestão roda, então itens de todas as fontes acessíveis são convertidos em `NewsItem`, e uma fonte fora do ar (mockada como erro de rede/parsing) não impede que as demais sejam processadas — o erro é registrado (log/observabilidade), não propagado como exceção fatal da task inteira.
2. Dado dois ou mais `NewsItem` de fontes diferentes sobre o mesmo acontecimento (mockado com títulos/conteúdo semanticamente equivalentes), quando o pipeline de deduplicação roda, então eles são associados ao mesmo `NewsCluster`, não tratados como itens independentes.
3. Todo `NewsItem` criado tem `url_fonte_original` e `nome_fonte` preenchidos e não-nulos; a ausência desses campos deve impedir a criação do item (validação, não best-effort).
4. Dado um item bruto ingerido, quando o `SummarizationProvider` processa (mockado em teste), então `NewsItem.resumo_proprio` é preenchido com o resultado do provider — nunca com uma cópia do texto bruto original ingerido (teste deve comparar e garantir que não são idênticos/near-idênticos).
5. Dado um `NewsItem`/`NewsCluster` que atende ao critério de alta relevância (categoria sensível OU 3+ fontes no cluster, ambos parametrizáveis), quando o pipeline classifica, então `status_revisao=pendente` e o item NÃO é considerado publicado automaticamente; dado um item que não atende ao critério, então `status_revisao=nao_aplicavel` e o item pode ser tratado como publicado.
6. Após uma execução de ingestão, existe um registro consultável (log estruturado, métrica, ou modelo de execução — a critério do executor, documentar a escolha) com: quantidade de itens por fonte, quantidade de duplicatas agrupadas, e quantidade/custo de chamadas ao `SummarizationProvider`.
7. A lista de categorias sensíveis e o limiar de fontes do critério de alta relevância são configuráveis sem alteração de código (equivalente ao padrão já usado para `FeatureLimit` em `ARCHITECTURE.md`, ou via Django admin/settings — a critério do executor, desde que não fique hardcoded na lógica).

## Não-objetivos
- Não construir UI de consumo (feed) — isso é `feed-consumo-noticias.md`, execução futura.
- Não implementar Radar de tendências por localização.
- Não construir uma UI administrativa customizada para a fila de revisão — o Django admin nativo é suficiente nesta execução.
- Não adicionar fontes além das 4 listadas no `task-plan.md`.
- Não realizar a validação jurídica dos termos de uso das fontes (fica registrado como follow-up, não é tarefa de engenharia desta execução).
- Não implementar o pipeline completo de "revisão humana" com fluxo de aprovação multi-etapa — apenas o flag `status_revisao` e a exposição no admin para o operador decidir.

## Restrições técnicas
- **Performance:** N/A para carga definida (sem meta numérica ainda); a task de ingestão deve ser assíncrona (Celery), não bloquear requisições HTTP.
- **Segurança/privacidade:** nenhuma coleta de dado pessoal de usuário neste módulo (a ingestão lida com conteúdo público de fontes de notícia, não dados de usuários da plataforma).
- **Direitos autorais:** restrição mais crítica desta execução — ver critérios de aceite 3 e 4. Qualquer violação (resumo idêntico à fonte, ausência de atribuição) é tratada como bug bloqueante, não estético.
- **Dependências permitidas:** um parser de RSS (ex: `feedparser`), um cliente HTTP para chamadas ao provedor de LLM escolhido pelo executor (documentar a escolha e justificar), `celery` e `redis` (client Python), já previstos em `ARCHITECTURE.md`. Qualquer outra dependência nova deve ser justificada no `implementation-history.md` e sinalizada para o `reviewer`.
- **Estilo/convenções:** seguir as convenções já registradas em `implementation-history.md` do run `20260901-2135-cadastro-auth` (um app por bounded context, serializers/services separados por caso de uso quando aplicável, nomes de campo de domínio em português).

## Definição de pronto (Definition of Done)
- [ ] Critérios de aceite implementados
- [ ] Testes escritos e passando (tester)
- [ ] Revisão de código aprovada — obrigatória por `review-triggers.md` (direitos autorais/compliance, migração de schema, novas dependências externas)
- [ ] Documentação atualizada (documenter)
- [ ] `implementation-history.md` completo e coerente
