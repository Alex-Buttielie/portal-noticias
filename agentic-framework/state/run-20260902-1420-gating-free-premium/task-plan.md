# Task Plan — 20260902-1420-gating-free-premium

## Metadados
- **run_id:** 20260902-1420-gating-free-premium
- **Data de abertura:** 2026-09-02
- **Solicitado por:** usuário ("continue a implementação do meu software até que eu tenha um MVP para iniciar")
- **Spec de origem:** `agentic-framework/specs/gating-free-premium.md`

## Objetivo
Ao final desta execução, deve existir uma camada central e parametrizável (`FeatureLimit`, editável via Django admin com auditoria) que qualquer módulo do sistema possa consultar para saber se um usuário tem acesso a um recurso Premium — sem que nenhum módulo precise fazer `if papel == "premium"` espalhado pelo código.

## Escopo

### Dentro do escopo
- App Django `gating/` (novo): modelo `FeatureLimit` (chave, plano, valor) e `FeatureLimitAlteracaoLog` (auditoria — quem, quando, valor anterior/novo).
- Camada de serviço (`has_feature`, `obter_limite_numerico`, `exigir_feature`) — ponto único de verificação, reutilizável por qualquer app futuro.
- Django admin com log automático de alteração (requisito 4 da spec).
- Seed de dados inicial (migration `RunPython`) com os 7 recursos citados na seção 7 do BRD, com valores de referência — claramente editáveis, não a decisão final de produto (a própria spec marca isso como "fora de escopo"/questão em aberto).
- Endpoint de leitura `GET /api/gating/meus-recursos/` — para o frontend (futuro) e para o próprio usuário saberem o que têm disponível no plano atual, sem adivinhar (user story 2 da spec).
- Testes cobrindo os critérios de aceite abaixo.

### Fora do escopo (explicitamente)
- Definição final dos valores de cada limite (já marcado como fora de escopo pela própria spec — os valores desta execução são um ponto de partida editável).
- Cupons e promoções.
- Integração de fato com os módulos que vão CONSUMIR o gating (alertas, newsletter, radar avançado, histórico) — esses módulos ainda não existem; esta execução só entrega a camada central e a documentação de como usá-la.
- Cache/otimização de performance (ex: Redis) para leituras de `FeatureLimit` — leitura direta do banco é aceitável na escala do MVP; requisito não-funcional "sem exigir logout/relogin" já é satisfeito por padrão (nenhum cache em memória por sessão está sendo introduzido).

## Suposições assumidas
- **Fonte do "plano" do usuário:** a spec diz depender de `assinatura-premium.md`, que ainda não foi implementada nesta sessão. Uso `User.papel` (`free`/`premium`/`admin`, já existente em `identidade/`) como a fonte de verdade do plano — o mesmo campo que o módulo `feed` já usa para `exibir_publicidade`. **Motivo:** o campo já existe e é exatamente o que a assinatura vai manter atualizado quando for implementada (ativar assinatura → `papel=premium`; cancelar/expirar → `papel=free`) — não é uma gambiarra, é a mesma fonte de dado que a spec de assinatura vai popular, só que a assinatura em si (cobrança, ciclo de vida) ainda não existe.
- **`papel=admin` mapeado para o plano "premium"** nas checagens de gating — administradores não devem ser limitados pelas mesmas regras de um consumidor final. **Motivo:** decisão operacional razoável, não estava explícita na spec, mas evita um admin ficar bloqueado por um gate pensado para usuários finais.
- **Valores de referência do seed** (não são a decisão final de produto, ver "Fora de escopo" da própria spec): publicidade (free=sim/premium=não), personalização avançada (free=não/premium=sim), alertas personalizados (free=limite 3/premium=ilimitado), resumo personalizado (free=não/premium=sim), newsletter personalizada (free=não/premium=sim), histórico avançado (free=não/premium=sim), distribuição personalizada (free=não/premium=sim). Recursos avançados do Radar (citado no BRD §7) NÃO foi incluído no seed — o módulo de Radar ainda não existe no roadmap desta sessão, seed antecipado seria dado morto sem consumidor.

## Restrições
- Stack obrigatória: Python/Django + DRF, PostgreSQL — mesmo projeto/backend.
- Auditoria obrigatória (BRD §17) de qualquer alteração de `FeatureLimit`.
- Fail-safe: ausência de configuração para uma chave/plano deve resultar em "recurso indisponível" (nunca liberar um recurso premium por omissão de dado).

## Divisão de trabalho
| Etapa | Agente responsável | Entrada esperada | Saída esperada |
|---|---|---|---|
| 1 | executor | implementation-contract.md | código + implementation-history.md |
| 2 | tester | implementation-contract.md | veredito passed/failed/blocked |
| 3 | reviewer (ver review-triggers.md) | diff do executor | code-review-contract.md |
| 4 | remediator (se necessário) | code-review-contract.md | correções + revalidação |
| 5 | documenter | implementation-history.md | documentation-update.md + docs atualizadas |
| 6 | historian | todos os artefatos acima | report.md + entrada em HISTORY.md |

## Critérios de aceite (nível de negócio/produto)
1. Um admin consegue alterar o valor de um `FeatureLimit` pelo Django admin, e essa mudança é imediatamente refletida para qualquer usuário (sem deploy, sem logout/login).
2. Toda alteração de `FeatureLimit` fica registrada com quem alterou, quando, e os valores antes/depois.
3. `has_feature(user, chave)` retorna corretamente `True`/`False` conforme o plano do usuário (via `papel`) e o valor configurado — inclusive para usuário anônimo (tratado como Free).
4. Ausência de configuração para uma chave/plano nunca libera acesso por omissão (fail-safe).
5. Um usuário consegue consultar, via API, quais recursos tem disponíveis no seu plano atual.
6. `papel=admin` tem acesso equivalente a Premium em todas as checagens de gating.

## Riscos identificados
| Risco | Impacto | Mitigação |
|---|---|---|
| Nenhum módulo consumidor real ainda existe para validar a integração de ponta a ponta (só a camada central) | Baixo | Testes cobrem a camada central isoladamente; a integração real acontece quando alertas/newsletter/etc. forem construídos, fora desta execução |
| Execução de código/testes ainda indisponível nesta sessão (mesmo bloqueio dos runs anteriores) | Alto | Implementação com o mesmo rigor de leitura manual já demonstrado; validação por execução assim que as ferramentas normalizarem — registrado como follow-up |

## Dependências
- Nenhuma decisão humana pendente adicional — a questão em aberto da própria spec (valores exatos) foi resolvida com valores de referência explicitamente editáveis, de baixo risco.
- Depende tecnicamente de `identidade.User.papel` (já existe).
