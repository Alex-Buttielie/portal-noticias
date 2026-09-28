"""Fixtures de `b2b/tests/`.

`canal_entregando` (P1-04)
=========================
O `pytest-django` injeta `locmem.EmailBackend` como `EMAIL_BACKEND`, e o
`locmem` está em `BACKENDS_SEM_ENTREGA_REAL` (`config/email_entrega.py`) — ele
é um buffer em memória, não uma entrega. Desde que o alerta B2B passou pelo
gate, um backend sem entrega real **não** é enviado: o job devolve
`total_alertas_enviados=0` e `total_falhas=1`, e o ratchet do critério não
anda.

Por que a fixture é explícita (não `autouse`)
=============================================
Antes desta mudança, os testes de alerta afirmavam `total_alertas_enviados == 1`
com o `locmem` do `pytest-django` — ou seja, **afirmavam a mentira que este
item fecha**: registravam uma entrega para um e-mail que foi só para um
dicionário em memória. Pedir `canal_entregando` é declarar "este teste quer o
caminho de entrega de verdade", e um teste que o esquece falha com
`total_alertas_enviados == 0`, que é a falha certa e legível.

O mesmo desenho de `identidade/tests/conftest.py` e dos testes de
`newsletter/`: o ambiente SEM canal é o que `b2b/tests/test_p1_04_entrega.py`
precisa observar, e uma fixture automática o esconderia.

`nenhum_teste_sai_para_a_rede` (autouse)
=======================================
Nenhum teste do pacote abre conexão de rede. Cobre os DOIS alvos: o da sessão
de egresso (`SessaoEgress.post`, que `config/email_resend.py` usa depois do
P0-10) e o `requests` cru — para que, se o código de produção voltar a chamar
`requests` direto, o teste quebre pelo motivo certo em vez de sair para
`api.resend.com`. Mesmo desenho de `identidade/tests/conftest.py`.
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
    preenchendo `django.core.mail.outbox` — os testes que leem o corpo do
    alerta entregue continuam funcionando sem mudar.
    """
    settings.EMAIL_BACKEND = BACKEND_QUE_ENTREGA
    EntregaSimuladaBackend.entregues.clear()
    yield settings
    EntregaSimuladaBackend.entregues.clear()
