"""Backends de e-mail usados SÓ pelos testes de `contato/`.

P1-04: as classes foram para `config/tests/backends.py` — o lugar único, que
`identidade/` e `newsletter/` também usam, porque o gate de entrega
(`config/email_entrega.py`) é único e um provedor de teste que elege de três
versões diferentes seria três opportunities de divergir. Aqui ficam só os
nomes que a suíte de contato já importava, para que nenhum teste precise mudar.

Nenhum deles é usado em runtime, e nenhum está em `BACKENDS_SEM_ENTREGA_REAL`
(`config/email_entrega.py`) — o ponto é justamente simular um provedor que
ACEITA ENTREGAR, para que o caminho de 2xx da view seja exercitado de
verdade, e simular provedores que recusam, para provar que recusas viram 503.

O "console" de verdade continua fora daqui: é o backend real do projeto e é
usado nos testes como está (`EMAIL_BACKEND` default), justamente para provar que
o endpoint recusa um backend que apenas imprime.
"""

from __future__ import annotations

from config.tests.backends import (  # noqa: F401 — reexportado de propósito
    EntregaSimuladaBackend,
    ExplodindoBackend,
    RecusaBackend,
    caminho_de,
)

