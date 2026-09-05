from rest_framework.exceptions import NotFound
from rest_framework.permissions import BasePermission


class IsAdmin404(BasePermission):
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if getattr(request.user, "papel", None) == "admin":
            return True
        raise NotFound(detail="Not found.")
