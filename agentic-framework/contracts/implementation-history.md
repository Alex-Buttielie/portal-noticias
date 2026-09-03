<!--
CONTRACT: implementation-history
DONO: executor (cria e adiciona entradas) / tester, remediator, historian (adicionam entradas)
QUANDO É CRIADO: junto com a primeira ação do executor sobre o implementation-contract.md.
PARA ONDE VAI A INSTÂNCIA: agentic-framework/state/run-<run_id>/implementation-history.md
NATUREZA: append-only durante a execução — cada entrada é uma iteração, nunca se edita uma entrada anterior.
-->

# Implementation History — {{run_id}}

<!-- Uma seção "## Iteração N" por evento relevante: implementação inicial, cada correção do remediator,
     cada validação do tester. Ordem cronológica, sem lacunas. -->

## Iteração 1 — {{data/hora}} — {{agente}} ({{implementação inicial | correção | validação}})

**O que foi feito:**
{{descrição objetiva}}

**Por quê:**
{{motivo — para correções, referenciar o finding ou a falha de teste que originou}}

**Arquivos tocados:**
- {{arquivo}}

**Comandos executados / evidência:**
```
{{comando e saída relevante, especialmente para o tester}}
```

**Resultado:**
{{sucesso | falha parcial | falha — e o que isso implica para a próxima iteração}}

**Notas fora do escopo (se houver):**
{{algo identificado como necessário mas fora do implementation-contract.md atual — não implementado aqui, só sinalizado}}

---

<!-- Repetir bloco "## Iteração N" para cada evento subsequente -->
