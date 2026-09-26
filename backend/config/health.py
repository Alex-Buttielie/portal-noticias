"""
Checagens de saúde e prontidão (P0-10, eixo 4).

=============================================================================
O QUE EXISTIA E O QUE ESTAVA ERRADO
=============================================================================
`config/views.py::healthz` (base `origin/develop`) fazia:

    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
    except Exception as exc:
        return JsonResponse({"status": "erro", "detalhe": str(exc)}, status=503)
    return JsonResponse({"status": "ok"})

Dois problemas, ambos de exposição:

1. **VAZAMENTO.** `str(exc)` de um `OperationalError` do psycopg2 contém
   host, porta, nome do banco, NOME DO USUÁRIO e uma fração da mensagem do
   driver. `/healthz` é público (chamado pelo `HEALTHCHECK` do Docker, pelo
   proxy e por monitor externo de uptime) — cada sondagem vaza topologia interna
   para qualquer visitor. Este é o vazamento citado no item de backlog.

2. **SEM SEPARAÇÃO ENTRE "VIVO" E "PRONTO".** Um único endpoint que exige
   banco obriga o orquestrador a MATAR o container quando o Postgres tem um
   pico de latência, em vez de tirar o container de rotação (readiness) e
   esperar (liveness). Também não havia timeout: um `SELECT 1` pendurado
   segura o worker do Gunicorn pelo tempo que o lock de rede permitir.

=============================================================================
O QUE ESTE MÓDULO FAZ
=============================================================================
- Três endpoints com CONTRATOS DIFERENTES: `livez` (o processo responde),
  `readyz` (pode receber tráfego) e `healthz` (resposta genérica e estável
  para monitor externo). Misturá-los é o que produz o falso verde.
- `readyz` faz checagem REAL, com TIMEOUT, de banco e — quando configurado
  — cache e broker. Degrada com HONESTIDADE: o status é derivado das
  checagens, nunca fixo. Um `ok` falso é pior que um 503, porque mantém
  tráfego sendo enviado a um serviço que não funciona.
- As funções de checagem nunca levantam: devolvem um resultado com
  `ok`, `motivo` e `duracao_ms`. Um `except: pass` aqui viraria
  exatamente o falso verde que o item quer evitar.
- Os motivos são redigidos para o endpoint público (categoria, sem
  mensagem do driver) e completos apenas para o endpoint restrito.
- O token de acesso é comparado com `hmac.compare_digest` (tempo
  constante) e, se não estiver configurado, o acesso por token é
  DESABILITADO (fail-closed) em vez de liberado.
"""

from __future__ import annotations

import hmac
import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable

logger = logging.getLogger(__name__)

#: Nomes usados como rótulo das checagens. Estáveis: monitor externo e
#: alerta dependem deles.
CHEIO = "banco"
CACHE = "cache"
BROKER = "broker"


# ---------------------------------------------------------------------------
# Resultado de uma checagem
# ---------------------------------------------------------------------------


@dataclass
class ResultadoChecagem:
    ok: bool
    #: Motivo já redigido para log/endpoint público. NUNCA contém a
    #: mensagem do driver, que carrega host/porta/usuário do banco.
    motivo: str = ""
    #: Categoria estável, para agrupar alerta sem parsear texto.
    categoria: str = "ok"
    duracao_ms: int = 0
    #: Só devolvido no endpoint RESTRITO.
    detalhe: str = ""

    def publica(self) -> dict[str, Any]:
        """Forma para endpoint público/restrito: sem `detalhe` cru."""
        dados = {
            "ok": self.ok,
            "categoria": self.categoria,
            "motivo": self.motivo,
        }
        if self.duracao_ms:
            dados["duracao_ms"] = self.duracao_ms
        return dados

    def publica_com_detalhe(self) -> dict[str, Any]:
        dados = self.publica()
        if self.detalhe:
            dados["detalhe"] = self.detalhe
        return dados


# ---------------------------------------------------------------------------
# Execução com timeout de verdade
# ---------------------------------------------------------------------------


def _com_timeout(funcao: Callable[[], Any], segundos: float) -> tuple[Any, bool]:
    """
    Executa `funcao` com limite de tempo PAREDE-DE-RELÓGIO.

    Por que uma thread e não um timeout do driver: o requisito é que
    `/readyz` responda em tempo limitado mesmo que a dependência esteja
    pendurada (lock de rede que o SO não reporta). Vários backends
    (psycopg2, django-redis) têm timeout próprio, mas não é uniforme, e um
    `SELECT 1` sem `statement_timeout` pode esperar indefinitely.

    IMPLEMENTAÇÃO: `threading.Thread(daemon=True)` crua, e NÃO
    `ThreadPoolExecutor`. A primeira versão usava o executor dentro de um
    `with`, e o `__exit__` chama `shutdown(wait=True)` — que BLOQUEIA
    até a thread travada terminar. Ou seja: o "timeout" voltava assim que
    a checagem pendurada terminasse, exatamente o oposto do que promete.
    O teste `test_com_timeout_retorna_no_prazo` pegou isso (30 s em vez de
    0,3 s).

    `daemon=True` garante que uma checagem realmente travada não impede o
    processo de encerrar no deploy. O custo é uma thread pendurada por
    request; aceito, porque a alternativa (não responder) é pior para o
    orquestrador e o `statement_timeout` do Postgres encurta o caso comum.
    """
    caixa: dict[str, Any] = {}

    def _alvo() -> None:
        try:
            caixa["valor"] = funcao()
        except BaseException as exc:  # noqa: BLE001 — repassado ao chamador abaixo
            caixa["erro"] = exc

    thread = threading.Thread(target=_alvo, name="saude", daemon=True)
    thread.start()
    thread.join(timeout=segundos)
    if thread.is_alive():
        return None, True
    if "erro" in caixa:
        raise caixa["erro"]
    return caixa.get("valor"), False


# ---------------------------------------------------------------------------
# Checagens
# ---------------------------------------------------------------------------


def checar_banco(timeout: float) -> ResultadoChecagem:
    """
    Conectividade real com o banco.

    `SELECT 1` sozinho pode passar em uma conexão ociosa que o pool
    considera viva mas cujo socket morreu; por isso a checagem usa o
    contexto de cursor do Django (que faz `ensure_connection`) e mede o
    tempo.

    Em PostgreSQL, aplica `statement_timeout` na sessão ANTES do comando:
    é o servidor que cancela a query, então uma query travada não segura
    uma conexão do pool além do limite.
    """
    from django.db import connection

    inicio = time.monotonic()

    def _executar() -> None:
        with connection.cursor() as cursor:
            vendor = connection.vendor
            if vendor == "postgresql":
                try:
                    # ms, na sessão. Não usa SET LOCAL porque o Django
                    # abre autocommit por padrão.
                    cursor.execute("SET statement_timeout = %s", [int(timeout * 1000)])
                except Exception:  # noqa: BLE001 — a checagem segue sem o timeout do servidor
                    logger.debug("Não foi possível aplicar statement_timeout na checagem de saúde.")
            cursor.execute("SELECT 1")
            cursor.fetchone()

    try:
        resultado, expirou = _com_timeout(_executar, timeout)
    except Exception as exc:  # noqa: BLE001 — qualquer falha vira resultado, nunca propagação
        duracao = int((time.monotonic() - inicio) * 1000)
        # O nome da exceção é útil; a MENSAGEM não pode vazar.
        return ResultadoChecagem(
            ok=False,
            categoria="indisponivel",
            motivo="banco indisponível",
            duracao_ms=duracao,
            detalhe=f"{exc.__class__.__name__}",
        )
    if expirou:
        return ResultadoChecagem(
            ok=False,
            categoria="timeout",
            motivo=f"banco não respondeu em {timeout:g}s",
            duracao_ms=int((time.monotonic() - inicio) * 1000),
        )
    return ResultadoChecagem(ok=True, duracao_ms=int((time.monotonic() - inicio) * 1000))


def checar_cache(timeout: float) -> ResultadoChecagem | None:
    """
    Cache default. Devolve `None` quando não há cache externo
    configurado (locmem em dev), porque aí não há dependência a checar —
    devolver `ok` para um `LocMemCache` seria um verde de mentira.
    """
    from django.conf import settings

    configuracao = (getattr(settings, "CACHES", {}) or {}).get("default", {})
    backend = str(configuracao.get("BACKEND", ""))
    if "locmem" in backend.lower() or "dummy" in backend.lower():
        return None

    from django.core.cache import cache

    inicio = time.monotonic()
    try:
        resultado, expirou = _com_timeout(lambda: cache.set("__saude__", "1", 10), timeout)
    except Exception as exc:  # noqa: BLE001
        return ResultadoChecagem(
            ok=False,
            categoria="indisponivel",
            motivo="cache indisponível",
            duracao_ms=int((time.monotonic() - inicio) * 1000),
            detalhe=f"{exc.__class__.__name__}",
        )
    if expirou:
        return ResultadoChecagem(
            ok=False,
            categoria="timeout",
            motivo=f"cache não respondeu em {timeout:g}s",
            duracao_ms=int((time.monotonic() - inicio) * 1000),
        )
    return ResultadoChecagem(ok=True, duracao_ms=int((time.monotonic() - inicio) * 1000))


def checar_broker(timeout: float) -> ResultadoChecagem | None:
    """
    Broker do Celery. Devolve `None` quando não há broker externo
    configurado (transporte em memória em dev/teste).

    Só checa ALCANÇABILIDADE (conectar e dar PING), não worker: um broker
    alcançável sem consumidor é um problema de provisionamento, e fazer o
    readiness falhar por isso derrubaria todo o tráfego web por causa de
    uma fila de e-mail.
    """
    from django.conf import settings

    url = str(getattr(settings, "CELERY_BROKER_URL", "") or "")
    if not url or url.startswith(("memory://", "sentinel://")):
        return None

    inicio = time.monotonic()

    def _executar() -> None:
        import redis

        cliente = redis.Redis.from_url(url, socket_timeout=timeout, socket_connect_timeout=timeout)
        try:
            cliente.ping()
        finally:
            cliente.close()

    try:
        _, expirou = _com_timeout(_executar, timeout)
    except ImportError:
        # `redis` não instalado: não dá para afirmar que o broker está ok.
        return ResultadoChecagem(
            ok=False,
            categoria="nao_verificavel",
            motivo="cliente redis ausente; broker não verificável",
            duracao_ms=int((time.monotonic() - inicio) * 1000),
        )
    except Exception as exc:  # noqa: BLE001
        return ResultadoChecagem(
            ok=False,
            categoria="indisponivel",
            motivo="broker indisponível",
            duracao_ms=int((time.monotonic() - inicio) * 1000),
            detalhe=f"{exc.__class__.__name__}",
        )
    if expirou:
        return ResultadoChecagem(
            ok=False,
            categoria="timeout",
            motivo=f"broker não respondeu em {timeout:g}s",
            duracao_ms=int((time.monotonic() - inicio) * 1000),
        )
    return ResultadoChecagem(ok=True, duracao_ms=int((time.monotonic() - inicio) * 1000))


# ---------------------------------------------------------------------------
# Agregação
# ---------------------------------------------------------------------------


@dataclass
class Relatorio:
    ok: bool
    checagens: dict[str, ResultadoChecagem] = field(default_factory=dict)
    #: Dependências que não puderam ser verificadas (ex.: cache locmem em
    #: dev). Não contam como falha, mas ficam VISÍVEIS para que ninguém
    #: confunda "não verificado" com "verificado e ok".
    nao_verificadas: list[str] = field(default_factory=list)

    def por_checagem(self) -> dict[str, dict[str, Any]]:
        return {nome: r.publica() for nome, r in self.checagens.items()}

    def por_checagem_detalhada(self) -> dict[str, dict[str, Any]]:
        return {nome: r.publica_com_detalhe() for nome, r in self.checagens.items()}


def _timeout_padrao() -> float:
    from django.conf import settings

    return float(getattr(settings, "HEALTH_TIMEOUT_SEGUNDOS", 2.0))


def verificar_prontidao(timeout: float | None = None) -> Relatorio:
    """
    Checagem completa de prontidão.

    `ok` é DERIVADO das checagens. Não existe caminho que devolva `ok`
    sem que banco tenha sido verificado com sucesso nesta chamada.
    """
    limite = _timeout_padrao() if timeout is None else timeout
    relatorio = Relatorio(ok=True)
    for nome, funcao in ((CHEIO, checar_banco), (CACHE, checar_cache), (BROKER, checar_broker)):
        try:
            resultado = funcao(limite)
        except Exception as exc:  # noqa: BLE001 — uma checagem que estoura não pode derrubar as outras
            logger.exception("Checagem de saúde '%s' levantou exceção inesperada", nome)
            resultado = ResultadoChecagem(
                ok=False,
                categoria="erro",
                motivo=f"checagem de {nome} falhou",
                detalhe=f"{exc.__class__.__name__}",
            )
        if resultado is None:
            relatorio.nao_verificadas.append(nome)
            continue
        relatorio.checagens[nome] = resultado
        if not resultado.ok:
            relatorio.ok = False
    return relatorio


# ---------------------------------------------------------------------------
# Autorização dos endpoints restritos
# ---------------------------------------------------------------------------


def token_configurado() -> str:
    from django.conf import settings

    return str(getattr(settings, "HEALTH_DETAIL_TOKEN", "") or "")


def token_valido(candidato: str | None) -> bool:
    """
    Compara o token com `hmac.compare_digest` (tempo constante).

    `==` em string vaza informação por tempo: um atacante pode descobrir
    o token byte a byte medindo a latência da resposta. `compare_digest`
    não.

    Sem token configurado, QUALQUER candidato é recusado (fail-closed):
    um deploy que esqueceu de configurar o segredo não pode acabar com
    métricas e detalhe de saúde públicos.
    """
    esperado = token_configurado()
    if not esperado:
        logger.error(
            "HEALTH_DETAIL_TOKEN não configurado: /health-detail e /metrics "
            "ficam acessíveis apenas por sessão de staff."
        )
        return False
    if not candidato:
        return False
    return hmac.compare_digest(str(candidato), esperado)


def eh_staff(request) -> bool:
    """Sessão autenticada de staff. `is_staff` é o portão padrão do Django."""
    usuario = getattr(request, "user", None)
    if usuario is None or not usuario.is_authenticated:
        return False
    return bool(getattr(usuario, "is_staff", False))


def _token_do_cabecalho(request) -> str | None:
    """
    Extrai o token do pedido, aceitando as duas convenções.

    `X-Observability-Token` é o cabeçalho dedicado (preferido: não
    conflita com proxy que injeta `Authorization`). `Authorization:
    Bearer` é aceito porque é o padrão de toolchain de observabilidade
    (Prometheus scrape config, Grafana, curl em script de smoke).
    """
    dedicado = request.headers.get("X-Observability-Token")
    if dedicado:
        return dedicado
    autorizacao = request.headers.get("Authorization") or ""
    if autorizacao[:7].lower() == "bearer ":
        return autorizacao[7:].strip()
    return None


def autorizado_para_detalhe(request) -> bool:
    """Staff autenticado OU token válido. Nunca anônimo."""
    if eh_staff(request):
        return True
    return token_valido(_token_do_cabecalho(request))


# ---------------------------------------------------------------------------
# Métricas (mínimo viável, sem dependência)
# ---------------------------------------------------------------------------


class _Registro:
    """
    Contadores em processo, formato de exposição do Prometheus.

   POR QUE SEM `prometheus_client`? O projeto não tem essa dependência e
    `requirements-lock.txt` está fora de escopo desta tarefa. Um
    registry mínimo em processo é suficiente para o que o item exige
    (métricas restritas, nunca públicas) e não introduz uma dependência de
    runtime. NÃO substitui o Prometheus: em processo, some no restart e não
    agrega entre workers do Gunicorn. Declarado como dívida consciente.
    """

    def __init__(self) -> None:
        import threading

        self._lock = threading.Lock()
        self._contadores: dict[tuple[str, tuple[tuple[str, str], ...]], float] = {}
        self._rotulos: dict[tuple[str, tuple[tuple[str, str], ...]], tuple[str, ...]] = {}
        self._descricoes: dict[str, str] = {}
        self._tempo_inicio = time.monotonic()

    def incrementar(self, nome: str, valor: float = 1.0, **rotulos: str) -> None:
        chave = (nome, tuple(sorted(rotulos.items())))
        with self._lock:
            self._contadores[chave] = self._contadores.get(chave, 0.0) + valor
            self._rotulos[chave] = tuple(sorted(rotulos.keys()))
            self._descricoes.setdefault(nome, nome.replace("_", " ").replace(".", "_"))

    def observar(self, nome: str, valor: float, **rotulos: str) -> None:
        self.incrementar(nome, valor, **rotulos)

    def render(self) -> str:
        linhas = [
            "# HELP portal_tempo_de_atividade_segundos Tempo desde o boot do processo.",
            "# TYPE portal_tempo_de_atividade_segundos gauge",
            f"portal_tempo_de_atividade_segundos {time.monotonic() - self._tempo_inicio:.3f}",
        ]
        with self._lock:
            itens = sorted(self._contadores.items())
        Metricas_por_nome: dict[str, list[tuple[str, tuple[tuple[str, str], ...], float]]] = {}
        for (nome, rotulos), valor in itens:
            Metricas_por_nome.setdefault(nome, []).append((nome, rotulos, valor))
        for nome, linhas_da_metrica in Metricas_por_nome.items():
            tipo = "gauge" if nome.endswith("_ms") or nome.endswith("_segundos") else "counter"
            linhas.append(f"# TYPE {nome} {tipo}")
            for _, rotulos, valor in linhas_da_metrica:
                if rotulos:
                    pares = ",".join(f'{k}="{_escapar(v)}"' for k, v in rotulos)
                    linhas.append(f"{nome}{{{pares}}} {valor:g}")
                else:
                    linhas.append(f"{nome} {valor:g}")
        return "\n".join(linhas) + "\n"


def _escapar(valor: str) -> str:
    return str(valor).replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


#: Registro único do processo.
METRICAS = _Registro()
