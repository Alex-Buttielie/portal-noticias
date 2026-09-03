<!--
CONTRACT: code-review-contract
DONO: reviewer
QUANDO E CRIADO: sempre que review-triggers.md indicar revisao obrigatoria, ou sob demanda (skill agentic-review).
PARA ONDE VAI A INSTANCIA: agentic-framework/state/run-<run_id>/code-review-contract.md
-->

# Code Review Contract - 20260901-2135-cadastro-auth

## Metadados
- **run_id:** 20260901-2135-cadastro-auth
- **Revisao:** 2a passada (pos-remediacao) - revalida os 6 findings da 1a passada apos implementation-history.md, Iteracao 3 (remediator), e faz nova varredura geral em busca de regressoes.
- **Escopo revisado:** backend/identidade/ completo (models, managers, adapters, tokens, emails, permissions, serializers, views, urls, admin, migrations, settings_test.py) e backend/config/ (settings.py, urls.py, pytest.ini). Nao inclui backend/identidade/tests/ como alvo de producao, mas os testes foram lidos e executados para validar o comportamento.
- **Contrato de referencia:** implementation-contract.md (20260901-2135-cadastro-auth)
- **Gatilhos aplicados:** autenticacao/sessao (login, logout, tokens, OAuth Google); dados pessoais (cadastro, consentimento LGPD); nova dependencia externa (ja endereçado na 1a passada)
- **Metodo de revalidacao:** leitura direta do codigo atual em backend/identidade/views.py, serializers.py, adapters.py e backend/config/settings.py, settings_test.py, pytest.ini; leitura do codigo-fonte de django-allauth (SocialLogin.connect/.save/.lookup); execucao propria e independente da suite completa (pytest identidade/tests/ -v com DJANGO_DB_ENGINE=sqlite3, resultado: 44 passed); validacao manual de manage.py check em varias configuracoes de ambiente para o Finding 3.

## Revalidacao dos findings da 1a passada

### Finding 1 (blocker, original) - GoogleLoginView crasha com IntegrityError para e-mail ja cadastrado
- **Status:** RESOLVIDO, confirmado.
- **Evidencia:** GoogleLoginView.post (views.py) agora consulta User.objects.get(email__iexact=email) antes de tratar como "usuario novo"; se existir, chama sociallogin.connect(request, existing_user). Inspecionei o codigo-fonte de allauth.socialaccount.models.SocialLogin.connect/.save: connect() seta self.user = existing_user (o objeto ja carregado do banco, com papel/senha originais) e chama save(request, connect=True), que apenas persiste esse mesmo objeto e cria o SocialAccount associado - nao chama populate_user/save_user, entao nao ha sobrescrita de papel/senha. O teste de regressao TestAC4LoginSocialGoogle::test_google_login_com_email_ja_cadastrado_por_senha_associa_sem_crashar e rigoroso: cria um usuario via create_user com papel=PREMIUM, mocka o Google retornando o mesmo e-mail, confirma HTTP 200 (nao 500), exatamente 1 User com aquele e-mail, papel e senha originais intactos, SocialAccount associada, e token retornado batendo com o token do usuario existente. Executei a suite eu mesmo: PASSED.

### Finding 2 (blocker, original) - cadastro via Google nao persiste consentimento LGPD
- **Status:** RESOLVIDO, confirmado.
- **Evidencia:** GoogleLoginSerializer ganhou aceite_termos (opcional, default False). No branch de usuario verdadeiramente novo (sem User nem SocialAccount previos), GoogleLoginView.post rejeita com 400 se aceite_termos nao for True (sem criar User/SocialAccount), e senao define consentimento_aceito_em/consentimento_versao_termos em sociallogin.user antes de save_user. Dois testes novos confirmam ambos os ramos: test_cadastro_via_google_com_aceite_termos_persiste_consentimento (200, consentimento_aceito_em preenchido) e test_google_login_sem_aceite_termos_e_rejeitado_para_usuario_novo (400, nenhum User/SocialAccount criado). Executei a suite eu mesmo: ambos PASSED.

### Finding 3 (major, original) - defaults inseguros de DEBUG/SECRET_KEY
- **Status:** RESOLVIDO, confirmado.
- **Evidencia:** config/settings.py agora tem DEBUG = env_bool("DJANGO_DEBUG", False) (default invertido) e uma checagem "if not DEBUG and SECRET_KEY == _SECRET_KEY_FALLBACK: raise ImproperlyConfigured(...)". Revalidei manualmente, fora da suite de testes: rodei manage.py check sem nenhuma variavel de ambiente relevante definida -> ImproperlyConfigured com mensagem clara (comportamento correto); rodei com DJANGO_DEBUG=true -> "System check identified no issues". O efeito colateral (a checagem tambem roda ao importar settings.py durante os testes) foi tratado com config/settings_test.py (os.environ.setdefault de uma SECRET_KEY de teste antes do "from .settings import *") e pytest.ini apontando para ele - mecanismo correto e documentado, sem gambiarra que mascare a checagem em producao (o setdefault so age se a variavel real nao estiver definida).

### Finding 4 (minor, original) - catch generico sem log em GoogleLoginView
- **Status:** RESOLVIDO, confirmado.
- **Evidencia:** logger.exception(...) adicionado antes do return de erro generico no bloco except Exception da chamada a verify_token().

### Finding 5 (minor, original) - DEFAULT_PERMISSION_CLASSES = AllowAny global
- **Status:** RESOLVIDO, confirmado.
- **Evidencia:** config/settings.py, REST_FRAMEWORK DEFAULT_PERMISSION_CLASSES agora e IsAuthenticated. Confirmei que todas as views publicas (CadastroView, VerificarEmailView, LoginView, RecuperarSenhaView, RedefinirSenhaView, GoogleLoginView) continuam com permission_classes = [AllowAny] explicito - a suite completa passa sem nenhuma view dependendo do default antigo.

### Finding 6 (minor, original) - dependencias transitivas nao fixadas por versao
- **Status:** RESOLVIDO, confirmado.
- **Evidencia:** backend/requirements-lock.txt existe (42 linhas, pip freeze do ambiente validado), requirements.txt aponta para ele em comentario.

## Novos findings (encontrados nesta 2a passada)

### Finding 7 (novo)
- **Arquivo:** backend/identidade/views.py
- **Linha:** bloco try existing_user = User.objects.get(email__iexact=email) except User.DoesNotExist, dentro de GoogleLoginView.post
- **Categoria:** correctness
- **Severidade:** minor
- **Resumo:** O novo codigo introduzido pela correcao do Finding 1 usa get(email__iexact=...), que so trata User.DoesNotExist - nao trata MultipleObjectsReturned. O campo email do modelo e unique=True mas case-sensitive no banco (nao ha citext/constraint case-insensitive), enquanto varios pontos do sistema (este iexact, e tambem RecuperarSenhaView.post, ja existente desde a Iteracao 1, fora do escopo desta remediacao) buscam por e-mail de forma case-insensitive.
- **Cenario de falha:** Se, por qualquer via (ex.: uma condicao de corrida em CadastroSerializer.validate_email, que tem o mesmo padrao check-then-create sem lock/transacao atomica: duas requisicoes POST /api/auth/cadastro/ quase simultaneas, uma com Alice@example.com e outra com alice@example.com, ambas passam pela checagem filter(email__iexact=...).exists() antes de qualquer uma commitar), acabarem existindo dois User no banco cujo e-mail difere apenas em maiusculas/minusculas, uma tentativa legitima de login via Google usando qualquer uma das variantes de case levanta User.MultipleObjectsReturned nesta linha, nao capturada por nenhum try/except da view, resultando em HTTP 500 nao tratado (a mesma classe de bug que o Finding 1 original corrigiu, agora reintroduzida por uma pre-condicao diferente). E um cenario de baixa probabilidade (exige uma corrida especifica ocorrer primeiro), mas o novo call site introduzido por esta remediacao especificamente fica exposto a ele sem tratamento.
- **Sugestao:** Capturar tambem User.MultipleObjectsReturned (tratando como erro de configuracao/dados, log + resposta generica, nunca 500) e, se for prioridade, considerar reforcar a unicidade de e-mail no nivel de banco de forma case-insensitive na migration, para eliminar a pre-condicao na raiz. Nao bloqueante, mas vale registrar para uma proxima iteracao.

## Verificacao geral (regressao) nos arquivos nao tocados pela remediacao

Revisados novamente por completude (managers.py, tokens.py, emails.py, permissions.py, urls.py, admin.py, migrations) - nenhuma mudanca nesses arquivos nesta iteracao, nenhum problema novo encontrado. manage.py check limpo em modo dev (DJANGO_DEBUG=true) e falha corretamente em modo producao sem SECRET_KEY, como esperado pelo Finding 3.

## Resumo quantitativo
| Severidade | Quantidade | Observacao |
|---|---|---|
| blocker | 0 | 2 originais, ambos resolvidos e confirmados |
| major | 0 | 1 original, resolvido e confirmado |
| minor | 4 | 3 originais resolvidos e confirmados (Findings 4, 5, 6) + 1 novo (Finding 7) |
| nit | 0 | - |

## Veredito
**approve_with_comments**

Os dois blockers (crash no login social do Google para e-mail ja cadastrado por senha; ausencia de consentimento LGPD auditavel para cadastro via Google) e o major (defaults inseguros de DEBUG/SECRET_KEY) foram corrigidos e revalidados de forma independente nesta 2a passada - li o codigo atual (nao apenas o relato do remediator), inspecionei o comportamento real da API do django-allauth usada na correcao (SocialLogin.connect/.save), e executei a suite de testes eu mesmo (44 passed), alem de validar manualmente o comportamento do Finding 3 em configuracoes de ambiente distintas fora da suite automatizada. Os 3 minors originais tambem foram resolvidos e confirmados. Um novo finding minor foi identificado nesta passada (Finding 7: MultipleObjectsReturned nao tratado no novo call site de email__iexact introduzido pela correcao do Finding 1) - severidade baixa, pre-condicao rara, nao bloqueia merge, mas deve ser tratado numa proxima iteracao pontual. Nenhum finding major/blocker permanece aberto.
