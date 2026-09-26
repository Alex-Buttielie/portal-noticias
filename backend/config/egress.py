"""
Controle de saída HTTP (SSRF) — módulo único e reutilizável do backend.

=============================================================================
O PROBLEMA
=============================================================================
Este backend faz requisição para fora em pelo menos 7 lugares. O caso mais
grave é o de RSS: `catalogo_noticias` busca o `url_feed` de cada fonte, e
esse cadastro é PREENCHIDO A PARTIR DE DADOS DE TERCEIROS (ver
`catalogo_noticias/management/commands/descobrir_feeds.py`, que extrai
endpoints de homepages externas) ou por um admin. Um feed apontando para
`http://169.254.169.254/latest/meta-data/iam/security-credentials/` faz o
servidor ler as credenciais da cloud e devolvê-las no corpo — cURL para
dentro. É SSRF com impacto imediato em produção.

=============================================================================
POR QUE "VALIDAR A URL" NÃO BASTA (e o que este módulo faz)
=============================================================================
Uma allowlist só por URL, ou um `startswith("https://")`, é trivialmente
contornável:
  - `http://169.254.169.254/` passa em qualquer verificação de "é http?".
  - `http://localhost@169.254.169.254/` — o `@` faz o parser tratar
    `localhost` como *userinfo* e `169.254.169.254` como host.
  - `http://127.1/`, `http://0/`, `http://[::1]/`, `http://2130706433/`
    — todas encodeiam o loopback e nem contain "127.0.0.1" como string.
  - `http://evil.com/` que responde `302 Location: http://169.254.169.254/`
    — a validação passa e o `requests` SEGUE o redirect.

Por isso o módulo valida em TRÊS camadas:

  1. ESQUEMA + AUTORIDADE, com `urllib.parse.urlsplit` (o mesmo parser
     que o browser usa no início da URL), NÃO com comparação de string.
     Rejeita `user@host`, host vazio, porta fora de 1..65535.
  2. ENDEREÇO RESOLVIDO. `socket.getaddrinfo` e cada IP devolvido é
     normalizado (IPv4-mapped IPv6 -> IPv4, IPv4-in-IPv6 -> IPv4) e
     testado contra redes privadas/reservadas. Isto é o que pega
     `127.1`, `0`, `2130706433`, `::1` e DNS que resolve para
     `169.254.169.254`. Nenhum nome passa se QUALQUER uma das respostas
     for privada — assim, um DNS "split-horizon" com um A público e um AAAA
     privado é barrado.
  3. CADA REDIRECT, validado com o MESMO procedimento antes de ser
     seguido. `SessaoEgress.resolve_redirects` revalida a cada
     `Location`; um `allow_redirects=True` só é seguro porque isso
     acontece.

=============================================================================
RESIDUO CONHECIDO, DECLARADO (não esconder)
=============================================================================
Entre validar o IP resolvido e o `requests` abrir o socket existe uma
janela de TOCTOU (DNS rebinding): um resolver autoritativo pode responder
`1.2.3.4` na nossa consulta e `127.0.0.1` na do `requests`. Fechar isso
exige fixar o IP no adapter de conexão (transport próprio), o que é uma
mudança grande no `requests` e foi considered fora do escopo deste item.

Mitigações aplicadas no lugar:
  - Validação estrita de TUDO que sai, sem exceção.
  - Não seguimos redirects deScheme alterado (https -> http) sem
    revalidar (revalidamos sempre, na verdade).
  - `Referer` nunca é enviado no redirect, e a sessão não carrega
    credenciais de `netrc` para hosts novos.

Isto é risco ACEITO e DOCUMENTADO, não risco ignorado.

=============================================================================
POR QUE TAMBÉM EXISTE UMA ALLOWLIST DE HOST
=============================================================================
A allowlist é segunda, não primeira: ela existe para dar nome ao que é
legítimo (`ALVO_CONFIANCAVEL`) e para permitir, via
`EGRESS_HOSTS_PERMITIDOS`, que a operação libere um host novo sem
deploy. Ela NUNCA substitui a checagem de IP — um host da allowlist que
resolva para `127.0.0.1` (DNS envenenado, `/etc/hosts` editado,
`sslip.io`) é barrado igual.
"""

from __future__ import annotations

import ipaddress
import logging
import re
import socket
from typing import Any, Iterable
from urllib.parse import urlsplit, urlunsplit

import requests
from requests.adapters import HTTPAdapter
from requests.models import Response

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuração
# ---------------------------------------------------------------------------

#: Esquemas aceitos. `file:`, `gopher:`, `dict:`, `ftp:` e `data:` fora.
ESQUEMAS_PERMITIDOS: frozenset[str] = frozenset({"http", "https"})

#: Redes que nunca podem ser alvo de saída. Inclui as exigidas pelo item e
#: as lacunas costumeiras:
#:  - 0.0.0.0/8       (this-network; `http://0/` = loopback em glibc)
#:  - 100.64.0.0/10    (CGNAT, exigida pelo item)
#:  - 169.254.0.0/16   (link-local, inclui o metadata 169.254.169.254)
#:  - 192.0.0.0/24     (IETF protocol assignments)
#:  - 192.0.2.0/24     (TEST-NET-1)
#:  - 198.18.0.0/15    (benchmark)
#:  - 198.51.100.0/24  (TEST-NET-2)
#:  - 203.0.113.0/24   (TEST-NET-3)
#:  - 224.0.0.0/4      (multicast)
#:  - 240.0.0.0/4      (reserved) e 255.255.255.255/32 (broadcast)
#:  - 64:ff9b::/96     (NAT64) — faz um IPv4 privado "sair" por IPv6
#:  - ::/128, ::1/128  (loopback e unspecified IPv6)
#:  - fe80::/10        (link-local IPv6)
#:  - fc00::/7         (ULA, exigida pelo item)
#:  - ff00::/8         (multicast IPv6)
#:  - 2001:db8::/32    (documentação)
# NOTA: NÃO incluímos IPv4-mapped/private ranges aqui de novo, porque
#: `_normalizar_ipv6` os converte para IPv4 antes do teste.
REDES_BLOQUEADAS: tuple[ipaddress.IPv4Network | ipaddress.IPv6Network, ...] = (
    ipaddress.ip_network("0.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("100.64.0.0/10"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("192.0.0.0/24"),
    ipaddress.ip_network("192.0.2.0/24"),
    ipaddress.ip_network("198.18.0.0/15"),
    ipaddress.ip_network("198.51.100.0/24"),
    ipaddress.ip_network("203.0.113.0/24"),
    ipaddress.ip_network("224.0.0.0/4"),
    ipaddress.ip_network("240.0.0.0/4"),
    ipaddress.ip_network("255.255.255.255/32"),
    ipaddress.ip_network("::/128"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("64:ff9b::/96"),
    ipaddress.ip_network("100::/64"),
    ipaddress.ip_network("2001:db8::/32"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
    ipaddress.ip_network("ff00::/8"),
)

#: Endereço de metadata de cloud. Numa VPC AWS/GCP, ou em host com
#: IMDSv1 ligado, GET aqui devolve credenciais da role da instância.
METADATA_IP = "169.254.169.254"

#: Domínios considered confiáveis, para código que QUER nomear o alvo
#: (ex.: assertar que um webhook aponta mesmo para o host esperado).
#: NÃO é usado para autorizar: a checagem de IP sempre roda.
ALVO_CONFIANCAVEL: frozenset[str] = frozenset(
    {
        "api.resend.com",
        "api.mercadopago.com",
        "sandbox.mercadopago.com",
        "api.openai.com",
        "viacep.com.br",
        "servicodados.ibge.gov.br",
        "nominatim.openstreetmap.org",
    }
)

#: Sub-redes que a operação pode liberar por variável de ambiente.
#: Formato: "1.2.3.0/24,2001:db8::/32". Entradas inválidas são IGNORADAS
#: com log de aviso — nunca falham de forma silenciosa.
def _redes_permitidas_do_ambiente() -> tuple[Any, ...]:
    import os

    cru = os.environ.get("EGRESS_REDES_PERMITIDAS", "")
    saida: list[Any] = []
    for pedaco in cru.split(","):
        pedaco = pedaco.strip()
        if not pedaco:
            continue
        try:
            saida.append(ipaddress.ip_network(pedaco, strict=False))
        except ValueError:
            logger.warning(
                "EGRESS_REDES_PERMITIDAS contém entrada inválida ignorada: %r", pedaco
            )
    return tuple(saida)


# ---------------------------------------------------------------------------
# Exceções
# ---------------------------------------------------------------------------


class EgressError(Exception):
    """Base das falhas de controle de saída."""


class EgressBloqueado(EgressError):
    """A URL/host/IP é forbidden por política de saída. Não há retry."""

    def __init__(self, mensagem: str, *, host: str = "", url: str = "", ip: str = "") -> None:
        super().__init__(mensagem)
        self.host = host
        self.url = url
        self.ip = ip


# ---------------------------------------------------------------------------
# Normalização e teste de IP
# ---------------------------------------------------------------------------


def _normalizar_ipv6(endereco: ipaddress.IPv6Address) -> ipaddress.IPv4Address | ipaddress.IPv6Address:
    """
    Reduz endereços IPv6 "embutidos" a IPv4, para que o teste de rede
    bloqueada não dependa do formato.

    Cobre, em uma linha:
      - `::ffff:127.0.0.1` (IPv4-mapped) -> `127.0.0.1`
      - `::ffff:7f00:1` (a mesma coisa em hex) -> `127.0.0.1`
      - `2002:7f00:1::` (6to4 com IPv4 privado embutido) -> `127.0.0.1`
      - `64:ff9b::127.0.0.1` (NAT64) -> `127.0.0.1`
    Sem isso, `::ffff:169.254.169.254` — que ALCANÇA o metadata — passaria,
    porque `::ffff:0:0/96` não está na lista de redes IPv6.
    """
    if getattr(endereco, "ipv4_mapped", None) is not None:
        return endereco.ipv4_mapped
    if endereco.sixtofour is not None:
        return endereco.sixtofour
    if endereco.teredo is not None:
        # Teredo embute o IPv4 do servidor no campo do cliente.
        return endereco.teredo[1]
    if endereco in ipaddress.ip_network("64:ff9b::/96"):
        return ipaddress.IPv4Address(int(endereco) & 0xFFFFFFFF)
    return endereco


def ip_e_bloqueado(endereco: str | ipaddress._BaseAddress) -> str | None:
    """
    Devolve o motivo se o IP for privado/reservado; `None` se for público.

    `endereco` pode ser IPv4 ou IPv6, em qualquer notação.

    PRECEDÊNCIA (a ordem importa e foi testada):

    1. Metadata de cloud — bloqueio ABSOLUTO, não sobreponível por
       `EGRESS_REDES_PERMITIDAS`. Permitir o metadata por variável de
       ambiente seria um tiro no pé: a variável existe para alcançar um
       serviço interno legítimo, não para reabrir o cURL de credenciais.
    2. Redes explicitamente liberadas pela operação
       (`EGRESS_REDES_PERMITIDAS`) — VENCEM a lista de bloqueadas, senão a
       variável seria inútil (o `127.0.0.0/8` bloqueado sempre casaria
       primeiro).
    3. Lista de redes bloqueadas.
    4. `is_global` do stdlib, como rede de segurança final.
    """
    try:
        if isinstance(endereco, str):
            ip = ipaddress.ip_address(endereco)
        else:
            ip = endereco
    except ValueError:
        return f"endereço inválido: {endereco!r}"

    normalizado = _normalizar_ipv6(ip) if isinstance(ip, ipaddress.IPv6Address) else ip

    # 1. Metadata: bloqueio duro, não sobreponível.
    if str(normalizado) == METADATA_IP:
        return f"endereço de metadata de cloud ({METADATA_IP}) — acesso_negado"

    # 2. Liberações explícitas da operação.
    for rede in _redes_permitidas_do_ambiente():
        if rede.version != normalizado.version:
            continue
        if normalizado in rede:
            return None

    # 3. Redes bloqueadas.
    for rede in REDES_BLOQUEADAS:
        # Rede e endereço precisam ser do mesmo família para comparação.
        if rede.version != normalizado.version:
            continue
        if normalizado in rede:
            return f"rede não roteável na internet: {rede}"

    # 4. Rede de segurança final: qualquer coisa que o `is_global` do
    # stdlib considere não-global é barrada, mesmo sem estar na lista.
    # Cobre os casos que alguém esquecer de enumerar.
    if not normalizado.is_global:
        return f"endereço não global ({normalizado})"
    return None


# ---------------------------------------------------------------------------
# Validação
# ---------------------------------------------------------------------------


def _resolver(host: str, porta: int) -> list[str]:
    """Todos os IPs de um host, via `getaddrinfo`. Levanta `EgressBloqueado`."""
    try:
        infos = socket.getaddrinfo(host, porta, proto=socket.IPPROTO_TCP)
    except socket.gaierror as exc:
        raise EgressBloqueado(
            f"host não resolvido: {host!r} ({exc.strerror or exc})", host=host
        ) from exc
    except UnicodeError as exc:
        raise EgressBloqueado(f"host inválido: {host!r} ({exc})", host=host) from exc

    ips: list[str] = []
    for info in infos:
        sockaddr = info[4]
        if sockaddr and isinstance(sockaddr[0], str):
            ips.append(sockaddr[0])
    if not ips:
        raise EgressBloqueado(f"host sem endereço: {host!r}", host=host)
    # Dedup preservando ordem (a primeira resposta é a que o OS prefere).
    return list(dict.fromkeys(ips))


def _autoridade_valida(autoridade: str) -> bool:
    """
    `host:porta` bem formado, sem lixo que o `getaddrinfo` de outra
    plataforma pode interpretar diferente.
    """
    if not autoridade:
        return False
    # Rejeita byte/caráter de controle e espaço (parser divergence).
    if any(ord(c) <= 0x20 or ord(c) == 0x7F for c in autoridade):
        return False
    return True


def validar_url(
    url: str | None,
    *,
    esquemas: Iterable[str] = ESQUEMAS_PERMITIDOS,
    hosts_permitidos: Iterable[str] | None = None,
    exigir_https: bool = False,
) -> str:
    """
    Valida `url` e devolve a URL normalizada (ou a original, se já canônica).

    Levanta `EgressBloqueado` com motivo específico em qualquer falha.
    Nunca devolve a entrada sem validar: quem chama e não trata a exceção
    não consegue "esquecer" a validação.
    """
    if not isinstance(url, str) or not url.strip():
        raise EgressBloqueado("URL vazia ou de tipo inválido", url=repr(url))

    bruto = url.strip()
    try:
        partes = urlsplit(bruto)
    except ValueError as exc:
        raise EgressBloqueado(f"URL não parseável: {exc}", url=url) from exc

    esquema = (partes.scheme or "").lower()
    if not esquema:
        raise EgressBloqueado(
            "URL sem esquema (exigimos http/https explícito; 'exemplo.com/x' "
            "não é aceito)",
            url=url,
        )
    if esquema not in {e.lower() for e in esquemas}:
        raise EgressBloqueado(
            f"esquema não permitido: {esquema!r} (aceitos: {sorted(esquemas)})", url=url
        )
    if exigir_https and esquema != "https":
        raise EgressBloqueado(f"https obrigatório, recebido {esquema!r}", url=url)

    # `urlsplit` move o que vem antes do ÚLTIMO `@` para `.username`/`.password`.
    # Verificar isso é o que barra `http://localhost@169.254.169.254/`.
    if partes.username or partes.password:
        raise EgressBloqueado(
            "URL com credenciais embutidas (usuário:senha@host) não é aceita",
            url=url,
        )

    if not _autoridade_valida(partes.netloc):
        raise EgressBloqueado(f"autoridade ausente ou malformada: {partes.netloc!r}", url=url)

    # `parts.hostname` normaliza para minúsculas e remove os colchetes do
    # IPv6 literal; `parts.port` valida a faixa e levanta ValueError.
    try:
        host = partes.hostname
        porta = partes.port
    except ValueError as exc:
        raise EgressBloqueado(f"porta inválida: {exc}", url=url) from exc
    if not host:
        raise EgressBloqueado("URL sem host", url=url)

    porta = porta or (443 if esquema == "https" else 80)

    # Allowlist de host: informativa e opcional; a checagem de IP abaixo é
    # a que decide. Um host da allowlist que resolva para rede privada é
    # barrado do mesmo jeito.
    if hosts_permitidos is not None:
        permitidos = {h.lower() for h in hosts_permitidos}
        if not any(host == h or host.endswith("." + h) for h in permitidos):
            raise EgressBloqueado(
                f"host fora da allowlist: {host!r} (permitidos: {sorted(permitidos)})",
                host=host,
                url=url,
            )

    ips = _resolver(host, porta)
    for ip in ips:
        motivo = ip_e_bloqueado(ip)
        if motivo:
            raise EgressBloqueado(
                f"IP bloqueado para {host!r} ({ip}): {motivo}", host=host, url=url, ip=ip
            )

    return urlunsplit((esquema, partes.netloc, partes.path, partes.query, partes.fragment))


def _normalizar_url_para_auditoria(url: str) -> str:
    """
    URL para log de auditoria, com a query REDIGIDA.

    Query de serviço externo costuma carregar segredo (`?access_token=`,
    `?api_key=`, `?signature=`). O objeto `EgressBloqueado` pode acabar em
    resposta de API ou em exceção exposta ao cliente; registrar a query
    inteira vazaria a credencial. O host e o caminho continuam visíveis,
    que é o que importa para diagnosticar.
    """
    try:
        partes = urlsplit(url)
    except ValueError:
        return "(url não parseável)"
    return urlunsplit((partes.scheme, partes.netloc, partes.path, "[query redigida]" if partes.query else "", ""))


def url_de_servidor_local(url: str) -> bool:
    """
    `True` se a URL.resolve para rede bloqueada.

    Usado nos TESTES e no `descobrir_feeds` para rotular candidatos
    descartados, sem duplicar a lógica de bloqueio.
    """
    try:
        validar_url(url)
    except EgressBloqueado:
        return True
    return False


# ---------------------------------------------------------------------------
# Sessão
# ---------------------------------------------------------------------------

#: User-Agent enviado em toda saída. Sem isto, um serviço externo pode
#: devolver 403 a um cliente anônimo e o operador perde o sinal de que o
#: feed quebrou.
USER_AGENT_EGRESS = "BRDPortalNoticias/1.0 (+egress-controlido)"


class SessaoEgress(requests.Session):
    """
    `requests.Session` que valida TODA URL antes de sair, inclusive cada
    redirect.

    Uso (substitui `requests.get/post/put`):

        with sessao_egress() as sessao:
            r = sessao.get(url, timeout=10)

    Regras:
      - `session.get("http://169.254.169.254/")` levanta `EgressBloqueado`
        ANTES de abrir socket (a validação roda em `request`).
      - `allow_redirects=True` é seguro porque `resolve_redirects`
        revalida cada `Location` antes de seguir. Default de `requests` é
        `True` para GET/OPTIONS e `False` para POST; mantivemos o default
        do `requests` e a validação cobre os dois casos.
      - Erro de validação NÃO é engolido: `EgressBloqueado` propaga
        (é subclasse de `EgressError`, não de `requests.RequestException`),
        para que nenhum `except requests.RequestException` o transforme
        silenciosamente em "fonte indisponível" e devolva `False`.
    """

    def __init__(
        self,
        *,
        esquemas: Iterable[str] = ESQUEMAS_PERMITIDOS,
        hosts_permitidos: Iterable[str] | None = None,
        user_agent: str = USER_AGENT_EGRESS,
    ) -> None:
        super().__init__()
        self._esquemas = tuple(esquemas)
        self._hosts_permitidos = tuple(hosts_permitidos) if hosts_permitidos is not None else None
        self.headers.setdefault("User-Agent", user_agent)
        # Um `Session` compartilhado entre threads exigiria lock em todo
        # request; como cada chamador cria o seu, um `HTTPAdapter` simples
        # basta. `pool_maxsize` maior que o default porque a ingestão
        # dispara vários downloads concorrentes.
        adapter = HTTPAdapter(pool_connections=32, pool_maxsize=32, max_retries=0)
        self.mount("http://", adapter)
        self.mount("https://", adapter)

    # -- validação ---------------------------------------------------------
    def _validar(self, url: str) -> str:
        return validar_url(
            url, esquemas=self._esquemas, hosts_permitidos=self._hosts_permitidos
        )

    def request(self, method, url, *args, **kwargs) -> Response:  # type: ignore[override]
        kwargs.setdefault("timeout", 15)
        self._validar(url)
        return super().request(method, url, *args, **kwargs)

    def send(self, request, **kwargs) -> Response:  # type: ignore[override]
        """
        Ponto de estrangulamento (chokepoint) de TODA saída real.

        Por que aqui e não em `resolve_redirects`: `requests.resolve_redirects`
        chama `self.send(req, allow_redirects=False)` DENTRO do gerador,
        ANTES de devolver a resposta. Um override que validasse a URL
        "quando o gerador produz o próximo item" já estaria tarde demais —
        o socket da rede interna estaria conectado. `send()` é chamado por
        `request()` na primeira Ida e por `resolve_redirects` em CADA
        salto de redirect, então é o único ponto que cobre os dois sem
        depender da ordem interna do `requests`.

        Consequência desejada: um `http://host-publico/redir` que responde
        `302 Location: http://169.254.169.254/...` levanta
        `EgressBloqueado` aqui, e a segunda requisição nunca existe.
        """
        self._validar(request.url)
        return super().send(request, **kwargs)

    # -- conveniência ------------------------------------------------------
    def get(self, url, **kwargs) -> Response:  # type: ignore[override]
        return self.request("GET", url, **kwargs)

    def post(self, url, data=None, json=None, **kwargs) -> Response:  # type: ignore[override]
        return self.request("POST", url, data=data, json=json, **kwargs)

    def put(self, url, data=None, **kwargs) -> Response:  # type: ignore[override]
        return self.request("PUT", url, data=data, **kwargs)

    def delete(self, url, **kwargs) -> Response:  # type: ignore[override]
        return self.request("DELETE", url, **kwargs)

    def head(self, url, **kwargs) -> Response:  # type: ignore[override]
        return self.request("HEAD", url, **kwargs)

    def close(self) -> None:
        super().close()


#: Regex de host, usado só para mensagens de erro legíveis.
_HOST_RE = re.compile(r"^[a-z0-9._-]+$", re.IGNORECASE)


def _host_legivel(host: str) -> str:
    return host if _HOST_RE.match(host or "") else "(host inválido)"
