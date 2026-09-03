# Task Plan — 20260902-1448-frontend-mvp-web

## Metadados
- **run_id:** 20260902-1448-frontend-mvp-web
- **Data de abertura:** 2026-09-02
- **Solicitado por:** usuário ("crie as interfaces web necessárias para meu sistema" — confirmado via pergunta direta: frontend do que já existe primeiro, antes do restante do BRD)
- **Specs de origem:** `cadastro-autenticacao-onboarding.md`, `feed-consumo-noticias.md`, `assinatura-premium.md` (as 3 specs cujo backend já está implementado e cuja UI o usuário quer ver funcionando)

## Objetivo
Ao final desta execução, deve existir uma aplicação web (Next.js/React, conforme `ARCHITECTURE.md`) funcional consumindo as APIs já implementadas: cadastro/login/onboarding, feed de notícias com busca/categoria e página de detalhe, e assinatura Premium (planos, assinar, status, cancelar, histórico de pagamentos) — permitindo a um usuário real usar o produto pela primeira vez sem chamar a API diretamente.

## Escopo

### Dentro do escopo
- Scaffold do projeto Next.js (App Router, TypeScript) em `frontend/`.
- Cliente de API central (`lib/api.ts`) cobrindo os endpoints já existentes dos 3 módulos.
- Contexto de autenticação (token em `localStorage`, estado de usuário logado/plano) compartilhado entre páginas.
- Páginas: cadastro, login, verificar e-mail, recuperar/redefinir senha, onboarding, feed (home), detalhe de notícia (cluster e item), planos/assinatura, minha conta (status + histórico + cancelar).
- Layout compartilhado (cabeçalho com navegação, estado de login, indicador Free/Premium).
- Estilo simples via CSS puro (sem framework de CSS adicional) — reduz superfície de risco de build sem poder validar por execução.

### Fora do escopo (explicitamente)
- Login social (Google) — não há credenciais reais configuradas; o botão pode existir na UI mas desabilitado/placeholder.
- Qualquer módulo do BRD ainda sem backend (Comunidade, Credenciamento, Radar, B2B, Newsletter, Landing Page/Lista de Espera) — frontend deles só depois que o backend existir.
- Testes automatizados de frontend (Jest/Playwright) — dado que nem o build básico pode ser validado por execução nesta sessão, escrever testes que também não podem rodar teria valor limitado; passa a ser prioridade assim que a execução voltar.
- Design visual refinado/identidade de marca (BRD §28 ainda não definido) — interface funcional e limpa, não uma peça de design final.

## Suposições assumidas
- **Next.js App Router + TypeScript**, sem framework de CSS (Tailwind etc.) — ARCHITECTURE.md já recomendava Next.js; a escolha de não usar Tailwind é para reduzir passos de build (PostCSS/config adicional) que não posso validar por execução nesta sessão. Pode ser adotado depois, quando a execução voltar e puder ser testado.
- **`NEXT_PUBLIC_API_BASE_URL`** configurável via `.env.local`, default `http://localhost:8000` — mesma porta padrão do `manage.py runserver` já documentado no `README.md`.
- **Token de API em `localStorage`** (não cookie httpOnly) — mais simples de implementar sem um backend-for-frontend, aceitável para MVP; nota de segurança (XSS) registrada como follow-up para quando o produto crescer.

## Restrições
- Consumir EXCLUSIVAMENTE os endpoints já implementados e documentados nos `implementation-history.md` dos runs de `identidade`, `feed` e `assinatura` — não inventar endpoints novos no frontend sem existirem no backend.
- Sem framework de UI pesado (Material UI, Chakra, etc.) — aumentaria a superfície de dependências não validáveis por execução nesta sessão.

## Divisão de trabalho
| Etapa | Agente responsável | Entrada esperada | Saída esperada |
|---|---|---|---|
| 1 | executor | implementation-contract.md | código + implementation-history.md |
| 2 | tester | implementation-contract.md | veredito passed/failed/blocked |
| 3 | reviewer | diff do executor | code-review-contract.md |
| 4 | remediator (se necessário) | code-review-contract.md | correções + revalidação |
| 5 | documenter | implementation-history.md | documentation-update.md + docs atualizadas |
| 6 | historian | todos os artefatos acima | report.md + entrada em HISTORY.md |

## Critérios de aceite (nível de negócio/produto)
1. Um visitante consegue se cadastrar, verificar e-mail (via link), fazer login e completar/pular o onboarding, tudo pela interface web.
2. Um visitante ou usuário logado consegue navegar pelo feed, filtrar por categoria, buscar por palavra-chave, e abrir o detalhe de uma notícia com todas as fontes.
3. Um usuário logado consegue ver os planos disponíveis, assinar um, ver o status da própria assinatura, ver o histórico de pagamentos, e cancelar — tudo sem sair da interface.
4. O indicador de anúncio/Premium reflete corretamente o plano do usuário (mesmo que a UI não implemente anúncios de verdade, o estado deve estar visível/correto).

## Riscos identificados
| Risco | Impacto | Mitigação |
|---|---|---|
| Nenhuma ferramenta de execução/build/preview disponível nesta sessão — frontend é mais sensível a erros de sintaxe (JSX/TS) do que Python | Alto | Escrever de forma conservadora (componentes simples, sem padrões avançados de TS/JSX que aumentem risco de erro sutil), revisão manual linha a linha antes de finalizar cada arquivo |
| Endpoints reais do backend também não foram validados por execução ainda (4 dos 5 módulos) — se houver um bug real no backend, o frontend vai herdar/expor esse problema | Alto | Já registrado nos runs de backend; este run não pode compensar isso, só reforça a prioridade de rodar a suíte assim que possível |

## Dependências
- Depende do backend já implementado (`identidade`, `feed`, `assinatura`) — código existe, mas ainda não validado por execução.
