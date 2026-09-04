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

from rest_framework.throttling import AnonRateThrottle, UserRateThrottle


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


class AuthSensivelAnonThrottle(AnonRateThrottle):
    """
    Achado de revisão de segurança (major): login e os demais endpoints de
    autenticação (recuperação/redefinição de senha, verificação de e-mail,
    login social) não tinham NENHUM rate limit — nada impedia um atacante de
    testar milhares de combinações de e-mail/senha por minuto (brute force /
    credential stuffing). `AnonRateThrottle` só limita quem ainda não está
    autenticado, exatamente o caso de um atacante tentando entrar. Taxa mais
    apertada que `escrita_publica` de propósito (esses endpoints não têm
    volume legítimo alto por IP), configurável via `THROTTLE_AUTH_SENSIVEL_RATE`.
    """

    scope = "auth_sensivel"


class DenunciaUserThrottle(UserRateThrottle):
    """
    Achado de revisão de segurança (minor): `DenunciarView` exige apenas
    `IsAuthenticated`, sem limite de taxa — uma única conta podia enviar um
    volume arbitrário de denúncias, inflando a fila de moderação (NFR de
    anti-spam do BRD §30). `UserRateThrottle` (não `AnonRateThrottle`, que não
    se aplica a endpoints autenticados) limita por usuário autenticado.
    """

    scope = "denuncia"
