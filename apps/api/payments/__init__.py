from django.conf import settings
from .adapters.fake import FakeProvider
def get_provider():
    name = getattr(settings, "PAYMENT_PROVIDER", "fake")
    if name == "fake":
        return FakeProvider()
    try:
        mod = __import__(f"payments.adapters.{name}", fromlist=["Provider"])
        return mod.Provider()
    except Exception:
        return FakeProvider()
