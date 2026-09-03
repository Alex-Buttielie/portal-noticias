# Implementation Contract — 20260901-2135-cadastro-auth

## Metadados
- **run_id:** 20260901-2135-cadastro-auth
- **Deriva de:** task-plan.md (20260901-2135-cadastro-auth)
- **Versão do contrato:** 1

## O que deve ser construído
Backend Django (com Django REST Framework) para o módulo `identidade/` do Portal de Notícias: scaffold do projeto, modelo de usuário customizado, cadastro por e-mail/senha com verificação de e-mail, login social via Google (`django-allauth`), login/logout/recuperação de senha via API, e endpoint(s) de onboarding (interesses, localidade, canal preferido, pulável). Sem frontend nesta execução.

## Áreas/arquivos esperados
- `backend/` (raiz do novo projeto Django — nome de diretório e do projeto Django a critério do executor, documentar em `implementation-history.md`)
- `backend/config/` — settings, urls raiz, configuração de PostgreSQL, `django-allauth`
- `backend/identidade/` (app Django) — models (`User` customizado), serializers, views/endpoints, urls
- `backend/identidade/migrations/`
- `backend/requirements.txt` (ou `pyproject.toml`, a critério do executor) — listar toda dependência nova aqui
- `backend/identidade/tests/`
- `README.md` (raiz do projeto) — seção "como rodar o backend" (delegar ao `documenter`, não ao executor)

## Interfaces afetadas
Novas interfaces (nada pré-existente é quebrado, pois é o primeiro código do repositório):
- `POST /api/auth/cadastro/` — cadastro e-mail/senha
- `POST /api/auth/verificar-email/` — confirmação de e-mail via token
- `GET/POST /api/auth/google/` (ou rota equivalente do `django-allauth`) — login/cadastro social
- `POST /api/auth/login/`, `POST /api/auth/logout/`
- `POST /api/auth/recuperar-senha/`, `POST /api/auth/redefinir-senha/`
- `GET/PATCH /api/onboarding/` — capturar/atualizar interesses, localidade, canal preferido; suportar "pular"
- Modelo de dados: tabela `User` com campo `papel` (`free` por padrão), campos de onboarding, e registro de consentimento (timestamp + versão dos termos aceitos)

## Critérios de aceite (técnicos, testáveis)
1. Dado um e-mail e senha válidos não cadastrados, quando `POST /api/auth/cadastro/`, então a conta é criada com `papel=free`, `email_verificado=False`, e um e-mail/token de verificação é gerado (pode ser mockado em teste, mas o mecanismo deve existir).
2. Dado um token de verificação válido, quando `POST /api/auth/verificar-email/`, então `email_verificado` passa a `True`.
3. Dado um usuário com e-mail não verificado, quando ele tenta acessar uma funcionalidade que exige identidade confirmada, então o acesso é negado com uma mensagem clara (não um erro genérico 500).
4. Dado um fluxo OAuth do Google bem-sucedido (mockado em teste), quando o callback é processado, então um `User` é criado ou associado, com `papel=free` se for novo.
5. Dado um usuário cadastrado e verificado, quando `POST /api/auth/login/` com credenciais corretas, então retorna sessão/token válido; com credenciais erradas, retorna erro sem revelar se o e-mail existe ou não (mitigação de user enumeration).
6. Dado um usuário logado, quando `POST /api/auth/logout/`, então a sessão/token é invalidada.
7. Dado um usuário cadastrado, quando `POST /api/auth/recuperar-senha/` com seu e-mail, então um token de redefinição é gerado; quando `POST /api/auth/redefinir-senha/` com token válido e nova senha, então a senha é alterada e o hash antigo não permite mais login.
8. Dado um usuário recém-cadastrado, quando ele acessa `GET /api/onboarding/`, então recebe o estado atual (não preenchido); quando `PATCH /api/onboarding/` com interesses/localidade/canal, então os dados são salvos e associados ao usuário.
9. Dado um usuário que opta por pular o onboarding, quando envia essa opção, então o sistema registra que foi pulado (não perde a informação de que deve ser reapresentado depois) sem bloquear o uso da conta.
10. Nenhuma senha é persistida em texto plano — validado inspecionando o campo armazenado no banco em teste (deve estar hasheado).
11. O aceite de consentimento LGPD no cadastro é persistido com timestamp e identificação do que foi aceito.

## Não-objetivos
- Não construir nenhuma tela/UI (frontend). Esta execução entrega apenas API.
- Não implementar papéis de jornalista/moderador/B2B.
- Não implementar rate limiting avançado ou proteção anti-bot além do básico do Django (fica para spec/execução futura de segurança, se necessário).
- Não integrar de fato com um provedor de e-mail transacional real — usar backend de e-mail do Django configurável (console/mock em dev e teste), documentando que a integração real (SendGrid, SES, etc.) é decisão em aberto.
- Não implementar os outros módulos (`catalogo-noticias`, `assinatura`, `gating`) mesmo que o modelo `User` seja compartilhado por eles depois.

## Restrições técnicas
- **Performance:** N/A para este escopo (sem requisito de carga definido ainda).
- **Segurança/privacidade:** senhas hasheadas (Argon2 ou PBKDF2, padrão Django); tokens de verificação/redefinição de senha devem expirar; nenhum endpoint deve vazar se um e-mail está ou não cadastrado (mensagens genéricas em login/recuperação); consentimento LGPD auditável.
- **Dependências permitidas:** `django`, `djangorestframework`, `django-allauth` (login social Google), `psycopg2-binary` (ou `psycopg`), `pytest-django` (testes). Qualquer outra dependência nova deve ser justificada no `implementation-history.md` e sinalizada para o `reviewer`.
- **Estilo/convenções:** não há guia de estilo prévio no projeto (primeiro código) — o executor deve adotar convenções padrão da comunidade Django/DRF (PEP 8, estrutura de app padrão) e documentar em `implementation-history.md` para servir de referência às próximas execuções.

## Definição de pronto (Definition of Done)
- [ ] Critérios de aceite implementados
- [ ] Testes escritos e passando (tester)
- [ ] Revisão de código aprovada — obrigatória por `review-triggers.md` (autenticação/sessão + dados pessoais + novas dependências externas)
- [ ] Documentação atualizada (documenter) — incluindo "como rodar o backend" no README
- [ ] `implementation-history.md` completo e coerente
