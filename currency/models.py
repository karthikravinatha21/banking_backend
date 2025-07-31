from django.core.validators import MinValueValidator
from django.db import models

# Create your models here.
from django.db import models
from decimal import Decimal

from core.models import Currency


class CurrencyConversion(models.Model):
    from_currency = models.ForeignKey(Currency, on_delete=models.CASCADE, related_name='currency_conversion_from')
    to_currency = models.ForeignKey(Currency, on_delete=models.CASCADE, related_name='currency_conversion_to')
    amount = models.DecimalField(max_digits=15, decimal_places=2, validators=[MinValueValidator(Decimal('0.01'))])
    converted_amount = models.DecimalField(max_digits=15, decimal_places=2, validators=[MinValueValidator(Decimal('0.01'))])
    exchange_rate = models.DecimalField(max_digits=18, decimal_places=8)  # Base rate of the currency conversion
    spread_applied = models.DecimalField(max_digits=10, decimal_places=4)  # Spread in the exchange rate
    total_rate = models.DecimalField(max_digits=18, decimal_places=8)  # Final rate after applying spread

    created_at = models.DateTimeField(auto_now_add=True)  # Automatically set when the object is created
    updated_at = models.DateTimeField(auto_now=True)  # Automatically set when the object is updated

    class Meta:
        verbose_name = 'Currency Conversion'
        verbose_name_plural = 'Currency Conversions'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.amount} {self.from_currency} to {self.to_currency} at rate {self.exchange_rate}"
