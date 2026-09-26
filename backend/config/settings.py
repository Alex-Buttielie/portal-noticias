"""
Django settings for config project (módulo identidade/ — cadastro, autenticação,
onboarding do Portal de Notícias).

Gerado por 'django-admin startproject' e customizado conforme
`agentic-framework/state/run-20260901-2135-cadastro-auth/implementation-contract.md`.

Decisões de configuração relevantes estão documentadas em
`agentic-framework/state/run-20260901-2135-cadastro-auth/implementation-history.md`.
"""

import logging
import os
from pathlib import Path

from celery.schedules import crontab
from django.core.exceptions import ImproperlyConfigured

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Carrega backend/.env (se existir) para dentro de os.environ ANTES de
# qualquer os.environ.get abaixo. `override=False`: uma variável já
# exportada no ambiente real (shell, CI, systemd) sempre vence o .env —
# o arquivo é só conveniência de desenvolvimento local, nunca a fonte de
# verdade em produção.
try:
    from dotenv import load_dotenv

    load_dotenv(BASE_DIR / ".env", override=False)
except ImportError:
    pass


def env_bool(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


# SECURITY WARNING: keep the secret key used in production secret!
# Em produção, definir DJANGO_SECRET_KEY via variável de ambiente.
_SECRET_KEY_FALLBACK = "django-insecure-dev-only-key-nao-usar-em-producao"
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", _SECRET_KEY_FALLBACK)

# SECURITY WARNING: don't run with debug turned on in production!
# Default é False (opt-in explícito para ligar debug em dev/local, definindo
# DJANGO_DEBUG=true), invertendo o padrão anterior (default True, opt-out) —
# uma equipe de deploy que esquecesse de definir DJANGO_DEBUG=false em
# produção ficava com a página de depuração exposta publicamente
# (code-review-contract.md Finding 3).
DEBUG = env_bool("DJANGO_DEBUG", False)

# Comprimento mínimo da SECRET_KEY em produção. Não é um número escolhido
# aqui: é o limiar exato do aviso `security.W009` do próprio Django ("Your
# SECRET_KEY has less than 50 characters, which is not recommended"). O
# ponto de guardá-lo é que o caminho de release roda `python manage.py check`
# SEM `--deploy` (`.github/workflows/deploy.yml:322`), então um aviso de
# `check --deploy` nunca chega a ninguém: medido no item P0-02c, uma chave
# de 1 caractere subia em produção e o boot real (`import config.wsgi`, o
# que o Gunicorn executa) terminava sem erro.
_SECRET_KEY_MIN_LEN_PRODUCAO = 50


def _motivo_secret_key_recusada_para_producao(valor: str) -> str | None:
    """Por que `valor` não serve como SECRET_KEY de produção, ou `None` se
    serve. Função pura — não lê o ambiente, não imprime, não levanta — para
    deixar o guard abaixo legível e para poder ser exercitada isolada.

    O guard anterior comparava apenas `SECRET_KEY == _SECRET_KEY_FALLBACK`, e
    a desigualdadeava buracos. Todos os casos abaixo foram medidos em
    subprocesso no item P0-02c, com DJANGO_DEBUG=false e o resto do ambiente
    de produção real: em todos, o boot de produção (`import config.wsgi`)
    terminava SEM ERRO e `manage.py check` não emitia warning algum.
      * `DJANGO_SECRET_KEY=""` — a variável existe com valor vazio, e string
        vazia não é igual ao fallback, logo a trava não disparava. O próprio
        Django recusa esse caso, mas só DEPOIS e de forma preguiçosa, no
        primeiro acesso a `settings.SECRET_KEY` ("The SECRET_KEY setting must
        not be empty") — ou seja, no meio do tráfego, e não no boot;
      * `DJANGO_SECRET_KEY="   "` — 3 bytes de segredo efetivo. Sessão,
        cookie de sessão e token de redefinição passam a ser assinados com
        material trivial de adivinhar;
      * o valor de fallback com espaços nas pontas (`" django-... "`): a
        comparação por igualdade falha e a chave publicada no repositório
        passa;
      * o valor de fallback em caixa alta: a mesma chave publicada, só com a
        aparência de ter mudado;
      * qualquer chave com menos de 50 caracteres (`"x"`, 49 caracteres):
        nenhuma sinalização fora de `check --deploy`, que o release não roda.

    Vazia/branca e "igual ao fallback (com ou sem variação de caixa ou
    espaços)" são as maneiras de não ter definido uma chave de verdade; o
    comprimento trata o resto da classe "chave adivinhável". O valor efetivo
    NÃO é normalizado, só julgado: reescrever a chave derrubaria toda sessão
    já assinada do ambiente, e nada aqui quer isso.
    """
    if not valor:
        return "está vazia"
    sem_branco = valor.strip()
    if not sem_branco:
        return "contém apenas espaços em branco"
    if sem_branco.casefold() == _SECRET_KEY_FALLBACK.casefold():
        return "é o valor de fallback de desenvolvimento (ou uma variação dele)"
    if len(sem_branco) < _SECRET_KEY_MIN_LEN_PRODUCAO:
        return (
            f"tem apenas {len(sem_branco)} caracteres "
            f"(mínimo de {_SECRET_KEY_MIN_LEN_PRODUCAO})"
        )
    return None


# Falha explícita e cedo (na inicialização, não em produção sob ataque) se
# alguém tentar rodar com DEBUG=False (indicando produção) com uma
# SECRET_KEY ausente, vazia, só com espaços em branco, curta demais, ou igual
# ao valor de fallback de desenvolvimento — nunca deve ser possível subir
# "produção" silenciosamente insegura por esquecimento de configurar
# DJANGO_SECRET_KEY (code-review-contract.md Finding 3; o item P0-02c fechou
# os contornos que a comparação por igualdade deixava).
if not DEBUG:
    _motivo = _motivo_secret_key_recusada_para_producao(SECRET_KEY)
    if _motivo:
        raise ImproperlyConfigured(
            f"DJANGO_SECRET_KEY {_motivo} — recusado com DEBUG=False. Defina "
            "DJANGO_SECRET_KEY via variável de ambiente com uma chave forte e "
            f"única de no mínimo {_SECRET_KEY_MIN_LEN_PRODUCAO} caracteres "
            "(por exemplo "
            "`python -c 'import secrets; print(secrets.token_urlsafe(50))'`, "
            "o mesmo valor forte que `.github/workflows/deploy.yml` grava no "
            "primeiro deploy) antes de rodar fora de desenvolvimento local, "
            "ou defina DJANGO_DEBUG=true, que é o único caso em que uma chave "
            "fraca é aceita."
        )

# Hosts aceitos. O default é a dupla de loopback, e ela só funcionaria se o
# proxy reverso reescrevesse o cabeçalho Host para localhost — o que nenhum
# dos dois proxies deste projeto faz: o Nginx de produção encaminha o
# hostname original (`proxy_set_header Host $host`,
# `infra/nginx/portal-prod.conf`) e o Caddy preserva o Host no
# `reverse_proxy web:8000` (`Caddyfile`). O efeito era silencioso e total:
# sem DJANGO_ALLOWED_HOSTS e com DEBUG=False, todo hostname real recebia
# DisallowedHost (HTTP 400), sem warning e sem erro no boot (medido no item
# P0-02c). As travas abaixo dão a esse furo o mesmo tratamento que a
# SECRET_KEY e o SQLite já recebem: falhar na inicialização, com mensagem que
# diz o que configurar, em vez de degradar em silêncio.
_ALLOWED_HOSTS_SO_LOOPBACK = frozenset({"localhost", "127.0.0.1"})


def _motivo_allowed_hosts_recusado_para_producao(hosts: list) -> str | None:
    """Por que `hosts` não pode ser o ALLOWED_HOSTS de produção, ou `None` se
    pode. Função pura, como as outras deste arquivo.

    Recusa dois estados, ambos medidos no item P0-02c subindo sem warning:
      * lista vazia — `DJANGO_ALLOWED_HOSTS` ausente NÃO cai aqui (cai no
        default de loopback), mas vazio, ou só com vírgulas e espaços,
        produz `[]`, e aí todo hostname é recusado;
      * só hosts de loopback — é o valor que o próprio
        `backend/.env.example` sugere e o que o default de código assume; em
        produção, o domínio real e o IP de acesso ficam em 400.

    Um host além do loopback conta como declaração de intenção do operador e
    é aceito, mesmo que esteja errado: decidir se aquele host é o correto é
    papel do smoke test do deploy, que sonda `https://$HOST/healthz`
    (`.github/workflows/deploy.yml:513`) e falha quando a resposta não é 200.
    Aqui o objetivo é não deixar a lista ausente passar por implícita.
    """
    if not hosts:
        return (
            "não define nenhum host (a variável está vazia, ou só com "
            "vírgulas e espaços)"
        )
    if set(hosts) <= _ALLOWED_HOSTS_SO_LOOPBACK:
        return (
            "define apenas hosts de loopback (localhost/127.0.0.1), que não "
            "servem em produção"
        )
    return None


ALLOWED_HOSTS = [
    h.strip() for h in os.environ.get("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",") if h.strip()
]

if not DEBUG:
    _motivo_hosts = _motivo_allowed_hosts_recusado_para_producao(ALLOWED_HOSTS)
    if _motivo_hosts:
        raise ImproperlyConfigured(
            f"DJANGO_ALLOWED_HOSTS {_motivo_hosts} — recusado com DEBUG=False. "
            "Defina DJANGO_ALLOWED_HOSTS via variável de ambiente com o domínio "
            "do deploy e, se o acesso por IP também for usado, o respectivo IP "
            "(ex.: `DJANGO_ALLOWED_HOSTS=api.seu-dominio.com.br,SEU_IP,"
            "localhost,127.0.0.1`, a mesma forma de `.env.production.example` "
            "e de `.github/workflows/deploy.yml`) antes de rodar fora de "
            "desenvolvimento local, ou defina DJANGO_DEBUG=true, que é o "
            "único caso em que o default de loopback é aceito. Sem host "
            "correto, todo hostname real é recusado com DisallowedHost "
            "(HTTP 400)."
        )

# ---------------------------------------------------------------------------
# Hardening de produção (ARCHITECTURE.md seção "Nova arquitetura de infra" —
# análise 2026-09-03). Só entra em vigor com DEBUG=False, para não atrapalhar
# `manage.py runserver` local em HTTP puro sem certificado. Atrás de um
# proxy reverso (Caddy, ver `Caddyfile`/`docker-compose.yml`) que termina TLS
# e injeta `X-Forwarded-Proto`, então SECURE_PROXY_SSL_HEADER é necessário
# para o Django reconhecer a requisição como segura (sem isso,
# SECURE_SSL_REDIRECT causaria loop de redirecionamento atrás do proxy).
# ---------------------------------------------------------------------------
if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    # Operação por IP sem TLS (sem DNS): desligar via env até o TLS existir.
    # Com domínio + certbot, remover essas variáveis (defaults True voltam).
    SECURE_SSL_REDIRECT = env_bool("DJANGO_SECURE_SSL_REDIRECT", True)
    SESSION_COOKIE_SECURE = env_bool("DJANGO_SESSION_COOKIE_SECURE", True)
    CSRF_COOKIE_SECURE = env_bool("DJANGO_CSRF_COOKIE_SECURE", True)
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    CSRF_COOKIE_SAMESITE = "Lax"
    # 1 ano com preload é o padrão recomendado, mas exige confiança total no
    # domínio estar sempre em HTTPS — default mais conservador (30 dias),
    # ajustável via env quando o domínio final estiver estável.
    SECURE_HSTS_SECONDS = int(os.environ.get("DJANGO_SECURE_HSTS_SECONDS", 60 * 60 * 24 * 30))
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = False
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = "DENY"


# Application definition

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.sites",
    # terceiros
    "rest_framework",
    "rest_framework.authtoken",
    "corsheaders",
    "allauth",
    "allauth.account",
    "allauth.socialaccount",
    "allauth.socialaccount.providers.google",
    # apps do projeto
    # `config` entra como app (sem models e sem migrations) para que o
    # Django discover `config/management/commands/`, onde vive
    # `saude_filas` (P1-03). Sem estar na lista, o comando de
    # observabilidade das filas simplesmente não existiria para
    # `manage.py` — e a "parte consultável" do item de backlog depende
    # dele. A app do Celery é o mesmo pacote; nada muda para o worker.
    "config",
    "identidade",
    "catalogo_noticias",
    "feed",
    "gating",
    "assinatura",
    "credenciamento",
    "comunidade",
    "moderacao",
    "radar",
    "enderecos",
    "newsletter",
    "landing",
    "b2b",
    "metricas",
    "painel_admin",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    # Observabilidade P0 item 10 — propaga X-Request-ID (uuid4 se não vier
    # ou se o header for inválido/excessivo)
    # para correlação nginx ↔ Django ↔ logs/Sentry. Deve vir cedo, logo
    # após SecurityMiddleware, antes de qualquer middleware que logue.
    "config.middleware.RequestIdMiddleware",
    # Serve os arquivos estáticos (principalmente o CSS/JS do admin do
    # Django — painel administrativo pesado exigido pelo BRD seção 6/17)
    # diretamente do processo Gunicorn, comprimidos e com hash no nome do
    # arquivo para cache "forever" no navegador. Sem isso, com DEBUG=False
    # (produção), o Django simplesmente não serve estático nenhum e o admin
    # fica sem estilo — não valia a pena rodar um servidor de arquivos
    # separado (nginx dedicado) só para os poucos MB de estático deste
    # projeto. Precisa vir logo após SecurityMiddleware (docs do WhiteNoise).
    "whitenoise.middleware.WhiteNoiseMiddleware",
    # CorsMiddleware precisa vir antes de CommonMiddleware (docs do
    # django-cors-headers) — frontend/ (run 20260902-1448-frontend-mvp-web)
    # roda em origem diferente (localhost:3000) do backend (localhost:8000),
    # então chamadas fetch() do navegador exigem CORS habilitado.
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "allauth.account.middleware.AccountMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"


# Database
# https://docs.djangoproject.com/en/5.2/ref/settings/#databases
#
# Stack obrigatória definida em ARCHITECTURE.md seção 1: PostgreSQL.
# A engine é PostgreSQL por padrão; os parâmetros de conexão vêm de variáveis
# de ambiente (ver `.env.example`). Para desenvolvimento local sem um servidor
# PostgreSQL disponível (ex.: sandbox de execução deste agente), é possível
# sobrescrever explicitamente com DJANGO_DB_ENGINE=sqlite3 — isso é uma
# conveniência de bootstrap, não a configuração recomendada; ver
# implementation-history.md para o racional completo.
_DB_ENGINE = os.environ.get("DJANGO_DB_ENGINE", "postgresql")

if _DB_ENGINE == "sqlite3":
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.environ.get("DJANGO_DB_NAME", "brd_portal_noticias"),
            "USER": os.environ.get("DJANGO_DB_USER", "postgres"),
            "PASSWORD": os.environ.get("DJANGO_DB_PASSWORD", "postgres"),
            "HOST": os.environ.get("DJANGO_DB_HOST", "localhost"),
            "PORT": os.environ.get("DJANGO_DB_PORT", "5432"),
            # Reaproveita conexões entre requisições (Gunicorn com múltiplos
            # workers) em vez de abrir/fechar uma conexão TCP por requisição —
            # reduz latência sob carga sem exigir um pooler externo (pgbouncer)
            # na escala inicial de uma única VPS.
            "CONN_MAX_AGE": int(os.environ.get("DJANGO_DB_CONN_MAX_AGE", 60)),
        }
    }

# Trava de segurança: DJANGO_DB_ENGINE=sqlite3 é um atalho de bootstrap local
# (ver comentário acima). Rodar "produção" (DEBUG=False) contra SQLite
# silenciosamente perderia a garantia de persistência/concorrência que todo
# o resto desta arquitetura assume (backup, múltiplos workers Gunicorn
# escrevendo ao mesmo tempo) — falha explícita na inicialização em vez de
# silenciosa, mesmo padrão já usado acima para SECRET_KEY fraca.
if not DEBUG and _DB_ENGINE == "sqlite3":
    raise ImproperlyConfigured(
        "DJANGO_DB_ENGINE=sqlite3 não é suportado com DEBUG=False. Configure "
        "DJANGO_DB_ENGINE=postgresql (ou remova a variável, que já é o "
        "padrão) e as variáveis DJANGO_DB_* de conexão."
    )


# Password validation
# https://docs.djangoproject.com/en/5.2/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

# Hashing de senha: usa a ordem padrão do Django (PBKDF2 primeiro), conforme
# permitido pelo implementation-contract.md ("Argon2 ou PBKDF2, padrão
# Django") sem necessidade de dependência extra (argon2-cffi).

AUTH_USER_MODEL = "identidade.User"

AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
]


# Internationalization
# https://docs.djangoproject.com/en/5.2/topics/i18n/

LANGUAGE_CODE = "pt-br"

TIME_ZONE = "America/Sao_Paulo"

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.2/howto/static-files/

STATIC_URL = "static/"
# `manage.py collectstatic` (rodado por `docker-entrypoint.sh` a cada deploy)
# copia o estático de cada app para cá — é o que o WhiteNoiseMiddleware
# acima serve em produção. Sem STATIC_ROOT definido, collectstatic falha.
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    # Comprime (gzip/brotli) e adiciona hash ao nome do arquivo (cache-busting
    # automático — um deploy que muda o CSS do admin não serve a versão
    # velha para quem já tinha em cache).
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

# Media files (uploads de usuário — ex.: documento de credenciamento de
# jornalista, run 20260902-1503-credenciamento-jornalistas). FileSystemStorage
# local sobre um volume Docker nomeado (ver docker-compose.yml), incluído no
# backup diário (infra/backup/pg_backup.sh também arquiva MEDIA_ROOT) — opção
# deliberada para manter custo zero de storage externo na escala inicial de
# uma única VPS; migrar para object storage (ex.: Cloudflare R2) é um passo
# documentado em ARCHITECTURE.md quando o volume de mídia justificar.
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

# ---------------------------------------------------------------------------
# Saúde e prontidão (P0-10, eixo 4)
# ---------------------------------------------------------------------------
# Teto de tempo de CADA checagem de dependência em `/readyz`. Precisa ser
# menor que o `timeoutSeconds` do probe do orquestrador, senão o probe dá
# timeout e o orquestrador não chega a ler o 503 — que é a informação que
# ele precisa.
HEALTH_TIMEOUT_SEGUNDOS = float(os.environ.get("HEALTH_TIMEOUT_SEGUNDOS", "2.0"))

# Segredo de acesso a `/health-detail` e `/metrics`.
#
# VAZIO POR PADRITO, E VAZIO = ACESSO POR TOKEN DESABILITADO (fail-closed).
# Não é descuido: um deploy que esqueça esta variável não pode acabar com
# detalhe de saúde e métricas abertos na internet. A alternativa (fallback
# para um valor embutido no código) publicaria o segredo no repositório.
# Staff autenticado continua tendo acesso em qualquer caso.
#
# Gere com: `python -c "import secrets; print(secrets.token_urlsafe(32))"`
HEALTH_DETAIL_TOKEN = os.environ.get("HEALTH_DETAIL_TOKEN", "")

# Default primary key field type
# https://docs.djangoproject.com/en/5.2/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


# django.contrib.sites — exigido por django-allauth.
SITE_ID = 1


# django-allauth — configuração mínima para suportar login social via Google.
# Fluxos de e-mail/senha (cadastro, verificação, login, logout, recuperação de
# senha) são implementados por endpoints próprios em `identidade/`, não pelas
# views padrão do allauth — o app é usado apenas como biblioteca de OAuth
# (evita implementação própria do protocolo, conforme ARCHITECTURE.md seção 1
# e task-plan.md).
ACCOUNT_LOGIN_METHODS = {"email"}
ACCOUNT_SIGNUP_FIELDS = ["email*", "password1*", "password2*"]
ACCOUNT_UNIQUE_EMAIL = True
ACCOUNT_EMAIL_VERIFICATION = "none"  # verificação de e-mail é feita pelo fluxo próprio, não pelo allauth
SOCIALACCOUNT_AUTO_SIGNUP = True
SOCIALACCOUNT_ADAPTER = "identidade.adapters.SocialAccountAdapter"

SOCIALACCOUNT_PROVIDERS = {
    "google": {
        "APP": {
            "client_id": os.environ.get("GOOGLE_OAUTH_CLIENT_ID", ""),
            "secret": os.environ.get("GOOGLE_OAUTH_CLIENT_SECRET", ""),
            "key": "",
        },
        "SCOPE": ["profile", "email"],
    }
}


# Django REST Framework
# DEFAULT_PERMISSION_CLASSES é IsAuthenticated (não AllowAny) — cada view do
# módulo `identidade/` já declara explicitamente sua própria permissão hoje
# (cadastro/login/etc. são públicos via AllowAny explícito; onboarding exige
# autenticação + e-mail verificado), então este default só entra em jogo
# como rede de segurança para uma futura view que esqueça de declarar
# `permission_classes` — nesse caso, o padrão seguro é bloquear acesso
# público por omissão em vez de liberá-lo (code-review-contract.md Finding 5).
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.TokenAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    # Rate limiting (implementation-contract.md run
    # 20260903-1134-seo-lgpd-design-system, escopo C). Não há
    # DEFAULT_THROTTLE_CLASSES global de propósito — isso também limitaria
    # endpoints de LEITURA pública (ex.: `feed/`) fora do escopo desta run.
    # `config.throttling.EscritaPublicaAnonThrottle` é aplicado
    # explicitamente só nas views de escrita pública listadas no contrato
    # (cadastro em `identidade`, criação de publicação em `comunidade`,
    # lista de espera em `landing`). A taxa é "conservadora" no sentido de
    # folgada o bastante para não bloquear uso legítimo (task-plan.md,
    # mitigação de risco), configurável sem alteração de código.
    "DEFAULT_THROTTLE_RATES": {
        "escrita_publica": os.environ.get("THROTTLE_ESCRITA_PUBLICA_RATE", "20/min"),
        # Achado de revisão de segurança (major): login/recuperação de
        # senha/verificação de e-mail/login social não tinham throttle
        # nenhum — ver config/throttling.py:AuthSensivelAnonThrottle.
        "auth_sensivel": os.environ.get("THROTTLE_AUTH_SENSIVEL_RATE", "10/min"),
        # Achado de revisão de segurança (minor): denúncia sem limite por
        # usuário autenticado — ver config/throttling.py:DenunciaUserThrottle.
        "denuncia": os.environ.get("THROTTLE_DENUNCIA_RATE", "20/hour"),
        # FRENTE 5 — proxy de endereços (ViaCEP/IBGE com cache): leitura
        # pública com upstream externo; teto folgado para digitação com
        # debounce nunca bater, mas rajadas batem — ver
        # config/throttling.py:EnderecosAnonThrottle.
        "enderecos": os.environ.get("THROTTLE_ENDERECOS_RATE", "60/min"),
    },
}

# FRENTE 5 — endereços inteligentes: base URLs e TTLs do proxy
# (`enderecos/services.py`). ViaCEP/IBGE são públicos e não exigem
# credencial; quando um provedor com credencial (ex.: Correios) for
# adotado, a chave entra aqui via env e o frontend não muda nada.
ENDERECOS_VIACEP_BASE_URL = os.environ.get("ENDERECOS_VIACEP_BASE_URL", "https://viacep.com.br")
ENDERECOS_IBGE_BASE_URL = os.environ.get(
    "ENDERECOS_IBGE_BASE_URL", "https://servicodados.ibge.gov.br/api/v1"
)
ENDERECOS_UPSTREAM_TIMEOUT_SEGUNDOS = int(os.environ.get("ENDERECOS_UPSTREAM_TIMEOUT_SEGUNDOS", 8))
ENDERECOS_CACHE_CEP_SEGUNDOS = int(os.environ.get("ENDERECOS_CACHE_CEP_SEGUNDOS", 86400))
ENDERECOS_CACHE_IBGE_SEGUNDOS = int(os.environ.get("ENDERECOS_CACHE_IBGE_SEGUNDOS", 604800))


# ---------------------------------------------------------------------------
# Cache (ARCHITECTURE.md — nova arquitetura de infra, 2026-09-03). Até esta
# mudança, Redis só era usado como broker/result backend do Celery — não
# havia NENHUM cache de aplicação configurado (Django caía no default
# `LocMemCache` implícito, que não é compartilhado entre os processos
# Gunicorn nem sobrevive a um restart/deploy). Usado por `feed/` para
# cachear listagens públicas (alto volume de leitura, o padrão de tráfego
# dominante deste produto). A invalidação atual é por TTL de 45 s
# (FEED_CACHE_TTL_SEGUNDOS); o evento `plano.preco_alterado` não invalida
# as listagens do feed. Em desenvolvimento local sem Redis disponível, cai para
# LocMemCache (mesma lógica de conveniência de bootstrap do DJANGO_DB_ENGINE
# acima) via DJANGO_CACHE_BACKEND=locmem.
_CACHE_BACKEND = os.environ.get("DJANGO_CACHE_BACKEND", "redis")
if _CACHE_BACKEND == "locmem":
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        }
    }
else:
    CACHES = {
        "default": {
            "BACKEND": "django_redis.cache.RedisCache",
            "LOCATION": os.environ.get("DJANGO_CACHE_REDIS_URL", "redis://localhost:6379/2"),
            "OPTIONS": {
                "CLIENT_CLASS": "django_redis.client.DefaultClient",
            },
            # Chave curta de propósito — cache de feed/listagens é sempre
            # reconstruível a partir do banco; um erro de conexão com o
            # Redis não deve derrubar a aplicação (ver `IGNORE_EXCEPTIONS`).
            "TIMEOUT": int(os.environ.get("DJANGO_CACHE_TIMEOUT_SEGUNDOS", 60)),
        }
    }
    # Redis indisponível degrada para "sem cache" (cada request bate direto
    # no Postgres) em vez de erro 500 — cache é uma otimização de
    # performance, nunca uma dependência dura de disponibilidade.
    CACHES["default"]["OPTIONS"]["IGNORE_EXCEPTIONS"] = True
    # IMPORTANTE (code-review-contract.md, run 20260903-1134-seo-lgpd-design-
    # system, Finding 1): IGNORE_EXCEPTIONS=True sozinho engole a falha em
    # silêncio total — sem isso, uma queda de Redis em produção também
    # desativa o rate limiting (config/throttling.py) sem nenhum sinal
    # observável. DJANGO_REDIS_LOG_IGNORED_EXCEPTIONS liga o log de exceção
    # (nível ERROR, logger "django_redis.cache") toda vez que uma exceção é
    # engolida por IGNORE_EXCEPTIONS, propagando para o logger "root" já
    # configurado acima (handler "console", stdout do container) — não
    # resolve observabilidade completa (sem alerta/métrica dedicados), mas
    # garante que a degradação apareça nos logs em vez de desaparecer.
    # (Lido de `settings.DJANGO_REDIS_LOG_IGNORED_EXCEPTIONS` diretamente por
    # `django_redis.cache.RedisCache.__init__` — não é uma chave de
    # `OPTIONS`, é setting de módulo top-level, por isso fica fora do dict
    # `CACHES` acima.)
    DJANGO_REDIS_LOG_IGNORED_EXCEPTIONS = True


# E-mail
# Provedor transacional: Resend (`config/email_resend.py`, sem SDK externo).
# Em desenvolvimento/teste, o default "console" imprime o e-mail no stdout
# (permite inspecionar tokens de verificação/redefinição manualmente). Em
# produção: `DJANGO_EMAIL_BACKEND=config.email_resend.ResendEmailBackend` +
# `RESEND_API_KEY=re_...` + remetente de domínio verificado no Resend.
EMAIL_BACKEND = os.environ.get(
    "DJANGO_EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend"
)
RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "")
DEFAULT_FROM_EMAIL = os.environ.get("DJANGO_DEFAULT_FROM_EMAIL", "no-reply@brdportalnoticias.local")

# Backends que NÃO entregam e-mail: imprimem no console, guardam em memória
# ou descartam. Manter um destes em produção é falha silenciosa de entrega —
# a verificação de cadastro, a redefinição de senha e a newsletter "saem" com
# sucesso, aparecem no stdout do container, e o deploy segue reportando
# sucesso. Este é o único dos três furos do item P0-02c que NÃO pode virar
# `raise ImproperlyConfigured` ainda: nenhum workflow define
# DJANGO_EMAIL_BACKEND, o `printf` que cria `backend/.env` no primeiro deploy
# (`.github/workflows/deploy.yml:277`) não escreve a variável, e
# `PROD_DECISOES.md` (item 2, "LLM / e-mail / OAuth") registra a integração
# Resend como "código pronto, aguardando chave Resend do Alex" — decisão de
# produto em aberto, não um bug. Um guard duro aqui derrubaria TODO deploy até
# essa credencial existir. O que dá para fazer sem mentir sobre o estado:
# tornar o furo barulhento no boot, no mesmo lugar onde o e-mail já vaza.
_EMAIL_BACKENDS_QUE_NAO_ENTREGAM = frozenset(
    {
        "django.core.mail.backends.console.EmailBackend",
        "django.core.mail.backends.locmem.EmailBackend",
        "django.core.mail.backends.dummy.EmailBackend",
    }
)

# O sinal é um log de nível ERROR no import, e não um system check, porque o
# boot de produção é o `import config.wsgi` do Gunicorn (ver
# `backend/gunicorn.conf.py` e o job de deploy) — caminho em que o Django NÃO
# roda os system checks, então um check registrado aqui passaria batido. Neste
# ponto `LOGGING` (mais abaixo) ainda não foi aplicado: o Django o instala em
# `django.setup()`, depois do import dos settings. O que resta é o
# `logging.lastResort` do Python, que escreve nível WARNING+ em stderr — que é
# o mesmo stream onde o e-mail, e o token de verificação, estavam sendo
# impressos. Ou seja: a falha deixa de ser invisível exatamente no lugar onde
# vinha acontecendo, e o operador vê a causa junto do sintoma.
if not DEBUG and EMAIL_BACKEND in _EMAIL_BACKENDS_QUE_NAO_ENTREGAM:
    logging.getLogger("config.settings").error(
        "E-mail em produção não é entregue: DJANGO_EMAIL_BACKEND=%s não envia "
        "nada — a verificação de cadastro, a redefinição de senha e a "
        "newsletter só aparecem no stdout deste container, e o deploy continua "
        "reportando sucesso. Defina "
        "DJANGO_EMAIL_BACKEND=config.email_resend.ResendEmailBackend e "
        "RESEND_API_KEY=re_... (chave em https://resend.com/api-keys, com o "
        "domínio verificado como remetente) antes de tratar o deploy como "
        "entregue. Estado da integração: PROD_DECISOES.md, item 2.",
        EMAIL_BACKEND,
    )

# P1-15b — destino das mensagens do formulário de contato (`contato/`).
# Endereço que a redação monitora e que recebe as mensagens. VAZIO por
# propósito: este item não inventa hostname nem domínio, e sem destino
# configurado o endpoint responde 503 dizendo exatamente o que falta
# (`contato/services.py:verificar_canal`) em vez de aceitar a mensagem e
# despejá-la em `console.EmailBackend`. Preencher por ambiente; ver
# `.env.localhost.example`/`.env.production.example`/`backend/.env.example`.
CONTATO_DESTINO = os.environ.get("CONTATO_DESTINO_EMAIL", "")

# Front-end (run 20260902-1448-frontend-mvp-web, frontend/ na raiz do
# projeto) — usado para montar links absolutos nos e-mails de
# verificação/redefinição de senha (ex.: {FRONTEND_BASE_URL}/verificar-email)
# e como origem permitida de CORS abaixo.
FRONTEND_BASE_URL = os.environ.get("FRONTEND_BASE_URL", "http://localhost:3000")

# CORS: o frontend Next.js roda em origem diferente (localhost:3000) do
# backend (localhost:8000) — chamadas fetch() do navegador exigem CORS
# habilitado explicitamente. Só a origem do próprio frontend é permitida
# (não CORS_ALLOW_ALL_ORIGINS=True, que seria excessivamente permissivo).
# Contingência por IP (sem DNS): origens extras via DJANGO_CORS_EXTRA_ORIGINS
# (separadas por vírgula, ex.: "http://108.174.147.50:3103") — permite usar o
# portal direto pelo IP enquanto o domínio não resolve. O canônico continua
# sendo o domínio via Nginx (FRONTEND_BASE_URL).
def _parse_extra_origins(raw: str) -> list:
    """Origens extras de `DJANGO_CORS_EXTRA_ORIGINS` (vírgula): ignora vazios
    e espaços. Função pura para ser testável sem recarregar o settings."""
    return [origem.strip() for origem in (raw or "").split(",") if origem.strip()]


CORS_ALLOWED_ORIGINS = [FRONTEND_BASE_URL] + _parse_extra_origins(
    os.environ.get("DJANGO_CORS_EXTRA_ORIGINS", "")
)
CORS_ALLOW_CREDENTIALS = True

# Expiração de tokens (segundos).
EMAIL_VERIFICATION_TOKEN_MAX_AGE_SECONDS = int(
    os.environ.get("EMAIL_VERIFICATION_TOKEN_MAX_AGE_SECONDS", 60 * 60 * 24)  # 24h
)
PASSWORD_RESET_TIMEOUT = int(
    os.environ.get("PASSWORD_RESET_TIMEOUT_SECONDS", 60 * 60)  # 1h — usado pelo PasswordResetTokenGenerator
)

# Validade do link/token de descadastro da newsletter (P1-06). O token é
# assinado com timestamp (`newsletter/tokens.py`, mesmo par de
# `identidade/tokens.py` para verificação de e-mail) e rotacionado no uso, então
# é de uso único: passado o prazo, o link do e-mail deixa de funcionar e a
# pessoa usa o link do e-mail mais recente. 30 dias cobre o intervalo típico
# entre o envio e a pessoa decidir cancelar, com folga para quem só abre o
# e-mail depois. Configurável por ambiente para não exigir deploy de código.
NEWSLETTER_TOKEN_DESCADASTRO_MAX_AGE_SECONDS = int(
    os.environ.get("NEWSLETTER_TOKEN_DESCADASTRO_MAX_AGE_SECONDS", 30 * 24 * 60 * 60)  # 30d
)

# Versão vigente dos Termos/Política de Privacidade que o cadastro exige aceite
# explícito (LGPD) — registrada em User.consentimento_versao_termos.
TERMOS_VERSAO_ATUAL = os.environ.get("TERMOS_VERSAO_ATUAL", "1.0")


# ---------------------------------------------------------------------------
# Celery + Redis (ARCHITECTURE.md seção 1) — jobs assíncronos. Usado hoje
# pela ingestão periódica de `catalogo_noticias` (ver `tasks.py`), e por
# qualquer job assíncrono futuro do projeto (envio de e-mail, etc.).
# ---------------------------------------------------------------------------
CELERY_BROKER_URL = os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379/0")
CELERY_RESULT_BACKEND = os.environ.get("CELERY_RESULT_BACKEND", "redis://localhost:6379/1")
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TIMEZONE = TIME_ZONE
CELERY_TASK_TRACK_STARTED = True

# P2-4 (run 20260923-1600-p2-backend-perf): prefetch e recycling são
# ajustes do worker. `acks_late` e `reject_on_worker_lost` NÃO são globais:
# são declarados somente nas tasks idempotentes (ingestão e evento de
# busca), para não reentregar efeitos externos de newsletters, alertas ou
# vencimentos depois de uma queda do worker.
CELERY_WORKER_PREFETCH_MULTIPLIER = 1
CELERY_WORKER_MAX_TASKS_PER_CHILD = int(os.environ.get("CELERY_WORKER_MAX_TASKS_PER_CHILD", "100"))

# ---------------------------------------------------------------------------
# Modo de execução das tasks (P1-03, WS-06) — broker vs. inline.
#
# PADRÃO = BROKER, e é o que vale em DEV/HOMOLOG/PROD: `.delay()` publica no
# broker e um `celery -A config worker` separado consome. É o único modo em
# que "a fila foi consumida" é um fato observável.
#
# INLINE (`CELERY_TASK_ALWAYS_EAGER=true`) executa a task no próprio processo
# que chamou `.delay()`. Existe para desenvolvimento/testes e para um
# ambiente sem broker; é atalho EXPLÍCITO (opt-in), nunca o default, porque
# um default inline esconderia a fila justamente no ambiente onde ela
# importa. Quem lida com essa escolha é `config/filas_saude.py`, que em modo
# inline responde `desconhecido` — não `ok` — para as sondagens de fila.
#
# `task_eager_propagates` fica ligado junto do inline para que uma falha
# suba como exceção no chamador em vez de virar um resultado "esquentado":
# em execução local a falha tem de ser visível, não enfileirada para ninguém.
CELERY_TASK_ALWAYS_EAGER = env_bool("CELERY_TASK_ALWAYS_EAGER", False)
CELERY_TASK_EAGER_PROPAGATES = env_bool("CELERY_TASK_EAGER_PROPAGATES", CELERY_TASK_ALWAYS_EAGER)

# ---------------------------------------------------------------------------
# Observabilidade das filas (P1-03, WS-06) — `config/filas_saude.py` +
# `config/filas_estado.py` + `manage.py saude_filas`.
#
# Os limites abaixo são o que transforma "números observados" em veredito.
# São deliberadamente explícitos (e não constantes escondidas no código) para
# que o valor de produção seja ajustável por ambiente sem deploy de código.
# ---------------------------------------------------------------------------
FILAS_NOME_FILA = os.environ.get("CELERY_QUEUE", "celery")

# Profundidade acima da qual a fila é considerada degradada. Com a ingestão a
# cada 15 min, centenas de itens pendentes já significam consumo parado, não
# uma rajada de tráfego.
FILAS_PROFUNDIDADE_MAXIMA = int(os.environ.get("FILAS_PROFUNDIDADE_MAXIMA", "500"))

# Idade da task em execução mais antiga acima da qual há task travada.
FILAS_IDADE_MAXIMA_TAREFA_SEGUNDOS = float(
    os.environ.get("FILAS_IDADE_MAXIMA_TAREFA_SEGUNDOS", "900")
)

# Intervalo do heartbeat do beat no `CELERY_BEAT_SCHEDULE` e idade máxima
# aceita para o registro. O limite (900s = 3 intervalos) tolera dois ticks
# perdidos — reboot, timer atrasado por I/O — antes de entrar em
# `degradado`. AUMENTAR o intervalo sem aumentar o limite troca um sinal
# sensível por um sinal atrasado; nunca o contrário.
FILAS_HEARTBEAT_INTERVALO_SEGUNDOS = int(
    os.environ.get("FILAS_HEARTBEAT_INTERVALO_SEGUNDOS", "300")
)
FILAS_BEAT_MAX_AGE_SEGUNDOS = float(os.environ.get("FILAS_BEAT_MAX_AGE_SEGUNDOS", "900"))

# Task cujo último ciclo é monitorado. É a ingestão porque é o job que
# produz conteúdo: é o único trabalho do portal em que "não rodou" significa
# "o portal está parado de atualizar". Um ambiente que ainda não rodou um
# ciclo de ingestão responde `desconhecido` — e essa é a resposta honesta.
FILAS_TAREFA_MONITORADA = os.environ.get(
    "FILAS_TAREFA_MONITORADA", "catalogo_noticias.tasks.ingerir_noticias"
)

# TTL curto para o vocabulário de autocomplete. O cache é reconstruível a
# partir de NewsItem/EventoBusca; a ingestão invalida as chaves de catálogo
# após uma escrita e o TTL cobre eventos/erros de cache como fallback.
FEED_AUTOCOMPLETE_CACHE_TTL_SEGUNDOS = int(
    os.environ.get("FEED_AUTOCOMPLETE_CACHE_TTL_SEGUNDOS", "300")
)

# Intervalo (minutos) do job periódico de ingestão de notícias — configurável
# sem alteração de código/deploy do worker.
CATALOGO_NOTICIAS_INTERVALO_INGESTAO_MINUTOS = int(
    os.environ.get("CATALOGO_NOTICIAS_INTERVALO_INGESTAO_MINUTOS", 15)
)
# Reconciliação de segurança contra 304 falso/perda local. Validators são
# otimização; após este TTL a próxima leitura de cada FonteRobo é feita sem
# If-None-Match/If-Modified-Since. Zero (ou menor) força revalidação sempre.
CATALOGO_NOTICIAS_REVALIDACAO_COMPLETA_HORAS = float(
    os.environ.get("CATALOGO_NOTICIAS_REVALIDACAO_COMPLETA_HORAS", 6)
)
# Provedor de pagamento plugável (ARCHITECTURE.md seção 6,
# `PaymentGatewayProvider`): "manual" é o placeholder sem rede; provedores
# reais futuros ("mercadopago", "stripe", ...) entram em
# `assinatura/providers/payment.py::obter_gateway_pagamento` sem mudar
# `services.py`. Ideia incorporada do protótipo `testes-ia` (PAYMENT_PROVIDER).
ASSINATURA_PAYMENT_GATEWAY_PROVIDER = os.environ.get("ASSINATURA_PAYMENT_GATEWAY_PROVIDER", "manual")
# Mercado Pago (assinatura/providers/payment.py::MercadoPagoGatewayProvider):
# Access Token (TEST-... em sandbox, APP_USR-... em produção) + flag sandbox
# (quando True, o checkout devolvido é o `sandbox_init_point`). Sem token
# configurado, o provider falha alto ao ser usado — nunca silenciosamente.
ASSINATURA_MP_ACCESS_TOKEN = os.environ.get("ASSINATURA_MP_ACCESS_TOKEN", "")
ASSINATURA_MP_SANDBOX = env_bool("ASSINATURA_MP_SANDBOX", True)
# Segredo do webhook do MP (o "secret signature" que o painel do MP gera
# por aplicação, em Webhooks > Configure notificação). É o que
# autentica a origem da notificação: sem ele o endpoint público do
# webhook é aceito por qualquer um (ver
# `providers.payment.verificar_assinatura_webhook`). NUNCA entra no
# código nem no log; o valor vem só do ambiente.
ASSINATURA_MP_WEBHOOK_SECRET = os.environ.get("ASSINATURA_MP_WEBHOOK_SECRET", "")
# Conciliação com o provedor: a notificação do MP é at-least-once (ele
# reenvia até 8 vezes em ~4 dias), então existe uma rotina que pergunta ao
# provedor o que está acontecendo e corrige a divergência. Ela é a única
# forma de um pagamento perdido na notificação virar assinatura ativa.
ASSINATURA_INTERVALO_RECONCILIAR_MINUTOS = int(
    os.environ.get("ASSINATURA_INTERVALO_RECONCILIAR_MINUTOS", 60)
)
ASSINATURA_INTERVALO_PROCESSAR_VENCIMENTOS_MINUTOS = int(
    os.environ.get("ASSINATURA_INTERVALO_PROCESSAR_VENCIMENTOS_MINUTOS", 60)
)

# Mesmo raciocínio do bloco do EMAIL_BACKEND acima (e pelo mesmo motivo
# documentado lá: o boot de produção é o `import config.wsgi` do
# Gunicorn, que NÃO roda system checks — um check aqui passaria
# batido): se o provedor configurado é o Mercado Pago e o segredo do
# webhook não veio, o endpoint público do webhook recusa TODA
# notificação (fail-closed, ver
# `providers.payment.verificar_assinatura_webhook`), o cliente paga e a
# assinatura nunca é confirmada. Isso é invisível se não for dito alto,
# e a conciliação só sana quando o segredo existir.
if ASSINATURA_PAYMENT_GATEWAY_PROVIDER == "mercadopago" and not ASSINATURA_MP_WEBHOOK_SECRET:
    logging.getLogger("config.settings").error(
        "ASSINATURA_PAYMENT_GATEWAY_PROVIDER=mercadopago sem "
        "ASSINATURA_MP_WEBHOOK_SECRET: o webhook do Mercado Pago recusará "
        "toda notificação (a origem não pode ser autenticada) e nenhuma "
        "assinatura será confirmada por webhook — o cliente paga e a "
        "assinatura fica em pagamento_pendente. Defina o mesmo secret "
        "gerado no painel do MP (Webhooks > Configure notificação) antes "
        "de tratar a integração de pagamento como entregue."
    )

B2B_INTERVALO_VERIFICAR_ALERTAS_MINUTOS = int(
    os.environ.get("B2B_INTERVALO_VERIFICAR_ALERTAS_MINUTOS", 60)
)
CELERY_BEAT_SCHEDULE = {
    "catalogo-noticias-ingerir-noticias": {
        "task": "catalogo_noticias.tasks.ingerir_noticias",
        "schedule": CATALOGO_NOTICIAS_INTERVALO_INGESTAO_MINUTOS * 60,
    },
    "assinatura-processar-vencimentos": {
        "task": "assinatura.tasks.processar_vencimentos",
        "schedule": ASSINATURA_INTERVALO_PROCESSAR_VENCIMENTOS_MINUTOS * 60,
    },
    # Rede de segurança do dinheiro: a notificação do Mercado Pago é
    # at-least-once e pode se perder (deploy no meio do request, 500
    # transitório, ela nunca chegar). Esta task pergunta ao provedor o
    # que ele diz e corrige a divergência — inclusive reenviando um
    # cancelamento que não chegou lá.
    "assinatura-reconciliar-com-provedor": {
        "task": "assinatura.tasks.reconciliar_com_provedor",
        "schedule": ASSINATURA_INTERVALO_RECONCILIAR_MINUTOS * 60,
    },
    # BRD §27 — "Resumo da manhã" e "Resumo da noite" são envios distintos de
    # verdade (horário fixo via crontab, timezone America/Sao_Paulo — ver
    # CELERY_TIMEZONE abaixo), não só uma etiqueta: cada um só alcança
    # inscrições com esse `periodo` (newsletter.models.InscricaoNewsletter).
    # Gap real encontrado na análise do BRD: antes havia só 1 agendamento a
    # cada 12h corridas (sem horário fixo, sem filtro de período nenhum).
    "newsletter-enviar-manha": {
        "task": "newsletter.tasks.enviar_newsletters_manha",
        "schedule": crontab(hour=7, minute=0),
    },
    "newsletter-enviar-noite": {
        "task": "newsletter.tasks.enviar_newsletters_noite",
        "schedule": crontab(hour=19, minute=0),
    },
    # BRD §19 — "Alertas" quando novo conteúdo bate em um critério
    # monitorado é um item explícito do produto B2B. Gap real encontrado na
    # análise do BRD: nenhum mecanismo de alerta existia antes.
    "b2b-verificar-alertas": {
        "task": "b2b.tasks.verificar_alertas",
        "schedule": B2B_INTERVALO_VERIFICAR_ALERTAS_MINUTOS * 60,
    },
    # P1-03 (WS-06): heartbeat do beat. É a ÚNICA entrada desta agenda cujo
    # produto é um arquivo, e é o que permite dizer "a agenda rodou" em vez
    # de "o processo existe". Sem ela, `manage.py saude_filas` só conseguiria
    # responder `desconhecido` para o estado do beat — sempre.
    #
    # `config.tasks.heartbeat_beat` é despachado pelo beat e executado por um
    # WORKER, então o arquivo só é gravado se as duas pontas estiverem de pé.
    # (Um producer que roda fora do beat — um timer do systemd, por exemplo —
    # provaria apenas que o timer está vivo, que é o falso verde que este
    # item existe para eliminar.)
    "portal-heartbeat-beat": {
        "task": "config.tasks.heartbeat_beat",
        "schedule": FILAS_HEARTBEAT_INTERVALO_SEGUNDOS,
    },
}


# ---------------------------------------------------------------------------
# catalogo_noticias/ — ingestão, deduplicação e curadoria (ARCHITECTURE.md
# seções 2, 3 e 6; task-plan.md "Suposições assumidas").
# ---------------------------------------------------------------------------

# Fontes-semente (RSS público) — configuração, não hardcoded na lógica de
# negócio (`services/ingestao.py` lê daqui via
# `construir_fontes_configuradas()`). Nacionais (uf None) + regionais (uf =
# sigla). TODAS verificadas ao vivo em 2026-09-18 (HTTP 200 + entries com
# pubDate < 48h) via `manage.py descobrir_feeds` — ver
# `catalogo_noticias/fontes_candidatas.json` e `feeds_descobertos.json`.
# Excluídas com motivo (rodada 1): Estadão (sem feed RSS público), R7 (sem
# endpoint válido), Correio Braziliense (feed congelado em 2024), Mais Goiás
# (web-stories desatualizado; /feed principal vazio), IG homepage (usar
# Último Segundo).
# Excluídas com motivo (rodada 2, 2026-09-19 — lista do Alex, `descobrir_feeds`
# + checagem de frescura <48h; O Liberal usa o feed geral "OLiberal.com",
# O Estado do MA usa o feed do grupo Imirante): Correio 24h (feed congelado),
# Matinal (/rss vazio), Mais Goiás (reconfirmado desatualizado); sem RSS
# público (404/HTML em todos os padrões): Tribuna Hoje, A Crítica, Gazeta
# Digital, O Povo, O Popular, Hoje em Dia, O Tempo, FolhaPE, GaúchaZH,
# Correio do Povo, Itatiaia, Jornal do Comércio, Jornal do Tocantins,
# Diário da Amazônia, Meio Norte, AF Notícias, Rondônia Ovivo, Olhar Direto,
# ABC do ABC, Gazeta do Povo; anti-bot (403): MidiaMax, LeiaJá, JB;
# inacessíveis (SSL/timeout/525): JDia, Diário do Amazonas, Diário
# Catarinense, Correio de Sergipe, Diário do Grande ABC, Diario de
# Pernambuco, ES360.
CATALOGO_NOTICIAS_FONTES_RSS = [
    {"nome": "G1", "url": "https://g1.globo.com/rss/g1/", "uf": None},
    {"nome": "UOL Notícias", "url": "https://rss.uol.com.br/feed/noticias.xml", "uf": None},
    {"nome": "CNN Brasil", "url": "https://www.cnnbrasil.com.br/feed/", "uf": None},
    {"nome": "Folha - Em Cima da Hora", "url": "https://feeds.folha.uol.com.br/emcimadahora/rss091.xml", "uf": None},
    {"nome": "O Globo", "url": "https://oglobo.globo.com/rss/oglobo", "uf": None},
    {"nome": "Metrópoles", "url": "https://www.metropoles.com/feed", "uf": None},
    {"nome": "Terra", "url": "https://www.terra.com.br/rss", "uf": None},
    {"nome": "Veja", "url": "https://veja.abril.com.br/feed/", "uf": None},
    {"nome": "IstoÉ", "url": "https://istoe.com.br/feed", "uf": None},
    {"nome": "Agência Brasil", "url": "https://agenciabrasil.ebc.com.br/rss/ultimasnoticias/feed.xml", "uf": None},
    {"nome": "Jovem Pan", "url": "https://jovempan.com.br/feed", "uf": None},
    {"nome": "Poder360", "url": "https://www.poder360.com.br/feed/", "uf": None},
    {"nome": "Brasil 247", "url": "https://www.brasil247.com/feed", "uf": None},
    {"nome": "IG", "url": "https://ultimosegundo.ig.com.br/rss", "uf": None},
    {"nome": "Exame", "url": "https://www.exame.com/feed", "uf": None},
    {"nome": "BBC Brasil", "url": "https://feeds.bbci.co.uk/portuguese/rss.xml", "uf": None},
    {"nome": "CartaCapital", "url": "https://www.cartacapital.com.br/feed/", "uf": None},
    {"nome": "G1 AC", "url": "https://g1.globo.com/rss/g1/ac/acre/", "uf": "AC"},
    {"nome": "AC24horas", "url": "https://ac24horas.com/feed", "uf": "AC"},
    {"nome": "Acre.com.br", "url": "https://www.acre.com.br/feed/", "uf": "AC"},
    {"nome": "G1 AL", "url": "https://g1.globo.com/rss/g1/al/alagoas/", "uf": "AL"},
    {"nome": "TNH1", "url": "https://www.tnh1.com.br/feed/", "uf": "AL"},
    {"nome": "Gazetaweb", "url": "https://www.gazetaweb.com/feed", "uf": "AL"},
    {"nome": "G1 AM", "url": "https://g1.globo.com/rss/g1/am/amazonas/", "uf": "AM"},
    {"nome": "Em Tempo", "url": "https://emtempo.com.br/feed", "uf": "AM"},
    {"nome": "G1 AP", "url": "https://g1.globo.com/rss/g1/ap/amapa/", "uf": "AP"},
    {"nome": "Diário do Amapá", "url": "https://www.diariodoamapa.com.br/feed", "uf": "AP"},
    {"nome": "G1 BA", "url": "https://g1.globo.com/rss/g1/ba/bahia/", "uf": "BA"},
    {"nome": "A Tarde", "url": "https://atarde.com.br/rss", "uf": "BA"},
    {"nome": "Bahia Notícias", "url": "https://www.bahianoticias.com.br/principal/rss.xml", "uf": "BA"},
    {"nome": "G1 CE", "url": "https://g1.globo.com/rss/g1/ce/ceara/", "uf": "CE"},
    {"nome": "Diário do Nordeste", "url": "https://diariodonordeste.verdesmares.com.br/cmlink/feed-1.3009099", "uf": "CE"},
    {"nome": "Ceará Agora", "url": "https://cearaagora.com.br/feed/", "uf": "CE"},
    {"nome": "G1 DF", "url": "https://g1.globo.com/rss/g1/df/distrito-federal/", "uf": "DF"},
    {"nome": "Jornal de Brasília", "url": "https://jornaldebrasilia.com.br/feed", "uf": "DF"},
    {"nome": "G1 ES", "url": "https://g1.globo.com/rss/g1/es/espirito-santo/", "uf": "ES"},
    {"nome": "Folha Vitória", "url": "https://www.folhavitoria.com.br/feed/", "uf": "ES"},
    {"nome": "A Gazeta", "url": "https://www.agazeta.com.br/rss", "uf": "ES"},
    {"nome": "G1 GO", "url": "https://g1.globo.com/rss/g1/go/goias/", "uf": "GO"},
    {"nome": "DM", "url": "https://www.dm.com.br/feed", "uf": "GO"},
    {"nome": "Empreender em Goiás", "url": "https://www.empreenderemgoias.com.br/feed", "uf": "GO"},
    {"nome": "G1 MA", "url": "https://g1.globo.com/rss/g1/ma/maranhao/", "uf": "MA"},
    {"nome": "Jornal Pequeno", "url": "https://jornalpequeno.com.br/rss", "uf": "MA"},
    {"nome": "O Imparcial", "url": "https://oimparcial.com.br/rss", "uf": "MA"},
    {"nome": "O Estado do MA", "url": "https://imirante.com/rss", "uf": "MA"},
    {"nome": "G1 MG", "url": "https://g1.globo.com/rss/g1/mg/minas-gerais/", "uf": "MG"},
    {"nome": "Estado de Minas", "url": "https://www.em.com.br/feed", "uf": "MG"},
    {"nome": "G1 MS", "url": "https://g1.globo.com/rss/g1/ms/mato-grosso-do-sul/", "uf": "MS"},
    {"nome": "Campo Grande News", "url": "https://www.campograndenews.com.br/rss/rss.xml", "uf": "MS"},
    {"nome": "G1 MT", "url": "https://g1.globo.com/rss/g1/mt/mato-grosso/", "uf": "MT"},
    {"nome": "Diário de Cuiabá", "url": "https://www.diariodecuiaba.com.br/rss.php", "uf": "MT"},
    {"nome": "G1 PA", "url": "https://g1.globo.com/rss/g1/pa/para/", "uf": "PA"},
    {"nome": "DOL", "url": "https://dol.com.br/feed", "uf": "PA"},
    {"nome": "Diário do Pará", "url": "https://diariodopara.com.br/feed/", "uf": "PA"},
    {"nome": "O Liberal", "url": "https://www.oliberal.com/cmlink/oliberal-com-1.169551", "uf": "PA"},
    {"nome": "G1 PB", "url": "https://g1.globo.com/rss/g1/pb/paraiba/", "uf": "PB"},
    {"nome": "A União", "url": "https://auniao.pb.gov.br/RSS", "uf": "PB"},
    {"nome": "Jornal da Paraíba", "url": "https://jornaldaparaiba.com.br/rss", "uf": "PB"},
    {"nome": "WSCom", "url": "https://wscom.com.br/feed/", "uf": "PB"},
    {"nome": "G1 PE", "url": "https://g1.globo.com/rss/g1/pe/pernambuco/", "uf": "PE"},
    {"nome": "JC", "url": "https://jc.uol.com.br/ultimas/rss.xml", "uf": "PE"},
    {"nome": "G1 PI", "url": "https://g1.globo.com/rss/g1/pi/piaui/", "uf": "PI"},
    {"nome": "GP1", "url": "https://feeds.feedburner.com/portalgp1", "uf": "PI"},
    {"nome": "Cidade Verde", "url": "https://cidadeverde.com/rss", "uf": "PI"},
    {"nome": "G1 PR", "url": "https://g1.globo.com/rss/g1/pr/parana/", "uf": "PR"},
    {"nome": "Banda B", "url": "https://www.bandab.com.br/feed/", "uf": "PR"},
    {"nome": "Bem Paraná", "url": "https://www.bemparana.com.br/feed/", "uf": "PR"},
    {"nome": "Tribuna PR", "url": "https://www.tribunapr.com.br/feed/", "uf": "PR"},
    {"nome": "G1 RJ", "url": "https://g1.globo.com/rss/g1/rj/rio-de-janeiro/", "uf": "RJ"},
    {"nome": "Extra", "url": "https://extra.globo.com/rss/extra", "uf": "RJ"},
    {"nome": "O Dia", "url": "https://odia.ig.com.br/_conteudo/ultimas-noticias/rss.xml", "uf": "RJ"},
    {"nome": "G1 RN", "url": "https://g1.globo.com/rss/g1/rn/rio-grande-do-norte/", "uf": "RN"},
    {"nome": "Agora RN", "url": "https://agorarn.com.br/feed/", "uf": "RN"},
    {"nome": "Novo Notícias", "url": "https://www.novonoticias.com.br/feed", "uf": "RN"},
    {"nome": "Tribuna do Norte", "url": "https://tribunadonorte.com.br/feed/", "uf": "RN"},
    {"nome": "G1 RO", "url": "https://g1.globo.com/rss/g1/ro/rondonia/", "uf": "RO"},
    {"nome": "Rondônia Agora", "url": "https://www.rondoniagora.com/rss", "uf": "RO"},
    {"nome": "G1 RR", "url": "https://g1.globo.com/rss/g1/rr/roraima/", "uf": "RR"},
    {"nome": "Folha BV", "url": "https://www.folhabv.com.br/feed/", "uf": "RR"},
    {"nome": "Roraima em Tempo", "url": "https://roraimaemtempo.com.br/feed/", "uf": "RR"},
    {"nome": "G1 RS", "url": "https://g1.globo.com/rss/g1/rs/rio-grande-do-sul/", "uf": "RS"},
    {"nome": "G1 SC", "url": "https://g1.globo.com/rss/g1/sc/santa-catarina/", "uf": "SC"},
    {"nome": "ND+", "url": "https://ndmais.com.br/feed/", "uf": "SC"},
    {"nome": "NSC Total", "url": "https://www.nsctotal.com.br/feed", "uf": "SC"},
    {"nome": "SCC10", "url": "https://www.scc10.com.br/feed", "uf": "SC"},
    {"nome": "G1 SP", "url": "https://g1.globo.com/rss/g1/sp/sao-paulo/", "uf": "SP"},
    {"nome": "G1 SE", "url": "https://g1.globo.com/rss/g1/se/sergipe/", "uf": "SE"},
    {"nome": "Infonet", "url": "https://infonet.com.br/feed/", "uf": "SE"},
    {"nome": "FaxAju", "url": "https://www.faxaju.com.br/feed/", "uf": "SE"},
    {"nome": "G1 TO", "url": "https://g1.globo.com/rss/g1/to/tocantins/", "uf": "TO"},
    {"nome": "Cleber Toledo", "url": "https://clebertoledo.com.br/feed/", "uf": "TO"},
]

# Critério de alta relevância (aciona fila de revisão humana) —
# task-plan.md, "Suposições assumidas": categoria sensível OU cluster com N+
# fontes distintas. Ambos parametrizáveis via variável de ambiente, sem
# alteração de código (implementation-contract.md, critério de aceite 7).
CATALOGO_NOTICIAS_CATEGORIAS_SENSIVEIS = [
    c.strip().lower()
    for c in os.environ.get(
        "CATALOGO_NOTICIAS_CATEGORIAS_SENSIVEIS", "política,economia,segurança pública"
    ).split(",")
    if c.strip()
]
CATALOGO_NOTICIAS_LIMIAR_FONTES_ALTA_RELEVANCIA = int(
    os.environ.get("CATALOGO_NOTICIAS_LIMIAR_FONTES_ALTA_RELEVANCIA", 3)
)

# Limiar de similaridade de título (0.0-1.0) usado por
# `services/deduplicacao.py` para agrupar itens no mesmo NewsCluster.
CATALOGO_NOTICIAS_DEDUP_LIMIAR_SIMILARIDADE = float(
    os.environ.get("CATALOGO_NOTICIAS_DEDUP_LIMIAR_SIMILARIDADE", 0.55)
)

# Finding 1 (code-review-contract.md run 20260902-0727-ingestao-noticias, 3a
# passada, major — REABERTO pela 2a vez, mudanca de ESTRATEGIA, nao mais uma
# lista de palavras): as duas rodadas anteriores tentaram fechar falsos-
# positivos de agrupamento (duas manchetes de FATOS DIFERENTES que
# compartilham vocabulario institucional/jornalistico) ampliando uma lista
# curada de "conectores comuns". O reviewer provou, com numeros concretos,
# que NENHUM limiar de similaridade (nem estatico, nem calculado a partir do
# tamanho do lote) consegue separar esses dois casos de forma confiavel:
#   - falso-positivo real (fatos DIFERENTES, vocabulario institucional
#     coincidente nao coberto pela lista curada): "Ministerio da Saude
#     confirma novo surto de dengue" vs "...sarampo" pontua 0.72;
#   - par genuino (MESMO fato, fontes diferentes): "Nova vacina e aprovada
#     pela agencia reguladora" vs "Agencia reguladora aprova nova vacina"
#     pontua 0.61.
# Ou seja, o falso-positivo pontua ACIMA de um par genuino real — nao existe
# NENHUM valor de limiar (nem de tamanho de lote minimo) que classifique um
# corretamente sem classificar o outro errado. Isso nao e uma lacuna de
# cobertura de vocabulario (corrigivel adicionando mais palavras): e uma
# propriedade matematica da heuristica lexical (Jaccard ponderado) em si,
# que so teria solucao real com dedup semantica (embeddings), fora do escopo
# deste MVP.
#
# Dado que a heuristica de AGRUPAMENTO (services/deduplicacao.py) nao pode
# garantir, por si so, que dois itens agrupados sao de fato o MESMO
# acontecimento, a defesa estrutural contra misattribution (BRD secao 18)
# passa a ser: TODO NewsCluster formado por agrupamento automatico (2+
# itens combinados em um unico resumo_proprio compartilhado) exige revisao
# humana por padrao — status_revisao=pendente — independente do numero de
# fontes distintas ou da categoria (o criterio de aceite 5 original,
# "categoria sensivel OU 3+ fontes", continua vigente e testado tal como
# especificado, mas so tem efeito pratico sobre itens STANDALONE, que nunca
# tiveram risco de mistura de conteudo de fatos diferentes — ver
# `services/ingestao.py::_persistir_grupo`/`_persistir_grupo_mesclado`).
#
# Configuravel (nao hardcoded) para permitir que um operador de negocio,
# ciente do risco residual documentado acima, opte por voltar ao
# comportamento anterior (fontes/categoria como unico criterio) definindo
# esta variavel como "false" — mas o DEFAULT e o comportamento seguro
# (True), dado que direitos autorais/misattribution e a restricao mais
# critica deste run (review-triggers.md, presente nas 3 passadas de review).
CATALOGO_NOTICIAS_DEDUP_CLUSTER_SEMPRE_EXIGE_REVISAO = env_bool(
    "CATALOGO_NOTICIAS_DEDUP_CLUSTER_SEMPRE_EXIGE_REVISAO", True
)

# Janela de tempo (horas) — code-review-contract.md run
# 20260902-0727-ingestao-noticias, Finding 3 (major): alem dos itens do LOTE
# ATUAL, `services/ingestao.py::executar_ingestao` tambem compara os itens
# novos contra `NewsItem`s JA PERSISTIDOS nesta janela recente (nao o
# historico inteiro do banco — evita comparar contra tudo). 24h cobre o
# cenario tipico do reviewer (G1 as 10:00, UOL/CNN Brasil as 10:15 sobre o
# mesmo fato) com folga generosa sem custar uma tabela inteira.
CATALOGO_NOTICIAS_DEDUP_JANELA_RECENTE_HORAS = float(
    os.environ.get("CATALOGO_NOTICIAS_DEDUP_JANELA_RECENTE_HORAS", 24)
)

# Finding 5 (code-review-contract.md run 20260902-0727-ingestao-noticias,
# minor/performance): teto superior de `NewsItem`s recentes trazidos por
# `_itens_recentes_persistidos` para dentro do MESMO lote de agrupamento a
# cada execucao, alem do filtro por janela de tempo acima — evita que o
# custo O(n^2) de `agrupar_itens_brutos` cresca sem limite junto com o
# volume acumulado de noticias das ultimas
# `CATALOGO_NOTICIAS_DEDUP_JANELA_RECENTE_HORAS` em um dia de alto volume.
# 300 e uma folga generosa para as 4 fontes-semente do contrato (bem acima
# do volume tipico de um dia inteiro a cada 15 min), configuravel sem
# alteracao de codigo caso o volume real de producao exija ajuste.
CATALOGO_NOTICIAS_DEDUP_MAX_ITENS_RECENTES = int(
    os.environ.get("CATALOGO_NOTICIAS_DEDUP_MAX_ITENS_RECENTES", 300)
)

# Limiar de similaridade (0.0-1.0, SequenceMatcher) ACIMA do qual
# `resumo_proprio` é considerado copia/quase-copia de `conteudo_bruto` e o
# item e forcado para status_revisao=pendente em vez de ser publicado
# automaticamente (code-review-contract.md run 20260902-0727-ingestao-noticias,
# Finding 1 — BRD secao 18, direitos autorais). 0.6 deixa margem de seguranca
# acima da similaridade tipica de um resumo genuinamente autoral (<0.5, ver
# testes de AC-4) e abaixo de uma copia literal (1.0).
CATALOGO_NOTICIAS_RESUMO_SIMILARIDADE_MAXIMA = float(
    os.environ.get("CATALOGO_NOTICIAS_RESUMO_SIMILARIDADE_MAXIMA", 0.6)
)

# Finding 2 (code-review-contract.md run 20260902-0727-ingestao-noticias, 2a
# passada, major): `CATALOGO_NOTICIAS_RESUMO_SIMILARIDADE_MAXIMA` acima usa
# SequenceMatcher.ratio() sobre os DOIS textos inteiros — insensivel a copia
# VERBATIM de um trecho CURTO dentro de um conteudo_bruto bem mais longo
# (a formula 2*M/T penaliza pela diferenca de tamanho). Este segundo limiar
# complementa o primeiro: proporcao (0.0-1.0) do PROPRIO resumo (nao do
# texto combinado) que aparece como sequencia continua identica em algum
# trecho do conteudo_bruto (ver
# `services/ingestao.py::_proporcao_do_resumo_copiada_literalmente`). 0.6
# significa "60% ou mais do resumo e, literalmente, um trecho copiado do
# bruto" — acima da sobreposicao tipica de uma sintese autoral que apenas
# reaproveita nomes proprios/numeros/citacoes curtas (ver testes de AC-4).
CATALOGO_NOTICIAS_RESUMO_TRECHO_COPIADO_MAXIMO = float(
    os.environ.get("CATALOGO_NOTICIAS_RESUMO_TRECHO_COPIADO_MAXIMO", 0.6)
)

# SummarizationProvider (ARCHITECTURE.md seção 6/8) — implementação concreta
# `LLMHttpSummarizationProvider` usa um formato de API HTTP compatível com
# "Chat Completions" (OpenAI e diversos provedores compatíveis). Nenhuma
# credencial real neste ambiente — CATALOGO_NOTICIAS_LLM_API_KEY fica vazia
# por padrão; provedor concreto de produção é decisão em aberto
# (ARCHITECTURE.md seção 8), documentada em implementation-history.md.
CATALOGO_NOTICIAS_LLM_API_BASE_URL = os.environ.get(
    "CATALOGO_NOTICIAS_LLM_API_BASE_URL", "https://api.openai.com/v1"
)
CATALOGO_NOTICIAS_LLM_API_KEY = os.environ.get("CATALOGO_NOTICIAS_LLM_API_KEY", "")
CATALOGO_NOTICIAS_LLM_MODEL = os.environ.get("CATALOGO_NOTICIAS_LLM_MODEL", "gpt-4o-mini")
CATALOGO_NOTICIAS_LLM_TIMEOUT_SEGUNDOS = int(
    os.environ.get("CATALOGO_NOTICIAS_LLM_TIMEOUT_SEGUNDOS", 30)
)

# Reducao de custo/numero de chamadas ao SummarizationProvider (pedido do
# usuario apos configurar uma chave real de LLM): quantos itens
# INDEPENDENTES entram em uma unica chamada HTTP de
# `resumir_e_classificar_em_lote` (providers/summarization.py) — trade-off
# documentado la: um lote maior custa menos chamadas, mas se a chamada
# inteira falhar (rede/parsing), TODOS os itens daquele lote caem no
# fallback de erro juntos, nao so 1.
CATALOGO_NOTICIAS_LLM_TAMANHO_LOTE = int(os.environ.get("CATALOGO_NOTICIAS_LLM_TAMANHO_LOTE", 10))

# Teto de tokens de RESPOSTA por item (multiplicado pelo tamanho do lote na
# chamada em lote) — sem isso, uma resposta prolixa do provedor custa mais
# tokens de saida (cobrados a taxa mais alta que os de entrada, na maioria
# dos provedores) do que o necessario para um resumo curto de 2-4 frases.
CATALOGO_NOTICIAS_LLM_MAX_TOKENS_POR_ITEM = int(
    os.environ.get("CATALOGO_NOTICIAS_LLM_MAX_TOKENS_POR_ITEM", 220)
)

# Teto de custo diário (USD, estimado a partir de tokens consumidos) para o
# SummarizationProvider — mitigação direta do risco "Custo de IA/infraestrutura"
# (BRD seção 30, impacto Alto: "Observabilidade e limites de consumo").
# `providers/summarization.py` deve registrar o custo estimado de cada
# chamada em `metricas` (ARCHITECTURE.md seção 7, "Custo de IA controlado" —
# observável desde o MVP) e, se o acumulado do dia corrente ultrapassar este
# teto, `services/ingestao.py` deve parar de chamar o provedor e cair para o
# fallback sem LLM (item vai para revisão humana em vez de resumo
# automático) até a virada do dia — nunca estourar orçamento silenciosamente.
CATALOGO_NOTICIAS_LLM_TETO_GASTO_DIARIO_USD = float(
    os.environ.get("CATALOGO_NOTICIAS_LLM_TETO_GASTO_DIARIO_USD", 5.0)
)

# Preco estimado (USD por 1000 tokens, entrada+saida somados) usado para
# calcular `ResultadoResumo.custo_estimado_usd` em `providers/summarization.py`
# a partir de `tokens_utilizados` (implementation-contract.md, run
# 20260903-1211-teto-gasto-diario-llm) — SEMPRE uma ESTIMATIVA, nunca a
# tabela de precos real de um provedor especifico (decisao de provedor
# concreto continua em aberto, ver ARCHITECTURE.md secao 8). Derivacao do
# default (gpt-4o-mini, default de CATALOGO_NOTICIAS_LLM_MODEL acima):
# entrada $0.15/1M = $0.00015/1k, saida $0.60/1M = $0.0006/1k; lote tipico
# de 10 itens ~= 5000 tokens in + 2200 out ~= $0.00207/7200 tokens ~=
# $0.00029/1k, arredondado para cima (conservador) => 0.0003. Revisar quando
# o provedor de producao for escolhido; ajuste via env var sem alterar codigo.
CATALOGO_NOTICIAS_LLM_PRECO_USD_POR_1K_TOKENS = float(
    os.environ.get("CATALOGO_NOTICIAS_LLM_PRECO_USD_POR_1K_TOKENS", 0.0003)
)


# ---------------------------------------------------------------------------
# Feed público — P1 performance (run 20260923-1216-p1-feed-cache-indices).
# ---------------------------------------------------------------------------

# Janela de listagem do feed (horas): `feed.services.itens_publicaveis`
# filtra `timestamp_ingestao >= agora - janela`. Cobre o ciclo de notícias
# sem varrer o acervo inteiro a cada request.
FEED_JANELA_HORAS = float(os.environ.get("FEED_JANELA_HORAS", 72))

# TTL (segundos) do cache das listagens públicas do feed
# (`FeedListView`, seções, destaques, urgentes, mais-lidas — ver
# `feed/views.py`). Staleness curta é aceitável (o frontend já pratica ISR
# de 60s) e dispensa invalidação explícita na ingestão.
FEED_CACHE_TTL_SEGUNDOS = int(os.environ.get("FEED_CACHE_TTL_SEGUNDOS", 45))

# TTL (segundos) do cache curto de configuração de gating (flag
# `ConfiguracaoSistema.premium_ativo` + `MeusRecursosView` — ver
# `gating/services.py`). Mesma ordem de grandeza do cache do feed.
GATING_CACHE_TTL_SEGUNDOS = int(os.environ.get("GATING_CACHE_TTL_SEGUNDOS", 45))

# ---------------------------------------------------------------------------
# b2b/ — isolamento, cota e limites de alerta (backlog P1-13 "B2B completo",
# workstream WS-12). Configuração, não código hardcoded: o comercial ajusta
# cota/plano e o teto de alertas por ambiente sem alterar código/redeploy do
# worker, mesmo padrão de `FEED_*`/`GATING_*` acima.
# ---------------------------------------------------------------------------

# TTL (segundos) do cache do painel B2B (`itens_monitorados` /
# `resumo_executivo` — as únicas consultas caras do app, uma por critério).
# A chave carrega OBRIGATORIAMENTE o id da organização (ver
# `b2b/cache.py`): sem o namespace de tenant no prefixo, a resposta de uma
# empresa serviria para outra. Invalidação explícita em toda escrita de
# critério; o TTL cobre falha/evento de invalidação.
B2B_CACHE_TTL_SEGUNDOS = int(os.environ.get("B2B_CACHE_TTL_SEGUNDOS", 45))

# Cota de critérios de monitoramento por plano comercial. É o teto de trabalho
# que UMA execução de `verificar_e_enviar_alertas` faz por tenant: cada
# criterio ativo vira uma varredura de `NewsItem`. Sem cota, uma organização
# (ou uma conta comprometida) criaria critérios sem limite e transformaria o
# job periódico em laço de varredura. Derivado de `Organizacao.plano` (campo
# que já existe — nenhuma migration necessária para esta entrega).
B2B_COTA_CRITERIOS_BASIC = int(os.environ.get("B2B_COTA_CRITERIOS_BASIC", 5))
B2B_COTA_CRITERIOS_PRO = int(os.environ.get("B2B_COTA_CRITERIOS_PRO", 25))
B2B_COTA_CRITERIOS_ENTERPRISE = int(os.environ.get("B2B_COTA_CRITERIOS_ENTERPRISE", 100))

# Teto de itens devolvidos por critério em `itens_monitorados`/`resumo_executivo`.
# A listagem é materializada em memória e ia sem teto: um critério genérico
# ("economia") casa com dezenas de milhares de `NewsItem` na janela e serializa
# tudo numa resposta. `numero_itens` continua sendo o total VERDADEIRO (count
# escopado na organização) — o teto limita só o corpo da lista.
B2B_MAX_ITENS_POR_CRITERIO = int(os.environ.get("B2B_MAX_ITENS_POR_CRITERIO", 50))

# Teto de itens por e-mail de alerta (BRD §19) — o destinatário recebe no
# máximo isto; o resto entra na próxima execução pelo ratchet de
# `ultimo_alerta_em`.
B2B_ALERTA_MAX_ITENS = int(os.environ.get("B2B_ALERTA_MAX_ITENS", 20))

# Teto de e-mails de alerta por execução do job, no total. Teto global de
# storm: mesmo com N organizações e M critérios, uma execução não passa disto
# (os critérios não processados voltam na próxima — o ratchet de
# `ultimo_alerta_em` não é consumido por um envio suprimido). O excedente é
# contado e logado como `total_alertas_suprimidos_por_limite_execucao`.
B2B_ALERTA_MAX_POR_EXECUCAO = int(os.environ.get("B2B_ALERTA_MAX_POR_EXECUCAO", 50))

# Teto de e-mails de alerta por organização em uma execução. Sem isto, uma
# organização com muitos critérios concentration o envio e esmaga o restante.
B2B_ALERTA_MAX_POR_ORGANIZACAO = int(os.environ.get("B2B_ALERTA_MAX_POR_ORGANIZACAO", 3))

# Intervalo mínimo (minutos) entre dois alertas do MESMO critério. O ratchet de
# `ultimo_alerta_em` só impede reenvio do MESMO item; sem cooldown, um fluxo
# contínuo de notícias vira um e-mail por execução, por critério. O cooldown
# adia, não cancela: passado o intervalo, o que entrou desde o último alerta
# sai na próxima execução.
B2B_ALERTA_COOLDOWN_MINUTOS = int(os.environ.get("B2B_ALERTA_COOLDOWN_MINUTOS", 240))


# ---------------------------------------------------------------------------
# Observabilidade (ARCHITECTURE.md — nova arquitetura de infra, 2026-09-03).
# ---------------------------------------------------------------------------

# Logging estruturado para stdout — em produção, os containers rodam sob
# Docker/Caddy sem acesso interativo a um terminal; `docker compose logs` e
# qualquer coletor de log (ex.: `docker logs` + logrotate na VPS) esperam
# stdout/stderr, não um arquivo de log local dentro do container (que some
# quando o container é recriado a cada deploy).
# DJANGO_LOG_JSON=true ativa saída JSON (requer python-json-logger); fallback
# silencioso para verbose se a lib não estiver instalada.
_USE_JSON_LOG = env_bool("DJANGO_LOG_JSON", False)
try:
    if _USE_JSON_LOG:
        import pythonjsonlogger.jsonlogger  # noqa: F401

        _LOG_FORMATTER = "json"
    else:
        _LOG_FORMATTER = "verbose"
except ImportError:
    _LOG_FORMATTER = "verbose"

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {
        "request_id": {
            "()": "config.middleware.RequestIdLogFilter",
        },
    },
    "formatters": {
        "verbose": {
            "format": "%(asctime)s %(levelname)s %(name)s [%(module)s] [%(request_id)s] %(message)s",
        },
        "json": {
            "()": "pythonjsonlogger.jsonlogger.JsonFormatter",
            "format": "%(asctime)s %(levelname)s %(name)s %(module)s %(request_id)s %(message)s",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": _LOG_FORMATTER,
            "filters": ["request_id"],
        },
    },
    "root": {
        "handlers": ["console"],
        "level": os.environ.get("DJANGO_LOG_LEVEL", "INFO"),
    },
    "loggers": {
        "django.request": {
            "handlers": ["console"],
            "level": "WARNING",
            "propagate": False,
        },
    },
}

# Sentry (rastreamento de erros) — opcional e desligado por padrão
# (SENTRY_DSN vazio = sentry_sdk nunca é importado nem inicializado, custo
# zero quando não configurado). Cobre a lacuna descrita em
# project-portal-noticias-tool-outage: uma boa parte deste projeto foi
# escrita sem poder executar/testar de verdade — captura de erro real em
# produção é a rede de segurança que substitui aquela validação que faltou.
SENTRY_DSN = os.environ.get("SENTRY_DSN", "")
if SENTRY_DSN:
    import sentry_sdk
    from sentry_sdk.integrations.celery import CeleryIntegration
    from sentry_sdk.integrations.django import DjangoIntegration

    sentry_sdk.init(
        dsn=SENTRY_DSN,
        integrations=[DjangoIntegration(), CeleryIntegration()],
        traces_sample_rate=float(os.environ.get("SENTRY_TRACES_SAMPLE_RATE", 0.1)),
        environment=os.environ.get("SENTRY_ENVIRONMENT", "production" if not DEBUG else "development"),
        send_default_pii=False,
    )
