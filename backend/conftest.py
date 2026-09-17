"""
Isolamento de cache entre testes.

O throttle do DRF (`config/throttling.py`) guarda contadores no cache
default. Com `DJANGO_CACHE_BACKEND=locmem` (modo do `subir-localhost.bat`,
carregado via `backend/.env`), o `LocMemCache` é compartilhado por todo o
processo — contagens de um arquivo de teste vazavam para o seguinte e
geravam 429 espúrios em testes de login/recuperação (ex.: rodar
`identidade/tests/test_acceptance_criteria.py` + `test_sanity.py` juntos).

Limpar o cache antes/depois de cada teste elimina a poluição sem afetar os
testes dedicados de throttling (`config/tests/test_throttling.py`), que
usam cache isolado próprio e sequências dentro de um único teste.
"""

from __future__ import annotations

import pytest
from django.core.cache import cache


@pytest.fixture(autouse=True)
def _limpa_cache_entre_testes():
    try:
        cache.clear()
    except Exception:
        pass
    yield
    try:
        cache.clear()
    except Exception:
        pass
