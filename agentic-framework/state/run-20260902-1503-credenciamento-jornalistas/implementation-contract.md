# Implementation Contract — 20260902-1503-credenciamento-jornalistas

Deriva de `task-plan.md` do mesmo run — ver lá para escopo/critérios completos (formato consolidado nesta leva de execuções, ver nota no task-plan).

## Áreas de arquivo
```
backend/credenciamento/
  models.py    # SolicitacaoCredenciamento, PerfilJornalista
  services.py  # solicitar, decidir (aprovar/reprovar/pedir_info), suspender, pode_publicar
  admin.py, serializers.py, views.py, urls.py, migrations/0001_initial.py, tests/
```

## Interfaces
- `SolicitacaoCredenciamento(user FK, cidade, uf, foto opcional, mini_bio, dados_profissionais, documento FileField, status[pendente|aprovado|reprovado|info_solicitada], criado_em, decidido_em, decidido_por FK, motivo_decisao)`
- `PerfilJornalista(user FK OneToOne, selo_ativo bool, credenciado_em, suspenso bool, motivo_suspensao)`
- `services.pode_publicar(user) -> bool` — função pública que `comunidade-blog` vai consumir.
- `POST /api/credenciamento/solicitar/`, `GET /api/credenciamento/minha-solicitacao/`

## Definição de pronto
Critérios de aceite do task-plan implementados; `implementation-history.md` registrando decisões e sinalizando validação por execução pendente (mesma limitação de sessão).
