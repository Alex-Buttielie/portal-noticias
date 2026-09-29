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


@pytest.fixture(autouse=True)
def _limpa_transporte_do_app_celery():
    """
    Limpa os caches de transporte do app Celery entre testes.

    POR QUE ISTO É NECESSÁRIO E NÃO COSMÉTICO
    ------------------------------------------
    `Celery.backend`, `Celery.amqp`, `Celery.control`, `Celery.pool` e
    `Celery.producer_pool` são `cached_property`: resolvidos na PRIMEIRA
    leitura e presos para o resto do processo. Como o `pytest-django`
    reconfigura `DJANGO_SETTINGS_MODULE`/`override_settings` o tempo todo,
    um teste que publique uma task resolve `app.backend` com a
    configuração daquele instante — e o teste seguinte, que espera
    `cache+memory://`, herda o backend de Redis já construído e falha
    com `ConnectionRefusedError` para `localhost:6379` que não tem nada a
    ver com ele.

    Não é bug do código de produção (lá as settings são lidas uma vez, no
    boot, e o cache é justamente o que se quer). É uma armadilha de teste, e a
    saída honesta é limpar o cache em vez de deixar alguns testes passarem
    "por acaso" e outros quebrarem conforme a ordem.

    Os campos que precisam ser zerados são `_backend_cache` e
    `_local.backend`: em Celery 5.6, `Celery.backend` é uma `property` que
    consulta `self._backend_cache` e, se for `None`, cai em
    `getattr(self._local, "backend", None)` — e é o `_local` (thread-local) que
    guardou o backend Redis nas tentativas anteriores (ver
    `celery/app/base.py:1428-1453`). `amqp`, `control` e `pool` são
    `cached_property`, portanto vivem em `__dict__` e são removidos por lá.
    """
    from config.celery import app as celery_app

    def _limpar():
        celery_app._backend_cache = None
        celery_app._local.__dict__.pop("backend", None)
        for atributo in ("amqp", "control", "pool", "producer_pool", "_pool"):
            celery_app.__dict__.pop(atributo, None)

    _limpar()
    yield
    _limpar()


@pytest.fixture
def diretorio_estado(tmp_path, monkeypatch):
    """
    Isola o estado durável das filas (`config/filas_estado.py`) num tmp_path.

    Existe por dois motivos, ambos de disciplina de entrega:

    1. Nenhum teste pode gravar no diretório de estado real. Sem isto, basta
       um teste que chame a task de ingestão (ou o `saude_filas`) para
       aparecer um `estado-filas.json` fora do repositório e, pior, para um
       teste "ver" o heartbeat do teste anterior e passar por acidente.
    2. O caminho vem de `PORTAL_FILAS_ESTADO_DIR`, lido por
       `filas_estado.diretorio_estado()` a CADA chamada — por isso
       monkeypatch no ambiente basta, sem reload de módulo nem de settings.
    """
    destino = tmp_path / "estado-filas"
    monkeypatch.setenv("PORTAL_FILAS_ESTADO_DIR", str(destino))
    return destino


@pytest.fixture
def sem_estado(diretorio_estado):
    """`diretorio_estado` garantindo que NÃO existe arquivo de estado ainda."""
    from config import filas_estado

    caminho = filas_estado.caminho_estado()
    if caminho.exists():
        caminho.unlink()
    return caminho


# ---------------------------------------------------------------------------
# P1-08 — fábrica de usuário Premium REALMENTE pago.
# ---------------------------------------------------------------------------


class _GatewaySempreAprova:
    """Gateway de mentira que aprova a cobrança.

    Existe para que os testes de gating usem a MESMA porta de entrada do
    produto (`assinatura.services.assinar_plano`) em vez de escrever
    `papel="premium"` direto no usuário. Um `papel` escrito à mão não é um
    pagante: é exatamente o estado que o P1-08 passou a tratar como NÃO
    premium (`gating.services._assinatura_autoriza_premium`), porque nada
    nesse usuário pagou nada.
    """

    def __init__(self):
        self._n = 0

    def criar_cobranca(self, subscription, valor):
        self._n += 1
        from assinatura.providers.payment import ResultadoCobranca

        return ResultadoCobranca(
            referencia_gateway=f"conftest-aprovado-{subscription.pk}-{self._n}",
            status="aprovado",
        )

    def consultar_status(self, referencia_gateway):
        return "aprovado"

    def cancelar(self, referencia_gateway):
        return None


@pytest.fixture
def fabrica_usuario_premium():
    """
    FÁBRICA de usuários Premium com assinatura autêntica.

    Por que existe (achado de segurança do P1-08): a maioria dos testes
    "Premium funciona" de 20260902 criava o usuário com `papel="premium"` e
    nenhuma assinatura. Isso fixava como VERDADE a premissa errada de que o
    campo `papel` sozinho concede acesso — a mesma que permitsia a uma
    assinatura vencida continuar Premium. Aqui o Premium só existe depois de
    `assinar_plano` (porta pública, a mesma do botão "Assinar"), então o
    teste exercita o caminho real e continua valendo o que queria valar.

    Parâmetros:
      vencimento_dias: negativo = já venceu (data passada).
      status:          para exercitar os demais estados da máquina do BRD.
      rebaixar_papel:  deixa `User.papel` como `papel` param — usado para
                       reproduzir o estado INCOERENTE (banco diz Premium,
                       assinatura vencida) que existia antes da correção.

    Devolve o usuário, já relido do banco (`papel` final é o que o gating lê).
    """
    from decimal import Decimal

    from django.contrib.auth import get_user_model
    from django.utils import timezone

    from assinatura.models import Plan, Subscription
    from assinatura.services import assinar_plano

    User = get_user_model()
    contador = {"n": 0}

    def _fabrica(
        *,
        email=None,
        status=None,
        vencimento_dias=10,
        papel="free",
        rebaixar_papel=False,
    ):
        from datetime import timedelta

        contador["n"] += 1
        user = User.objects.create_user(
            email=email or f"premium-pago-{contador['n']}@example.com",
            password="senha123",
            papel=papel,
        )
        plan, _ = Plan.objects.get_or_create(
            nome="Premium Teste P1-08",
            defaults={"preco": Decimal("29.90"), "duracao_dias": 30, "ativo": True},
        )
        subscription = assinar_plano(user, plan, payment_gateway=_GatewaySempreAprova())

        if status is not None:
            Subscription.objects.filter(pk=subscription.pk).update(status=status)
        if vencimento_dias is not None:
            Subscription.objects.filter(pk=subscription.pk).update(
                vencimento=timezone.now() + timedelta(days=vencimento_dias)
            )
        if rebaixar_papel:
            # Reproduz o estado incoerente herdado do P1-08: o snapshot
            # `papel` continua "premium" (a task de vencimentos ainda não
            # rodou) enquanto a assinatura já venceu.
            User.objects.filter(pk=user.pk).update(papel="premium")
        else:
            from assinatura.services import _sincronizar_papel_usuario

            subscription.refresh_from_db()
            _sincronizar_papel_usuario(subscription)
        user.refresh_from_db()
        return user

    return _fabrica


