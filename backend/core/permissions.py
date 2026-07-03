# core/permissions.py
from rest_framework.permissions import BasePermission

class IsSuperUser(BasePermission):
    """
    يسمح بالوصول فقط للمشرفين العامين (Superusers)
    """
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_superuser)