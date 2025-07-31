"""
Transaction models for the banking system.
"""

from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator
from django.utils import timezone
from core.models import TimeStampedModel, Currency
from accounts.models import Account
import uuid
from decimal import Decimal


User = get_user_model()


class TransactionCategory(TimeStampedModel):
    """
    Categories for transactions for better organization and reporting.
    """
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    icon = models.CharField(max_length=50, blank=True)  # For UI purposes
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Transaction Category'
        verbose_name_plural = 'Transaction Categories'
        ordering = ['name']

    def __str__(self):
        return self.name


class Transaction(TimeStampedModel):
    """
    Main transaction model for all types of financial transactions.
    """
    TRANSACTION_TYPES = [
        ('deposit', 'Deposit'),
        ('withdrawal', 'Withdrawal'),
        ('transfer', 'Transfer'),
        ('payment', 'Payment'),
        ('fee', 'Fee'),
        ('interest', 'Interest'),
        ('refund', 'Refund'),
        ('adjustment', 'Adjustment'),
    ]
    
    TRANSACTION_STATUS = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
        ('reversed', 'Reversed'),
    ]
    
    TRANSACTION_METHODS = [
        ('cash', 'Cash'),
        ('check', 'Check'),
        ('wire', 'Wire Transfer'),
        ('ach', 'ACH Transfer'),
        ('card', 'Card Payment'),
        ('online', 'Online Transfer'),
        ('mobile', 'Mobile Transfer'),
        ('atm', 'ATM'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    transaction_id = models.CharField(max_length=50, unique=True, editable=False)
    
    # Account and User information
    account = models.ForeignKey(Account, on_delete=models.CASCADE, related_name='transactions')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='transactions')
    
    # Transaction details
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPES)
    amount = models.DecimalField(max_digits=15, decimal_places=2, validators=[MinValueValidator(Decimal('0.01'))])
    currency = models.ForeignKey(Currency, on_delete=models.PROTECT)
    exchange_rate = models.DecimalField(max_digits=18, decimal_places=8, null=True, blank=True)
    
    # Balances (for audit trail)
    balance_before = models.DecimalField(max_digits=15, decimal_places=2)
    balance_after = models.DecimalField(max_digits=15, decimal_places=2)
    
    # Status and processing
    status = models.CharField(max_length=20, choices=TRANSACTION_STATUS, default='pending')
    method = models.CharField(max_length=20, choices=TRANSACTION_METHODS, default='online')
    
    # Description and categorization
    description = models.TextField()
    category = models.ForeignKey(TransactionCategory, on_delete=models.SET_NULL, null=True, blank=True)
    reference_number = models.CharField(max_length=100, blank=True)
    
    # Processing information
    processed_at = models.DateTimeField(null=True, blank=True)
    processed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='processed_transactions')
    
    # External reference (for transfers, payments, etc.)
    external_reference = models.CharField(max_length=200, blank=True)
    
    # Fees
    fee_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    
    # Metadata
    metadata = models.JSONField(default=dict, blank=True)  # For storing additional transaction data
    notes = models.TextField(blank=True)

    class Meta:
        db_table = 'transactions_transaction'
        verbose_name = 'Transaction'
        verbose_name_plural = 'Transactions'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['transaction_id']),
            models.Index(fields=['account', 'status']),
            models.Index(fields=['user', 'created_at']),
            models.Index(fields=['transaction_type', 'status']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        return f"{self.transaction_id} - {self.get_transaction_type_display()} - {self.amount} {self.currency.code}"

    def save(self, *args, **kwargs):
        if not self.transaction_id:
            self.transaction_id = self.generate_transaction_id()
        super().save(*args, **kwargs)

    @staticmethod
    def generate_transaction_id():
        """
        Generate unique transaction ID.
        """
        import time
        timestamp = str(int(time.time()))
        uuid_part = str(uuid.uuid4()).replace('-', '')[:8]
        return f"TXN{timestamp}{uuid_part}".upper()

    def complete_transaction(self):
        """
        Mark transaction as completed and update processed timestamp.
        """
        self.status = 'completed'
        self.processed_at = timezone.now()
        self.save(update_fields=['status', 'processed_at'])

    def fail_transaction(self, reason=None):
        """
        Mark transaction as failed.
        """
        self.status = 'failed'
        if reason:
            self.notes += f"\nFailure reason: {reason}"
        self.save(update_fields=['status', 'notes'])

    def reverse_transaction(self, reason=None):
        """
        Mark transaction as reversed.
        """
        self.status = 'reversed'
        if reason:
            self.notes += f"\nReversal reason: {reason}"
        self.save(update_fields=['status', 'notes'])


class Transfer(TimeStampedModel):
    """
    Transfer model for money transfers between accounts.
    """
    TRANSFER_TYPES = [
        ('internal', 'Internal Transfer'),
        ('external', 'External Transfer'),
        ('wire', 'Wire Transfer'),
        ('ach', 'ACH Transfer'),
    ]
    
    TRANSFER_STATUS = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    transfer_id = models.CharField(max_length=50, unique=True, editable=False)
    
    # Source and destination
    from_account = models.ForeignKey(Account, on_delete=models.CASCADE, related_name='outgoing_transfers')
    to_account = models.ForeignKey(Account, on_delete=models.CASCADE, related_name='incoming_transfers', null=True, blank=True)
    to_external_account = models.CharField(max_length=50, blank=True)  # For external transfers
    to_bank_code = models.CharField(max_length=20, blank=True)  # Routing number, SWIFT code, etc.
    
    # Transfer details
    transfer_type = models.CharField(max_length=20, choices=TRANSFER_TYPES, default='internal')
    amount = models.DecimalField(max_digits=15, decimal_places=2, validators=[MinValueValidator(Decimal('0.01'))])
    currency = models.ForeignKey(Currency, on_delete=models.PROTECT)
    exchange_rate = models.DecimalField(max_digits=18, decimal_places=8, null=True, blank=True)
    converted_amount = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    
    # Status and processing
    status = models.CharField(max_length=20, choices=TRANSFER_STATUS, default='pending')
    initiated_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='initiated_transfers')
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_transfers')
    
    # Description and reference
    description = models.TextField()
    reference_number = models.CharField(max_length=100, blank=True)
    external_reference = models.CharField(max_length=200, blank=True)
    
    # Fees
    transfer_fee = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    
    # Processing timestamps
    scheduled_at = models.DateTimeField(null=True, blank=True)  # For scheduled transfers
    processed_at = models.DateTimeField(null=True, blank=True)
    
    # Related transactions
    debit_transaction = models.OneToOneField(Transaction, on_delete=models.SET_NULL, null=True, blank=True, related_name='debit_transfer')
    credit_transaction = models.OneToOneField(Transaction, on_delete=models.SET_NULL, null=True, blank=True, related_name='credit_transfer')
    
    # Metadata
    metadata = models.JSONField(default=dict, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        db_table = 'transactions_transfer'
        verbose_name = 'Transfer'
        verbose_name_plural = 'Transfers'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['transfer_id']),
            models.Index(fields=['from_account', 'status']),
            models.Index(fields=['to_account', 'status']),
            models.Index(fields=['initiated_by', 'created_at']),
            models.Index(fields=['status', 'scheduled_at']),
        ]

    def __str__(self):
        return f"{self.transfer_id} - {self.amount} {self.currency.code} - {self.get_status_display()}"

    def save(self, *args, **kwargs):
        if not self.transfer_id:
            self.transfer_id = self.generate_transfer_id()
        super().save(*args, **kwargs)

    @staticmethod
    def generate_transfer_id():
        """
        Generate unique transfer ID.
        """
        import time
        timestamp = str(int(time.time()))
        uuid_part = str(uuid.uuid4()).replace('-', '')[:8]
        return f"TRF{timestamp}{uuid_part}".upper()

    def is_internal_transfer(self):
        """
        Check if this is an internal transfer (between accounts in the same system).
        """
        return self.transfer_type == 'internal' and self.to_account is not None

    def is_external_transfer(self):
        """
        Check if this is an external transfer.
        """
        return self.transfer_type in ['external', 'wire', 'ach'] or self.to_account is None


class ScheduledTransaction(TimeStampedModel):
    """
    Model for scheduled/recurring transactions.
    """
    FREQUENCY_CHOICES = [
        ('once', 'One Time'),
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('biweekly', 'Bi-weekly'),
        ('monthly', 'Monthly'),
        ('quarterly', 'Quarterly'),
        ('annually', 'Annually'),
    ]
    
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('paused', 'Paused'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    account = models.ForeignKey(Account, on_delete=models.CASCADE, related_name='scheduled_transactions')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='scheduled_transactions')
    
    # Transaction details
    transaction_type = models.CharField(max_length=20, choices=Transaction.TRANSACTION_TYPES)
    amount = models.DecimalField(max_digits=15, decimal_places=2, validators=[MinValueValidator(Decimal('0.01'))])
    currency = models.ForeignKey(Currency, on_delete=models.PROTECT)
    description = models.TextField()
    category = models.ForeignKey(TransactionCategory, on_delete=models.SET_NULL, null=True, blank=True)
    
    # Scheduling
    frequency = models.CharField(max_length=20, choices=FREQUENCY_CHOICES)
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    next_execution = models.DateTimeField()
    last_execution = models.DateTimeField(null=True, blank=True)
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    
    # Execution tracking
    execution_count = models.PositiveIntegerField(default=0)
    max_executions = models.PositiveIntegerField(null=True, blank=True)
    
    # Transfer specific (if applicable)
    destination_account = models.ForeignKey(Account, on_delete=models.CASCADE, null=True, blank=True, related_name='incoming_scheduled_transactions')
    
    # Metadata
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        verbose_name = 'Scheduled Transaction'
        verbose_name_plural = 'Scheduled Transactions'
        indexes = [
            models.Index(fields=['next_execution', 'status']),
            models.Index(fields=['account', 'status']),
        ]

    def __str__(self):
        return f"{self.get_transaction_type_display()} - {self.amount} {self.currency.code} - {self.get_frequency_display()}"

    def should_execute(self):
        """
        Check if the scheduled transaction should be executed now.
        """
        return (
            self.status == 'active' and
            timezone.now() >= self.next_execution and
            (self.max_executions is None or self.execution_count < self.max_executions) and
            (self.end_date is None or timezone.now().date() <= self.end_date)
        )

    def calculate_next_execution(self):
        """
        Calculate the next execution datetime based on frequency.
        """
        from dateutil.relativedelta import relativedelta
        
        if self.frequency == 'once':
            return None
        elif self.frequency == 'daily':
            return self.next_execution + timezone.timedelta(days=1)
        elif self.frequency == 'weekly':
            return self.next_execution + timezone.timedelta(weeks=1)
        elif self.frequency == 'biweekly':
            return self.next_execution + timezone.timedelta(weeks=2)
        elif self.frequency == 'monthly':
            return self.next_execution + relativedelta(months=1)
        elif self.frequency == 'quarterly':
            return self.next_execution + relativedelta(months=3)
        elif self.frequency == 'annually':
            return self.next_execution + relativedelta(years=1)
        
        return None

    def execute(self):
        """
        Execute the scheduled transaction and update execution tracking.
        """
        # This method would be called by the Celery task
        # Implementation would create the actual transaction
        self.execution_count += 1
        self.last_execution = timezone.now()
        
        next_exec = self.calculate_next_execution()
        if next_exec:
            self.next_execution = next_exec
        else:
            self.status = 'completed'
        
        if self.max_executions and self.execution_count >= self.max_executions:
            self.status = 'completed'
            
        self.save()


class TransactionLimit(TimeStampedModel):
    """
    Model to define transaction limits for accounts or users.
    """
    LIMIT_TYPES = [
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly'),
        ('per_transaction', 'Per Transaction'),
    ]
    
    APPLIES_TO = [
        ('account', 'Account'),
        ('user', 'User'),
        ('global', 'Global'),
    ]

    account = models.ForeignKey(Account, on_delete=models.CASCADE, null=True, blank=True, related_name='transaction_limits')
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True, related_name='transaction_limits')
    
    # Limit details
    transaction_type = models.CharField(max_length=20, choices=Transaction.TRANSACTION_TYPES)
    limit_type = models.CharField(max_length=20, choices=LIMIT_TYPES)
    applies_to = models.CharField(max_length=20, choices=APPLIES_TO)
    
    # Amounts
    limit_amount = models.DecimalField(max_digits=15, decimal_places=2)
    currency = models.ForeignKey(Currency, on_delete=models.PROTECT)
    
    # Status
    is_active = models.BooleanField(default=True)
    
    # Period tracking
    current_period_usage = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    period_start = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Transaction Limit'
        verbose_name_plural = 'Transaction Limits'

    def __str__(self):
        target = self.account or self.user or "Global"
        return f"{target} - {self.get_transaction_type_display()} - {self.limit_amount} {self.currency.code} ({self.get_limit_type_display()})"

    def reset_period_usage(self):
        """
        Reset the current period usage and update period start.
        """
        self.current_period_usage = Decimal('0.00')
        self.period_start = timezone.now()
        self.save(update_fields=['current_period_usage', 'period_start'])

    def is_limit_exceeded(self, transaction_amount):
        """
        Check if adding the transaction amount would exceed the limit.
        """
        return (self.current_period_usage + transaction_amount) > self.limit_amount

    def update_usage(self, transaction_amount):
        """
        Update the current period usage.
        """
        self.current_period_usage += transaction_amount
        self.save(update_fields=['current_period_usage'])
