from rest_framework.permissions import BasePermission


class IsModeradorOuAdmin(BasePermission):
    """
    Simplificação desta execução (BRD §29 prevê um papel "moderador"
    operacional distinto, ainda não modelado como um papel próprio de
    `identidade.User`): por ora, só `papel=admin` pode moderar. Centralizado
    aqui para trocar facilmente quando um papel de moderador dedicado for
    introduzido, sem precisar caçar checagens espalhadas pelas views.
    """

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.papel == "admin")
