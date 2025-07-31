import uuid

from rest_framework import serializers
from django.db import transaction
from django.db import models
from django.utils import timezone
from decimal import Decimal

from core.constants import ACCOUNT_ACTIVE_STATUS
from core.models import Currency
from .models import Transaction, Transfer, TransactionCategory, ScheduledTransaction, TransactionLimit
from accounts.models import Account
import logging

logger = logging.getLogger(__name__)


class TransactionCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = TransactionCategory
        fields = ('id', 'name', 'description', 'is_active', 'created_at')
        read_only_fields = ('id', 'created_at')


class TransactionSerializer(serializers.ModelSerializer):
    account_number = serializers.CharField(source='account.account_number', read_only=True)
    category_name = serializers.CharField(source='category.name', read_only=True)

    class Meta:
        model = Transaction
        fields = ('id', 'account', 'account_number', 'transaction_type', 'amount',
                  'description', 'reference_number', 'category', 'category_name',
                  'balance_before', 'balance_after', 'status', 'created_at', 'updated_at')
        read_only_fields = ('id', 'reference_number', 'balance_before', 'balance_after',
                            'created_at', 'updated_at')


class DepositSerializer(serializers.Serializer):
    account_id = serializers.UUIDField()
    amount = serializers.DecimalField(max_digits=15, decimal_places=2, min_value=Decimal('0.01'))
    description = serializers.CharField(max_length=255, required=False)
    category_id = serializers.IntegerField(required=False)

    def validate_account_id(self, value):
        try:
            account = Account.objects.get(id=value, status='active')
            self.account = account
            return value
        except Account.DoesNotExist:
            raise serializers.ValidationError("Account not found or inactive")

    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError("Amount must be greater than zero")
        if value > Decimal('1000000'):
            raise serializers.ValidationError("Amount exceeds maximum limit")
        return value

    def create(self, validated_data):
        account = self.account
        amount = validated_data['amount']
        description = validated_data.get('description', 'Deposit')
        category_id = validated_data.get('category_id')

        category = None
        if category_id:
            try:
                category = TransactionCategory.objects.get(id=category_id, is_active=True)
            except TransactionCategory.DoesNotExist:
                pass

        with transaction.atomic():
            # Create transaction record
            try:
                currency = Currency.objects.get(code='USD')  # Assuming 'code' is the field storing currency codes
            except Exception as ex:
                raise ValueError("Currency 'USD' does not exist.")
            txn = Transaction.objects.create(
                account=account,
                user=account.user,
                transaction_type='deposit',
                amount=amount,
                description=description,
                category=category,
                balance_before=account.balance,
                balance_after=account.balance + amount,
                status='completed',
                currency=currency,
                reference_number=uuid.uuid1()
                # tenant_id=account.tenant_id
            )

            # Update account balance
            account.balance += amount
            account.save(update_fields=['balance', 'updated_at'])

            logger.info(f"Deposit of {amount} completed for account {account.account_number}")
            return txn


class WithdrawSerializer(serializers.Serializer):
    account_id = serializers.UUIDField()
    amount = serializers.DecimalField(max_digits=15, decimal_places=2, min_value=Decimal('0.01'))
    description = serializers.CharField(max_length=255, required=False)
    category_id = serializers.IntegerField(required=False)

    def validate_account_id(self, value):
        try:
            account = Account.objects.get(id=value, status='active')
            self.account = account
            return value
        except Account.DoesNotExist:
            raise serializers.ValidationError("Account not found or inactive")

    def validate(self, attrs):
        account = self.account
        amount = attrs['amount']

        # Check sufficient balance
        if account.balance < amount:
            raise serializers.ValidationError("Insufficient balance")

        # Check daily withdrawal limits
        from datetime import date
        today_withdrawals = Transaction.objects.filter(
            account=account,
            transaction_type='DEBIT',
            created_at__date=date.today(),
            status='COMPLETED'
        ).aggregate(total=models.Sum('amount'))['total'] or Decimal('0')

        daily_limit = Decimal('10000')  # Default daily limit
        if today_withdrawals + amount > daily_limit:
            raise serializers.ValidationError("Daily withdrawal limit exceeded")

        return attrs

    def create(self, validated_data):
        account = self.account
        amount = validated_data['amount']
        description = validated_data.get('description', 'Withdrawal')
        category_id = validated_data.get('category_id')

        category = None
        if category_id:
            try:
                category = TransactionCategory.objects.get(id=category_id, is_active=True)
            except TransactionCategory.DoesNotExist:
                pass

        with transaction.atomic():
            try:
                currency = Currency.objects.get(code='USD')  # Assuming 'code' is the field storing currency codes
            except Exception as ex:
                raise ValueError("Currency 'USD' does not exist.")
            # Create transaction record
            txn = Transaction.objects.create(
                account=account,
                user=account.user,
                transaction_type='withdrawal',
                amount=amount,
                description=description,
                category=category,
                balance_before=account.balance,
                balance_after=account.balance - amount,
                status='completed',
                currency=currency
            )

            # Update account balance
            account.balance -= amount
            account.save(update_fields=['balance', 'updated_at'])

            logger.info(f"Withdrawal of {amount} completed for account {account.account_number}")
            return txn


class TransferSerializer(serializers.ModelSerializer):
    from_account_number = serializers.CharField(source='from_account.account_number', read_only=True)
    to_account_number = serializers.CharField(source='to_account.account_number', read_only=True)

    class Meta:
        model = Transfer
        fields = ('id', 'from_account', 'to_account', 'from_account_number',
                  'to_account_number', 'amount', 'description', 'reference_number',
                  'status', 'transfer_type', 'transfer_fee', 'exchange_rate',
                  'created_at', 'updated_at')
        read_only_fields = ('id', 'reference_number', 'transfer_fee', 'exchange_rate',
                            'created_at', 'updated_at')


class InternalTransferSerializer(serializers.Serializer):
    from_account_id = serializers.UUIDField()
    to_account_id = serializers.UUIDField()
    amount = serializers.DecimalField(max_digits=15, decimal_places=2, min_value=Decimal('0.01'))
    description = serializers.CharField(max_length=255, required=False)

    def validate(self, attrs):
        from_account_id = attrs['from_account_id']
        to_account_id = attrs['to_account_id']
        amount = attrs['amount']

        # Validate accounts exist and are active
        try:
            from_account = Account.objects.get(id=from_account_id, status=ACCOUNT_ACTIVE_STATUS)
            to_account = Account.objects.get(id=to_account_id, status=ACCOUNT_ACTIVE_STATUS)
        except Account.DoesNotExist:
            raise serializers.ValidationError("One or both accounts not found or inactive")

        # Can't transfer to same account
        if from_account_id == to_account_id:
            raise serializers.ValidationError("Cannot transfer to the same account")

        # Check sufficient balance
        if from_account.balance < amount:
            raise serializers.ValidationError("Insufficient balance")

        # Check daily transfer limits
        from datetime import date
        today_transfers = Transfer.objects.filter(
            from_account=from_account,
            created_at__date=date.today(),
            status='COMPLETED'
        ).aggregate(total=models.Sum('amount'))['total'] or Decimal('0')

        daily_limit = Decimal('50000')  # Default daily transfer limit
        if today_transfers + amount > daily_limit:
            raise serializers.ValidationError("Daily transfer limit exceeded")

        attrs['from_account'] = from_account
        attrs['to_account'] = to_account
        return attrs

    def create(self, validated_data):
        from_account = validated_data['from_account']
        to_account = validated_data['to_account']
        amount = validated_data['amount']
        description = validated_data.get('description', 'Internal Transfer')

        with transaction.atomic():
            # Create transfer record
            transfer = Transfer.objects.create(
                from_account=from_account,
                to_account=to_account,
                amount=amount,
                description=description,
                transfer_type='INTERNAL',
                status='COMPLETED',
                currency=from_account.currency,
                initiated_by=from_account.user
            )

            # Create debit transaction for source account
            Transaction.objects.create(
                account=from_account,
                transaction_type='DEBIT',
                amount=amount,
                description=f"Transfer to {to_account.account_number}",
                reference_number=transfer.reference_number,
                balance_before=from_account.balance,
                balance_after=from_account.balance - amount,
                status='COMPLETED',
                currency=to_account.currency,
                user=from_account.user
            )

            # Create credit transaction for destination account
            Transaction.objects.create(
                account=to_account,
                transaction_type='CREDIT',
                amount=amount,
                description=f"Transfer from {from_account.account_number}",
                reference_number=transfer.reference_number,
                balance_before=to_account.balance,
                balance_after=to_account.balance + amount,
                status='COMPLETED',
                currency=from_account.currency,
                user=to_account.user
            )

            # Update account balances
            from_account.balance -= amount
            to_account.balance += amount
            from_account.save(update_fields=['balance', 'updated_at'])
            to_account.save(update_fields=['balance', 'updated_at'])

            logger.info(
                f"Internal transfer of {amount} completed from {from_account.account_number} to {to_account.account_number}")
            return transfer


class ExternalTransferSerializer(serializers.Serializer):
    from_account_id = serializers.UUIDField()
    to_account_number = serializers.CharField(max_length=20)
    to_bank_code = serializers.CharField(max_length=20)
    amount = serializers.DecimalField(max_digits=15, decimal_places=2, min_value=Decimal('0.01'))
    description = serializers.CharField(max_length=255, required=False)
    beneficiary_name = serializers.CharField(max_length=100)

    def validate_from_account_id(self, value):
        try:
            account = Account.objects.get(id=value, status=ACCOUNT_ACTIVE_STATUS)
            self.from_account = account
            return value
        except Account.DoesNotExist:
            raise serializers.ValidationError("Account not found or inactive")

    def validate(self, attrs):
        from_account = self.from_account
        amount = attrs['amount']

        # Check sufficient balance including fees
        fee_amount = amount * Decimal('0.01')  # 1% fee for external transfers
        total_deduction = amount + fee_amount

        if from_account.balance < total_deduction:
            raise serializers.ValidationError("Insufficient balance including fees")

        # Check daily external transfer limits
        from datetime import date
        today_transfers = Transfer.objects.filter(
            from_account=from_account,
            transfer_type='EXTERNAL',
            created_at__date=date.today(),
            status__in=['COMPLETED', 'PENDING']
        ).aggregate(total=models.Sum('amount'))['total'] or Decimal('0')

        daily_limit = Decimal('25000')  # Default daily external transfer limit
        if today_transfers + amount > daily_limit:
            raise serializers.ValidationError("Daily external transfer limit exceeded")

        attrs['fee_amount'] = fee_amount
        return attrs

    def create(self, validated_data):
        from_account = self.from_account
        amount = validated_data['amount']
        fee_amount = validated_data['fee_amount']
        description = validated_data.get('description', 'External Transfer')

        # Create transfer record with PENDING status
        transfer = Transfer.objects.create(
            from_account=from_account,
            to_account=None,  # External account
            amount=amount,
            description=description,
            transfer_type='EXTERNAL',
            status='PENDING',
            transfer_fee=fee_amount,
            metadata={
                'to_account_number': validated_data['to_account_number'],
                'to_bank_code': validated_data['to_bank_code'],
                'beneficiary_name': validated_data['beneficiary_name']
            },
            currency=from_account.currency,
        initiated_by=from_account.user
        )

        # Process transfer asynchronously
        from .tasks import process_external_transfer
        process_external_transfer.delay(transfer.id)

        logger.info(f"External transfer of {amount} initiated from {from_account.account_number}")
        return transfer


class ScheduledTransactionSerializer(serializers.ModelSerializer):
    from_account_number = serializers.CharField(source='from_account.account_number', read_only=True)
    to_account_number = serializers.CharField(source='to_account.account_number', read_only=True)

    class Meta:
        model = ScheduledTransaction
        fields = ('id', 'from_account', 'to_account', 'from_account_number',
                  'to_account_number', 'amount', 'description', 'schedule_type',
                  'scheduled_date', 'frequency', 'end_date', 'is_active',
                  'next_execution', 'last_executed', 'execution_count',
                  'created_at', 'updated_at')
        read_only_fields = ('id', 'next_execution', 'last_executed',
                            'execution_count', 'created_at', 'updated_at')


class TransactionLimitSerializer(serializers.ModelSerializer):
    account_number = serializers.CharField(source='account.account_number', read_only=True)

    class Meta:
        model = TransactionLimit
        fields = ('id', 'account', 'account_number', 'limit_type', 'daily_limit',
                  'monthly_limit', 'transaction_limit', 'is_active', 'created_at')
        read_only_fields = ('id', 'created_at')


class TransactionHistorySerializer(serializers.ModelSerializer):
    account_number = serializers.CharField(source='account.account_number', read_only=True)
    category_name = serializers.CharField(source='category.name', read_only=True)

    class Meta:
        model = Transaction
        fields = ('id', 'account_number', 'transaction_type', 'amount',
                  'description', 'reference_number', 'category_name',
                  'balance_after', 'status', 'created_at')
        read_only_fields = ('id', 'account_number', 'reference_number',
                            'balance_after', 'created_at')


class TransactionAnalyticsSerializer(serializers.Serializer):
    total_transactions = serializers.DecimalField(max_digits=20, decimal_places=2)
    total_deposits = serializers.DecimalField(max_digits=20, decimal_places=2)
    total_withdrawals = serializers.DecimalField(max_digits=20, decimal_places=2)
    total_fees = serializers.DecimalField(max_digits=20, decimal_places=2)
    total_refunds = serializers.DecimalField(max_digits=20, decimal_places=2)
    total_interest = serializers.DecimalField(max_digits=20, decimal_places=2)
    total_balance_before = serializers.DecimalField(max_digits=20, decimal_places=2)
    total_balance_after = serializers.DecimalField(max_digits=20, decimal_places=2)
    total_pending = serializers.IntegerField()
    total_completed = serializers.IntegerField()
    total_failed = serializers.IntegerField()
    total_transactions_by_user = serializers.IntegerField()
