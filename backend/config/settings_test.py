"""
Settings usadas exclusivamente pela suíte de testes (pytest-django, ver
`pytest.ini`, `DJANGO_SETTINGS_MODULE`).

Define, ANTES de importar `config.settings` (que faz a validação logo na
primeira linha do módulo), uma `DJANGO_SECRET_KEY` de teste não-fraca via
variável de ambiente. Isso é necessário depois da correção do Finding 3
(code-review-contract.md, run-20260901-2135-cadastro-auth): `config/settings.py`
agora recusa subir (`ImproperlyConfigured`) se `DEBUG=False` (o novo default,
que passou a exigir opt-in explícito para `True`) e `SECRET_KEY` ainda for o
valor de fallback fraco de desenvolvimento — o que aconteceria na suíte de
testes se nada aqui definisse a variável antes do import.

Um módulo Python separado (em vez de tentar definir a variável de ambiente
num `conftest.py`) evita depender da ordem de execução dos hooks internos do
pytest/pytest-django em relação ao carregamento de `conftest.py` — a inicialização
do Django (`pytest_load_initial_conftests`) importa o settings module
diretamente, então o `os.environ.setdefault` abaixo precisa rodar como parte
dessa mesma cadeia de import, não de um hook concorrente.

`os.environ.setdefault` só entra em ação se `DJANGO_SECRET_KEY` não tiver
sido definida no ambiente (ex.: um CI real com segredo próprio) — nesse
caso, o valor do ambiente sempre tem prioridade sobre este.
"""

import os
import tempfile
from pathlib import Path

os.environ.setdefault(
    "DJANGO_SECRET_KEY",
    "test-only-secret-key-nao-usar-fora-da-suite-de-testes-0123456789",
)

from .settings import *  # noqa: F401,F403

# Run 20260923-1216-p1-feed-cache-indices (P1-1): a suíte usa `DummyCache`
# (nunca armazena) para que o cache curto das listagens/gating — com TTL de
# ~45s, maior que o intervalo entre testes no mesmo processo — não vaze
# respostas entre testes (o Django não limpa caches entre testes e o banco é
# isolado por teste, mas o cache locmem seria global). Os testes DEDICADOS de
# cache (`feed/tests/test_p1_feed_cache_indices.py`) religam um backend real
# via `override_settings(CACHES=...)` + `cache.clear()` no escopo deles.
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.dummy.DummyCache",
    }
}

# A suíte não sobe Redis. O transporte em memória permite testar o
# dispatch sem transformar a task em INSERT síncrono; os dois testes de
# integração que precisam observar a persistência ativam `always_eager`
# localmente com override_settings.
CELERY_BROKER_URL = "memory://"
CELERY_RESULT_BACKEND = "cache+memory://"
CELERY_TASK_ALWAYS_EAGER = False

# Observabilidade (run 20260925-1020-observabilidade). A suíte não sobe worker
# Celery, então `check_celery` reportaria "degraded" em TODAS as requisições e
# todo teste que olha `X-Operational-State` ficaria dependente de um broker que
# não existe. Desligado aqui; os testes que precisam da degradação reativam com
# `override_settings` + monkeypatch no check.
OBSERVABILITY_CHECK_CELERY = False
# Sem memoização: o probe de degradação é por processo e a suíte precisa poder
# reavaliar a cada requisição (isolamento, sem estado entre testes).
OBSERVABILITY_DEGRADED_PROBE_INTERVAL_SECONDS = 0.0

# Heartbeat do beat e estado de job: a suíte não sobe beat nem worker, então os
# dois ficariam `not_configured` — e, desde o achado MAJOR-3, "não configurado"
# em check SEM SINAL PRÓPRIO (`celery_beat`, `celery_jobs`) conta como
# DEGRADAÇÃO. Isso é o comportamento correto em produção e contaminaria todo
# teste que olha `X-Operational-State` (que não é sobre beat). Por isso os
# arquivos existem de antemão, com mtime recente: o check vê "ok" e os testes
# que precisam de `not_configured`/degradação usam `override_settings`.
_TESTE_TMP = Path(tempfile.gettempdir()) / "portal-observabilidade-suite"
_TESTE_TMP.mkdir(parents=True, exist_ok=True)
_BEAT_HEARTBEAT = _TESTE_TMP / "beat.heartbeat"
_BEAT_HEARTBEAT.touch(exist_ok=True)
_ESTADO_JOB = _TESTE_TMP / "job-state.json"
if not _ESTADO_JOB.exists():
    _ESTADO_JOB.write_text('{"versao": 1, "atualizado_em": 0, "tasks": {}}', encoding="utf-8")
OBSERVABILITY_BEAT_HEARTBEAT_FILE = str(_BEAT_HEARTBEAT)
OBSERVABILITY_JOB_STATE_FILE = str(_ESTADO_JOB)
