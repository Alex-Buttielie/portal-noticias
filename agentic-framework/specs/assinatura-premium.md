# Spec: Assinatura Premium

## Contexto de negócio
BRD seção 6 (Assinatura Premium) e seção 9 (Período de Teste e Ciclo da Assinatura). Ver `ARCHITECTURE.md` seções 3 (`Subscription`/`Plan`), 6 (`PaymentGatewayProvider`) e 8 (decisão em aberto: provedor de pagamento concreto).

## Problema / oportunidade
Sem gestão de assinatura, não há como o negócio capturar receita Premium (prioridade "Alta" no modelo de receita do BRD, seção 5), nem como diferenciar a experiência Free x Premium de forma confiável.

## Histórias de usuário
- Como usuário, eu quero assinar o plano Premium (semestral ou anual) e ter acesso liberado automaticamente após confirmação de pagamento.
- Como usuário, eu quero cancelar minha assinatura de forma simples, sem barreiras artificiais.
- Como administrador, eu quero alterar o preço de qualquer plano no painel, sem depender de alteração de código.
- Como usuário com pagamento recusado, eu quero ser avisado e ter um período de tolerância antes de perder o acesso Premium.

## Requisitos funcionais
1. `Plan` (nome, preço, periodicidade, ativo) totalmente editável pelo admin — preço não pode estar hardcoded. Referência inicial: R$20/6 meses, R$30/12 meses (valores default, não fixos em código).
2. Criação de `Subscription` ao assinar; ativação automática após confirmação de pagamento via `PaymentGatewayProvider`.
3. Estados da assinatura: `teste`, `ativa`, `pagamento_pendente`, `inadimplente`, `cancelada`, `expirada`, `encerrada` (exatamente os do BRD §9).
4. Renovação automática quando o meio de pagamento suportar e houver consentimento do usuário.
5. Aviso de vencimento/renovação ao usuário antes da cobrança.
6. Grace period configurável (pelo admin) para falhas de pagamento antes de rebaixar para Free.
7. Downgrade automático para Free ao final do grace period sem regularização.
8. Cancelamento pelo usuário, autoatendido, sem exigir contato humano.
9. Histórico de pagamentos visível ao usuário.
10. Suporte a período de teste configurável (duração, elegibilidade, benefícios) — mesmo que não ativado no lançamento, a estrutura de dados/estado já deve suportar.
11. Preservação dos dados do usuário ao encerrar assinatura, conforme política de privacidade (não deletar conta por inadimplência).

## Requisitos não-funcionais
- Toda mudança de estado de assinatura deve ser rastreável (log/auditoria) — decisões financeiras não podem ser "silenciosas".
- Integração com gateway de pagamento deve passar exclusivamente pela interface `PaymentGatewayProvider` (ver `ARCHITECTURE.md`), nunca por chamadas diretas ao SDK do provedor espalhadas pelo domínio.
- Comunicações de renovação/cobrança devem ser transparentes, sem práticas de retenção abusivas no cancelamento (requisito explícito do BRD §8).

## Fora de escopo
- Cupons e promoções (futuro, BRD §6).
- Planos B2B (fase B2B, fora deste recorte).
- Escolha do provedor concreto de pagamento — tratada como decisão em aberto em `ARCHITECTURE.md`, não nesta spec.

## Critérios de sucesso
- Um usuário assina, paga e tem acesso Premium liberado automaticamente sem intervenção manual do admin.
- Um pagamento recusado não derruba o acesso do usuário imediatamente — só após o grace period configurado.
- O admin altera o preço de um plano e a mudança aparece no checkout sem deploy.

## Questões em aberto
- Provedor de pagamento concreto (bloqueia a implementação real do `PaymentGatewayProvider`, mas não bloqueia o desenho do domínio/estados).
- Duração default do grace period e do período de teste, se ativado.
