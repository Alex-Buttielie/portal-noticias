# agentic-framework

Framework de desenvolvimento assistido por agentes de IA para o projeto **BRD Portal de Notícias**. Define como o trabalho de desenvolvimento é planejado, implementado, testado, revisado, documentado e auditado, com responsabilidades claras entre agentes especializados e artefatos rastreáveis para cada execução.

## Visão geral do pipeline

```
Pedido (humano ou spec)
        │
        ▼
  orchestrator ──► task-plan.md ──► implementation-contract.md
        │
        ▼
     executor ──► implementa + implementation-history.md
        │
        ▼
      tester ──► valida critérios de aceite (passed / failed / blocked)
        │
        ▼
  [review-triggers.md indica revisão?] ──não──► pula para documenter
        │ sim
        ▼
    reviewer ──► code-review-contract.md (findings + veredito)
        │
        ▼
  [changes_requested / blocked?] ──não──► documenter
        │ sim
        ▼
  remediator ──► corrige (direto ou via executor) ──► volta para tester/reviewer
        │            (máx. 3 iterações antes de escalar para humano)
        ▼
   documenter ──► documentation-update.md + docs atualizadas
        │
        ▼
   historian ──► report.md + entrada em state/HISTORY.md ──► execução fechada
```

## Agentes (`.claude/agents/`)

| Agente | Responsabilidade | Não faz |
|---|---|---|
| `orchestrator` | Planeja, delega, mantém `run-state.json`, decide quando escalar | Não implementa nem revisa código |
| `executor` | Implementa exatamente o que está no `implementation-contract.md` | Não aprova o próprio trabalho |
| `tester` | Valida critérios de aceite com evidência real | Não corrige bugs encontrados |
| `reviewer` | Avalia qualidade/segurança do código, produz findings + veredito | Não edita código (sem `Write`/`Edit`) |
| `remediator` | Fecha o loop de correção a partir dos findings | Não introduz escopo novo |
| `documenter` | Atualiza documentação a partir do que foi de fato implementado | Não documenta o planejado-mas-não-feito |
| `historian` | Mantém o registro histórico e auditável, append-only | Não implementa nem revisa |

## Skills (`.claude/skills/`)

| Skill | Quando usar |
|---|---|
| `agentic-run` | Pipeline completo — implementar feature, corrigir bug, qualquer trabalho de desenvolvimento novo |
| `agentic-review` | Revisão isolada de código já escrito, antes de um merge |
| `agentic-verify` | Checagem objetiva se algo já implementado atende ao que foi pedido, sem revisar qualidade nem corrigir |

## Estrutura de diretórios

```
agentic-framework/
  README.md                  # este arquivo
  contracts/                 # templates dos documentos trocados entre agentes
    task-plan.md
    implementation-contract.md
    code-review-contract.md
    documentation-update.md
    report.md
    history.md                # formato de UMA linha do ledger
    implementation-history.md
  prompts/                    # regras e critérios usados pelos agentes
    contract-checklist.md      # valida se um contrato está completo
    request-exemplos.md        # o que torna um pedido bem formado
    review-triggers.md         # quando revisão de código é obrigatória
  schemas/
    run-state.schema.json      # schema do estado de cada execução
  specs/                       # requisitos de produto recortados do BRD ou novos
    README.md
    _template.md
  state/                       # artefatos gerados em tempo de execução (não são templates)
    README.md
    HISTORY.md                  # ledger append-only de todas as execuções
    run-<run_id>/                # uma pasta por execução (gerada, não versionada manualmente)
```

## Princípios do framework

1. **Contratos antes de código.** Nenhum agente implementa, revisa ou documenta sem um contrato preenchido e validado (`prompts/contract-checklist.md`).
2. **Rastreabilidade total.** Toda execução tem `run_id`, `run-state.json` e uma linha permanente em `state/HISTORY.md` — nada acontece "por fora".
3. **Separação de papéis.** Quem implementa não aprova o próprio trabalho; quem revisa não edita código; quem documenta só registra o que foi validado.
4. **Loop de correção com teto.** Falhas de revisão/teste geram remediação automática até um limite de iterações (padrão 3); depois disso, escala para decisão humana em vez de insistir indefinidamente.
5. **Histórico é append-only.** Nada é reescrito silenciosamente — correções de registro viram novas entradas.

## Origem do domínio

O contexto de produto usado pelos agentes (nomes de features, regras sensíveis em `review-triggers.md`, exemplos em `request-exemplos.md`) vem de `BRD_portal_noticias_versao_1.docx`, na raiz do projeto. Specs recortadas dessa BRD ficam em `agentic-framework/specs/`.

## Extensões futuras (não implementadas ainda)

- Automação do loop `agentic-run` via hook/CI (hoje é conduzido por uma sessão do Claude Code seguindo as skills manualmente).
- Métricas agregadas a partir de `state/HISTORY.md` (tempo médio por execução, taxa de findings por severidade).
