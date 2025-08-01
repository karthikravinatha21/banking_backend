from django.core.management.base import BaseCommand
from django.db import transaction
from decimal import Decimal
from core.models import Currency, ExchangeRate
from accounts.models import UserRole, User
import logging
from django.contrib.auth.models import Permission

from transactions.models import TransactionCategory

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Initialize banking system with sample data'

    def add_arguments(self, parser):
        parser.add_argument(
            '--skip-currencies',
            action='store_true',
            help='Skip currency and exchange rate creation',
        )
        parser.add_argument(
            '--skip-roles',
            action='store_true',
            help='Skip user role creation',
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Starting banking system initialization...'))
        
        with transaction.atomic():
            if not options['skip_currencies']:
                self.create_currencies()
                self.create_exchange_rates()
                # self.create_superuser()
                self.create_transaction_category()

            if not options['skip_roles']:
                self.create_user_roles()
        
        self.stdout.write(self.style.SUCCESS('Banking system initialization completed!'))

    def create_currencies(self):
        """Create common currencies"""
        currencies = [
            {'code': 'INR', 'name': 'Indian Rupee', 'symbol': '₹'},
            {'code': 'USD', 'name': 'US Dollar', 'symbol': '$'},
            {'code': 'EUR', 'name': 'Euro', 'symbol': '€'},
            {'code': 'GBP', 'name': 'British Pound', 'symbol': '£'},
            {'code': 'JPY', 'name': 'Japanese Yen', 'symbol': '¥'},
            {'code': 'CAD', 'name': 'Canadian Dollar', 'symbol': 'C$'},
            {'code': 'AUD', 'name': 'Australian Dollar', 'symbol': 'A$'},
            {'code': 'CHF', 'name': 'Swiss Franc', 'symbol': 'CHF'},
            {'code': 'CNY', 'name': 'Chinese Yuan', 'symbol': '¥'},
            {'code': 'SEK', 'name': 'Swedish Krona', 'symbol': 'kr'},
            {'code': 'NZD', 'name': 'New Zealand Dollar', 'symbol': 'NZ$'},
        ]
        
        created_count = 0
        for currency_data in currencies:
            currency, created = Currency.objects.get_or_create(
                code=currency_data['code'],
                defaults={
                    'name': currency_data['name'],
                    'symbol': currency_data['symbol'],
                    'is_active': True
                }
            )
            if created:
                created_count += 1
                self.stdout.write(f"Created currency: {currency.code}")
        
        self.stdout.write(
            self.style.SUCCESS(f'Created {created_count} currencies')
        )

    def create_exchange_rates(self):
        """Create sample exchange rates"""
        # Sample exchange rates (USD as base)
        rates = {
            ('USD', 'EUR'): Decimal('0.85'),
            ('USD', 'GBP'): Decimal('0.73'),
            ('USD', 'JPY'): Decimal('110.00'),
            ('USD', 'CAD'): Decimal('1.25'),
            ('USD', 'AUD'): Decimal('1.35'),
            ('USD', 'CHF'): Decimal('0.92'),
            ('USD', 'CNY'): Decimal('6.45'),
            ('USD', 'SEK'): Decimal('8.60'),
            ('USD', 'NZD'): Decimal('1.42'),
        }

        created_count = 0
        for (from_code, to_code), rate in rates.items():
            try:
                from_currency = Currency.objects.get(code=from_code)
                to_currency = Currency.objects.get(code=to_code)

                exchange_rate, created = ExchangeRate.objects.get_or_create(
                    from_currency=from_currency,
                    to_currency=to_currency,
                    defaults={
                        'rate': rate,
                        'spread': Decimal('0.01'),  # 1% spread
                        'is_active': True
                    }
                )

                if created:
                    created_count += 1
                    self.stdout.write(f"Created exchange rate: {from_code}/{to_code} = {rate}")

                # Create reverse rate
                reverse_rate = Decimal('1') / rate
                reverse_exchange_rate, reverse_created = ExchangeRate.objects.get_or_create(
                    from_currency=to_currency,
                    to_currency=from_currency,
                    defaults={
                        'rate': reverse_rate,
                        'spread': Decimal('0.01'),
                        'is_active': True
                    }
                )

                if reverse_created:
                    created_count += 1
                    self.stdout.write(f"Created reverse exchange rate: {to_code}/{from_code} = {reverse_rate}")

            except Currency.DoesNotExist:
                self.stdout.write(
                    self.style.WARNING(f'Currency not found for rate {from_code}/{to_code}')
                )

        self.stdout.write(
            self.style.SUCCESS(f'Created {created_count} exchange rates')
        )

    def create_user_roles(self):
        """Create default user roles"""
        roles = [
            {
                'name': 'Customer',
                'description': 'Regular banking customer with basic access',
                'permissions': [
                    'view_own_accounts',
                    'view_own_transactions',
                    'make_deposits',
                    'make_withdrawals',
                    'make_internal_transfers',
                    'view_exchange_rates',
                    'convert_currency'
                ]
            },
            {
                'name': 'Premium Customer',
                'description': 'Premium customer with additional privileges',
                'permissions': [
                    'view_own_accounts',
                    'view_own_transactions',
                    'make_deposits',
                    'make_withdrawals',
                    'make_internal_transfers',
                    'make_external_transfers',
                    'schedule_transactions',
                    'view_exchange_rates',
                    'convert_currency',
                    'request_statements'
                ]
            },
            {
                'name': 'Teller',
                'description': 'Bank teller with customer service access',
                'permissions': [
                    'view_customer_accounts',
                    'view_customer_transactions',
                    'make_deposits_for_customers',
                    'make_withdrawals_for_customers',
                    'process_internal_transfers',
                    'view_exchange_rates',
                    'assist_customers'
                ]
            },
            {
                'name': 'Manager',
                'description': 'Branch manager with extended access',
                'permissions': [
                    'view_all_accounts',
                    'view_all_transactions',
                    'manage_customer_accounts',
                    'approve_large_transactions',
                    'manage_account_holds',
                    'view_reports',
                    'manage_transaction_limits',
                    'update_exchange_rates'
                ]
            },
            {
                'name': 'Admin',
                'description': 'System administrator with full access',
                'permissions': [
                    'manage_users',
                    'manage_roles',
                    'manage_accounts',
                    'manage_transactions',
                    'manage_currencies',
                    'manage_exchange_rates',
                    'view_system_stats',
                    'manage_settings',
                    'view_audit_logs'
                ]
            }
        ]

        created_count = 0
        for role_data in roles:
            role, created = UserRole.objects.get_or_create(
                name=role_data['name'],
                defaults={
                    'description': role_data['description'],
                    'is_active': True
                }
            )

            if created:
                # Get or create permission objects for each role
                permissions = []
                for perm_code in role_data['permissions']:
                    try:
                        permission = Permission.objects.get(codename=perm_code)
                        permissions.append(permission)
                    except Permission.DoesNotExist:
                        self.stdout.write(self.style.WARNING(f"Permission '{perm_code}' does not exist."))

                # Set the permissions for the role using the set() method
                role.permissions.set(permissions)

                created_count += 1
                self.stdout.write(f"Created role: {role.name}")

        self.stdout.write(
            self.style.SUCCESS(f'Created {created_count} user roles')
        )

    def create_superuser(self):
        try:
            user = User.objects.create_superuser(
                username='9999900000',
                password='999000',
                email='superadmin@mnk.com',
                is_active=True
            )
            print(f"Superuser {user.username} created successfully with email {user.email}")
        except:
            print(f'Already user exists!')

    def create_transaction_category(self):
        TransactionCategory.objects.create(name='Deposit',description='description',is_active=True)
        TransactionCategory.objects.create(name='Withdrawal',description='description',is_active=True)
        TransactionCategory.objects.create(name='Transfer',description='description',is_active=True)
        TransactionCategory.objects.create(name='Payment',description='description',is_active=True)
        TransactionCategory.objects.create(name='Adjustment',description='description',is_active=True)


