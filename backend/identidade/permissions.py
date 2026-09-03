from rest_framework.permissions import BasePermission


class IsEmailVerified(BasePermission):
    """
    Bloqueia acesso a funcionalidades que exigem identidade confirmada
    (critério de aceite 3 do implementation-contract.md). Retorna 403 com
    mensagem clara em vez de deixar a view falhar de forma genérica.
    """

    message = "É necessário confirmar seu e-mail para acessar este recurso."

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.email_verificado)
