<!--
CONTRACT: implementation-history
DONO: executor (cria e adiciona entradas) / tester, remediator, historian (adicionam entradas)
QUANDO É CRIADO: junto com a primeira ação do executor sobre o implementation-contract.md.
PARA ONDE VAI A INSTÂNCIA: agentic-framework/state/run-<run_id>/implementation-history.md
NATUREZA: append-only durante a execução — cada entrada é uma iteração, nunca se edita uma entrada anterior.
-->

# Implementation History — 20260901-2135-cadastro-auth

## Iteração 1 — 2026-09-01 — executor (implementação inicial)

**O que foi feito:**

Criado o scaffold inicial do backend Django (primeiro código do repositório, `brd_portal_noticias/backend/`), implementando o módulo `identidade/` completo conforme `implementation-contract.md`: modelo `User` customizado, cadastro por e-mail/senha com verificação por token assinado, login social via Google (`django-allauth`), login/logout via token de API, recuperação/redefinição de senha, e endpoint de onboarding (interesses, localidade, canal preferido, pulável). Nenhum frontend foi tocado (fora de escopo, conforme `task-plan.md`).

### Estrutura de pastas criada

```
backend/
  .env.example              # variáveis de ambiente documentadas (sem segredos reais)
  .gitignore
  manage.py
  pytest.ini                 # configuração do pytest-django (DJANGO_SETTINGS_MODULE=config.settings)
  requirements.txt
  config/                    # projeto Django (nome escolhido: "config" — convenção comum na comunidade)
    settings.py
    urls.py
    wsgi.py / asgi.py
  identidade/                # app Django do módulo identidade/
    models.py                # User (AbstractBaseUser + PermissionsMixin)
    managers.py               # UserManager (create_user/create_superuser por e-mail)
    adapters.py               # SocialAccountAdapter customizado (django-allauth) p/ papel=free e email_verificado=True no login social
    tokens.py                 # geração/leitura de token de verificação de e-mail (TimestampSigner) + PasswordResetTokenGenerator padrão do Django
    emails.py                  # envio de e-mails de verificação e redefinição de senha
    permissions.py             # IsEmailVerified (DRF permission)
    serializers.py
    views.py
    urls.py
    admin.py
    migrations/0001_initial.py
    tests/test_sanity.py       # testes mínimos de sanidade do executor (não é a suíte formal)
```

### Dependências instaladas (venv `backend/.venv`, Python 3.13.14)

Interpretador escolhido: **Python 3.13** (havia também Python 3.14.6 disponível na máquina, mas por ser um interpretador muito recente com risco maior de incompatibilidade com o ecossistema Django/allauth no momento desta execução, optei pelo 3.13, mais maduro para essa stack).

| Pacote | Versão | Motivo |
|---|---|---|
| Django | 5.2.17 (LTS) | Stack obrigatória (ARCHITECTURE.md §1). Escolhida a série LTS mais recente disponível (suporte até ~04/2028) em vez da 6.x (mais nova, não-LTS), para estabilidade de um projeto que está começando agora. |
| djangorestframework | 3.16.1 | Permitida pelo contrato. |
| django-allauth[socialaccount] | 65.19.2 | Permitida pelo contrato (login social Google). O extra `[socialaccount]` foi necessário — ver "Desvios" abaixo. |
| psycopg2-binary | 2.9.12 | Permitida pelo contrato (driver PostgreSQL). |
| pytest-django | 4.14.0 | Permitida pelo contrato (testes). |

Todas registradas em `backend/requirements.txt` com versões fixadas.

**Desvio/dependência transitiva não prevista explicitamente no contrato:** `django-allauth` sozinho (sem extras) **não** instala `requests`, `oauthlib` e `pyjwt[crypto]`, que são exigidos em runtime pelo provider do Google (`allauth.socialaccount.providers.google.provider` faz `import requests` no carregamento do app, e `manage.py check` falhava com `ModuleNotFoundError: No module named 'requests'`). A própria `django-allauth` declara esses pacotes como dependências opcionais sob o extra `socialaccount` (confirmado via `importlib.metadata`). Resolvi instalando `django-allauth[socialaccount]==65.19.2`, que traz `requests==2.34.2`, `oauthlib==3.3.1`, `PyJWT==2.13.0`, `cryptography==50.0.1` e dependências transitivas delas (`certifi`, `cffi`, `charset-normalizer`, `idna`, `pycparser`, `urllib3`). Não é uma dependência nova de arquitetura — é a forma correta/oficial de instalar a feature de login social do próprio `django-allauth` já aprovado no contrato — mas registro aqui e **sinalizo para o `reviewer`** por ser tecnicamente pacotes que não estavam nominalmente na lista de "dependências permitidas".

### Decisões técnicas (dentro da liberdade deixada pelo contrato)

1. **Nome do projeto Django:** `config` (raiz `backend/`, `django-admin startproject config .`), app do módulo: `identidade`. Convenção comum na comunidade Django (`config/` para settings, um app por bounded context).
2. **Backend de e-mail em dev/teste:** `django.core.mail.backends.console.EmailBackend` (imprime o e-mail — incluindo o token — no stdout), configurável via `DJANGO_EMAIL_BACKEND`. Não há integração real com provedor transacional (decisão em aberto, conforme "Não-objetivos" do contrato).
3. **Autenticação de API:** `rest_framework.authtoken` (`TokenAuthentication`), nativo do próprio DRF — não é uma dependência nova. Login retorna `{"token": ..., "usuario": {...}}`; logout deleta o token do usuário (torna-o inválido imediatamente). `SessionAuthentication` também habilitada como fallback (conveniência para o admin/browsable API).
4. **Hashing de senha:** mantida a ordem padrão do Django (PBKDF2 primeiro em `PASSWORD_HASHERS`), sem adicionar `argon2-cffi` — o contrato permite "Argon2 ou PBKDF2, padrão Django", e PBKDF2 já é o padrão sem dependência extra.
5. **Token de verificação de e-mail:** `django.core.signing.TimestampSigner` com salt próprio e expiração configurável via `EMAIL_VERIFICATION_TOKEN_MAX_AGE_SECONDS` (default 24h). Reaplicar um token já usado é inofensivo (idempotente), então não foi criado um modelo de token de uso único — decisão para manter o escopo enxuto; se o `reviewer`/`tester` considerarem isso insuficiente (ex.: exigir invalidação estrita de uso único), é um ajuste pontual no `remediator`.
6. **Token de redefinição de senha:** `django.contrib.auth.tokens.PasswordResetTokenGenerator` padrão do Django + `uidb64` (mesmo mecanismo do fluxo nativo de reset de senha do Django). Vantagem: o hash do token incorpora o hash de senha atual, então trocar a senha invalida automaticamente qualquer token antigo (critério de aceite 7) sem código adicional.
7. **Onboarding modelado como campos no próprio `User`** (não uma tabela separada) — `interesses` (JSONField), `localidade`, `canal_preferido`, `onboarding_concluido`, `onboarding_pulado`, `onboarding_atualizado_em`. Justificativa: é um conjunto pequeno de dados 1:1 com o usuário, conforme a própria definição de `ARCHITECTURE.md` §3 ("preferências de onboarding" como atributo de `User`).
8. **`OnboardingView` exige `IsAuthenticated` + `IsEmailVerified`.** Esta foi uma decisão de interpretação sobre uma ambiguidade do contrato: o critério de aceite 3 fala genericamente em "uma funcionalidade que exige identidade confirmada", e o único candidato concreto no escopo desta execução é o onboarding. A ordem dos critérios de aceite no contrato (2 verificação → 3 bloqueio por e-mail não verificado → ... → 8 onboarding) sugere um fluxo coerente ponta a ponta (cadastro → verificação → login → onboarding). **Sinalizo isso explicitamente para o `tester`/`reviewer`**: se a intenção fosse permitir onboarding antes da verificação de e-mail, é uma mudança de uma linha (remover `IsEmailVerified` de `OnboardingView.permission_classes`), mas exigiria contrato atualizado ou confirmação explícita, já que é uma leitura razoável mas não a única possível do texto do contrato.
9. **Consentimento LGPD não é assumido automaticamente no cadastro social (Google).** `SocialAccountAdapter.save_user` marca `papel=free` e `email_verificado=True` para novo usuário via Google, mas **não** define `consentimento_aceito_em` — porque não há, neste escopo backend-only, nenhuma etapa de aceite explícito de termos no fluxo social (diferente do cadastro por e-mail/senha, que exige `aceite_termos=true` obrigatoriamente no payload). Isso é uma lacuna conhecida: **o consentimento para usuários que entram via Google precisa ser capturado em algum outro momento** (ex.: uma tela obrigatória pós-login social, a implementar quando o frontend existir, ou um endpoint dedicado). Não implementei isso por ser uma funcionalidade não descrita no contrato (endpoint de consentimento pós-social-login) — **nota fora do escopo, sinalizada abaixo**.
10. **Mensagem de erro de cadastro para e-mail duplicado** é propositalmente genérica ("Não foi possível concluir o cadastro com os dados informados"), mas tecnicamente ainda permite inferir a duplicidade pelo simples fato do cadastro falhar (diferente de login/recuperação de senha, onde a resposta é idêntica em qualquer cenário). O contrato exige mensagens não-reveladoras apenas para login e recuperação de senha (critérios 5 e a restrição de segurança) — cadastro não está no mesmo escopo de mitigação, e revelar duplicidade no cadastro é uma prática comum e necessária para UX. Documentado aqui para transparência.
11. **Google login usa o fluxo de `id_token` (ID Token / JWT via Google Identity Services), não `access_token`.** O endpoint `POST /api/auth/google/` espera `{"id_token": "<jwt>"}` e usa `GoogleProvider.verify_token()` do `django-allauth`, que valida assinatura/emissor/audiência do token junto às chaves públicas do Google. Escolhido por ser o fluxo mais simples de integrar num backend puro de API (sem redirect OAuth completo) e o mais comum em SPAs modernas (botão "Entrar com Google" do Google Identity Services retorna exatamente esse token).
12. **Banco de dados: PostgreSQL é a engine padrão** (`config/settings.py`), configurável via variáveis `DJANGO_DB_*` (ver `.env.example`). **Não há servidor PostgreSQL disponível neste ambiente sandbox de execução** (verificado: nenhum `psql`/`pg_ctl` instalado). Para permitir rodar `manage.py check`, `makemigrations`, `migrate` e os testes de sanidade nesta execução, adicionei um *override* explícito via `DJANGO_DB_ENGINE=sqlite3` (variável de ambiente), documentado no próprio `settings.py` e no `.env.example` como um atalho de conveniência para bootstrap local — **não é a configuração recomendada nem o comportamento default** (o default, sem a variável, é `postgresql`). O `tester`/ambiente de CI precisará de um PostgreSQL real (ou continuar usando esse override) para rodar a suíte formal.

### Comandos executados / evidência

```
# venv
"C:\...\Python313\python.exe" -m venv backend/.venv

# instalação de dependências
pip install "Django==5.2.17" "djangorestframework==3.16.1" "django-allauth==65.19.2" \
            "psycopg2-binary==2.9.12" "pytest-django==4.14.0"
# -> falhou em manage.py check por falta de `requests` (ver "Desvios")
pip install "django-allauth[socialaccount]==65.19.2"
# -> resolvido

# scaffold
django-admin startproject config .
python manage.py startapp identidade

# checagem do sistema (com override sqlite p/ ambiente sem Postgres)
DJANGO_DB_ENGINE=sqlite3 python manage.py check
# -> "System check identified no issues (0 silenced)."

# migrations
DJANGO_DB_ENGINE=sqlite3 python manage.py makemigrations identidade
# -> "Migrations for 'identidade': identidade\migrations\0001_initial.py + Create model User"
DJANGO_DB_ENGINE=sqlite3 python manage.py migrate
# -> todas as migrations (auth, admin, contenttypes, sessions, sites,
#    account, socialaccount, authtoken, identidade) aplicadas com sucesso ("OK" em todas)

# testes de sanidade (escritos pelo próprio executor, não é a suíte formal do tester)
DJANGO_DB_ENGINE=sqlite3 python -m pytest identidade/tests/ -v
# -> 13 passed in ~9s
```

Saída final da suíte de sanidade:
```
identidade/tests/test_sanity.py::test_cadastro_cria_usuario_free_com_senha_hasheada PASSED
identidade/tests/test_sanity.py::test_cadastro_sem_aceite_termos_e_rejeitado PASSED
identidade/tests/test_sanity.py::test_cadastro_envia_email_de_verificacao PASSED
identidade/tests/test_sanity.py::test_logout_invalida_token PASSED
identidade/tests/test_sanity.py::test_login_com_senha_errada_retorna_mensagem_generica PASSED
identidade/tests/test_sanity.py::test_login_com_credenciais_corretas_retorna_token PASSED
identidade/tests/test_sanity.py::test_onboarding_bloqueado_sem_email_verificado PASSED
identidade/tests/test_sanity.py::test_onboarding_funciona_apos_verificacao_e_suporta_pular PASSED
identidade/tests/test_sanity.py::test_verificar_email_com_token_valido PASSED
identidade/tests/test_sanity.py::test_verificar_email_com_token_invalido PASSED
identidade/tests/test_sanity.py::test_fluxo_completo_recuperar_e_redefinir_senha_invalida_hash_antigo PASSED
identidade/tests/test_sanity.py::test_recuperar_senha_com_email_inexistente_retorna_mensagem_generica_e_nao_envia_email PASSED
identidade/tests/test_sanity.py::test_google_login_cria_usuario_novo_free_com_email_verificado PASSED
13 passed in 8.99s
```

### Convenções de estilo adotadas (referência para próximas execuções)

- PEP 8 padrão; nomes de campos de modelo/API em português (`papel`, `senha`, `nome`, `aceite_termos`, `interesses`, etc.), alinhado ao domínio de negócio em português usado no BRD/ARCHITECTURE.md/specs — mas nomes de classes, módulos, variáveis internas e comentários de código seguem inglês/português misto conforme já é comum em times brasileiros (classes em inglês técnico quando genéricas — `User`, `UserManager` — campos e mensagens de usuário em português).
- Um app Django por bounded context de `ARCHITECTURE.md` §2 (`identidade/` nesta execução); `catalogo-noticias`, `assinatura`, `gating` etc. devem virar apps próprios em execuções futuras, não pastas dentro de `identidade/`.
- Serializers separados por caso de uso (não um serializer genérico de `User` reaproveitado para tudo) — `CadastroSerializer`, `LoginSerializer`, `OnboardingSerializer`, etc.
- Permissions customizadas da API em `permissions.py` próprio do app (`IsEmailVerified`), não inline nas views.
- Docstrings de view/classe referenciam o número do critério de aceite do `implementation-contract.md` que implementam, para rastreabilidade.

**Resultado:** sucesso — todos os endpoints do contrato foram implementados, o projeto sobe (`manage.py check` limpo), migrations aplicam sem erro, e os 13 testes de sanidade escritos para validar o próprio código passam.

### Status dos critérios de aceite técnicos (implementation-contract.md)

| # | Critério | Status | Evidência |
|---|---|---|---|
| 1 | Cadastro cria conta `papel=free`, `email_verificado=False`, mecanismo de e-mail/token existe | ✅ Implementado | `CadastroView` + `emails.enviar_email_verificacao`; `test_cadastro_cria_usuario_free_com_senha_hasheada`, `test_cadastro_envia_email_de_verificacao` |
| 2 | Token de verificação válido → `email_verificado=True` | ✅ Implementado | `VerificarEmailView`; `test_verificar_email_com_token_valido` |
| 3 | E-mail não verificado → acesso negado a funcionalidade que exige identidade confirmada, com mensagem clara (não 500) | ✅ Implementado (com interpretação documentada — ver decisão técnica 8) | `IsEmailVerified` aplicada a `OnboardingView`; `test_onboarding_bloqueado_sem_email_verificado` (retorna 403 com `message` claro, não 500) |
| 4 | OAuth Google (mockado) cria/associa `User`, `papel=free` se novo | ✅ Implementado | `GoogleLoginView` + `SocialAccountAdapter`; `test_google_login_cria_usuario_novo_free_com_email_verificado` |
| 5 | Login correto → token válido; errado → erro genérico sem revelar existência do e-mail | ✅ Implementado | `LoginView`; `test_login_com_credenciais_corretas_retorna_token`, `test_login_com_senha_errada_retorna_mensagem_generica` |
| 6 | Logout invalida sessão/token | ✅ Implementado | `LogoutView`; `test_logout_invalida_token` |
| 7 | Recuperação gera token; redefinição com token válido troca a senha e invalida hash antigo | ✅ Implementado | `RecuperarSenhaView`/`RedefinirSenhaView`; `test_fluxo_completo_recuperar_e_redefinir_senha_invalida_hash_antigo` (inclui reuso do token após troca, que falha como esperado) |
| 8 | `GET /api/onboarding/` retorna estado não preenchido; `PATCH` salva interesses/localidade/canal | ✅ Implementado | `OnboardingView`; `test_onboarding_funciona_apos_verificacao_e_suporta_pular` |
| 9 | Pular onboarding não perde a informação de que deve ser reapresentado, não bloqueia uso da conta | ✅ Implementado | `OnboardingSerializer.update` (mantém `onboarding_concluido=False` ao pular); `test_onboarding_funciona_apos_verificacao_e_suporta_pular` |
| 10 | Nenhuma senha em texto plano | ✅ Implementado | `User.set_password` (PBKDF2 padrão Django); `test_cadastro_cria_usuario_free_com_senha_hasheada` verifica prefixo `pbkdf2_` no campo `password` |
| 11 | Consentimento LGPD persistido com timestamp e identificação do que foi aceito | ✅ Implementado para cadastro e-mail/senha (`consentimento_aceito_em` + `consentimento_versao_termos`); ⚠️ **não implementado para cadastro via Google** (ver decisão técnica 9 e nota fora do escopo abaixo) | `CadastroSerializer.create`; `test_cadastro_cria_usuario_free_com_senha_hasheada` |

**Resumo:** 10 de 11 critérios totalmente atendidos; o critério 11 está parcialmente atendido (cadastro por e-mail/senha cobre 100% do exigido; cadastro via Google não captura consentimento, ver nota fora do escopo). Critério 3 atendido sob uma interpretação de escopo documentada acima, que peço ao `tester`/`reviewer` para confirmar.

**Notas fora do escopo (não implementadas aqui, só sinalizadas):**

1. **Captura de consentimento LGPD para usuários que entram via Google.** O contrato define consentimento como parte do "cadastro" (critério 11) e o cadastro por e-mail/senha exige `aceite_termos=true` no payload; o fluxo social não tem equivalente. Isso deveria virar um requisito explícito em uma próxima iteração/contrato (ex.: endpoint `POST /api/auth/consentimento/` para ser chamado logo após um primeiro login social, ou capturar aceite como parâmetro do próprio `POST /api/auth/google/`). Sinalizando para `orchestrator`/`remediator` decidir se isso é um ajuste pontual desta execução ou uma spec futura.
2. **Sem servidor PostgreSQL real neste ambiente de execução** — a configuração aponta para PostgreSQL por padrão e foi validada estruturalmente (`ENGINE = django.db.backends.postgresql`, driver `psycopg2-binary` instalado e funcional), mas as migrations/testes desta iteração rodaram contra SQLite via override explícito (`DJANGO_DB_ENGINE=sqlite3`) por não haver Postgres disponível. Recomendo ao `tester` rodar (ou pedir que seja provisionado) um PostgreSQL real antes de considerar a validação completa — comportamento específico de PostgreSQL (ex.: `JSONField` usa `jsonb` nativo lá, vs. `TEXT` serializado no SQLite) não foi validado.
3. **Credenciais reais do Google OAuth** não existem neste ambiente (`GOOGLE_OAUTH_CLIENT_ID`/`SECRET` vazias no `.env.example`) — já era um risco conhecido e aceito em `task-plan.md`. O fluxo foi validado com o provider mockado (`GoogleProvider.verify_token` mockado no teste de sanidade), não ponta a ponta com o Google real.
4. **Rate limiting/anti-bot** explicitamente fora do escopo (não-objetivo do contrato) — não implementado, conforme esperado.

**Arquivos tocados:**
- `backend/manage.py` (novo)
- `backend/requirements.txt` (novo)
- `backend/.env.example` (novo)
- `backend/.gitignore` (novo)
- `backend/pytest.ini` (novo)
- `backend/config/settings.py`, `urls.py`, `wsgi.py`, `asgi.py`, `__init__.py` (novos)
- `backend/identidade/models.py`, `managers.py`, `adapters.py`, `tokens.py`, `emails.py`, `permissions.py`, `serializers.py`, `views.py`, `urls.py`, `admin.py`, `apps.py`, `__init__.py` (novos)
- `backend/identidade/migrations/0001_initial.py` (novo)
- `backend/identidade/tests/__init__.py`, `test_sanity.py` (novos — testes mínimos do executor)

---

## Iteração 2 — 2026-09-01 — tester (verificação formal dos critérios de aceite)

**O que foi feito:**

Escrita uma suíte formal de testes, independente da suíte de sanidade do executor, cobrindo explicitamente cada um dos 11 critérios de aceite de `implementation-contract.md`, com casos de borda adicionais não cobertos pela suíte do executor (token de verificação expirado, usuário Google já existente associado sem duplicar, papel não sobrescrito em login social de conta pré-existente, token Google inválido não cria usuário/registro, inspeção direta via SQL cru do campo `password` no banco, senha "unusable" de conta social, mensagem idêntica de erro de login para e-mail existente vs. inexistente, reuso de token após logout, logout sem autenticação, PATCH de onboarding bloqueado sem e-mail verificado).

Arquivo criado: `backend/identidade/tests/test_acceptance_criteria.py` (29 testes, organizados em classes `TestAC1`…`TestAC11`, um teste rastreável por critério no mínimo, vários com múltiplos casos de borda).

### Ambiente de execução

Mesmo mecanismo usado pelo executor, pelo mesmo motivo: **não há servidor PostgreSQL disponível neste ambiente** (nenhum `psql`/serviço rodando). Repeti a validação com o override `DJANGO_DB_ENGINE=sqlite3` documentado pelo executor em `config/settings.py`. **Isto é uma limitação do ambiente, não uma decisão do tester** — os testes não validam comportamento específico do PostgreSQL (ex.: `JSONField` como `jsonb` nativo, constraints/índices específicos do driver `psycopg2`). Fica registrado como lacuna de cobertura para quando houver Postgres disponível (CI ou ambiente de staging).

### Comando executado / evidência

```
DJANGO_DB_ENGINE=sqlite3 backend/.venv/Scripts/python.exe -m pytest identidade/tests/ -v
```

Resultado real (suíte completa: 13 testes de sanidade do executor + 29 testes formais do tester = 42 testes):

```
collected 42 items

identidade/tests/test_acceptance_criteria.py::TestAC1CadastroEmailSenha::test_cadastro_valido_cria_usuario_free_nao_verificado PASSED
identidade/tests/test_acceptance_criteria.py::TestAC1CadastroEmailSenha::test_cadastro_gera_email_com_token_de_verificacao_valido PASSED
identidade/tests/test_acceptance_criteria.py::TestAC1CadastroEmailSenha::test_cadastro_com_email_ja_cadastrado_e_rejeitado PASSED
identidade/tests/test_acceptance_criteria.py::TestAC2VerificacaoEmail::test_token_valido_marca_email_verificado PASSED
identidade/tests/test_acceptance_criteria.py::TestAC2VerificacaoEmail::test_token_invalido_nao_marca_email_verificado PASSED
identidade/tests/test_acceptance_criteria.py::TestAC2VerificacaoEmail::test_token_expirado_e_rejeitado PASSED
identidade/tests/test_acceptance_criteria.py::TestAC3BloqueioSemEmailVerificado::test_get_onboarding_sem_email_verificado_retorna_403_com_mensagem_clara PASSED
identidade/tests/test_acceptance_criteria.py::TestAC3BloqueioSemEmailVerificado::test_patch_onboarding_sem_email_verificado_tambem_e_bloqueado PASSED
identidade/tests/test_acceptance_criteria.py::TestAC3BloqueioSemEmailVerificado::test_usuario_verificado_acessa_onboarding_normalmente PASSED
identidade/tests/test_acceptance_criteria.py::TestAC4LoginSocialGoogle::test_google_login_usuario_novo_cria_com_papel_free PASSED
identidade/tests/test_acceptance_criteria.py::TestAC4LoginSocialGoogle::test_google_login_usuario_existente_associa_sem_duplicar PASSED
identidade/tests/test_acceptance_criteria.py::TestAC4LoginSocialGoogle::test_google_login_com_token_invalido_nao_cria_usuario PASSED
identidade/tests/test_acceptance_criteria.py::TestAC5Login::test_login_credenciais_corretas_retorna_token_valido PASSED
identidade/tests/test_acceptance_criteria.py::TestAC5Login::test_login_email_existente_senha_errada_mensagem_generica PASSED
identidade/tests/test_acceptance_criteria.py::TestAC5Login::test_login_conta_inativa_nao_autentica PASSED
identidade/tests/test_acceptance_criteria.py::TestAC6Logout::test_logout_invalida_token_e_impede_reuso PASSED
identidade/tests/test_acceptance_criteria.py::TestAC6Logout::test_logout_sem_autenticacao_e_rejeitado PASSED
identidade/tests/test_acceptance_criteria.py::TestAC7RecuperacaoSenha::test_fluxo_completo_recupera_e_redefine_senha PASSED
identidade/tests/test_acceptance_criteria.py::TestAC7RecuperacaoSenha::test_redefinir_senha_com_token_invalido_e_rejeitado PASSED
identidade/tests/test_acceptance_criteria.py::TestAC7RecuperacaoSenha::test_recuperar_senha_email_inexistente_nao_revela_e_nao_envia PASSED
identidade/tests/test_acceptance_criteria.py::TestAC8Onboarding::test_get_onboarding_usuario_recem_cadastrado_estado_nao_preenchido PASSED
identidade/tests/test_acceptance_criteria.py::TestAC8Onboarding::test_patch_onboarding_salva_interesses_localidade_canal PASSED
identidade/tests/test_acceptance_criteria.py::TestAC9PularOnboarding::test_pular_onboarding_registra_pulado_sem_marcar_concluido PASSED
identidade/tests/test_acceptance_criteria.py::TestAC9PularOnboarding::test_pular_onboarding_nao_bloqueia_uso_da_conta PASSED
identidade/tests/test_acceptance_criteria.py::TestAC10SenhaNuncaEmTextoPlano::test_senha_do_cadastro_por_email_esta_hasheada_no_banco PASSED
identidade/tests/test_acceptance_criteria.py::TestAC10SenhaNuncaEmTextoPlano::test_usuario_criado_via_google_nao_tem_senha_utilizavel_nem_plana PASSED
identidade/tests/test_acceptance_criteria.py::TestAC11ConsentimentoLGPD::test_cadastro_email_senha_persiste_consentimento_com_timestamp_e_versao PASSED
identidade/tests/test_acceptance_criteria.py::TestAC11ConsentimentoLGPD::test_cadastro_sem_aceite_explicito_de_termos_e_rejeitado PASSED
identidade/tests/test_acceptance_criteria.py::TestAC11ConsentimentoLGPD::test_cadastro_via_google_TAMBEM_deveria_persistir_consentimento FAILED
identidade/tests/test_sanity.py (13 testes do executor) PASSED

FAILURES:
_ TestAC11ConsentimentoLGPD.test_cadastro_via_google_TAMBEM_deveria_persistir_consentimento _
AssertionError: GAP CONFIRMADO: cadastro via Google não registra consentimento LGPD
(consentimento_aceito_em ficou None) — ver implementation-history.md, Iteração 1, decisão técnica 9.
assert None is not None
 +  where None = <User: consentimento.google.ac11@example.com>.consentimento_aceito_em

======================== 1 failed, 41 passed in 22.67s ========================
```

### Veredito por critério de aceite

| # | Critério | Veredito | Evidência |
|---|---|---|---|
| 1 | Cadastro cria `papel=free`, `email_verificado=False`, mecanismo de token existe | **passed** | `TestAC1CadastroEmailSenha` (3 testes) — inclui verificação de que o token do e-mail enviado de fato decodifica para o usuário criado, não é um valor decorativo |
| 2 | Token de verificação válido → `email_verificado=True` | **passed** | `TestAC2VerificacaoEmail` (3 testes) — inclui caso de borda de token expirado (`EMAIL_VERIFICATION_TOKEN_MAX_AGE_SECONDS=0` + sleep), não coberto pela suíte de sanidade original |
| 3 | E-mail não verificado → acesso negado com mensagem clara (não 500) | **passed**, com ressalva de escopo | `TestAC3BloqueioSemEmailVerificado` (3 testes) — comportamento coerente e testável no único endpoint protegido (`/api/onboarding/`, GET e PATCH), retorna 403 com `detail`/`message`, nunca 500. **Ressalva (não é motivo de falha para o tester, é observação para o reviewer):** a decisão do executor de aplicar essa regra só ao onboarding é uma interpretação de escopo válida, mas o contrato fala genericamente em "uma funcionalidade que exige identidade confirmada" — se surgirem outros endpoints autenticados no futuro sem `IsEmailVerified`, o critério pode deixar de ser satisfeito de forma ampla. Sinalizado para o `reviewer` decidir se a interpretação de escopo é aceitável. |
| 4 | OAuth Google (mockado) cria/associa `User`, `papel=free` se novo | **passed** | `TestAC4LoginSocialGoogle` (3 testes) — inclui caso de usuário já existente (associa via `SocialAccount`, não duplica, não sobrescreve `papel` pré-existente) e token inválido (400, não 500, nenhum usuário criado) |
| 5 | Login correto → token válido; errado → erro genérico sem revelar existência do e-mail | **passed** | `TestAC5Login` (3 testes) — comparação direta confirma que a mensagem de erro é **idêntica** para e-mail existente com senha errada vs. e-mail inexistente; inclui caso de conta inativa |
| 6 | Logout invalida sessão/token | **passed** | `TestAC6Logout` (2 testes) — confirma que o token, após logout, não pode ser reutilizado (401), e que logout sem autenticação é rejeitado |
| 7 | Recuperação gera token; redefinição com token válido troca a senha e invalida hash antigo | **passed** | `TestAC7RecuperacaoSenha` (3 testes) — fluxo completo ponta a ponta incluindo tentativa de login com senha antiga (falha) e nova (funciona); token inválido rejeitado sem alterar a senha; e-mail inexistente não envia e-mail e responde com a mesma mensagem genérica |
| 8 | `GET /api/onboarding/` retorna estado não preenchido; `PATCH` salva interesses/localidade/canal | **passed** | `TestAC8Onboarding` (2 testes) |
| 9 | Pular onboarding não perde a informação de que deve ser reapresentado, não bloqueia uso da conta | **passed** | `TestAC9PularOnboarding` (2 testes) — confirma `onboarding_concluido=False` e `onboarding_pendente=True` após pular, e que login e acesso ao onboarding continuam funcionando normalmente depois |
| 10 | Nenhuma senha em texto plano | **passed** | `TestAC10SenhaNuncaEmTextoPlano` (2 testes) — inspeção via **SQL cru** (`SELECT password FROM identidade_user`), não via `check_password` (que sempre re-hasheia e não provaria nada sobre o valor persistido); também valida que contas Google têm senha "unusable" do Django, não vazia/plana |
| 11 | Consentimento LGPD persistido com timestamp e identificação do que foi aceito | **FAILED** (parcial) | `TestAC11ConsentimentoLGPD` (3 testes): cadastro por e-mail/senha **passed** (`consentimento_aceito_em` e `consentimento_versao_termos` persistidos corretamente); cadastro via Google **FAILED** — `test_cadastro_via_google_TAMBEM_deveria_persistir_consentimento` confirma com evidência que `consentimento_aceito_em` permanece `None` para um usuário novo criado via login social, mesmo com `criado_agora=True`. Isso corrobora a lacuna que o próprio executor já havia sinalizado (Iteração 1, decisão técnica 9, "Notas fora do escopo" item 1). O contrato define o critério 11 em termos de "cadastro" de forma genérica, sem restringir ao fluxo e-mail/senha, e cadastro via Google é uma forma de cadastro coberta pelo critério 4 — portanto trato isso como **falha do critério 11**, não como fora de escopo. |

### Veredito geral da fase de testing: **failed**

Motivo: o critério de aceite 11 (consentimento LGPD) falha para o fluxo de cadastro via Google — usuários novos criados por login social não têm `consentimento_aceito_em`/`consentimento_versao_termos` persistidos, apesar de o critério 11 não distinguir "cadastro" por origem (e-mail/senha vs. social). Isso não é uma questão de qualidade de código (não é escopo do `reviewer`) nem uma limitação de ambiente — é um comportamento ausente, verificado com teste automatizado real. Correção é responsabilidade do `remediator`/`executor`, não do `tester`.

Os demais 10 critérios técnicos passaram com evidência real de execução, incluindo casos de borda além dos testados pela suíte de sanidade do executor.

**Observações não-bloqueantes para o `reviewer`:**
- Critério 3: decisão de escopo do executor (aplicar `IsEmailVerified` só ao onboarding) é testável e coerente hoje, mas é uma leitura entre outras possíveis do texto do contrato — merece confirmação explícita do `reviewer`/`orchestrator`, não é um bug.
- Ambiente sem PostgreSQL: toda a suíte (sanidade + formal) rodou contra SQLite via `DJANGO_DB_ENGINE=sqlite3`. Comportamento específico de PostgreSQL (`jsonb` nativo do `JSONField`, constraints do driver `psycopg2`) não foi exercitado nesta verificação. Recomendo confirmar contra PostgreSQL real antes do deploy, mas isso não é uma responsabilidade que o `tester` pode suprir neste ambiente.

**Arquivos tocados:**
- `backend/identidade/tests/test_acceptance_criteria.py` (novo — 29 testes formais, um por critério no mínimo, cobrindo os 11 critérios de aceite)

---

## Iteração 3 — 2026-09-01 — remediator (correção dos findings do code-review-contract.md)

**O que foi feito:**

Recebido `code-review-contract.md` com veredito **blocked** (2 blocker + 1 major + 3 minor). Todos os 6 findings foram corrigidos diretamente pelo próprio `remediator` (nenhuma correção foi grande/ambígua o suficiente para justificar delegação ao `executor` — todos os fixes couberam em poucos arquivos, com mudanças localizadas). Nenhuma delegação foi necessária nesta iteração.

### Finding 1 (blocker) — GoogleLoginView crasha com IntegrityError para e-mail já cadastrado

**Arquivo:** `backend/identidade/views.py` (`GoogleLoginView.post`).

**Mudança:** Antes de tratar `sociallogin.is_existing is False` como "usuário novo", a view agora consulta explicitamente `User.objects.get(email__iexact=email)`. Se já existir um `User` com este e-mail (cadastrado por e-mail/senha ou por qualquer outro meio) mas sem `SocialAccount` do Google vinculado, a view chama `sociallogin.connect(request, existing_user)` — API nativa do `django-allauth` que associa a `SocialAccount` ao `User` existente (via `SocialLogin.save(request, connect=True)`) sem tentar criar um `User` duplicado. `papel`, `consentimento_aceito_em` e a senha do usuário pré-existente não são tocados. Só chega ao branch de "criar `User` novo" quando de fato não existe nenhum `User` com aquele e-mail.

Também aproveitado para resolver o **Finding 4 (minor)** no mesmo bloco: o `except Exception` em torno de `provider.verify_token(...)` agora chama `logger.exception(...)` antes de retornar a mensagem genérica ao cliente, para dar visibilidade operacional a falhas sistêmicas (config/rede) vs. token realmente inválido.

**Revalidação:** novo teste `TestAC4LoginSocialGoogle::test_google_login_com_email_ja_cadastrado_por_senha_associa_sem_crashar` (`backend/identidade/tests/test_acceptance_criteria.py`) — cria um `User` via `create_user` (e-mail/senha, papel=premium), mocka `GoogleProvider.verify_token` retornando um `SocialLogin` para o mesmo e-mail, chama `POST /api/auth/google/` e confirma: `status_code == 200` (não 500), `criado_agora is False`, exatamente 1 `User` com aquele e-mail (sem duplicar), `papel` e senha originais preservados, `SocialAccount` associada ao `User` existente, e o token de API retornado corresponde ao `Token` do usuário existente. **PASSED.**

### Finding 2 (blocker) — cadastro via Google não persiste consentimento LGPD (critério de aceite 11)

**Arquivos:** `backend/identidade/views.py` (`GoogleLoginView.post`), `backend/identidade/serializers.py` (`GoogleLoginSerializer`), `backend/identidade/adapters.py` (`SocialAccountAdapter.save_user`, apenas comentário atualizado).

**Mudança:** `GoogleLoginSerializer` ganhou um campo opcional `aceite_termos` (default `False`). No branch de `GoogleLoginView.post` que só é alcançado quando não existe nenhum `User` nem `SocialAccount` prévios para o e-mail (usuário verdadeiramente novo), a view agora: (1) rejeita com `400` e mensagem clara se `aceite_termos` não vier `True` no payload — nenhum `User`/`SocialAccount` é criado nesse caso; (2) se vier `True`, define `sociallogin.user.consentimento_aceito_em = timezone.now()` e `sociallogin.user.consentimento_versao_termos = settings.TERMOS_VERSAO_ATUAL` **antes** de chamar `get_social_adapter(request).save_user(request, sociallogin)`, que persiste esses campos junto com o resto do `User` (mesmo padrão já usado por `CadastroSerializer.create` no cadastro por e-mail/senha). O comentário em `adapters.py` foi atualizado para não afirmar mais que consentimento "não é assumido automaticamente" — hoje ele é responsabilidade da view (que tem acesso ao payload da requisição), documentado explicitamente.

**Revalidação:**
- Teste substituído: `TestAC11ConsentimentoLGPD::test_cadastro_via_google_TAMBEM_deveria_persistir_consentimento` (que documentava o gap) virou `test_cadastro_via_google_com_aceite_termos_persiste_consentimento` — envia `aceite_termos: True`, confirma `consentimento_aceito_em is not None` e `consentimento_versao_termos` preenchido. **PASSED** (antes falhava, era o teste que confirmava o gap).
- Novo teste: `TestAC4LoginSocialGoogle::test_google_login_sem_aceite_termos_e_rejeitado_para_usuario_novo` — chama `POST /api/auth/google/` para um e-mail totalmente novo sem `aceite_termos` no payload e confirma `status_code == 400` (não 500), nenhum `User` nem `SocialAccount` criado. **PASSED.**
- Testes existentes que criavam usuário novo via Google (`test_google_login_usuario_novo_cria_com_papel_free`, `test_usuario_criado_via_google_nao_tem_senha_utilizavel_nem_plana` em `test_acceptance_criteria.py`, e `test_google_login_cria_usuario_novo_free_com_email_verificado` em `test_sanity.py`) foram ajustados para enviar `aceite_termos: True` no payload — sem isso, passariam a receber `400` em vez de criar o usuário, já que essa é exatamente a mudança de comportamento intencional deste fix. Todos **PASSED** após o ajuste.

### Finding 3 (major) — defaults inseguros de DEBUG/SECRET_KEY

**Arquivo:** `backend/config/settings.py`.

**Mudança:** `DEBUG` passou de `env_bool("DJANGO_DEBUG", True)` para `env_bool("DJANGO_DEBUG", False)` — default agora é `False` (opt-in explícito para ligar debug em dev, definindo `DJANGO_DEBUG=true`), em vez do padrão antigo (opt-out, arriscando produção rodar com `DEBUG=True` por esquecimento). Adicionado um `if not DEBUG and SECRET_KEY == _SECRET_KEY_FALLBACK: raise ImproperlyConfigured(...)` logo após a definição de `SECRET_KEY`/`DEBUG` — falha alto e cedo (na inicialização do processo Django, não em produção sob ataque) se alguém tentar rodar com `DEBUG=False` mas ainda com a `SECRET_KEY` fraca de fallback, com uma mensagem de erro clara orientando a correção.

**Efeito colateral tratado:** essa validação roda toda vez que `config/settings.py` é importado — incluindo pela suíte de testes, que não define `DJANGO_SECRET_KEY` nem `DJANGO_DEBUG` no ambiente (só `DJANGO_DB_ENGINE=sqlite3`, documentado nas iterações anteriores). Para não quebrar a suíte, foi criado `backend/config/settings_test.py` (importado via `DJANGO_SETTINGS_MODULE = config.settings_test` em `pytest.ini`, alterado de `config.settings`), que define `DJANGO_SECRET_KEY` com um valor de teste não-fraco via `os.environ.setdefault` **antes** de fazer `from .settings import *` — garante que o `import` sequencial do Python resolve o `os.environ.setdefault` antes do código de `settings.py` executar, evitando depender da ordem (não-determinística neste ambiente, testada e confirmada problemática) entre os hooks internos `pytest_load_initial_conftests` do pytest-django e o carregamento de um `conftest.py` de raiz (uma primeira tentativa usando `conftest.py` com `os.environ.setdefault` foi testada e **não funcionou** — a inicialização do Django pelo pytest-django ocorreu antes do conftest.py rodar; abandonada em favor do módulo `settings_test.py`). `DJANGO_SECRET_KEY`/`DJANGO_SECRET_KEY` reais do ambiente (ex.: CI configurado com segredo próprio) sempre têm prioridade sobre o valor de teste, via `setdefault`.

**Revalidação (comportamento, não só testes automatizados):**
- `DJANGO_DB_ENGINE=sqlite3 manage.py check` sem `DJANGO_SECRET_KEY`/`DJANGO_DEBUG` no ambiente → `ImproperlyConfigured` com mensagem clara (comportamento correto: por padrão agora é "produção", e recusa subir com a chave fraca).
- `DJANGO_DB_ENGINE=sqlite3 DJANGO_DEBUG=true manage.py check` → `System check identified no issues` (dev local continua funcionando com opt-in explícito).
- `DJANGO_DB_ENGINE=sqlite3 DJANGO_SECRET_KEY=<chave-real> manage.py check` (DEBUG ainda False/default) → `System check identified no issues` (produção configurada corretamente sobe sem erro).
- Suíte completa (`pytest identidade/tests/`, 44 testes, rodando com o novo `config.settings_test`) → **44 passed**.

`.env.example` recebeu comentários atualizados explicando o novo default e a checagem de inicialização.

### Finding 4 (minor) — catch genérico sem log em GoogleLoginView

Resolvido junto com o Finding 1 (mesmo bloco de código) — ver acima. `logger.exception(...)` adicionado antes do `return` de erro genérico.

### Finding 5 (minor) — DEFAULT_PERMISSION_CLASSES = AllowAny global

**Arquivo:** `backend/config/settings.py` (`REST_FRAMEWORK`).

**Mudança:** `DEFAULT_PERMISSION_CLASSES` invertido de `AllowAny` para `IsAuthenticated`. Confirmado antes da mudança que todas as views existentes (`CadastroView`, `VerificarEmailView`, `LoginView`, `RecuperarSenhaView`, `RedefinirSenhaView`, `GoogleLoginView` = `AllowAny` explícito; `LogoutView`, `OnboardingView` = `IsAuthenticated`/`IsEmailVerified` explícito) já declaram `permission_classes` próprio — a troca do default é uma rede de segurança para views futuras que esqueçam de declarar, sem alterar nenhum comportamento hoje.

**Revalidação:** suíte completa re-executada após a mudança — **44 passed** (nenhuma regressão; nenhuma view dependia do default `AllowAny` implícito).

### Finding 6 (minor) — dependências transitivas não fixadas por versão

**Arquivo:** novo `backend/requirements-lock.txt` (via `pip freeze` do `backend/.venv` validado nesta execução), com uma nota em `backend/requirements.txt` apontando para ele. Fixa todas as transitivas do extra `django-allauth[socialaccount]` (`requests`, `oauthlib`, `PyJWT`, `cryptography`, `certifi`, `cffi`, `charset-normalizer`, `idna`, `pycparser`, `urllib3`) e as diretas, para reprodutibilidade total do ambiente (CI, outro desenvolvedor, produção).

**Revalidação:** arquivo gerado a partir do ambiente já validado pela suíte de testes desta mesma iteração (44 passed) — não há mudança de código de runtime a revalidar, apenas o lock file reflete exatamente as versões já em uso e testadas.

### Suíte de testes — resultado final desta iteração

```
DJANGO_DB_ENGINE=sqlite3 backend/.venv/Scripts/python.exe -m pytest identidade/tests/ -v
...
44 passed in ~31s
```

(42 testes pré-existentes das Iterações 1–2, todos ainda passando após os ajustes de payload necessários pela mudança de comportamento do Finding 2, + 2 testes novos desta iteração: um para Finding 1, um para o caso de rejeição do Finding 2 — o teste que já existia para o "gap" do Finding 2 foi convertido em teste de regressão positivo.)

**Findings resolvidos nesta iteração:** 1 (blocker), 2 (blocker), 3 (major), 4 (minor), 5 (minor), 6 (minor) — todos os 6 findings do `code-review-contract.md`.

**Findings pendentes:** nenhum.

**Arquivos tocados:**
- `backend/identidade/views.py` (Finding 1, 2, 4 — `GoogleLoginView.post`, imports `logging`/`django.conf.settings`/`django.utils.timezone`)
- `backend/identidade/serializers.py` (Finding 2 — `GoogleLoginSerializer.aceite_termos`)
- `backend/identidade/adapters.py` (Finding 2 — comentário de `save_user` atualizado, sem mudança de comportamento)
- `backend/config/settings.py` (Finding 3 — `DEBUG`/`SECRET_KEY`; Finding 5 — `DEFAULT_PERMISSION_CLASSES`)
- `backend/config/settings_test.py` (novo — necessário para suportar o fix do Finding 3 sem quebrar a suíte de testes)
- `backend/pytest.ini` (`DJANGO_SETTINGS_MODULE` apontando para `config.settings_test`)
- `backend/.env.example` (comentários atualizados sobre o novo default de `DEBUG`/checagem de `SECRET_KEY`)
- `backend/requirements.txt` (nota apontando para o lock file)
- `backend/requirements-lock.txt` (novo — Finding 6)
- `backend/identidade/tests/test_acceptance_criteria.py` (2 testes novos — Finding 1 e Finding 2; 1 teste substituído — antigo teste de gap do Finding 2 virou teste de regressão positivo; 2 testes existentes ajustados para enviar `aceite_termos: True`)
- `backend/identidade/tests/test_sanity.py` (1 teste existente ajustado para enviar `aceite_termos: True`)

---
