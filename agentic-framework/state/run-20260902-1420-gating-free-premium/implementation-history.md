<!--
CONTRACT: implementation-history
DONO: executor (cria e adiciona entradas) / tester, remediator, historian (adicionam entradas)
QUANDO É CRIADO: junto com a primeira ação do executor sobre o implementation-contract.md.
PARA ONDE VAI A INSTÂNCIA: agentic-framework/state/run-<run_id>/implementation-history.md
NATUREZA: append-only durante a execução — cada entrada é uma iteração, nunca se edita uma entrada anterior.
-->

# Implementation History — 20260902-1420-gating-free-premium

## Iteração 1 — 2026-09-02 — orchestrator agindo como executor (ferramentas de execução/subagente ainda indisponíveis)

**Quem implementou e por quê:** mesma situação registrada nos runs `20260902-0727-ingestao-noticias` (Iteração 5) e `20260902-1409-feed-consumo` — `Agent`/`Bash` de execução seguem indisponíveis. O usuário, ciente do risco (confirmado explicitamente via pergunta direta), pediu para continuar implementando todos os módulos do MVP, incluindo `assinatura-premium`. O `orchestrator` implementou este módulo via `Edit`/`Write`.

**O que foi feito:** app Django `gating/` — modelo `FeatureLimit` (chave/plano/valor, editável via admin), `FeatureLimitAlteracaoLog` (auditoria automática via `ModelAdmin.save_model`), camada de serviço (`has_feature`, `obter_limite_numerico`, `exigir_feature`, `plano_do_usuario`, `obter_valor`), seed de 7 recursos do BRD §7 via migration `RunPython`, e endpoint `GET /api/gating/meus-recursos/`.

### Estrutura de pastas criada

```
backend/gating/
  __init__.py
  apps.py                  # GatingConfig
  models.py                 # FeatureLimit, FeatureLimitAlteracaoLog
  services.py                # has_feature, obter_limite_numerico, exigir_feature, plano_do_usuario, obter_valor, RecursoGatedException
  admin.py                    # FeatureLimitAdmin (log automático), FeatureLimitAlteracaoLogAdmin (somente leitura)
  serializers.py
  views.py                    # MeusRecursosView
  urls.py
  migrations/
    __init__.py
    0001_initial.py           # CreateModel dos 2 modelos (escrito à mão — ver nota de risco abaixo)
    0002_seed_feature_limits.py  # RunPython, 7 recursos x 2 planos = 14 linhas
  tests/
    __init__.py
    test_sanity.py            # 11 testes
```

### Decisões técnicas (dentro da liberdade deixada pelo contrato)

1. **Fonte do "plano":** `User.papel` (`identidade/`), não um modelo `Subscription` (que ainda não existe) — já registrado como suposição no `task-plan.md`. `services.plano_do_usuario` é o ÚNICO lugar do código que faz essa tradução; qualquer módulo futuro (incluindo `assinatura-premium`, quando escrito) deve manter `User.papel` atualizado, não reimplementar a lógica de resolução de plano.
2. **`papel=admin` → plano `premium`** para fins de gating, conforme suposição registrada no `task-plan.md`.
3. **`valor` como string livre**, interpretado por `has_feature` (booleano: `"true"`/`"1"`/`"sim"`/`"yes"`, case-insensitive) ou `obter_limite_numerico` (inteiro, `-1` convencionado como ilimitado) — evita um schema por tipo de recurso, ao custo de não ter validação de tipo no nível do banco (aceitável para o MVP; o admin pode digitar um valor malformado, mas `obter_limite_numerico` já trata isso com fail-safe para o `default`, nunca lança exceção).
4. **Log de auditoria sem FK para `FeatureLimit`** (usa `feature_limit_chave`/`plano` como string, não `ForeignKey`) — decisão deliberada: o log deve sobreviver mesmo que a linha original de `FeatureLimit` seja apagada no futuro (histórico não pode desaparecer junto com o dado atual). Documentado na docstring do modelo.
5. **Seed via migration `RunPython`, não fixture/comando de management** — garante que qualquer ambiente novo (dev, CI, produção) já nasce com os 7 recursos parametrizáveis, sem passo manual extra. `get_or_create` (não `create`) para ser seguro rodar a migration mais de uma vez sem duplicar linhas.
6. **Migration `0001_initial.py` escrita À MÃO** (não gerada por `manage.py makemigrations`, que exigiria rodar código) — segui rigorosamente o formato já usado em `catalogo_noticias/migrations/0001_initial.py` como referência de estilo, incluindo `migrations.swappable_dependency(settings.AUTH_USER_MODEL)` para a dependência do `ForeignKey` para `User`. **Este é o maior risco desta iteração**: uma migration escrita à mão sem `makemigrations` real pode ter um erro sutil de sintaxe/formato que só um `migrate` de verdade revelaria — sinalizado explicitamente abaixo.

### Status dos critérios de aceite técnicos (implementation-contract.md)

| # | Critério | Status | Evidência |
|---|---|---|---|
| 1 | `has_feature` retorna `True` para premium com registro verdadeiro | ✅ Implementado | `test_has_feature_true_para_premium_com_registro_verdadeiro` |
| 2 | `has_feature` retorna `False` para free sem registro correspondente | ✅ Implementado | `test_has_feature_false_para_free_sem_registro_correspondente` |
| 3 | Fail-safe para chave desconhecida (nunca lança exceção, nunca libera) | ✅ Implementado | `test_has_feature_fail_safe_para_chave_desconhecida` |
| 4 | Usuário anônimo tratado como Free | ✅ Implementado | `test_has_feature_usuario_anonimo_tratado_como_free` |
| 5 | `papel=admin` equivalente a premium | ✅ Implementado | `test_admin_equivalente_a_premium` |
| 6 | Alteração via admin gera log de auditoria e reflete imediatamente | ✅ Implementado | `test_alteracao_via_admin_gera_log_de_auditoria` — **nota:** testado chamando `FeatureLimitAdmin.save_model` diretamente com um objeto de request simulado (não via cliente HTTP do admin autenticado como staff), ver "Lacunas de cobertura" abaixo |
| 7 | `exigir_feature` levanta/não levanta `RecursoGatedException` corretamente | ✅ Implementado | `test_exigir_feature_levanta_excecao_quando_nao_disponivel`, `test_exigir_feature_nao_levanta_quando_disponivel` |
| 8 | `GET /api/gating/meus-recursos/` funciona anônimo e autenticado | ✅ Implementado | `test_endpoint_meus_recursos_funciona_sem_autenticacao`, `test_endpoint_meus_recursos_para_usuario_premium` |
| 9 | `obter_limite_numerico` com default para valor malformado/ausente | ✅ Implementado | `test_obter_limite_numerico_convencao_ilimitado`, `test_obter_limite_numerico_valor_malformado_cai_no_default` |

**Resumo:** 9 de 9 critérios implementados, 11 testes de sanidade escritos.

### Lacunas de cobertura conhecidas (sinalizadas para o `tester`)

1. O teste do critério 6 (auditoria) chama `FeatureLimitAdmin.save_model` diretamente, sem passar pela URL real do admin (`/admin/gating/featurelimit/<id>/change/`) com um cliente autenticado como staff — não exercita permissões do admin nem o fluxo de formulário HTML real. Recomendo ao `tester` adicionar um teste via `Client` do Django autenticado como superuser acessando a URL do admin de verdade.
2. Não testei o comportamento de `FeatureLimitAlteracaoLogAdmin` recusando adicionar/editar/apagar (`has_add_permission`, etc.) — implementado, mas sem teste direto.

### Validação por execução: **NÃO REALIZADA nesta iteração**

Mesma limitação dos runs anteriores. **Risco adicional específico desta iteração:** a migration `0001_initial.py` foi escrita manualmente (não gerada por `makemigrations`), então além da suíte de testes, é ESPECIALMENTE importante rodar `manage.py makemigrations --check --dry-run` (ou simplesmente `migrate`) assim que possível para confirmar que o Django consegue interpretar o arquivo sem erro E que ele bate exatamente com o que `makemigrations` geraria a partir de `models.py` (evita drift entre o modelo real e a migration).

**Ação necessária antes de considerar este módulo pronto:**
```
cd C:\alex\brd_portal_noticias\backend && DJANGO_DB_ENGINE=sqlite3 .venv/Scripts/python.exe manage.py makemigrations --check --dry-run
cd C:\alex\brd_portal_noticias\backend && DJANGO_DB_ENGINE=sqlite3 .venv/Scripts/python.exe -m pytest -q
```

**Arquivos tocados:**
- `backend/gating/__init__.py`, `apps.py`, `models.py`, `services.py`, `admin.py`, `serializers.py`, `views.py`, `urls.py` (novos)
- `backend/gating/migrations/__init__.py`, `0001_initial.py`, `0002_seed_feature_limits.py` (novos)
- `backend/gating/tests/__init__.py`, `test_sanity.py` (novos)
- `backend/config/settings.py` (modificado — `INSTALLED_APPS += "gating"`)
- `backend/config/urls.py` (modificado — `path("api/gating/", include("gating.urls"))`)
