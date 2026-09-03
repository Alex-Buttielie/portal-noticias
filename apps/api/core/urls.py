from django.urls import path
from django.http import JsonResponse
def config_view(_):
    from django.conf import settings
    return JsonResponse({"payment_provider": settings.PAYMENT_PROVIDER})
urlpatterns = [path("config/", config_view), path("summarize/", lambda r: JsonResponse({"summary": "mock"}))]
