# Task Plan — 20260902-1513-radar-tendencias-localizacao

Spec: `agentic-framework/specs/radar-tendencias-localizacao.md`. Formato conciso (ver runs anteriores desta leva).

## Objetivo
App `radar`: endpoint de tendências por localização (país/estado/cidade), evolução temporal simples, salvar/seguir localidade. Estende `catalogo_noticias.NewsItem` com campos `pais`/`estado`/`cidade` (migration `0002`, já aplicada nesta iteração).

## Critérios de aceite (técnicos)
1. `GET /api/radar/tendencias/?pais=X&estado=Y&cidade=Z` retorna categorias/assuntos em alta no recorte, ordenados por volume (contagem de `NewsCluster`/`NewsItem` publicáveis na janela), com `numero_noticias` e `numero_fontes`.
2. Recorte sem nenhum filtro retorna tendência nacional/global (sem quebrar).
3. `GET /api/radar/evolucao/?categoria=X&...localidade` retorna série temporal (contagem por dia) dos últimos N dias.
4. Resposta do radar SEMPRE inclui um campo de aviso deixando explícito que a métrica é volume de COBERTURA jornalística agrupada, não dado de busca real (BRD §11, restrição explícita).
5. Usuário autenticado consegue salvar/remover/listar localidades seguidas (idempotente).
6. Recurso "avançado" do radar (evolução temporal) é limitado no Free via `gating.services.has_feature` (chave `radar_avancado`) — Free vê só o retrato do momento (`tendencias`), Premium vê também `evolucao`.

## Suposições assumidas
- Localidade em `NewsItem` é preenchida best-effort (campos livres `pais`/`estado`/`cidade`, sem validação de lista fechada) — pipeline de ingestão real (fora desta execução) fica responsável por popular; sem dado, o item simplesmente não aparece em filtros de localidade específicos (não quebra, só fica de fora).
- Chave de gating `radar_avancado` adicionada ao seed de `gating` (nova migration de dados, `gating/migrations/0003_seed_radar_avancado.py`).
