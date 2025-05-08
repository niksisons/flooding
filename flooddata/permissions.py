from rest_framework import permissions

class IsAdminOrReadOnly(permissions.BasePermission):
    """
    Разрешает только чтение для всех пользователей.
    Полный доступ только для администраторов и персонала.
    """
    
    def has_permission(self, request, view):
        # Разрешено чтение для всех
        if request.method in permissions.SAFE_METHODS:
            return True
            
        # Запись только для авторизованных администраторов
        return request.user and request.user.is_authenticated and (
            request.user.is_staff or request.user.is_superuser)