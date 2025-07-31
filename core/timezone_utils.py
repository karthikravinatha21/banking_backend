"""
Timezone utilities for the banking system.
"""
import pytz
from datetime import datetime, timezone as dt_timezone
from django.utils import timezone
from django.conf import settings
from typing import Optional, Union


class TimezoneHandler:
    """Utility class for handling timezone operations."""
    
    DEFAULT_TIMEZONE = 'UTC'
    
    @classmethod
    def get_user_timezone(cls, user) -> str:
        """
        Get the user's preferred timezone.
        
        Args:
            user: User instance
            
        Returns:
            str: Timezone string (e.g., 'America/New_York')
        """
        if hasattr(user, 'profile') and user.profile.timezone:
            return user.profile.timezone
        return cls.DEFAULT_TIMEZONE
    
    @classmethod
    def convert_to_user_timezone(cls, dt: datetime, user) -> datetime:
        """
        Convert a datetime to the user's timezone.
        
        Args:
            dt: Datetime object (should be timezone-aware)
            user: User instance
            
        Returns:
            datetime: Datetime in user's timezone
        """
        if dt is None:
            return None
            
        user_tz_str = cls.get_user_timezone(user)
        user_tz = pytz.timezone(user_tz_str)
        
        # Ensure datetime is timezone-aware
        if dt.tzinfo is None:
            dt = timezone.make_aware(dt)
        
        return dt.astimezone(user_tz)
    
    @classmethod
    def convert_to_utc(cls, dt: datetime, user_timezone: Optional[str] = None) -> datetime:
        """
        Convert a datetime from user timezone to UTC.
        
        Args:
            dt: Datetime object
            user_timezone: User's timezone string
            
        Returns:
            datetime: Datetime in UTC
        """
        if dt is None:
            return None
        
        if user_timezone:
            user_tz = pytz.timezone(user_timezone)
            if dt.tzinfo is None:
                dt = user_tz.localize(dt)
        
        return dt.astimezone(pytz.UTC)
    
    @classmethod
    def get_current_time_for_user(cls, user) -> datetime:
        """
        Get the current time in the user's timezone.
        
        Args:
            user: User instance
            
        Returns:
            datetime: Current time in user's timezone
        """
        utc_now = timezone.now()
        return cls.convert_to_user_timezone(utc_now, user)
    
    @classmethod
    def format_datetime_for_user(cls, dt: datetime, user, format_str: str = None) -> str:
        """
        Format datetime for display to user in their timezone.
        
        Args:
            dt: Datetime object
            user: User instance
            format_str: Custom format string
            
        Returns:
            str: Formatted datetime string
        """
        if dt is None:
            return ""
        
        user_dt = cls.convert_to_user_timezone(dt, user)
        
        if format_str is None:
            format_str = "%Y-%m-%d %H:%M:%S %Z"
        
        return user_dt.strftime(format_str)
    
    @classmethod
    def get_business_hours(cls, user, date: Optional[datetime] = None) -> tuple:
        """
        Get business hours for a user's timezone on a given date.
        
        Args:
            user: User instance
            date: Date to get business hours for (defaults to today)
            
        Returns:
            tuple: (start_time, end_time) in user's timezone
        """
        if date is None:
            date = cls.get_current_time_for_user(user).date()
        
        user_tz_str = cls.get_user_timezone(user)
        user_tz = pytz.timezone(user_tz_str)
        
        # Default business hours: 9 AM to 5 PM
        start_time = user_tz.localize(
            datetime.combine(date, datetime.min.time().replace(hour=9))
        )
        end_time = user_tz.localize(
            datetime.combine(date, datetime.min.time().replace(hour=17))
        )
        
        return start_time, end_time
    
    @classmethod
    def is_business_hours(cls, user, dt: Optional[datetime] = None) -> bool:
        """
        Check if a datetime falls within business hours for the user.
        
        Args:
            user: User instance
            dt: Datetime to check (defaults to current time)
            
        Returns:
            bool: True if within business hours
        """
        if dt is None:
            dt = cls.get_current_time_for_user(user)
        else:
            dt = cls.convert_to_user_timezone(dt, user)
        
        # Skip weekends (Saturday=5, Sunday=6)
        if dt.weekday() >= 5:
            return False
        
        start_time, end_time = cls.get_business_hours(user, dt.date())
        return start_time <= dt <= end_time
    
    @classmethod
    def get_supported_timezones(cls) -> list:
        """
        Get list of supported timezones.
        
        Returns:
            list: List of timezone strings
        """
        return [
            'UTC',
            'America/New_York',
            'America/Chicago',
            'America/Denver',
            'America/Los_Angeles',
            'Europe/London',
            'Europe/Paris',
            'Europe/Berlin',
            'Asia/Tokyo',
            'Asia/Shanghai',
            'Asia/Kolkata',
            'Australia/Sydney',
            'Pacific/Auckland',
        ]
    
    @classmethod
    def validate_timezone(cls, timezone_str: str) -> bool:
        """
        Validate if a timezone string is valid.
        
        Args:
            timezone_str: Timezone string to validate
            
        Returns:
            bool: True if valid timezone
        """
        try:
            pytz.timezone(timezone_str)
            return True
        except pytz.UnknownTimeZoneError:
            return False


class BusinessCalendar:
    """Business calendar utilities for banking operations."""
    
    @classmethod
    def is_banking_day(cls, date: datetime, user_timezone: str = 'UTC') -> bool:
        """
        Check if a date is a banking day (weekday, non-holiday).
        
        Args:
            date: Date to check
            user_timezone: Timezone for the check
            
        Returns:
            bool: True if banking day
        """
        # Convert to user timezone
        tz = pytz.timezone(user_timezone)
        if date.tzinfo is None:
            date = tz.localize(date)
        else:
            date = date.astimezone(tz)
        
        # Check if weekday (Monday=0, Sunday=6)
        if date.weekday() >= 5:  # Saturday or Sunday
            return False
        
        # Check for holidays (simplified - in real implementation,
        # you would check against a holiday calendar)
        holidays = cls.get_holidays(date.year, user_timezone)
        return date.date() not in holidays
    
    @classmethod
    def get_next_banking_day(cls, date: datetime, user_timezone: str = 'UTC') -> datetime:
        """
        Get the next banking day after the given date.
        
        Args:
            date: Starting date
            user_timezone: Timezone for calculation
            
        Returns:
            datetime: Next banking day
        """
        next_day = date
        while not cls.is_banking_day(next_day, user_timezone):
            next_day = next_day + timezone.timedelta(days=1)
        return next_day
    
    @classmethod
    def get_holidays(cls, year: int, user_timezone: str = 'UTC') -> set:
        """
        Get set of holiday dates for a given year.
        
        Args:
            year: Year to get holidays for
            user_timezone: Timezone for holidays
            
        Returns:
            set: Set of holiday dates
        """
        # Simplified holiday list - in real implementation,
        # you would use a proper holiday library or database
        holidays = set()
        
        # Add common US holidays (as example)
        if user_timezone.startswith('America/'):
            from datetime import date
            holidays.update({
                date(year, 1, 1),   # New Year's Day
                date(year, 7, 4),   # Independence Day
                date(year, 12, 25), # Christmas Day
            })
        
        return holidays


class TransactionTimeHandler:
    """Handle timing for financial transactions."""
    
    @classmethod
    def get_transaction_processing_time(cls, user, transaction_type: str) -> datetime:
        """
        Get the processing time for a transaction based on type and user timezone.
        
        Args:
            user: User instance
            transaction_type: Type of transaction
            
        Returns:
            datetime: When the transaction will be processed
        """
        current_time = TimezoneHandler.get_current_time_for_user(user)
        
        # Same-day processing for internal transactions during business hours
        if transaction_type in ['DEPOSIT', 'WITHDRAW', 'INTERNAL_TRANSFER']:
            if TimezoneHandler.is_business_hours(user, current_time):
                return current_time
            else:
                # Next business day at 9 AM
                next_day = current_time.date() + timezone.timedelta(days=1)
                while not BusinessCalendar.is_banking_day(
                    datetime.combine(next_day, datetime.min.time()),
                    TimezoneHandler.get_user_timezone(user)
                ):
                    next_day += timezone.timedelta(days=1)
                
                user_tz_str = TimezoneHandler.get_user_timezone(user)
                user_tz = pytz.timezone(user_tz_str)
                return user_tz.localize(
                    datetime.combine(next_day, datetime.min.time().replace(hour=9))
                )
        
        # External transfers typically take 1-3 business days
        elif transaction_type == 'EXTERNAL_TRANSFER':
            processing_days = 2  # 2 business days
            processing_date = current_time.date()
            
            for _ in range(processing_days):
                processing_date += timezone.timedelta(days=1)
                while not BusinessCalendar.is_banking_day(
                    datetime.combine(processing_date, datetime.min.time()),
                    TimezoneHandler.get_user_timezone(user)
                ):
                    processing_date += timezone.timedelta(days=1)
            
            user_tz_str = TimezoneHandler.get_user_timezone(user)
            user_tz = pytz.timezone(user_tz_str)
            return user_tz.localize(
                datetime.combine(processing_date, datetime.min.time().replace(hour=10))
            )
        
        # Default: immediate processing
        return current_time
    
    @classmethod
    def calculate_cutoff_times(cls, user) -> dict:
        """
        Calculate cutoff times for different transaction types.
        
        Args:
            user: User instance
            
        Returns:
            dict: Cutoff times for different transaction types
        """
        user_tz_str = TimezoneHandler.get_user_timezone(user)
        user_tz = pytz.timezone(user_tz_str)
        current_date = TimezoneHandler.get_current_time_for_user(user).date()
        
        return {
            'same_day_transfer': user_tz.localize(
                datetime.combine(current_date, datetime.min.time().replace(hour=15))
            ),
            'next_day_transfer': user_tz.localize(
                datetime.combine(current_date, datetime.min.time().replace(hour=17))
            ),
            'wire_transfer': user_tz.localize(
                datetime.combine(current_date, datetime.min.time().replace(hour=14))
            ),
        }


def get_transaction_deadline(transaction_type: str, user_timezone: str) -> str:
    """
    Get user-friendly deadline description for transaction types.
    
    Args:
        transaction_type: Type of transaction
        user_timezone: User's timezone
        
    Returns:
        str: Human-readable deadline description
    """
    deadlines = {
        'INTERNAL_TRANSFER': "Transfers submitted before 5 PM will be processed same day",
        'EXTERNAL_TRANSFER': "External transfers typically take 2-3 business days",
        'WIRE_TRANSFER': "Wire transfers submitted before 2 PM will be processed same day",
        'ACH_TRANSFER': "ACH transfers typically process within 1-2 business days",
    }
    
    return deadlines.get(transaction_type, "Processing time varies by transaction type")


# Utility functions for common timezone operations
def localize_datetime(dt: datetime, timezone_str: str) -> datetime:
    """Localize a naive datetime to a specific timezone."""
    if dt.tzinfo is not None:
        return dt
    
    tz = pytz.timezone(timezone_str)
    return tz.localize(dt)


def convert_timezone(dt: datetime, from_tz: str, to_tz: str) -> datetime:
    """Convert datetime from one timezone to another."""
    if dt.tzinfo is None:
        dt = localize_datetime(dt, from_tz)
    
    to_timezone = pytz.timezone(to_tz)
    return dt.astimezone(to_timezone)


def format_currency_with_timezone(amount: float, currency: str, user_timezone: str) -> str:
    """Format currency amount with timezone-appropriate formatting."""
    # This could be extended to use locale-specific formatting
    # based on the user's timezone/region
    
    timezone_formats = {
        'America/New_York': f"${amount:,.2f} USD",
        'Europe/London': f"£{amount:,.2f} GBP",
        'Europe/Paris': f"€{amount:,.2f} EUR",
        'Asia/Tokyo': f"¥{amount:,.0f} JPY",
    }
    
    return timezone_formats.get(user_timezone, f"{amount:,.2f} {currency}")
