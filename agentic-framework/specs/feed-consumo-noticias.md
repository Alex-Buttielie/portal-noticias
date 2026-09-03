# Spec: Feed e Consumo de Notícias

## Contexto de negócio
BRD seção 1-2 (Resumo Executivo, Proposta de Valor) e seção 7 (Free x Premium — linha "Notícias", "Categorias", "Busca", "Resumo"). Depende de `ingestao-curadoria-noticias.md` já ter `NewsItem`/`NewsCluster` disponíveis.

## Problema / oportunidade
A curadoria por si só não entrega valor sem uma experiência de consumo (feed, busca, categorias) onde o usuário efetivamente encontra e lê o que é relevante para ele.

## Histórias de usuário
- Como usuário, eu quero navegar por um feed de notícias organizadas por categoria, para encontrar rapidamente assuntos do meu interesse.
- Como usuário, eu quero buscar notícias por palavra-chave, para encontrar algo específico.
- Como usuário, eu quero ler o resumo de um acontecimento e, se quiser, ir até a fonte original, para decidir o quanto vou aprofundar.

## Requisitos funcionais
1. Feed principal listando `NewsCluster`/`NewsItem` mais relevantes, com categoria e indicação de urgente/normal.
2. Filtro por categoria.
3. Busca textual por palavra-chave.
4. Página de detalhe do acontecimento: resumo, lista de fontes agrupadas com link para cada uma, categoria, timestamp.
5. Publicidade exibida para usuário `free`/visitante, ausente para `premium` (ligação com `gating-free-premium.md`).
6. Disponível tanto para visitante quanto para usuário autenticado (Free/Premium) — cadastro não é obrigatório para ler o feed público básico.

## Requisitos não-funcionais
- Tempo de carregamento do feed deve ser mensurável desde o MVP, mesmo sem meta numérica definida ainda (base para otimizações futuras).
- Acessibilidade básica (contraste, navegação por teclado) no feed e na busca.

## Fora de escopo
- Linha do tempo de assuntos de longa duração (mencionada no BRD §22, tratar como extensão futura do agrupamento, não do MVP).
- Personalização avançada do feed (ordenação por interesse do usuário) — fica em `gating-free-premium.md`, que define o que é "limitado" vs "completo".
- Newsletter (BRD §27) — spec futura própria.

## Critérios de sucesso
- Um usuário consegue, a partir do feed, entender o principal acontecimento do dia sem visitar outro portal (critério de sucesso do próprio BRD, seção 32).
- Um usuário consegue identificar claramente a fonte original de qualquer notícia que ler.

## Questões em aberto
- Definição de "categorias" iniciais (lista fechada para o MVP) — necessário para o filtro de categoria funcionar.
