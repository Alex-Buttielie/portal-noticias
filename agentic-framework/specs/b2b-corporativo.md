# Spec: B2B — Produto Corporativo

## Contexto de negócio
BRD seção 19 (B2B — Produto Corporativo) e seção 20 (Arquitetura Comercial para B2B). Fase "B2B" do roadmap (§31), depois de Comunidade e Inteligência.

## Problema / oportunidade
O modelo de negócio (BRD §5) já prevê B2B como fonte de receita "Média/Alta" — monitoramento e inteligência de notícias para empresas (setor, concorrente, palavra-chave), hoje inexistente.

## Histórias de usuário
- Como usuário corporativo, eu quero monitorar notícias sobre minha empresa, concorrentes, setor e palavras-chave, para acompanhamento estratégico.
- Como administrador de uma organização, eu quero convidar outros usuários da minha empresa e controlar permissões, para uso em equipe.
- Como usuário corporativo, eu quero receber alertas e relatórios periódicos, para não precisar checar manualmente.

## Requisitos funcionais
1. `Organizacao` (empresa cliente B2B): nome, plano corporativo (Basic/Pro/Enterprise), múltiplos usuários vinculados.
2. Monitoramento configurável por: empresa (nome/menção), concorrente, setor, palavra-chave — reaproveita `NewsItem`/`NewsCluster` de `catalogo_noticias` como fonte de dado, com um índice de busca por esses critérios.
3. Painel corporativo: lista de itens monitorados, resumos executivos, histórico de acontecimentos por critério monitorado.
4. Alertas (e-mail, mesmo mecanismo de `newsletter.md`) quando novo conteúdo bate em um critério monitorado.
5. Relatórios periódicos (semanal/mensal, resumo consolidado dos critérios monitorados de uma organização).
6. Múltiplos usuários por organização, com permissões (admin da organização vs. usuário comum — não confundir com `papel` de `identidade/`, é uma dimensão de permissão dentro da organização).
7. Planos corporativos configuráveis (mesmo padrão de `Plan`/preço editável de `assinatura-premium.md`, mas para o contexto B2B).

## Requisitos não-funcionais
- Isolamento estrito de dados entre organizações diferentes (usuário de uma organização nunca vê monitoramento de outra).
- Reaproveita a infraestrutura de assinatura (`assinatura/`) para cobrança do plano corporativo, não duplica lógica de pagamento.

## Fora de escopo
- Monitoramento de legislação/temas regulatórios (BRD menciona "quando houver fontes adequadas" — nenhuma fonte regulatória está integrada em `catalogo_noticias` hoje).
- Onboarding comercial/vendas (processo humano, não parte do software).

## Critérios de sucesso
- Uma organização consegue configurar monitoramento e ver resultados relevantes sem intervenção manual da equipe do produto.
- Dados de uma organização nunca vazam para outra.

## Questões em aberto
- Definição exata dos limites/recursos de cada camada comercial (Basic/Pro/Enterprise, BRD §20) — parametrizável, valores iniciais a definir com produto/vendas.
