from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.html import format_html
from .models import (
    User, Account, UserRole, UserRoleAssignment, 
    AccountHold, LoginAttempt
)


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ('email', 'first_name', 'last_name', 'is_active', 'is_staff', 'date_joined')
    list_filter = ('is_active', 'is_staff', 'is_superuser', 'date_joined')
    search_fields = ('email', 'first_name', 'last_name', 'phone_number')
    ordering = ('-date_joined',)
    
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Personal info', {'fields': ('first_name', 'last_name', 'phone_number', 'timezone')}),
        ('Permissions', {
            'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions'),
        }),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
        ('2FA', {'fields': ('otp_code', 'otp_created_at')}),
    )
    
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'password1', 'password2'),
        }),
    )
    
    readonly_fields = ('date_joined', 'last_login')


@admin.register(Account)
class AccountAdmin(admin.ModelAdmin):
    list_display = ('account_number', 'user_email', 'account_type', 'balance', 'currency',  'created_at')
    list_filter = ('account_type', 'currency', 'created_at')
    search_fields = ('account_number', 'user__email', 'user__first_name', 'user__last_name')
    readonly_fields = ('account_number', 'created_at', 'updated_at')
    ordering = ('-created_at',)
    
    def user_email(self, obj):
        return obj.user.email
    user_email.short_description = 'User Email'
    
    fieldsets = (
        (None, {
            'fields': ('account_number', 'user', 'account_type', 'currency')
        }),
        ('Balance', {
            'fields': ('balance',)
        }),
        ('Status', {
            'fields': ('is_active',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(UserRole)
class UserRoleAdmin(admin.ModelAdmin):
    list_display = ('name', 'description', 'is_active', 'created_at')
    list_filter = ('is_active', 'created_at')
    search_fields = ('name', 'description')
    readonly_fields = ('created_at', 'updated_at')
    
    fieldsets = (
        (None, {
            'fields': ('name', 'description', 'permissions', 'is_active')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(UserRoleAssignment)
class UserRoleAssignmentAdmin(admin.ModelAdmin):
    list_display = ('user_email', 'role_name', 'assigned_by_email', 'is_active')
    # list_filter = ('role__name', 'is_active', 'assigned_at')
    search_fields = ('user__email', 'role__name', 'assigned_by__email')
    # readonly_fields = ('assigned_at',)
    
    def user_email(self, obj):
        return obj.user.email
    user_email.short_description = 'User'
    
    def role_name(self, obj):
        return obj.role.name
    role_name.short_description = 'Role'
    
    def assigned_by_email(self, obj):
        return obj.assigned_by.email if obj.assigned_by else 'System'
    assigned_by_email.short_description = 'Assigned By'


@admin.register(AccountHold)
class AccountHoldAdmin(admin.ModelAdmin):
    list_display = ('account_number', 'amount', 'reason', 'hold_type', 'expires_at', 'is_active', 'created_at')
    list_filter = ('hold_type', 'is_active', 'created_at', 'expires_at')
    search_fields = ('account__account_number', 'reason')
    readonly_fields = ('created_at', 'updated_at')
    
    def account_number(self, obj):
        return obj.account.account_number
    account_number.short_description = 'Account'


@admin.register(LoginAttempt)
class LoginAttemptAdmin(admin.ModelAdmin):
    list_display = ('user_email', 'ip_address', 'user_agent_short')
    # list_filter = ('success', 'timestamp')
    search_fields = ('user__email', 'ip_address')
    # readonly_fields = ('timestamp',)
    # ordering = ('-timestamp',)
    
    def user_email(self, obj):
        return obj.user.email if obj.user else 'Unknown'
    user_email.short_description = 'User'
    
    def user_agent_short(self, obj):
        if obj.user_agent:
            return obj.user_agent[:50] + '...' if len(obj.user_agent) > 50 else obj.user_agent
        return 'Unknown'
    user_agent_short.short_description = 'User Agent'
    
    def has_add_permission(self, request):
        return False  # Don't allow manual creation
    
    def has_change_permission(self, request, obj=None):
        return False  # Don't allow editing
