from rest_framework.permissions import BasePermission


class IsAdmin(BasePermission):
    """Restringe a administração de robôs/ingestão a `papel=admin`.

    Centralizado em vez de checagem manual por método: um método novo que
    esqueça a checagem fica exposto a qualquer usuário autenticado, e a
    view de robôs dispara custo de LLM e tráfego de rede.
    """

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.papel == "admin")
