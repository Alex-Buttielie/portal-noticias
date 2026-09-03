# Implementation Contract — 20260902-1506-comunidade-blog

Ver `task-plan.md` do mesmo run para escopo/critérios completos (formato consolidado).

## Áreas de arquivo
```
backend/comunidade/
  models.py    # Publicacao, Comentario, Seguidor
  services.py  # criar_rascunho, enviar_para_publicacao, publicar, comentar, seguir, deixar_de_seguir, denunciar (chama moderacao tardiamente)
  admin.py, serializers.py, views.py, urls.py, migrations/0001_initial.py, tests/
```

## Definição de pronto
Critérios de aceite do task-plan implementados; `implementation-history.md` com decisões e status de validação.
