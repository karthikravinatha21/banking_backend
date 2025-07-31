from django.contrib import admin
from .models import Currency, ExchangeRate


@admin.register(Currency)
class CurrencyAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'symbol', 'is_active', 'created_at')
    list_filter = ('is_active', 'created_at')
    search_fields = ('code', 'name')
    readonly_fields = ('created_at', 'updated_at')
    ordering = ('code',)


@admin.register(ExchangeRate)
class ExchangeRateAdmin(admin.ModelAdmin):
    list_display = ('currency_pair', 'rate', 'is_active', 'updated_at')
    list_filter = ('is_active', 'updated_at', 'from_currency__code', 'to_currency__code')
    search_fields = ('from_currency__code', 'to_currency__code')
    readonly_fields = ('created_at', 'updated_at')
    ordering = ('from_currency__code', 'to_currency__code')
    
    def currency_pair(self, obj):
        return f"{obj.from_currency.code}/{obj.to_currency.code}"
    currency_pair.short_description = 'Currency Pair'
    
    fieldsets = (
        (None, {
            'fields': ('from_currency', 'to_currency', 'rate', 'spread')
        }),
        ('Status', {
            'fields': ('is_active',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
