# Spec: Radar de Tendências por Localização

## Contexto de negócio
BRD seção 11 (Radar de Tendências por Localização) — diferencial citado desde a proposta de valor (§2). Estende `feed-consumo-noticias.md` com filtro geográfico e métricas de tendência.

## Problema / oportunidade
O feed atual só filtra por categoria/busca textual — não há como um usuário acompanhar o que está em alta numa localidade específica (país/estado/cidade/município), um dos diferenciais centrais do produto.

## Histórias de usuário
- Como usuário, eu quero selecionar uma localidade (país, estado, cidade ou município) e ver os assuntos em alta ali, para acompanhar o que importa na minha região.
- Como usuário, eu quero salvar/seguir uma localidade, para acessá-la rapidamente depois.
- Como usuário, eu quero ver a evolução do interesse por um assunto ao longo do tempo, não só um retrato do momento.

## Requisitos funcionais
1. Campo de localização no `NewsItem` (país/estado/cidade/município, quando extraível da matéria/fonte) — pode exigir enriquecer o pipeline de `catalogo_noticias` para inferir localidade (ex.: da fonte, de menções no título/resumo).
2. Endpoint de radar: dado um recorte geográfico, retorna assuntos em alta (clusters com maior número de itens/fontes na janela recente), quantidade de notícias relacionadas, principais categorias.
3. Evolução do interesse: série temporal simples (contagem de itens por dia/semana) para um assunto/localidade.
4. Salvar/seguir localidade (por usuário autenticado).
5. Acesso ao acontecimento agrupado a partir do radar (reaproveita `feed-consumo-noticias.md`, detalhe de cluster).
6. Distinguir, quando possível, cobertura jornalística (quantidade de notícias) de volume de busca/interesse real — NÃO apresentar estimativa como número oficial quando a fonte não permitir (BRD §11, restrição explícita).

## Requisitos não-funcionais
- Radar avançado é recurso Premium (parcialmente limitado no Free) — integrar com `gating-free-premium.md` via uma nova chave de `FeatureLimit` (ex.: `radar_avancado`).

## Fora de escopo
- Dados de busca externos (Google Trends etc.) — nesta execução, "interesse" é aproximado por volume de cobertura jornalística agrupada, não por dado de busca real (documentar essa limitação na UI, conforme restrição do BRD §11).
- Geolocalização automática do usuário (opt-in) — usuário escolhe manualmente a localidade.

## Critérios de sucesso
- O radar apresenta tendências úteis e compreensíveis (critério de sucesso do próprio BRD, seção 32).
- Nenhuma métrica de "interesse" é exibida como se fosse um número oficial de busca quando não é.

## Questões em aberto
- Fonte de dado de localidade: depende de as fontes RSS trazerem essa informação de forma confiável, ou de inferência textual — decisão técnica a validar quando o pipeline de ingestão for testado com fontes reais.
