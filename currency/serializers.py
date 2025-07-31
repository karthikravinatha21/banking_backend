from rest_framework import serializers
from django.utils import timezone
from decimal import Decimal
# from .models import CurrencyConversion
from core.models import Currency, ExchangeRate
import logging

from currency.models import CurrencyConversion

logger = logging.getLogger(__name__)


class CurrencySerializer(serializers.ModelSerializer):
    class Meta:
        model = Currency
        fields = ('id', 'code', 'name', 'symbol', 'is_active', 'created_at')
        read_only_fields = ('id', 'created_at')


class ExchangeRateSerializer(serializers.ModelSerializer):
    from_currency_code = serializers.CharField(source='from_currency.code', read_only=True)
    to_currency_code = serializers.CharField(source='to_currency.code', read_only=True)
    
    class Meta:
        model = ExchangeRate
        fields = ('id', 'from_currency', 'to_currency', 'from_currency_code', 
                 'to_currency_code', 'rate', 'spread', 'is_active', 'updated_at')
        read_only_fields = ('id', 'updated_at')


class CurrencyConversionSerializer(serializers.ModelSerializer):
    from_currency_code = serializers.CharField(source='from_currency.code', read_only=True)
    to_currency_code = serializers.CharField(source='to_currency.code', read_only=True)
    
    class Meta:
        model = CurrencyConversion
        fields = ('id', 'from_currency', 'to_currency', 'from_currency_code',
                 'to_currency_code', 'amount', 'converted_amount', 'exchange_rate',
                 'spread_applied', 'total_rate', 'created_at')
        read_only_fields = ('id', 'converted_amount', 'exchange_rate', 
                           'spread_applied', 'total_rate', 'created_at')


class ConvertCurrencySerializer(serializers.Serializer):
    from_currency = serializers.CharField(max_length=3)
    to_currency = serializers.CharField(max_length=3)
    amount = serializers.DecimalField(max_digits=15, decimal_places=2, min_value=Decimal('0.01'))
    
    def validate_from_currency(self, value):
        try:
            currency = Currency.objects.get(code=value.upper(), is_active=True)
            self.from_currency_obj = currency
            return value.upper()
        except Currency.DoesNotExist:
            raise serializers.ValidationError(f"Currency {value} not found or inactive")
    
    def validate_to_currency(self, value):
        try:
            currency = Currency.objects.get(code=value.upper(), is_active=True)
            self.to_currency_obj = currency
            return value.upper()
        except Currency.DoesNotExist:
            raise serializers.ValidationError(f"Currency {value} not found or inactive")
    
    def validate(self, attrs):
        from_currency = attrs['from_currency']
        to_currency = attrs['to_currency']
        
        if from_currency == to_currency:
            raise serializers.ValidationError("Cannot convert to the same currency")
        
        # Check if exchange rate exists
        try:
            exchange_rate = ExchangeRate.objects.get(
                from_currency=self.from_currency_obj,
                to_currency=self.to_currency_obj,
                is_active=True
            )
            self.exchange_rate_obj = exchange_rate
        except ExchangeRate.DoesNotExist:
            # Try reverse conversion
            try:
                exchange_rate = ExchangeRate.objects.get(
                    from_currency=self.to_currency_obj,
                    to_currency=self.from_currency_obj,
                    is_active=True
                )
                self.exchange_rate_obj = exchange_rate
                self.reverse_conversion = True
            except ExchangeRate.DoesNotExist:
                raise serializers.ValidationError(
                    f"Exchange rate not available for {from_currency} to {to_currency}"
                )
        else:
            self.reverse_conversion = False
        
        return attrs
    
    def create(self, validated_data):
        from_currency = self.from_currency_obj
        to_currency = self.to_currency_obj
        amount = validated_data['amount']
        exchange_rate_obj = self.exchange_rate_obj
        
        # Calculate conversion
        base_rate = exchange_rate_obj.rate
        spread = exchange_rate_obj.spread or Decimal('0')
        
        if self.reverse_conversion:
            # Convert using reverse rate
            base_rate = Decimal('1') / base_rate
        
        # Apply spread for large transactions (> 10000)
        if amount > Decimal('10000'):
            spread_applied = spread
            total_rate = base_rate * (Decimal('1') - spread)
        else:
            spread_applied = Decimal('0')
            total_rate = base_rate
        
        converted_amount = amount * total_rate
        
        # Create conversion record
        conversion = CurrencyConversion.objects.create(
            from_currency=from_currency,
            to_currency=to_currency,
            amount=amount,
            converted_amount=converted_amount,
            exchange_rate=base_rate,
            spread_applied=spread_applied,
            total_rate=total_rate
        )
        
        logger.info(f"Currency conversion: {amount} {from_currency.code} = {converted_amount} {to_currency.code}")
        
        return conversion


class ExchangeRateUpdateSerializer(serializers.Serializer):
    rates = serializers.DictField(
        child=serializers.DecimalField(max_digits=10, decimal_places=6),
        help_text="Dictionary of currency codes and their rates"
    )
    base_currency = serializers.CharField(max_length=3, default='USD')
    
    def validate_base_currency(self, value):
        try:
            currency = Currency.objects.get(code=value.upper(), is_active=True)
            self.base_currency_obj = currency
            return value.upper()
        except Currency.DoesNotExist:
            raise serializers.ValidationError(f"Base currency {value} not found or inactive")
    
    def validate_rates(self, value):
        validated_rates = {}
        for currency_code, rate in value.items():
            try:
                currency = Currency.objects.get(code=currency_code.upper(), is_active=True)
                validated_rates[currency] = Decimal(str(rate))
            except Currency.DoesNotExist:
                # Skip invalid currencies
                continue
            except (ValueError, TypeError):
                raise serializers.ValidationError(f"Invalid rate for {currency_code}")
        
        if not validated_rates:
            raise serializers.ValidationError("No valid currency rates provided")
        
        return validated_rates
    
    def create(self, validated_data):
        base_currency = self.base_currency_obj
        rates = validated_data['rates']
        
        updated_count = 0
        
        for currency, rate in rates.items():
            exchange_rate, created = ExchangeRate.objects.get_or_create(
                from_currency=base_currency,
                to_currency=currency,
                defaults={
                    'rate': rate,
                    'spread': Decimal('0.01'),  # Default 1% spread
                    'is_active': True
                }
            )
            
            if not created:
                exchange_rate.rate = rate
                exchange_rate.updated_at = timezone.now()
                exchange_rate.save()
            
            updated_count += 1
        
        return {'updated_count': updated_count, 'base_currency': base_currency.code}


class CurrencyTransferSerializer(serializers.Serializer):
    from_account_id = serializers.IntegerField()
    to_account_id = serializers.IntegerField()
    amount = serializers.DecimalField(max_digits=15, decimal_places=2, min_value=Decimal('0.01'))
    description = serializers.CharField(max_length=255, required=False)
    
    def validate(self, attrs):
        from accounts.models import Account
        
        from_account_id = attrs['from_account_id']
        to_account_id = attrs['to_account_id']
        amount = attrs['amount']
        
        # Validate accounts exist and are active
        try:
            from_account = Account.objects.get(id=from_account_id, is_active=True)
            to_account = Account.objects.get(id=to_account_id, is_active=True)
        except Account.DoesNotExist:
            raise serializers.ValidationError("One or both accounts not found or inactive")
        
        # Can't transfer to same account
        if from_account_id == to_account_id:
            raise serializers.ValidationError("Cannot transfer to the same account")
        
        # Check if currencies are different
        if from_account.currency == to_account.currency:
            raise serializers.ValidationError("Use regular transfer for same currency accounts")
        
        # Check sufficient balance
        if from_account.balance < amount:
            raise serializers.ValidationError("Insufficient balance")
        
        # Get exchange rate
        try:
            from_currency = Currency.objects.get(code=from_account.currency, is_active=True)
            to_currency = Currency.objects.get(code=to_account.currency, is_active=True)
        except Currency.DoesNotExist:
            raise serializers.ValidationError("Currency not found")
        
        try:
            exchange_rate = ExchangeRate.objects.get(
                from_currency=from_currency,
                to_currency=to_currency,
                is_active=True
            )
        except ExchangeRate.DoesNotExist:
            # Try reverse conversion
            try:
                exchange_rate = ExchangeRate.objects.get(
                    from_currency=to_currency,
                    to_currency=from_currency,
                    is_active=True
                )
                attrs['reverse_conversion'] = True
            except ExchangeRate.DoesNotExist:
                raise serializers.ValidationError(
                    f"Exchange rate not available for {from_account.currency} to {to_account.currency}"
                )
        else:
            attrs['reverse_conversion'] = False
        
        attrs['from_account'] = from_account
        attrs['to_account'] = to_account
        attrs['from_currency'] = from_currency
        attrs['to_currency'] = to_currency
        attrs['exchange_rate'] = exchange_rate
        
        return attrs
    
    def create(self, validated_data):
        from django.db import transaction
        from transactions.models import Transfer, Transaction
        
        from_account = validated_data['from_account']
        to_account = validated_data['to_account']
        amount = validated_data['amount']
        description = validated_data.get('description', 'Currency Transfer')
        exchange_rate_obj = validated_data['exchange_rate']
        reverse_conversion = validated_data['reverse_conversion']
        
        # Calculate conversion
        base_rate = exchange_rate_obj.rate
        spread = exchange_rate_obj.spread or Decimal('0')
        
        if reverse_conversion:
            base_rate = Decimal('1') / base_rate
        
        # Apply spread for large transactions
        if amount > Decimal('10000'):
            spread_applied = spread
            total_rate = base_rate * (Decimal('1') - spread)
        else:
            spread_applied = Decimal('0')
            total_rate = base_rate
        
        converted_amount = amount * total_rate
        
        with transaction.atomic():
            # Create currency conversion record
            conversion = CurrencyConversion.objects.create(
                from_currency=validated_data['from_currency'],
                to_currency=validated_data['to_currency'],
                amount=amount,
                converted_amount=converted_amount,
                exchange_rate=base_rate,
                spread_applied=spread_applied,
                total_rate=total_rate
            )
            
            # Create transfer record
            transfer = Transfer.objects.create(
                from_account=from_account,
                to_account=to_account,
                amount=amount,
                description=description,
                transfer_type='CURRENCY',
                status='COMPLETED',
                exchange_rate=total_rate,
                metadata={
                    'conversion_id': conversion.id,
                    'original_amount': str(amount),
                    'converted_amount': str(converted_amount),
                    'from_currency': validated_data['from_currency'].code,
                    'to_currency': validated_data['to_currency'].code
                },
                tenant_id=from_account.tenant_id
            )
            
            # Create debit transaction for source account
            Transaction.objects.create(
                account=from_account,
                transaction_type='DEBIT',
                amount=amount,
                description=f"Currency transfer to {to_account.account_number}",
                reference_number=transfer.reference_number,
                balance_before=from_account.balance,
                balance_after=from_account.balance - amount,
                status='COMPLETED',
                tenant_id=from_account.tenant_id
            )
            
            # Create credit transaction for destination account
            Transaction.objects.create(
                account=to_account,
                transaction_type='CREDIT',
                amount=converted_amount,
                description=f"Currency transfer from {from_account.account_number}",
                reference_number=transfer.reference_number,
                balance_before=to_account.balance,
                balance_after=to_account.balance + converted_amount,
                status='COMPLETED',
                tenant_id=to_account.tenant_id
            )
            
            # Update account balances
            from_account.balance -= amount
            to_account.balance += converted_amount
            from_account.save(update_fields=['balance', 'updated_at'])
            to_account.save(update_fields=['balance', 'updated_at'])
            
            logger.info(
                f"Currency transfer completed: {amount} {validated_data['from_currency'].code} "
                f"-> {converted_amount} {validated_data['to_currency'].code}"
            )
            
            return {
                'transfer': transfer,
                'conversion': conversion,
                'converted_amount': converted_amount,
                'exchange_rate': total_rate
            }
