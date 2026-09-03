"""
Throttling compartilhado (implementation-contract.md run
20260903-1134-seo-lgpd-design-system, escopo C — rate limiting).

Antes desta run, `backend/config/settings.py` não tinha NENHUM throttling
configurado (`REST_FRAMEWORK` só definia autenticação/permissão) — confirmado
por leitura direta do arquivo antes de assumir que era greenfield.

Decisão de escopo: em vez de ligar `DEFAULT_THROTTLE_CLASSES` globalmente
(o que também limitaria endpoints de LEITURA pública como `feed/`, que não
fazem parte do escopo desta run e não devem ser degradados), esta classe é
aplicada explicitamente só nas views de escrita pública listadas no
implementation-contract.md: cadastro (`identidade`), criação de
publicação (`comunidade`) e lista de espera (`landing`).

`AnonRateThrottle` só limita requisições de clientes NÃO autenticados
(`request.user.is_authenticated is False`) — usuários autenticados não são
afetados por esta classe.
"""

from rest_framework.throttling import AnonRateThrottle


class EscritaPublicaAnonThrottle(AnonRateThrottle):
    """
    Throttle conservador (folgado o bastante para uso legítimo, apertado o
    bastante para dificultar abuso automatizado) para endpoints públicos de
    escrita. Taxa configurável via `REST_FRAMEWORK.DEFAULT_THROTTLE_RATES`
    em `config/settings.py` (por sua vez configurável via variável de
    ambiente `THROTTLE_ESCRITA_PUBLICA_RATE`), sem exigir alteração de
    código para recalibrar.
    """

    scope = "escrita_publica"
