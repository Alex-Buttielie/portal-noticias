# Implementation History — 20260902-1503-credenciamento-jornalistas

## Iteração 1 — 2026-09-02 — orchestrator agindo como executor (mesma limitação de ferramentas de execução de toda a sessão)

App `credenciamento/` criado: `SolicitacaoCredenciamento`, `PerfilJornalista`, serviço de domínio (`solicitar`, `decidir`, `suspender`, `reativar`, `pode_publicar`), admin com ações em massa de aprovar/reprovar, 3 endpoints (`solicitar/`, `minha-solicitacao/`, `solicitacoes/<id>/documento/` — download protegido, nunca servido via URL estática pública), migration manual, 5 testes de sanidade.

**Decisões:**
- `MEDIA_ROOT`/`MEDIA_URL` adicionados ao projeto (primeira feature com upload de arquivo) — `config/settings.py`.
- Documento NUNCA servido via `django.conf.urls.static` (que não tem controle de acesso) — só via `DocumentoView`, que checa dono ou admin.
- Credenciamento é um dado separado (`PerfilJornalista`), não um novo valor de `User.papel` — evita conflito com a semântica free/premium/admin já usada por `gating`.

**Status dos critérios de aceite:** 7/7 implementados (solicitar, fila+decisão, selo criado só na aprovação, consulta de status, documento protegido, suspensão, `pode_publicar`).

**Validação por execução:** não realizada (mesma limitação de sessão). Superfície nova de risco: upload de arquivo (`FileSystemStorage` padrão, sem dependência externa) — nunca exercitada.

**Arquivos:** `backend/credenciamento/` (novo, ver estrutura em `implementation-contract.md`); `backend/config/settings.py` (`INSTALLED_APPS`, `MEDIA_ROOT`/`MEDIA_URL`); `backend/config/urls.py`.
