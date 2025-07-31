from rest_framework import generics, status, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.views import APIView
from django.shortcuts import get_object_or_404
from django.core.cache import cache
from django.utils import timezone
from django_ratelimit.decorators import ratelimit
from django.utils.decorators import method_decorator
from django.db.models import Count, Sum, Avg
from decimal import Decimal

# from .models import CurrencyConversion
from .serializers import (
    CurrencySerializer, ExchangeRateSerializer, CurrencyConversionSerializer,
    ConvertCurrencySerializer, ExchangeRateUpdateSerializer, CurrencyTransferSerializer
)
from core.models import Currency, ExchangeRate
from accounts.permissions import IsAdminUser
from .tasks import update_exchange_rates_from_api
import logging

logger = logging.getLogger(__name__)


class CurrencyListView(generics.ListAPIView):
    queryset = Currency.objects.filter(is_active=True)
    serializer_class = CurrencySerializer
    permission_classes = [permissions.AllowAny]  # Public endpoint for currency list


class CurrencyDetailView(generics.RetrieveAPIView):
    queryset = Currency.objects.filter(is_active=True)
    serializer_class = CurrencySerializer
    permission_classes = [permissions.AllowAny]
    lookup_field = 'code'


class ExchangeRateListView(generics.ListAPIView):
    serializer_class = ExchangeRateSerializer
    permission_classes = [permissions.AllowAny]
    
    def get_queryset(self):
        queryset = ExchangeRate.objects.filter(is_active=True)
        
        # Filter by currencies
        from_currency = self.request.query_params.get('from_currency')
        to_currency = self.request.query_params.get('to_currency')
        
        if from_currency:
            queryset = queryset.filter(from_currency__code=from_currency.upper())
        
        if to_currency:
            queryset = queryset.filter(to_currency__code=to_currency.upper())
        
        return queryset.select_related('from_currency', 'to_currency').order_by(
            'from_currency__code', 'to_currency__code'
        )


class CurrencyConvertView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    
    @method_decorator(ratelimit(key='user', rate='20/m', method='POST'))
    def post(self, request):
        serializer = ConvertCurrencySerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        
        conversion = serializer.save()
        
        return Response({
            'conversion': CurrencyConversionSerializer(conversion).data,
            'message': 'Currency converted successfully'
        }, status=status.HTTP_201_CREATED)


@api_view(['GET'])
@permission_classes([permissions.AllowAny])
def get_cached_exchange_rate(request, from_currency, to_currency):
    """Get cached exchange rate between two currencies"""
    from_currency = from_currency.upper()
    to_currency = to_currency.upper()
    
    if from_currency == to_currency:
        return Response({
            'from_currency': from_currency,
            'to_currency': to_currency,
            'rate': 1.0,
            'cached': False,
            'timestamp': timezone.now()
        })
    
    # Check cache first
    cache_key = f'exchange_rate_{from_currency}_{to_currency}'
    cached_rate = cache.get(cache_key)
    
    if cached_rate:
        return Response({
            'from_currency': from_currency,
            'to_currency': to_currency,
            'rate': cached_rate['rate'],
            'spread': cached_rate.get('spread', 0),
            'cached': True,
            'timestamp': cached_rate['timestamp']
        })
    
    # Get from database
    try:
        exchange_rate = ExchangeRate.objects.get(
            from_currency__code=from_currency,
            to_currency__code=to_currency,
            is_active=True
        )
        rate_data = {
            'rate': exchange_rate.rate,
            'spread': exchange_rate.spread,
            'timestamp': timezone.now()
        }
    except ExchangeRate.DoesNotExist:
        # Try reverse conversion
        try:
            exchange_rate = ExchangeRate.objects.get(
                from_currency__code=to_currency,
                to_currency__code=from_currency,
                is_active=True
            )
            rate_data = {
                'rate': 1 / exchange_rate.rate,
                'spread': exchange_rate.spread,
                'timestamp': timezone.now()
            }
        except ExchangeRate.DoesNotExist:
            return Response(
                {'error': f'Exchange rate not found for {from_currency} to {to_currency}'},
                status=status.HTTP_404_NOT_FOUND
            )
    
    # Cache for 5 minutes
    cache.set(cache_key, rate_data, 300)
    
    return Response({
        'from_currency': from_currency,
        'to_currency': to_currency,
        'rate': rate_data['rate'],
        'spread': rate_data.get('spread', 0),
        'cached': False,
        'timestamp': rate_data['timestamp']
    })


@api_view(['GET'])
@permission_classes([permissions.AllowAny])
def currency_conversion_calculator(request):
    """Simple currency conversion calculator"""
    from_currency = request.query_params.get('from', '').upper()
    to_currency = request.query_params.get('to', '').upper()
    amount = request.query_params.get('amount', '1')
    
    if not from_currency or not to_currency:
        return Response(
            {'error': 'from and to currency parameters are required'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        amount = Decimal(str(amount))
        if amount <= 0:
            raise ValueError("Amount must be positive")
    except (ValueError, TypeError):
        return Response(
            {'error': 'Invalid amount'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Get exchange rate
    cache_key = f'exchange_rate_{from_currency}_{to_currency}'
    cached_rate = cache.get(cache_key)
    
    if cached_rate:
        rate = cached_rate['rate']
        spread = cached_rate.get('spread', Decimal('0'))
    else:
        try:
            exchange_rate = ExchangeRate.objects.get(
                from_currency__code=from_currency,
                to_currency__code=to_currency,
                is_active=True
            )
            rate = exchange_rate.rate
            spread = exchange_rate.spread or Decimal('0')
        except ExchangeRate.DoesNotExist:
            # Try reverse conversion
            try:
                exchange_rate = ExchangeRate.objects.get(
                    from_currency__code=to_currency,
                    to_currency__code=from_currency,
                    is_active=True
                )
                rate = Decimal('1') / exchange_rate.rate
                spread = exchange_rate.spread or Decimal('0')
            except ExchangeRate.DoesNotExist:
                return Response(
                    {'error': f'Exchange rate not found for {from_currency} to {to_currency}'},
                    status=status.HTTP_404_NOT_FOUND
                )
        
        # Cache the rate
        cache.set(cache_key, {
            'rate': rate,
            'spread': spread,
            'timestamp': timezone.now()
        }, 300)
    
    # Calculate conversion
    base_converted = amount * rate
    
    # Apply spread for large amounts
    if amount > Decimal('10000'):
        spread_applied = spread
        final_rate = rate * (Decimal('1') - spread)
        final_converted = amount * final_rate
    else:
        spread_applied = Decimal('0')
        final_rate = rate
        final_converted = base_converted
    
    return Response({
        'from_currency': from_currency,
        'to_currency': to_currency,
        'amount': amount,
        'base_rate': rate,
        'spread': spread_applied,
        'final_rate': final_rate,
        'converted_amount': final_converted,
        'timestamp': timezone.now()
    })
