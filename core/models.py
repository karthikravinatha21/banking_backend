"""
Core models for the banking system.
"""

from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.validators import RegexValidator
import uuid
from decimal import Decimal


class TimeStampedModel(models.Model):
    """
    Abstract base class with timestamp fields.
    """
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Currency(TimeStampedModel):
    """
    Currency model for multi-currency support.
    """
    code = models.CharField(max_length=3, unique=True, help_text="ISO 4217 currency code")
    name = models.CharField(max_length=100)
    symbol = models.CharField(max_length=10)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name_plural = "currencies"
        ordering = ['code']

    def __str__(self):
        return f"{self.code} - {self.name}"

    def save(self, *args, **kwargs):
        cache.delete('currency_list')
        super().save(*args, **kwargs)


class ExchangeRate(TimeStampedModel):
    """
    Exchange rate model for currency conversion.
    """
    from_currency = models.ForeignKey(Currency, on_delete=models.CASCADE, related_name='from_rates')
    to_currency = models.ForeignKey(Currency, on_delete=models.CASCADE, related_name='to_rates')
    rate = models.DecimalField(max_digits=18, decimal_places=8)
    spread = models.DecimalField(max_digits=5, decimal_places=4, default=Decimal('0.01'))  # Add spread field
    date = models.DateField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ['from_currency', 'to_currency', 'date']
        ordering = ['-date']

    def __str__(self):
        return f"{self.from_currency.code}/{self.to_currency.code}: {self.rate}"
