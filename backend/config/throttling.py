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

MAJOR-1 (Onda 2): as 3 classes anônimas passam a resolver a identidade do
balde por `config.proxies.get_ident`, e não pelo `get_ident` do DRF. Com
`NUM_PROXIES` ausente, o do DRF devolve o `X-Forwarded-For` cru — que o
cliente escolhe. `DenunciaUserThrottle` NÃO é afetada: ela é `UserRateThrottle`
(exige `IsAuthenticated`) e o DRF já usa `request.user.pk` como chave, que o
cliente não pode forjar. Por isso ela fica como está, de propósito.
"""

from rest_framework.throttling import AnonRateThrottle, UserRateThrottle

from config.proxies import get_ident as _identidade_do_cliente


class _AnonThrottleIdentidadeDeclarada(AnonRateThrottle):
    """Base das classes de throttle anônimo deste arquivo.

    MAJOR-1 (Onda 2): o `get_ident` do DRF usa o `X-Forwarded-For` cru
    quando `REST_FRAMEWORK["NUM_PROXIES"]` não está definido — e esse
    cabeçalho é escolhido pelo cliente. Medido nesta base: 12 valores de XFF
    com o mesmo `REMOTE_ADDR` abriram 12 baldes e "zeraram" o limite de
    10/min do login. `NUM_PROXIES: 0` não serve (tudo vira `127.0.0.1` e um
    atacante causa 429 global); `NUM_PROXIES: 1` não serve (o Nginx repassa
    o cabeçalho verbatim, então o último elemento é do cliente).

    Aqui a identidade vem de `config.proxies.get_ident`, que só lê o
    cabeçalho quando o `REMOTE_ADDR` pertence ao conjunto declarado em
    `TRUSTED_PROXY_IPS`, toma o último elemento e exige que ele seja um IP
    válido — caindo em `REMOTE_ADDR` em qualquer outro caso. Todo caminho
    de falha mantém o comportamento correto por IP, então um cabeçalho
    malformado não vira balde novo nem derruba tráfego legítimo.
    """

    def get_ident(self, request) -> str:
        return _identidade_do_cliente(request)


class EscritaPublicaAnonThrottle(_AnonThrottleIdentidadeDeclarada):
    """
    Throttle conservador (folgado o bastante para uso legítimo, apertado o
    bastante para dificultar abuso automatizado) para endpoints públicos de
    escrita. Taxa configurável via `REST_FRAMEWORK.DEFAULT_THROTTLE_RATES`
    em `config/settings.py` (por sua vez configurável via variável de
    ambiente `THROTTLE_ESCRITA_PUBLICA_RATE`), sem exigir alteração de
    código para recalibrar.
    """

    scope = "escrita_publica"


class AuthSensivelAnonThrottle(_AnonThrottleIdentidadeDeclarada):
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


class EnderecosAnonThrottle(_AnonThrottleIdentidadeDeclarada):
    """
    FRENTE 5 — proxy de endereços (`enderecos/`): endpoints públicos de
    LEITURA com upstream externo (ViaCEP/IBGE). Sem throttle, um único
    cliente em loop de debounce mal implementado repassa rajadas ao
    upstream; com cache + este limite folgado (60/min), uso legítimo
    (digitação com debounce) nunca bate no teto.
    """

    scope = "enderecos"
