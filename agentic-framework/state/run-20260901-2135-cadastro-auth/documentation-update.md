<!--
CONTRACT: documentation-update
DONO: documenter
QUANDO É CRIADO: depois que testes passam e a revisão (se exigida) está aprovada.
PARA ONDE VAI A INSTÂNCIA: agentic-framework/state/run-<run_id>/documentation-update.md
-->

# Documentation Update — 20260901-2135-cadastro-auth

## Metadados
- **run_id:** 20260901-2135-cadastro-auth
- **Baseado em:** implementation-history.md (20260901-2135-cadastro-auth), code-review-contract.md (veredito final: approve_with_comments)

## Documentos afetados
| Documento | Tipo de mudança | Resumo |
|---|---|---|
| `README.md` (raiz do projeto) | Atualização + nova seção | Removida a afirmação de que "o código-fonte do portal ainda não foi iniciado" (estava desatualizada — havia código novo em `backend/`). Adicionada uma linha em "Onde começar" apontando para `backend/`. Adicionada uma nova seção "Como rodar o backend" com os passos reais para rodar o projeto localmente (venv, `requirements.txt`, `.env` a partir de `.env.example`, `migrate`, `runserver`, `pytest`) e uma tabela com os 9 endpoints reais de `identidade/` (cadastro, verificação de e-mail, login, logout, recuperação/redefinição de senha, login Google, onboarding GET/PATCH). O parágrafo de "Como pedir uma tarefa de desenvolvimento" também foi ajustado para não repetir a afirmação de que nada foi construído ainda. |
| `agentic-framework/specs/cadastro-autenticacao-onboarding.md` | Nota informativa (não é doc voltada ao usuário final, é rastreabilidade interna) | Adicionada uma nota de status logo no topo da spec, indicando que já existe uma execução concluída e aprovada cobrindo essa spec, sem frontend, com link para o histórico da execução. Não reescrevi a spec em si (requisitos/critérios de sucesso continuam como estavam, pois ainda não estão 100% cobertos — ex.: onboarding com canais além de e-mail ainda é questão em aberto). |

## Sem impacto em documentação?
Não se aplica — houve documentos afetados (ver tabela acima). Não há CHANGELOG separado neste projeto ainda; ver seção "Entrada de changelog" abaixo para a justificativa de não criar um agora.

## Exemplos/snippets novos ou atualizados
- Bloco de comandos "Como rodar o backend" em `README.md` (venv, instalação, cópia do `.env.example`, migrate, runserver, pytest) — baseado nos comandos reais que o executor/tester/remediator efetivamente rodaram e validaram em `implementation-history.md` (com a única diferença documentada de que, no ambiente do próprio agentic-framework, as validações rodaram contra SQLite por falta de PostgreSQL disponível; o README recomenda PostgreSQL como padrão e menciona o atalho SQLite como conveniência, não como caminho recomendado).
- Tabela de endpoints em `README.md`, construída lendo diretamente `backend/identidade/urls.py`, `backend/identidade/views.py` e `backend/identidade/serializers.py` (não a partir do `implementation-contract.md`, que descreve a intenção original — algumas rotas mudaram de forma sutil na implementação real, ex.: `POST /api/auth/google/` usa `id_token`, e onboarding é `GET`/`PATCH` em vez de `GET/POST`).

## Entrada de changelog
Este projeto não mantém um `CHANGELOG.md` (não existe no repositório e não há convenção estabelecida em nenhum outro documento de processo). Não criei um agora porque isso seria uma decisão de processo maior que uma atualização pontual de documentação — não introduzi esse artefato para não estabelecer uma convenção nova sem alinhamento explícito do time/usuário. Se o projeto adotar um CHANGELOG no futuro, esta execução (primeiro backend do repositório: módulo `identidade/` com cadastro, verificação de e-mail, login social Google, login/logout, recuperação de senha e onboarding) seria a primeira entrada natural dele.

## Verificação
- [x] Nenhum exemplo/trecho de documentação existente ficou contraditório com a mudança — a única contradição identificada era a frase "o código-fonte do portal ainda não foi iniciado" em `README.md`, corrigida. Os documentos ARCHITECTURE.md, agentic-framework/README.md e as demais specs não fazem afirmações sobre o estado de implementação do código, então não precisaram de ajuste.
- [x] Build/lint de documentação rodado (se o projeto tiver um) — não aplicável: não há `package.json`, `markdownlint` ou qualquer ferramenta de build/lint de documentação configurada neste repositório (verificado por busca no diretório raiz).

## Observações adicionais (não fazem parte do template, mas relevantes para o `orchestrator`/usuário)
- Não documentei o fluxo de login social do Google como "pronto para produção" ponta a ponta — o README deixa claro que `GOOGLE_OAUTH_CLIENT_ID`/`SECRET` precisam ser preenchidos e que os demais endpoints funcionam sem eles; a validação real foi feita com o provider mockado (não há credenciais reais de Google Cloud neste ambiente).
- Não documentei nenhum comportamento de frontend, nem de integração com provedor de e-mail transacional real (a doc é explícita: em dev, e-mails são impressos no console).
- O finding minor pendente da revisão (Finding 7 — `User.MultipleObjectsReturned` não tratado em um cenário raro de corrida em `GoogleLoginView`) é um detalhe interno de robustez, não um comportamento de uso da API — não incluí isso na documentação voltada ao desenvolvedor que só quer rodar o projeto; fica registrado apenas em `implementation-history.md`/`code-review-contract.md` para quem for tratá-lo depois.
