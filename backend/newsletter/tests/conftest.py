"""
Fixtures do pacote de testes da `newsletter/`.

O `canal_de_entrega` É AUTOUSE DE PROPÓSITO, e é a decisão de teste mais
consequente do double opt-in. Ela está aqui, e não dentro de cada arquivo,
porque uma decisão que precisa ser lembrada em oito arquivos não é uma
decisão: é uma armadilha esperando o oitavo arquivo.

POR QUE O BACKEND PRECISA SER MUDADO PARA OS TESTES DESTA SUÍTE
==============================================================
A suíte roda com `locmem`: `django.test.utils.setup_test_environment()`
(`django/test/utils.py:146-147`) sobrescreve `settings.EMAIL_BACKEND` com
`locmem` no início de toda sessão. E `locmem` está em
`BACKENDS_SEM_ENTREGA_REAL` (`config/email_entrega.py:82-90`) — ele é um buffer
em memória, não um provedor.

Isso já era verdade antes do double opt-in, e o P1-04 já tinha lidado com isso
do lado do ENVIO: cada teste de envio declara
`override_settings(EMAIL_BACKEND=CAMINHO_ENTREGA)` porque, sem isso, contaria
"entregas" que foram só para um dicionário.

O double opt-in acrescenta o segundo ponto de escrita — a INSCRIÇÃO, que agora
também precisa de canal para existir. Sem esta fixture, `services.inscrever`
levantaria `CanalDeConfirmacaoIndisponivel` em praticamente todo teste do
pacote, e cada um falharia por um motivo que não é o que diz medir: um teste
de descadastro não deveria reprovar porque o e-mail do portal não está
configurado.

O QUE ISTO NÃO FAZ, E É O QUE IMPORTA
=====================================
**Não contorna o portão para ninguém.** O fixture é autouse, então ela se
aplica a todos os testes do pacote — inclusive aos que MEDEM o portão. E eles
não são afetados, porque definem `settings.EMAIL_BACKEND` explicitamente no
corpo do teste, e a atribuição direta prevalece sobre a do fixture. O resultado
é que o portão é medido de verdade, num ambiente cujo default é "tem canal" —
que é o cenário em que o portão é interessante, e o oposto de medir um portão
num ambiente quebrado.

O que seria errado: pôr a fixture como NÃO-autouse e fazer cada teste lembrar
de usá-la. Aí um teste novo que não soubesse dela falha com
`CanalDeConfirmacaoIndisponivel`, alguém "conserta" trocando por
`pytest.raises(...)`, e o teste passa a afirmar o contrário do que diz — que a
inscrição é recusada, quando o que ele queria era uma inscrição. Erro
introduzido por conveniência de teste é erro de produção esperando.
"""

from __future__ import annotations

import pytest

from config.tests.backends import EntregaSimuladaBackend, caminho_de

#: Caminho pontilhado do dublê que "entrega de verdade" — o mesmo backend que
#: `newsletter/tests/doubles.py` e `config/tests/backends.py` usam. Um caminho
#: pontilhado (e não a classe) é o que o `verificar_canal_email()` resolve; se o
#: nome da classe mudasse, o fixture deixaria de importar e o teste falharia
#: aqui em vez de passar por um motivo errado.
CANAL_QUE_ENTREGA = caminho_de(EntregaSimuladaBackend)


@pytest.fixture(autouse=True)
def canal_de_entrega(settings):
    """Aponta o `EMAIL_BACKEND` para um dublê que entrega. Ver o docstring."""
    settings.EMAIL_BACKEND = CANAL_QUE_ENTREGA
    yield settings