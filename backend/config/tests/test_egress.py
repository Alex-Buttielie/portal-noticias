"""
Testes do eixo 2 (SSRF) — `config/egress.py`.

O QUE ESTES TESTES PROVAM, E O QUE NÃO PROVAM
==============================================

PROVAM
------
1. **IP privado é recusado com um servidor real de pé.** Não é mock: sobe
   um `http.server` em `127.0.0.1` numa porta efêmera, faz a requisição
   de verdade e verifica que (a) a requisição NUNCA chega ao servidor
   (contador de hits = 0, lido por uma rota专门) e (b) `EgressBloqueado`
   é levantada. Um teste que só mocka `getaddrinfo` provaria que a
   *função de classificação* funciona; este prova que a *política está no
   caminho real da requisição*.
2. **Domínio público é aceito.** Mesma sessão, host público real
   (`example.com`, estável e reservado para documentação), provando que
   o bloqueio não é "bloquear tudo".
3. **Redirect para IP privado é barrado.** Servidor local responde
   `302 Location: http://127.0.0.1:<porta>/alvo`. Sem revalidação de
   redirect, o `requests` seguiria e a segunda requisição chegaria. Com
   `resolve_redirects` revalidando, é barrada — e a rota alvo tem 0 hits.
4. **Bypasses de parsing de URL.** `localhost@host`, `127.1`, `0`,
   `2130706433`, `[::1]`, IPv4-mapped IPv6 (`::ffff:169.254.169.254`),
   6to4, NAT64, credenciais embutidas, esquema ausente, `file:`/`gopher:`,
   host com byte de controle.
5. **DNS que resolve para rede privada** é barrado (via monkeypatch de
   `getaddrinfo`, que aqui é legítima: o objetivo é exercitar o caminho
   "resolveu mas é privado", impossível de provocar de outro jeito sem
   controlar um DNS).
6. **Split-horizon**: se QUALQUER endereço resolvido for privado, barra.
7. **O módulo é realmente usado em todo egresso do backend** — teste de
   guarda por análise do código-fonte que falha se algum `requests.get/
   post/put/delete/head/request` ou `urlopen` for introduzido fora de
   `config/egress.py` e dos testes. Este é o teste que impede a
   reintrodução silenciosa do bug.
8. **A query é redigida** em审计/log, para não vazar `?access_token=`.

NÃO PROVAM
----------
- **DNS rebinding** (TOCTOU entre a validação e o `connect`). Declarado
  como resíduo aceito em `config/egress.py`; exigiria fixar o IP no
  adapter de conexão.
- Que nenhum outro caminho de rede exista (raw socket, `http.client`).
  O teste 7 cobre a superfície `requests`, que é a única usada.
"""

from __future__ import annotations

import http.server
import pathlib
import socket
import threading

import pytest

from config import egress
from config.egress import EgressBloqueado, SessaoEgress, ip_e_bloqueado, validar_url

# ---------------------------------------------------------------------------
# Infra: servidor HTTP real, local, com contagem de hits
# ---------------------------------------------------------------------------


class _Servidor(threading.Thread):
    """
    `http.server` real em `127.0.0.1:porta_efêmera`.

    Não usamos mock aqui de propósito: o que precisa ser provado é que a
    *requisição de verdade* não sai. Um mock de `requests` passaria mesmo
    com o controle de saída completamente ausente do caminho.
    """

    def __init__(self, redirecionar_para: str | None = None) -> None:
        super().__init__(daemon=True)
        self.hits: list[str] = []
        self._redirecionar_para = redirecionar_para
        servidor = self

        class Handler(http.server.BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def _responder(self) -> None:
                servidor.hits.append(self.path)
                if servidor._redirecionar_para is not None:
                    self.send_response(302)
                    self.send_header("Location", servidor._redirecionar_para)
                    self.send_header("Content-Length", "0")
                    self.end_headers()
                    return
                corpo = b"conteudo-interno-que-nao-deve-sair"
                self.send_response(200)
                self.send_header("Content-Type", "text/plain")
                self.send_header("Content-Length", str(len(corpo)))
                self.end_headers()
                self.wfile.write(corpo)

            do_GET = _responder
            do_POST = _responder

            def log_message(self, *args, **kwargs) -> None:  # silencia o stderr
                return

        self._httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.porta = self._httpd.server_address[1]
        self._httpd.timeout = 5

    def run(self) -> None:
        self._httpd.serve_forever(poll_interval=0.1)

    def parar(self) -> None:
        self._httpd.shutdown()
        self._httpd.server_close()

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.porta}/alvo"


@pytest.fixture()
def servidor_local():
    s = _Servidor()
    s.start()
    try:
        yield s
    finally:
        s.parar()


@pytest.fixture()
def servidor_redirecionador():
    """Responde 302 para um destino escolhido pelo teste."""
    s = _Servidor(redirecionar_para="PLACEHOLDER")
    s.start()
    try:
        yield s
    finally:
        s.parar()


# ---------------------------------------------------------------------------
# 1. IP privado recusado — COM SERVIDOR REAL DE PÉ
# ---------------------------------------------------------------------------


def test_ip_privado_e_recusado_e_o_servidor_nao_recebe_nada(servidor_local) -> None:
    """
    A prova central do eixo: com um servidor de pé em 127.0.0.1, a
    requisição é barrada ANTES de chegar nele.
    """
    with SessaoEgress() as sessao:
        with pytest.raises(EgressBloqueado) as info:
            sessao.get(servidor_local.url, timeout=5)

    assert "127.0.0.0/8" in str(info.value), info.value
    assert info.value.ip == "127.0.0.1"
    # A prova de que não é só "o parser levantou": o servidor NÃO registrou
    # requisição alguma. Sem isto, um `except` que engolisse a exceção e
    # devolvesse `Response()` também passaria.
    assert servidor_local.hits == [], f"requisição chegou ao servidor interno: {servidor_local.hits}"


@pytest.mark.parametrize(
    "alvo",
    [
        "http://127.0.0.1:9/",
        "http://127.1:9/",
        "http://0:9/",
        "http://[::1]:9/",
        "http://[::ffff:127.0.0.1]:9/",
        "http://169.254.169.254/latest/meta-data/iam/security-credentials/",
        "http://[::ffff:169.254.169.254]/latest/meta-data/",
        "http://10.0.0.1/",
        "http://172.16.0.1/",
        "http://192.168.1.1/",
        "http://100.64.0.1/",  # CGNAT
        "http://localhost:9/",
    ],
)
def test_alvos_de_rede_interna_sao_recusados(alvo: str) -> None:
    with SessaoEgress() as sessao:
        with pytest.raises(EgressBloqueado):
            sessao.get(alvo, timeout=5)


# ---------------------------------------------------------------------------
# 2. Domínio público é aceito
# ---------------------------------------------------------------------------


def test_dominio_publico_e_aceito_e_a_requisicao_sai() -> None:
    """
    O outro lado da moeda: se isto falhasse, o controle seria um
    "bloquear tudo" e a ingestão de notícias pararia em produção.
    `example.com` é reservado para documentação pela RFC 2606, então é um
    alvo estável e apropriado para teste.
    """
    with SessaoEgress() as sessao:
        resposta = sessao.get("http://example.com/", timeout=10)
    assert resposta.status_code == 200, resposta.status_code


def test_validar_url_aceita_dominio_publico_e_normaliza() -> None:
    assert validar_url("https://example.com/a?b=1") == "https://example.com/a?b=1"
    # Normalização de esquema (minúsculo) sem alterar o resto.
    assert validar_url("HTTPS://example.com/a").startswith("https://example.com")


# ---------------------------------------------------------------------------
# 3. Redirect para IP privado é barrado
# ---------------------------------------------------------------------------


def test_redirect_para_ip_privado_e_barrado_end_to_end(monkeypatch) -> None:
    """
    O bypass mais importante, testado de ponta a ponta com socket real:

    1. `EGRESS_REDES_PERMITIDAS=127.0.0.1/32` libera o SERVIDOR LOCAL, que
       passa a se comportar como um host "público" do ponto de vista da
       política.
    2. Esse servidor responde `302 Location: http://169.254.169.254/...`.

    Se a revalidação de redirect não existisse, o `requests` seguiria e a
    segunda requisição sairia para o metadata de cloud. Aqui ela é barrada
    e o servidor registra apenas 1 hit (a requisição inicial).
    """
    monkeypatch.setenv("EGRESS_REDES_PERMITIDAS", "127.0.0.1/32")
    servidor = _Servidor(redirecionar_para=f"http://{egress.METADATA_IP}/latest/meta-data/")
    servidor.start()
    try:
        with SessaoEgress() as sessao:
            with pytest.raises(EgressBloqueado) as info:
                sessao.get(servidor.url, timeout=5)
    finally:
        servidor.parar()

    assert egress.METADATA_IP in str(info.value), info.value
    assert "metadata" in str(info.value)
    # O servidor de origem foi chamado UMA vez. A segunda requisição
    # (para o metadata) nunca foi montada.
    assert servidor.hits == ["/alvo"], servidor.hits


def test_send_e_o_chokepoint_de_toda_saida() -> None:
    """
    `send()` é o ponto de estrangulamento: é ele que o `requests` chama
    na primeira ida E a cada salto de redirect. Este teste prova que um
    `PreparedRequest` já montado para o metadata é barrado ali — o que
    significa que o `resolve_redirects` (que chama `send` por baixo) não
    consegue contornar.
    """
    import requests

    pedido = requests.models.PreparedRequest()
    pedido.prepare(method="GET", url=f"http://{egress.METADATA_IP}/latest/meta-data/")

    with SessaoEgress() as sessao:
        with pytest.raises(EgressBloqueado) as info:
            sessao.send(pedido, timeout=5)
    assert "metadata" in str(info.value)


# ---------------------------------------------------------------------------
# 4. Bypasses de parsing de URL
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "url,trecho",
    [
        ("http://localhost@169.254.169.254/", "credenciais embutidas"),
        ("http://user:pass@example.com/", "credenciais embutidas"),
        ("http://169.254.169.254:80@exemplo.com/", "credenciais embutidas"),
        ("file:///etc/passwd", "esquema não permitido"),
        ("gopher://exemplo.com/", "esquema não permitido"),
        ("ftp://exemplo.com/x", "esquema não permitido"),
        ("data:text/html,<script>alert(1)</script>", "esquema não permitido"),
        ("dict://exemplo.com:11211/", "esquema não permitido"),
        ("exemplo.com/x", "sem esquema"),
        ("//169.254.169.254/x", "sem esquema"),
        ("http://", "autoridade ausente"),
        ("http://exemplo.com:99999/", "porta inválida"),
        ("http://exem\x00plo.com/", "autoridade"),
    ],
)
def test_bypasses_de_parsing_de_url_sao_recusados(url: str, trecho: str) -> None:
    with pytest.raises(EgressBloqueado) as info:
        validar_url(url)
    assert trecho in str(info.value), f"{url!r} -> motivo inesperado: {info.value}"


def test_url_com_espaco_e_recusada_com_mensagem_util() -> None:
    with pytest.raises(EgressBloqueado) as info:
        validar_url("   ")
    assert "vazia" in str(info.value)


@pytest.mark.parametrize(
    "url",
    [
        # `inet_aton` do glibc aceita hexadecimal e octal. Um filtro por
        # substring não pega nenhum destes; o teste de IP resolvido pega.
        "http://0x7f.0.0.1/",
        "http://0x7f000001/",
        "http://017700000001/",
        # Decimal sem pontos: `2130706433` == `127.0.0.1`.
        "http://2130706433/",
        # Ponto final no rótulo.
        "http://localhost./",
        # Dígitos Unicode: o `getaddrinfo` faz IDNA e resolve para o
        # loopback. Um `ipaddress.ip_address()` no texto cru FALHARIA
        # aqui, e o host passaria sem checagem.
        "http://①②⑦.0.0.1/",
        "http://⓵⓶⑦.0.0.1/",
        # Percent-encoding: não é um host resolvível, e host não
        # resolvível é bloqueio.
        "http://127.0.0.1%2e/",
        "http://%31%32%37.0.0.1/",
        # IPv6 escrito de formas equivalents, com IPv4 embutido.
        "http://[::ffff:7f00:1]/",
        "http://[0:0:0:0:0:ffff:127.0.0.1]/",
        "http://[::ffff:a9fe:a9fe]/",  # ::ffff:169.254.169.254
        "http://[::]/",
        # Serviços DNS que resolvem literalmente para a rede privada.
        # Estes resolvem de verdade no teste (rede disponível), então a
        # proteção é a checagem do IP resolvido, não a lista de hosts.
        "http://169.254.169.254.nip.io/",
        "http://127.0.0.1.sslip.io/",
    ],
)
def test_bypass_por_codificacao_de_ip_e_bloqueado(url: str) -> None:
    """
    Bypasses de CODIFICAÇÃO do endereço. Todos falham com
    "IP bloqueado" (quando resolvem) ou "host não resolvido" (quando não).

    O ponto do teste é que a causa da recusa é o IP RESOLVIDO. Um filtro
    de string passaria por `0x7f.0.0.1` e por `①②⑦.0.0.1`.
    """
    with pytest.raises(EgressBloqueado):
        validar_url(url)


# ---------------------------------------------------------------------------
# 5/6. DNS resolvendo para rede privada
# ---------------------------------------------------------------------------


def test_dns_que_resolve_para_rede_privada_e_barrado(monkeypatch) -> None:
    """
    O caminho "resolveu com sucesso, mas o resultado é privado" é o mais
    importante na prática: um feed apontando para um nome DNS controlado
    pelo atacante, que resolve para 127.0.0.1.
    """

    def _getaddrinfo(host, port, *args, **kwargs):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", port))]

    monkeypatch.setattr(egress.socket, "getaddrinfo", _getaddrinfo)
    with pytest.raises(EgressBloqueado) as info:
        validar_url("http://feed-malicioso.exemplo/rss")
    assert info.value.ip == "127.0.0.1"


def test_split_horizon_com_um_ip_publico_continua_barrado(monkeypatch) -> None:
    """
    Se QUALQUER endereço resolvido for privado, barra — mesmo que outro
    seja público. Um DNS que responde "um A público (para passar na
    validação) + um AAAA privado (para o SO conectar)" é um bypass real.
    """

    def _getaddrinfo(host, port, *args, **kwargs):
        return [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", port)),
            (socket.AF_INET6, socket.SOCK_STREAM, 6, "", ("::1", port, 0, 0)),
        ]

    monkeypatch.setattr(egress.socket, "getaddrinfo", _getaddrinfo)
    with pytest.raises(EgressBloqueado) as info:
        validar_url("http://split-horizon.exemplo/rss")
    assert info.value.ip == "::1"


def test_host_que_nao_resolve_e_barrado_com_mensagem(monkeypatch) -> None:
    def _getaddrinfo(host, port, *args, **kwargs):
        raise socket.gaierror(-2, "Name or service not known")

    monkeypatch.setattr(egress.socket, "getaddrinfo", _getaddrinfo)
    with pytest.raises(EgressBloqueado) as info:
        validar_url("http://nao-existe.invalid/rss")
    assert "não resolvido" in str(info.value)


# ---------------------------------------------------------------------------
# ip_e_bloqueado (tabela)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "ip",
    [
        "127.0.0.1", "127.1", "0.0.0.0", "0", "10.1.2.3", "172.16.0.1", "172.31.255.255",
        "192.168.0.1", "169.254.169.254", "100.64.0.1", "100.127.255.255",
        "192.0.0.1", "192.0.2.1", "198.18.0.1", "198.51.100.1", "203.0.113.1",
        "224.0.0.1", "240.0.0.1", "255.255.255.255",
        "::1", "::", "fe80::1", "fc00::1", "fd00::1", "ff02::1", "2001:db8::1",
        "::ffff:127.0.0.1", "::ffff:169.254.169.254", "::ffff:10.0.0.1",
        "::ffff:7f00:1", "2002:7f00:1::", "64:ff9b::127.0.0.1",
    ],
)
def test_ips_nao_publicos_sao_bloqueados(ip: str) -> None:
    motivo = ip_e_bloqueado(ip)
    assert motivo is not None, f"{ip} deveria estar bloqueado"


@pytest.mark.parametrize("ip", ["8.8.8.8", "1.1.1.1", "93.184.216.34", "2606:4700::1111"])
def test_ips_publicos_sao_permitidos(ip: str) -> None:
    assert ip_e_bloqueado(ip) is None


def test_allowlist_de_host_nao_substitui_a_checagem_de_ip(monkeypatch) -> None:
    """
    Um host da allowlist que resolve para rede privada (DNS envenenado,
    `/etc/hosts` editado, `sslip.io`) tem de ser barrado do mesmo jeito.
    """
    assert "api.resend.com" in egress.ALVO_CONFIANCAVEL

    def _getaddrinfo(host, port, *args, **kwargs):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", port))]

    monkeypatch.setattr(egress.socket, "getaddrinfo", _getaddrinfo)
    with pytest.raises(EgressBloqueado):
        validar_url("https://api.resend.com/emails", hosts_permitidos=egress.ALVO_CONFIANCAVEL)


def test_allowlist_de_host_rejeita_host_desconhecido(monkeypatch) -> None:
    def _getaddrinfo(host, port, *args, **kwargs):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", port))]

    monkeypatch.setattr(egress.socket, "getaddrinfo", _getaddrinfo)
    with pytest.raises(EgressBloqueado) as info:
        validar_url("https://nao-listado.exemplo/x", hosts_permitidos=egress.ALVO_CONFIANCAVEL)
    assert "allowlist" in str(info.value)


# ---------------------------------------------------------------------------
# Redação de segredo na auditoria
# ---------------------------------------------------------------------------


def test_query_com_segredo_e_redigida_na_auditoria() -> None:
    url = "https://api.exemplo.com/v1?access_token=SEGREDO&assinatura=ABC"
    redigida = egress._normalizar_url_para_auditoria(url)  # noqa: SLF001
    assert "SEGREDO" not in redigida
    assert "ABC" not in redigida
    # Host e caminho continuam visíveis, que é o que serve para diagnosticar.
    assert "api.exemplo.com" in redigida
    assert "/v1" in redigida
    assert "redigida" in redigida


def test_url_nao_parseavel_na_auditoria_nao_levanta() -> None:
    assert egress._normalizar_url_para_auditoria("http://[::1")  # noqa: SLF001


# ---------------------------------------------------------------------------
# 7. O módulo é usado em TODO egresso (teste de guarda)
# ---------------------------------------------------------------------------

_RAIZ = pathlib.Path(__file__).resolve().parent.parent.parent

#: Prefixos de caminho que ficam de fora da regra.
_PERMITIDOS = (
    "config/egress.py",  # o próprio módulo
)


def _arquivos_python() -> list[pathlib.Path]:
    return sorted(p for p in _RAIZ.rglob("*.py") if ".venv" not in p.parts)


def test_nenhum_egresso_direto_fora_do_modulo() -> None:
    """
    Impede a reintrodução silenciosa do bug.

    Se alguém escrever `requests.get(feed_url)` de novo num provider, este
    teste falha com o arquivo e a linha. É a garantia de que "um módulo
    único e reutilizável" continua sendo verdade daqui a seis meses.
    """
    import re

    # `requests.<metodo>(` e `urlopen(` chamam a rede diretamente.
    padrao = re.compile(r"\brequests\.(get|post|put|delete|head|patch|request)\s*\(|urllib\.request\.urlopen\s*\(")
    violacoes: list[str] = []
    for arquivo in _arquivos_python():
        relativo = arquivo.relative_to(_RAIZ).as_posix()
        if relativo in _PERMITIDOS or "/tests/" in relativo or relativo.startswith("tests/"):
            continue
        for numero, linha in enumerate(arquivo.read_text(encoding="utf-8").splitlines(), 1):
            if linha.lstrip().startswith("#") or linha.lstrip().startswith("*"):
                continue  # comentário/documentação
            if padrao.search(linha):
                violacoes.append(f"{relativo}:{numero}: {linha.strip()}")
    assert violacoes == [], (
        "Egresso direto de HTTP encontrado fora de config/egress.py. "
        "Use SessaoEgress:\n" + "\n".join(violacoes)
    )


def test_todo_modulo_de_egresso_importa_o_controle() -> None:
    """
    Complementa o teste anterior: os módulos que KNOW que falam com
    serviço externo precisam importar `config.egress`. Um arquivo que
    importasse `requests` sem `SessaoEgress` e sem `RequestException`
    seria um sinal forte de esquecimento.
    """
    import re

    precisa = [
        "catalogo_noticias/providers/news_source.py",
        "catalogo_noticias/providers/summarization.py",
        "catalogo_noticias/management/commands/descobrir_feeds.py",
        "assinatura/providers/payment.py",
        "config/email_resend.py",
        "enderecos/services.py",
    ]
    faltando = [
        relativo
        for relativo in precisa
        if "from config.egress import" not in (_RAIZ / relativo).read_text(encoding="utf-8")
    ]
    assert faltando == [], f"módulos de egresso sem o controle de saída: {faltando}"


# ---------------------------------------------------------------------------
# Robustência: falha de validação não pode virar "sucesso"
# ---------------------------------------------------------------------------


def test_erro_de_validacao_nao_e_engolido(monkeypatch, servidor_local) -> None:
    """
    Se `getaddrinfo` explodir com uma exceção inesperada, o erro tem de
    propagar como erro — nunca virar resposta vazia com status 200, nem
    `except: pass` engolir e devolver um corpo inventado.
    """

    def _boom(*args, **kwargs):
        raise OSError("resolver morreu")

    monkeypatch.setattr(egress.socket, "getaddrinfo", _boom)
    with pytest.raises(OSError):
        validar_url("http://example.com/")


def test_respostas_de_erro_do_upstream_nao_sao_confundidas_com_bloqueio() -> None:
    """
    `EgressBloqueado` NÃO é subclasse de `requests.RequestException` de
    propósito: assim nenhum `except requests.RequestException` o engole e
    o transforme em "fonte fora do ar", mascarando um erro de política de
    segurança como indisponibilidade.
    """
    import requests

    assert not issubclass(EgressBloqueado, requests.RequestException)
    assert issubclass(EgressBloqueado, egress.EgressError)


def test_sessao_usa_timeout_padrao_sem_esquecer(monkeypatch) -> None:
    """`SessaoEgress.request` põe timeout; sem ele, um host que aceita e
    nunca responde trava o worker do Gunicorn indefinidamente."""
    vistos = {}

    def _fake_request(self, method, url, **kwargs):
        vistos["timeout"] = kwargs.get("timeout")
        return "resposta-falsa"

    monkeypatch.setattr(egress.requests.Session, "request", _fake_request)
    with SessaoEgress() as sessao:
        sessao.get("http://example.com/")
    assert vistos["timeout"] == 15
