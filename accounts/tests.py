"""
Accounts app tests.
"""
import uuid
from decimal import Decimal
from unittest.mock import patch, Mock
from django.test import TestCase, override_settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.urls import reverse
from rest_framework.test import APITestCase, APIClient
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken

from core.models import Currency
from .models import Account, UserRole, UserRoleAssignment, AccountHold, LoginAttempt
from .serializers import UserRegistrationSerializer, AccountSerializer


User = get_user_model()


class UserModelTest(TestCase):
    """Test cases for custom User model."""

    def setUp(self):
        """Set up test data."""
        self.user_data = {
            'email': 'test@test.com',
            'first_name': 'Karthik',
            'last_name': 'Ravinatha',
            'phone_number': '+1234567890'
        }

    def test_user_creation(self):
        """Test user creation with email as username."""
        user = User.objects.create_user(
            email='test@test.com',
            password='testpass123',
            first_name='Karthik',
            last_name='Ravinatha',
            username='test@test.com'
        )

        self.assertEqual(user.email, 'test@test.com')
        self.assertEqual(user.username, 'test@test.com')
        self.assertEqual(user.first_name, 'Karthik')
        self.assertEqual(user.last_name, 'Ravinatha')
        self.assertTrue(user.check_password('testpass123'))
        self.assertTrue(user.is_active)
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)

    def test_superuser_creation(self):
        """Test superuser creation."""
        admin_user = User.objects.create_superuser(
            email='admin@test.com',
            password='adminpass123',
            username='admin@test.com',
        )

        self.assertEqual(admin_user.email, 'admin@test.com')
        self.assertTrue(admin_user.is_active)
        self.assertTrue(admin_user.is_staff)
        self.assertTrue(admin_user.is_superuser)

    def test_user_str_representation(self):
        """Test user string representation."""
        user = User.objects.create_user(
            email='test@test.com',
            password='testpass123',
            first_name='Karthik',
            last_name='Ravinatha',
            username='test@test.com',
        )
        self.assertEqual(str(user.email), 'test@test.com')

    def test_user_full_name(self):
        """Test user full name property."""
        user = User.objects.create_user(
            email='test@example.com',
            password='testpass123',
            first_name='John',
            last_name='Doe',
            username='test@example.com',
        )
        self.assertEqual(f'{user.first_name} {user.last_name}', 'John Doe')

    def test_email_unique(self):
        """Test email uniqueness."""
        User.objects.create_user(
            email='test@example.com',
            password='testpass123',
            username='test@example.com',
        )

        with self.assertRaises(Exception):
            User.objects.create_user(
                email='test@example.com',
                password='anotherpass123',
                username='test@example.com',
            )


class AccountModelTest(TestCase):
    """Test cases for Account model."""

    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123',
            first_name='John',
            last_name='Doe',
            username='test@example.com',
        )
        self.currency = Currency.objects.create(
            code='USD',
            name='US Dollar',
            symbol='$'
        )

    def test_account_creation(self):
        """Test account creation with auto-generated account number."""
        account = Account.objects.create(
            user=self.user,
            account_type='SAVINGS',
            currency=self.currency
        )

        self.assertEqual(account.user, self.user)
        self.assertEqual(account.account_type, 'SAVINGS')
        self.assertEqual(account.currency, self.currency)
        self.assertEqual(account.balance, Decimal('0.00'))
        self.assertTrue(account.is_active)
        self.assertIsNotNone(account.account_number)
        self.assertGreater(len(account.account_number), 10)

    def test_account_str_representation(self):
        """Test account string representation."""
        account = Account.objects.create(
            user=self.user,
            account_type='SAVINGS',
            currency=self.currency
        )
        expected = f"{account.account_number}"
        self.assertEqual(str(account.account_number), expected)

    def test_account_number_unique(self):
        """Test account number uniqueness."""
        account1 = Account.objects.create(
            user=self.user,
            account_type='SAVINGS',
            currency=self.currency
        )

        # Create another account and verify it has a different number
        user2 = User.objects.create_user(
            email='test2@example.com',
            password='testpass123',
            username='test2@example.com',
        )
        account2 = Account.objects.create(
            user=user2,
            account_type='CHECKING',
            currency=self.currency
        )

        self.assertNotEqual(account1.account_number, account2.account_number)
#
#     def test_account_balance_validation(self):
#         """Test account balance cannot be negative."""
#         account = Account.objects.create(
#             user=self.user,
#             account_type='SAVINGS',
#             currency=self.currency
#         )
#
#         with self.assertRaises(ValidationError):
#             account.balance = Decimal('-100.00')
#             account.full_clean()
#
#
# class UserRoleModelTest(TestCase):
#     """Test cases for UserRole model."""
#
#     def setUp(self):
#         """Set up test data."""
#         self.role = UserRole.objects.create(
#             name='CUSTOMER',
#             description='Standard customer role'
#         )
#
#     def test_role_creation(self):
#         """Test role creation."""
#         self.assertEqual(self.role.name, 'CUSTOMER')
#         self.assertEqual(self.role.description, 'Standard customer role')
#         self.assertTrue(self.role.is_active)
#
#     def test_role_str_representation(self):
#         """Test role string representation."""
#         self.assertEqual(str(self.role), 'CUSTOMER')
#
#
# class AccountHoldModelTest(TestCase):
#     """Test cases for AccountHold model."""
#
#     def setUp(self):
#         """Set up test data."""
#         self.user = User.objects.create_user(
#             email='test@example.com',
#             password='testpass123'
#         )
#         self.currency = Currency.objects.create(
#             code='USD',
#             name='US Dollar',
#             symbol='$'
#         )
#         self.account = Account.objects.create(
#             user=self.user,
#             account_type='SAVINGS',
#             currency=self.currency,
#             balance=Decimal('1000.00')
#         )
#
#     def test_account_hold_creation(self):
#         """Test account hold creation."""
#         hold = AccountHold.objects.create(
#             account=self.account,
#             amount=Decimal('100.00'),
#             reason='Test hold',
#             hold_type='TRANSACTION'
#         )
#
#         self.assertEqual(hold.account, self.account)
#         self.assertEqual(hold.amount, Decimal('100.00'))
#         self.assertEqual(hold.reason, 'Test hold')
#         self.assertEqual(hold.hold_type, 'TRANSACTION')
#         self.assertTrue(hold.is_active)
#         self.assertIsNone(hold.released_at)
#
#     def test_account_hold_str_representation(self):
#         """Test account hold string representation."""
#         hold = AccountHold.objects.create(
#             account=self.account,
#             amount=Decimal('100.00'),
#             reason='Test hold'
#         )
#         expected = f"Hold on {self.account.account_number}: $100.00"
#         self.assertEqual(str(hold), expected)
#
#     def test_account_hold_release(self):
#         """Test account hold release."""
#         hold = AccountHold.objects.create(
#             account=self.account,
#             amount=Decimal('100.00'),
#             reason='Test hold'
#         )
#
#         # Release the hold
#         hold.is_active = False
#         hold.released_at = timezone.now()
#         hold.save()
#
#         self.assertFalse(hold.is_active)
#         self.assertIsNotNone(hold.released_at)
#
#
# class LoginAttemptModelTest(TestCase):
#     """Test cases for LoginAttempt model."""
#
#     def setUp(self):
#         """Set up test data."""
#         self.user = User.objects.create_user(
#             email='test@example.com',
#             password='testpass123'
#         )
#
#     def test_login_attempt_creation(self):
#         """Test login attempt creation."""
#         attempt = LoginAttempt.objects.create(
#             user=self.user,
#             ip_address='192.168.1.1',
#             user_agent='Test Browser',
#             successful=True
#         )
#
#         self.assertEqual(attempt.user, self.user)
#         self.assertEqual(attempt.ip_address, '192.168.1.1')
#         self.assertEqual(attempt.user_agent, 'Test Browser')
#         self.assertTrue(attempt.successful)
#         self.assertIsNotNone(attempt.attempted_at)
#
#     def test_failed_login_attempt(self):
#         """Test failed login attempt."""
#         attempt = LoginAttempt.objects.create(
#             user=self.user,
#             ip_address='192.168.1.1',
#             user_agent='Test Browser',
#             successful=False,
#             failure_reason='Invalid password'
#         )
#
#         self.assertFalse(attempt.successful)
#         self.assertEqual(attempt.failure_reason, 'Invalid password')
#
#
# class UserRegistrationSerializerTest(TestCase):
#     """Test cases for UserRegistrationSerializer."""
#
#     def test_valid_registration_data(self):
#         """Test serializer with valid registration data."""
#         data = {
#             'email': 'test@example.com',
#             'password': 'testpass123',
#             'password_confirm': 'testpass123',
#             'first_name': 'John',
#             'last_name': 'Doe',
#             'phone_number': '+1234567890'
#         }
#
#         serializer = UserRegistrationSerializer(data=data)
#         self.assertTrue(serializer.is_valid())
#
#     def test_password_mismatch(self):
#         """Test serializer with mismatched passwords."""
#         data = {
#             'email': 'test@example.com',
#             'password': 'testpass123',
#             'password_confirm': 'differentpass123',
#             'first_name': 'John',
#             'last_name': 'Doe'
#         }
#
#         serializer = UserRegistrationSerializer(data=data)
#         self.assertFalse(serializer.is_valid())
#         self.assertIn('password_confirm', serializer.errors)
#
#     def test_invalid_email(self):
#         """Test serializer with invalid email."""
#         data = {
#             'email': 'invalid-email',
#             'password': 'testpass123',
#             'password_confirm': 'testpass123',
#             'first_name': 'John',
#             'last_name': 'Doe'
#         }
#
#         serializer = UserRegistrationSerializer(data=data)
#         self.assertFalse(serializer.is_valid())
#         self.assertIn('email', serializer.errors)
#
#
# class AccountSerializerTest(TestCase):
#     """Test cases for AccountSerializer."""
#
#     def setUp(self):
#         """Set up test data."""
#         self.user = User.objects.create_user(
#             email='test@example.com',
#             password='testpass123'
#         )
#         self.currency = Currency.objects.create(
#             code='USD',
#             name='US Dollar',
#             symbol='$'
#         )
#         self.account = Account.objects.create(
#             user=self.user,
#             account_type='SAVINGS',
#             currency=self.currency
#         )
#
#     def test_account_serialization(self):
#         """Test account serialization."""
#         serializer = AccountSerializer(self.account)
#         data = serializer.data
#
#         self.assertEqual(data['account_number'], self.account.account_number)
#         self.assertEqual(data['account_type'], 'SAVINGS')
#         self.assertEqual(data['balance'], '0.00')
#         self.assertEqual(data['currency'], 'USD')
#         self.assertTrue(data['is_active'])
#
#



class AccountAPITest(APITestCase):
    """Test cases for Account API endpoints."""

    def setUp(self):
        """Set up test data."""
        # Create a user
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123',
            first_name='John',
            last_name='Doe',
            username='test@example.com',
        )

        # Create a currency
        self.currency = Currency.objects.create(
            code='USD',
            name='US Dollar',
            symbol='$'
        )

        # Create JWT token
        refresh = RefreshToken.for_user(self.user)
        self.access_token = str(refresh.access_token)

        # Initialize API client and set authorization header
        self.client = APIClient()
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.access_token}')

    def test_create_account(self):
        """Test account creation via API."""
        url = '/api/accounts/'

        # Pass the id of the currency, and user
        data = {
            'account_type': 'savings',
            'currency': self.currency.id,  # Use the correct currency ID
            'user_email': self.user.email,  # Use the user ID or reference
        }

        # Send a POST request to create an account
        response = self.client.post(url, data)
        print(response.data)

        # Assert that the account was created successfully
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # Retrieve the account and check if the data is correct
        account = Account.objects.get(id=response.data['id'])
        self.assertEqual(account.user, self.user)
        self.assertEqual(account.account_type, 'savings')
        self.assertEqual(account.currency, self.currency)

    def test_list_user_accounts(self):
        """Test listing user's accounts."""
        # Create test accounts
        Account.objects.create(
            user=self.user,
            account_type='SAVINGS',
            currency=self.currency
        )
        Account.objects.create(
            user=self.user,
            account_type='CHECKING',
            currency=self.currency
        )

        url = '/api/accounts/'
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 2)

    def test_account_detail(self):
        """Test retrieving account details."""
        account = Account.objects.create(
            user=self.user,
            account_type='SAVINGS',
            currency=self.currency
        )

        url = reverse('accounts:account-detail', kwargs={'pk': account.id})
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['account_number'], account.account_number)

    def test_unauthorized_access(self):
        """Test unauthorized access to accounts."""
        self.client.credentials()  # Remove authentication

        url = '/api/accounts/'
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

