"""Confiança de proxy: quem é o cliente por trás de um `REMOTE_ADDR`.

Este módulo centraliza a decisão que JÁ era tomada em dois lugares com o mesmo
vocabulário — o gating de `/health-detail`/`/metrics`
(`config/observability_views.py`) e agora o balde do rate limit
(`config/throttling.py`) — para que "quem é confiável" tenha uma única
implementação, fail-closed e testável.

Por que ele existe (achado MAJOR-1 da revisão do backend, run
20260925-1020-observabilidade): o `SimpleRateThrottle.get_ident` do DRF, sem
`NUM_PROXIES` configurado, devolve o header `X-Forwarded-For` **cru** — e os
nginx versionados não definem esse header, então o valor chegava ao Django
intacto. O balde do rate limit era, portanto, escolhido pelo próprio cliente:
40 POSTs contra um teto de 30/min responderam 201 sem um único 429. O emissor
de token de consentimento é um controle de PRIVACIDADE; um teto que o cliente
escolhe não é teto.

Decisões (todas fail-closed):

* `X-Forwarded-For` **não** é lido por padrão. Só é considerado quando o par
  (`REMOTE_ADDR`) é um proxy declarado em
  `OBSERVABILITY_TRUSTED_PROXY_NETWORKS` ou o loopback da própria máquina.
* Mesmo trusting o header, o que vira o balde é **o último elemento** da
  cadeia: quem o proxy confiável **anexou**, nunca o que o cliente alegou. As
  duas configurações usuais do Nginx (`$proxy_add_x_forwarded_for`, que
  anexa, e `$remote_addr`, que sobrescreve) produzem o mesmo último elemento.
* Configuração que não dá para interpretar (rede inválida) é **ignorada**,
  nunca aproximada: o resultado é "não confiável", que é o lado seguro.
* `Host`/`X-Forwarded-Host` nunca entram na decisão — são controlados pelo
  cliente e não dizem nada sobre quem é o cliente.

Dependência de infra que o backend NÃO pode garantir sozinho: o proxy
confiável precisa **reescrever ou anexar** `X-Forwarded-For` com o endereço
real (é o default do Nginx). Um proxy que repassasse o header do cliente sem
tocar nele reabriria o bypass para quem estiver na rede do proxy — por isso o
requisito está escrito aqui e no runbook, e não escondido num default.
"""

from __future__ import annotations

import ipaddress
import logging
import threading

logger = logging.getLogger("config.proxies")

# Valores inválidos já avisados: a lista é lida em requisições e o WARNING
# repetido a cada request viraria flood de log (o sintoma esconderia a causa).
_avisados: set[str] = set()
_avisos_lock = threading.Lock()

# Só o loopback e as redes declaradas são "proxy confiável". Nunca "qualquer
# IP privado": atrás de Docker/Nginx o tráfego público também chega com IP
# privado, e tratá-lo como confiável publicaria o diagnóstico de operação.
_FALLBACK_SEM_CLIENTE = "desconhecido"


def _setting(nome: str, padrao: str = "") -> str:
    try:
        from django.conf import settings
    except Exception:  # noqa: BLE001 - importável sem Django pronto
        return padrao
    try:
        return str(getattr(settings, nome, padrao) or "").strip()
    except Exception:  # noqa: BLE001 - settings meia-montado não derruba o request
        return padrao


def redes_confiaveis() -> tuple:
    """Redes declaradas como proxy confiável (fail-closed: inválido é ignorado)."""

    redes = []
    for bruto in _setting("OBSERVABILITY_TRUSTED_PROXY_NETWORKS").split(","):
        item = bruto.strip()
        if not item:
            continue
        try:
            redes.append(ipaddress.ip_network(item, strict=False))
        except ValueError:
            with _avisos_lock:
                novo = item not in _avisados
                _avisados.add(item)
            if novo:
                logger.warning(
                    "OBSERVABILITY_TRUSTED_PROXY_NETWORKS: valor inválido ignorado (%s)",
                    item[:64],
                )
    return tuple(redes)


def endereco_remoto(request) -> ipaddress._BaseAddress | None:
    """`REMOTE_ADDR` como endereço IP, ou `None` se não for interpretável."""

    bruto = ""
    try:
        bruto = str((getattr(request, "META", None) or {}).get("REMOTE_ADDR") or "").strip()
    except Exception:  # noqa: BLE001
        return None
    try:
        return ipaddress.ip_address(bruto)
    except ValueError:
        return None


def _em_rede_confiavel(endereco) -> bool:
    return any(endereco in rede for rede in redes_confiaveis())


def eh_proxy_confiavel(request) -> bool:
    """True quando quem abriu a conexão é um hop declarado ou o loopback local."""

    endereco = endereco_remoto(request)
    if endereco is None:
        return False
    return bool(endereco.is_loopback or _em_rede_confiavel(endereco))


def identificar_cliente(request) -> str:
    """Identidade do cliente para o balde de rate limit.

    Substitui `SimpleRateThrottle.get_ident` (ver `config/throttling.py`).
    O balde é o endereço do par que realmente falou com o processo; o
    `X-Forwarded-For` só entra — e só o último elemento — quando esse par é um
    proxy declarado/loopback. Cliente que gira o header a cada requisição
    continua caindo no mesmo balde.
    """

    meta = getattr(request, "META", None) or {}
    remoto = str(meta.get("REMOTE_ADDR") or "").strip()
    endereco = endereco_remoto(request)
    if endereco is None:
        # Sem endereço utilizável não há balde por IP: um identificador estável
        # e inútil para o atacante é melhor do que um balde novo por request.
        return remoto or _FALLBACK_SEM_CLIENTE
    if not (endereco.is_loopback or _em_rede_confiavel(endereco)):
        return str(endereco)
    xff = str(meta.get("HTTP_X_FORWARDED_FOR") or "")
    entradas = [parte.strip() for parte in xff.split(",") if parte.strip()]
    if entradas:
        return entradas[-1]
    return str(endereco)


__all__ = [
    "eh_proxy_confiavel",
    "endereco_remoto",
    "identificar_cliente",
    "redes_confiaveis",
]
