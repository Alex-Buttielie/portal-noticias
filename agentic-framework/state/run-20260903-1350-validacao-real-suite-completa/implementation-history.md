# Implementation History — 20260903-1350-validacao-real-suite-completa

Solicitado por: usuário ("o que falta ser feito?"). Antes de responder de memória, rodei a suíte de testes completa do backend pela primeira vez desde que o ambiente de execução voltou a funcionar de verdade nesta sessão — só `catalogo_noticias/` tinha sido validado até então (turno anterior, 71 testes).

## Achados reais (nunca detectáveis sem execução — confirma o risco documentado durante toda a sessão)

**1. Migração de `comunidade` fora de sincronia com o modelo** — `manage.py makemigrations --check` acusou diferença cosmética na serialização do `CheckConstraint` de `Comentario` (ordem das cláusulas do `Q()` trocada em relação ao migration `0001_initial.py` escrito à mão durante a falha de ferramentas). Gerada `0002_remove_comentario_comentario_exatamente_um_alvo_and_more.py` (auto, via `makemigrations`) e aplicada — sem impacto de schema real, só sincroniza o estado que o Django rastreia.

**2. `gating`/`radar`/`newsletter`: testes de sanidade colidindo com dados de seed** — `gating/migrations/0002_seed_feature_limits.py` e `0003_seed_radar_avancado.py` populam linhas padrão (`publicidade`, `personalizacao_avancada`, `radar_avancado`, etc.) em `FeatureLimit`. Os testes de sanidade desses 3 apps tentavam `FeatureLimit.objects.create(...)` com as MESMAS chaves, violando a constraint UNIQUE `(chave, plano)` — nunca detectado porque nenhum desses testes tinha rodado de verdade antes. Corrigido trocando `.create()` por `.update_or_create()` em 16 pontos (`gating/tests/test_sanity.py`, `radar/tests/test_sanity.py`, `newsletter/tests/test_sanity.py`).

**3. `radar`: assertion de teste com case errado** — `test_tendencias_sem_filtro_agrega_por_categoria` checava `"cobertura jornalística"` (minúsculo) contra uma mensagem que deliberadamente usa `"COBERTURA"` maiúsculo para ênfase (`radar/services.py::AVISO_METODOLOGIA`). Bug do teste, não do serviço — corrigido o teste.

**4. `assinatura`: BUG REAL — grace period derrubava acesso Premium na hora** — `Subscription.STATUS_COM_ACESSO_PREMIUM` não incluía `inadimplente`, então `processar_pagamento_recusado` rebaixava `User.papel` para `free` IMEDIATAMENTE, contradizendo o próprio critério de aceite 4 ("acesso Premium NÃO é derrubado imediatamente" — grace period). Primeira correção (incluir `inadimplente` incondicionalmente) quebrou um SEGUNDO teste que prova o oposto: uma assinatura NOVA cujo primeiro pagamento já é recusado não deve conceder Premium (nunca esteve ativa). Corrigido com a distinção correta: `deveria_ter_acesso_premium` agora trata `inadimplente` separadamente, checando `self.inicio is not None` (só preenchido por um pagamento aprovado alguma vez) para decidir se há "algo a preservar" durante o grace period.

**5. `credenciamento`: BUG REAL — jornalista suspenso continuava podendo publicar** — `pode_publicar(user)` usava o acessor reverso `user.perfil_jornalista`, que fica CACHEADO na instância de `user` assim que qualquer código atribui o lado direto do `OneToOneField` (`PerfilJornalista.objects.update_or_create(user=..., ...)` dentro de `decidir()`), mesmo sem `user.perfil_jornalista` ter sido acessado explicitamente antes — comportamento built-in do Django para O2O. Uma suspensão posterior (via uma instância obtida por outra query) nunca invalidava esse cache, então `pode_publicar` continuava lendo o perfil pré-suspensão. Diagnosticado com um teste de depuração temporário (removido depois) que confirmou: o banco tinha `suspenso=True` corretamente, mas `usuario.perfil_jornalista.suspenso` retornava `False`. Corrigido trocando o acessor cacheável por uma query direta (`PerfilJornalista.objects.filter(user=user).first()`) — elimina o risco também em produção, não só no teste (qualquer código que toque o lado direto do O2O antes de uma suspensão no mesmo processo teria o mesmo problema).

## Validação

- `manage.py check`: sem problemas.
- `manage.py makemigrations --check --dry-run`: sem diferenças (após aplicar a migração do achado 1).
- `pytest -q` (suíte completa, todos os 13 apps): **190 passed, 0 failed** (7 warnings pré-existentes de `DeprecationWarning` do `feedparser`, não relacionados).
- Frontend: `npx tsc --noEmit` limpo; `npm run build` — build de produção completo, 21 rotas compiladas sem erro.

## Status
Todos os achados desta execução foram corrigidos e re-validados por execução real (não só leitura). Nenhum finding residual conhecido nesta passada.
