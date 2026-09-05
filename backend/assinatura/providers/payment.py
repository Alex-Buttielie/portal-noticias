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
# Provedores reais futuros registram seu próprio nome aqui (ex.: "mercadopago",
# "stripe") sem mudar `services.py` — só este dicionário cresce.
GATEWAY_MANUAL = "manual"

_GATEWAYS_SUPORTADOS = (GATEWAY_MANUAL,)


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
    raise ValueError(
        f"Provedor de pagamento desconhecido: {nome!r}. "
        f"Suportados: {', '.join(_GATEWAYS_SUPORTADOS)}."
    )
