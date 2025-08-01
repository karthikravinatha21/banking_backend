from rest_framework import generics, status, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import login
from django.db import transaction
from django.utils import timezone
from django.shortcuts import get_object_or_404
from django_ratelimit.decorators import ratelimit
from django.utils.decorators import method_decorator

from core.constants import ACCOUNT_ACTIVE_STATUS
from .models import User, Account, UserRole, UserRoleAssignment, AccountHold
from .serializers import (
    UserRegistrationSerializer, UserLoginSerializer, UserSerializer,
    AccountSerializer, AccountCreateSerializer, BatchAccountCreateSerializer,
    UserRoleSerializer, UserRoleAssignmentSerializer, AccountHoldSerializer,
    OTPRequestSerializer, OTPVerifySerializer, ChangePasswordSerializer,
    AccountCreateSerializerProxy
)
from .tasks import send_otp_email, create_accounts_batch
from .permissions import IsOwnerOrAdmin, IsAdminUser
import logging

logger = logging.getLogger(__name__)


class UserRegistrationView(generics.CreateAPIView):
    queryset = User.objects.all()
    serializer_class = UserRegistrationSerializer
    permission_classes = [permissions.AllowAny]
    
    @method_decorator(ratelimit(key='ip', rate='5/m', method='POST'))
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)
    
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        
        # Generate JWT tokens
        refresh = RefreshToken.for_user(user)
        
        return Response({
            'user': UserSerializer(user).data,
            'tokens': {
                'refresh': str(refresh),
                'access': str(refresh.access_token),
            },
            'message': 'Registration successful'
        }, status=status.HTTP_201_CREATED)


class UserLoginView(APIView):
    permission_classes = [permissions.AllowAny]
    
    @method_decorator(ratelimit(key='ip', rate='10/m', method='POST'))
    def post(self, request):
        serializer = UserLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        user = serializer.validated_data['user']
        from .models import LoginAttempt
        LoginAttempt.objects.create(
            email=user.email,
            ip_address=self.get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            is_successful=True
        )
        refresh = RefreshToken.for_user(user)
        user.last_login = timezone.now()
        user.save(update_fields=['last_login'])
        
        return Response({
            'user': UserSerializer(user).data,
            'tokens': {
                'refresh': str(refresh),
                'access': str(refresh.access_token),
            },
            'message': 'Login successful'
        })
    
    def get_client_ip(self, request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip


class OTPRequestView(APIView):
    permission_classes = [permissions.AllowAny]
    
    @method_decorator(ratelimit(key='ip', rate='3/m', method='POST'))
    def post(self, request):
        serializer = OTPRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        user = serializer.user
        otp_code = '1234'#user.generate_otp()
        user.otp = otp_code
        user.save()
        # Send OTP via Celery task
        send_otp_email.delay(user.id, otp_code)
        
        return Response({
            'message': 'OTP sent to your email address',
            'expires_in': '10 minutes'
        })


class OTPVerifyView(APIView):
    permission_classes = [permissions.AllowAny]
    
    def post(self, request):
        serializer = OTPVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        user = serializer.validated_data['user']
        
        # Generate JWT tokens
        refresh = RefreshToken.for_user(user)
        
        return Response({
            'user': UserSerializer(user).data,
            'tokens': {
                'refresh': str(refresh),
                'access': str(refresh.access_token),
            },
            'message': '2FA verification successful'
        })


class UserProfileView(generics.RetrieveUpdateAPIView):
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_object(self):
        return self.request.user


class ChangePasswordView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        
        return Response({'message': 'Password changed successfully'})


class AccountListCreateView(generics.ListCreateAPIView):
    serializer_class = AccountSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        user = self.request.user
        if user.is_staff:
            return Account.objects.all()
        return Account.objects.filter(user=user)
    
    def get_serializer_class(self):
        if self.request.method == 'POST':
            return AccountCreateSerializerProxy
        return AccountSerializer
    
    def perform_create(self, serializer):
        if not self.request.user.is_staff:
            # Regular users can only create accounts for themselves
            serializer.save(user=self.request.user)
        else:
            # Admin users can create accounts for any user
            serializer.save()


class AccountDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = AccountSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwnerOrAdmin]
    
    def get_queryset(self):
        user = self.request.user
        if user.is_staff:
            return Account.objects.all()
        return Account.objects.filter(user=user)
    
    def destroy(self, request, *args, **kwargs):
        account = self.get_object()
        if account.balance > 0:
            return Response(
                {'error': 'Cannot delete account with positive balance'},
                status=status.HTTP_400_BAD_REQUEST
            )
        account.is_active = False
        account.save()
        return Response({'message': 'Account deactivated successfully'})


class BatchAccountCreateView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsAdminUser]
    
    def post(self, request):
        serializer = BatchAccountCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        accounts_data = serializer.validated_data['accounts']
        
        # Process batch creation asynchronously
        task = create_accounts_batch.delay(accounts_data, request.user.id)
        
        return Response({
            'message': 'Batch account creation started',
            'task_id': task.id,
            'accounts_count': len(accounts_data)
        }, status=status.HTTP_202_ACCEPTED)


class UserRoleListCreateView(generics.ListCreateAPIView):
    queryset = UserRole.objects.filter(is_active=True)
    serializer_class = UserRoleSerializer
    permission_classes = [permissions.IsAuthenticated, IsAdminUser]


class UserRoleDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = UserRole.objects.all()
    serializer_class = UserRoleSerializer
    permission_classes = [permissions.IsAuthenticated, IsAdminUser]


class UserRoleAssignmentListCreateView(generics.ListCreateAPIView):
    serializer_class = UserRoleAssignmentSerializer
    permission_classes = [permissions.IsAuthenticated, IsAdminUser]
    
    def get_queryset(self):
        return UserRoleAssignment.objects.filter(is_active=True)
    
    def perform_create(self, serializer):
        serializer.save(assigned_by=self.request.user)


class UserRoleAssignmentDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = UserRoleAssignment.objects.all()
    serializer_class = UserRoleAssignmentSerializer
    permission_classes = [permissions.IsAuthenticated, IsAdminUser]
    
    def destroy(self, request, *args, **kwargs):
        assignment = self.get_object()
        assignment.is_active = False
        assignment.save()
        return Response({'message': 'Role assignment removed successfully'})


class AccountHoldListCreateView(generics.ListCreateAPIView):
    serializer_class = AccountHoldSerializer
    permission_classes = [permissions.IsAuthenticated, IsAdminUser]
    
    def get_queryset(self):
        account_id = self.request.query_params.get('account_id')
        queryset = AccountHold.objects.filter(is_active=True)
        if account_id:
            queryset = queryset.filter(account_id=account_id)
        return queryset


class AccountHoldDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = AccountHold.objects.all()
    serializer_class = AccountHoldSerializer
    permission_classes = [permissions.IsAuthenticated, IsAdminUser]
    
    def destroy(self, request, *args, **kwargs):
        hold = self.get_object()
        hold.is_active = False
        hold.save()
        return Response({'message': 'Account hold removed successfully'})


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def user_accounts_summary(request):
    """Get summary of user's accounts"""
    user = request.user
    if user.is_staff:
        return Response(
            {'error': 'Access Denied'}, status=status.HTTP_400_BAD_REQUEST
        )
    accounts = Account.objects.filter(user=user, status=ACCOUNT_ACTIVE_STATUS)
    
    summary = {
        'total_accounts': accounts.count(),
        'total_balance': sum(account.balance for account in accounts),
        'accounts_by_type': {},
        'accounts_by_currency': {}
    }

    for account in accounts:
        # Group by account type
        if account.account_type not in summary['accounts_by_type']:
            summary['accounts_by_type'][account.account_type] = {
                'count': 0,
                'total_balance': 0
            }
        summary['accounts_by_type'][account.account_type]['count'] += 1
        summary['accounts_by_type'][account.account_type]['total_balance'] += account.balance

        # Group by currency - Use currency code or name to make it serializable
        currency_key = str(account.currency.code)  # Use the currency code or name
        if currency_key not in summary['accounts_by_currency']:
            summary['accounts_by_currency'][currency_key] = {
                'count': 0,
                'total_balance': 0
            }
        summary['accounts_by_currency'][currency_key]['count'] += 1
        summary['accounts_by_currency'][currency_key]['total_balance'] += account.balance

    return Response(summary)


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def request_account_statement(request, account_id):
    """Request account statement via email"""
    account = get_object_or_404(Account, id=account_id)
    
    # Check permissions
    if account.user != request.user and not request.user.is_staff:
        return Response(
            {'error': 'Permission denied'},
            status=status.HTTP_403_FORBIDDEN
        )
    
    start_date = request.data.get('start_date')
    end_date = request.data.get('end_date')
    
    if not start_date or not end_date:
        return Response(
            {'error': 'start_date and end_date are required'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Generate statement asynchronously
    from .tasks import generate_account_statement
    task = generate_account_statement.delay(
        account_id, start_date, end_date, request.user.email
    )
    
    return Response({
        'message': 'Account statement generation started',
        'task_id': task.id
    })


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated, IsAdminUser])
def system_stats(request):
    """Get system statistics for admin dashboard"""
    stats = {
        'total_users': User.objects.filter(is_staff=False).count(),
        'active_users': User.objects.filter(is_active=True, is_staff=False).count(),
        'total_accounts': Account.objects.count(),
        'active_accounts': Account.objects.filter(status=ACCOUNT_ACTIVE_STATUS).count(),
        'total_balance': sum(account.balance for account in Account.objects.filter(status=ACCOUNT_ACTIVE_STATUS)),
        'users_by_date': {},
        'accounts_by_type': {}
    }
    
    # Users created in last 30 days
    from datetime import timedelta
    thirty_days_ago = timezone.now() - timedelta(days=30)
    recent_users = User.objects.filter(date_joined__gte=thirty_days_ago)
    
    for user in recent_users:
        date_key = user.date_joined.strftime('%Y-%m-%d')
        stats['users_by_date'][date_key] = stats['users_by_date'].get(date_key, 0) + 1
    
    # Accounts by type
    for account in Account.objects.filter(status=ACCOUNT_ACTIVE_STATUS):
        account_type = account.account_type
        if account_type not in stats['accounts_by_type']:
            stats['accounts_by_type'][account_type] = {
                'count': 0,
                'total_balance': 0
            }
        stats['accounts_by_type'][account_type]['count'] += 1
        stats['accounts_by_type'][account_type]['total_balance'] += account.balance
    
    return Response(stats)
