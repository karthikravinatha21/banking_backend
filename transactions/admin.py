from django.contrib import admin
from django.utils.html import format_html
from django.db.models import Sum
from .models import (
    TransactionCategory, Transaction, Transfer, 
    ScheduledTransaction, TransactionLimit
)


@admin.register(TransactionCategory)
class TransactionCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'description', 'is_active', 'created_at')
    list_filter = ('is_active', 'created_at')
    search_fields = ('name', 'description')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ('reference_number', 'account_number', 'transaction_type', 'amount', 
                   'status', 'created_at')
    list_filter = ('transaction_type', 'status', 'created_at', 'account__currency')
    search_fields = ('reference_number', 'account__account_number', 'description')
    readonly_fields = ('reference_number', 'balance_before', 'balance_after', 'created_at', 'updated_at')
    ordering = ('-created_at',)
    
    def account_number(self, obj):
        return obj.account.account_number
    account_number.short_description = 'Account'
    
    fieldsets = (
        (None, {
            'fields': ('reference_number', 'account', 'transaction_type', 'amount', 'description')
        }),
        ('Balance Info', {
            'fields': ('balance_before', 'balance_after'),
            'classes': ('collapse',)
        }),
        ('Categorization', {
            'fields': ('category',)
        }),
        ('Status', {
            'fields': ('status',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def has_add_permission(self, request):
        return False  # Don't allow manual creation
    
    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser  # Only superusers can edit


@admin.register(Transfer)
class TransferAdmin(admin.ModelAdmin):
    list_display = ('reference_number', 'from_account_number', 'to_account_number', 
                   'amount', 'transfer_type', 'status', 'created_at')
    list_filter = ('transfer_type', 'status', 'created_at')
    search_fields = ('reference_number', 'from_account__account_number', 
                    'to_account__account_number', 'description')
    readonly_fields = ('reference_number', 'created_at', 'updated_at', 'processed_at')
    ordering = ('-created_at',)
    
    def from_account_number(self, obj):
        return obj.from_account.account_number
    from_account_number.short_description = 'From Account'
    
    def to_account_number(self, obj):
        return obj.to_account.account_number if obj.to_account else 'External'
    to_account_number.short_description = 'To Account'
    
    fieldsets = (
        (None, {
            'fields': ('reference_number', 'from_account', 'to_account', 'amount', 'description')
        }),
        ('Transfer Details', {
            'fields': ('transfer_type', 'status', 'fee_amount', 'exchange_rate')
        }),
        ('External Transfer Info', {
            'fields': ('metadata', 'failure_reason'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at', 'processed_at'),
            'classes': ('collapse',)
        }),
    )
    
    def has_add_permission(self, request):
        return False  # Don't allow manual creation


@admin.register(ScheduledTransaction)
class ScheduledTransactionAdmin(admin.ModelAdmin):
    list_display = ('from_account_number', 'to_account_number', 'amount', 
                   'next_execution')
    # list_filter = ('schedule_type', 'is_active', 'created_at')
    search_fields = ('from_account__account_number', 'to_account__account_number', 'description')
    readonly_fields = ('next_execution', 'execution_count', 'created_at', 'updated_at')
    
    def from_account_number(self, obj):
        return obj.from_account.account_number
    from_account_number.short_description = 'From Account'
    
    def to_account_number(self, obj):
        return obj.to_account.account_number
    to_account_number.short_description = 'To Account'
    
    fieldsets = (
        (None, {
            'fields': ('from_account', 'to_account', 'amount', 'description')
        }),
        ('Schedule', {
            'fields': ('schedule_type', 'scheduled_date', 'frequency', 'end_date', 'is_active')
        }),
        ('Execution Info', {
            'fields': ('next_execution', 'last_executed', 'execution_count'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(TransactionLimit)
class TransactionLimitAdmin(admin.ModelAdmin):
    list_display = ('account_number', 'limit_type',
                   'is_active')
    list_filter = ('limit_type', 'is_active', 'created_at')
    search_fields = ('account__account_number',)
    readonly_fields = ('created_at', 'updated_at')
    
    def account_number(self, obj):
        return obj.account.account_number
    account_number.short_description = 'Account'


# Custom admin actions
@admin.action(description='Mark selected transactions as completed')
def mark_completed(modeladmin, request, queryset):
    queryset.update(status='COMPLETED')


@admin.action(description='Mark selected transactions as failed')
def mark_failed(modeladmin, request, queryset):
    queryset.update(status='FAILED')


# Add actions to TransactionAdmin
TransactionAdmin.actions = [mark_completed, mark_failed]
