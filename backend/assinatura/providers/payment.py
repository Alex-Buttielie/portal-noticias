"""
Interface abstrata de gateway de pagamento (ARCHITECTURE.md seção 6:
`PaymentGatewayProvider`) + uma implementação concreta placeholder.

Decisão em aberto (ARCHITECTURE.md seção 8, spec assinatura-premium.md
"Questões em aberto"): o provedor de pagamento REAL (Mercado Pago, Stripe,
Pagar.me/Iugu) ainda não foi escolhido. `ManualPaymentGatewayProvider` NÃO é
uma simulação de nenhum provedor específico — é um placeholder deliberadamente
genérico que aprova cobranças imediatamente, suficiente para exercitar toda a
máquina de estados de `Subscription` e permitir operação manual/assistida
pelo admin antes de uma integração real existir. Trocar por um provedor real
não deve exigir mudar `services.py`/`models.py` — só a classe concreta
injetada (mesmo padrão já usado para `SummarizationProvider`/
`NewsSourceProvider` em `catalogo_noticias`).

A seleção da implementação concreta é feita por ambiente via
`ASSINATURA_PAYMENT_GATEWAY_PROVIDER` (ver `config/settings.py` e
`obter_gateway_pagamento` abaixo) — ideia incorporada do protótipo
`testes-ia` (`PAYMENT_PROVIDER=fake` + `PaymentProvider` plugável):
trocar de gateway é mudar 1 variável de ambiente, sem alterar código
cliente (`services.py` só chama `obter_gateway_pagamento()` quando nenhum
gateway é injetado explicitamente, o que mantém os testes existentes
intactos).
"""

from __future__ import annotations

import hashlib
import hmac
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from config.egress import EgressBloqueado, SessaoEgress

logger = logging.getLogger(__name__)


@dataclass
class ResultadoCobranca:
    referencia_gateway: str
    status: str  # "aprovado" | "pendente" | "recusado" — ver HistoricoPagamento.STATUS_CHOICES
    url_checkout: str | None = None


@dataclass
class CobrancaGateway:
    """
    Estado de uma cobrança/assinatura LIDO NO PROVEDOR (fonte da verdade),
    por referência opaca. Diferente de `ResultadoCobranca` (que é o que
    acabamos de pedir ao provedor), aqui `valor`/`moeda` são o que o
    provedor AFIRMA ter cobrado.

    `valor`/`moeda` são `None` quando o provedor não os relata — daí
    `PaymentGatewayProvider.relata_valor` existir: só um provedor que se
    declara reporter de valor é obrigado a devolver os dois, e é contra
    ESSES dois que a assinatura confere antes de aceitar uma confirmação
    como pagamento. `None` nunca é lido como "bateu": ou o provedor
    relata (e então é conferido) ou a conferência de valor é explicitamente
    inaplicável e isso fica registrado em log — nunca silencioso.
    """

    referencia_gateway: str
    status: str
    valor: Decimal | None = None
    moeda: str | None = None


class PaymentGatewayProvider(ABC):
    #: Moeda da plataforma. Produto de moeda única (o modelo `Plan` não tem
    #: coluna de moeda e nenhuma migration pode ser tocada), então a moeda
    #: esperada é do provedor, não do plano — mas ainda assim é CONFERIDA
    #: contra o que o provedor dice que cobrou (ver
    #: `services._divergencia_de_valor`).
    moeda: str = "BRL"

    #: `True` só para provedores que devolvem `valor`/`moeda` em
    #: `consultar_cobranca`. Um provedor que se declara reporter e devolve
    #: `None` é tratado como resposta suspeita (não como "conferiu e bateu").
    relata_valor: bool = False

    @abstractmethod
    def criar_cobranca(self, subscription, valor: Decimal) -> ResultadoCobranca:
        """Inicia uma cobrança para a assinatura. `subscription` ainda não tem `gateway_referencia`."""

    @abstractmethod
    def consultar_status(self, referencia_gateway: str) -> str:
        """Consulta o status atual de uma cobrança/assinatura no gateway, por referência opaca."""

    @abstractmethod
    def cancelar(self, referencia_gateway: str) -> None:
        """Cancela a cobrança recorrente no gateway (não afeta o histórico já cobrado)."""

    def consultar_cobranca(self, referencia_gateway: str) -> CobrancaGateway:
        """
        Detalhe da cobrança no provedor (status + o que ele afirma ter
        cobrado). O default usa só o `consultar_status` — para os
        provedores que não relatam valor, e que portanto ficam com
        `valor`/`moeda` em `None`. Provedores de dinheiro real
        sobrescrevem.
        """
        return CobrancaGateway(
            referencia_gateway=referencia_gateway,
            status=self.consultar_status(referencia_gateway),
        )


class ManualPaymentGatewayProvider(PaymentGatewayProvider):
    """
    Placeholder: aprova toda cobrança imediatamente, sem chamada de rede.
    Referência gerada localmente (`manual-<contador>`), não vem de nenhum
    provedor real. Uso pretendido: desenvolvimento, testes, e operação
    manual/assistida do admin no lançamento do MVP, até um provedor real
    ser integrado (ver docstring do módulo).
    """

    #: O placeholder não tem API externa: ele "cobra" o valor que o
    #: chamador mandou, sem nunca confirmá-lo a ninguém. Por isso NÃO se
    #: declara `relata_valor` — a conferência de valor contra o provedor é
    #: inaplicável aqui, e fingir que ela existe daria um verde falso para
    #: um gateway que, por construção, não tem o que conferir.
    moeda: str = "BRL"
    relata_valor: bool = False

    def __init__(self):
        self._contador = 0

    def criar_cobranca(self, subscription, valor: Decimal) -> ResultadoCobranca:
        self._contador += 1
        referencia = f"manual-{subscription.pk}-{self._contador}"
        return ResultadoCobranca(referencia_gateway=referencia, status="aprovado")

    def consultar_status(self, referencia_gateway: str) -> str:
        return "aprovado"

    def cancelar(self, referencia_gateway: str) -> None:
        return None


# Nome canônico do placeholder em `ASSINATURA_PAYMENT_GATEWAY_PROVIDER`.
# Provedores reais registram seu próprio nome aqui (ex.: "mercadopago")
# sem mudar `services.py` — só este dicionário cresce.
GATEWAY_MANUAL = "manual"
GATEWAY_MERCADOPAGO = "mercadopago"

_GATEWAYS_SUPORTADOS = (GATEWAY_MANUAL, GATEWAY_MERCADOPAGO)

MP_API_BASE = "https://api.mercadopago.com"


class ProvedorPagamentoError(Exception):
    """Falha de comunicação/configuração com o gateway real (rede, HTTP
    não-2xx, credencial ausente). Não é erro do usuário — quem chama decide
    como reportar (a view de webhook, por ex., loga e responde 200 para o
    Mercado Pago não retentar em loop)."""


def _para_decimal(bruto) -> Decimal | None:
    """
    Converte o valor monetário que o provedor devolveu em `Decimal`, ou
    `None` se não for um número-usável.

    `Decimal(str(bruto))` e não `Decimal(float)`: o MP devolve JSON, e
    `json.loads` já entrega `float` — `Decimal(0.1)` carrega o erro
    binário do float para dentro da comparação de dinheiro. `None` para
    qualquer coisa não numérica (inclusive `""` e `None`) é o que permite
    distinguir "o provedor não informou" de "o provedor informou 0".
    """
    if bruto is None or isinstance(bruto, bool):
        return None
    try:
        return Decimal(str(bruto))
    except (InvalidOperation, ValueError, TypeError):
        return None


def _mapear_status_mp(estado) -> str:
    """
    Estado do acordo no MP -> vocabulário de `HistoricoPagamento`.

    `authorized` é o usuário ter AUTORIZADO o débito (equivale a
    aprovado); `cancelled`/`paused` é o acordo não continuar (recusado);
    qualquer outro estado (incluindo `pending`) fica pendente. Um estado
    desconhecido NÃO vira "aprovado": no máximo, "pendente", que é o
    estado que não muda dinheiro.
    """
    normalizado = str(estado or "").strip().lower()
    if normalizado == "authorized":
        return "aprovado"
    if normalizado in ("cancelled", "paused"):
        return "recusado"
    return "pendente"


class MercadoPagoGatewayProvider(PaymentGatewayProvider):
    """
    Assinaturas recorrentes via Mercado Pago (API `/preapproval`), sem SDK
    externo — só `requests` (já dependência do projeto).

    Fluxo: `criar_cobranca` cria a preapproval e devolve status "pendente" +
    `url_checkout` (`sandbox_init_point` com credencial TEST-); o usuário
    aprova no checkout do MP; o MP avisa via webhook
    (`assinatura/views.WebhookMercadoPagoView`), que confirma/recusa a
    assinatura. `consultar_status`/`cancelar` operam pela preapproval id
    (guardada em `Subscription.gateway_referencia`).

    Configuração via settings (`config/settings.py`): `ASSINATURA_MP_ACCESS_TOKEN`
    (obrigatório) e `ASSINATURA_MP_SANDBOX` (default True). O webhook é
    autenticado por `ASSINATURA_MP_WEBHOOK_SECRET` (ver
    `verificar_assinatura_webhook`).
    """

    #: Este provedor relata o que cobrou: `consultar_cobranca` devolve
    #: `valor` e `moeda`, e a assinatura exige os dois antes de aceitar
    #: uma confirmação como pagamento (ver `services._divergencia_de_valor`).
    moeda: str = "BRL"
    relata_valor: bool = True

    def __init__(self, access_token: str | None = None, sandbox: bool | None = None):
        from django.conf import settings

        token = access_token or getattr(settings, "ASSINATURA_MP_ACCESS_TOKEN", "")
        if not token:
            raise ProvedorPagamentoError(
                "ASSINATURA_MP_ACCESS_TOKEN não configurado. Defina o Access Token "
                "(TEST-... em sandbox) no ambiente."
            )
        self._token = token
        if sandbox is None:
            sandbox = bool(getattr(settings, "ASSINATURA_MP_SANDBOX", True))
        self._sandbox = sandbox

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self._token}", "Content-Type": "application/json"}

    def criar_cobranca(self, subscription, valor: Decimal) -> ResultadoCobranca:
        import requests

        from django.conf import settings

        try:
            meses = max(1, round(int(subscription.plan.duracao_dias) / 30))
        except (TypeError, ValueError):
            meses = 1
        corpo = {
            "reason": f"{subscription.plan.nome} — Portal de Notícias",
            "payer_email": getattr(subscription.user, "email", ""),
            "auto_recurring": {
                "frequency": 1,
                "frequency_type": "months",
                "transaction_amount": float(valor),
                "currency_id": "BRL",
            },
            "back_url": f"{getattr(settings, 'FRONTEND_BASE_URL', 'http://localhost:3000').rstrip('/')}/minha-conta",
        }
        # `meses` documenta a intenção; a recorrência real do MP é mensal e o
        # período contratado é controlado pelo `vencimento` local.
        corpo["auto_recurring"]["repetitions"] = meses
        try:
            with SessaoEgress() as sessao:
                resposta = sessao.post(
                    f"{MP_API_BASE}/preapproval", json=corpo, headers=self._headers(), timeout=20
                )
        except EgressBloqueado as exc:
            raise ProvedorPagamentoError(
                f"Destino do Mercado Pago bloqueado pela política de segurança de saída: {exc}"
            ) from exc
        except requests.RequestException as exc:
            raise ProvedorPagamentoError(f"Falha de rede ao criar preapproval no Mercado Pago: {exc}") from exc
        if resposta.status_code not in (200, 201):
            raise ProvedorPagamentoError(
                f"Mercado Pago recusou a criação da preapproval (HTTP {resposta.status_code}): {resposta.text[:300]}"
            )
        dados = resposta.json()
        referencia = str(dados.get("id") or "")
        if not referencia:
            raise ProvedorPagamentoError("Mercado Pago não devolveu o id da preapproval.")
        url = dados.get("sandbox_init_point" if self._sandbox else "init_point") or dados.get("init_point")
        return ResultadoCobranca(referencia_gateway=referencia, status="pendente", url_checkout=url)

    def _obter_preapproval(self, referencia_gateway: str) -> dict:
        """GET /preapproval/<id> — dados CRU do provedor (fonte da verdade)."""
        import requests

        try:
            with SessaoEgress() as sessao:
                resposta = sessao.get(
                    f"{MP_API_BASE}/preapproval/{referencia_gateway}", headers=self._headers(), timeout=20
                )
        except EgressBloqueado as exc:
            raise ProvedorPagamentoError(
                f"Destino do Mercado Pago bloqueado pela política de segurança de saída: {exc}"
            ) from exc
        except requests.RequestException as exc:
            raise ProvedorPagamentoError(f"Falha de rede ao consultar preapproval no Mercado Pago: {exc}") from exc
        if resposta.status_code == 404:
            raise ProvedorPagamentoError(f"Preapproval {referencia_gateway} não encontrada no Mercado Pago.")
        if resposta.status_code != 200:
            raise ProvedorPagamentoError(
                f"Mercado Pago respondeu HTTP {resposta.status_code}: {resposta.text[:300]}"
            )
        dados = resposta.json()
        return dados if isinstance(dados, dict) else {}

    def consultar_cobranca(self, referencia_gateway: str) -> CobrancaGateway:
        """
        Lê a preapproval no MP e devolve status + o que o MP AFIRMA ter
        cobrado.

        O `status` do MP é o estado do *acordo* (`authorized` = o usuário
        autorizou o débito; `cancelled`/`paused` = não renova mais), não o
        de um pagamento individual — é essa a informação que decide se a
        assinatura pode ser ativada.

        `valor`/`moeda` vêm de `auto_recurring` (a forma canônica do
        `/preapproval`), com fallback para o nível de topo e para a chave
        `recurring` (formato antigo) — para que uma mudança de forma do
        documento no MP vire `None` (e portanto uma divergência registrada
        e um estado que NÃO é aceito), e não um `0` ou um valor herdado do
        plano local, que seria aceitar um pagamento que ninguém conferiu.
        """
        dados = self._obter_preapproval(referencia_gateway)
        auto = dados.get("auto_recurring") if isinstance(dados.get("auto_recurring"), dict) else {}
        recorrente = auto if auto else (dados.get("recurring") or {})
        bruto = recorrente.get("transaction_amount") if recorrente else None
        if bruto is None:
            bruto = dados.get("transaction_amount")
        valor = _para_decimal(bruto)
        moeda = (recorrente.get("currency_id") or dados.get("currency_id") or "") or None
        return CobrancaGateway(
            referencia_gateway=referencia_gateway,
            status=_mapear_status_mp(dados.get("status")),
            valor=valor,
            moeda=str(moeda).strip().upper() if moeda else None,
        )

    def consultar_status(self, referencia_gateway: str) -> str:
        return self.consultar_cobranca(referencia_gateway).status

    def cancelar(self, referencia_gateway: str) -> None:
        import requests

        try:
            with SessaoEgress() as sessao:
                resposta = sessao.put(
                    f"{MP_API_BASE}/preapproval/{referencia_gateway}",
                    json={"status": "cancelled"},
                    headers=self._headers(),
                    timeout=20,
                )
        except EgressBloqueado as exc:
            raise ProvedorPagamentoError(
                f"Destino do Mercado Pago bloqueado pela política de segurança de saída: {exc}"
            ) from exc
        except requests.RequestException as exc:
            raise ProvedorPagamentoError(f"Falha de rede ao cancelar preapproval no Mercado Pago: {exc}") from exc
        if resposta.status_code not in (200, 201):
            raise ProvedorPagamentoError(
                f"Mercado Pago recusou o cancelamento (HTTP {resposta.status_code}): {resposta.text[:300]}"
            )


# ======================================================================
# Autenticação da origem do webhook
# ======================================================================
# O endpoint `/api/assinatura/webhook/mercadopago/` é público por
# natureza (o MP não tem token de usuário) e, sem verificação de
# assinatura, é uma surface de escrita de estado financeiro aberta a
# qualquer um que descubra a URL. A defesa é o esquema oficial do MP:
# o provedor envia `x-signature: ts=<unix>,v1=<md5>` e `x-request-id`, e
# `v1` é o MD5 do SHA-256 do manifesto montado com o SEGREDO do webhook
# (o mesmo secret do painel do MP), o que torna a requisição
# impreproduzível para quem não tem o segredo.

#: Nome do header de assinatura no `HttpRequest`/`META` do Django.
HEADER_ASSINATURA = "HTTP_X_SIGNATURE"
HEADER_REQUEST_ID = "HTTP_X_REQUEST_ID"

#: Tolerância de relógio para o `ts` do manifesto. O `ts` do MP é o
#: momento de EMISSÃO; sem esta janela, um webhook capturado (uma
#: requisição válida gravada em log/proxy) seria aceito para sempre
#: depois — replay. 5 min é a janela recomendada pelo MP e é folgada o
#: bastante para relógio dessincronizado entre containers.
TOLERANCIA_REPLAY_SEGUNDOS = 300


@dataclass
class VerificacaoAssinatura:
    """
    Resultado da verificação da origem. `ok=False` significa "NÃO
    processe nada" — nenhum estado, nenhuma chamada ao provedor. `motivo`
    é um rótulo curto e SEM valor de segredo: ele vai para o log e nunca
    carrega o `v1` recebido nem o segredo, só o porque da recusa.
    """

    ok: bool
    motivo: str = ""


def _parse_header_assinatura(cabecalho: str) -> dict:
    """
    `"ts=1704908011,v1=abc..."` -> `{"ts": "1704908011", "v1": "abc..."}`.
    Ignora pares vazios/desconhecidos em vez de levantar: um header
    malformado é uma requisição INVÁLIDA, e o caminho de recusa é o mesmo
    de uma assinatura que não bate (comparar e recusar), não uma exceção.
    """
    partes: dict = {}
    for pedaco in str(cabecalho or "").split(","):
        chave, _, valor = pedaco.partition("=")
        chave = chave.strip().lower()
        if chave and valor:
            partes[chave] = valor.strip()
    return partes


def manifesto_webhook(referencia: str, request_id: str = "", ts: str = "") -> str:
    """
    Manifesto canônico do MP, montado na ordem documentada e com `;` ao
    final de cada par. Componentes vazios são OMITIDOS (o MP documenta
    exatamente isso: sem `x-request-id` o manifesto é `id:X;ts:Y;`).
    """
    pares = []
    if referencia:
        pares.append(f"id:{referencia}")
    if request_id:
        pares.append(f"request-id:{request_id}")
    if ts:
        pares.append(f"ts:{ts}")
    return "".join(f"{par};" for par in pares)


def _segredo_webhook() -> str:
    from django.conf import settings

    return str(getattr(settings, "ASSINATURA_MP_WEBHOOK_SECRET", "") or "")


def verificar_assinatura_webhook(
    *,
    referencia: str,
    cabecalho_assinatura: str,
    request_id: str = "",
    segredo: str | None = None,
    agora: float | None = None,
) -> VerificacaoAssinatura:
    """
    Autentica que a requisição veio do Mercado Pago.

    Esquema do MP: `v1 == md5( sha256_hex(manifesto) + segredo )`, tudo em
    minúsculas, comparado com `hmac.compare_digest` (comparar com `==`
    vaza o valor byte a byte pelo tempo de resposta).

    Três recusas, todas "não processe nada":

    1. **Segredo ausente** — fail-closed, e LÓDICO. Um deploy que
       esqueceu o segredo não pode acabar aceitando webhook de
       qualquer um; e também não pode simplesmente ligar o webhook
       (o usuário pagaria e nada seria confirmado). Registra ERROR e
       devolve `ok=False`. Segredo nunca aparece na mensagem.
    2. **Header ausente/malformado** — quem não tem o segredo não
       consegue produzi-lo; é o caso de qualquer requisição forjada.
    3. **`ts` fora da janela de replay** — assinatura válida mas velha:
       é um replay, e replay de um evento de pagamento é exatamente o
       que a assinatura por si só não impede.
    """
    segredo_efetivo = _segredo_webhook() if segredo is None else str(segredo or "")
    if not segredo_efetivo:
        logger.error(
            "Webhook do Mercado Pago: ASSINATURA_MP_WEBHOOK_SECRET não "
            "configurado — TODAS as notificações serão recusadas e nenhuma "
            "assinatura será confirmada por webhook até o segredo ser "
            "definido. Defina o mesmo secret cadastrado no painel do MP "
            "(https://www.mercadopago.com.br/developers/pt_BR/manage-your-account/webhooks)."
        )
        return VerificacaoAssinatura(False, "segredo_nao_configurado")

    partes = _parse_header_assinatura(cabecalho_assinatura)
    v1 = partes.get("v1", "")
    ts = partes.get("ts", "")
    if not v1 or not ts:
        return VerificacaoAssinatura(False, "header_de_assinatura_ausente_ou_malformado")

    if not ts.isdigit():
        return VerificacaoAssinatura(False, "timestamp_de_assinatura_invalido")

    if agora is None:
        import time

        agora = time.time()
    # Janela simétrica (±): o `ts` pode estar levemente no futuro se os
    # relógios divergirem, e recusar por isso seria perder pagamento.
    if abs(float(agora) - int(ts)) > TOLERANCIA_REPLAY_SEGUNDOS:
        return VerificacaoAssinatura(False, "assinatura_fora_da_janela_de_replay")

    manifesto = manifesto_webhook(referencia, request_id, ts)
    digest = hashlib.sha256(manifesto.encode("utf-8")).hexdigest()
    esperado = hashlib.md5((digest + segredo_efetivo).encode("utf-8")).hexdigest()
    if not hmac.compare_digest(esperado, v1.strip().lower()):
        return VerificacaoAssinatura(False, "assinatura_nao_confere")
    return VerificacaoAssinatura(True)


def assinar_cabecalho_webhook(
    referencia: str, segredo: str, request_id: str = "", ts: str | None = None
) -> str:
    """
    Monta o valor de `x-signature` que o MP enviaria. Existe para os
    TESTES construírem um webhook genuíno (é a mesma conta que o
    provedor faz) e para documentar o esquema executável — em produção
    quem produz o header é o MP, nunca este código.

    Não é um atalho para `verificar_assinatura_webhook`: o valor é
    recalculado do zero, como o provedor faz, de modo que um teste que
    usa esta função prova a verificação contra o esquema, e não contra
    uma função que partilha o mesmo bug.
    """
    if ts is None:
        import time

        ts = str(int(time.time()))
    digest = hashlib.sha256(manifesto_webhook(referencia, request_id, ts).encode("utf-8")).hexdigest()
    v1 = hashlib.md5((digest + segredo).encode("utf-8")).hexdigest()
    return f"ts={ts},v1={v1}"


def obter_gateway_pagamento(nome: str | None = None) -> PaymentGatewayProvider:
    """
    Fábrica do gateway de pagamento a partir do nome configurado no ambiente.

    `nome=None` (default) lê `settings.ASSINATURA_PAYMENT_GATEWAY_PROVIDER`
    (default `"manual"`); passar um nome explícito tem prioridade sobre o
    settings — útil em testes e scripts. Nome desconhecido levanta
    `ValueError` em vez de cair silenciosamente para o manual, para erro de
    digitação em `.env.production` falhar alto no boot em vez de cobrar
    errado em produção.
    """
    if nome is None:
        from django.conf import settings

        nome = getattr(settings, "ASSINATURA_PAYMENT_GATEWAY_PROVIDER", GATEWAY_MANUAL) or GATEWAY_MANUAL
    normalizado = str(nome).strip().lower() or GATEWAY_MANUAL
    if normalizado == GATEWAY_MANUAL:
        return ManualPaymentGatewayProvider()
    if normalizado == GATEWAY_MERCADOPAGO:
        return MercadoPagoGatewayProvider()
    raise ValueError(
        f"Provedor de pagamento desconhecido: {nome!r}. "
        f"Suportados: {', '.join(_GATEWAYS_SUPORTADOS)}."
    )
