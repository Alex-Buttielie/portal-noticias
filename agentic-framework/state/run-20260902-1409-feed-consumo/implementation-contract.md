# Implementation Contract — 20260902-1409-feed-consumo

## Metadados
- **run_id:** 20260902-1409-feed-consumo
- **Deriva de:** task-plan.md (20260902-1409-feed-consumo)
- **Versão do contrato:** 1

## O que deve ser construído
App Django `feed` (novo, dentro do projeto `backend/` já existente) expondo endpoints de leitura sobre `catalogo_noticias.NewsItem`/`NewsCluster`: feed paginado, filtro por categoria, busca por palavra-chave, e detalhe de acontecimento. Sem escrita — este app não cria/altera `NewsItem`/`NewsCluster`, apenas lê. Sinaliza `exibir_publicidade` a partir do `papel` do usuário (via `identidade.User`), quando autenticado.

## Áreas/arquivos esperados
- `backend/feed/` (novo app Django)
  - `serializers.py` — serializers de leitura para `NewsItem`/`NewsCluster` (payload de feed, de detalhe)
  - `views.py` — `FeedListView`, `NewsClusterDetailView` (ou nomes equivalentes)
  - `urls.py`
  - `tests/`
- `backend/config/settings.py` — registrar `feed` em `INSTALLED_APPS`; `backend/config/urls.py` — incluir as rotas do novo app
- `backend/requirements.txt` — só se alguma dependência nova for necessária (não esperado; DRF/filtros do próprio Django devem bastar)

## Interfaces afetadas
Novas interfaces (leitura apenas, nada existente é alterado):
- `GET /api/feed/` — lista paginada de `NewsCluster`/`NewsItem` publicáveis. Query params: `categoria` (filtro exato ou "todas"), `busca` (texto livre).
- `GET /api/feed/<id>/` — detalhe de um acontecimento (cluster ou item standalone): resumo, categoria, urgente, timestamps, lista de fontes (nome + URL de cada uma).
- Payload de resposta inclui `exibir_publicidade: bool`, calculado a partir de `request.user.papel` quando autenticado (`TokenAuthentication`/`SessionAuthentication` já configuradas em `identidade/`), ou `True` por padrão para requisição anônima.

## Critérios de aceite (técnicos, testáveis)
1. Dado que existem `NewsItem` com `status_revisao=nao_aplicavel` e `aprovado`, quando `GET /api/feed/` sem autenticação, então retorna 200 com esses itens, sem exigir token/sessão.
2. Dado um `NewsItem` com `status_revisao=pendente` ou `rejeitado`, quando `GET /api/feed/` ou `GET /api/feed/<id>/` (para esse item/cluster), então esse item NUNCA aparece na resposta (nem na lista, nem acessível por id direto — 404, não um vazamento parcial).
3. Dado `GET /api/feed/?categoria=<x>`, então só itens com `categoria=<x>` (publicáveis) são retornados.
4. Dado `GET /api/feed/?busca=<termo>`, então só itens cujo título OU resumo contém `<termo>` (case-insensitive) são retornados.
5. Dado um `NewsCluster` com múltiplos `NewsItem` (múltiplas fontes), quando `GET /api/feed/<id>/` para esse cluster, então a resposta lista TODAS as fontes associadas, cada uma com `nome_fonte` e `url_fonte_original`.
6. Dado um `NewsItem` standalone (sem cluster) publicável, quando `GET /api/feed/<id>/`, então a resposta funciona igualmente (uma "fonte" só), sem erro por ausência de cluster.
7. Dado um usuário autenticado com `papel=premium`, quando `GET /api/feed/`, então a resposta tem `exibir_publicidade=false`; dado um usuário `papel=free` ou requisição anônima, então `exibir_publicidade=true`.
8. `GET /api/feed/<id>/` para um id inexistente retorna 404, não 500.

## Não-objetivos
- Não implementar personalização/ordenação por interesse do usuário (fica em `gating-free-premium.md`).
- Não implementar a matriz completa de `FeatureLimit` (só o booleano de publicidade, que não depende dela).
- Não implementar busca full-text avançada (ranking, sinônimos) — `icontains` simples é suficiente para o MVP.
- Não construir frontend.
- Não alterar nada em `catalogo_noticias` ou `identidade` além de, se estritamente necessário, registrar o novo app em `INSTALLED_APPS`/`urls.py`.

## Restrições técnicas
- **Performance:** paginação obrigatória no feed (não retornar todos os itens de uma vez); página default e tamanho configuráveis via DRF `PageNumberPagination` ou equivalente.
- **Segurança/privacidade:** nenhuma exposição de dado de outro usuário — este módulo não lida com dados pessoais além do `papel` do requisitante (já autenticado via mecanismo existente). Itens `pendente`/`rejeitado` são estritamente privados à operação editorial (nunca vazam via este app).
- **Dependências permitidas:** nenhuma nova biblioteca externa esperada — usar Django ORM (`Q` objects) e DRF já instalados.
- **Estilo/convenções:** seguir convenções já registradas em `implementation-history.md` dos runs anteriores (app por bounded context, serializers por caso de uso, campos de domínio em português).

## Definição de pronto (Definition of Done)
- [ ] Critérios de aceite implementados
- [ ] Testes escritos e passando (tester) — **incluindo validação por execução real, não só leitura de código** (ver risco registrado no task-plan.md sobre indisponibilidade de ferramentas de execução)
- [ ] Revisão de código, se `review-triggers.md` exigir (avaliar: este módulo é só leitura, sem autenticação/pagamento/dados pessoais novos — improvável gatilho obrigatório, mas confirmar)
- [ ] Documentação atualizada (documenter)
- [ ] `implementation-history.md` completo e coerente
