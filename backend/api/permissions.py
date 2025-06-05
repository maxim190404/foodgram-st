from rest_framework import permissions
from rest_framework.exceptions import PermissionDenied


class IsAuthorOrReadOnly(permissions.BasePermission):
    def has_permission(self, request, view):
        return True

    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        if not request.user.is_authenticated:
            return False
        if obj.author == request.user:
            return True
        raise PermissionDenied(
            detail='У вас недостаточно прав для выполнения данного действия.'
        )
