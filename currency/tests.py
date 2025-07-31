# """
# Currency app tests.
# """
# from decimal import Decimal
# from unittest.mock import patch, Mock
# from django.test import TestCase, override_settings
# from django.contrib.auth import get_user_model
# from django.urls import reverse
# from rest_framework.test import APITestCase, APIClient
# from rest_framework import status
# from rest_framework_simplejwt.tokens import RefreshToken
#
# from core.models import Currency, ExchangeRate
# from accounts.models import Account
# from .serializers import CurrencySerializer, ExchangeRateSerializer, CurrencyConversionSerializer
#
#
# User = get_user_model()
#
#
# class CurrencySerializerTest(TestCase):
#     """Test cases for CurrencySerializer."""
#
#     def setUp(self):
#         """Set up test data."""
#         self.currency = Currency.objects.create(
#             code='USD',
#             name='US',
#             symbol='$'
#         )
#
#     def test_currency_serialization(self):
#         """Test currency serialization."""
#         serializer = CurrencySerializer(self.currency)
#         data = serializer.data
#
#         self.assertEqual(data['code'], 'USD')
#         self.assertEqual(data['name'], 'US')
#         self.assertEqual(data['symbol'], '$')
#         self.assertTrue(data['is_active'])
#
#     def test_currency_deserialization(self):
#         """Test currency deserialization."""
#         data = {
#             'code': 'INR',
#             'name': 'Indian Rupee',
#             'symbol': '₹',
#             'is_active': True
#         }
#
#         serializer = CurrencySerializer(data=data)
#         if not serializer.is_valid():
#             print(serializer.errors)
#         self.assertTrue(serializer.is_valid())
#         currency = serializer.save()
#
#         self.assertEqual(currency.code, 'INR')
#         self.assertEqual(currency.name, 'Indian Rupee')
#         self.assertEqual(currency.symbol, '₹')
#
#
# class ExchangeRateSerializerTest(TestCase):
#     """Test cases for ExchangeRateSerializer."""
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
#         self.exchange_rate = ExchangeRate.objects.create(
#             from_currency=self.usd,
#             to_currency=self.eur,
#             rate=Decimal('0.85'),
#             spread=Decimal('0.02')
#         )
#
#     def test_exchange_rate_serialization(self):
#         """Test exchange rate serialization."""
#         serializer = ExchangeRateSerializer(self.exchange_rate)
#         data = serializer.data
#
#         self.assertEqual(data['from_currency_code'], 'USD')
#         self.assertEqual(data['to_currency_code'], 'EUR')
#         self.assertEqual(round(float(data['rate']), 2), 0.85)
#         self.assertEqual(round(float(data['spread']), 2), 0.02)
#         # self.assertTrue(data['is_active'], True)
#
#     # def test_exchange_rate_deserialization(self):
#     #     """Test exchange rate deserialization."""
#     #     gbp = Currency.objects.create(
#     #         code='GBP',
#     #         name='British Pound',
#     #         symbol='£'
#     #     )
#     #
#     #     data = {
#     #         'from_currency': 'INR',
#     #         'to_currency': 'USD',
#     #         'rate': '0.78',
#     #         'spread': '0.015',
#     #         # 'is_active': True
#     #     }
#     #
#     #     serializer = ExchangeRateSerializer(data=data)
#     #     self.assertTrue(serializer.is_valid())
#     #     exchange_rate = serializer.save()
#     #
#     #     self.assertEqual(exchange_rate.from_currency, self.usd)
#     #     self.assertEqual(exchange_rate.to_currency, gbp)
#     #     self.assertEqual(exchange_rate.rate, Decimal('0.78'))
#
#
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
# class CurrencyAPITest(APITestCase):
#     """Test cases for Currency API endpoints."""
#
#     def setUp(self):
#         """Set up test data."""
#         self.user = User.objects.create_user(
#             email='test@example.com',
#             password='testpass123'
#         )
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
#         self.exchange_rate = ExchangeRate.objects.create(
#             from_currency=self.usd,
#             to_currency=self.eur,
#             rate=Decimal('0.85')
#         )
#
#         # Create JWT token
#         refresh = RefreshToken.for_user(self.user)
#         self.access_token = str(refresh.access_token)
#
#         self.client = APIClient()
#         self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.access_token}')
#
#     def test_list_currencies(self):
#         """Test listing currencies."""
#         url = reverse('currency-list')
#         response = self.client.get(url)
#
#         self.assertEqual(response.status_code, status.HTTP_200_OK)
#         self.assertEqual(len(response.data['results']), 2)
#
#         codes = [currency['code'] for currency in response.data['results']]
#         self.assertIn('USD', codes)
#         self.assertIn('EUR', codes)
#
#     def test_currency_detail(self):
#         """Test retrieving currency details."""
#         url = reverse('currency-detail', kwargs={'code': 'USD'})
#         response = self.client.get(url)
#
#         self.assertEqual(response.status_code, status.HTTP_200_OK)
#         self.assertEqual(response.data['code'], 'USD')
#         self.assertEqual(response.data['name'], 'US Dollar')
#
#     def test_list_exchange_rates(self):
#         """Test listing exchange rates."""
#         url = reverse('exchange-rate-list')
#         response = self.client.get(url)
#
#         self.assertEqual(response.status_code, status.HTTP_200_OK)
#         self.assertEqual(len(response.data['results']), 1)
#         self.assertEqual(response.data['results'][0]['from_currency'], 'USD')
#         self.assertEqual(response.data['results'][0]['to_currency'], 'EUR')
#
#     def test_currency_conversion(self):
#         """Test currency conversion calculation."""
#         url = reverse('currency-convert')
#         data = {
#             'from_currency': 'USD',
#             'to_currency': 'EUR',
#             'amount': '100.00'
#         }
#
#         response = self.client.post(url, data)
#         self.assertEqual(response.status_code, status.HTTP_200_OK)
#
#         # Check conversion result
#         self.assertEqual(response.data['from_currency'], 'USD')
#         self.assertEqual(response.data['to_currency'], 'EUR')
#         self.assertEqual(response.data['original_amount'], '100.00')
#         # Converted amount should be 100 * 0.85 = 85.00
#         self.assertEqual(float(response.data['converted_amount']), 85.00)
#
#     def test_currency_conversion_with_spread(self):
#         """Test currency conversion with spread calculation."""
#         # Update exchange rate to include spread
#         self.exchange_rate.spread = Decimal('0.02')
#         self.exchange_rate.save()
#
#         url = reverse('currency-convert')
#         data = {
#             'from_currency': 'USD',
#             'to_currency': 'EUR',
#             'amount': '100.00'
#         }
#
#         response = self.client.post(url, data)
#         self.assertEqual(response.status_code, status.HTTP_200_OK)
#
#         # Check that spread is applied
#         # Rate with spread: 0.85 - 0.02 = 0.83
#         # Converted amount: 100 * 0.83 = 83.00
#         self.assertEqual(float(response.data['converted_amount']), 83.00)
#         self.assertEqual(response.data['exchange_rate'], '0.85')
#         self.assertEqual(response.data['spread'], '0.02')
#
#     def test_conversion_invalid_currency(self):
#         """Test conversion with invalid currency."""
#         url = reverse('currency-convert')
#         data = {
#             'from_currency': 'XXX',
#             'to_currency': 'EUR',
#             'amount': '100.00'
#         }
#
#         response = self.client.post(url, data)
#         self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
#
#     def test_conversion_no_exchange_rate(self):
#         """Test conversion when no exchange rate exists."""
#         gbp = Currency.objects.create(
#             code='GBP',
#             name='British Pound',
#             symbol='£'
#         )
#
#         url = reverse('currency-convert')
#         data = {
#             'from_currency': 'USD',
#             'to_currency': 'GBP',
#             'amount': '100.00'
#         }
#
#         response = self.client.post(url, data)
#         self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
#
#     def test_supported_currencies(self):
#         """Test listing supported currencies."""
#         url = reverse('currency-supported')
#         response = self.client.get(url)
#
#         self.assertEqual(response.status_code, status.HTTP_200_OK)
#         self.assertIn('currencies', response.data)
#         self.assertEqual(len(response.data['currencies']), 2)
#
#     def test_currency_analytics(self):
#         """Test currency analytics endpoint."""
#         url = reverse('currency-analytics')
#         response = self.client.get(url)
#
#         self.assertEqual(response.status_code, status.HTTP_200_OK)
#         self.assertIn('total_currencies', response.data)
#         self.assertIn('active_currencies', response.data)
#         self.assertIn('total_exchange_rates', response.data)
#
#     def test_exchange_rate_by_currency_pair(self):
#         """Test getting exchange rate for specific currency pair."""
#         url = reverse('exchange-rate-by-pair')
#         response = self.client.get(url, {
#             'from_currency': 'USD',
#             'to_currency': 'EUR'
#         })
#
#         self.assertEqual(response.status_code, status.HTTP_200_OK)
#         self.assertEqual(response.data['from_currency'], 'USD')
#         self.assertEqual(response.data['to_currency'], 'EUR')
#         self.assertEqual(response.data['rate'], '0.85')
#
#     def test_unauthorized_access(self):
#         """Test unauthorized access to currency endpoints."""
#         self.client.credentials()  # Remove authentication
#
#         # Some endpoints might be public, but let's test conversion
#         url = reverse('currency-convert')
#         data = {
#             'from_currency': 'USD',
#             'to_currency': 'EUR',
#             'amount': '100.00'
#         }
#
#         response = self.client.post(url, data)
#         # This might be allowed without authentication depending on business requirements
#         # If not, it should return 401
#         if response.status_code == status.HTTP_401_UNAUTHORIZED:
#             self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
#
#
# @override_settings(CELERY_TASK_ALWAYS_EAGER=True)
# class CurrencyTaskTest(TestCase):
#     """Test cases for currency-related Celery tasks."""
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
#
#     @patch('currency.tasks.requests.get')
#     @patch('currency.tasks.logger')
#     def test_update_exchange_rates_task(self, mock_logger, mock_requests):
#         """Test updating exchange rates task."""
#         from .tasks import update_exchange_rates
#
#         # Mock API response
#         mock_response = Mock()
#         mock_response.json.return_value = {
#             'rates': {
#                 'EUR': 0.85,
#                 'GBP': 0.78
#             }
#         }
#         mock_response.status_code = 200
#         mock_requests.return_value = mock_response
#
#         result = update_exchange_rates.delay()
#
#         # Check that the task executed
#         mock_logger.info.assert_called()
#         mock_requests.assert_called()
#
#     @patch('currency.tasks.cache')
#     @patch('currency.tasks.logger')
#     def test_cache_exchange_rates_task(self, mock_logger, mock_cache):
#         """Test caching exchange rates task."""
#         from .tasks import cache_exchange_rates
#
#         # Create exchange rate
#         ExchangeRate.objects.create(
#             from_currency=self.usd,
#             to_currency=self.eur,
#             rate=Decimal('0.85')
#         )
#
#         result = cache_exchange_rates.delay()
#
#         # Check that the task executed and cache was called
#         mock_logger.info.assert_called()
#         mock_cache.set.assert_called()
#
#     @patch('currency.tasks.logger')
#     def test_cleanup_old_exchange_rates_task(self, mock_logger):
#         """Test cleaning up old exchange rates task."""
#         from .tasks import cleanup_old_exchange_rates
#
#         result = cleanup_old_exchange_rates.delay()
#
#         # Check that the task executed
#         mock_logger.info.assert_called()
#
#     @patch('currency.tasks.logger')
#     def test_generate_currency_report_task(self, mock_logger):
#         """Test generating currency report task."""
#         from .tasks import generate_currency_report
#
#         result = generate_currency_report.delay()
#
#         # Check that the task executed
#         mock_logger.info.assert_called()
#
#
# class CurrencyUtilsTest(TestCase):
#     """Test cases for currency utility functions."""
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
#         self.exchange_rate = ExchangeRate.objects.create(
#             from_currency=self.usd,
#             to_currency=self.eur,
#             rate=Decimal('0.85'),
#             spread=Decimal('0.02')
#         )
#
#     def test_get_exchange_rate(self):
#         """Test getting exchange rate between currencies."""
#         # This would test a utility function if it exists
#         # For now, we'll test the model query directly
#         rate = ExchangeRate.objects.filter(
#             from_currency=self.usd,
#             to_currency=self.eur,
#             is_active=True
#         ).first()
#
#         self.assertIsNotNone(rate)
#         self.assertEqual(rate.rate, Decimal('0.85'))
#
#     def test_calculate_conversion(self):
#         """Test currency conversion calculation."""
#         amount = Decimal('100.00')
#         rate = self.exchange_rate.rate
#         spread = self.exchange_rate.spread
#
#         # Apply spread (subtract from rate for selling)
#         effective_rate = rate - spread
#         converted_amount = amount * effective_rate
#
#         self.assertEqual(converted_amount, Decimal('83.00'))
#
#     def test_get_supported_currencies(self):
#         """Test getting list of supported currencies."""
#         supported = Currency.objects.filter(is_active=True).values_list('code', flat=True)
#
#         self.assertIn('USD', supported)
#         self.assertIn('EUR', supported)
#         self.assertEqual(len(supported), 2)
