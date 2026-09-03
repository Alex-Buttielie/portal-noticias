from typing import Protocol, TypedDict

class Checkout(TypedDict):
    url: str
    session_id: str

class PaymentEvent(TypedDict):
    payment_id: str
    status: str
    plan_id: str
    user_id: str
    amount: int

class PaymentProvider(Protocol):
    def create_checkout(self, plan: dict, user: dict, success_url: str, cancel_url: str) -> Checkout: ...
    def handle_webhook(self, request) -> PaymentEvent: ...
    def refund(self, payment_id: str) -> None: ...
    def get_status(self, payment_id: str) -> str: ...
