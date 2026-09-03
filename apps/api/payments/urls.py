from django.urls import path
from django.http import JsonResponse
from . import get_provider
def webhook(request, provider):
    ev = get_provider().handle_webhook(request)
    return JsonResponse(ev)
urlpatterns = [path("", webhook)]
