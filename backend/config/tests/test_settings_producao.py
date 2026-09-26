"""
Integridade funcional de `config/settings.py` no caminho de PRODUÇÃO
(item de backlog P0-02b, workstream WS-02, gate GP-1b).

O gate GP-1b exige que `manage.py check` e o import de `config.settings`
sejam verdes no SHA de release **em configuração de produção**
(`DEBUG=False`, `SECRET_KEY` forte, `ALLOWED_HOSTS` preenchido) — não
apenas no modo relaxado de desenvolvimento. Este módulo fixa esse
comportamento como regressão automatizada, para que uma edição futura de
`config/settings.py` que quebre a subida em produção deixe de ser verde
no CI.

Por que subprocesso, e não `importlib.reload` ou `override_settings`
O bloco de hardening de produção e as duas travas de ambiente de
`config/settings.py` são decididos **no import do módulo**, por código de
toplevel (`if not DEBUG:` em `config/settings.py:81` e os dois
`raise ImproperlyConfigured` em `config/settings.py:59` e
`config/settings.py:229`). Não existe forma de exercitar o outro lado
dessas decisões dentro do processo de teste: o Django já está
inicializado com `config.settings_test` (`pytest.ini`) e recarregar o
módulo no mesmo processo exigiria religar `django.conf.settings` e
`django.setup()` por baixo dos testes, contaminando o estado global de
toda a suíte. Um `python -c` isolado é a única aproximação honesta — e é
exatamente o que o processo de produção faz (Gunicorn/PM2 importam
`config.wsgi` → `config.settings` em um processo novo).

Por que isto NÃO é um módulo de settings de teste
`config/settings_test.py` (referenciado por `pytest.ini`) existe e é o
settings module **da suíte**; ele é importado por TODO teste, inclusive
estes. Ele força `DJANGO_DEBUG=true` via o ambiente do CI e define
`DJANGO_SECRET_KEY` com `os.environ.setdefault` justamente para
*desabilitar* as travas de `config/settings.py` — ou seja, é justamente
o oposto do que este módulo precisa verificar. Ele não pode ser
reaproveitado aqui: ao ser importado, ele já fixa o ambiente e o
settings module que os testes usam. Este módulo então fala diretamente
com `config.settings` (o alvo real do gate) em processos próprios, via
`DJANGO_SETTINGS_MODULE=config.settings`, e por isso não precisa — e não
deve — de nenhum settings module intermediário.

Observação sobre cobertura de linhas
Estes testes são *comportamentais*: eles não movem a porcentagem de
cobertura de `config/settings.py`, porque um `if not DEBUG:` no nível de
módulo só pode ser percorrido por UM dos lados dentro de um mesmo
processo, e a suíte roda com `DJANGO_DEBUG=true` (env do job de CI em
`.github/workflows/ci.yml`). O que eles compram é a garantia de que o
ramo de produção continua executável — que nenhuma métrica de cobertura
consegue expressar.
"""

from __future__ import annotations

import json
import os
import re
import secrets
import subprocess
import sys
from pathlib import Path

# config/tests/test_settings_producao.py -> parents[0]=tests, [1]=config,
# [2]=backend. É o diretório que precisa estar no caminho para
# `import config.settings` resolver, e onde `manage.py` mora.
BACKEND_DIR = Path(__file__).resolve().parents[2]

# Gerado por execução, nunca um segredo real: o gate exige uma
# SECRET_KEY forte, e `secrets.token_urlsafe(64)` produz 86 caracteres de
# entropia real sem nunca tocar em material de produção.
def _chave_forte() -> str:
    return secrets.token_urlsafe(64)


# Variáveis que decidem QUAL ramo de `config/settings.py` é executado. São
# removidas do ambiente filho antes de cada execução para que o teste não
# dependa do que a máquina ou o job de CI tenham exportado — sem esta
# limpeza, um `DJANGO_DEBUG=true` ou um `DJANGO_SECRET_KEY` ambiente
# (o próprio `settings_test.py` define um via `setdefault`!) mudaria o
# ramo sob teste e o teste passaria por acidente medindo outra coisa.
_VARS_DE_RAMO = (
    "DJANGO_SETTINGS_MODULE",
    "DJANGO_DEBUG",
    "DJANGO_SECRET_KEY",
    "DJANGO_ALLOWED_HOSTS",
    "DJANGO_DB_ENGINE",
    "DJANGO_SECURE_SSL_REDIRECT",
    "DJANGO_SESSION_COOKIE_SECURE",
    "DJANGO_CSRF_COOKIE_SECURE",
    "DJANGO_SECURE_HSTS_SECONDS",
    "DJANGO_CACHE_BACKEND",
    "DJANGO_LOG_JSON",
    "SENTRY_DSN",
)


def _env_producao(**extra: str) -> dict[str, str]:
    """Ambiente de PRODUÇÃO para o processo filho: DEBUG desligado
    explicitamente, SECRET_KEY forte e ALLOWED_HOSTS preenchido — as três
    condições do critério de saída do gate GP-1b."""
    env = dict(os.environ)
    for var in _VARS_DE_RAMO:
        env.pop(var, None)
    env["DJANGO_SETTINGS_MODULE"] = "config.settings"
    env["DJANGO_DEBUG"] = "false"
    env["DJANGO_SECRET_KEY"] = _chave_forte()
    env["DJANGO_ALLOWED_HOSTS"] = "portal-noticias.com"
    env.update(extra)
    return env


def _rodar(env: dict[str, str], *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, *args],
        cwd=BACKEND_DIR,
        env=env,
        capture_output=True,
        text=True,
        timeout=300,
    )


# Trechos executados no processo filho. Cada um imprime uma linha
# `P0-02B_JSON=<...>` para o pai parsear — assim as asserções ficam sobre
# os VALORES efetivos do settings, e não sobre texto de traceback.
_SNIPPET_PRODUCAO = """
import json
import django
import config.settings as s

django.setup()
from django.conf import settings as ds

print("P0-02B_JSON=" + json.dumps({
    "DEBUG": ds.DEBUG,
    "ALLOWED_HOSTS": ds.ALLOWED_HOSTS,
    "SECRET_KEY": ds.SECRET_KEY,
    "SECRET_KEY_FALLBACKS": list(ds.SECRET_KEY_FALLBACKS),
    "DB_ENGINE": ds.DATABASES["default"]["ENGINE"],
    "SECURE_PROXY_SSL_HEADER": list(ds.SECURE_PROXY_SSL_HEADER),
    "SECURE_SSL_REDIRECT": ds.SECURE_SSL_REDIRECT,
    "SESSION_COOKIE_SECURE": ds.SESSION_COOKIE_SECURE,
    "SESSION_COOKIE_HTTPONLY": ds.SESSION_COOKIE_HTTPONLY,
    "SESSION_COOKIE_SAMESITE": ds.SESSION_COOKIE_SAMESITE,
    "CSRF_COOKIE_SECURE": ds.CSRF_COOKIE_SECURE,
    "CSRF_COOKIE_SAMESITE": ds.CSRF_COOKIE_SAMESITE,
    "SECURE_HSTS_SECONDS": ds.SECURE_HSTS_SECONDS,
    "SECURE_HSTS_INCLUDE_SUBDOMAINS": ds.SECURE_HSTS_INCLUDE_SUBDOMAINS,
    "SECURE_HSTS_PRELOAD": ds.SECURE_HSTS_PRELOAD,
    "SECURE_CONTENT_TYPE_NOSNIFF": ds.SECURE_CONTENT_TYPE_NOSNIFF,
    "X_FRAME_OPTIONS": ds.X_FRAME_OPTIONS,
    "STATIC_ROOT": str(ds.STATIC_ROOT),
    "FALLBACK_USADO": ds.SECRET_KEY == s._SECRET_KEY_FALLBACK,
}))
"""


def _saida_json(proc: subprocess.CompletedProcess) -> dict:
    match = re.search(r"^P0-02B_JSON=(.*)$", proc.stdout, re.MULTILINE)
    assert match is not None, (
        f"processo filho não emitiu o JSON de saída.\n"
        f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
    )
    return json.loads(match.group(1))


# ---------------------------------------------------------------------------
# 1. Import de `config.settings` + `django.setup()` em produção
# ---------------------------------------------------------------------------


def test_import_de_config_settings_sobe_em_producao():
    """Critério de saída do gate GP-1b: `import config.settings` e
    `django.setup()` bem-sucedidos com DEBUG=False, SECRET_KEY forte e
    ALLOWED_HOSTS preenchido."""
    env = _env_producao()
    proc = _rodar(env, "-c", _SNIPPET_PRODUCAO)

    assert proc.returncode == 0, (
        f"import de config.settings FALHOU em produção "
        f"(exit={proc.returncode}).\nstdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
    )

    dados = _saida_json(proc)

    # As três condições do gate, conferidas no settings EFETIVO (não no
    # ambiente que pedimos) — é aqui que um default silencioso falharia.
    assert dados["DEBUG"] is False
    assert dados["ALLOWED_HOSTS"] == ["portal-noticias.com"]
    assert len(dados["SECRET_KEY"]) >= 50
    assert dados["FALLBACK_USADO"] is False


def test_hardening_de_producao_ativa_com_debug_false():
    """O bloco `if not DEBUG:` (`config/settings.py:81-98`) precisa estar
    realmente em vigor em produção. Se alguém mover essas definições para
    dentro de `if DEBUG:` (ou removê-las), este teste falha — é o ramo que
    hoje tem ZERO cobertura de linha na suíte, porque o CI roda com
    DJANGO_DEBUG=true."""
    proc = _rodar(_env_producao(), "-c", _SNIPPET_PRODUCAO)
    assert proc.returncode == 0, f"stderr:\n{proc.stderr}"
    dados = _saida_json(proc)

    # Atrás do proxy reverso (Caddy) que termina TLS e injeta
    # X-Forwarded-Proto; sem isso SECURE_SSL_REDIRECT causaria loop.
    assert dados["SECURE_PROXY_SSL_HEADER"] == ["HTTP_X_FORWARDED_PROTO", "https"]
    assert dados["SECURE_SSL_REDIRECT"] is True
    # Cookies de sessão/CSRF só sobre HTTPS, e sessão legível só pelo
    # servidor.
    assert dados["SESSION_COOKIE_SECURE"] is True
    assert dados["SESSION_COOKIE_HTTPONLY"] is True
    assert dados["CSRF_COOKIE_SECURE"] is True
    # SameSite=Lax nos dois: o frontend roda em outra origem, então
    # "Strict" quebraria o fluxo e "None" exigiria Secure.
    assert dados["SESSION_COOKIE_SAMESITE"] == "Lax"
    assert dados["CSRF_COOKIE_SAMESITE"] == "Lax"
    # HSTS positivo (o valor exato é parametrizável por env, o que não
    # pode é ser zero/desligado em produção).
    assert dados["SECURE_HSTS_SECONDS"] > 0
    assert dados["SECURE_HSTS_INCLUDE_SUBDOMAINS"] is True
    # DEFAULT para não entrar na preload list: decisão deliberada
    # documentada em `config/settings.py:91-96` (HSTS de 1 ano com preload
    # exige confiança total no domínio estar sempre em HTTPS). Fica
    # coberto por `test_check_deploy_nao_emite_warnings_inesperados`.
    assert dados["SECURE_HSTS_PRELOAD"] is False
    assert dados["SECURE_CONTENT_TYPE_NOSNIFF"] is True
    assert dados["X_FRAME_OPTIONS"] == "DENY"
    # `collectstatic` (rodado a cada deploy) falha sem STATIC_ROOT —
    # descobrir isso só no deploy seria tarde.
    assert dados["STATIC_ROOT"]
    # Stack obrigatória do ARCHITECTURE.md seção 1.
    assert dados["DB_ENGINE"] == "django.db.backends.postgresql"
    # Nenhuma chave de fallback em rotação: nenhum segundo segredo
    # aceito para assinar sessão/token.
    assert dados["SECRET_KEY_FALLBACKS"] == []


def test_config_wsgi_importa_em_producao():
    """O caminho de boot real do release é o Gunicorn importando
    `config.wsgi` (ver `backend/gunicorn.conf.py` e o job de deploy em
    `.github/workflows/deploy.yml`). Um import de `config.settings` que
    passa não prova que o entrypoint de produção sobe."""
    proc = _rodar(
        _env_producao(),
        "-c",
        "import config.wsgi; print('P0-02B_JSON=' + config.wsgi.__name__)",
    )
    assert proc.returncode == 0, f"stderr:\n{proc.stderr}"
    assert "P0-02B_JSON=config.wsgi" in proc.stdout


# ---------------------------------------------------------------------------
# 2. `manage.py check` em produção
# ---------------------------------------------------------------------------


def test_manage_py_check_passa_em_producao():
    """O gate GP-1b propriamente dito: `manage.py check` sem erro em
    configuração de produção."""
    proc = _rodar(_env_producao(), "manage.py", "check")

    assert proc.returncode == 0, (
        f"`manage.py check` FALHOU em produção (exit={proc.returncode}).\n"
        f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
    )
    assert "System check identified no issues" in proc.stdout


def test_check_deploy_nao_emite_warnings_inesperados():
    """`check --deploy` no caminho de produção não pode emitir ERROR nem
    NENHUM warning de segurança além do W021 (HSTS preload), que é
    default deliberado e documentado (`config/settings.py:91-96`).

    Fixar a lista de warnings é deliberado: se um dia alguém corrigir o
    W021, este teste falha e a whitelist é atualizada junto do comentário
    — o inverso (teste que aceita qualquer warning novo) não protegeria
    nada. Warnings não fazem `check` retornar != 0, então sem esta
    asserção a regressão passaria pelo CI verde."""
    proc = _rodar(_env_producao(), "manage.py", "check", "--deploy")

    # --deploy não falha por warning; falha só por ERROR.
    assert proc.returncode == 0, f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"

    # Os warnings vão para STDERR, não para stdout: é o comportamento
    # documentado do próprio Django (`BaseCommand.check`: "If there are
    # only light messages (like warnings), print them to stderr and don't
    # raise an exception"). Varrer só o stdout daria uma lista vazia e o
    # teste passaria sem verificar nada — por isso as duas streams.
    saida = proc.stdout + proc.stderr
    encontrados = sorted(set(re.findall(r"\((security\.W\d+)\)", saida)))
    assert encontrados == ["security.W021"], (
        f"warnings de segurança inesperados em produção: {encontrados}\n"
        f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
    )


# ---------------------------------------------------------------------------
# 3. As travas de ambiente de `config/settings.py` não são vácuas
#    (regressão: uma trava que parou de disparar é pior que nenhuma)
# ---------------------------------------------------------------------------


def test_trava_recusa_secret_key_de_fallback_com_debug_false():
    """`config/settings.py:59-66` — com DEBUG=False e a SECRET_KEY ainda
    no valor de fallback de desenvolvimento, o import tem de recusar.
    Fixamos a variável no MESMO valor de fallback lido do módulo real
    (via env) em vez de simplesmente removê-la: assim o teste é
    independente de um `backend/.env` local (que `config/settings.py:29`
    carrega com `override=False` e que o CI não tem)."""
    fallback = "django-insecure-dev-only-key-nao-usar-em-producao"
    env = _env_producao(DJANGO_SECRET_KEY=fallback)

    proc = _rodar(env, "-c", "import config.settings")

    assert proc.returncode != 0, (
        "a trava de SECRET_KEY de fallback NÃO disparou com DEBUG=False — "
        "produção subiria com a chave de desenvolvimento."
    )
    assert "ImproperlyConfigured" in proc.stderr
    assert "DJANGO_SECRET_KEY" in proc.stderr


def test_trava_recusa_sqlite3_com_debug_false():
    """`config/settings.py:229-234` — SQLite é atalho de bootstrap local;
    com DEBUG=False (produção) precisa falhar alto, senão a garantia de
    persistência do ARCHITECTURE.md seria perdida em silêncio."""
    proc = _rodar(
        _env_producao(DJANGO_DB_ENGINE="sqlite3"), "-c", "import config.settings"
    )

    assert proc.returncode != 0, (
        "a trava de DJANGO_DB_ENGINE=sqlite3 NÃO disparou com DEBUG=False."
    )
    assert "ImproperlyConfigured" in proc.stderr
    assert "sqlite3" in proc.stderr


def test_trava_de_secret_key_e_condicional_a_debug():
    """Contraprova das duas travas: elas não podem existir para o
    ambiente de desenvolvimento. Com DJANGO_DEBUG=true, a SECRET_KEY de
    fallback e o SQLite são explicitamente permitidos (é assim que a
    suíte de testes e o `runserver` local funcionam)."""
    env = _env_producao(
        DJANGO_DEBUG="true",
        DJANGO_SECRET_KEY="django-insecure-dev-only-key-nao-usar-em-producao",
        DJANGO_DB_ENGINE="sqlite3",
    )
    proc = _rodar(env, "-c", "import config.settings; print('P0-02B_JSON=ok')")

    assert proc.returncode == 0, f"stderr:\n{proc.stderr}"
    assert "P0-02B_JSON=ok" in proc.stdout
