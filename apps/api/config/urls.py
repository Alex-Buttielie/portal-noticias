from django.urls import path, include
from django.http import JsonResponse
def health(_): return JsonResponse({"ok": True})
urlpatterns = [path("api/health/", health), path("api/", include("core.urls")), path("api/webhooks/payments/<str:provider>/", include("payments.urls"))]
