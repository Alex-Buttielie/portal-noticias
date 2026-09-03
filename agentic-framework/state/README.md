# State

Diretório de **artefatos em tempo de execução** do agentic-framework. Diferente de `contracts/`, `prompts/` e `schemas/` (que são templates e regras estáveis), tudo aqui é gerado durante execuções reais.

## Estrutura

```
state/
  HISTORY.md              # ledger append-only — uma linha por execução fechada (mantido pelo historian)
  run-<run_id>/            # uma pasta por execução
    run-state.json          # estado da execução (schemas/run-state.schema.json)
    task-plan.md
    implementation-contract.md
    implementation-history.md
    code-review-contract.md       # se a execução passou por revisão
    documentation-update.md       # se a execução tocou documentação
    report.md
```

## Regras

- **Nunca edite manualmente** um `run-<run_id>/` de uma execução já fechada (`status: closed` no `run-state.json`) — é registro histórico.
- **`HISTORY.md` é append-only.** Correções de uma entrada anterior viram uma nova linha, nunca uma edição da linha original (ver `agentic-framework/contracts/history.md`).
- Execuções abandonadas/canceladas continuam com sua pasta (não são apagadas) — ficam com `status: cancelled` no `run-state.json`, para preservar o histórico do que foi tentado.
