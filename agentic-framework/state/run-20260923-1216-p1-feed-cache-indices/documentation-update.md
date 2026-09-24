# Documentation Update — 20260923-1216-p1-feed-cache-indices

## Docs verificados

- `README.md` — grep por `exibir_publicidade|feed|cache|FEED_|GATING_|gating|publicidade|premium|endpoint|status`: nenhuma afirmação contrária ao novo comportamento. README nunca documentou tabela de endpoints do feed nem payload com `exibir_publicidade`; seção gating listava só `meus-recursos/`. Linha 156-equivalente não existe no README (o "feed sem cache com N+1" está em `ARCHITECTURE.md:156`, contexto histórico — ver abaixo).
- `backend/.env.example` — as 3 settings novas JÁ presentes (`FEED_JANELA_HORAS=72`, `FEED_CACHE_TTL_SEGUNDOS=45`, `GATING_CACHE_TTL_SEGUNDOS=45`, linhas 134-139) com defaults e motivo (staleness ~45s aceitável, ISR 60s). Nenhuma alteração necessária.
- `ARCHITECTURE.md` §7/§9 — §9.3 tabela Performance já afirma cache Redis de aplicação (compatível, agora verdade também para o feed). §7 sem menção a feed/cache. Linha 156 ("feed sem cache com N+1") é citação histórica dos achados de `ANALISE_CUSTO_PERFORMANCE.md`, não afirmação de estado atual — mantida.
- `infra/DEPLOY.md` — seção "Deploy de uma nova versão" sem nota de janela fria; `docker-entrypoint.sh` roda `migrate` automático (linhas 98-100). Adicionada nota.
- `backend/gating/urls.py`, `views.py` — confirmado `GET /api/gating/status/` público retornando `{"premium_ativo": ...}` (fonte do frontend p/ ads).
- Migração `0011_newsitem_busca_trgm.py` docstring — confirma `CREATE INDEX` não-CONCURRENTLY com bloqueio de escrita; mesma justificativa usada na nota do DEPLOY.md.

## Alterações aplicadas (arquivo:linha, antes→depois)

1. `README.md:93-94` — tabela gating: adicionada linha `GET /api/gating/status/` (flag `premium_ativo`, fonte do frontend p/ publicidade; payloads do feed não expõem mais `exibir_publicidade`; cache curto `GATING_CACHE_TTL_SEGUNDOS` 45s). Antes: só `meus-recursos/`.
2. `ARCHITECTURE.md:43` — entidade `NewsCluster`: antes "id, acontecimento, lista de NewsItem relacionados, categoria dominante" → depois + "`numero_fontes_distintas` (coluna denormalizada, mantida pela ingestão/admin; evita COUNT por cluster no caminho quente do feed)".
3. `infra/DEPLOY.md` (~linha 140, após bloco CI) — adicionado blockquote de 3 linhas: migração `0011_newsitem_busca_trgm` cria índice GIN não-CONCURRENTLY, bloqueia escrita em `catalogo_noticias_newsitem`; rodar migrate em horário de baixo tráfego.

## Não-alterados + motivo

- `backend/.env.example` — 3 settings já presentes com defaults e motivo (linhas 134-139, adicionadas pelo executor). Nada a fazer.
- `ARCHITECTURE.md:156` ("feed sem cache com N+1") — citação histórica de achados da análise de 2026-09-22, não descrição do estado atual. Alterar reescreveria história; mantido.
- `README.md` demais seções — nenhuma menção a `exibir_publicidade`, janela do feed ou endpoints do feed; nada desatualizado para corrigir.
- Tabela `§9.3 Performance` (ARCHITECTURE.md:132) — já afirma cache Redis de aplicação; agora inclui o feed de fato. Sem contradição, sem edição.
- `ANALISE_CUSTO_PERFORMANCE.md`, specs (`feed-consumo-noticias.md`, `gating-free-premium.md`) — backlog vivo / requisitos, não documentação de estado; fora do escopo pedido.
