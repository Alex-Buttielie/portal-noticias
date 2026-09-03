# Spec: Cadastro, Autenticação e Onboarding

> **Status:** já tem uma execução concluída e aprovada (`run-20260901-2135-cadastro-auth`), cobrindo o backend de API descrito abaixo (cadastro e-mail/senha, verificação de e-mail, login social Google, login/logout/recuperação de senha, onboarding). Sem frontend ainda. Detalhes de "como rodar" estão no `README.md` da raiz do repositório. Detalhes completos da execução (decisões, testes, revisão) em `agentic-framework/state/run-20260901-2135-cadastro-auth/implementation-history.md`.

## Contexto de negócio
BRD seção 4 (Público-Alvo Prioritário) e seção 8 (Retenção e Encantamento do Premium — onboarding). Ver também `ARCHITECTURE.md` seção 3 (entidade `User`) e seção 4 (papéis/permissões).

## Problema / oportunidade
O sistema ainda não existe. Sem cadastro/login e sem captura de preferências no onboarding, nenhuma outra feature (feed personalizado, gating Free/Premium, assinatura) tem uma base de usuário para operar sobre.

## Histórias de usuário
- Como visitante, eu quero me cadastrar com e-mail/senha ou login social (Google), para acessar recursos que exigem conta.
- Como usuário recém-cadastrado, eu quero informar meus interesses, localidade e canal de comunicação preferido no onboarding, para receber conteúdo relevante desde o início.
- Como usuário, eu quero fazer login e logout de forma simples, para acessar minha conta em diferentes sessões.

## Requisitos funcionais
1. Cadastro por e-mail/senha com verificação de e-mail antes de liberar funcionalidades que dependem de identidade confirmada.
2. Login social via Google (mínimo), usando biblioteca madura de OAuth (não implementação própria do protocolo).
3. Fluxo de onboarding pós-cadastro: perguntar interesses (categorias), localidade de interesse e canal preferido (e-mail, push — o que estiver disponível no MVP). Deve ser pulável, mas o sistema deve reter que foi pulado para reapresentar depois.
4. Todo usuário novo nasce com papel `free` (ver `ARCHITECTURE.md` seção 4).
5. Login/logout, recuperação de senha.
6. Registrar consentimento de comunicação/dados no cadastro, conforme legislação aplicável (LGPD).

## Requisitos não-funcionais
- LGPD: consentimento explícito e auditável; usuário deve poder solicitar exclusão de seus dados.
- Senhas nunca em texto plano; usar hashing padrão da framework escolhida (Django: PBKDF2/Argon2 built-in).
- Sessão/token deve expirar e ser renovável sem exigir novo login constante.

## Fora de escopo
- Autenticação de jornalistas credenciados com fluxo diferenciado (fica para a spec de Credenciamento, fase futura).
- Múltiplos usuários por organização / SSO corporativo (fase B2B).
- Outros provedores de login social além de Google (podem ser adicionados depois sem redesenho, dado que a integração já usa uma lib plugável).

## Critérios de sucesso
- Um visitante consegue se cadastrar e chegar ao feed personalizado (ainda que com poucos dados) em menos de 3 passos após o cadastro.
- Taxa de conclusão do onboarding (não abandono) é mensurável.

## Questões em aberto
- Lista definitiva de canais de comunicação disponíveis no MVP (só e-mail, ou também push/SMS?) — impacta o formulário de onboarding.
