<!--
CONTRACT: history (formato de UMA linha do ledger)
DONO: historian
QUANDO É USADO: toda vez que uma execução é fechada, o historian acrescenta uma linha neste formato
             ao final de agentic-framework/state/HISTORY.md. Nunca reescreve linhas existentes.
-->

# Formato de entrada do HISTORY.md

Cada execução gera exatamente uma linha na tabela de `agentic-framework/state/HISTORY.md`, sempre acrescentada ao final (append-only):

```
| {{data ISO}} | {{run_id}} | {{tarefa em poucas palavras}} | {{agentes envolvidos, separados por vírgula}} | {{resultado}} | {{link para report.md}} |
```

## Campos
- **data ISO:** `AAAA-MM-DD HH:mm` (fuso do projeto).
- **run_id:** o identificador único da execução.
- **tarefa:** título curto, o mesmo do `task-plan.md`.
- **agentes envolvidos:** só os que efetivamente participaram (ex: `executor, tester, historian` quando não houve revisão).
- **resultado:** um de `entregue`, `entregue_parcialmente`, `bloqueado`, `cancelado`.
- **link:** caminho relativo para `state/run-<run_id>/report.md`.

## Regra de ouro
Se uma entrada estiver errada, a correção é uma **nova linha** referenciando a linha original e explicando a correção — o ledger nunca é editado retroativamente.
