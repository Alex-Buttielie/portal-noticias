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
