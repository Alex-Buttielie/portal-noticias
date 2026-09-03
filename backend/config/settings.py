"""
Django settings for config project (módulo identidade/ — cadastro, autenticação,
onboarding do Portal de Notícias).

Gerado por 'django-admin startproject' e customizado conforme
`agentic-framework/state/run-20260901-2135-cadastro-auth/implementation-contract.md`.

Decisões de configuração relevantes estão documentadas em
`agentic-framework/state/run-20260901-2135-cadastro-auth/implementation-history.md`.
"""

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

# Falha explícita e cedo (na inicialização, não em produção sob ataque) se
# alguém tentar rodar com DEBUG=False (indicando produção) mas ainda com a
# SECRET_KEY fraca de fallback — nunca deve ser possível subir "produção"
# silenciosamente insegura por esquecimento de configurar DJANGO_SECRET_KEY
# (code-review-contract.md Finding 3).
if not DEBUG and SECRET_KEY == _SECRET_KEY_FALLBACK:
    raise ImproperlyConfigured(
        "DJANGO_SECRET_KEY não foi definida (está usando o valor de fallback "
        "de desenvolvimento) com DEBUG=False. Defina uma SECRET_KEY forte e "
        "única via variável de ambiente antes de rodar fora de "
        "desenvolvimento local (ou defina DJANGO_DEBUG=true apenas para "
        "desenvolvimento)."
    )

ALLOWED_HOSTS = [
    h.strip() for h in os.environ.get("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",") if h.strip()
]

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
    SECURE_SSL_REDIRECT = env_bool("DJANGO_SECURE_SSL_REDIRECT", True)
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
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
    "identidade",
    "catalogo_noticias",
    "feed",
    "gating",
    "assinatura",
    "credenciamento",
    "comunidade",
    "moderacao",
    "radar",
    "newsletter",
    "landing",
    "b2b",
    "metricas",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
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
    },
}


# ---------------------------------------------------------------------------
# Cache (ARCHITECTURE.md — nova arquitetura de infra, 2026-09-03). Até esta
# mudança, Redis só era usado como broker/result backend do Celery — não
# havia NENHUM cache de aplicação configurado (Django caía no default
# `LocMemCache` implícito, que não é compartilhado entre os processos
# Gunicorn nem sobrevive a um restart/deploy). Usado por `feed/` para
# cachear listagens públicas (alto volume de leitura, o padrão de tráfego
# dominante deste produto) e invalidado explicitamente no evento
# `plano.preco_alterado` (ARCHITECTURE.md seção 5) — ver `gating`/`assinatura`
# services. Em desenvolvimento local sem Redis disponível, cai para
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
# Não há integração real com um provedor transacional (SendGrid, SES, etc.)
# neste escopo — decisão em aberto (ver implementation-contract.md,
# "Não-objetivos"). Em desenvolvimento/teste, usa o backend "console" do
# Django (imprime o e-mail no stdout) para permitir inspecionar tokens de
# verificação/redefinição de senha manualmente. Em produção, definir
# DJANGO_EMAIL_BACKEND explicitamente para um backend real.
EMAIL_BACKEND = os.environ.get(
    "DJANGO_EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend"
)
DEFAULT_FROM_EMAIL = os.environ.get("DJANGO_DEFAULT_FROM_EMAIL", "no-reply@brdportalnoticias.local")

# Front-end (run 20260902-1448-frontend-mvp-web, frontend/ na raiz do
# projeto) — usado para montar links absolutos nos e-mails de
# verificação/redefinição de senha (ex.: {FRONTEND_BASE_URL}/verificar-email)
# e como origem permitida de CORS abaixo.
FRONTEND_BASE_URL = os.environ.get("FRONTEND_BASE_URL", "http://localhost:3000")

# CORS: o frontend Next.js roda em origem diferente (localhost:3000) do
# backend (localhost:8000) — chamadas fetch() do navegador exigem CORS
# habilitado explicitamente. Só a origem do próprio frontend é permitida
# (não CORS_ALLOW_ALL_ORIGINS=True, que seria excessivamente permissivo).
CORS_ALLOWED_ORIGINS = [FRONTEND_BASE_URL]
CORS_ALLOW_CREDENTIALS = True

# Expiração de tokens (segundos).
EMAIL_VERIFICATION_TOKEN_MAX_AGE_SECONDS = int(
    os.environ.get("EMAIL_VERIFICATION_TOKEN_MAX_AGE_SECONDS", 60 * 60 * 24)  # 24h
)
PASSWORD_RESET_TIMEOUT = int(
    os.environ.get("PASSWORD_RESET_TIMEOUT_SECONDS", 60 * 60)  # 1h — usado pelo PasswordResetTokenGenerator
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

# Intervalo (minutos) do job periódico de ingestão de notícias — configurável
# sem alteração de código/deploy do worker.
CATALOGO_NOTICIAS_INTERVALO_INGESTAO_MINUTOS = int(
    os.environ.get("CATALOGO_NOTICIAS_INTERVALO_INGESTAO_MINUTOS", 15)
)
ASSINATURA_INTERVALO_PROCESSAR_VENCIMENTOS_MINUTOS = int(
    os.environ.get("ASSINATURA_INTERVALO_PROCESSAR_VENCIMENTOS_MINUTOS", 60)
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
}


# ---------------------------------------------------------------------------
# catalogo_noticias/ — ingestão, deduplicação e curadoria (ARCHITECTURE.md
# seções 2, 3 e 6; task-plan.md "Suposições assumidas").
# ---------------------------------------------------------------------------

# Fontes-semente (RSS público) — configuração, não hardcoded na lógica de
# negócio (`services/ingestao.py` lê daqui via
# `construir_fontes_configuradas()`). URLs validadas manualmente em
# 2026-09-02 pelo executor (ver implementation-history.md); nenhuma
# substituição foi necessária — todas retornaram HTTP 200 (CNN Brasil via
# redirect 302 -> 200, seguido automaticamente pelo cliente HTTP).
CATALOGO_NOTICIAS_FONTES_RSS = [
    {"nome": "G1", "url": "https://g1.globo.com/rss/g1/"},
    {"nome": "UOL", "url": "https://rss.uol.com.br/feed/noticias.xml"},
    {"nome": "CNN Brasil", "url": "https://www.cnnbrasil.com.br/feed/"},
    {"nome": "Folha - Em Cima da Hora", "url": "https://feeds.folha.uol.com.br/emcimadahora/rss091.xml"},
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
# concreto continua em aberto, ver ARCHITECTURE.md secao 8). Default 0.15 na
# mesma faixa de mercado de um modelo economico tipo `gpt-4o-mini` (o proprio
# default de CATALOGO_NOTICIAS_LLM_MODEL acima) — ajustar via env var quando
# o provedor real de producao for escolhido, sem alterar codigo.
CATALOGO_NOTICIAS_LLM_PRECO_USD_POR_1K_TOKENS = float(
    os.environ.get("CATALOGO_NOTICIAS_LLM_PRECO_USD_POR_1K_TOKENS", 0.15)
)


# ---------------------------------------------------------------------------
# Observabilidade (ARCHITECTURE.md — nova arquitetura de infra, 2026-09-03).
# ---------------------------------------------------------------------------

# Logging estruturado para stdout — em produção, os containers rodam sob
# Docker/Caddy sem acesso interativo a um terminal; `docker compose logs` e
# qualquer coletor de log (ex.: `docker logs` + logrotate na VPS) esperam
# stdout/stderr, não um arquivo de log local dentro do container (que some
# quando o container é recriado a cada deploy).
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "%(asctime)s %(levelname)s %(name)s [%(module)s] %(message)s",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
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
    from sentry_sdk.integrations.django import DjangoIntegration

    sentry_sdk.init(
        dsn=SENTRY_DSN,
        integrations=[DjangoIntegration()],
        traces_sample_rate=float(os.environ.get("SENTRY_TRACES_SAMPLE_RATE", 0.1)),
        environment=os.environ.get("SENTRY_ENVIRONMENT", "production" if not DEBUG else "development"),
        send_default_pii=False,
    )
