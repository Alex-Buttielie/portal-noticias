# Task Plan — 20260902-1426-assinatura-premium

## Metadados
- **run_id:** 20260902-1426-assinatura-premium
- **Data de abertura:** 2026-09-02
- **Solicitado por:** usuário ("continue a implementação do meu software até que eu tenha um MVP para iniciar" — confirmado explicitamente via pergunta direta que este módulo deveria ser implementado mesmo sem validação por execução ainda disponível)
- **Spec de origem:** `agentic-framework/specs/assinatura-premium.md`

## Objetivo
Ao final desta execução, deve existir o domínio completo de assinatura Premium: planos com preço/duração editáveis pelo admin, ciclo de vida de assinatura com os 7 estados exatos do BRD §9, integração com pagamento através de uma interface abstrata (`PaymentGatewayProvider` — nenhum provedor real escolhido ainda, decisão em aberto), grace period configurável para inadimplência, cancelamento self-service, histórico de pagamentos, e sincronização automática de `User.papel` (free ⇄ premium) conforme o estado da assinatura.

## Escopo

### Dentro do escopo
- App Django `assinatura/`: modelos `Plan`, `Subscription`, `HistoricoPagamento`, `AssinaturaMudancaEstadoLog` (auditoria), `ConfiguracaoAssinatura` (singleton — grace period e período de teste configuráveis).
- `PaymentGatewayProvider` (interface abstrata) + `ManualPaymentGatewayProvider` (implementação concreta placeholder, sem integração real — ver "Suposições assumidas").
- Serviço de domínio (`services.py`): assinar, processar confirmação/recusa de pagamento, cancelar, sincronizar `papel` do usuário.
- Task periódica (Celery, já configurado no projeto desde `ingestao-curadoria-noticias`) para processar vencimentos/grace periods/renovação automática.
- Django admin: `Plan` (preço/duração/ativo editáveis), `ConfiguracaoAssinatura` (grace period/teste), `Subscription`/`HistoricoPagamento`/log (leitura/operação administrativa).
- Endpoints: listar planos ativos, assinar um plano, cancelar assinatura própria, ver histórico de pagamentos próprio, ver status da própria assinatura.
- Sincronização de `User.papel` com o estado da assinatura — fecha o ciclo que `gating-free-premium` já assumia como suposição.
- Testes cobrindo os critérios de aceite abaixo.

### Fora do escopo (explicitamente)
- Escolha e integração de um provedor de pagamento real (Mercado Pago/Stripe/Pagar.me) — decisão em aberto, registrada em `ARCHITECTURE.md` §8. `ManualPaymentGatewayProvider` é um placeholder funcional para desenvolvimento/teste, não uma integração de produção.
- Cupons e promoções.
- Planos B2B.
- Envio real de e-mail/notificação de aviso de vencimento/pagamento recusado (o evento é registrado/logado; a integração com um provedor de e-mail transacional real já é uma decisão em aberto desde `identidade/`, não desta execução).
- Frontend (checkout, tela de assinatura).
- Ativação do período de teste no lançamento (a estrutura de dados suporta, conforme requisito funcional 10, mas fica desligada por padrão — `ConfiguracaoAssinatura.periodo_teste_ativo=False`).

## Suposições assumidas
- **`PaymentGatewayProvider` sem integração real:** a única opção responsável dado que o provedor concreto é uma decisão de negócio em aberto (confirmado em `ARCHITECTURE.md`). Implemento a interface abstrata (contrato completo: criar cobrança, consultar status, cancelar) + `ManualPaymentGatewayProvider`, que simula aprovação imediata — suficiente para exercitar toda a máquina de estados e permitir operação manual/assistida pelo admin antes de uma integração real existir. **Não é uma simulação de um provedor específico** (não finge ser Mercado Pago ou Stripe), é deliberadamente genérico.
- **Cancelamento mantém acesso até o fim do período já pago:** ao cancelar, `status` vira `cancelada` e `renovacao_automatica=False`, mas o usuário continua com `papel=premium` até `vencimento` (já pago, não é reembolsado nem cortado na hora) — decisão alinhada com o requisito explícito do BRD §8 ("sem práticas de retenção abusivas"), que também implica não punir o usuário cortando acesso que ele já pagou. Depois de `vencimento`, a task periódica move para `encerrada` e sincroniza `papel=free`.
- **Sincronização de `User.papel`** é responsabilidade exclusiva deste módulo (`services._sincronizar_papel_usuario`) — nenhum outro módulo (incluindo `gating`) deve escrever em `papel` diretamente; eles só leem.
- **`Plan.duracao_dias`** (não "periodicidade" como enum fechado semestral/anual) — mais parametrizável (o admin pode criar qualquer duração sem alteração de código), consistente com o espírito do requisito 1 ("preço não pode estar hardcoded" — estendi para duração também).

## Restrições
- Stack obrigatória: Python/Django + DRF + Celery (já configurado), PostgreSQL — mesmo projeto/backend.
- Toda mudança de estado de assinatura deve ser auditável (requisito não-funcional da spec).
- Nenhuma chamada direta a SDK de gateway fora de `PaymentGatewayProvider` (requisito não-funcional da spec).
- LGPD: cancelar/inadimplência nunca apaga a conta do usuário (requisito funcional 11).

## Divisão de trabalho
| Etapa | Agente responsável | Entrada esperada | Saída esperada |
|---|---|---|---|
| 1 | executor | implementation-contract.md | código + implementation-history.md |
| 2 | tester | implementation-contract.md | veredito passed/failed/blocked |
| 3 | reviewer (obrigatório — ver review-triggers.md) | diff do executor | code-review-contract.md |
| 4 | remediator (se necessário) | code-review-contract.md | correções + revalidação |
| 5 | documenter | implementation-history.md | documentation-update.md + docs atualizadas |
| 6 | historian | todos os artefatos acima | report.md + entrada em HISTORY.md |

## Critérios de aceite (nível de negócio/produto)
1. Um admin cria/edita um `Plan` (nome, preço, duração, ativo) pelo Django admin, sem tocar em código.
2. Um usuário assina um plano; ao gateway confirmar o pagamento (mesmo que via `ManualPaymentGatewayProvider`), a assinatura vira `ativa` e `User.papel` vira `premium` automaticamente, sem intervenção do admin.
3. As transições de estado seguem exatamente os 7 estados do BRD §9, nunca um estado fora dessa lista.
4. Um pagamento recusado move a assinatura para `inadimplente`, mas o usuário continua `premium` até o grace period (configurável) expirar.
5. Ao expirar o grace period sem regularização, a assinatura vira `expirada` e `User.papel` volta para `free` automaticamente.
6. O usuário consegue cancelar sua própria assinatura via API, sem precisar de aprovação/contato humano, e mantém acesso Premium até o fim do período já pago.
7. O usuário consegue consultar seu histórico de pagamentos.
8. Toda mudança de estado de uma assinatura gera uma entrada de auditoria (estado anterior, novo, motivo, quando).
9. Cancelar/expirar uma assinatura nunca apaga ou desativa a conta do usuário (`User` continua existindo e acessível).
10. A estrutura de dados suporta período de teste configurável, mesmo desligado por padrão.

## Riscos identificados
| Risco | Impacto | Mitigação |
|---|---|---|
| Módulo financeiro — maior superfície de risco de todo o MVP (dinheiro, mesmo que simulado) implementado sem nenhuma validação por execução ainda | Alto | Máximo rigor de leitura manual, revisão obrigatória (`review-triggers.md` já lista "cobrança/pagamento/assinatura" como gatilho obrigatório), e sinalização explícita de que este módulo é o mais crítico para validar assim que ferramentas de execução voltarem — não deve ir para produção sem suíte de testes rodando de verdade |
| Ausência de provedor de pagamento real significa que o fluxo de webhook/confirmação assíncrona de pagamento não é exercitado com um gateway de verdade | Médio | `PaymentGatewayProvider` desenhado para que trocar `ManualPaymentGatewayProvider` por uma implementação real não exija mudar `services.py`/models — só a classe concreta injetada |
| Task periódica de vencimento/grace period depende de Celery Beat, que já foi sinalizado como não validado com broker real desde `ingestao-curadoria-noticias` | Médio | Mesma limitação já registrada; lógica de negócio (não a infraestrutura de agendamento) é o que os testes devem cobrir, chamando a função da task diretamente |

## Dependências
- Nenhuma decisão humana pendente bloqueia o DESENHO desta execução — a única questão em aberto real da spec (provedor de pagamento concreto) é tratada como decisão de negócio futura, não bloqueia a implementação técnica (a própria spec já dizia isso).
- Depende de `gating-free-premium` (via `User.papel`) e `identidade` (User) — ambos já existentes no código.
