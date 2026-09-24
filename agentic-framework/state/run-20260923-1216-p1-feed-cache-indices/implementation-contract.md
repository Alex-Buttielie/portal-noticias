# Implementation Contract — 20260923-1216-p1-feed-cache-indices

## Metadados
- **run_id:** 20260923-1216-p1-feed-cache-indices
- **Deriva de:** task-plan.md (20260923-1216-p1-feed-cache-indices)
- **Versão do contrato:** 1

## O que deve ser construído

### Parte A — fim do N+1 e da materialização total (P1-1)
1. **Denormalizar `numero_fontes_distintas`**: nova coluna em
   `NewsCluster` (`backend/catalogo_noticias/models.py`), com migração
   que cria a coluna **e faz backfill** (COUNT DISTINCT de `nome_fonte`
   por cluster existente). Atualizar todos os caminhos de escrita em
   `backend/catalogo_noticias/services/ingestao.py` (`_persistir_grupo`,
   `_persistir_grupo_mesclado` e o ponto que hoje lê a property,
   ~linha 523). Trocar o uso no caminho quente
   (`backend/feed/services.py:71`) para a coluna. Decidir e justificar:
   remover a property `numero_fontes_distintas` (evita regressão
   acidental) ou mantê-la fora do caminho quente.
2. **Corte no SQL + `.only()`**: `itens_publicaveis()` (e equivalentes
   em seções/destaques/radar regional) passa a filtrar janela de 72h
   (configurável, default em settings) e carregar via `.only()` apenas
   os campos usados no caminho de lista (id, título, resumo, metadados,
   localidade, FKs, a nova coluna). Views de detalhe
   (`detalhe_cluster`, `detalhe_item`) mantêm fetch completo
   (`conteudo_completo` vai no payload delas). Garantir que
   `equilibrar_por_categoria` e `aplicar_regras_curadoria` não toquem
   campos deferred (ou incluí-los no `.only()`).
3. **Cache de listagens públicas** (TTL 30–60s, configurável): chave por
   querystring normalizada (categoria, busca, page, page_size) para
   `FeedListView`, seções, destaques, urgentes, mais-lidas. Backend de
   cache já configurado (Redis prod / locmem dev) — usar `django.core.cache`.
4. **Mover `exibir_publicidade`**: remover o campo de todos os payloads
   do feed (grep `exibir_publicidade` no backend — views
   `FeedListView`, detalhe de cluster/item, seções/destaques). No
   frontend, grepar todos os usos do campo vindo do feed e migrar para
   o endpoint dedicado (`GET /api/gating/status`, já consumido em
   `lib/premium.ts`). Manter o campo no microservice_client apenas se
   ele espelhar o contrato local (se o microserviço estiver desligado
   por default, não quebrar nada).
5. **Cache curto de configuração**: `ConfiguracaoSistema` (flag premium
   em `gating/services.py:27`) e limites de `MeusRecursosView`
   (`gating/views.py:21-35`) com TTL curto (mesma ordem do cache do
   feed), consolidando as ~3N queries.

### Parte B — índices (P1-2)
6. Migração em `catalogo_noticias` com: índice composto
   `(status_revisao, -timestamp_ingestao)` em `NewsItem`; índices em
   `categoria`, `urgente`, `estado`/`pais`/`cidade` (ou o recorte que o
   executor confirmar via filtros reais do código). Extensão `pg_trgm`
   + índice GIN trigram sobre os campos da busca — **isolados em
   migração com guarda por `connection.vendor`** (`CREATE EXTENSION`
   só em postgresql; no sqlite a migração vira no-op sem falhar).
   Sem reescrever as queries de busca (o LIKE existente usa o índice
   GIN trigram).

## Áreas/arquivos esperados
- `backend/catalogo_noticias/models.py` + `migrations/`
- `backend/catalogo_noticias/services/ingestao.py`
- `backend/feed/services.py`, `backend/feed/views.py`, `backend/feed/busca.py` (só se necessário)
- `backend/feed/microservice_client.py` (só se espelhar `exibir_publicidade`)
- `backend/gating/services.py`, `backend/gating/views.py`
- `backend/config/settings.py` (novas settings: TTL cache feed, janela 72h — nomes a critério do executor, documentados)
- `frontend/`: arquivos que consumirem `exibir_publicidade` do feed (grep exaustivo)
- `backend/*/tests/` (novos testes de queries/cache/backfill)
- Qualquer mudança fora desta lista deve ser justificada em `implementation-history.md`.

## Interfaces afetadas
- **API pública (breaking controlado)**: `exibir_publicidade` sai dos payloads do feed (`/api/feed/`, detalhe cluster/item, seções/destaques). Substituto oficial: `GET /api/gating/status` (existente, sem mudança). Frontend atualizado na mesma run.
- **Schema**: nova coluna `NewsCluster.numero_fontes_distintas` + índices (migrações reversíveis; backfill idempotente).
- `GET /api/metricas/painel/`, admin, ingestão: sem mudança de contrato.

## Critérios de aceite (técnicos, testáveis)
1. Dado um cluster com N fontes distintas, quando persistido/mesclado pela ingestão, então a coluna vale N (teste dedicado cobrindo criação e mesclagem).
2. Dado backfill em banco com clusters pré-existentes, quando rodada a migração, então a coluna reflete o COUNT DISTINCT real (teste de migração ou teste com dados criados antes do preenchimento).
3. Dada página do feed com K clusters, quando `GET /api/feed/`, então o número de queries é limitado e **não cresce com K** (`assertNumQueries` com teto fixo; sem COUNT por cluster).
4. Dado `conteudo_bruto`/`conteudo_completo` populados, quando `GET /api/feed/`, então essas colunas não são selecionadas no SQL das listagens (verificável via `assertNumQueries` + Inspection de queries, ou `connection.queries` sem esses campos).
5. Dados dois `GET /api/feed/` idênticos em sequência, quando o segundo ocorre dentro do TTL, então ele não emite queries de listagem (cache efetivo; teste com cache locmem).
6. Dado qualquer endpoint de feed, quando inspecionado o JSON, então **não** contém `exibir_publicidade`; e o frontend compila (`tsc --noEmit`) sem referências ao campo vindo do feed.
7. `migrate` aplica limpo em sqlite (teste local) e a migração `pg_trgm`/GIN está presente e correta para Postgres (validade sai no CI; o executor deve ao menos validar o SQL gerado via `sqlmigrate` se possível).
8. Suíte completa `pytest` passa com o gate de cobertura do CI.

## Não-objetivos
- `EventoBusca` async, paginação da comunidade, FTS dedicado, cache de borda/Cloudflare, ETag nos RSS, runs B/C.
- Separar preço in/out de LLM, trocar provedor, qualquer item P2.
- Nova dependência; mudança em regras de curadoria/moderação/gating (além do cache de leitura).

## Restrições técnicas
- **Performance:** teto de queries do feed documentado no teste; TTL e janela configuráveis via settings/env.
- **Segurança/privacidade:** nenhum dado novo exposto; cache só em endpoints públicos (`AllowAny`) sem variar por usuário após a remoção de `exibir_publicidade`.
- **Dependências permitidas:** nenhuma nova.
- **Estilo/convenções:** comentários em português no padrão do projeto; settings novas com prefixo do módulo e documentadas em `.env.example`.
- **Revisão:** OBRIGATÓRIA (`review-triggers.md`: migração de schema + mudança em API pública). Diff esperado pode passar de 300 linhas — aceitável nesta run, com reviewer dedicado.

## Definição de pronto (Definition of Done)
- [ ] Critérios de aceite implementados
- [ ] Testes escritos e passando (tester)
- [ ] Revisão de código aprovada (reviewer — obrigatório)
- [ ] Documentação atualizada (documenter)
- [ ] `implementation-history.md` completo e coerente
