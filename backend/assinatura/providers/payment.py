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

from abc import ABC, abstractmethod
from dataclasses import dataclass
from decimal import Decimal


@dataclass
class ResultadoCobranca:
    referencia_gateway: str
    status: str  # "aprovado" | "pendente" | "recusado" — ver HistoricoPagamento.STATUS_CHOICES
    url_checkout: str | None = None


class PaymentGatewayProvider(ABC):
    @abstractmethod
    def criar_cobranca(self, subscription, valor: Decimal) -> ResultadoCobranca:
        """Inicia uma cobrança para a assinatura. `subscription` ainda não tem `gateway_referencia`."""

    @abstractmethod
    def consultar_status(self, referencia_gateway: str) -> str:
        """Consulta o status atual de uma cobrança/assinatura no gateway, por referência opaca."""

    @abstractmethod
    def cancelar(self, referencia_gateway: str) -> None:
        """Cancela a cobrança recorrente no gateway (não afeta o histórico já cobrado)."""


class ManualPaymentGatewayProvider(PaymentGatewayProvider):
    """
    Placeholder: aprova toda cobrança imediatamente, sem chamada de rede.
    Referência gerada localmente (`manual-<contador>`), não vem de nenhum
    provedor real. Uso pretendido: desenvolvimento, testes, e operação
    manual/assistida do admin no lançamento do MVP, até um provedor real
    ser integrado (ver docstring do módulo).
    """

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
    (obrigatório) e `ASSINATURA_MP_SANDBOX` (default True).
    """

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
            resposta = requests.post(
                f"{MP_API_BASE}/preapproval", json=corpo, headers=self._headers(), timeout=20
            )
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

    def consultar_status(self, referencia_gateway: str) -> str:
        import requests

        try:
            resposta = requests.get(
                f"{MP_API_BASE}/preapproval/{referencia_gateway}", headers=self._headers(), timeout=20
            )
        except requests.RequestException as exc:
            raise ProvedorPagamentoError(f"Falha de rede ao consultar preapproval no Mercado Pago: {exc}") from exc
        if resposta.status_code == 404:
            raise ProvedorPagamentoError(f"Preapproval {referencia_gateway} não encontrada no Mercado Pago.")
        if resposta.status_code != 200:
            raise ProvedorPagamentoError(
                f"Mercado Pago respondeu HTTP {resposta.status_code}: {resposta.text[:300]}"
            )
        estado = (resposta.json().get("status") or "").strip().lower()
        if estado == "authorized":
            return "aprovado"
        if estado in ("cancelled", "paused"):
            return "recusado"
        return "pendente"

    def cancelar(self, referencia_gateway: str) -> None:
        import requests

        try:
            resposta = requests.put(
                f"{MP_API_BASE}/preapproval/{referencia_gateway}",
                json={"status": "cancelled"},
                headers=self._headers(),
                timeout=20,
            )
        except requests.RequestException as exc:
            raise ProvedorPagamentoError(f"Falha de rede ao cancelar preapproval no Mercado Pago: {exc}") from exc
        if resposta.status_code not in (200, 201):
            raise ProvedorPagamentoError(
                f"Mercado Pago recusou o cancelamento (HTTP {resposta.status_code}): {resposta.text[:300]}"
            )


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
