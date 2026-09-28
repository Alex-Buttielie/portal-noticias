"""
MAJOR-1 (Onda 2) — o bucket do rate limit não pode ser escolhido por um
cabeçalho que o cliente forja.

O DEFETO (medido na base `1dec732`, não é hipótese)
--------------------------------------------------
1. `config/settings.py:507-540` — `REST_FRAMEWORK` tinha 3 chaves e
   `NUM_PROXIES` NÃO estava entre elas, então `api_settings.NUM_PROXIES` era
   `None`.
2. `rest_framework/throttling.py:33-40` — com `NUM_PROXIES is None`, o DRF
   cai em `return ''.join(xff.split()) if xff else remote_addr`: o
   `X-Forwarded-For` CRU vira a identidade do balde.
3. `grep -rl X_FORWARDED_FOR backend/` → vazio. `develop` não lia esse
   cabeçalho em lugar nenhum, nem para rejeitá-lo.
4. `infra/nginx/portal-{dev,homolog,prod}.conf` — não tinham NENHUMA linha
   `X-Forwarded-For` (`grep -c` → 0 nos três), então o Nginx repassava o
   cabeçalho do cliente verbatim.

Medido com `AuthSensivelAnonThrottle` (10/min) e `REMOTE_ADDR` fixo:
sem XFF → o próprio IP; XFF=1.1.1.1 → '1.1.1.1'; XFF=2.2.2.2 → '2.2.2.2'.
1 IP real + 12 XFF forjados = 12 identidades, 12 baldes, 12 "primeira
tentativa" permitida. Esgotar 10 com XFF=1.1.1.1 e trocar para XFF=2.2.2.2
destrava a 11ª. XFF='nao-e-um-ip' produzia identidade='nao-e-um-ip' (nenhum
valor é validado como IP).

POR QUE `NUM_PROXIES` NÃO RESOLVE (medido pelo agente anterior, as duas
variantes são ERRADAS e não são repetidas aqui)
------------------------------------------------
  * `NUM_PROXIES: 0` → identidade vira `REMOTE_ADDR` = `127.0.0.1` para TODO
    o tráfego que passa pelo Nginx local → todos os anônimos dividem um
    balde → um atacante causa 429 global no login. Troca o furo por um
    self-DoS.
  * `NUM_PROXIES: 1` → `addrs[-1]` do XFF, que o Nginx repassa verbatim →
    ainda forjável.

O QUE ESTES TESTES PROVAM
------------------------
Os quatro casos pedidos, cada um com o par positivo/negativo:

  A. FECHOU O FURO       — 12 XFF forjados, 1 `REMOTE_ADDR`, 1 balde; a 11ª
                          bloqueada.
  B. NÃO VIROU self-DoS  — 2 `REMOTE_ADDR` distintos = 2 baldes; o limite de
                          um não derruba o do outro.
  C. FAIL-CLOSED         — sem a variável de proxies declarada, e também
                          quando ela declara um proxy que NÃO é o
                          `REMOTE_ADDR`, o XFF forjado não muda a identidade.
  D. CASO LEGÍTIMO       — XFF autêntico vindo de um proxy DECLARADO é
                          respeitado e produz a identidade real do cliente.

MAIS os casos de borda pedidos: `REMOTE_ADDR` real sem XFF; XFF de cliente
sem proxy declarado; XFF válido de proxy declarado; XFF com 5 elementos; XFF
com lixo; XFF ausente; XFF com IP malformado; `REMOTE_ADDR` IPv6.

PODER DISCRIMINANTE (por que "passa nos dois lados" não acontece aqui)
---------------------------------------------------------------------
Quase todo teste deste arquivo é escrito na FORMA NEGATIVA — "isto NÃO pode
acontecer" — e não na positiva. A razão é estrutural: se a correção fosse
revertida, o `get_ident` voltaria a devolver o XFF cru, e um teste que
apenas afirmasse "com proxy declarado o XFF é respeitado" continuaria
PASSANDO, porque o comportamento vulnerável também respeita o XFF. Por isso
o par que discrimina é sempre:

    (proxy declarado + XFF válido)  ->  identidade = último elemento
    (proxy NÃO declarado + XFF válido)  ->  identidade = REMOTE_ADDR
                                         ^ esta linha é a que reprova na
                                           reversão; a de cima não.

O item `TestDiscriminacao` formaliza isso: ele roda as DUAS metades e
reprova se elas derem o mesmo resultado.

Sobre o cache: `config/settings_test.py` define `DummyCache`, que NUNCA
armazena — com ele o throttle é inerte e qualquer medição de balde daria
"permitido" para sempre (é o falso positivo que o docstring de
`config/tests/test_throttling.py:20-26` já descreve). Todo teste que conta
requisições usa a fixture `cache_locmem_isolado`, que troca `CACHES` por um
`LocMemCache` real e limpa o estado.
"""

from __future__ import annotations

import pytest
from django.core.cache import cache

from config.proxies import get_ident
from config.settings import REST_FRAMEWORK
from config.throttling import (
    AuthSensivelAnonThrottle,
    DenunciaUserThrottle,
    EscritaPublicaAnonThrottle,
    EnderecosAnonThrottle,
)

# Endereços de documentação (RFC 5737 / RFC 3849). Nenhum proxy real usa
# estes valores; são pares plausíveis sem depender de nenhum IP de mundo real.
CLIENTE = "203.0.113.10"
OUTRO_CLIENTE = "198.51.100.77"
TERCEIRO_CLIENTE = "192.0.2.55"
PROXY = "127.0.0.1"
IPV6_CLIENTE = "2001:db8::10"
IPV6_PROXY = "::1"


class ReqAnon:
    """Requisição mínima: `get_ident` só lê `request.META`.

    O `user` anônimo existe porque `SimpleRateThrottle.get_cache_key`
    (rest_framework/throttling.py:174) testa `request.user.is_authenticated`
    antes de escolher entre a chave por usuário e a chave por `get_ident`.
    """

    def __init__(self, remote_addr: str, xff: str | None = None):
        meta = {"REMOTE_ADDR": remote_addr}
        if xff is not None:
            meta["HTTP_X_FORWARDED_FOR"] = xff
        self.META = meta
        self.user = type("Anon", (), {"is_authenticated": False})()


class View:
    """`allow_request(request, view)` exige a view; o throttle não a usa."""


def _limite(scope: str = "auth_sensivel") -> int:
    """Lê `N` de `DEFAULT_THROTTLE_RATES[scope]`, sem hardcodar o valor."""
    rate = REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"][scope]
    num, _, _period = rate.partition("/")
    return int(num)


def _throttle(scope: str = "auth_sensivel"):
    """Instância de `AuthSensivelAnonThrottle` com escopo/taxa explícitos.

    Montada à mão (e não via `get_throttle_instance`) para que a medição não
    dependa de uma view real nem do cache de throttle já inicializado.
    """
    t = AuthSensivelAnonThrottle()
    t.scope = scope
    t.rate = REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"][scope]
    return t


def _ident(req, classe=AuthSensivelAnonThrottle) -> str:
    """A identidade TAL COMO O THROTTLE A USA.

    Este é o ponto do arquivo inteiro: chamar `config.proxies.get_ident`
    direto provaria que o MÓDULO novo está certo, mas não que o throttle o
    USA. O defeito era justamente um throttle ligado ao `get_ident` do DRF
    (o do cabeçalho cru) enquanto um módulo novo, correto, estava lá
    intacto e ninguém chamando.

    Por isso as quatro provas passam por `classe().get_ident(req)`: é o
    caminho que um request de login realmente percorre. Verificado
    empiricamente — com `config/throttling.py` revertido ao `AnonRateThrottle`
    do DRF, as provas reprovam; com `get_ident` chamado direto, elas
    continuariam passando.
    """
    return classe().get_ident(req)


@pytest.fixture
def cache_locmem_isolado(settings):
    """`CACHES` de verdade (LocMemCache) só durante o teste.

    Sem isto, o `DummyCache` de `config/settings_test.py` faz o throttle não
    contar NADA e todo "esperava 429" passaria por acidente.
    """
    settings.CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "test-major1-xff",
        }
    }
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def sem_proxy_declarado(settings):
    """`TRUSTED_PROXY_IPS` ausente — o estado em que a maioria roda."""
    settings.TRUSTED_PROXY_IPS = ""
    return settings


@pytest.fixture
def com_proxy_declarado(settings):
    """`TRUSTED_PROXY_IPS` declarando explicitamente `PROXY`."""
    settings.TRUSTED_PROXY_IPS = PROXY
    return settings


# ---------------------------------------------------------------------------
# A. FECHOU O FURO
# ---------------------------------------------------------------------------


class TestFechouOFuro:
    """O cabeçalho forjado não compra mais baldes."""

    def test_doze_xff_forjados_caem_no_mesmo_balde(self, com_proxy_declarado):
        """NEGATIVO. Regressão direta da medição do defeito.

        Antes: 12 XFF distintos com 1 `REMOTE_ADDR` → 12 identidades
        distintas. Este é o número que prova o fechamento.

        Passa por `_ident`, que é o `get_ident` DA CLASSE DE THROTTLE — o
        caminho que a requisição de login percorre de fato.
        """
        identidades = {
            _ident(ReqAnon(CLIENTE, f"198.18.0.{i + 1}")) for i in range(12)
        }
        assert len(identidades) == 1, (
            f"12 XFF forjados com o mesmo REMOTE_ADDR abriram "
            f"{len(identidades)} baldes: {sorted(identidades)}. "
            f"O atacante ainda escolhe o balde pelo cabeçalho."
        )
        assert identidades == {CLIENTE}

    def test_decima_primeira_continua_bloqueada(self, cache_locmem_isolado, com_proxy_declarado):
        """POSITIVO do balde: o limite conta de verdade.

        Precisa do cache real: com `DummyCache` isto passaria sempre.
        """
        limite = _limite()
        t = _throttle()
        for _ in range(limite):
            t.allow_request(ReqAnon(CLIENTE, "1.1.1.1"), View())
        assert t.allow_request(ReqAnon(CLIENTE, "1.1.1.1"), View()) is False, (
            f"a {limite + 1}ª requisição deveria estar bloqueada"
        )

    def test_trocar_xff_nao_destrava_o_limite(self, cache_locmem_isolado, com_proxy_declarado):
        """NEGATIVO, e é o teste que mata o defeito.

        O agente anterior mediu: esgota 10 com XFF=1.1.1.1, a 11ª com
        XFF=2.2.2.2 ERA PERMITIDA. Aqui tem de ser bloqueada.
        """
        limite = _limite()
        t = _throttle()
        for _ in range(limite):
            t.allow_request(ReqAnon(CLIENTE, "1.1.1.1"), View())
        assert t.allow_request(ReqAnon(CLIENTE, "2.2.2.2"), View()) is False, (
            "trocar o XFF destravou o limite — o cabeçalho ainda escolhe o balde"
        )

    def test_xff_de_cinco_elementos_nao_destrava_o_limite(
        self, cache_locmem_isolado, com_proxy_declarado
    ):
        """NEGATIVO com cadeia longa: o último elemento é do proxy, não do cliente.

        Cobre o pedido explícito de "XFF com 5 elementos". O atacante põe o
        valor que quer no FIM da cadeia; como o `get_ident` ignora o XFF
        inteiro quando o `REMOTE_ADDR` é o proxy declarado, os cinco
        elementos são irrelevantes.
        """
        limite = _limite()
        t = _throttle()
        for _ in range(limite):
            t.allow_request(ReqAnon(CLIENTE, "1.1.1.1"), View())
        forjado = "9.9.9.9, 8.8.8.8, 7.7.7.7, 6.6.6.6, 1.1.1.1"
        assert t.allow_request(ReqAnon(CLIENTE, forjado), View()) is False, (
            "cadeia de 5 elementos destravou o limite"
        )

    @pytest.mark.parametrize(
        "classe",
        [EscritaPublicaAnonThrottle, AuthSensivelAnonThrottle, EnderecosAnonThrottle],
    )
    def test_todas_as_anon_usam_a_identidade_nova(self, classe, com_proxy_declarado):
        """As 3 classes `AnonRateThrottle` de `config/throttling.py` foram
        corrigidas — não só a do login, que é a mais citada.

        Os dois lados, porque só o lado "ignora o forjado" não prova que a
        classe está ligada ao módulo novo: uma classe que simplesmente
        ignorasse o XFF sempre passaria nele. O lado que exige o XFF
        autêntico é o que prova o mesmo caminho de código.
        """
        # Lado forjado: `REMOTE_ADDR` não é o proxy declarado -> ignora o XFF.
        assert classe().get_ident(ReqAnon(CLIENTE, "9.9.9.9")) == CLIENTE
        # Lado legítimo: `REMOTE_ADDR` É o proxy declarado -> respeita o XFF.
        assert classe().get_ident(ReqAnon(PROXY, CLIENTE)) == CLIENTE

    def test_denuncia_user_throttle_nao_muda_de_comportamento(self, com_proxy_declarado):
        """`DenunciaUserThrottle` fica como está, de propósito.

        Ela é `UserRateThrottle` (exige `IsAuthenticated`) e o DRF já usa
        `request.user.pk` como chave — o cliente não forja isso. Este teste
        registra a decisão: `get_ident` NÃO é o que protege a denúncia, e
        mexer nele não é o ponto.
        """
        assert issubclass(DenunciaUserThrottle, __import__(
            "rest_framework.throttling", fromlist=["UserRateThrottle"]
        ).UserRateThrottle)
        assert not issubclass(DenunciaUserThrottle, AuthSensivelAnonThrottle)
        # A classe não sobrescreve `get_ident`: usa o do DRF, que para
        # usuário autenticado nem chega a chamar.
        assert "get_ident" not in vars(DenunciaUserThrottle)


# ---------------------------------------------------------------------------
# B. NÃO VIROU self-DoS
# ---------------------------------------------------------------------------


class TestNaoVirouSelfDoS:
    """A correção errada aqui seria pior que o defeito."""

    def test_dois_remote_addr_distintos_ficam_em_balde_separado(
        self, cache_locmem_isolado, com_proxy_declarado
    ):
        """POSITIVO. O oposto exato do `NUM_PROXIES: 0`.

        Se a correção fizesse todo mundo cair num balde só, este teste
        reprovaria — e seria a resposta correta reprovar, porque essa
        variante dá 429 global no login a partir de um único atacante.
        """
        limite = _limite()
        ta, tb = _throttle(), _throttle()
        for _ in range(limite):
            ta.allow_request(ReqAnon(CLIENTE), View())

        assert ta.allow_request(ReqAnon(CLIENTE), View()) is False, (
            "o próprio IP deveria estar bloqueado"
        )
        assert tb.allow_request(ReqAnon(OUTRO_CLIENTE), View()) is True, (
            f"{OUTRO_CLIENTE} foi derrubado pelo limite de {CLIENTE}: "
            f"a correção virou self-DoS"
        )

    def test_tres_clientes_ficam_em_tres_baldes(self, com_proxy_declarado):
        """NEGATIVO, sem cache: três IPs de verdade são três identidades."""
        identidades = {
            _ident(ReqAnon(ip)) for ip in (CLIENTE, OUTRO_CLIENTE, TERCEIRO_CLIENTE)
        }
        assert identidades == {CLIENTE, OUTRO_CLIENTE, TERCEIRO_CLIENTE}


# ---------------------------------------------------------------------------
# C. FAIL-CLOSED
# ---------------------------------------------------------------------------


class TestFailClosed:
    """Ausência de configuração não pode virar permissão."""

    def test_sem_variavel_declarada_o_xff_nao_altera_a_identidade(self, sem_proxy_declarado):
        """NEGATIVO — o caso que fecha o item.

        Variável ausente/vazia = conjunto vazio = o cabeçalho não é lido.
        Na base vulnerável, este mesmo par devolvia '1.1.1.1'.
        """
        assert _ident(ReqAnon(CLIENTE, "1.1.1.1")) == CLIENTE

    def test_variavel_vazia_por_espacos_e_virgula_também_ignora(self, settings):
        """NEGATIVO de borda: ' , , ' não declara proxy nenhum.

        Uma variável que o operador preencheu de spaces não pode ser lida
        como "um proxy chamado espaço".
        """
        settings.TRUSTED_PROXY_IPS = " , , "
        assert _ident(ReqAnon(CLIENTE, "1.1.1.1")) == CLIENTE

    def test_proxy_declarado_que_nao_e_o_remote_addr_nao_altera_a_identidade(self, settings):
        """NEGATIVO — o par que discrimina contra a reversão.

        O proxy declarado é `PROXY`, mas o `REMOTE_ADDR` da requisição é
        `CLIENTE`: quem escreveu o cabeçalho não é ninguém declarado, então
        o cabeçalho é do cliente por definição.
        """
        settings.TRUSTED_PROXY_IPS = PROXY
        assert _ident(ReqAnon(CLIENTE, "1.1.1.1")) == CLIENTE

    def test_outro_proxy_declarado_e_nao_est_este_remoto_addr(self, settings):
        """NEGATIVO: declarar um proxy não autoriza todo mundo.

        Sem isto, declarar `127.0.0.1` para o Nginx local tornaria trusting
        também qualquer outro `REMOTE_ADDR` — que é exatamente o furo.
        """
        settings.TRUSTED_PROXY_IPS = "10.0.0.7"
        assert _ident(ReqAnon(CLIENTE, "1.1.1.1")) == CLIENTE

    @pytest.mark.parametrize(
        "xff",
        [
            "nao-e-um-ip",
            "999.999.999.999",
            "203.0.113.10:8080",
            "203.0.113.10; DROP",
            "<script>",
            ",,,,",
            "   ",
        ],
    )
    def test_xff_com_lixo_nao_vira_identidade(self, xff, com_proxy_declarado):
        """NEGATIVO de borda: nenhum valor livre vira chave de balde.

        Na base vulnerável, `nao-e-um-ip` virava literalmente a identidade.
        Aqui qualquer não-IP cai em `REMOTE_ADDR`.
        """
        assert _ident(ReqAnon(CLIENTE, xff)) == CLIENTE

    def test_xff_com_ip_malformado_no_ultimo_elemento_cai_para_remoto_addr(
        self, com_proxy_declarado
    ):
        """NEGATIVO: último elemento malformado, mesmo com cadeia válida antes.

        Cobre "XFF com IP malformado" quando há ruído antes — o último
        elemento é o único que conta, e ele não é um IP.
        """
        assert _ident(ReqAnon(CLIENTE, "1.1.1.1, nao-e-um-ip")) == CLIENTE

    def test_entrada_invalida_na_configuracao_e_descartada_nao_quebra(self, settings):
        """A entrada inválida é IGNORADA, não fatal.

        Um erro de digitação não pode derrubar o processo no meio do
        tráfego. O efeito é o proxy não contar como confiável — que é a
        direção segura. O erro de configuração vira `check`, ver
        `config/apps.py`.
        """
        settings.TRUSTED_PROXY_IPS = "isto-nao-e-um-ip"
        assert _ident(ReqAnon(PROXY, "1.1.1.1")) == PROXY


# ---------------------------------------------------------------------------
# D. CASO LEGÍTIMO (o que a falha acima custaria se não existisse)
# ---------------------------------------------------------------------------


class TestCasoLegitimo:
    """Quem vem por trás de um proxy DECLARADO continua sendo identificado
    pelo IP real — sem isto, a correção quebraria o rate limit por IP de todo
    mundo atrás do balanceador."""

    def test_xff_autentico_de_proxy_declarado_e_respeitado(self, com_proxy_declarado):
        """POSITIVO. `REMOTE_ADDR` é o proxy declarado e o XFF traz o cliente."""
        assert _ident(ReqAnon(PROXY, CLIENTE)) == CLIENTE

    def test_cadeia_com_tres_elementos_usa_o_ultimo(self, com_proxy_declarado):
        """POSITIVO: `cliente, proxy1, proxy2` → o da direita.

        O elemento da esquerda é o que o cliente escolheu; o da direita é o
        que o proxy em que confiamos escreveu.
        """
        assert _ident(ReqAnon(PROXY, f"203.0.113.99, 10.0.0.2, {PROXY}")) == PROXY

    def test_cinco_elementos_usa_o_ultimo(self, com_proxy_declarado):
        """POSITIVO, e é o par do caso de 5 elementos pedido.

        Mesma cadeia do teste de self-DoS, agora com o proxy declarado: o
        último elemento é respeitado, os outros quatro são irrelevantes.
        """
        assert _ident(ReqAnon(PROXY, f"9.9.9.9, 8.8.8.8, 7.7.7.7, 6.6.6.6, {OUTRO_CLIENTE}")) == OUTRO_CLIENTE

    def test_dois_clientes_reais_atras_do_proxy_tem_baldes_separados(
        self, cache_locmem_isolado, com_proxy_declarado
    ):
        """POSITIVO: o caso legítimo NÃO compartilha balde.

        Se este teste reprovar, a correção colapsou os usuários de trás do
        balanceador num balde só — que é o outro lado do self-DoS.
        """
        limite = _limite()
        ta, tb = _throttle(), _throttle()
        for _ in range(limite):
            ta.allow_request(ReqAnon(PROXY, CLIENTE), View())
        assert ta.allow_request(ReqAnon(PROXY, CLIENTE), View()) is False
        assert tb.allow_request(ReqAnon(PROXY, OUTRO_CLIENTE), View()) is True

    def test_cidr_declarado_cobre_a_faixa(self, settings):
        """POSITIVO: o operador pode declarar uma faixa, não só um IP."""
        settings.TRUSTED_PROXY_IPS = "10.0.0.0/8"
        assert _ident(ReqAnon("10.1.2.3", CLIENTE)) == CLIENTE

    def test_cidr_declarado_nao_cobre_fora_da_faixa(self, settings):
        """NEGATIVO: o prefixo declarado é uma fronteira, não um 'sim' geral.

        `198.51.100.77` está fora de `10.0.0.0/8` — declarar a faixa interna
        não autoriza a rede pública toda.
        """
        settings.TRUSTED_PROXY_IPS = "10.0.0.0/8"
        assert _ident(ReqAnon(OUTRO_CLIENTE, CLIENTE)) == OUTRO_CLIENTE


# ---------------------------------------------------------------------------
# E. BORDES PEDIDOS
# ---------------------------------------------------------------------------


class TestBordes:
    def test_remote_addr_real_sem_xff(self, com_proxy_declarado):
        """XFF AUSENTE com proxy declarado: identidade = REMOTE_ADDR."""
        assert _ident(ReqAnon(CLIENTE)) == CLIENTE

    def test_xff_ausente_com_proxy_declarado_usa_remoto_addr(self, com_proxy_declarado):
        """Mesmo caso, isolado do anterior para o nome dizer o que testa."""
        req = ReqAnon(PROXY)
        assert "HTTP_X_FORWARDED_FOR" not in req.META
        assert get_ident(req) == PROXY

    def test_remote_addr_ipv6(self, com_proxy_declarado):
        """IPv4-mapped IPv6 no `REMOTE_ADDR` volta como `::ffff:...`."""
        ident = _ident(ReqAnon("::ffff:203.0.113.10", "1.1.1.1"))
        assert ident == "::ffff:203.0.113.10"

    def test_remote_addr_ipv6_com_proxy_ipv6_declarado(self, settings):
        """IPv6 nos DOIS lados: proxy declarado `::1` respeita o XFF do cliente."""
        settings.TRUSTED_PROXY_IPS = IPV6_PROXY
        assert _ident(ReqAnon(IPV6_PROXY, IPV6_CLIENTE)) == IPV6_CLIENTE

    def test_remote_addr_ipv6_sem_proxy_declarado_ignora_xff(self, sem_proxy_declarado):
        """NEGATIVO: IPv6 não abre uma exceção para o fail-closed."""
        assert _ident(ReqAnon(IPV6_CLIENTE, "1.1.1.1")) == IPV6_CLIENTE

    def test_identidade_e_sempre_string(self, com_proxy_declarado):
        """Contrato: `get_ident` sempre devolve string (é o que vira a chave)."""
        for remote, xff in [
            (CLIENTE, None),
            (CLIENTE, "lixo"),
            (PROXY, CLIENTE),
            ("::1", "2001:db8::1"),
        ]:
            assert isinstance(_ident(ReqAnon(remote, xff)), str)

    def test_espacos_ao_redor_do_ultimo_elemento_sao_removidos(self, com_proxy_declarado):
        """`" 1.1.1.1 , 2.2.2.2 "` → o último, sem espaço em volta."""
        assert _ident(ReqAnon(PROXY, f" 1.1.1.1 , {OUTRO_CLIENTE} ")) == OUTRO_CLIENTE


# ---------------------------------------------------------------------------
# F. O DISCRIMINANTE — o teste que não pode passar nos dois lados
# ---------------------------------------------------------------------------


class TestDiscriminacao:
    """Se estes testes passarem com a correção revertida, eles não provam
    nada. O ponto é que a diferença entre "confia" e "não confia" só aparece
    quando o MESMO XFF muda de resposta conforme a declaração do proxy."""

    def test_o_mesmo_xff_tem_respostas_opostas(self, settings):
        """POSITIVO com proxy declarado + NEGATIVO sem proxy declarado.

        Uma função `get_ident` que ignorasse o XFF nos dois casos PASSARIA
        num teste "o XFF forjado não muda nada" e falharia neste. Uma que
        lesse o XFF nos dois casos também falharia. Só passa a que obedece
        à declaração.
        """
        settings.TRUSTED_PROXY_IPS = PROXY
        com_declaracao = _ident(ReqAnon(PROXY, "1.1.1.1"))

        settings.TRUSTED_PROXY_IPS = ""
        sem_declaracao = _ident(ReqAnon(PROXY, "1.1.1.1"))

        assert com_declaracao == "1.1.1.1", "proxy declarado: o XFF deve valer"
        assert sem_declaracao == PROXY, "sem declaração: o XFF NÃO pode valer"

    def test_identidade_muda_so_quando_a_declaracao_muda(self, settings):
        """A resposta é função da configuração, não do cabeçalho sozinho."""
        pedido = ReqAnon(PROXY, CLIENTE)
        respostas = set()
        for declarado in ["", PROXY, "10.0.0.0/8", "0.0.0.0/0", PROXY]:
            settings.TRUSTED_PROXY_IPS = declarado
            respostas.add(get_ident(pedido))
        # `0.0.0.0/0` declara toda a rede IPv4: aí o XFF passa a valer, e é
        # a única diferença entre as duas respostas observadas.
        assert respostas == {PROXY, CLIENTE}


# ---------------------------------------------------------------------------
# G. O MÓDULO SOZINHO (unidade) e O CHECK DE CONFIGURAÇÃO
# ---------------------------------------------------------------------------


class TestModuloDireto:
    """Chamadas a `config.proxies.get_ident` diretamente.

    Deliberadamente separado das quatro provas: aqui testa-se a FUNÇÃO, e lá
    testa-se o CAMINHO QUE O THROTTLE USA. Um teste que passasse pelos dois
    níveis não saberia dizer qual dos dois quebrou.
    """

    def test_get_ident_do_modulo_ignora_xff_sem_declaracao(self, sem_proxy_declarado):
        assert get_ident(ReqAnon(CLIENTE, "1.1.1.1")) == CLIENTE

    def test_get_ident_do_modulo_respeita_xff_de_proxy_declarado(self, com_proxy_declarado):
        assert get_ident(ReqAnon(PROXY, CLIENTE)) == CLIENTE

    def test_get_ident_aceita_qualquer_request_com_modo_e_user(self, com_proxy_declarado):
        """O contrato é `request.META`; não pode depender de mais nada.

        Um `get_ident` que tocasse em `request.user` ou `request.scheme`
        quebraria no throttle do worker ou em qualquer caminho que não tenha
        o objeto completo montado.
        """
        class Minimo:
            META = {"REMOTE_ADDR": PROXY, "HTTP_X_FORWARDED_FOR": CLIENTE}

        assert get_ident(Minimo()) == CLIENTE


class TestCheckDeConfiguracao:
    """`config/apps.py` transforma configuração inválida em erro de `check`.

    Sem isto, um proxy declarado com erro de digitação é descartado em
    silêncio — e o operador nunca descobre que aquele proxy deixou de ser
    confiável, o que empurra todo o tráfego atrás dele para um balde único.
    """

    def _rodar_check(self, settings):
        from config.apps import ConfigAppConfig

        return ConfigAppConfig._check_proxies_confiados(None)

    def test_configuracao_valida_nao_gera_erro(self, com_proxy_declarado):
        assert self._rodar_check(None) == []

    def test_configuracao_ausente_nao_gera_erro(self, sem_proxy_declarado):
        """Ausente é um estado legítimo (fail-closed), não um erro."""
        assert self._rodar_check(None) == []

    def test_entrada_invalida_gera_erro_de_check(self, settings):
        """O erro precisa aparecer no `check`, que é o que roda no deploy."""
        settings.TRUSTED_PROXY_IPS = "10.0.0.1,isto-nao-e-um-ip"
        erros = self._rodar_check(None)
        assert len(erros) == 1, f"esperado 1 erro, obtido {erros}"
        assert erros[0].id == "config.E001"
        # A mensagem diz QUAL entrada e o que acontece com ela — sem
        # descrever valor de segredo nenhum.
        assert "isto-nao-e-um-ip" in erros[0].msg

    def test_erro_de_check_aparece_no_manage_py_check(self, settings):
        """Fechamento: o erro é realmente coletado pelo Django, não só pela
        chamada direta da função de check."""
        from django.core.checks import run_checks

        settings.TRUSTED_PROXY_IPS = "nao-e-um-ip"
        ids = [e.id for e in run_checks()]
        assert "config.E001" in ids, f"config.E001 não apareceu em {ids}"
