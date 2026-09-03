<!--
CONTRACT: code-review-contract
DONO: reviewer
QUANDO É CRIADO: sempre que review-triggers.md indicar revisão obrigatória, ou sob demanda (skill agentic-review).
PARA ONDE VAI A INSTÂNCIA: agentic-framework/state/run-<run_id>/code-review-contract.md
-->

# Code Review Contract — {{run_id}}

## Metadados
- **run_id:** {{run_id}}
- **Escopo revisado:** {{arquivos/diff/PR}}
- **Contrato de referência:** implementation-contract.md ({{run_id}}), se existir
- **Gatilhos aplicados (de review-triggers.md):** {{lista}}

## Findings

<!-- Um bloco por finding, ordenado do mais grave para o menos grave. Sem findings inventados: se não há problema, a lista fica vazia. -->

### Finding {{n}}
- **Arquivo:** {{caminho}}
- **Linha:** {{linha ou "N/A"}}
- **Categoria:** {{correctness | security | performance | maintainability | test-coverage | docs | style}}
- **Severidade:** {{blocker | major | minor | nit}}
- **Resumo:** {{uma frase, o defeito em si}}
- **Cenário de falha:** {{entrada/estado concreto → resultado incorreto ou risco concreto}}
- **Sugestão:** {{opcional — como corrigir, sem ser prescritivo demais}}

## Resumo quantitativo
| Severidade | Quantidade |
|---|---|
| blocker | {{n}} |
| major | {{n}} |
| minor | {{n}} |
| nit | {{n}} |

## Veredito
**{{approve | approve_with_comments | changes_requested | blocked}}**

{{Justificativa em 1-2 frases — por que este veredito, referenciando os findings relevantes.}}
