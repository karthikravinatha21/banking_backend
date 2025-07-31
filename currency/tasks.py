from celery import shared_task
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone
from decimal import Decimal
import requests
import logging

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def update_exchange_rates_from_api(self):
    """Update exchange rates from external API"""
    try:
        from core.models import Currency, ExchangeRate
        
        # Get API configuration
        api_key = getattr(settings, 'EXCHANGE_RATES_API_KEY', None)
        api_url = getattr(settings, 'EXCHANGE_RATES_API_URL', 'https://api.exchangeratesapi.io/v1/latest')
        
        if not api_key:
            logger.warning("Exchange rates API key not configured")
            return "API key not configured"
        
        # Fetch rates from external API
        response = requests.get(
            api_url,
            params={'access_key': api_key},
            timeout=30
        )
        
        if response.status_code != 200:
            logger.error(f"API request failed with status {response.status_code}")
            raise Exception(f"API request failed: {response.status_code}")
        
        data = response.json()
        
        if not data.get('success', False):
            error_msg = data.get('error', {}).get('info', 'Unknown API error')
            logger.error(f"API returned error: {error_msg}")
            raise Exception(f"API error: {error_msg}")
        
        base_currency_code = data.get('base', 'EUR')
        rates = data.get('rates', {})
        
        if not rates:
            logger.warning("No exchange rates received from API")
            return "No rates received"
        
        # Get or create base currency
        base_currency, created = Currency.objects.get_or_create(
            code=base_currency_code,
            defaults={
                'name': base_currency_code,
                'symbol': base_currency_code,
                'is_active': True
            }
        )
        
        updated_count = 0
        
        # Update exchange rates
        for currency_code, rate in rates.items():
            try:
                # Get or create target currency
                target_currency, created = Currency.objects.get_or_create(
                    code=currency_code,
                    defaults={
                        'name': currency_code,
                        'symbol': currency_code,
                        'is_active': True
                    }
                )
                
                # Skip if same currency
                if base_currency.code == target_currency.code:
                    continue
                
                # Update or create exchange rate
                exchange_rate, created = ExchangeRate.objects.get_or_create(
                    from_currency=base_currency,
                    to_currency=target_currency,
                    defaults={
                        'rate': Decimal(str(rate)),
                        'spread': Decimal('0.01'),  # 1% default spread
                        'is_active': True
                    }
                )
                
                if not created:
                    exchange_rate.rate = Decimal(str(rate))
                    exchange_rate.updated_at = timezone.now()
                    exchange_rate.save()
                
                # Clear cache for this rate
                cache_key = f'exchange_rate_{base_currency.code}_{target_currency.code}'
                cache.delete(cache_key)
                
                # Also clear reverse rate cache
                reverse_cache_key = f'exchange_rate_{target_currency.code}_{base_currency.code}'
                cache.delete(reverse_cache_key)
                
                updated_count += 1
                
            except Exception as exc:
                logger.error(f"Error updating rate for {currency_code}: {str(exc)}")
                continue
        
        # Clear all exchange rate cache patterns
        cache.delete_pattern('exchange_rate_*')
        
        logger.info(f"Updated {updated_count} exchange rates from external API")
        return f"Updated {updated_count} exchange rates"
        
    except requests.RequestException as exc:
        logger.error(f"Network error updating exchange rates: {str(exc)}")
        raise self.retry(exc=exc, countdown=300)  # Retry after 5 minutes
        
    except Exception as exc:
        logger.error(f"Error updating exchange rates: {str(exc)}")
        raise self.retry(exc=exc, countdown=60)


@shared_task
def cache_popular_exchange_rates():
    """Pre-cache popular exchange rate pairs"""
    try:
        from core.models import ExchangeRate
        
        # Popular currency pairs to cache
        popular_pairs = [
            ('USD', 'EUR'), ('EUR', 'USD'),
            ('USD', 'GBP'), ('GBP', 'USD'),
            ('USD', 'JPY'), ('JPY', 'USD'),
            ('EUR', 'GBP'), ('GBP', 'EUR'),
            ('USD', 'CAD'), ('CAD', 'USD'),
            ('USD', 'AUD'), ('AUD', 'USD'),
        ]
        
        cached_count = 0
        
        for from_code, to_code in popular_pairs:
            try:
                exchange_rate = ExchangeRate.objects.get(
                    from_currency__code=from_code,
                    to_currency__code=to_code,
                    is_active=True
                )
                
                cache_key = f'exchange_rate_{from_code}_{to_code}'
                rate_data = {
                    'rate': exchange_rate.rate,
                    'spread': exchange_rate.spread,
                    'timestamp': timezone.now()
                }
                
                # Cache for 1 hour
                cache.set(cache_key, rate_data, 3600)
                cached_count += 1
                
            except ExchangeRate.DoesNotExist:
                continue
        
        logger.info(f"Cached {cached_count} popular exchange rates")
        return f"Cached {cached_count} rates"
        
    except Exception as exc:
        logger.error(f"Error caching exchange rates: {str(exc)}")
        return f"Error: {str(exc)}"


@shared_task
def cleanup_old_currency_conversions():
    """Clean up old currency conversion records"""
    try:
        from .models import CurrencyConversion
        from datetime import timedelta
        
        # Delete conversion records older than 90 days
        cutoff_date = timezone.now() - timedelta(days=90)
        
        old_conversions = CurrencyConversion.objects.filter(
            created_at__lt=cutoff_date
        )
        
        count = old_conversions.count()
        old_conversions.delete()
        
        logger.info(f"Cleaned up {count} old currency conversion records")
        return f"Cleaned up {count} conversion records"
        
    except Exception as exc:
        logger.error(f"Error cleaning up currency conversions: {str(exc)}")
        return f"Error: {str(exc)}"


@shared_task
def monitor_exchange_rate_changes():
    """Monitor for significant exchange rate changes"""
    try:
        from core.models import ExchangeRate
        from accounts.models import User
        from django.core.mail import send_mail
        from decimal import Decimal
        
        # Check for rates that changed more than 5% in the last update
        significant_changes = []
        
        # Get rates updated in the last hour
        recent_time = timezone.now() - timezone.timedelta(hours=1)
        recent_rates = ExchangeRate.objects.filter(
            updated_at__gte=recent_time,
            is_active=True
        )
        
        for rate in recent_rates:
            # Get previous rate from cache or estimate
            cache_key = f'previous_rate_{rate.from_currency.code}_{rate.to_currency.code}'
            previous_rate = cache.get(cache_key)
            
            if previous_rate:
                change_percent = abs((rate.rate - previous_rate) / previous_rate * 100)
                
                if change_percent >= 5:  # 5% change threshold
                    significant_changes.append({
                        'pair': f'{rate.from_currency.code}/{rate.to_currency.code}',
                        'old_rate': previous_rate,
                        'new_rate': rate.rate,
                        'change_percent': change_percent
                    })
            
            # Update cache with current rate
            cache.set(cache_key, rate.rate, 86400)  # Cache for 24 hours
        
        # Send alerts if significant changes detected
        if significant_changes:
            admin_emails = User.objects.filter(is_staff=True).values_list('email', flat=True)
            
            if admin_emails:
                alert_message = "Significant exchange rate changes detected:\n\n"
                
                for change in significant_changes:
                    alert_message += (
                        f"- {change['pair']}: {change['old_rate']} → {change['new_rate']} "
                        f"({change['change_percent']:.2f}% change)\n"
                    )
                
                send_mail(
                    subject='Exchange Rate Alert - Significant Changes Detected',
                    message=alert_message,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=list(admin_emails),
                    fail_silently=False,
                )
                
                logger.warning(f"Exchange rate alert sent for {len(significant_changes)} currency pairs")
        
        return f"Monitored rates, found {len(significant_changes)} significant changes"
        
    except Exception as exc:
        logger.error(f"Error monitoring exchange rate changes: {str(exc)}")
        return f"Error: {str(exc)}"


@shared_task
def update_currency_metadata():
    """Update currency metadata from external sources"""
    try:
        from core.models import Currency
        
        # Currency metadata (in a real system, this might come from an API)
        currency_metadata = {
            'USD': {'name': 'US Dollar', 'symbol': '$'},
            'EUR': {'name': 'Euro', 'symbol': '€'},
            'GBP': {'name': 'British Pound', 'symbol': '£'},
            'JPY': {'name': 'Japanese Yen', 'symbol': '¥'},
            'CAD': {'name': 'Canadian Dollar', 'symbol': 'C$'},
            'AUD': {'name': 'Australian Dollar', 'symbol': 'A$'},
            'CHF': {'name': 'Swiss Franc', 'symbol': 'CHF'},
            'CNY': {'name': 'Chinese Yuan', 'symbol': '¥'},
            'SEK': {'name': 'Swedish Krona', 'symbol': 'kr'},
            'NZD': {'name': 'New Zealand Dollar', 'symbol': 'NZ$'},
        }
        
        updated_count = 0
        
        for code, metadata in currency_metadata.items():
            try:
                currency = Currency.objects.get(code=code)
                
                # Update if metadata is different
                if currency.name != metadata['name'] or currency.symbol != metadata['symbol']:
                    currency.name = metadata['name']
                    currency.symbol = metadata['symbol']
                    currency.save()
                    updated_count += 1
                    
            except Currency.DoesNotExist:
                # Create new currency if it doesn't exist
                Currency.objects.create(
                    code=code,
                    name=metadata['name'],
                    symbol=metadata['symbol'],
                    is_active=True
                )
                updated_count += 1
        
        logger.info(f"Updated metadata for {updated_count} currencies")
        return f"Updated {updated_count} currency metadata"
        
    except Exception as exc:
        logger.error(f"Error updating currency metadata: {str(exc)}")
        return f"Error: {str(exc)}"


@shared_task
def generate_currency_conversion_report():
    """Generate daily currency conversion report"""
    try:
        from .models import CurrencyConversion
        from accounts.models import User
        from django.core.mail import EmailMessage
        from datetime import date, timedelta
        from io import StringIO
        import csv
        
        yesterday = date.today() - timedelta(days=1)
        
        # Get conversion statistics
        conversions = CurrencyConversion.objects.filter(
            created_at__date=yesterday
        )
        
        if not conversions.exists():
            logger.info("No currency conversions for yesterday")
            return "No conversions to report"
        
        stats = {
            'date': yesterday.strftime('%Y-%m-%d'),
            'total_conversions': conversions.count(),
            'total_volume': sum(conv.amount for conv in conversions),
            'average_amount': sum(conv.amount for conv in conversions) / conversions.count(),
            'by_currency_pair': {}
        }
        
        # Group by currency pairs
        for conversion in conversions:
            pair = f"{conversion.from_currency.code}/{conversion.to_currency.code}"
            if pair not in stats['by_currency_pair']:
                stats['by_currency_pair'][pair] = {
                    'count': 0,
                    'volume': Decimal('0')
                }
            stats['by_currency_pair'][pair]['count'] += 1
            stats['by_currency_pair'][pair]['volume'] += conversion.amount
        
        # Create CSV report
        csv_buffer = StringIO()
        writer = csv.writer(csv_buffer)
        
        # Write header
        writer.writerow(['Metric', 'Value'])
        writer.writerow(['Date', stats['date']])
        writer.writerow(['Total Conversions', stats['total_conversions']])
        writer.writerow(['Total Volume', f"{stats['total_volume']:.2f}"])
        writer.writerow(['Average Amount', f"{stats['average_amount']:.2f}"])
        writer.writerow(['', ''])
        writer.writerow(['Currency Pair', 'Count', 'Volume'])
        
        for pair, data in stats['by_currency_pair'].items():
            writer.writerow([pair, data['count'], f"{data['volume']:.2f}"])
        
        # Send email to admins
        admin_emails = User.objects.filter(is_staff=True).values_list('email', flat=True)
        
        if admin_emails:
            email = EmailMessage(
                subject=f'Daily Currency Conversion Report - {yesterday}',
                body=f'Please find attached the daily currency conversion report for {yesterday}.',
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=list(admin_emails),
            )
            
            email.attach(
                f'currency_conversion_report_{yesterday}.csv',
                csv_buffer.getvalue(),
                'text/csv'
            )
            
            email.send()
            logger.info(f"Daily currency conversion report sent for {yesterday}")
        
        return stats
        
    except Exception as exc:
        logger.error(f"Error generating currency conversion report: {str(exc)}")
        return f"Error: {str(exc)}"
