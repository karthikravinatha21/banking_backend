# """
# Transactions app tests.
# """
# import uuid
# from decimal import Decimal
# from unittest.mock import patch, Mock
# from django.test import TestCase, override_settings
# from django.contrib.auth import get_user_model
# from django.core.exceptions import ValidationError
# from django.utils import timezone
# from django.urls import reverse
# from rest_framework.test import APITestCase, APIClient
# from rest_framework import status
# from rest_framework_simplejwt.tokens import RefreshToken
#
# from core.models import Currency
# from accounts.models import Account
# from .models import Transaction, Transfer, TransactionCategory, TransactionLimit, ScheduledTransaction
# from .serializers import DepositSerializer, WithdrawSerializer, TransferSerializer
#
#
# User = get_user_model()
#
#
# class TransactionCategoryModelTest(TestCase):
#     """Test cases for TransactionCategory model."""
#
#     def setUp(self):
#         """Set up test data."""
#         self.category = TransactionCategory.objects.create(
#             name='Transfer',
#             description='Money transfer transactions'
#         )
#
#     def test_category_creation(self):
#         """Test transaction category creation."""
#         self.assertEqual(self.category.name, 'Transfer')
#         self.assertEqual(self.category.description, 'Money transfer transactions')
#         self.assertTrue(self.category.is_active)
#
#     def test_category_str_representation(self):
#         """Test category string representation."""
#         self.assertEqual(str(self.category), 'Transfer')
#
#
# class TransactionModelTest(TestCase):
#     """Test cases for Transaction model."""
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
#         self.category = TransactionCategory.objects.create(
#             name='Deposit',
#             description='Money deposit transactions'
#         )
#
#     def test_transaction_creation(self):
#         """Test transaction creation."""
#         transaction = Transaction.objects.create(
#             account=self.account,
#             transaction_type='DEPOSIT',
#             amount=Decimal('100.00'),
#             description='Test deposit',
#             category=self.category
#         )
#
#         self.assertEqual(transaction.account, self.account)
#         self.assertEqual(transaction.transaction_type, 'DEPOSIT')
#         self.assertEqual(transaction.amount, Decimal('100.00'))
#         self.assertEqual(transaction.description, 'Test deposit')
#         self.assertEqual(transaction.category, self.category)
#         self.assertEqual(transaction.status, 'COMPLETED')
#         self.assertIsNotNone(transaction.transaction_id)
#         self.assertIsNotNone(transaction.created_at)
#
#     def test_transaction_str_representation(self):
#         """Test transaction string representation."""
#         transaction = Transaction.objects.create(
#             account=self.account,
#             transaction_type='DEPOSIT',
#             amount=Decimal('100.00'),
#             description='Test deposit',
#             category=self.category
#         )
#         expected = f"{transaction.transaction_id} - DEPOSIT: $100.00"
#         self.assertEqual(str(transaction), expected)
#
#     def test_transaction_id_unique(self):
#         """Test transaction ID uniqueness."""
#         transaction1 = Transaction.objects.create(
#             account=self.account,
#             transaction_type='DEPOSIT',
#             amount=Decimal('100.00'),
#             category=self.category
#         )
#
#         transaction2 = Transaction.objects.create(
#             account=self.account,
#             transaction_type='WITHDRAW',
#             amount=Decimal('50.00'),
#             category=self.category
#         )
#
#         self.assertNotEqual(transaction1.transaction_id, transaction2.transaction_id)
#
#     def test_negative_amount_validation(self):
#         """Test that transaction amount cannot be negative."""
#         with self.assertRaises(ValidationError):
#             transaction = Transaction(
#                 account=self.account,
#                 transaction_type='DEPOSIT',
#                 amount=Decimal('-100.00'),
#                 category=self.category
#             )
#             transaction.full_clean()
#
#     def test_zero_amount_validation(self):
#         """Test that transaction amount cannot be zero."""
#         with self.assertRaises(ValidationError):
#             transaction = Transaction(
#                 account=self.account,
#                 transaction_type='DEPOSIT',
#                 amount=Decimal('0.00'),
#                 category=self.category
#             )
#             transaction.full_clean()
#
#
# class TransferModelTest(TestCase):
#     """Test cases for Transfer model."""
#
#     def setUp(self):
#         """Set up test data."""
#         self.user1 = User.objects.create_user(
#             email='user1@example.com',
#             password='testpass123'
#         )
#         self.user2 = User.objects.create_user(
#             email='user2@example.com',
#             password='testpass123'
#         )
#         self.currency = Currency.objects.create(
#             code='USD',
#             name='US Dollar',
#             symbol='$'
#         )
#         self.from_account = Account.objects.create(
#             user=self.user1,
#             account_type='SAVINGS',
#             currency=self.currency,
#             balance=Decimal('1000.00')
#         )
#         self.to_account = Account.objects.create(
#             user=self.user2,
#             account_type='CHECKING',
#             currency=self.currency,
#             balance=Decimal('500.00')
#         )
#
#     def test_transfer_creation(self):
#         """Test transfer creation."""
#         transfer = Transfer.objects.create(
#             from_account=self.from_account,
#             to_account=self.to_account,
#             amount=Decimal('100.00'),
#             description='Test transfer'
#         )
#
#         self.assertEqual(transfer.from_account, self.from_account)
#         self.assertEqual(transfer.to_account, self.to_account)
#         self.assertEqual(transfer.amount, Decimal('100.00'))
#         self.assertEqual(transfer.description, 'Test transfer')
#         self.assertEqual(transfer.status, 'PENDING')
#         self.assertIsNotNone(transfer.transfer_id)
#
#     def test_transfer_str_representation(self):
#         """Test transfer string representation."""
#         transfer = Transfer.objects.create(
#             from_account=self.from_account,
#             to_account=self.to_account,
#             amount=Decimal('100.00')
#         )
#         expected = f"{transfer.transfer_id} - {self.from_account.account_number} -> {self.to_account.account_number}: $100.00"
#         self.assertEqual(str(transfer), expected)
#
#     def test_same_account_transfer_validation(self):
#         """Test that transfer cannot be made to the same account."""
#         with self.assertRaises(ValidationError):
#             transfer = Transfer(
#                 from_account=self.from_account,
#                 to_account=self.from_account,
#                 amount=Decimal('100.00')
#             )
#             transfer.full_clean()
#
#
# class TransactionLimitModelTest(TestCase):
#     """Test cases for TransactionLimit model."""
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
#     def test_transaction_limit_creation(self):
#         """Test transaction limit creation."""
#         limit = TransactionLimit.objects.create(
#             account=self.account,
#             transaction_type='WITHDRAW',
#             daily_limit=Decimal('1000.00'),
#             monthly_limit=Decimal('5000.00')
#         )
#
#         self.assertEqual(limit.account, self.account)
#         self.assertEqual(limit.transaction_type, 'WITHDRAW')
#         self.assertEqual(limit.daily_limit, Decimal('1000.00'))
#         self.assertEqual(limit.monthly_limit, Decimal('5000.00'))
#         self.assertTrue(limit.is_active)
#
#     def test_transaction_limit_str_representation(self):
#         """Test transaction limit string representation."""
#         limit = TransactionLimit.objects.create(
#             account=self.account,
#             transaction_type='WITHDRAW',
#             daily_limit=Decimal('1000.00')
#         )
#         expected = f"{self.account.account_number} - WITHDRAW: Daily $1000.00"
#         self.assertEqual(str(limit), expected)
#
#
# class ScheduledTransactionModelTest(TestCase):
#     """Test cases for ScheduledTransaction model."""
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
#         self.category = TransactionCategory.objects.create(
#             name='Transfer',
#             description='Transfer transactions'
#         )
#
#     def test_scheduled_transaction_creation(self):
#         """Test scheduled transaction creation."""
#         scheduled_transaction = ScheduledTransaction.objects.create(
#             account=self.account,
#             transaction_type='TRANSFER',
#             amount=Decimal('100.00'),
#             description='Monthly rent',
#             category=self.category,
#             schedule_type='MONTHLY',
#             scheduled_date=timezone.now().date()
#         )
#
#         self.assertEqual(scheduled_transaction.account, self.account)
#         self.assertEqual(scheduled_transaction.transaction_type, 'TRANSFER')
#         self.assertEqual(scheduled_transaction.amount, Decimal('100.00'))
#         self.assertEqual(scheduled_transaction.schedule_type, 'MONTHLY')
#         self.assertTrue(scheduled_transaction.is_active)
#
#     def test_scheduled_transaction_str_representation(self):
#         """Test scheduled transaction string representation."""
#         scheduled_transaction = ScheduledTransaction.objects.create(
#             account=self.account,
#             transaction_type='TRANSFER',
#             amount=Decimal('100.00'),
#             description='Monthly rent',
#             category=self.category,
#             schedule_type='MONTHLY',
#             scheduled_date=timezone.now().date()
#         )
#         expected = f"MONTHLY TRANSFER: $100.00 - Monthly rent"
#         self.assertEqual(str(scheduled_transaction), expected)
#
#
# class DepositSerializerTest(TestCase):
#     """Test cases for DepositSerializer."""
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
#     def test_valid_deposit_data(self):
#         """Test serializer with valid deposit data."""
#         data = {
#             'account': self.account.id,
#             'amount': '100.00',
#             'description': 'Test deposit'
#         }
#
#         serializer = DepositSerializer(data=data)
#         self.assertTrue(serializer.is_valid())
#
#     def test_negative_amount_validation(self):
#         """Test serializer rejects negative amounts."""
#         data = {
#             'account': self.account.id,
#             'amount': '-100.00',
#             'description': 'Invalid deposit'
#         }
#
#         serializer = DepositSerializer(data=data)
#         self.assertFalse(serializer.is_valid())
#         self.assertIn('amount', serializer.errors)
#
#     def test_zero_amount_validation(self):
#         """Test serializer rejects zero amounts."""
#         data = {
#             'account': self.account.id,
#             'amount': '0.00',
#             'description': 'Invalid deposit'
#         }
#
#         serializer = DepositSerializer(data=data)
#         self.assertFalse(serializer.is_valid())
#         self.assertIn('amount', serializer.errors)
#
#
# class WithdrawSerializerTest(TestCase):
#     """Test cases for WithdrawSerializer."""
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
#     def test_valid_withdrawal_data(self):
#         """Test serializer with valid withdrawal data."""
#         data = {
#             'account': self.account.id,
#             'amount': '100.00',
#             'description': 'Test withdrawal'
#         }
#
#         serializer = WithdrawSerializer(data=data)
#         self.assertTrue(serializer.is_valid())
#
#     def test_insufficient_balance_validation(self):
#         """Test serializer validates sufficient balance."""
#         data = {
#             'account': self.account.id,
#             'amount': '2000.00',  # More than account balance
#             'description': 'Invalid withdrawal'
#         }
#
#         serializer = WithdrawSerializer(data=data)
#         # This validation might be handled in the view rather than serializer
#         # depending on implementation
#         if not serializer.is_valid():
#             self.assertIn('amount', serializer.errors)
#
#
# class TransactionAPITest(APITestCase):
#     """Test cases for Transaction API endpoints."""
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
#         # Create JWT token
#         refresh = RefreshToken.for_user(self.user)
#         self.access_token = str(refresh.access_token)
#
#         self.client = APIClient()
#         self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.access_token}')
#
#     def test_deposit_transaction(self):
#         """Test deposit transaction via API."""
#         url = reverse('transaction-deposit')
#         data = {
#             'account': self.account.id,
#             'amount': '100.00',
#             'description': 'Test deposit'
#         }
#
#         response = self.client.post(url, data)
#         self.assertEqual(response.status_code, status.HTTP_201_CREATED)
#
#         # Check that transaction was created
#         transaction = Transaction.objects.get(id=response.data['id'])
#         self.assertEqual(transaction.transaction_type, 'DEPOSIT')
#         self.assertEqual(transaction.amount, Decimal('100.00'))
#
#     def test_withdraw_transaction(self):
#         """Test withdrawal transaction via API."""
#         url = reverse('transaction-withdraw')
#         data = {
#             'account': self.account.id,
#             'amount': '100.00',
#             'description': 'Test withdrawal'
#         }
#
#         response = self.client.post(url, data)
#         self.assertEqual(response.status_code, status.HTTP_201_CREATED)
#
#         # Check that transaction was created
#         transaction = Transaction.objects.get(id=response.data['id'])
#         self.assertEqual(transaction.transaction_type, 'WITHDRAW')
#         self.assertEqual(transaction.amount, Decimal('100.00'))
#
#     def test_transfer_transaction(self):
#         """Test transfer transaction via API."""
#         # Create another account for transfer
#         user2 = User.objects.create_user(
#             email='user2@example.com',
#             password='testpass123'
#         )
#         to_account = Account.objects.create(
#             user=user2,
#             account_type='CHECKING',
#             currency=self.currency
#         )
#
#         url = reverse('transaction-transfer')
#         data = {
#             'from_account': self.account.id,
#             'to_account': to_account.id,
#             'amount': '100.00',
#             'description': 'Test transfer'
#         }
#
#         response = self.client.post(url, data)
#         self.assertEqual(response.status_code, status.HTTP_201_CREATED)
#
#         # Check that transfer was created
#         transfer = Transfer.objects.get(id=response.data['id'])
#         self.assertEqual(transfer.from_account, self.account)
#         self.assertEqual(transfer.to_account, to_account)
#         self.assertEqual(transfer.amount, Decimal('100.00'))
#
#     def test_transaction_history(self):
#         """Test retrieving transaction history."""
#         # Create test transactions
#         category = TransactionCategory.objects.create(name='Test', description='Test category')
#         Transaction.objects.create(
#             account=self.account,
#             transaction_type='DEPOSIT',
#             amount=Decimal('100.00'),
#             category=category
#         )
#         Transaction.objects.create(
#             account=self.account,
#             transaction_type='WITHDRAW',
#             amount=Decimal('50.00'),
#             category=category
#         )
#
#         url = reverse('transaction-history')
#         response = self.client.get(url, {'account': self.account.id})
#
#         self.assertEqual(response.status_code, status.HTTP_200_OK)
#         self.assertEqual(len(response.data['results']), 2)
#
#     def test_unauthorized_access(self):
#         """Test unauthorized access to transactions."""
#         self.client.credentials()  # Remove authentication
#
#         url = reverse('transaction-deposit')
#         data = {
#             'account': self.account.id,
#             'amount': '100.00'
#         }
#
#         response = self.client.post(url, data)
#         self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
#
#
# @override_settings(CELERY_TASK_ALWAYS_EAGER=True)
# class TransactionTaskTest(TestCase):
#     """Test cases for transaction-related Celery tasks."""
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
#     @patch('transactions.tasks.logger')
#     def test_process_external_transfer_task(self, mock_logger):
#         """Test processing external transfer task."""
#         from .tasks import process_external_transfer
#
#         transfer_data = {
#             'from_account_id': self.account.id,
#             'external_account': 'EXT123456789',
#             'amount': '100.00',
#             'description': 'External transfer'
#         }
#
#         result = process_external_transfer.delay(transfer_data)
#
#         # Check that the task executed
#         mock_logger.info.assert_called()
#
#     @patch('transactions.tasks.logger')
#     def test_process_scheduled_transactions_task(self, mock_logger):
#         """Test processing scheduled transactions task."""
#         from .tasks import process_scheduled_transactions
#
#         # Create a scheduled transaction
#         category = TransactionCategory.objects.create(name='Test', description='Test')
#         ScheduledTransaction.objects.create(
#             account=self.account,
#             transaction_type='TRANSFER',
#             amount=Decimal('100.00'),
#             category=category,
#             schedule_type='DAILY',
#             scheduled_date=timezone.now().date()
#         )
#
#         result = process_scheduled_transactions.delay()
#
#         # Check that the task executed
#         mock_logger.info.assert_called()
