# Implementation History — 20260902-1513-radar-tendencias-localizacao

## Iteração 1 — 2026-09-02 — orchestrator agindo como executor

Adicionados `pais`/`estado`/`cidade` a `catalogo_noticias.NewsItem` (migration `0002_newsitem_localidade.py`, campos opcionais, não quebra itens existentes). App `radar/`: `LocalidadeSalva`, agregação de tendências (`Count`/`TruncDate` do ORM, sem trazer dados para Python), aviso de metodologia sempre presente na resposta, gating do recurso avançado (`radar_avancado`, seed via `gating/migrations/0003_seed_radar_avancado.py`). 3 endpoints, 5 testes.

**Status:** 6/6 critérios implementados. Validação: não realizada (mesma limitação de sessão).

**Arquivos:** `backend/radar/` (novo); `backend/catalogo_noticias/models.py` + `migrations/0002_newsitem_localidade.py`; `backend/gating/migrations/0003_seed_radar_avancado.py`; `backend/config/settings.py`, `urls.py`.
