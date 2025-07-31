from rest_framework import permissions


class IsOwnerOrAdmin(permissions.BasePermission):
    """
    Custom permission to only allow owners of an object or admin users to access it.
    """
    
    def has_object_permission(self, request, view, obj):
        # Admin users have all permissions
        if request.user.is_staff:
            return True
        
        # Check if the object has a user attribute and if it matches the request user
        if hasattr(obj, 'user'):
            return obj.user == request.user
        
        # Check if the object is the user itself
        if hasattr(obj, 'email'):
            return obj == request.user
        
        return False


class IsAdminUser(permissions.BasePermission):
    """
    Custom permission to only allow admin users.
    """
    
    def has_permission(self, request, view):
        return request.user and request.user.is_staff


class IsOwnerOrReadOnly(permissions.BasePermission):
    """
    Custom permission to only allow owners of an object to edit it.
    Others can only read.
    """
    
    def has_object_permission(self, request, view, obj):
        # Read permissions are allowed for any request,
        # so we'll always allow GET, HEAD or OPTIONS requests.
        if request.method in permissions.SAFE_METHODS:
            return True
        
        # Write permissions are only allowed to the owner of the object
        if hasattr(obj, 'user'):
            return obj.user == request.user
        
        return obj == request.user


class CanViewAccount(permissions.BasePermission):
    """
    Custom permission for account viewing.
    Users can view their own accounts, admins can view all accounts.
    """
    
    def has_object_permission(self, request, view, obj):
        # Admin users can view all accounts
        if request.user.is_staff:
            return True
        
        # Users can view their own accounts
        return obj.user == request.user


class CanPerformTransaction(permissions.BasePermission):
    """
    Custom permission for transaction operations.
    """
    
    def has_permission(self, request, view):
        # User must be authenticated
        if not request.user or not request.user.is_authenticated:
            return False

        # Check if user account is active
        if not request.user.is_active:
            return False
        
        return True
    
    def has_object_permission(self, request, view, obj):
        # Admin users can perform operations on any account
        if request.user.is_staff:
            return True
        
        # Users can perform operations on their own accounts
        if hasattr(obj, 'user'):
            return obj.user == request.user
        
        # For transaction objects, check the account ownership
        if hasattr(obj, 'account'):
            return obj.account.user == request.user
        
        return False


class HasRolePermission(permissions.BasePermission):
    """
    Custom permission based on user roles.
    """
    
    def __init__(self, required_permissions):
        self.required_permissions = required_permissions if isinstance(required_permissions, list) else [required_permissions]
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Admin users have all permissions
        if request.user.is_staff:
            return True
        
        # Check user roles and permissions
        user_permissions = []
        user_roles = request.user.userroleassignment_set.filter(
            is_active=True,
            role__is_active=True
        )
        
        for role_assignment in user_roles:
            user_permissions.extend(role_assignment.role.permissions or [])
        
        # Check if user has any of the required permissions
        return any(permission in user_permissions for permission in self.required_permissions)


class IsAccountOwnerOrAdmin(permissions.BasePermission):
    """
    Permission for account-specific operations.
    """
    
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated
    
    def has_object_permission(self, request, view, obj):
        # Admin users have full access
        if request.user.is_staff:
            return True
        
        # For account objects
        if hasattr(obj, 'user'):
            return obj.user == request.user
        
        # For transaction objects
        if hasattr(obj, 'account'):
            return obj.account.user == request.user
        
        # For transfer objects (check both from and to accounts)
        if hasattr(obj, 'from_account') and hasattr(obj, 'to_account'):
            return (obj.from_account.user == request.user or 
                   obj.to_account.user == request.user)
        
        return False


class CanManageUsers(permissions.BasePermission):
    """
    Permission for user management operations.
    """
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Check if user has user management role
        user_roles = request.user.userroleassignment_set.filter(
            is_active=True,
            role__is_active=True
        )
        
        for role_assignment in user_roles:
            permissions = role_assignment.role.permissions or []
            if 'manage_users' in permissions or request.user.is_staff:
                return True
        
        return False


class CanViewReports(permissions.BasePermission):
    """
    Permission for viewing reports and analytics.
    """
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Admin users can view all reports
        if request.user.is_staff:
            return True
        
        # Check if user has reporting role
        user_roles = request.user.userroleassignment_set.filter(
            is_active=True,
            role__is_active=True
        )
        
        for role_assignment in user_roles:
            permissions = role_assignment.role.permissions or []
            if 'view_reports' in permissions:
                return True
        
        return False


class CanManageRoles(permissions.BasePermission):
    """
    Permission for role management operations.
    """
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Only admin users or users with role management permission
        if request.user.is_staff:
            return True
        
        user_roles = request.user.userroleassignment_set.filter(
            is_active=True,
            role__is_active=True
        )
        
        for role_assignment in user_roles:
            permissions = role_assignment.role.permissions or []
            if 'manage_roles' in permissions:
                return True
        
        return False


def has_permission(user, permission_name):
    """
    Utility function to check if a user has a specific permission.
    """
    if not user or not user.is_authenticated:
        return False
    
    # Admin users have all permissions
    if user.is_staff:
        return True
    
    # Check user roles
    user_roles = user.userroleassignment_set.filter(
        is_active=True,
        role__is_active=True
    )
    
    for role_assignment in user_roles:
        permissions = role_assignment.role.permissions or []
        if permission_name in permissions:
            return True
    
    return False


def get_user_permissions(user):
    """
    Get all permissions for a user.
    """
    if not user or not user.is_authenticated:
        return []
    
    # Admin users have all permissions
    if user.is_staff:
        return ['*']  # Wildcard for all permissions
    
    permissions = set()
    user_roles = user.userroleassignment_set.filter(
        is_active=True,
        role__is_active=True
    )
    
    for role_assignment in user_roles:
        role_permissions = role_assignment.role.permissions or []
        permissions.update(role_permissions)
    
    return list(permissions)
