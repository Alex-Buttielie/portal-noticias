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
toplevel (`if not DEBUG:` em `config/settings.py:209` e os `raise
ImproperlyConfigured` de `config/settings.py:123`, `:187` e `:358`).
Não existe forma de exercitar o outro lado
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
consegue expressar. A única exceção é a seção 7, que exercita dentro
deste processo as duas funções puras de classificação: elas são o cérebro
dos guards (decidem o motivo da recusa) e um erro nelas passaria batido
pelos testes de subprocesso, que só olham returncode e mensagem.

O que o item P0-02c acrescentou a este arquivo
As seções 4 e 5 fecham os contornos que a comparação por igualdade da
trava da SECRET_KEY deixava (`""`, só espaços, fallback com espaço nas
pontas, fallback em caixa alta, chave curta) e fecham a degradação
silenciosa de `DJANGO_ALLOWED_HOSTS`. A seção 6 é diferente, e vale ler
com atenção: o furo 3 (e-mail em backend que não entrega) **não** foi
fechado com `raise`, e este arquivo não afirma que tenha sido — a razão
está inteira em `test_email_backend_console_em_producao_e_sinalizado_no_boot`.
O que lá está fixado é a passagem de "falha silenciosa" para "falha logged
em todo boot de produção".
"""

from __future__ import annotations

import json
import os
import re
import secrets
import subprocess
import sys
from pathlib import Path

import pytest

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
    # Item P0-02c: o furo 3 (e-mail que não entrega) só é observável se o
    # valor em vigor for conhecido e conhecido por este módulo. Sem isto, um
    # `DJANGO_EMAIL_BACKEND` exportado na máquina (ou um `RESEND_API_KEY` no
    # ambiente) mudaria o ramo sob teste e a asserção passaria por acidente.
    "DJANGO_EMAIL_BACKEND",
    "RESEND_API_KEY",
    "DJANGO_DB_ENGINE",
    "DJANGO_SECURE_SSL_REDIRECT",
    "DJANGO_SESSION_COOKIE_SECURE",
    "DJANGO_CSRF_COOKIE_SECURE",
    "DJANGO_SECURE_HSTS_SECONDS",
    "DJANGO_CACHE_BACKEND",
    "DJANGO_LOG_JSON",
    "SENTRY_DSN",
)

# Espelha literalmente `config/settings.py:_SECRET_KEY_FALLBACK`. Fixada como
# literal, e não importada do módulo, de propósito: se um dia o valor de
# fallback mudar no settings, este teste tem de continuar descrevendo a chave
# publicada que o repositório carrega. O teste do P0-02b
# (`test_trava_recusa_secret_key_de_fallback_com_debug_false`) fixa o mesmo
# literal localmente, pela mesma razão — os dois são independentes de
# propósito.
_FALLBACK = "django-insecure-dev-only-key-nao-usar-em-producao"


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
    """O bloco `if not DEBUG:` (`config/settings.py:209-226`) precisa estar
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
    # documentada em `config/settings.py:219-224` (HSTS de 1 ano com preload
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
    default deliberado e documentado (`config/settings.py:219-224`).

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
    """`config/settings.py:120-132` — com DEBUG=False e a SECRET_KEY ainda
    no valor de fallback de desenvolvimento, o import tem de recusar.
    Fixamos a variável no MESMO valor de fallback lido do módulo real
    (via env) em vez de simplesmente removê-la: assim o teste é
    independente de um `backend/.env` local (que `config/settings.py:30`
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
    """`config/settings.py:357-362` — SQLite é atalho de bootstrap local;
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


# ---------------------------------------------------------------------------
# 4. Furo 1 (P0-02c): a trava da SECRET_KEY não pode ter contornos
#
#    O guard do P0-02b era `SECRET_KEY == _SECRET_KEY_FALLBACK`. Medido em
#    subprocesso antes desta correção, com DJANGO_DEBUG=false e todo o resto
#    do ambiente de produção real, CADA um destes contornos subia sem erro,
#    `manage.py check` não emitia warning nenhum, e o boot de produção
#    (`import config.wsgi`, o que o Gunicorn executa) terminava sem erro —
#    isto é, o PM2 reportava o processo online e o deploy seguia verde.
# ---------------------------------------------------------------------------


def _recusa_import(env_extra: dict[str, str], *trechos: str) -> None:
    """Exige que `import config.settings` seja RECUSADO no ambiente dado,
    com `ImproperlyConfigured` e com todos os `trechos` na mensagem de erro.
    Centralizado porque a asserção que dá peso a estes testes é a mesma em
    todos (`returncode != 0`), e é exatamente ela que a prova por mutação
    derruba quando um guard volta ao formato antigo."""
    env = _env_producao(**env_extra)
    proc = _rodar(env, "-c", "import config.settings")

    assert proc.returncode != 0, (
        f"a trava NÃO disparou com {env_extra!r} e DEBUG=False — o processo "
        f"subiria em produção nesta configuração.\n"
        f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
    )
    assert "ImproperlyConfigured" in proc.stderr, proc.stderr
    for trecho in trechos:
        assert trecho in proc.stderr, (
            f"a inicialização foi recusada, mas a mensagem não diz {trecho!r} — "
            f"ela tem de dizer o que fazer, não só que algo está errado."
            f"\nstderr:\n{proc.stderr}"
        )


def test_trava_recusa_secret_key_vazia_com_debug_false():
    """Furo 1, forma principal: `DJANGO_SECRET_KEY=""` — a variável existe,
    com valor vazio. O guard antigo só comparava por igualdade com o
    fallback, e string vazia não é igual a ele, logo a trava não disparava.

    O Django recusa esse caso, mas só DEPOIS e de forma preguiçosa, no
    primeiro acesso a `settings.SECRET_KEY` ("The SECRET_KEY setting must not
    be empty") — ou seja, no meio do tráfego, e não no boot."""
    _recusa_import({"DJANGO_SECRET_KEY": ""}, "DJANGO_SECRET_KEY", "vazia")


def test_trava_recusa_secret_key_so_com_espacos_com_debug_false():
    """Furo 1, contorno 2: `DJANGO_SECRET_KEY="   "` — 3 bytes de segredo
    efetivo. Sessão, cookie de sessão e token de redefinição passam a ser
    assinados com material trivial de adivinhar, e nem `check` nem
    `check --deploy` sinalizavam isso."""
    _recusa_import(
        {"DJANGO_SECRET_KEY": "   "}, "DJANGO_SECRET_KEY", "espaços em branco"
    )


def test_trava_recusa_fallback_com_espacos_nas_pontas_com_debug_false():
    """Furo 1, contorno 3: a chave de fallback com um espaço em cada ponta. A
    comparação por igualdade original falhava (a string não é igual ao
    fallback) e a chave publicada no repositório passava."""
    _recusa_import(
        {"DJANGO_SECRET_KEY": f" {_FALLBACK} "}, "DJANGO_SECRET_KEY", "fallback"
    )


def test_trava_recusa_fallback_em_caixa_alta_com_debug_false():
    """Furo 1, contorno 4: a mesma chave publicada, em caixa alta. Só mudou a
    aparência — quem a configurou continua com um segredo que está no
    repositório."""
    _recusa_import(
        {"DJANGO_SECRET_KEY": _FALLBACK.upper()}, "DJANGO_SECRET_KEY", "fallback"
    )


def test_trava_recusa_secret_key_curta_demais_com_debug_false():
    """Furo 1, contorno 5: chave com menos de 50 caracteres. O limiar não é
    um número escolhido aqui: é o do aviso `security.W009` do Django, que só
    é emitido por `check --deploy` — e o caminho de release roda `python
    manage.py check` SEM `--deploy` (`.github/workflows/deploy.yml:322`),
    então esse aviso nunca chegava a ninguém. Antes da correção,
    `DJANGO_SECRET_KEY=x` subia em produção com zero sinal."""
    _recusa_import({"DJANGO_SECRET_KEY": "x" * 49}, "DJANGO_SECRET_KEY", "49 caracteres")


def test_limiar_de_comprimento_da_secret_key_e_inclusivo():
    """Fixa a fronteira em 50 caracteres: 49 é recusado (teste acima), 50
    passa. Existe para que um endurecimento futuro não mova o limiar em
    silêncio — o custo de um limiar errado apareceria no deploy, não aqui."""
    proc = _rodar(
        _env_producao(DJANGO_SECRET_KEY="z" * 50), "-c", "import config.settings"
    )
    assert proc.returncode == 0, f"stderr:\n{proc.stderr}"


def test_boot_de_producao_do_wsgi_e_recusado_com_secret_key_vazia():
    """`import config.settings` não é o caminho de boot da produção: o
    Gunicorn importa `config.wsgi` (ver `backend/gunicorn.conf.py` e o job
    de deploy). Este teste fixa a trava no caminho real — foi por ele que o
    furo 1 passou despercebido: o boot terminava sem erro, `manage.py check`
    passava, e só o tráfego revelava o problema."""
    env = _env_producao(DJANGO_SECRET_KEY="")
    proc = _rodar(env, "-c", "import config.wsgi")

    assert proc.returncode != 0, (
        "o boot de produção (config.wsgi) NÃO foi recusado com SECRET_KEY "
        f"vazia e DEBUG=False.\nstderr:\n{proc.stderr}"
    )
    assert "ImproperlyConfigured" in proc.stderr
    assert "DJANGO_SECRET_KEY" in proc.stderr


def test_travas_de_secret_key_permanecem_livres_em_desenvolvimento():
    """Contraprova: nenhuma das formas degeneradas é recusada com
    DJANGO_DEBUG=true. `runserver` local, `subir-localhost.sh` e a suíte de
    testes (que define a chave por `setdefault` em
    `config/settings_test.py`) continuam funcionando — o guard é sobre
    produção, não sobre desenvolvimento."""
    for degenerada, rotulo in (
        ("", "vazia"),
        ("   ", "só espaços"),
        ("x", "curta demais"),
        (_FALLBACK, "fallback"),
    ):
        env = _env_producao(DJANGO_DEBUG="true", DJANGO_SECRET_KEY=degenerada)
        proc = _rodar(env, "-c", "import config.settings; print('P0-02C_JSON=ok')")
        assert proc.returncode == 0, (
            f"SECRET_KEY {rotulo} foi recusada com DJANGO_DEBUG=true — a trava "
            f"de produção não pode existir para desenvolvimento.\n{proc.stderr}"
        )
        assert "P0-02C_JSON=ok" in proc.stdout


# ---------------------------------------------------------------------------
# 5. Furo 2 (P0-02c): DJANGO_ALLOWED_HOSTS não pode degradar calado
#
#    Sem DJANGO_ALLOWED_HOSTS, com DEBUG=False, o default de código é a dupla
#    de loopback. Medido antes da correção: `ALLOWED_HOSTS` ficava
#    `['localhost', '127.0.0.1']`, o processo subia sem warning algum, e todo
#    hostname real recebia DisallowedHost (HTTP 400). O default nunca acertava
#    o domínio, porque o Nginx de produção encaminha o Host original
#    (`proxy_set_header Host $host`, `infra/nginx/portal-prod.conf`) e o Caddy
#    preserva o Host no `reverse_proxy web:8000` (`Caddyfile`).
# ---------------------------------------------------------------------------


def _env_local_define_allowed_hosts() -> bool:
    """Diz se existe um `backend/.env` local que DEFINA
    DJANGO_ALLOWED_HOSTS. `config/settings.py:30` carrega esse arquivo com
    `override=False`, ou seja, escreve em `os.environ` qualquer variável que
    ainda não esteja exportada no ambiente do processo. Como o teste
    "variável ausente" precisa justamente de uma variável que não esteja no
    ambiente, um `.env` local viraria o resultado do teste por baixo dos panos.

    Só interessa a definição da variável: o arquivo existir não atrapalha,
    porque `override=False` respeita o que o teste já fixou no ambiente filho."""
    arquivo = BACKEND_DIR / ".env"
    if not arquivo.is_file():
        return False
    for linha in arquivo.read_text(encoding="utf-8").splitlines():
        limpa = linha.strip()
        if limpa.startswith("DJANGO_ALLOWED_HOSTS") and not limpa.startswith("#"):
            return True
    return False


def test_trava_recusa_allowed_hosts_ausente_com_debug_false():
    """Furo 2: a variável simplesmente não existe no ambiente.

    Pula (em vez de dar um verde silencioso) quando um `backend/.env` local
    define DJANGO_ALLOWED_HOSTS, porque aí o `load_dotenv` de
    `config/settings.py:30` reintroduziria o valor e o teste não estaria
    medindo o que diz medir — o motivo fica visível no relatório do pytest.
    O CI e a revisão de release não têm esse arquivo (ver `CI-CD.md`:
    `backend/.env` é gerado na VPS), e os demais casos desta seção cobrem os
    mesmos dois ramos do guard de forma hermética, fixando a variável
    explicitamente no ambiente filho — que o `load_dotenv` não pode
    sobrescrever, porque a variável já existe."""
    if _env_local_define_allowed_hosts():
        pytest.skip(
            "existe um backend/.env local que define DJANGO_ALLOWED_HOSTS; "
            "ele é carregado com override=False e tornaria este caso "
            "inconclusivo (ver _env_local_define_allowed_hosts)"
        )

    env = _env_producao()
    env.pop("DJANGO_ALLOWED_HOSTS")
    proc = _rodar(env, "-c", "import config.settings")

    assert proc.returncode != 0, (
        "a trava de DJANGO_ALLOWED_HOSTS NÃO disparou com a variável ausente "
        "e DEBUG=False — produção subiria com o default de loopback e "
        f"responderia DisallowedHost (400) a todo hostname real.\n{proc.stderr}"
    )
    assert "ImproperlyConfigured" in proc.stderr
    assert "DJANGO_ALLOWED_HOSTS" in proc.stderr


def test_trava_recusa_allowed_hosts_vazia_com_debug_false():
    """`DJANGO_ALLOWED_HOSTS=` (presente, vazio) produz `ALLOWED_HOSTS == []`,
    que é pior que o default: recusa TODOS os hostnames, inclusive o de
    loopback. Antes da correção subia sem warning."""
    _recusa_import({"DJANGO_ALLOWED_HOSTS": ""}, "DJANGO_ALLOWED_HOSTS", "nenhum host")


def test_trava_recusa_allowed_hosts_so_com_separadores_com_debug_false():
    """`DJANGO_ALLOWED_HOSTS=", ,  ,"` — só vírgulas e espaços, que o filtro
    de `settings.py` descarta um a um. Mesmo `[]` e mesma ausência de sinal
    antes da correção."""
    _recusa_import({"DJANGO_ALLOWED_HOSTS": ", ,  ,"}, "DJANGO_ALLOWED_HOSTS", "nenhum host")


def test_trava_recusa_allowed_hosts_so_com_loopback_com_debug_false():
    """Só `localhost,127.0.0.1` — exatamente o valor de
    `backend/.env.example` e o default de código. Em produção, o domínio real
    e o IP de acesso ficam em 400.

    Note que o smoke test do deploy já pegaria este caso
    (`https://$HOST/healthz`, `.github/workflows/deploy.yml:513`, que falha
    quando a resposta não é 200). O que a trava muda é QUANDO: antes do
    `migrate`/`collectstatic` e do restart do PM2, com o motivo escrito, em
    vez de depois de o processo quebrado já estar no ar."""
    _recusa_import(
        {"DJANGO_ALLOWED_HOSTS": "localhost,127.0.0.1"},
        "DJANGO_ALLOWED_HOSTS",
        "loopback",
    )


def test_allowed_hosts_com_host_real_e_aceito_em_producao():
    """Contraprova do lado verde: host real + loopback sobe e preserva a lista
    exata. Sem este teste, um "endurecimento" que simplesmente rejeitasse
    qualquer valor também passaria pelos casos negativos."""
    proc = _rodar(_env_producao(), "-c", _SNIPPET_PRODUCAO)
    assert proc.returncode == 0, f"stderr:\n{proc.stderr}"
    assert _saida_json(proc)["ALLOWED_HOSTS"] == ["portal-noticias.com"]


def test_trava_de_allowed_hosts_permanece_livre_em_desenvolvimento():
    """Contraprova: com DJANGO_DEBUG=true, lista vazia e só loopback são
    aceitos. É assim que `runserver` e `subir-localhost.sh` funcionam local,
    e é assim que a suíte roda (que não define DJANGO_ALLOWED_HOSTS)."""
    for valor, rotulo in (
        ("", "vazia"),
        ("localhost,127.0.0.1", "só loopback"),
    ):
        env = _env_producao(DJANGO_DEBUG="true", DJANGO_ALLOWED_HOSTS=valor)
        proc = _rodar(env, "-c", "import config.settings; print('P0-02C_JSON=ok')")
        assert proc.returncode == 0, (
            f"DJANGO_ALLOWED_HOSTS {rotulo} foi recusada com DJANGO_DEBUG=true "
            f"— a trava de produção não pode existir para desenvolvimento."
            f"\n{proc.stderr}"
        )
        assert "P0-02C_JSON=ok" in proc.stdout


# ---------------------------------------------------------------------------
# 6. Furo 3 (P0-02c): e-mail que não entrega não pode ser silencioso
#
#    ATENÇÃO AO LER: esta seção NÃO afirma que o furo 3 esteja fechado por um
#    `raise`. O que ela fixa é a parte que este item pôde entregar sem
#    mentir sobre o estado do projeto — a justificativa está, inteira, em
#    `test_email_backend_console_em_producao_e_sinalizado_no_boot`.
# ---------------------------------------------------------------------------

# Imprime o backend efetivo DEPOIS do import de `config.wsgi`, para o teste
# poder afirmar as duas coisas ao mesmo tempo: que o valor em vigor é o console
# e que o boot o sinalizou.
_SNIPPET_BOOT_E_EMAIL = """
import config.wsgi
from django.conf import settings as ds

print("P0-02C_JSON=" + repr(ds.EMAIL_BACKEND))
"""


def test_email_backend_console_em_producao_e_sinalizado_no_boot():
    """Furo 3: com DEBUG=False e DJANGO_EMAIL_BACKEND=console — que é o
    DEFAULT do código e o que o `backend/.env` do deploy realmente contém —
    a verificação de cadastro, a redefinição de senha e a newsletter não
    saem: elas são impressas no stdout do container, e o deploy segue
    reportando sucesso.

    Por que este teste NÃO exige falha na inicialização, ao contrário dos
    furos 1 e 2: nenhum workflow define DJANGO_EMAIL_BACKEND, o `printf` que
    cria `backend/.env` no primeiro deploy (`.github/workflows/deploy.yml:277`)
    não escreve a variável, e `PROD_DECISOES.md` (item 2, "LLM / e-mail /
    OAuth") registra a integração Resend como "código pronto, aguardando
    chave Resend do Alex" — uma decisão de produto em aberto, não um bug. Um
    `raise ImproperlyConfigured` aqui derrubaria TODO deploy até essa
    credencial existir.

    O que este item entrega é o que dá sem mentir: a falha deixa de ser
    silenciosa. Um ERROR é logado em todo boot de produção, no mesmo stream
    onde o e-mail já vaza em claro. Quando a chave do Resend existir, a
    evolução correta é o `raise` — e este teste é o que vai passar a falhar
    no dia em que essa evolução for feita de fato.
    """
    env = _env_producao()  # DJANGO_EMAIL_BACKEND ausente => default console
    proc = _rodar(env, "-c", _SNIPPET_BOOT_E_EMAIL)

    # O boot continua de pé (é o comportamento real hoje, por decisão de
    # produto), então este teste também fixa que a sinalização NÃO foi
    # implementada como falha — para ninguém "endurecer" este item por engano
    # e derrubar o deploy no mesmo commit.
    assert proc.returncode == 0, f"stderr:\n{proc.stderr}"
    assert "P0-02C_JSON=" in proc.stdout
    assert "console.EmailBackend" in proc.stdout, (
        f"o default de DJANGO_EMAIL_BACKEND mudou; este teste fixava o "
        f"console.\nstdout:\n{proc.stdout}"
    )

    sinal = proc.stderr
    assert "não é entregue" in sinal, (
        "a degradação de e-mail em produção NÃO foi sinalizada no boot — o "
        f"furo 3 voltou a ser silencioso.\nstderr:\n{sinal}"
    )
    # A mensagem tem de dizer o que fazer, como as outras travas do arquivo.
    assert "config.email_resend.ResendEmailBackend" in sinal, sinal
    assert "RESEND_API_KEY" in sinal, sinal
    # Sai pelo log de boot (stderr) e não pelo stdout do backend de e-mail: é
    # um sinal sobre a configuração, não mais uma linha parecendo um e-mail
    # entregue. (O nível ERROR é propriedade do código; o que o subprocesso
    # consegue observar é o conteúdo e a stream.)
    assert "não é entregue" not in proc.stdout, proc.stdout


def test_email_backend_que_entrega_nao_e_sinalizado_em_producao():
    """Contraprova do lado verde: com o backend de Resend configurado, o boot
    é silencioso. Sem isto, um teste que só procurasse a string do aviso
    passaria mesmo com o sinal disparando para todo e-mail de produção."""
    env = _env_producao(
        DJANGO_EMAIL_BACKEND="config.email_resend.ResendEmailBackend",
        RESEND_API_KEY="re_0000000000000000000000000000000",
    )
    proc = _rodar(env, "-c", _SNIPPET_BOOT_E_EMAIL)

    assert proc.returncode == 0, f"stderr:\n{proc.stderr}"
    assert "ResendEmailBackend" in proc.stdout
    assert "não é entregue" not in proc.stderr, (
        f"um backend de e-mail que ENTREGA foi sinalizado como degradado."
        f"\n{proc.stderr}"
    )


def test_email_backend_console_nao_e_sinalizado_em_desenvolvimento():
    """Contraprova: em desenvolvimento o console é o comportamento correto e
    desejado (é assim que se inspeciona o token de verificação), logo o sinal
    não pode aparecer com DJANGO_DEBUG=true."""
    env = _env_producao(
        DJANGO_DEBUG="true",
        DJANGO_EMAIL_BACKEND="django.core.mail.backends.console.EmailBackend",
    )
    proc = _rodar(env, "-c", _SNIPPET_BOOT_E_EMAIL)

    assert proc.returncode == 0, f"stderr:\n{proc.stderr}"
    assert "não é entregue" not in proc.stderr, (
        f"desenvolvimento foi alertado sobre e-mail.\n{proc.stderr}"
    )


# ---------------------------------------------------------------------------
# 7. Os classificadores puros, exercitados dentro deste processo
#
#    Os testes das seções 4 a 6 rodam em subprocesso e, por isso, não movem um
#    único ponto de cobertura de `config/settings.py` (ver a observação sobre
#    cobertura no cabeçalho deste arquivo). Esta seção existe para exercitar a
#    lógica de classificação no próprio processo: é ela — e não o `raise` — que
#    decide o motivo da recusa, e um erro de classificação (aceitar
#    `" django-... "`, recusar uma chave legítima) passaria batido nos testes de
#    subprocesso, que só olham returncode e mensagem.
#
#    `config.settings` já está importado neste processo: `pytest.ini` define
#    DJANGO_SETTINGS_MODULE=config.settings_test, e esse módulo faz
#    `from .settings import *`. O import abaixo é só um cache hit, e as
#    funções exercitadas não dependem de nenhum valor do módulo — só do
#    argumento.
# ---------------------------------------------------------------------------


def test_classificador_de_secret_key():
    from config.settings import _motivo_secret_key_recusada_para_producao as julga

    assert julga("z" * 50) is None
    assert julga("z" * 200) is None
    assert julga("") == "está vazia"
    assert julga("   ") == "contém apenas espaços em branco"
    assert julga(" \t\n ") == "contém apenas espaços em branco"
    assert "fallback" in julga(_FALLBACK)
    assert "fallback" in julga(f"  {_FALLBACK}  ")
    assert "fallback" in julga(_FALLBACK.upper())
    assert "49 caracteres" in julga("z" * 49)
    # Um segredo forte que por acaso tenha espaços nas pontas continua
    # válido: o comprimento é medido sobre o valor sem o branco das bordas,
    # porque espaço na borda não muda a entropia.
    assert julga(" " + "z" * 60 + " ") is None


def test_classificador_de_allowed_hosts():
    from config.settings import _motivo_allowed_hosts_recusado_para_producao as julga

    assert julga([]) is not None
    assert julga(["localhost", "127.0.0.1"]) is not None
    assert julga(["localhost"]) is not None
    assert julga(["127.0.0.1"]) is not None
    assert julga(["portal-noticias.com"]) is None
    assert julga(["portal-noticias.com", "localhost", "127.0.0.1"]) is None


def test_backends_que_nao_entregam_de_e_mail():
    """A lista é a decisão de segurança do furo 3: um backend que também não
    entrega precisa entrar aqui para o sinal continuar valendo. Os três são os
    que o Django traz de fábrica e que não fazem I/O de rede."""
    from config.settings import _EMAIL_BACKENDS_QUE_NAO_ENTREGAM as nao_entregam

    assert nao_entregam == frozenset(
        {
            "django.core.mail.backends.console.EmailBackend",
            "django.core.mail.backends.locmem.EmailBackend",
            "django.core.mail.backends.dummy.EmailBackend",
        }
    )
