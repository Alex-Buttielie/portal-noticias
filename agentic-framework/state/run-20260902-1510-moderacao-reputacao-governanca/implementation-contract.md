# Implementation Contract — 20260902-1510-moderacao-reputacao-governanca

Ver `task-plan.md` do mesmo run.

## Áreas de arquivo
```
backend/moderacao/
  models.py    # Denuncia (GenericForeignKey), AcaoModeracao, RecursoModeracao, Reputacao, ReputacaoEventoLog, PaginaEditorial
  services.py  # denunciar, resolver_denuncia, aplicar_acao, criar_recurso, registrar_evento_reputacao, obter_reputacao
  admin.py, serializers.py, views.py, urls.py, migrations/0001_initial.py, tests/
```
Depende de `django.contrib.contenttypes` (já instalado por padrão do Django, `django.contrib.contenttypes` precisa estar em `INSTALLED_APPS` — confirmar/adicionar).
