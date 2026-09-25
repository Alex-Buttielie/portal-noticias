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

Identidade do cliente (achado MAJOR-1 da revisão do backend, run
20260925-1020-observabilidade): o `SimpleRateThrottle.get_ident` do DRF, sem
`NUM_PROXIES`, devolve o `X-Forwarded-For` CRU. Os nginx versionados não
definem esse header, então o valor chegava intacto: o balde era escolhido pelo
próprio cliente e 40 POSTs contra um teto de 30/min deram 40×`201`. Toda
throttle anônima deste arquivo passa a identificar o cliente por
`config.proxies.identificar_cliente` (fail-closed: o header só é lido quando o
par é loopback ou uma rede declarada em `OBSERVABILITY_TRUSTED_PROXY_NETWORKS`,
e só o último elemento da cadeia, que é o que o proxy anexou).
"""

from rest_framework.throttling import AnonRateThrottle, UserRateThrottle

from .proxies import identificar_cliente


class _IdentidadePorParReal:
    """Mixin de `get_ident` para as throttles anônimas.

    Deliberadamente NÃO aplicado a `UserRateThrottle`: lá o balde é o usuário
    autenticado (`request.user.pk`), não o endereço — trocar por IP daria a um
    único usuário o mesmo balde de todo mundo atrás do mesmo proxy.
    """

    def get_ident(self, request) -> str:
        return identificar_cliente(request)


class EscritaPublicaAnonThrottle(_IdentidadePorParReal, AnonRateThrottle):
    """
    Throttle conservador (folgado o bastante para uso legítimo, apertado o
    bastante para dificultar abuso automatizado) para endpoints públicos de
    escrita. Taxa configurável via `REST_FRAMEWORK.DEFAULT_THROTTLE_RATES`
    em `config/settings.py` (por sua vez configurável via variável de
    ambiente `THROTTLE_ESCRITA_PUBLICA_RATE`), sem exigir alteração de
    código para recalibrar.
    """

    scope = "escrita_publica"


class AuthSensivelAnonThrottle(_IdentidadePorParReal, AnonRateThrottle):
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


class EnderecosAnonThrottle(_IdentidadePorParReal, AnonRateThrottle):
    """
    FRENTE 5 — proxy de endereços (`enderecos/`): endpoints públicos de
    LEITURA com upstream externo (ViaCEP/IBGE). Sem throttle, um único
    cliente em loop de debounce mal implementado repassa rajadas ao
    upstream; com cache + este limite folgado (60/min), uso legítimo
    (digitação com debounce) nunca bate no teto.
    """

    scope = "enderecos"


class ConsentimentoAnonThrottle(_IdentidadePorParReal, AnonRateThrottle):
    """
    Run 20260925-1020-observabilidade (Bloco A2) — emissão do token de
    consentimento de analytics (`POST /api/metricas/consent/`).

    Escopo próprio (e não `escrita_publica`) porque o risco é diferente: o
    endpoint é público, não grava nada em banco e responde em microssegundos,
    então um chamador automatizado pode pedir milhares de tokens por minuto e
    transformar o emissor num coletor de dados com o carimbo do próprio site. A
    taxa (`30/min`, configurável por `THROTTLE_CONSENTIMENTO_RATE`) é folgada o
    bastante para a renovação normal — uma vez por sessão por TTL — nunca bater.

    É este teto que o achado MAJOR-1 furou: com o `X-Forwarded-For` cru como
    balde, o limite não existia para o cliente que gira o header. O teto é um
    controle de privacidade, então a correção (`_IdentidadePorParReal`) é
    obrigatória — não é ajuste de taxa.
    """

    scope = "consentimento"
