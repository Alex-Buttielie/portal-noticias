---
name: agentic-verify
description: Verifica, de forma somente-leitura sobre o comportamento (pode adicionar testes faltantes, mas não corrige código), se uma implementação existente atende aos critérios de aceite de um implementation-contract.md ou spec. Use quando o usuário pergunta "isso já está pronto?"/"isso atende ao que foi pedido?", antes de um merge ou fechamento de tarefa, sem querer rodar o pipeline completo nem uma revisão de qualidade de código.
---

# agentic-verify

Fluxo de checagem objetiva: produz um veredito verificável sobre se a implementação faz o que deveria — não é revisão de qualidade (`agentic-review`) nem execução de trabalho novo (`agentic-run`).

## Passo a passo

1. **Localizar o contrato/spec de referência.** Peça ao usuário (ou localize em `agentic-framework/state/run-*/implementation-contract.md`, ou em `agentic-framework/specs/`) qual é a definição do que deveria estar implementado. Sem isso, não há contra o que verificar — não invente critérios.
2. **Gerar `run_id`**, criar `agentic-framework/state/run-<run_id>/` e inicializar `run-state.json` com `current_phase: "testing"`, `status: "in_progress"`.
3. **Delegar ao `tester`** (`Agent({subagent_type: "tester", ...})`) com o contrato/spec localizado. Ele extrai os critérios de aceite, roda a suíte existente, escreve testes para lacunas de cobertura (sem alterar comportamento de produção) e devolve um veredito por critério: `passed`, `failed` ou `blocked`.
4. **Opcional — checagem leve de risco:** se o escopo verificado cair em algum gatilho de `agentic-framework/prompts/review-triggers.md`, ofereça ao usuário rodar também o `reviewer` (mas isso já é entrar no território de `agentic-review` — não faça automaticamente, pergunte).
5. **Registrar o resultado:** preencha uma versão enxuta de `agentic-framework/contracts/report.md` (foco na seção de métricas/veredito, o resto pode ficar "N/A — verificação isolada") em `state/run-<run_id>/report.md`.
6. **Fechar o registro:** delegue ao `historian` para acrescentar a linha correspondente em `agentic-framework/state/HISTORY.md` (resultado = veredito de verificação).
7. **Responder ao usuário** com o veredito por critério de aceite (não só um "sim"/"não" agregado) e, se houver falhas, o que especificamente não está atendido.

## Regra importante

Este fluxo **não corrige nada**. Se a verificação encontrar que algo não está pronto, o encaminhamento é sugerir `agentic-run` (para retomar a implementação) ou `agentic-review` (se o problema for qualidade/segurança do código já escrito) — não corrija por conta própria dentro do `agentic-verify`.

## Quando não usar esta skill

- Para implementar algo novo → use `agentic-run`.
- Para avaliar qualidade/segurança de código já escrito, além de "funciona ou não" → use `agentic-review`.
