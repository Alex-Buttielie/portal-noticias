<!--
CONTRACT: implementation-history
DONO: executor (cria e adiciona entradas) / tester, remediator, historian (adicionam entradas)
QUANDO É CRIADO: junto com a primeira ação do executor sobre o implementation-contract.md.
PARA ONDE VAI A INSTÂNCIA: agentic-framework/state/run-<run_id>/implementation-history.md
NATUREZA: append-only durante a execução — cada entrada é uma iteração, nunca se edita uma entrada anterior.
-->

# Implementation History — 20260902-1409-feed-consumo

## Iteração 1 — 2026-09-02 — orchestrator agindo como executor (ferramentas de execução/subagente indisponíveis)

**Quem implementou e por quê:** normalmente esta etapa seria do `executor` via `Agent`, mas o classificador de segurança que autoriza `Agent`/`Bash` executando código permanece indisponível nesta sessão desde a execução anterior (`run-20260902-0727-ingestao-noticias`, Iteração 5 — ver esse arquivo para o histórico completo de tentativas). O usuário pediu explicitamente para continuar a implementação até ter um MVP ("continue a implementação do meu software até que eu tenha um MPV para iniciar"). O `orchestrator` implementou este módulo diretamente via `Edit`/`Write`, com o mesmo rigor de leitura cuidadosa já demonstrado na correção anterior.

**O que foi feito:** app Django `feed/` (novo, sem modelo próprio — só leitura de `catalogo_noticias.NewsItem`/`NewsCluster`) implementando os 8 critérios de aceite do `implementation-contract.md`: feed público paginado, filtro por categoria, busca por palavra-chave, detalhe de acontecimento (cluster ou item standalone) com todas as fontes, e sinalização de `exibir_publicidade` a partir do `papel` do usuário.

### Estrutura de pastas criada

```
backend/feed/
  __init__.py
  apps.py                # FeedConfig
  services.py             # itens_publicaveis, construir_feed_entries, detalhe_cluster, detalhe_item, exibir_publicidade
  serializers.py           # FeedEntrySerializer, FonteDetalheSerializer, FeedDetalheSerializer
  views.py                 # FeedListView, ClusterDetailView, ItemDetailView
  urls.py
  tests/
    __init__.py
    test_sanity.py         # 8 testes mínimos de sanidade
```

Nenhum modelo novo, nenhuma migration — este app é estritamente de leitura sobre os modelos já existentes de `catalogo_noticias`.

### Decisões técnicas (dentro da liberdade deixada pelo contrato)

1. **Esquema de identificação de detalhe:** o contrato descrevia genericamente `GET /api/feed/<id>/`, mas um `NewsCluster.id` e um `NewsItem.id` standalone podem colidir (tabelas diferentes, ambas auto-incrementais a partir de 1). Implementei duas rotas de detalhe explícitas — `GET /api/feed/cluster/<id>/` e `GET /api/feed/item/<id>/` — e cada entrada do feed já informa `tipo` (`"cluster"` ou `"item"`) + `id`, para o consumidor da API montar a URL correta sem ambiguidade. Documentado aqui por ser uma interpretação, não uma cópia literal do contrato.
2. **Construção do feed a partir de `NewsItem`, não de `NewsCluster`:** os filtros de categoria/busca (critérios 3 e 4) operam sobre campos do item (`categoria`, `titulo`, `resumo_proprio`) — cada item pode ter seu próprio resumo desde a correção estrutural do run de ingestão (Iteração 5). Por isso, `services.itens_publicaveis()` filtra `NewsItem` primeiro; `services.construir_feed_entries()` agrupa o resultado em memória (por `cluster_id`, ou por `id` quando standalone), escolhendo como representante da entrada de cluster o item mais recente do subconjunto FILTRADO que pertence àquele cluster. Isso significa que, com um termo de busca, o representante mostrado é sempre um item que de fato bate com a busca — não um item aleatório do cluster.
3. **`numero_fontes` na listagem reflete o TOTAL do cluster** (via `NewsCluster.numero_fontes_distintas`, já existente), não só a contagem de itens que passaram no filtro — decisão de UX (mostrar "3 fontes" mesmo que a busca só tenha batido em 1), ao custo de uma query extra por cluster distinto na página (aceitável na escala do MVP; não é um módulo de alto volume ainda).
4. **Paginação:** `PageNumberPagination` padrão do DRF, `page_size=20`, `page_size_query_param="page_size"`, `max_page_size=100` — instanciada manualmente dentro de `FeedListView.get()` (padrão válido para `APIView` puro, sem usar `GenericAPIView`/`ListAPIView`, para manter a view simples e poder injetar `exibir_publicidade` no payload final sem lutar contra a estrutura de uma view genérica).
5. **`AllowAny` explícito em todas as views:** o `DEFAULT_PERMISSION_CLASSES` global do projeto é `IsAuthenticated` (definido na correção de segurança do run `20260901-2135-cadastro-auth`, Finding 5) — as 3 views deste módulo (`FeedListView`, `ClusterDetailView`, `ItemDetailView`) sobrescrevem isso explicitamente, conforme critério de aceite 1/6 (feed público, sem exigir login).
6. **`exibir_publicidade`** calculado por uma função pura (`services.exibir_publicidade(user)`), reaproveitada nas 3 views — evita duplicar a regra "premium autenticado → sem anúncio" em três lugares.

### Status dos critérios de aceite técnicos (implementation-contract.md)

| # | Critério | Status | Evidência |
|---|---|---|---|
| 1 | Feed público sem autenticação obrigatória | ✅ Implementado | `FeedListView` com `permission_classes=[AllowAny]`; `test_feed_publico_sem_autenticacao_retorna_200` |
| 2 | Itens `pendente`/`rejeitado` nunca aparecem (lista nem detalhe) | ✅ Implementado | `services.STATUS_PUBLICAVEIS` é a única fonte de verdade usada por `itens_publicaveis`/`detalhe_cluster`/`detalhe_item`; `test_item_pendente_nunca_aparece_no_feed`, `test_item_pendente_no_detalhe_retorna_404` |
| 3 | Filtro por categoria | ✅ Implementado | `itens_publicaveis(categoria=...)`; `test_filtro_por_categoria` |
| 4 | Busca por palavra-chave (título OU resumo) | ✅ Implementado | `Q(titulo__icontains=...) | Q(resumo_proprio__icontains=...)`; `test_busca_por_palavra_chave` |
| 5 | Detalhe de cluster lista todas as fontes | ✅ Implementado | `services.detalhe_cluster`; `test_detalhe_de_cluster_lista_todas_as_fontes` |
| 6 | Detalhe de item standalone funciona igual | ✅ Implementado | `services.detalhe_item`; `test_detalhe_de_item_standalone_funciona` (caminho feliz), `test_item_pendente_no_detalhe_retorna_404` (caminho de erro) |
| 7 | `exibir_publicidade` por papel do usuário | ✅ Implementado | `services.exibir_publicidade`; `test_usuario_premium_nao_ve_publicidade`, `test_visitante_ve_publicidade` |
| 8 | Id inexistente → 404, não 500 | ✅ Implementado | `detalhe_cluster`/`detalhe_item` retornam `None` em `DoesNotExist`, tratado pela view como 404 antes de qualquer serialização; `test_id_inexistente_retorna_404_nos_dois_endpoints_de_detalhe` (id genuinamente inexistente, nos dois endpoints) + `test_item_pendente_no_detalhe_retorna_404` (existe mas não publicável, mesmo tratamento)

**Resumo:** 8 de 8 critérios implementados e cobertos por teste de sanidade (10 testes ao todo, após fechar as 2 lacunas de cobertura inicialmente sinalizadas nesta mesma iteração).

### Validação por execução: **NÃO REALIZADA nesta iteração**

Múltiplas tentativas de rodar `manage.py check`, migrations (não deveriam ser necessárias — nenhum modelo novo) e a suíte de testes falharam com o mesmo erro de indisponibilidade do classificador de execução já documentado no run anterior. Todo o código acima foi escrito e revisado por leitura cuidadosa (conferindo nomes de campo reais em `catalogo_noticias/models.py` e `identidade/models.py`, o padrão de autenticação de teste já usado em `identidade/tests/`, e o comportamento conhecido do `django.core.paginator.Paginator` com listas Python simples em vez de querysets — especificamente confirmando que `Paginator` distingue `list.count(x)` de `QuerySet.count()` via `method_has_no_args`, para não cair num bug de assinatura), mas **isso não substitui rodar a suíte de verdade**.

**Ação necessária antes de considerar este módulo pronto:** assim que ferramentas de execução estiverem disponíveis, rodar:
```
cd C:\alex\brd_portal_noticias\backend && DJANGO_DB_ENGINE=sqlite3 .venv/Scripts/python.exe -m pytest -q
```
e confirmar que os 8 testes de sanidade deste módulo passam, junto com a suíte pré-existente (que também está com validação pendente desde o run anterior).

**Arquivos tocados:**
- `backend/feed/__init__.py`, `apps.py`, `services.py`, `serializers.py`, `views.py`, `urls.py` (novos)
- `backend/feed/tests/__init__.py`, `test_sanity.py` (novos)
- `backend/config/settings.py` (modificado — `INSTALLED_APPS += "feed"`)
- `backend/config/urls.py` (modificado — `path("api/feed/", include("feed.urls"))`)
