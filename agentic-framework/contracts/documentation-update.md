<!--
CONTRACT: documentation-update
DONO: documenter
QUANDO É CRIADO: depois que testes passam e a revisão (se exigida) está aprovada.
PARA ONDE VAI A INSTÂNCIA: agentic-framework/state/run-<run_id>/documentation-update.md
-->

# Documentation Update — {{run_id}}

## Metadados
- **run_id:** {{run_id}}
- **Baseado em:** implementation-history.md ({{run_id}})

## Documentos afetados
| Documento | Tipo de mudança | Resumo |
|---|---|---|
| {{caminho}} | {{nova seção / atualização / remoção}} | {{o que mudou}} |

## Sem impacto em documentação?
{{Se nenhuma doc precisa mudar, marque aqui e justifique — não deixe a seção acima vazia sem explicação.}}
- [ ] Confirmado: esta execução não requer atualização de documentação porque {{motivo}}

## Exemplos/snippets novos ou atualizados
{{Cole aqui ou referencie onde ficaram os exemplos de uso adicionados/alterados.}}

## Entrada de changelog
{{Se o projeto mantiver CHANGELOG, a entrada exata adicionada.}}
- `{{versão ou "Unreleased"}}`: {{descrição da mudança do ponto de vista do usuário}}

## Verificação
- [ ] Nenhum exemplo/trecho de documentação existente ficou contraditório com a mudança
- [ ] Build/lint de documentação rodado (se o projeto tiver um)
