# Implementation Contract — 20260902-1420-gating-free-premium

## Metadados
- **run_id:** 20260902-1420-gating-free-premium
- **Deriva de:** task-plan.md (20260902-1420-gating-free-premium)
- **Versão do contrato:** 1

## O que deve ser construído
App Django `gating` com modelo `FeatureLimit` (chave/plano/valor, editável via admin) e `FeatureLimitAlteracaoLog` (auditoria automática), uma camada de serviço (`has_feature`, `obter_limite_numerico`, `exigir_feature`) para qualquer módulo consumir, seed inicial de 7 recursos do BRD §7, e um endpoint de leitura para o usuário consultar seus recursos disponíveis.

## Áreas/arquivos esperados
- `backend/gating/` (novo app Django)
  - `models.py` — `FeatureLimit`, `FeatureLimitAlteracaoLog`
  - `services.py` — `has_feature`, `obter_limite_numerico`, `exigir_feature`, `RecursoGatedException`
  - `admin.py` — `FeatureLimitAdmin` (com log automático em `save_model`), `FeatureLimitAlteracaoLogAdmin` (somente leitura)
  - `serializers.py`, `views.py`, `urls.py` — endpoint `GET /api/gating/meus-recursos/`
  - `migrations/0001_initial.py`, `migrations/0002_seed_feature_limits.py` (RunPython)
  - `tests/`
- `backend/config/settings.py` — `INSTALLED_APPS += "gating"`; `backend/config/urls.py` — incluir rotas

## Interfaces afetadas
- Modelo `FeatureLimit(chave: str, plano: str["free"|"premium"], valor: str, descricao: str, atualizado_em, atualizado_por: FK User null)`, `unique_together=[("chave", "plano")]`.
- Modelo `FeatureLimitAlteracaoLog(feature_limit_chave, plano, valor_anterior, valor_novo, alterado_em, alterado_por: FK User null)` — append-only, sem edição/remoção via admin.
- `services.has_feature(user, chave: str) -> bool`
- `services.obter_limite_numerico(user, chave: str, default: int = 0) -> int` (convenção: `-1` = ilimitado)
- `services.exigir_feature(user, chave: str, mensagem: str | None = None) -> None` — levanta `RecursoGatedException` (DRF `APIException`, HTTP 403) se `has_feature` for `False`.
- `GET /api/gating/meus-recursos/` — retorna, para o usuário autenticado (ou anônimo), o plano resolvido e o valor de cada `FeatureLimit` conhecida.

## Critérios de aceite (técnicos, testáveis)
1. Dado um `FeatureLimit(chave="personalizacao_avancada", plano="premium", valor="true")` e um usuário `papel=premium`, quando `has_feature(user, "personalizacao_avancada")`, então retorna `True`.
2. Dado o mesmo `FeatureLimit`, mas um usuário `papel=free` (sem registro correspondente para `plano="free"`, ou registro `valor="false"`), quando `has_feature(user, "personalizacao_avancada")`, então retorna `False`.
3. Dado nenhum `FeatureLimit` cadastrado para uma chave, quando `has_feature(user, "chave_inexistente")` para qualquer usuário (inclusive premium), então retorna `False` (fail-safe — nunca lançar exceção, nunca liberar por omissão).
4. Dado um usuário anônimo (`AnonymousUser`), quando `has_feature(user, chave)`, então é tratado como plano `free`, sem lançar exceção.
5. Dado um usuário `papel=admin`, quando `has_feature(user, chave)` para uma chave configurada só para `plano="premium"`, então retorna `True` (admin equivalente a premium).
6. Dado um admin alterando um `FeatureLimit` pelo Django admin (`valor` de "false" para "true"), quando a alteração é salva, então um `FeatureLimitAlteracaoLog` é criado com `valor_anterior="false"`, `valor_novo="true"`, `alterado_por=<admin>`, e a MESMA leitura via `has_feature`/`obter_valor_feature` já reflete o novo valor na consulta seguinte (sem cache obsoleto).
7. `exigir_feature(user, chave)` não levanta exceção quando `has_feature` é `True`; levanta `RecursoGatedException` (403) quando `False`.
8. `GET /api/gating/meus-recursos/` retorna 200 tanto para requisição anônima quanto autenticada, com a lista de `FeatureLimit` resolvida para o plano do requisitante.
9. `obter_limite_numerico(user, chave, default=N)` retorna o valor numérico configurado quando existe e é um inteiro válido; retorna `default` quando não há registro ou o valor não é um inteiro válido (nunca lança exceção por dado malformado).

## Não-objetivos
- Não implementar nenhum módulo consumidor real (alertas, newsletter, radar, histórico) — só a camada central.
- Não implementar cache (Redis) para leitura de `FeatureLimit`.
- Não definir os valores finais de produto — o seed é um ponto de partida editável, não uma decisão de negócio travada em migration.
- Não construir frontend.

## Restrições técnicas
- **Performance:** N/A (sem meta definida; leitura direta ao banco aceitável no MVP).
- **Segurança/privacidade:** `FeatureLimitAlteracaoLog` não deve poder ser editado/apagado via admin (`has_change_permission`/`has_delete_permission` retornando `False`) — é um log de auditoria, não um dado operacional comum.
- **Dependências permitidas:** nenhuma nova biblioteca externa esperada.
- **Estilo/convenções:** mesmas já registradas nos runs anteriores.

## Definição de pronto (Definition of Done)
- [ ] Critérios de aceite implementados
- [ ] Testes escritos e passando (tester) — **incluindo validação por execução real** (ver risco de indisponibilidade de ferramentas já registrado no task-plan.md)
- [ ] Revisão de código, se `review-triggers.md` exigir (avaliar: nova migração de schema de banco é um gatilho obrigatório — revisão provavelmente necessária)
- [ ] Documentação atualizada (documenter)
- [ ] `implementation-history.md` completo e coerente
