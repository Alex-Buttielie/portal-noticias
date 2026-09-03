<!--
CONTRACT: task-plan
DONO: orchestrator
QUANDO É CRIADO: no início de toda execução (agentic-run), antes de qualquer implementação.
PARA ONDE VAI A INSTÂNCIA: agentic-framework/state/run-<run_id>/task-plan.md
-->

# Task Plan — {{run_id}}

## Metadados
- **run_id:** {{run_id}}
- **Data de abertura:** {{data}}
- **Solicitado por:** {{humano_ou_origem}}
- **Spec de origem:** {{link_para_spec_em_agentic-framework/specs/_ou_BRD}}

## Objetivo
{{Uma ou duas frases descrevendo o que precisa ser verdade ao final desta execução.}}

## Escopo
### Dentro do escopo
- {{item}}

### Fora do escopo (explicitamente)
- {{item}}

## Suposições assumidas
{{Preencher só quando o orchestrator precisou assumir algo por falta de resposta do solicitante — cada suposição deve poder ser revertida se estiver errada.}}
- {{suposição}} — motivo: {{motivo}}

## Restrições
{{Prazo, stack obrigatória, compatibilidade retroativa, requisitos de segurança/LGPD, etc.}}

## Divisão de trabalho
| Etapa | Agente responsável | Entrada esperada | Saída esperada |
|---|---|---|---|
| 1 | executor | implementation-contract.md | código + implementation-history.md |
| 2 | tester | implementation-contract.md | veredito passed/failed/blocked |
| 3 | reviewer (se `review-triggers.md` aplicar) | diff do executor | code-review-contract.md |
| 4 | remediator (se necessário) | code-review-contract.md | correções + revalidação |
| 5 | documenter | implementation-history.md | documentation-update.md + docs atualizadas |
| 6 | historian | todos os artefatos acima | report.md + entrada em HISTORY.md |

## Critérios de aceite (nível de negócio/produto)
{{Lista de afirmações verificáveis — viram a base dos critérios técnicos do implementation-contract.}}
1. {{critério}}

## Riscos identificados
| Risco | Impacto | Mitigação |
|---|---|---|
| {{risco}} | {{alto/médio/baixo}} | {{mitigação}} |

## Dependências
{{Outras tarefas, sistemas externos, ou decisões humanas pendentes que bloqueiam ou influenciam esta execução.}}
