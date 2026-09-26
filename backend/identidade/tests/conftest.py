"""Fixtures de `identidade/tests/`.

`canal_entregando` (P1-04)
==========================
O `pytest-django` injeta `locmem.EmailBackend` como `EMAIL_BACKEND`, e o
`locmem` está em `BACKENDS_SEM_ENTREGA_REAL` (`config/email_entrega.py`) — ele
é um buffer em memória, não uma entrega. Desde o P1-04, cadastro e redefinição
de senha recusam um backend sem entrega real, então **qualquer teste que
exercita o caminho de sucesso precisa de um backend que entrega**.

A fixture é explícita (não `autouse`) de propósito: os testes do próprio
P1-04 precisam do ambiente SEM canal para provar a recusa, e uma fixture
automática esconderia exatamente o caso que eles precisam observar. Pedir
`canal_entregando` é declarar "este teste quer o caminho de entrega real" — e
um teste que o esquece falha com 503, que é a falha certa e legível.

`nenhum_teste_sai_para_a_rede` (autouse)
========================================
Nenhum teste do pacote abre conexão de rede. Cobre os DOIS alvos: o da sessão
de egresso (`SessaoEgress.post`, que `config/email_resend.py` usa depois do
P0-10) e o `requests` cru — para que, se o código de produção voltar a chamar
`requests` direto, o teste quebre pelo motivo certo em vez de sair para
`api.resend.com`. Mesmo desenho de `contato/tests/test_entrega.py`.
"""

from __future__ import annotations

import pytest

from config.tests.backends import EntregaSimuladaBackend, caminho_de

#: Backend que entrega de verdade (ver `config/tests/backends.py`).
BACKEND_QUE_ENTREGA = caminho_de(EntregaSimuladaBackend)


def _rede_proibida(*args, **kwargs):
    raise AssertionError(
        "este teste tentou sair para a rede real; o dublê de e-mail tem que "
        "estar no backend simulado, não no `requests`"
    )


@pytest.fixture(autouse=True)
def nenhum_teste_sai_para_a_rede(monkeypatch):
    monkeypatch.setattr("requests.post", _rede_proibida)
    monkeypatch.setattr("requests.get", _rede_proibida)
    monkeypatch.setattr("urllib.request.urlopen", _rede_proibida)


@pytest.fixture
def canal_entregando(settings):
    """Configura um canal que o projeto considera de entrega real.

    `EntregaSimuladaBackend` herda de `locmem.EmailBackend`, então continua
    preenchendo `django.core.mail.outbox` — os testes que leem o token de
    verificação do e-mail entregue continuam funcionando sem mudar.
    """
    settings.EMAIL_BACKEND = BACKEND_QUE_ENTREGA
    EntregaSimuladaBackend.entregues.clear()
    yield settings
    EntregaSimuladaBackend.entregues.clear()


#: `LocMemCache` isolado: o `settings_test.py` usa `DummyCache` (que nunca
#: armazena nada), então sem esta troca o throttle NUNCA bloqueia e um teste
#: de rate limit passa sem testar nada — falso positivo silencioso. Mesmo
#: desenho de `config/tests/test_throttling.py` e `contato/tests/test_throttle.py`.
_LOCMEM_CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "identidade-throttle-locmem",
    }
}


@pytest.fixture
def throttle_ativo(settings):
    """Habilita de fato o rate limit por IP dentro do teste.

    Necessário para `POST /api/auth/cadastro/`, `/recuperar-senha/`,
    `/redefinir-senha/` e `/verificar-email/`: os três escopos
    (`escrita_publica`, `auth_sensivel`) só contam em cache funcional, e o
    cache da suíte é `DummyCache`.
    """
    from django.core.cache import cache

    settings.CACHES = _LOCMEM_CACHES
    cache.clear()
    yield settings
    cache.clear()

