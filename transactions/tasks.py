from celery import shared_task
from django.db import transaction
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings
from decimal import Decimal
import logging
import requests

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def process_external_transfer(self, transfer_id):
    """Process external fund transfer"""
    try:
        from .models import Transfer, Transaction
        from accounts.models import Account
        
        transfer = Transfer.objects.get(id=transfer_id)
        
        if transfer.status != 'PENDING':
            logger.warning(f"Transfer {transfer_id} is not in pending status")
            return
        
        from_account = transfer.from_account
        amount = transfer.amount
        fee_amount = transfer.transfer_fee or Decimal('0')
        total_deduction = amount + fee_amount
        
        # Check if account still has sufficient balance
        if from_account.balance < total_deduction:
            transfer.status = 'FAILED'
            transfer.failure_reason = 'Insufficient balance'
            transfer.save()
            
            # Send notification
            send_transfer_notification.delay(transfer.id, 'FAILED')
            return
        
        with transaction.atomic():
            # Simulate external transfer processing
            # In real implementation, this would call external bank APIs
            external_success = simulate_external_transfer(transfer)
            
            if external_success:
                # Update transfer status
                transfer.status = 'COMPLETED'
                transfer.processed_at = timezone.now()
                transfer.save()
                
                # Create debit transaction for source account
                Transaction.objects.create(
                    account=from_account,
                    transaction_type='DEBIT',
                    amount=total_deduction,
                    description=f"External transfer to {transfer.metadata.get('beneficiary_name', 'External Account')}",
                    reference_number=transfer.reference_number,
                    balance_before=from_account.balance,
                    balance_after=from_account.balance - total_deduction,
                    status='COMPLETED',
                    tenant_id=from_account.tenant_id
                )
                
                # Update account balance
                from_account.balance -= total_deduction
                from_account.save(update_fields=['balance', 'updated_at'])
                
                logger.info(f"External transfer {transfer_id} completed successfully")
                
                # Send success notification
                send_transfer_notification.delay(transfer.id, 'COMPLETED')
                
            else:
                transfer.status = 'FAILED'
                transfer.failure_reason = 'External bank processing failed'
                transfer.save()
                
                # Send failure notification
                send_transfer_notification.delay(transfer.id, 'FAILED')
                
                logger.error(f"External transfer {transfer_id} failed")
        
    except Exception as exc:
        logger.error(f"Error processing external transfer {transfer_id}: {str(exc)}")
        
        # Update transfer status to failed after max retries
        if self.request.retries >= self.max_retries:
            try:
                transfer = Transfer.objects.get(id=transfer_id)
                transfer.status = 'FAILED'
                transfer.failure_reason = 'Processing error after multiple attempts'
                transfer.save()
                send_transfer_notification.delay(transfer.id, 'FAILED')
            except:
                pass
        
        raise self.retry(exc=exc, countdown=60)


def simulate_external_transfer(transfer):
    """Simulate external bank transfer processing"""
    # In real implementation, this would integrate with external bank APIs
    # For now, we'll simulate with a simple success rate
    import random
    return random.random() > 0.1  # 90% success rate


@shared_task
def send_transfer_notification(transfer_id, status):
    """Send transfer status notification to user"""
    try:
        from .models import Transfer
        
        transfer = Transfer.objects.get(id=transfer_id)
        user = transfer.from_account.user
        
        if status == 'COMPLETED':
            subject = 'Transfer Completed Successfully'
            message = f'Your transfer of {transfer.amount} to {transfer.metadata.get("beneficiary_name", "External Account")} has been completed successfully.'
        else:
            subject = 'Transfer Failed'
            message = f'Your transfer of {transfer.amount} has failed. Reason: {getattr(transfer, "failure_reason", "Unknown error")}'
        
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=False,
        )
        
        logger.info(f"Transfer notification sent to {user.email} for transfer {transfer_id}")
        
    except Exception as exc:
        logger.error(f"Failed to send transfer notification: {str(exc)}")


@shared_task
def process_scheduled_transactions():
    """Process scheduled transactions that are due"""
    try:
        from .models import ScheduledTransaction, Transfer, Transaction
        from django.utils import timezone
        
        now = timezone.now()
        due_transactions = ScheduledTransaction.objects.filter(
            is_active=True,
            next_execution__lte=now
        )
        
        processed_count = 0
        
        for scheduled_txn in due_transactions:
            try:
                with transaction.atomic():
                    # Check if accounts are still active and have sufficient balance
                    if not scheduled_txn.from_account.is_active or not scheduled_txn.to_account.is_active:
                        scheduled_txn.is_active = False
                        scheduled_txn.save()
                        continue
                    
                    if scheduled_txn.from_account.balance < scheduled_txn.amount:
                        # Skip this execution, will try again next time
                        logger.warning(f"Insufficient balance for scheduled transaction {scheduled_txn.id}")
                        scheduled_txn.calculate_next_execution()
                        scheduled_txn.save()
                        continue
                    
                    # Create transfer
                    transfer = Transfer.objects.create(
                        from_account=scheduled_txn.from_account,
                        to_account=scheduled_txn.to_account,
                        amount=scheduled_txn.amount,
                        description=f"Scheduled: {scheduled_txn.description}",
                        transfer_type='INTERNAL',
                        status='COMPLETED',
                        tenant_id=scheduled_txn.from_account.tenant_id
                    )
                    
                    # Create transactions
                    Transaction.objects.create(
                        account=scheduled_txn.from_account,
                        transaction_type='DEBIT',
                        amount=scheduled_txn.amount,
                        description=f"Scheduled transfer to {scheduled_txn.to_account.account_number}",
                        reference_number=transfer.reference_number,
                        balance_before=scheduled_txn.from_account.balance,
                        balance_after=scheduled_txn.from_account.balance - scheduled_txn.amount,
                        status='COMPLETED',
                        tenant_id=scheduled_txn.from_account.tenant_id
                    )
                    
                    Transaction.objects.create(
                        account=scheduled_txn.to_account,
                        transaction_type='CREDIT',
                        amount=scheduled_txn.amount,
                        description=f"Scheduled transfer from {scheduled_txn.from_account.account_number}",
                        reference_number=transfer.reference_number,
                        balance_before=scheduled_txn.to_account.balance,
                        balance_after=scheduled_txn.to_account.balance + scheduled_txn.amount,
                        status='COMPLETED',
                        tenant_id=scheduled_txn.to_account.tenant_id
                    )
                    
                    # Update balances
                    scheduled_txn.from_account.balance -= scheduled_txn.amount
                    scheduled_txn.to_account.balance += scheduled_txn.amount
                    scheduled_txn.from_account.save(update_fields=['balance', 'updated_at'])
                    scheduled_txn.to_account.save(update_fields=['balance', 'updated_at'])
                    
                    # Update scheduled transaction
                    scheduled_txn.last_executed = now
                    scheduled_txn.execution_count += 1
                    scheduled_txn.calculate_next_execution()
                    
                    # Check if it should be deactivated
                    if scheduled_txn.end_date and now >= scheduled_txn.end_date:
                        scheduled_txn.is_active = False
                    
                    scheduled_txn.save()
                    processed_count += 1
                    
                    logger.info(f"Scheduled transaction {scheduled_txn.id} processed successfully")
                    
            except Exception as exc:
                logger.error(f"Error processing scheduled transaction {scheduled_txn.id}: {str(exc)}")
                continue
        
        logger.info(f"Processed {processed_count} scheduled transactions")
        return f"Processed {processed_count} scheduled transactions"
        
    except Exception as exc:
        logger.error(f"Error in scheduled transaction processing: {str(exc)}")
        return f"Error: {str(exc)}"


@shared_task
def update_exchange_rates():
    """Update currency exchange rates from external API"""
    try:
        from core.models import ExchangeRate, Currency
        import requests
        
        # Get API key from settings
        api_key = getattr(settings, 'EXCHANGE_RATES_API_KEY', None)
        if not api_key:
            logger.warning("Exchange rates API key not configured")
            return
        
        # Fetch rates from external API
        url = f"https://api.exchangeratesapi.io/v1/latest?access_key={api_key}"
        response = requests.get(url, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            base_currency = data.get('base', 'EUR')
            rates = data.get('rates', {})
            
            updated_count = 0
            
            for currency_code, rate in rates.items():
                try:
                    # Get or create currency
                    currency, created = Currency.objects.get_or_create(
                        code=currency_code,
                        defaults={'name': currency_code, 'is_active': True}
                    )
                    
                    # Update or create exchange rate
                    exchange_rate, created = ExchangeRate.objects.get_or_create(
                        from_currency=Currency.objects.get(code=base_currency),
                        to_currency=currency,
                        defaults={
                            'rate': Decimal(str(rate)),
                            'spread': Decimal('0.01'),  # 1% spread
                            'is_active': True
                        }
                    )
                    
                    if not created:
                        exchange_rate.rate = Decimal(str(rate))
                        exchange_rate.updated_at = timezone.now()
                        exchange_rate.save()
                    
                    updated_count += 1
                    
                except Exception as exc:
                    logger.error(f"Error updating rate for {currency_code}: {str(exc)}")
                    continue
            
            logger.info(f"Updated {updated_count} exchange rates")
            return f"Updated {updated_count} exchange rates"
            
        else:
            logger.error(f"Failed to fetch exchange rates: {response.status_code}")
            return f"API error: {response.status_code}"
            
    except Exception as exc:
        logger.error(f"Error updating exchange rates: {str(exc)}")
        return f"Error: {str(exc)}"


@shared_task
def generate_daily_transaction_report():
    """Generate daily transaction report"""
    try:
        from .models import Transaction, Transfer
        from datetime import date, timedelta
        from django.core.mail import EmailMessage
        from io import StringIO
        import csv
        
        yesterday = date.today() - timedelta(days=1)
        
        # Get transaction statistics
        transactions = Transaction.objects.filter(
            created_at__date=yesterday,
            status='COMPLETED'
        )
        
        transfers = Transfer.objects.filter(
            created_at__date=yesterday,
            status='COMPLETED'
        )
        
        stats = {
            'date': yesterday.strftime('%Y-%m-%d'),
            'total_transactions': transactions.count(),
            'total_transfers': transfers.count(),
            'total_transaction_amount': sum(txn.amount for txn in transactions),
            'total_transfer_amount': sum(trf.amount for trf in transfers),
            'credit_transactions': transactions.filter(transaction_type='CREDIT').count(),
            'debit_transactions': transactions.filter(transaction_type='DEBIT').count(),
            'internal_transfers': transfers.filter(transfer_type='INTERNAL').count(),
            'external_transfers': transfers.filter(transfer_type='EXTERNAL').count(),
        }
        
        # Create CSV report
        csv_buffer = StringIO()
        writer = csv.writer(csv_buffer)
        
        # Write header
        writer.writerow(['Metric', 'Value'])
        for key, value in stats.items():
            writer.writerow([key.replace('_', ' ').title(), value])
        
        # Send email to admins
        from accounts.models import User
        admin_emails = User.objects.filter(is_staff=True).values_list('email', flat=True)
        
        if admin_emails:
            email = EmailMessage(
                subject=f'Daily Transaction Report - {yesterday}',
                body=f'Please find attached the daily transaction report for {yesterday}.',
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=list(admin_emails),
            )
            
            email.attach(
                f'daily_report_{yesterday}.csv',
                csv_buffer.getvalue(),
                'text/csv'
            )
            
            email.send()
            logger.info(f"Daily transaction report sent for {yesterday}")
        
        return stats
        
    except Exception as exc:
        logger.error(f"Error generating daily transaction report: {str(exc)}")
        return f"Error: {str(exc)}"


@shared_task
def cleanup_failed_transactions():
    """Clean up old failed transactions"""
    try:
        from .models import Transaction, Transfer
        from datetime import timedelta
        from django.utils import timezone
        
        # Clean up failed transactions older than 30 days
        cutoff_date = timezone.now() - timedelta(days=30)
        
        old_transactions = Transaction.objects.filter(
            status='FAILED',
            created_at__lt=cutoff_date
        )
        
        old_transfers = Transfer.objects.filter(
            status='FAILED',
            created_at__lt=cutoff_date
        )
        
        transaction_count = old_transactions.count()
        transfer_count = old_transfers.count()
        
        # Archive instead of delete (move to separate table or mark as archived)
        old_transactions.update(status='ARCHIVED')
        old_transfers.update(status='ARCHIVED')
        
        logger.info(f"Archived {transaction_count} transactions and {transfer_count} transfers")
        return f"Archived {transaction_count} transactions and {transfer_count} transfers"
        
    except Exception as exc:
        logger.error(f"Error cleaning up failed transactions: {str(exc)}")
        return f"Error: {str(exc)}"


@shared_task
def monitor_suspicious_transactions():
    """Monitor for suspicious transaction patterns"""
    try:
        from .models import Transaction, Transfer
        from accounts.models import User
        from datetime import timedelta, date
        from django.core.mail import send_mail
        
        today = date.today()
        alerts = []
        
        # Check for unusually high transaction amounts
        high_amount_threshold = Decimal('100000')
        high_transactions = Transaction.objects.filter(
            created_at__date=today,
            amount__gte=high_amount_threshold,
            status='COMPLETED'
        )
        
        if high_transactions.exists():
            alerts.append(f"High amount transactions: {high_transactions.count()}")
        
        # Check for rapid consecutive transactions
        from django.db.models import Count
        rapid_transactions = Transaction.objects.filter(
            created_at__date=today
        ).values('account').annotate(
            count=Count('id')
        ).filter(count__gte=50)  # More than 50 transactions per day
        
        if rapid_transactions.exists():
            alerts.append(f"Accounts with high transaction frequency: {len(rapid_transactions)}")
        
        # Check for failed external transfers
        failed_external = Transfer.objects.filter(
            created_at__date=today,
            transfer_type='EXTERNAL',
            status='FAILED'
        ).count()
        
        if failed_external > 10:
            alerts.append(f"High number of failed external transfers: {failed_external}")
        
        # Send alerts if any suspicious activity found
        if alerts:
            admin_emails = User.objects.filter(is_staff=True).values_list('email', flat=True)
            
            if admin_emails:
                alert_message = f"Suspicious transaction activity detected for {today}:\n\n"
                alert_message += "\n".join(f"- {alert}" for alert in alerts)
                
                send_mail(
                    subject=f'Suspicious Transaction Activity Alert - {today}',
                    message=alert_message,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=list(admin_emails),
                    fail_silently=False,
                )
                
                logger.warning(f"Suspicious activity alert sent: {alerts}")
        
        return alerts if alerts else "No suspicious activity detected"
        
    except Exception as exc:
        logger.error(f"Error monitoring suspicious transactions: {str(exc)}")
        return f"Error: {str(exc)}"
