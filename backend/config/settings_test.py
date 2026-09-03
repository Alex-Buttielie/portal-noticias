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

os.environ.setdefault(
    "DJANGO_SECRET_KEY",
    "test-only-secret-key-nao-usar-fora-da-suite-de-testes-0123456789",
)

from .settings import *  # noqa: F401,F403
