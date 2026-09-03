---
name: agentic-run
description: Executa o pipeline agentic completo para uma tarefa de desenvolvimento neste projeto — planejamento (task-plan), implementação, testes, revisão condicional, remediação em loop, documentação e fechamento com histórico. Use quando o usuário pede para implementar uma feature, corrigir um bug, ou qualquer trabalho de desenvolvimento que deva seguir o processo do agentic-framework, não apenas revisar ou verificar algo já existente.
---

# agentic-run

Esta skill faz você (a sessão que a invocou) assumir o papel de **orchestrator** e conduzir a execução completa descrita em `.claude/agents/orchestrator.md`, delegando para os demais agentes via a ferramenta Agent. Leia `.claude/agents/orchestrator.md` inteiro antes de prosseguir — ele é a definição de comportamento canônica; este arquivo é o roteiro operacional de como invocá-lo passo a passo.

## Pré-requisitos

Antes de abrir uma execução, tenha em mãos (ou obtenha do usuário):
- O pedido em si, avaliado contra `agentic-framework/prompts/request-exemplos.md`.
- Se o pedido referenciar o BRD do projeto (`BRD_portal_noticias_versao_1.docx`) ou uma spec em `agentic-framework/specs/`, tenha o caminho/seção à mão.

Se o pedido estiver subespecificado (ver critérios em `request-exemplos.md`), pergunte antes de abrir a execução — a menos que esteja operando sem supervisão, caso em que você assume e registra a suposição no `task-plan.md`.

## Passo a passo

1. **Gerar `run_id`** no formato `AAAAMMDD-HHmm-slug-curto` (use a data/hora atual e um slug curto do pedido).
2. **Criar a pasta da execução:** `agentic-framework/state/run-<run_id>/`.
3. **Inicializar `run-state.json`** nessa pasta, seguindo `agentic-framework/schemas/run-state.schema.json`, com `status: "planning"` e `current_phase: "planning"`.
4. **Produzir `task-plan.md`** copiando `agentic-framework/contracts/task-plan.md` para a pasta da execução e preenchendo todos os campos. Valide contra `agentic-framework/prompts/contract-checklist.md`.
5. **Produzir `implementation-contract.md`** a partir do task-plan, na mesma pasta.
6. **Delegar ao `executor`** (`Agent({subagent_type: "executor", ...})`) passando o caminho do `implementation-contract.md`. Atualize `run-state.json` (`current_phase: "implementation"`) antes e depois.
7. **Delegar ao `tester`** para validar os critérios de aceite. Atualize `run-state.json` (`current_phase: "testing"`).
8. **Checar `agentic-framework/prompts/review-triggers.md`.** Se algum gatilho se aplicar (ou se o `task-plan.md` já marcou revisão como obrigatória), delegue ao `reviewer` (`current_phase: "review"`).
9. **Se o reviewer devolver `changes_requested` ou `blocked`:** delegue ao `remediator` (`current_phase: "remediation"`), incremente `iteration_count` em `run-state.json`. Repita os passos 6-9 conforme necessário.
   - **Limite:** se `iteration_count` ultrapassar `max_iterations` (padrão 3) sem resolver, marque `status: "blocked"`, preencha `blocked_reason` e pare o loop — reporte ao usuário em vez de continuar tentando.
10. **Delegar ao `documenter`** (`current_phase: "documentation"`) assim que testes passarem e a revisão (se exigida) estiver aprovada.
11. **Delegar ao `historian`** para produzir `report.md`, finalizar `implementation-history.md` e acrescentar a linha em `agentic-framework/state/HISTORY.md`. Marque `run-state.json` com `status: "closed"` (ou `"blocked"`/`"cancelled"` conforme o desfecho real) e `current_phase: "done"`.
12. **Responder ao usuário** com um resumo objetivo: o que foi entregue, link para `report.md`, e follow-ups pendentes (se houver).

## Quando não usar esta skill

- Para revisar código já existente sem passar pelo ciclo completo → use `agentic-review`.
- Para só verificar se uma implementação já feita atende a um contrato/spec, sem alterar o pipeline inteiro → use `agentic-verify`.
