# Exemplos de Pedidos (request-exemplos)

Referência usada pelo `orchestrator` para avaliar se um pedido tem informação suficiente para virar um `task-plan.md` sem precisar inventar requisito. Os exemplos usam o domínio do projeto (portal de notícias — ver `BRD_portal_noticias_versao_1.docx`), mas o critério vale para qualquer pedido.

## O que torna um pedido "bem formado"

Um pedido bom não precisa ser longo, mas deixa claro: **o quê**, **para quem/por quê** (quando não é óbvio) e **como saber que deu certo**.

## Exemplos bons

> "Implementar o fluxo de credenciamento manual de jornalistas descrito na seção 13 do BRD: administrador aprova/rejeita solicitação de credenciamento a partir de um painel; jornalista aprovado ganha permissão de publicar opinião/análise. Critério de aceite: um usuário sem credencial não consegue publicar; um administrador consegue aprovar e, a partir daí, o usuário publica normalmente."

Por que é bom: escopo claro, referência à spec de origem, critério de aceite verificável.

> "Adicionar campo de 'localidade de interesse' no cadastro da lista de espera (seção 26 do BRD), obrigatório, usado depois pelo radar de tendências por localização. Não precisa implementar o radar agora, só capturar o dado."

Por que é bom: escopo pequeno e explícito, inclusive o que fica de fora ("não precisa implementar o radar agora").

> "Revisar (agentic-review) o módulo de cálculo de reputação de autores antes de mergear — é código sensível porque afeta quem pode publicar sem moderação prévia (seção 15 do BRD)."

Por que é bom: pedido de revisão isolada, com justificativa de por que o gatilho de revisão se aplica (ver `review-triggers.md`).

## Exemplos que precisam de esclarecimento antes de virar task-plan

> "Melhora o sistema de assinatura premium."

Falta: o quê especificamente (preço configurável? novo benefício? fluxo de cobrança? cancelamento?), critério de aceite, e se é uma mudança de produto (precisa decisão humana) ou só técnica.
**Ação do orchestrator:** perguntar o que especificamente deve mudar, referenciando a seção 6/7/9 do BRD (Assinatura Premium / Free x Premium / Período de Teste) para ajudar o solicitante a precisar o pedido — não escolher uma interpretação sozinho, salvo em modo não-supervisionado (nesse caso, registrar a suposição no `task-plan.md`).

> "Deixa o site mais rápido."

Falta: rápido em quê (carregamento inicial, busca, feed personalizado?), meta numérica, e qual é hoje a linha de base.
**Ação do orchestrator:** pedir uma meta mensurável (ex: "reduzir tempo de carregamento do feed de X para Y segundos") antes de abrir a execução.

> "Corrige o bug da comunidade."

Falta: qual bug, como reproduzir, qual o comportamento esperado.
**Ação do orchestrator:** pedir passos de reprodução e comportamento esperado — sem isso, `tester` não consegue escrever um teste que prove que o bug foi corrigido.

## Regra prática

Se o `orchestrator` conseguir escrever os "Critérios de aceite" do `task-plan.md` sem inventar nada que o solicitante não disse (ou que não está na spec/BRD referenciada), o pedido está bem formado o suficiente para prosseguir.
