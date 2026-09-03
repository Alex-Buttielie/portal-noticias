# Implementation History — 20260902-1519-b2b-corporativo

## Iteração 1 — 2026-09-02 — orchestrator agindo como executor

App `b2b/`: `Organizacao` (reaproveita `assinatura.Subscription` via FK, não duplica cobrança), `MembroOrganizacao` (1 organização por usuário, papel admin/membro), `CriterioMonitoramento`, agregação de itens monitorados via busca textual sobre `catalogo_noticias.NewsItem` sempre escopada à organização. 3 endpoints, todos derivando a organização de `services.organizacao_do_usuario(request.user)` — nunca de um id vindo da URL (garantia estrutural do isolamento, critério de aceite 5).

**Bug real encontrado e corrigido durante a escrita dos testes:** `adicionar_membro` original exigia um admin JÁ EXISTENTE para adicionar o primeiro membro — impossível de bootstrapar uma organização nova. Adicionada `criar_organizacao_com_admin` (operação privilegiada de onboarding comercial, sem passar pela checagem de permissão) para resolver o caso de criação inicial. Mesma classe de erro que apareceu no módulo `assinatura` (Iteração 5) — encontrado por escrever o teste antes de assumir que a função "obviamente" funcionava.

**Status:** 6/6 critérios implementados. Validação: não realizada.

**Arquivos:** `backend/b2b/` (novo); `backend/config/settings.py`, `urls.py`.
