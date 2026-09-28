"""
Identidade de cliente para rate limiting (`config/throttling.py`).

O QUE ISTO CONSERTA
-------------------
O throttle anônimo do DRF escolhe o balde pelo resultado de
`SimpleRateThrottle.get_ident`, que — com `REST_FRAMEWORK["NUM_PROXIES"]`
ausente — devolve o `X-Forwarded-For` cru, concatenado sem validação:

    return ''.join(xff.split()) if xff else remote_addr
    (rest_framework/throttling.py:33-40 na base 1dec732)

`X-Forwarded-For` é um cabeçalho que o CLIENTE escolhe. Medido nesta base:
com `REMOTE_ADDR` fixo, 12 valores de XFF distintos produziram 12 baldes
distintos, e o limite de 10/min de `AuthSensivelAnonThrottle` (o limite
anti brute force do login, `config/throttling.py:37-49`) foi "reiniciado"
indefinidamente trocando o cabeçalho. `develop` não lia esse cabeçalho em
nenhum ponto (`grep -rl X_FORWARDED_FOR backend/` → vazio) e o Nginx
(`infra/nginx/portal-{dev,homolog,prod}.conf`) não tinha nenhuma linha
`X-Forwarded-For`, ou seja, repassava verbatim o que o cliente mandou.

POR QUE UM MÓDULO NOVO, E NÃO `NUM_PROXIES`
------------------------------------------
`NUM_PROXIES` não serve, medido:

  * `NUM_PROXIES: 0` → identidade vira `REMOTE_ADDR`, que atrás do Nginx
    local é `127.0.0.1` para TODO o tráfego → todos os anônimos dividem um
    balde → um atacante causa 429 global no login. Troca o furo por um
    self-DoS.
  * `NUM_PROXIES: 1` → `addrs[-1]`, exatamente o elemento que o cliente
    controla (o Nginx não reescreve o cabeçalho) → continua forjável.

A diferença entre "confiar no cabeçalho" e "confiar no proxy que escreveu o
cabeçalho" é o ponto inteiro deste módulo: o cabeçalho só tem valor quando
quem o escreveu é um proxy que o operador declarou confiável. Isso é o que
`NUM_PROXIES` não expressa — ele conta proxies, não decide se o par que
falou é confiável.

CONTRATO
--------
`get_ident(request)` devolve SEMPRE uma string:

  1. Sem conjunto de proxies declarado (`TRUSTED_PROXY_IPS` ausente ou
     vazio) → devolve `REMOTE_ADDR` e ignora o cabeçalho inteiro.
     Fail-CLOSED: não configurado não pode significar "confio em qualquer
     XFF", que é justamente o defeito que este módulo fecha.
  2. `REMOTE_ADDR` fora do conjunto declarado → `REMOTE_ADDR`.
     Quem escreveu o cabeçalho não é ninguém que o operador declarou
     confiável, então o cabeçalho é do cliente, por definição.
  3. Dentro do conjunto → o ÚLTIMO elemento de `X-Forwarded-For` (o mais
     à direita), desde que seja um endereço IP válido; qualquer outro caso
     (ausente, vazio, "lixo", elemento malformado) → `REMOTE_ADDR`.

Todos os caminhos de falha caem em `REMOTE_ADDR`: um cabeçalho malformado
não pode virar uma chave de balde nova, e também não pode derrubar o
tráfego legítimo — ele apenas não é usado.

CONFIGURAÇÃO (o valor é do operador, nunca um default deste arquivo)
--------------------------------------------------------------------
Variável de ambiente `TRUSTED_PROXY_IPS`: lista separada por vírgula de IPs
ou prefixos CIDR de PROXIES CONFIÁVEIS — os que podem falar em nome de um
cliente. Exemplo de forma (não de valor): `TRUSTED_PROXY_IPS=127.0.0.1`
para o caso em que o Nginx roda na mesma máquina, ou os ranges do
balanceador quando existir um na frente.

Ausente/vazia = fail-closed (ignora o cabeçalho). Com o Nginx reescrevendo o
cabeçalho, isso ainda dá a identidade correta de quem está na frente do
Nginx; o que se perde é a distinção entre clientes atrás de um balanceador
não declarado — que é a escolha segura, não um acidente.
"""

from __future__ import annotations

import ipaddress
from functools import lru_cache

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

# Endereços IPv4/IPv6 RFC 5737/3849 — rede de documentação. Nenhum proxy
# real usa estes endereços; servem para os testes exercitarem um par
# cliente/proxy plausível sem depender de nenhum IP de mundo real.
_ENDERECO_VAZIO = ""


@lru_cache(maxsize=None)
def _conjunto_confiados_bruto(bruto: str) -> frozenset:
    """Traduz a lista de texto de `TRUSTED_PROXY_IPS` em objetos de rede.

    `bruto` é a lista separada por vírgula. Elementos que não são IP nem CIDR
    são DESCARTADOS (não levantam): um erro de digitação na configuração não
    pode derrubar o processo no meio do tráfego — o efeito de descartar é
    apenas que aquele endereço não conta como confiável, que é a direção
    segura. Entradas em branco são ignoradas, para que vírgula sobrando não
    vire um item.
    """
    if not bruto:
        return frozenset()
    itens = set()
    for pedaco in bruto.split(","):
        pedaco = pedaco.strip()
        if not pedaco:
            continue
        try:
            itens.add(ipaddress.ip_network(pedaco, strict=False))
        except ValueError:
            # Configuração inválida: este endereço simplesmente não será
            # considerado confiável. Ver a docstring do módulo.
            continue
    return frozenset(itens)


def _conjunto_confiados() -> frozenset:
    """O conjunto de redes confiáveis, como valor de setting do Django.

    Lê de `settings` (e não de `os.environ`) para que `override_settings`
    funcione nos testes. `getattr` com default evita `AttributeError` se um
    projeto que importe este módulo não declarar o setting — nesse caso o
    comportamento é o fail-closed (conjunto vazio).
    """
    return _conjunto_confiados_bruto(getattr(settings, "TRUSTED_PROXY_IPS", _ENDERECO_VAZIO))


def _ip_valido(valor: str):
    """`valor` como endereço IP, ou `None` se não for um IP.

    Existe separado do try/except dos callers porque o DRF também aceita
    IPv6 aqui: o par (`REMOTE_ADDR`, `X-Forwarded-For`) pode ser IPv6 sem
    que isso mude a regra (o elemento tem que ser um endereço, não texto).
    """
    try:
        return ipaddress.ip_address(valor)
    except ValueError:
        return None


def _ip_no_conjunto(valor: str, conjunto: frozenset) -> bool:
    """`valor` (REMOTE_ADDR) pertence a alguma rede declarada confiável."""
    if not valor or not conjunto:
        return False
    endereco = _ip_valido(valor)
    if endereco is None:
        return False
    # `in` numa tupla de redes: `IPv4Address in (IPv4Network, ...)` é o
    # teste de pertinência correto e não levanta para redes de outra
    # família.
    return any(endereco in rede for rede in conjunto)


def _ultimo_elemento_xff(cabecalho: str):
    """O último endereço de uma cadeia `X-Forwarded-For`, ou `None`.

    A cadeia é `cliente, proxy1, proxy2` — o elemento mais à DIREITA é o
    mais próximo de nós e o ÚNICO que o proxy em que confiamos escreveu por
    conta própria. Tomar o da esquerda é tomar o que o cliente escolheu.

    Devolve `None` (em vez de levantar) para: cabeçalho vazio, cadeia só de
    vírgulas/espaços, elemento em branco, ou elemento que não é um IP. O
    caller cai em `REMOTE_ADDR` em todos esses casos.
    """
    if not cabecalho:
        return None
    ultimo = cabecalho.rsplit(",", 1)[-1].strip()
    if not ultimo:
        return None
    return _ip_valido(ultimo)


def _resolver_endereco(valor: str) -> str:
    """Normaliza um endereço para a forma canônica, sem changing de família.

    Usado para que `REMOTE_ADDR` e o XFF comparáveis usem a mesma grafia
    (ex.: IPv6 comprimido das duas formas), e a chave do balde não dependa
    de como o proxy escreveu o endereço.
    """
    endereco = _ip_valido(valor)
    return str(endereco) if endereco is not None else valor


def get_ident(request) -> str:
    """Identidade do balde para uma requisição anônima.

    Ver o contrato na docstring do módulo. Resumo do que volta, em ordem de
    teste:

    1. conjunto vazio (fail-closed)            -> REMOTE_ADDR
    2. REMOTE_ADDR não declarado confiável      -> REMOTE_ADDR
    3. XFF ausente/inválido                     -> REMOTE_ADDR
    4. REMOTE_ADDR declarado + XFF válido       -> último elemento do XFF
    """
    remote_addr = request.META.get("REMOTE_ADDR") or ""

    conjunto = _conjunto_confiados()
    if not conjunto:
        # Fail-closed: sem declaração de proxies, o cabeçalho não é lido.
        return _resolver_endereco(remote_addr)

    if not _ip_no_conjunto(remote_addr, conjunto):
        # Quem está do outro lado não foi declarado confiável: o cabeçalho,
        # se existir, foi escrito por quem não tem autoridade para falar em
        # nome de um cliente.
        return _resolver_endereco(remote_addr)

    candidato = _ultimo_elemento_xff(request.META.get("HTTP_X_FORWARDED_FOR"))
    if candidato is None:
        return _resolver_endereco(remote_addr)

    return _resolver_endereco(str(candidato))


def _falhar_se_configuracao_invalida() -> None:
    """Levanta se `TRUSTED_PROXY_IPS` tiver alguma entrada não interpretável.

    Chamado por um `manage.py check` customizado (ver
    `config/apps.py`): um proxy declarado com erro de digitação não quebra o
    processo, mas TAMBÉM não protege o cabeçalho que ele deveria proteger — o
    efeito é silencioso e na direção perigosa (volta-se ao comportamento de
    `REMOTE_ADDR` para todo o tráfego atrás daquele proxy). Convertido em
    erro de `check`, o operador vê o problema no deploy.
    """
    bruto = getattr(settings, "TRUSTED_PROXY_IPS", _ENDERECO_VAZIO)
    if not bruto:
        return
    invalidos = []
    for pedaco in bruto.split(","):
        pedaco = pedaco.strip()
        if not pedaco:
            continue
        try:
            ipaddress.ip_network(pedaco, strict=False)
        except ValueError:
            invalidos.append(pedaco)
    if invalidos:
        raise ImproperlyConfigured(
            "TRUSTED_PROXY_IPS contém entradas que não são IP nem CIDR: "
            + ", ".join(repr(i) for i in invalidos)
            + " — elas serão DESCARTADAS, e como proxy não declarado não "
            "confia em X-Forwarded-For, todo o tráfego atrás dele volta a ser "
            "limitado pelo IP do proxy (mais restritivo, não menos). Corrija "
            "a configuração."
        )
