"""
Multi-tenancy utilities for the banking system.
"""
from django.db import models
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from typing import Optional, Any
import threading


# Thread-local storage for current tenant
_thread_local = threading.local()


class TenantContext:
    """Context manager for tenant operations."""
    
    def __init__(self, tenant_id: Optional[str] = None):
        self.tenant_id = tenant_id
        self.previous_tenant_id = None
    
    def __enter__(self):
        self.previous_tenant_id = get_current_tenant_id()
        set_current_tenant_id(self.tenant_id)
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        set_current_tenant_id(self.previous_tenant_id)


def get_current_tenant_id() -> Optional[str]:
    """Get the current tenant ID from thread-local storage."""
    return getattr(_thread_local, 'tenant_id', None)


def set_current_tenant_id(tenant_id: Optional[str]):
    """Set the current tenant ID in thread-local storage."""
    _thread_local.tenant_id = tenant_id


def clear_current_tenant():
    """Clear the current tenant from thread-local storage."""
    if hasattr(_thread_local, 'tenant_id'):
        delattr(_thread_local, 'tenant_id')


class TenantMixin(models.Model):
    """
    Mixin for models that need to be tenant-aware.
    
    This mixin adds a tenant_id field and provides utilities
    for filtering data by tenant.
    """
    
    tenant_id = models.CharField(
        max_length=50,
        db_index=True,
        help_text=_("Tenant identifier for multi-tenancy")
    )
    
    class Meta:
        abstract = True
    
    def save(self, *args, **kwargs):
        """Auto-set tenant_id if not provided."""
        if not self.tenant_id:
            current_tenant = get_current_tenant_id()
            if current_tenant:
                self.tenant_id = current_tenant
            else:
                raise ValidationError(_("No tenant context available"))
        super().save(*args, **kwargs)
    
    def clean(self):
        """Validate tenant_id is set."""
        super().clean()
        if not self.tenant_id:
            raise ValidationError(_("tenant_id is required"))


class TenantQuerySet(models.QuerySet):
    """QuerySet that automatically filters by current tenant."""
    
    def filter_by_tenant(self, tenant_id: Optional[str] = None):
        """Filter queryset by tenant ID."""
        if tenant_id is None:
            tenant_id = get_current_tenant_id()
        
        if tenant_id is None:
            raise ValidationError(_("No tenant context available for filtering"))
        
        return self.filter(tenant_id=tenant_id)
    
    def for_current_tenant(self):
        """Filter queryset for the current tenant."""
        return self.filter_by_tenant()


class TenantManager(models.Manager):
    """Manager that automatically filters by current tenant."""
    
    def get_queryset(self):
        """Return queryset filtered by current tenant if available."""
        queryset = TenantQuerySet(self.model, using=self._db)
        
        # Only auto-filter if we have a current tenant
        current_tenant = get_current_tenant_id()
        if current_tenant and hasattr(self.model, 'tenant_id'):
            return queryset.filter_by_tenant(current_tenant)
        
        return queryset
    
    def all_tenants(self):
        """Return queryset for all tenants (bypass tenant filtering)."""
        return TenantQuerySet(self.model, using=self._db)
    
    def for_tenant(self, tenant_id: str):
        """Return queryset for a specific tenant."""
        return TenantQuerySet(self.model, using=self._db).filter_by_tenant(tenant_id)


class TenantAwareModel(TenantMixin):
    """
    Base model for tenant-aware models.
    
    Automatically includes tenant_id field and uses TenantManager.
    """
    
    objects = TenantManager()
    
    class Meta:
        abstract = True


class TenantMiddleware:
    """
    Middleware to set tenant context based on request.
    
    This middleware extracts tenant information from the request
    and sets it in thread-local storage for use throughout the request.
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        """Process request and set tenant context."""
        # Extract tenant from various sources
        tenant_id = self.extract_tenant_from_request(request)
        
        # Set tenant context
        set_current_tenant_id(tenant_id)
        
        try:
            response = self.get_response(request)
        finally:
            # Clear tenant context after request
            clear_current_tenant()
        
        return response
    
    def extract_tenant_from_request(self, request) -> Optional[str]:
        """
        Extract tenant ID from request.
        
        This can be customized based on your tenant identification strategy:
        - Subdomain (tenant.example.com)
        - Header (X-Tenant-ID)
        - URL path (/tenant/tenant-id/...)
        - User association
        """
        # Method 1: From HTTP header
        tenant_id = request.headers.get('X-Tenant-ID')
        if tenant_id:
            return tenant_id
        
        # Method 2: From subdomain
        host = request.get_host()
        if '.' in host:
            subdomain = host.split('.')[0]
            if subdomain not in ['www', 'api']:  # Exclude common subdomains
                return subdomain
        
        # Method 3: From URL path
        path_parts = request.path.strip('/').split('/')
        if len(path_parts) >= 2 and path_parts[0] == 'tenant':
            return path_parts[1]
        
        # Method 4: From authenticated user
        if hasattr(request, 'user') and request.user.is_authenticated:
            if hasattr(request.user, 'tenant_id'):
                return request.user.tenant_id
            # Or get from user's organization/company
            if hasattr(request.user, 'organization'):
                return request.user.organization.tenant_id
        
        # Default: no tenant (could be admin or public endpoints)
        return None


class TenantUtils:
    """Utility functions for tenant operations."""
    
    @staticmethod
    def create_tenant_schema(tenant_id: str):
        """
        Create database schema for a new tenant.
        
        This is a placeholder for schema-based multi-tenancy.
        In shared database multi-tenancy, this would be a no-op.
        """
        # This would contain logic to:
        # 1. Create a new database schema
        # 2. Run migrations for the new schema
        # 3. Set up initial data
        pass
    
    @staticmethod
    def delete_tenant_data(tenant_id: str, confirm: bool = False):
        """
        Delete all data for a tenant.
        
        Args:
            tenant_id: Tenant to delete data for
            confirm: Safety confirmation
        """
        if not confirm:
            raise ValidationError(_("Confirmation required to delete tenant data"))
        
        # Import here to avoid circular imports
        from django.apps import apps
        
        # Find all models with tenant_id field
        tenant_models = []
        for model in apps.get_models():
            if hasattr(model, 'tenant_id'):
                tenant_models.append(model)
        
        # Delete data for each model
        with TenantContext(tenant_id):
            for model in tenant_models:
                model.objects.filter(tenant_id=tenant_id).delete()
    
    @staticmethod
    def migrate_tenant_data(from_tenant: str, to_tenant: str):
        """
        Migrate data from one tenant to another.
        
        Args:
            from_tenant: Source tenant ID
            to_tenant: Destination tenant ID
        """
        from django.apps import apps
        
        # Find all models with tenant_id field
        for model in apps.get_models():
            if hasattr(model, 'tenant_id'):
                model.objects.filter(tenant_id=from_tenant).update(tenant_id=to_tenant)
    
    @staticmethod
    def get_tenant_stats(tenant_id: str) -> dict:
        """
        Get statistics for a tenant.
        
        Args:
            tenant_id: Tenant ID
            
        Returns:
            dict: Tenant statistics
        """
        from django.apps import apps
        
        stats = {
            'tenant_id': tenant_id,
            'models': {},
            'total_records': 0
        }
        
        with TenantContext(tenant_id):
            for model in apps.get_models():
                if hasattr(model, 'tenant_id'):
                    count = model.objects.filter(tenant_id=tenant_id).count()
                    stats['models'][model._meta.label] = count
                    stats['total_records'] += count
        
        return stats
    
    @staticmethod
    def validate_tenant_access(user, tenant_id: str) -> bool:
        """
        Validate if a user has access to a specific tenant.
        
        Args:
            user: User instance
            tenant_id: Tenant ID to check
            
        Returns:
            bool: True if user has access
        """
        # Admin users can access all tenants
        if user.is_superuser:
            return True
        
        # Check user's tenant membership
        if hasattr(user, 'tenant_id'):
            return user.tenant_id == tenant_id
        
        # Check organization membership
        if hasattr(user, 'organizations'):
            return user.organizations.filter(tenant_id=tenant_id).exists()
        
        return False


def tenant_required(tenant_id: Optional[str] = None):
    """
    Decorator to ensure a tenant context is available.
    
    Args:
        tenant_id: Specific tenant ID to require
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            current_tenant = get_current_tenant_id()
            
            if tenant_id and current_tenant != tenant_id:
                raise ValidationError(f"Tenant {tenant_id} required, got {current_tenant}")
            
            if not current_tenant:
                raise ValidationError("No tenant context available")
            
            return func(*args, **kwargs)
        return wrapper
    return decorator


def with_tenant(tenant_id: str):
    """
    Decorator to execute function with a specific tenant context.
    
    Args:
        tenant_id: Tenant ID to use
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            with TenantContext(tenant_id):
                return func(*args, **kwargs)
        return wrapper
    return decorator


# Example usage for models:
"""
from core.multi_tenancy import TenantAwareModel

class Account(TenantAwareModel):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    account_number = models.CharField(max_length=10, unique=True)
    balance = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    
    class Meta:
        # Ensure tenant_id is included in uniqueness constraints
        unique_together = [('tenant_id', 'account_number')]

# Usage in views:
def get_user_accounts(request):
    # Automatically filtered by current tenant
    accounts = Account.objects.filter(user=request.user)
    return accounts

# Manual tenant operations:
with TenantContext('tenant-123'):
    accounts = Account.objects.all()  # Only accounts for tenant-123
"""
