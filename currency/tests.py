"""
Currency app tests.
"""
from decimal import Decimal
from unittest.mock import patch, Mock
from django.test import TestCase, override_settings
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APITestCase, APIClient
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken

from core.models import Currency, ExchangeRate
from accounts.models import Account
from .serializers import CurrencySerializer, ExchangeRateSerializer, CurrencyConversionSerializer


User = get_user_model()


class CurrencySerializerTest(TestCase):
    """Test cases for CurrencySerializer."""

    def setUp(self):
        """Set up test data."""
        self.currency = Currency.objects.create(
            code='USD',
            name='US',
            symbol='$'
        )

    def test_currency_serialization(self):
        """Test currency serialization."""
        serializer = CurrencySerializer(self.currency)
        data = serializer.data

        self.assertEqual(data['code'], 'USD')
        self.assertEqual(data['name'], 'US')
        self.assertEqual(data['symbol'], '$')
        self.assertTrue(data['is_active'])

    def test_currency_deserialization(self):
        """Test currency deserialization."""
        data = {
            'code': 'INR',
            'name': 'Indian Rupee',
            'symbol': '₹',
            'is_active': True
        }

        serializer = CurrencySerializer(data=data)
        if not serializer.is_valid():
            print(serializer.errors)
        self.assertTrue(serializer.is_valid())
        currency = serializer.save()

        self.assertEqual(currency.code, 'INR')
        self.assertEqual(currency.name, 'Indian Rupee')
        self.assertEqual(currency.symbol, '₹')


class ExchangeRateSerializerTest(TestCase):
    """Test cases for ExchangeRateSerializer."""

    def setUp(self):
        """Set up test data."""
        self.usd = Currency.objects.create(
            code='USD',
            name='US Dollar',
            symbol='$'
        )
        self.eur = Currency.objects.create(
            code='EUR',
            name='Euro',
            symbol='€'
        )
        self.exchange_rate = ExchangeRate.objects.create(
            from_currency=self.usd,
            to_currency=self.eur,
            rate=Decimal('0.85'),
            spread=Decimal('0.02')
        )

    def test_exchange_rate_serialization(self):
        """Test exchange rate serialization."""
        serializer = ExchangeRateSerializer(self.exchange_rate)
        data = serializer.data

        self.assertEqual(data['from_currency_code'], 'USD')
        self.assertEqual(data['to_currency_code'], 'EUR')
        self.assertEqual(round(float(data['rate']), 2), 0.85)
        self.assertEqual(round(float(data['spread']), 2), 0.02)
        # self.assertTrue(data['is_active'], True)

    # def test_exchange_rate_deserialization(self):
    #     """Test exchange rate deserialization."""
    #     gbp = Currency.objects.create(
    #         code='GBP',
    #         name='British Pound',
    #         symbol='£'
    #     )
    #
    #     data = {
    #         'from_currency': 'INR',
    #         'to_currency': 'USD',
    #         'rate': '0.78',
    #         'spread': '0.015',
    #         # 'is_active': True
    #     }
    #
    #     serializer = ExchangeRateSerializer(data=data)
    #     self.assertTrue(serializer.is_valid())
    #     exchange_rate = serializer.save()
    #
    #     self.assertEqual(exchange_rate.from_currency, self.usd)
    #     self.assertEqual(exchange_rate.to_currency, gbp)
    #     self.assertEqual(exchange_rate.rate, Decimal('0.78'))


# class CurrencyConversionSerializerTest(TestCase):
#     """Test cases for CurrencyConversionSerializer."""
#
#     def setUp(self):
#         """Set up test data."""
#         self.usd = Currency.objects.create(
#             code='USD',
#             name='US Dollar',
#             symbol='$'
#         )
#         self.eur = Currency.objects.create(
#             code='EUR',
#             name='Euro',
#             symbol='€'
#         )
#         ExchangeRate.objects.create(
#             from_currency=self.usd,
#             to_currency=self.eur,
#             rate=Decimal('0.85')
#         )
#
#     def test_valid_conversion_data(self):
#         """Test serializer with valid conversion data."""
#         data = {
#             'from_currency': 'USD',
#             'to_currency': 'EUR',
#             'amount': '100.00'
#         }
#
#         serializer = CurrencyConversionSerializer(data=data)
#         self.assertTrue(serializer.is_valid())
#
#     def test_same_currency_validation(self):
#         """Test serializer rejects same currency conversion."""
#         data = {
#             'from_currency': 'USD',
#             'to_currency': 'USD',
#             'amount': '100.00'
#         }
#
#         serializer = CurrencyConversionSerializer(data=data)
#         self.assertFalse(serializer.is_valid())
#         self.assertIn('non_field_errors', serializer.errors)
#
#     def test_negative_amount_validation(self):
#         """Test serializer rejects negative amounts."""
#         data = {
#             'from_currency': 'USD',
#             'to_currency': 'EUR',
#             'amount': '-100.00'
#         }
#
#         serializer = CurrencyConversionSerializer(data=data)
#         self.assertFalse(serializer.is_valid())
#         self.assertIn('amount', serializer.errors)
#
#
class CurrencyAPITest(APITestCase):
    """Test cases for Currency API endpoints."""

    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123',
            username='test@example.com',
        )
        self.usd = Currency.objects.create(
            code='USD',
            name='US Dollar',
            symbol='$'
        )
        self.eur = Currency.objects.create(
            code='EUR',
            name='Euro',
            symbol='€'
        )
        self.exchange_rate = ExchangeRate.objects.create(
            from_currency=self.usd,
            to_currency=self.eur,
            rate=Decimal('0.85')
        )

        # Create JWT token
        refresh = RefreshToken.for_user(self.user)
        self.access_token = str(refresh.access_token)

        self.client = APIClient()
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.access_token}')

    def test_list_currencies(self):
        """Test listing currencies."""
        url = '/api/currency/currencies/'
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 2)

        codes = [currency['code'] for currency in response.data['results']]
        self.assertIn('USD', codes)
        self.assertIn('EUR', codes)

    # def test_currency_detail(self):
    #     """Test retrieving currency details."""
    #     url = f'/api/currency/currencies/{self.currency.code}'
    #     response = self.client.get(url)
    #
    #     self.assertEqual(response.status_code, status.HTTP_200_OK)
    #     self.assertEqual(response.data['code'], 'USD')
    #     self.assertEqual(response.data['name'], 'US Dollar')

    def test_list_exchange_rates(self):
        """Test listing exchange rates."""
        url = '/api/currency/rates/'
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)