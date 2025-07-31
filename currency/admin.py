"""
Currency app admin configuration.
"""
from django.contrib import admin
from core.models import Currency, ExchangeRate


# @admin.register(Currency)
class CurrencyAdmin(admin.ModelAdmin):
    """Admin interface for Currency model."""
    
    list_display = ('code', 'name', 'symbol', 'is_active', 'created_at', 'updated_at')
    list_filter = ('is_active', 'created_at')
    search_fields = ('code', 'name')
    ordering = ('code',)
    readonly_fields = ('created_at', 'updated_at')
    
    fieldsets = (
        (None, {
            'fields': ('code', 'name', 'symbol', 'is_active')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


# @admin.register(ExchangeRate)
class ExchangeRateAdmin(admin.ModelAdmin):
    """Admin interface for ExchangeRate model."""
    
    list_display = ('currency_pair', 'rate', 'spread', 'is_active', 'created_at', 'updated_at')
    list_filter = ('is_active', 'from_currency__code', 'to_currency__code', 'created_at')
    search_fields = ('from_currency__code', 'to_currency__code')
    ordering = ('from_currency__code', 'to_currency__code')
    readonly_fields = ('created_at', 'updated_at')
    
    fieldsets = (
        (None, {
            'fields': ('from_currency', 'to_currency', 'rate', 'spread', 'is_active')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def currency_pair(self, obj):
        """Display currency pair as 'FROM -> TO'."""
        return f"{obj.from_currency.code} -> {obj.to_currency.code}"
    currency_pair.short_description = 'Currency Pair'
