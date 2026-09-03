<!--
CONTRACT: implementation-contract
DONO: orchestrator (preenche) / executor, tester, reviewer (leem)
QUANDO É CRIADO: logo após o task-plan.md ser aceito.
PARA ONDE VAI A INSTÂNCIA: agentic-framework/state/run-<run_id>/implementation-contract.md
-->

# Implementation Contract — {{run_id}}

## Metadados
- **run_id:** {{run_id}}
- **Deriva de:** task-plan.md ({{run_id}})
- **Versão do contrato:** {{n}} (incremente se o escopo mudar durante a execução — nunca edite silenciosamente)

## O que deve ser construído
{{Descrição técnica objetiva — não é a descrição de negócio do task-plan, é o "o quê" técnico.}}

## Áreas/arquivos esperados
{{Módulos, diretórios ou arquivos que provavelmente serão tocados. Não é uma lista fechada, mas qualquer mudança fora daqui deve ser justificada no implementation-history.md.}}
- {{área/arquivo}}

## Interfaces afetadas
{{APIs, contratos de dados, schemas de banco, eventos — qualquer coisa que outros componentes dependem.}}

## Critérios de aceite (técnicos, testáveis)
{{Cada item deve poder virar um teste automatizado. Formato: dado X, quando Y, então Z.}}
1. {{critério}}

## Não-objetivos
{{O que explicitamente NÃO deve ser feito nesta execução, mesmo que pareça relacionado — evita scope creep.}}
- {{item}}

## Restrições técnicas
- **Performance:** {{se aplicável}}
- **Segurança/privacidade:** {{ex: dados de usuário, LGPD, autenticação}}
- **Dependências permitidas:** {{bibliotecas novas precisam de aprovação explícita aqui}}
- **Estilo/convenções:** {{referenciar guia de estilo do projeto, se existir}}

## Definição de pronto (Definition of Done)
- [ ] Critérios de aceite implementados
- [ ] Testes escritos e passando (tester)
- [ ] Revisão de código aprovada, se exigida por `review-triggers.md` (reviewer)
- [ ] Documentação atualizada (documenter)
- [ ] `implementation-history.md` completo e coerente
