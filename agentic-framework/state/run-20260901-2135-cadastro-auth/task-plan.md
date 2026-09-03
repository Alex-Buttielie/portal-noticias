# Task Plan — 20260901-2135-cadastro-auth

## Metadados
- **run_id:** 20260901-2135-cadastro-auth
- **Data de abertura:** 2026-09-01
- **Solicitado por:** usuário, via `agentic-run` (referenciando a spec abaixo)
- **Spec de origem:** `agentic-framework/specs/cadastro-autenticacao-onboarding.md`

## Objetivo
Ao final desta execução, um usuário deve conseguir se cadastrar (e-mail/senha ou Google), confirmar e-mail, fazer login/logout, recuperar senha e completar (ou pular) um onboarding que captura interesses, localidade e canal preferido — tudo via API backend testável, com papel `free` atribuído por padrão.

## Escopo

### Dentro do escopo
- Scaffold inicial do backend: projeto Django + Django REST Framework, configuração de PostgreSQL, estrutura do módulo `identidade/` (ver `ARCHITECTURE.md` seção 2).
- Modelo `User` (ver `ARCHITECTURE.md` seção 3): email, senha/hash, nome, papel (`free` default), preferências de onboarding.
- Cadastro por e-mail/senha com verificação de e-mail antes de liberar funcionalidades que dependem de identidade confirmada.
- Login social via Google usando `django-allauth`.
- Endpoints de login, logout, recuperação de senha.
- Endpoint(s) de onboarding: capturar interesses, localidade, canal preferido; pulável, com flag para reapresentar depois.
- Registro de consentimento de comunicação/dados (LGPD) no cadastro.
- Testes automatizados cobrindo os critérios de aceite abaixo.

### Fora do escopo (explicitamente)
- Interface web (Next.js) consumindo essa API — fica para uma execução `agentic-run` separada, focada em frontend, depois que a API estiver estável.
- Autenticação diferenciada de jornalistas credenciados (fase Credenciamento, sem spec ainda).
- SSO corporativo / múltiplos usuários por organização (fase B2B).
- Provedores sociais além de Google.
- Feed, gating Free/Premium e assinatura (specs próprias, dependem deste módulo mas não são construídas aqui).

## Suposições assumidas
- **Escopo backend-only nesta execução** (sem frontend) — motivo: nenhum código existe no repositório ainda; combinar scaffold de backend + frontend + auth completa em uma única execução tornaria o diff grande demais para revisão (review-triggers.md já sinaliza diffs >300 linhas como gatilho de revisão, e este run já tem múltiplos gatilhos). Preferi entregar a API sólida e testada primeiro; a UI consome uma API já validada.
- **`django-allauth` para login social** — motivo: é a biblioteca padrão de mercado para isso em Django, evita implementação própria de OAuth (risco de segurança), já registrada como dependência nova a ser aprovada no `implementation-contract.md`.

## Restrições
- Stack obrigatória: Python/Django + Django REST Framework, PostgreSQL (`ARCHITECTURE.md` seção 1).
- LGPD: consentimento explícito e auditável (`ARCHITECTURE.md` seção 7, spec seção "Requisitos não-funcionais").
- Senhas nunca em texto plano (hashing padrão do Django).

## Divisão de trabalho
| Etapa | Agente responsável | Entrada esperada | Saída esperada |
|---|---|---|---|
| 1 | executor | implementation-contract.md | código + implementation-history.md |
| 2 | tester | implementation-contract.md | veredito passed/failed/blocked |
| 3 | reviewer (obrigatório — ver review-triggers.md) | diff do executor | code-review-contract.md |
| 4 | remediator (se necessário) | code-review-contract.md | correções + revalidação |
| 5 | documenter | implementation-history.md | documentation-update.md + docs atualizadas |
| 6 | historian | todos os artefatos acima | report.md + entrada em HISTORY.md |

## Critérios de aceite (nível de negócio/produto)
1. Um visitante consegue se cadastrar com e-mail/senha e recebe um e-mail de verificação antes de ter a conta totalmente ativa.
2. Um visitante consegue se cadastrar/logar via Google.
3. Um usuário cadastrado consegue fazer login, logout e recuperar a senha esquecida.
4. Após o cadastro, o usuário passa por um onboarding que captura interesses, localidade e canal preferido — e pode pular essa etapa sem travar o uso da conta.
5. Todo usuário novo nasce com papel `free`.
6. O consentimento de dados/comunicação é registrado no cadastro e é auditável (existe registro de quando e o quê foi aceito).
7. Nenhuma senha é armazenada em texto plano.

## Riscos identificados
| Risco | Impacto | Mitigação |
|---|---|---|
| Primeiro código do projeto — decisões de scaffold (estrutura de pastas, settings) ficam implícitas em vez de documentadas | Médio | `implementation-history.md` deve registrar a estrutura criada; `documenter` atualiza README com "como rodar o projeto" |
| Integração OAuth Google mal configurada expõe risco de segurança (ex: validação incorreta de token) | Alto | Revisão obrigatória (gatilho de autenticação); usar fluxo padrão do `django-allauth`, não implementação manual |
| Falta de credenciais reais do Google Cloud (Client ID/Secret) para testar o fluxo social ponta a ponta | Médio | Tester usa mocks/sandbox para o fluxo OAuth; teste de integração real fica marcado como follow-up manual |

## Dependências
- Nenhuma decisão humana pendente bloqueia esta execução especificamente (diferente de `ingestao-curadoria-noticias.md` e `assinatura-premium.md`, que dependem de provedores externos ainda não escolhidos).
- Credenciais reais do Google OAuth (Client ID/Secret) precisarão ser fornecidas pelo usuário antes de testar o login social em ambiente real — não bloqueia a implementação, bloqueia apenas o teste ponta a ponta com o provedor real.
