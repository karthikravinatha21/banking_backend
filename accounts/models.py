"""
Account models for the banking system.
"""

from django.db import models
from django.contrib.auth.models import AbstractUser, Group, Permission
from django.core.validators import RegexValidator
from django.utils import timezone
from core.models import TimeStampedModel, Currency
import uuid
from decimal import Decimal


class UserRole(TimeStampedModel):
    """
    Custom role model for role-based access control.
    """
    ROLE_CHOICES = [
        ('admin', 'Administrator'),
        ('manager', 'Manager'),
        ('teller', 'Teller'),
        ('customer', 'Customer'),
        ('support', 'Support'),
    ]

    name = models.CharField(max_length=50, choices=ROLE_CHOICES, unique=True)
    description = models.TextField(blank=True)
    permissions = models.ManyToManyField(Permission, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'User Role'
        verbose_name_plural = 'User Roles'

    def __str__(self):
        return self.get_name_display()


class User(AbstractUser):
    """
    Custom User model with additional fields for banking system.
    """
    email = models.EmailField(unique=True)
    phone_regex = RegexValidator(
        regex=r'^\+?1?\d{9,15}$',
        message="Phone number must be entered in the format: '+999999999'. Up to 15 digits allowed."
    )
    phone_number = models.CharField(validators=[phone_regex], max_length=17, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    address = models.TextField(blank=True)
    city = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=100, blank=True)
    country = models.CharField(max_length=100, blank=True)
    postal_code = models.CharField(max_length=20, blank=True)
    
    # 2FA fields
    is_2fa_enabled = models.BooleanField(default=False)
    backup_tokens = models.JSONField(default=list, blank=True)
    otp = models.CharField(max_length=4)
    
    # Account status
    is_verified = models.BooleanField(default=False)
    verification_token = models.UUIDField(default=uuid.uuid4, unique=True, null=True, blank=True)
    
    # Profile
    profile_picture = models.ImageField(upload_to='profile_pics/', blank=True, null=True)
    
    # Preferences
    preferred_currency = models.ForeignKey(Currency, on_delete=models.SET_NULL, null=True, blank=True)
    timezone = models.CharField(max_length=50, default='UTC')
    language = models.CharField(max_length=10, default='en')
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_login_ip = models.GenericIPAddressField(null=True, blank=True)
    role = models.ForeignKey(UserRole, on_delete=models.SET_NULL, null=True, blank=True)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username', 'first_name', 'last_name']

    class Meta:
        db_table = 'accounts_user'
        verbose_name = 'User'
        verbose_name_plural = 'Users'

    def __str__(self):
        return f"{self.email} - {self.get_full_name()}"

    def get_full_name(self):
        return f"{self.first_name} {self.last_name}".strip()


class UserRoleAssignment(TimeStampedModel):
    """
    Assignment of roles to users with optional expiry.
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='role_assignments')
    role = models.ForeignKey(UserRole, on_delete=models.CASCADE)
    assigned_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='assigned_roles')
    expires_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ['user', 'role']
        verbose_name = 'User Role Assignment'
        verbose_name_plural = 'User Role Assignments'

    def __str__(self):
        return f"{self.user.email} - {self.role.name}"

    def is_expired(self):
        if self.expires_at:
            return timezone.now() > self.expires_at
        return False


class Account(TimeStampedModel):
    """
    Bank account model.
    """
    ACCOUNT_TYPES = [
        ('savings', 'Savings Account'),
        ('checking', 'Checking Account'),
        ('business', 'Business Account'),
        ('investment', 'Investment Account'),
    ]
    
    ACCOUNT_STATUS = [
        ('active', 'Active'),
        ('suspended', 'Suspended'),
        ('closed', 'Closed'),
        ('frozen', 'Frozen'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    account_number = models.CharField(max_length=20, unique=True, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='accounts')
    account_type = models.CharField(max_length=20, choices=ACCOUNT_TYPES, default='savings')
    currency = models.ForeignKey(Currency, on_delete=models.PROTECT)
    balance = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    available_balance = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    status = models.CharField(max_length=20, choices=ACCOUNT_STATUS, default='active')
    
    # Account limits
    daily_withdrawal_limit = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('1000.00'))
    daily_transfer_limit = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('5000.00'))
    monthly_withdrawal_limit = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('10000.00'))
    
    # Interest
    interest_rate = models.DecimalField(max_digits=5, decimal_places=4, default=Decimal('0.0100'))  # 1%
    last_interest_calculated = models.DateTimeField(null=True, blank=True)
    
    # Overdraft
    overdraft_limit = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    overdraft_fee = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('35.00'))
    
    # Metadata
    opened_date = models.DateTimeField(auto_now_add=True)
    closed_date = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        db_table = 'accounts_account'
        verbose_name = 'Account'
        verbose_name_plural = 'Accounts'
        indexes = [
            models.Index(fields=['account_number']),
            models.Index(fields=['user', 'status']),
            models.Index(fields=['currency']),
        ]

    def __str__(self):
        return f"{self.account_number} - {self.user.get_full_name()} ({self.get_account_type_display()})"

    def save(self, *args, **kwargs):
        if not self.account_number:
            self.account_number = self.generate_account_number()
        super().save(*args, **kwargs)

    @staticmethod
    def generate_account_number():
        """
        Generate unique account number using timestamp and UUID.
        """
        import time
        timestamp = str(int(time.time()))[-8:]  # Last 8 digits of timestamp
        uuid_part = str(uuid.uuid4()).replace('-', '')[:8]  # First 8 chars of UUID
        return f"AC{timestamp}{uuid_part}".upper()

    def is_active(self):
        return self.status == 'active'

    def can_withdraw(self, amount):
        """
        Check if withdrawal is possible considering balance and limits.
        """
        if not self.is_active():
            return False, "Account is not active"
        
        if amount <= 0:
            return False, "Invalid amount"
        
        available = self.available_balance + self.overdraft_limit
        if amount > available:
            return False, "Insufficient funds"
        
        return True, "OK"

    def update_balance(self, amount, transaction_type='credit'):
        """
        Update account balance. Amount should be positive for both credit and debit.
        """
        if transaction_type == 'credit':
            self.balance += amount
            self.available_balance += amount
        elif transaction_type == 'debit':
            self.balance -= amount
            self.available_balance -= amount
        
        self.save(update_fields=['balance', 'available_balance', 'updated_at'])


class AccountHold(TimeStampedModel):
    """
    Model to track holds/blocks on account funds.
    """
    HOLD_TYPES = [
        ('transaction', 'Transaction Hold'),
        ('legal', 'Legal Hold'),
        ('security', 'Security Hold'),
        ('administrative', 'Administrative Hold'),
    ]
    
    account = models.ForeignKey(Account, on_delete=models.CASCADE, related_name='holds')
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    hold_type = models.CharField(max_length=20, choices=HOLD_TYPES)
    reason = models.TextField()
    reference_id = models.CharField(max_length=100, blank=True)  # For transaction or case reference
    expires_at = models.DateTimeField(null=True, blank=True)
    released_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Account Hold'
        verbose_name_plural = 'Account Holds'

    def __str__(self):
        return f"Hold on {self.account.account_number}: {self.amount} {self.account.currency.code}"

    def release(self):
        """
        Release the hold and update account available balance.
        """
        if self.is_active:
            self.account.available_balance += self.amount
            self.account.save(update_fields=['available_balance'])
            self.is_active = False
            self.released_at = timezone.now()
            self.save(update_fields=['is_active', 'released_at'])


class LoginAttempt(TimeStampedModel):
    """
    Track login attempts for security monitoring.
    """
    email = models.EmailField()
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField(blank=True)
    is_successful = models.BooleanField(default=False)
    failure_reason = models.CharField(max_length=100, blank=True)
    location = models.CharField(max_length=200, blank=True)  # Derived from IP

    class Meta:
        verbose_name = 'Login Attempt'
        verbose_name_plural = 'Login Attempts'
        indexes = [
            models.Index(fields=['email', 'created_at']),
            models.Index(fields=['ip_address', 'created_at']),
        ]

    def __str__(self):
        status = "Success" if self.is_successful else "Failed"
        return f"{self.email} - {status} - {self.created_at}"
