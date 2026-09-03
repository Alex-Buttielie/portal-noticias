<!--
CONTRACT: report
DONO: historian
QUANDO É CRIADO: no fechamento de cada execução (run).
PARA ONDE VAI A INSTÂNCIA: agentic-framework/state/run-<run_id>/report.md
-->

# Report — {{run_id}}

## Metadados
- **run_id:** {{run_id}}
- **Período:** {{data_abertura}} → {{data_fechamento}}
- **Tarefa:** {{título do task-plan}}
- **Resultado final:** {{entregue | entregue_parcialmente | bloqueado | cancelado}}

## Resumo executivo
{{3-5 frases: o que foi pedido, o que foi entregue, e se houve desvio relevante do plano original.}}

## Métricas
| Métrica | Valor |
|---|---|
| Iterações (implementação ↔ revisão/remediação) | {{n}} |
| Findings de revisão — abertos | {{n}} |
| Findings de revisão — resolvidos | {{n}} |
| Arquivos alterados | {{n}} |
| Testes adicionados | {{n}} |
| Veredito final do tester | {{passed/failed/blocked}} |
| Veredito final do reviewer | {{approve/approve_with_comments/changes_requested/blocked/N-A}} |

## Linha do tempo resumida
{{Lista curta, uma linha por evento relevante — a versão detalhada está em implementation-history.md.}}
- {{data/hora}} — {{evento}}

## Desvios do plano original
{{Diferenças entre o que o task-plan.md previa e o que de fato aconteceu, e por quê.}}

## Follow-ups / pendências
{{O que ficou para depois — deve virar novo item de backlog/spec, não ficar só registrado aqui.}}
- {{item}}

## Artefatos desta execução
- task-plan.md
- implementation-contract.md
- implementation-history.md
- code-review-contract.md {{se aplicável}}
- documentation-update.md {{se aplicável}}
