# Spec: Ingestão e Curadoria de Notícias

## Contexto de negócio
BRD seção 10 (Conteúdo e Estratégia Editorial) e seção 18 (Direitos Autorais e Compliance). Ver `ARCHITECTURE.md` seções 3 (`NewsItem`/`NewsCluster`), 6 (`NewsSourceProvider`, `SummarizationProvider`) e 7 (rastreabilidade de fonte, custo de IA).

## Problema / oportunidade
Sem um pipeline de ingestão que colete, deduplique, classifique e agrupe notícias de múltiplas fontes, não há conteúdo para o usuário consumir — este é o núcleo do MVP conforme roadmap do BRD (seção 31: "Validar descoberta, curadoria e consumo de notícias").

## Histórias de usuário
- Como usuário, eu quero ver notícias de múltiplas fontes agrupadas por acontecimento, para não precisar visitar vários portais.
- Como usuário, eu quero identificar claramente a fonte original de cada notícia, para confiar na informação e poder acessá-la na origem.
- Como equipe editorial, eu quero que conteúdo duplicado ou de baixo valor seja filtrado automaticamente, para manter a qualidade do feed sem trabalho manual constante.

## Requisitos funcionais
1. Ingerir notícias de fontes configuradas (RSS/API), via `NewsSourceProvider`, respeitando termos de uso de cada fonte (BRD §18).
2. Preservar URL e identificação da fonte original em todo `NewsItem` — nunca reproduzir o texto integral da matéria de terceiros.
3. Gerar resumo próprio via `SummarizationProvider` — não republicar o texto original como resumo.
4. Detectar duplicidade/mesma cobertura de um acontecimento e agrupar em `NewsCluster`.
5. Classificar relevância e separar notícias urgentes de normais.
6. Permitir fila de revisão humana para casos sensíveis ou de alta relevância antes de publicação automática (flag `status de revisão`).
7. Manter equilíbrio entre categorias (evitar concentração excessiva em um único assunto no agrupamento/priorização).
8. Registrar, por chamada ao `SummarizationProvider`, custo/uso para observabilidade (BRD §30 — risco de custo de IA).

## Requisitos não-funcionais
- Direitos autorais: qualquer falha em preservar a atribuição de fonte é um bug bloqueante, não um "nice to have".
- Observabilidade: taxa de deduplicação, volume ingerido por fonte, tempo entre publicação na fonte e disponibilização no portal.
- O pipeline deve ser resiliente a fontes fora do ar (uma fonte falhando não pode travar a ingestão das demais).

## Fora de escopo
- Radar de tendências por localização (fase "Inteligência" do roadmap, spec futura).
- Curadoria de conteúdo de opinião/análise de autores credenciados (fase Comunidade).
- Mecanismo de correção/remoção de conteúdo publicado por denúncia de terceiros (depende de governança editorial completa, fase futura) — para o MVP, correção/remoção é operação manual do admin sobre o `NewsItem`.

## Critérios de sucesso
- Um mesmo acontecimento coberto por 3+ fontes aparece como um único cluster com as fontes listadas, não como notícias repetidas.
- Nenhum `NewsItem` publicado sem fonte original rastreável.

## Questões em aberto
- Lista concreta de fontes/RSS/APIs a integrar no MVP (ver `ARCHITECTURE.md` seção 8, item 5) — bloqueia a primeira execução real deste módulo.
- Threshold de "alta relevância" que aciona revisão humana obrigatória — precisa de definição de produto, não só técnica.
