# Spec: Moderação, Reputação e Governança Editorial

## Contexto de negócio
BRD seção 15 (Modelo de Reputação), seção 16 (Política de Respeito e Moderação) e seção 17 (Governança Editorial) — tratadas juntas por serem profundamente interligadas (reputação alimenta prioridade de moderação; moderação alimenta reputação; governança define as regras que ambas aplicam). Consumida por `comunidade-blog.md` e `credenciamento-jornalistas.md`.

## Problema / oportunidade
Sem moderação e reputação, a comunidade fica exposta a abuso (ameaças, assédio, spam) e sem mecanismo de confiança para diferenciar autores/usuários consistentes de problemáticos — e sem governança, não há regra pública e auditável de como decisões editoriais são tomadas.

## Histórias de usuário
- Como leitor, eu quero denunciar um comentário/publicação abusivo, para que a equipe de moderação avalie.
- Como moderador, eu quero uma fila priorizada de denúncias, para agir rápido nos casos mais graves.
- Como administrador, eu quero ver o histórico de reputação de um autor/usuário, para decisões de moderação informadas.
- Como leitor, eu quero acessar a política editorial pública, para entender os critérios de relevância/destaque/correção do produto.

## Requisitos funcionais
1. Sistema de denúncia (comentário, publicação, perfil) com motivo estruturado (ameaça, assédio, dado pessoal, spam, outro).
2. Fila de moderação, priorizável por severidade/reputação do denunciado.
3. Ações de moderação: aviso, remoção de conteúdo, bloqueio temporário, bloqueio permanente — todas registradas (quem, quando, motivo).
4. Canal de recurso: usuário moderado pode contestar a decisão (fica registrado, não precisa de fluxo de aprovação automática).
5. Modelo de reputação: pontuação/nível interno por usuário/autor, calculado a partir de histórico de cumprimento de regras, denúncias procedentes, ações de moderação recebidas, consistência de identificação opinião/análise (autores), histórico de correções.
6. Reputação NUNCA é o único critério de decisões sensíveis (BRD §15) — toda suspensão/revogação de credenciamento exige decisão humana, reputação só prioriza/sinaliza.
7. Página de política editorial pública (conteúdo estático/CMS simples: critérios de relevância, destaque, correção, retirada de conteúdo, conflito de interesse).
8. Procedimento de correção/retirada de conteúdo publicado, com rastro público (nota de correção visível, não apagar silenciosamente).

## Requisitos não-funcionais
- Toda ação de moderação é auditável (BRD §17 — auditoria de alterações relevantes).
- Rate limiting básico contra spam na comunidade (BRD §30, risco "Spam na comunidade").

## Fora de escopo
- Detecção automática de conteúdo abusivo por IA/ML — moderação nesta execução é humana, acionada por denúncia.
- Painel de analytics de moderação (métricas agregadas) — fica para `painel-metricas-negocio.md`.

## Critérios de sucesso
- Nenhuma decisão de suspensão/revogação acontece sem revisão humana e sem registro auditável.
- Um usuário consegue denunciar conteúdo e recebe (mesmo que de forma simples) confirmação de que a denúncia foi recebida.

## Questões em aberto
- Composição exata da fórmula de reputação (pesos de cada fator) — fica como parâmetro configurável, valores iniciais a calibrar com produto/operação.
