"""
Settings de TESTE para o worker Celery real (P1-03, WS-06).

POR QUE ESTE MÓDULO EXISTE
--------------------------
`config/tests/test_filas_worker_real.py` sobe um `celery -A config worker` de
verdade, num processo separado, com o broker de filesystem do kombu. Esse
transporte precisa de diretorios (`data_folder_in`/`data_folder_out`/
`control_folder`), e o kombu os resolve por `transport_options` — que o
Celery lê de `app.conf.broker_transport_options`.

O problema: `CELERY_BROKER_TRANSPORT_OPTIONS` vindo do AMBIENTE não vira
dict. Verificado no Celery 5.6 (`celery 5.6.0`): com
`CELERY_BROKER_TRANSPORT_OPTIONS='{"data_folder_in": "/tmp/a"}'`,
`app.conf.broker_transport_options` é `{}` — o Celery não faz `json.loads`
nessa chave. Passar os diretorios pela query string da URL não resolve
também: o Celery expande os parâmetros da query em `Connection(**kwargs)` e
o kombu recusa com
`TypeError: Connection._init_params() got an unexpected keyword argument
'data_folder_in'`.

Ou seja: NÃO HÁ caminho por variável de ambiente para apontar o transporte de
filesystem, e o default do kombu é `data_in`/`data_out` relativos ao CWD — o
worker escreveria dentro do diretório do código, que é justamente o que um
teste não pode fazer. Um módulo de settings é o único jeito de injetar isso
no processo filho, e é a razão de este arquivo existir (e de ele ser
exclusivamente de teste: `DJANGO_SETTINGS_MODULE` só é sobrescrito aqui).

O QUE ESTE MÓDULO NÃO MUDA
--------------------------
Nenhuma regra de negócio, nenhum limite de observabilidade, nenhum segredo.
Ele só troca o broker/resultado de execução e aponta o diretório de estado
para o tmp_path do teste. Em DEV/HOMOLOG/PROD o broker é Redis e nenhum
diretório de transporte é necessário — por isso nada aqui é etapa de
provisionamento de P0-07.
"""

import os
from pathlib import Path

os.environ.setdefault(
    "DJANGO_SECRET_KEY",
    "test-only-secret-key-worker-filas-0123456789abcdef",
)

from .settings import *  # noqa: F401,F403

# Raiz do transporte de filesystem, injetada pelo teste via ambiente.
_TRANSPORTE = os.environ.get("P103_BROKER_TRANSPORT_DIR", "")

if _TRANSPORTE:
    _raiz = Path(_TRANSPORTE)
    CELERY_BROKER_URL = "filesystem://"
    CELERY_BROKER_TRANSPORT_OPTIONS = {
        "data_folder_in": str(_raiz / "entrada"),
        "data_folder_out": str(_raiz / "saida"),
        "control_folder": str(_raiz / "controle"),
        "store_processed": False,
        "polling_interval": 0.1,
    }
    # O resultado nao e lido pelo pai (o teste le o ARQUIVO de estado), e o
    # backend de filesystem exigiria um diretorio de resultados a mais sem
    # acrescentar prova nenhuma.
    CELERY_RESULT_BACKEND = "cache+memory://"
