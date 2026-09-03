# Contract Checklist

Checklist genérico usado por qualquer agente antes de considerar **qualquer** contrato (`task-plan.md`, `implementation-contract.md`, `code-review-contract.md`, `documentation-update.md`, `report.md`) como completo o suficiente para passar adiante. Se algum item falhar, o contrato volta para quem o produziu — não segue no pipeline.

## Checklist universal

1. **Sem placeholders.** Nenhum `{{...}}` do template restou sem preenchimento (ou preenchido explicitamente como "N/A" com justificativa, quando de fato não se aplica).
2. **Verificável.** Toda afirmação de critério de aceite, finding ou resultado pode ser checada por outra pessoa/agente sem precisar confiar na palavra de quem escreveu — tem evidência, exemplo concreto ou caminho de arquivo.
3. **Escopo explícito.** Fica claro o que está dentro e o que está fora, não só o que está dentro.
4. **Rastreável.** O contrato referencia o `run_id` e, quando aplicável, o contrato do qual deriva (ex: `implementation-contract.md` referencia `task-plan.md`).
5. **Sem ambiguidade de responsável.** Está claro qual agente produz e qual(is) agente(s) consomem este contrato.
6. **Consistente com os artefatos anteriores.** Não contradiz o `task-plan.md`/`implementation-contract.md` sem justificar a mudança (e, se mudou, a versão do contrato foi incrementada).

## Checklist específico por contrato

### task-plan.md
- [ ] Critérios de aceite são de negócio/produto, não implementação.
- [ ] Toda suposição assumida (quando o solicitante não respondeu) está listada com motivo.
- [ ] A divisão de trabalho cobre da implementação ao fechamento (historian incluso).

### implementation-contract.md
- [ ] Critérios de aceite estão no formato dado/quando/então (testáveis).
- [ ] Não-objetivos explícitos, não só implícitos.
- [ ] Restrições de segurança/performance preenchidas ou explicitamente marcadas como N/A.

### code-review-contract.md
- [ ] Cada finding tem cenário de falha concreto, não uma afirmação genérica.
- [ ] Findings estão ordenados por severidade.
- [ ] O veredito é coerente com a tabela de severidades (ex: não pode ser `approve` havendo `blocker` aberto).

### documentation-update.md
- [ ] Se não há impacto em documentação, isso está justificado, não implícito por uma seção vazia.
- [ ] Toda mudança de comportamento visível ao usuário tem entrada de changelog correspondente.

### report.md
- [ ] Métricas vêm de artefatos reais da execução (contagem real de findings, resultado real do tester), não de estimativa.
- [ ] Todo follow-up listado é acionável (não é uma vaga "melhorar depois").
