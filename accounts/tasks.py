from celery import shared_task
from django.core.mail import send_mail
from django.conf import settings
from django.template.loader import render_to_string
from django.utils import timezone
from django.db import transaction
import secrets
import string
import logging

from core.models import Currency

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def send_otp_email(self, user_id, otp_code):
    """Send OTP email to user"""
    try:
        from .models import User
        user = User.objects.get(id=user_id)
        
        subject = 'Your OTP Code - Banking System'
        message = f'Your OTP code is: {otp_code}. This code will expire in 10 minutes.'
        
        # You can create an HTML template for better formatting
        html_message = render_to_string('emails/otp_email.html', {
            'user': user,
            'otp_code': otp_code,
            'expires_in': 10  # minutes
        })
        
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            html_message=html_message,
            fail_silently=False,
        )
        
        logger.info(f"OTP email sent successfully to {user.email}")
        return f"OTP sent to {user.email}"
        
    except User.DoesNotExist:
        logger.error(f"User with ID {user_id} not found")
        raise self.retry(countdown=60)
    except Exception as exc:
        logger.error(f"Failed to send OTP email: {str(exc)}")
        raise self.retry(exc=exc, countdown=60)


@shared_task(bind=True, max_retries=3)
def create_accounts_batch(self, accounts_data, created_by_id):
    """Create multiple accounts in batch"""
    try:
        from .models import User, Account
        created_accounts = []
        
        with transaction.atomic():
            for account_data in accounts_data:
                user = User.objects.get(email=account_data['user_email'])
                currency_code = account_data.get('currency', 'USD')
                account = Account.objects.create(
                    user=user,
                    account_type=account_data['account_type'],
                    currency=Currency.objects.filter(code=currency_code).first(),
                    # tenant_id=getattr(user, 'tenant_id', 1)
                )
                created_accounts.append({
                    'account_number': account.account_number,
                    'user_email': user.email,
                    'account_type': account.account_type
                })
        
        # Send notification email about batch creation
        # if created_by_id:
        #     send_batch_creation_notification.delay(created_by_id, len(created_accounts))
        
        logger.info(f"Batch account creation completed: {len(created_accounts)} accounts created")
        return created_accounts
        
    except Exception as exc:
        logger.error(f"Batch account creation failed: {str(exc)}")
        raise self.retry(exc=exc, countdown=60)


@shared_task
def send_batch_creation_notification(created_by_id, accounts_count):
    """Send notification about batch account creation completion"""
    try:
        from .models import User
        admin_user = User.objects.get(id=created_by_id)
        
        subject = 'Batch Account Creation Completed'
        message = f'Your batch account creation request has been completed. {accounts_count} accounts were created successfully.'
        
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[admin_user.email],
            fail_silently=False,
        )
        
        logger.info(f"Batch creation notification sent to {admin_user.email}")
        
    except Exception as exc:
        logger.error(f"Failed to send batch creation notification: {str(exc)}")


@shared_task
def cleanup_expired_otps():
    """Clean up expired OTP codes"""
    try:
        from .models import User
        from django.utils import timezone
        from datetime import timedelta
        
        expired_time = timezone.now() - timedelta(minutes=10)
        users_with_expired_otps = User.objects.filter(
            otp_created_at__lt=expired_time,
            otp_code__isnull=False
        )
        
        count = users_with_expired_otps.count()
        users_with_expired_otps.update(
            otp_code=None,
            otp_created_at=None
        )
        
        logger.info(f"Cleaned up {count} expired OTP codes")
        return f"Cleaned up {count} expired OTPs"
        
    except Exception as exc:
        logger.error(f"Failed to cleanup expired OTPs: {str(exc)}")
        return f"Error: {str(exc)}"


@shared_task
def send_account_status_notification(account_id, new_status, reason=None):
    """Send notification when account status changes"""
    try:
        from .models import Account
        account = Account.objects.get(id=account_id)
        
        subject = f'Account Status Update - {account.account_number}'
        message = f'Your account {account.account_number} status has been updated to: {new_status}'
        if reason:
            message += f'\nReason: {reason}'
        
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[account.user.email],
            fail_silently=False,
        )
        
        logger.info(f"Account status notification sent for account {account.account_number}")
        
    except Exception as exc:
        logger.error(f"Failed to send account status notification: {str(exc)}")


@shared_task
def generate_account_statement(account_id, start_date, end_date, user_email):
    """Generate and email account statement"""
    try:
        from .models import Account
        from transactions.models import Transaction
        from django.core.mail import EmailMessage
        from io import BytesIO
        import csv
        
        account = Account.objects.get(id=account_id)
        transactions = Transaction.objects.filter(
            account=account,
            created_at__date__range=[start_date, end_date]
        ).order_by('-created_at')
        
        # Create CSV statement
        buffer = BytesIO()
        writer = csv.writer(buffer.getvalue().decode('utf-8').splitlines())
        writer.writerow(['Date', 'Description', 'Amount', 'Balance', 'Type'])
        
        for txn in transactions:
            writer.writerow([
                txn.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                txn.description,
                txn.amount,
                txn.balance_after,
                txn.transaction_type
            ])
        
        # Send email with statement
        email = EmailMessage(
            subject=f'Account Statement - {account.account_number}',
            body=f'Please find attached your account statement for {start_date} to {end_date}.',
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[user_email],
        )
        
        email.attach(
            f'statement_{account.account_number}_{start_date}_{end_date}.csv',
            buffer.getvalue(),
            'text/csv'
        )
        
        email.send()
        logger.info(f"Account statement sent for account {account.account_number}")
        
    except Exception as exc:
        logger.error(f"Failed to generate account statement: {str(exc)}")


@shared_task
def monitor_failed_login_attempts():
    """Monitor and alert on suspicious login attempts"""
    try:
        from .models import LoginAttempt, User
        from django.utils import timezone
        from django.db.models import Count
        from datetime import timedelta
        
        # Check for multiple failed attempts in last hour
        one_hour_ago = timezone.now() - timedelta(hours=1)
        suspicious_ips = LoginAttempt.objects.filter(
            timestamp__gte=one_hour_ago,
            success=False
        ).values('ip_address').annotate(
            attempt_count=Count('id')
        ).filter(attempt_count__gte=5)
        
        if suspicious_ips:
            # Send alert to admin
            admin_emails = User.objects.filter(is_staff=True).values_list('email', flat=True)
            ip_list = [f"{ip['ip_address']}: {ip['attempt_count']} attempts" for ip in suspicious_ips]
            
            send_mail(
                subject='Security Alert: Suspicious Login Attempts',
                message=f'Multiple failed login attempts detected:\n\n{chr(10).join(ip_list)}',
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=list(admin_emails),
                fail_silently=False,
            )
            
            logger.warning(f"Security alert sent for {len(suspicious_ips)} suspicious IPs")
        
    except Exception as exc:
        logger.error(f"Failed to monitor login attempts: {str(exc)}")
