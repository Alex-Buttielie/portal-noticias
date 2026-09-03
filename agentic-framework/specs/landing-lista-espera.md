# Spec: Landing Page e Lista de Espera

## Contexto de negócio
BRD seção 25 (Landing Page) e seção 26 (Lista de Espera) — parte do plano de lançamento (§23).

## Problema / oportunidade
Antes/durante o lançamento, o produto precisa de uma página pública de captação (proposta de valor, exemplos, CTA) e um mecanismo de captura de interesse (lista de espera) segmentável para o lançamento.

## Histórias de usuário
- Como visitante, eu quero entender a proposta de valor do produto numa página simples, antes de ele estar disponível/completo.
- Como visitante interessado, eu quero me cadastrar na lista de espera informando meus interesses e localidade, para ser avisado do lançamento.

## Requisitos funcionais
1. Página pública (`/`  quando o produto ainda não está em lançamento geral, ou uma rota dedicada `/lista-de-espera`) com: headline, proposta de valor, "como funciona" em 3 passos, exemplo de notícia agrupada/resumo/radar, benefícios Free/Premium, CTA para lista de espera, FAQ.
2. Formulário de lista de espera: nome, e-mail, interesses, localidade de interesse, preferência de canal, aceite de comunicação conforme legislação aplicável.
3. Registro da data de entrada (para ordenação/priorização de convite).
4. Segmentação para lançamento (admin consegue filtrar a lista por interesse/localidade para campanhas de convite).

## Requisitos não-funcionais
- Mesmo tratamento de consentimento LGPD já usado em `identidade/` (timestamp + versão dos termos aceitos).
- Formulário funciona sem exigir conta/login (é justamente para quem ainda não é usuário).

## Fora de escopo
- Identidade visual/design final de marca (BRD §28, ainda não definido) — landing funcional, não uma peça de marketing finalizada.
- Envio de convite de lançamento em si (fica como operação manual do admin usando o export/segmentação, não um fluxo automatizado nesta execução).

## Critérios de sucesso
- Um visitante consegue se cadastrar na lista de espera em menos de 1 minuto.
- O admin consegue segmentar a lista por interesse/localidade.

## Questões em aberto
- Nenhuma — spec já é acionável sem decisão de produto adicional (marca/identidade visual final fica explicitamente fora de escopo).
