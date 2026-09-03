# Implementation History — 20260902-1620-frontend-b2b-metricas

## Iteração 1 — 2026-09-02 — orchestrator agindo como executor

**Lacuna de backend encontrada e corrigida:** `b2b/services.py` já tinha `adicionar_membro`/`remover_membro` (com `_exigir_admin_da_organizacao`), mas nada em `b2b/views.py`/`urls.py` os expunha. Adicionado `MembrosView` (`GET/POST/DELETE /api/b2b/membros/`) + `MembroOrganizacaoSerializer`. Ao escrever o `POST`, percebi que `services.adicionar_membro` deixa passar um `IntegrityError` não tratado se o usuário convidado já for membro de outra organização (`MembroOrganizacao.user` é `OneToOneField`) — mesma classe de bug já corrigida antes nesta sessão em `GoogleLoginView` (run `cadastro-auth`, e-mail duplicado). Adicionada checagem prévia (`MembroOrganizacao.objects.filter(user=...).exists()`) retornando 409 em vez de deixar estourar 500. 3 testes novos em `b2b/tests/test_sanity.py`.

Frontend:
- `lib/api.ts` — seções `b2b` e `metricas` (tipos + funções), conferidas campo-a-campo contra `b2b/serializers.py`/`views.py` e `metricas/services.py`/`views.py` antes de escrever as páginas.
- `frontend/app/empresa/page.tsx` — painel corporativo novo: resumo executivo, formulário de novo critério, itens monitorados agrupados por critério, lista de membros com convite/remoção (visibilidade de admin deduzida no cliente a partir do próprio e-mail logado batendo com um membro `papel_na_organizacao === "admin_organizacao"` na lista retornada pela API — não é uma fonte de autorização, só de UI; a autorização real continua 100% no backend via `_exigir_admin_da_organizacao`).
- `frontend/app/admin/metricas/page.tsx` — painel de métricas novo, com seletor de período e leitura de `usuario.papel` (contexto de auth) para bloquear a tela antes mesmo de chamar a API — o backend também rejeita com 403 quem não é admin, então a tela é defesa em profundidade, não a única barreira.
- `frontend/components/Header.tsx` — links "Empresa" (qualquer autenticado) e "Métricas" (só `papel === "admin"`).

**Status:** 5/5 critérios de aceite implementados. Validação: não realizada — mesma limitação de sessão (Bash/Agent/Browser bloqueados pelo classificador de segurança, sem recuperação até este ponto). Revisão manual: URLs conferidas em `config/urls.py` (`/api/b2b/`, `/api/metricas/`) e `b2b/urls.py`/`metricas/urls.py`; tipos TS conferidos contra os serializers/services reais.

**Arquivos:** `backend/b2b/views.py`, `backend/b2b/serializers.py`, `backend/b2b/urls.py`, `backend/b2b/tests/test_sanity.py` (modificados); `frontend/lib/api.ts`, `frontend/components/Header.tsx` (modificados); `frontend/app/empresa/page.tsx`, `frontend/app/admin/metricas/page.tsx` (novos).

**Marco:** com esta execução, todos os 13 módulos do BRD (identidade, catalogo_noticias/ingestão, feed, gating, assinatura, credenciamento, comunidade, moderação, radar, newsletter, landing, b2b, métricas) têm alguma superfície de frontend. Nenhuma parte do software — backend ou frontend — foi executada de fato desde o início da falha do classificador de segurança; esse é o maior risco residual do projeto e precisa ser resolvido antes de qualquer lançamento.
