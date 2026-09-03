# Task Plan — 20260902-1534-frontend-comunidade-credenciamento

Solicitado por: usuário ("aplique DDD... e siga na implementação do meu MVP"). Formato conciso.

## Objetivo
Frontend de Credenciamento (`/jornalista/solicitar`, `/jornalista/status`) e Comunidade (`/comunidade`, `/comunidade/nova`, `/comunidade/[id]`, `/autor/[id]`) — fecha o fluxo "jornalista se credencia → publica análise → leitor lê e comenta" de ponta a ponta.

## Nota sobre DDD
A partir desta execução, disciplina reforçada explicitamente: toda mutação de estado no backend continua passando por um único serviço de domínio por bounded context (já era o padrão desde `assinatura`/`moderacao`/`b2b`); nenhuma view escreve direto num modelo. Não houve refatoração retroativa dos 12 apps já implementados — seria uma mudança grande e arriscada em código já não-validado; a aplicação é para código novo a partir de agora.

## Lacuna de backend encontrada e corrigida nesta execução
`comunidade` não tinha endpoint de "buscar publicação por id" (só listagem) — necessário para a tela de detalhe funcionar. Adicionado `GET /api/comunidade/publicacoes/<id>/` (`PublicacaoDetailView`): publicada é pública, rascunho/enviado só visível ao próprio autor. 2 testes novos.

## Critérios de aceite
1. Usuário autenticado envia solicitação de credenciamento com upload de arquivo (multipart) pela UI.
2. Usuário vê o status da própria solicitação.
3. Qualquer visitante navega pela lista de publicações da comunidade e abre o detalhe.
4. Usuário autenticado comenta numa publicação.
5. Jornalista credenciado (aprovado) consegue criar e publicar uma análise pela UI.
6. Usuário autenticado segue/deixa de seguir um autor a partir do perfil público dele.
