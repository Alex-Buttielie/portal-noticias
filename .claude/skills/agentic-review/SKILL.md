---
name: agentic-review
description: Roda uma revisão de código isolada (sem o pipeline completo de implementação) sobre um diff, PR ou conjunto de arquivos existente, produzindo um code-review-contract.md com findings e veredito, com opção de loop de remediação. Use quando o usuário pede para revisar código já escrito, antes de um merge, ou quando um gatilho de review-triggers.md se aplica a uma mudança feita fora do agentic-run.
---

# agentic-review

Fluxo standalone de revisão, mais leve que o `agentic-run` completo — não recria `task-plan.md`/`implementation-contract.md` do zero, mas ainda gera artefatos rastreáveis em `agentic-framework/state/`.

## Passo a passo

1. **Determinar o escopo:** diff, PR, branch ou lista de arquivos indicada pelo usuário. Se não for explícito, pergunte (não assuma "revisar tudo").
2. **Gerar `run_id`** (mesmo formato de `agentic-run`) e criar `agentic-framework/state/run-<run_id>/`. Inicialize `run-state.json` com `status: "in_progress"`, `current_phase: "review"` — este fluxo não passa por `planning`/`implementation` completos.
3. **Verificar se existe um `implementation-contract.md` relacionado** (de uma execução anterior do mesmo trabalho). Se existir, referencie-o para o reviewer avaliar contra o que foi pedido, não só contra preferência de estilo. Se não existir, o reviewer avalia pelo `agentic-framework/prompts/review-triggers.md` e pelas boas práticas gerais.
4. **Delegar ao `reviewer`** (`Agent({subagent_type: "reviewer", ...})`) com o escopo e o contrato de referência (se houver). Ele produz `code-review-contract.md` em `state/run-<run_id>/`.
5. **Se o veredito for `changes_requested` ou `blocked`:**
   - Pergunte ao usuário se deseja que o `remediator` já corrija (loop automático) ou só reportar os findings.
   - Se autorizado, delegue ao `remediator`, depois peça uma nova passada do `reviewer` sobre o que mudou. Respeite o mesmo limite de iterações do `agentic-run` (padrão 3).
6. **Fechar o registro:** delegue ao `historian` para acrescentar uma linha em `agentic-framework/state/HISTORY.md` (resultado = veredito final da revisão) — não é necessário `report.md` completo neste fluxo leve, um resumo direto ao usuário basta, mas a entrada no `HISTORY.md` é obrigatória para manter o ledger completo.
7. **Responder ao usuário** com o veredito final e a lista de findings (ou o caminho para `code-review-contract.md`).

## Quando não usar esta skill

- Para conduzir uma feature do zero (planejamento → implementação → testes → docs) → use `agentic-run`.
- Para apenas confirmar se algo já implementado bate com seus critérios de aceite, sem foco em qualidade/segurança do código → use `agentic-verify`.
