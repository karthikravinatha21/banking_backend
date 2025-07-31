from rest_framework import generics, status, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.views import APIView
from django.shortcuts import get_object_or_404
from django.db.models import Q, Sum, Count
from django.utils import timezone
from django_ratelimit.decorators import ratelimit
from django.utils.decorators import method_decorator
from datetime import datetime, timedelta
from decimal import Decimal

from core.custom_pagination import CustomPaginationClass
from .models import Transaction, Transfer, TransactionCategory, ScheduledTransaction, TransactionLimit
from .serializers import (
    TransactionSerializer, TransferSerializer, TransactionCategorySerializer,
    DepositSerializer, WithdrawSerializer, InternalTransferSerializer,
    ExternalTransferSerializer, ScheduledTransactionSerializer,
    TransactionLimitSerializer, TransactionHistorySerializer, TransactionAnalyticsSerializer
)
from accounts.models import Account
from accounts.permissions import IsOwnerOrAdmin, IsAdminUser, CanPerformTransaction
import logging

logger = logging.getLogger(__name__)


class TransactionCategoryListCreateView(generics.ListCreateAPIView):
    queryset = TransactionCategory.objects.filter(is_active=True)
    serializer_class = TransactionCategorySerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_permissions(self):
        if self.request.method == 'POST':
            self.permission_classes = [permissions.IsAuthenticated, IsAdminUser]
        return super().get_permissions()


class TransactionCategoryDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = TransactionCategory.objects.all()
    serializer_class = TransactionCategorySerializer
    permission_classes = [permissions.IsAuthenticated, IsAdminUser]


class DepositView(APIView):
    permission_classes = [permissions.IsAuthenticated, CanPerformTransaction]
    
    @method_decorator(ratelimit(key='user', rate='10/m', method='POST'))
    def post(self, request):
        serializer = DepositSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # Check if user owns the account or is admin
        account = serializer.account
        if account.user != request.user and not request.user.is_staff:
            return Response(
                {'error': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        transaction_obj = serializer.save()
        
        return Response({
            'message': 'Deposit successful',
            'transaction': TransactionSerializer(transaction_obj).data
        }, status=status.HTTP_201_CREATED)


class WithdrawView(APIView):
    permission_classes = [permissions.IsAuthenticated, CanPerformTransaction]
    
    @method_decorator(ratelimit(key='user', rate='10/m', method='POST'))
    def post(self, request):
        serializer = WithdrawSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # Check if user owns the account or is admin
        account = serializer.account
        if account.user != request.user and not request.user.is_staff:
            return Response(
                {'error': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        transaction_obj = serializer.save()
        
        return Response({
            'message': 'Withdrawal successful',
            'transaction': TransactionSerializer(transaction_obj).data
        }, status=status.HTTP_201_CREATED)


class InternalTransferView(APIView):
    permission_classes = [permissions.IsAuthenticated, CanPerformTransaction]
    
    @method_decorator(ratelimit(key='user', rate='5/m', method='POST'))
    def post(self, request):
        serializer = InternalTransferSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # Check if user owns the from_account or is admin
        from_account = serializer.validated_data['from_account']
        if from_account.user != request.user and not request.user.is_staff:
            return Response(
                {'error': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        transfer = serializer.save()
        
        return Response({
            'message': 'Internal transfer successful',
            'transfer': TransferSerializer(transfer).data
        }, status=status.HTTP_201_CREATED)


class ExternalTransferView(APIView):
    permission_classes = [permissions.IsAuthenticated, CanPerformTransaction]
    # permission_classes = [permissions.IsAuthenticated]

    # @method_decorator(ratelimit(key='user', rate='3/h', method='POST'))
    def post(self, request):
        serializer = ExternalTransferSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # Check if user owns the from_account or is admin
        from_account = serializer.from_account
        # if from_account.user != request.user and not request.user.is_staff:
        #     return Response(
        #         {'error': 'Permission denied'},
        #         status=status.HTTP_403_FORBIDDEN
        #     )
        
        transfer = serializer.save()
        
        return Response({
            'message': 'External transfer initiated. You will be notified once processed.',
            'transfer': TransferSerializer(transfer).data
        }, status=status.HTTP_202_ACCEPTED)


class TransactionListView(generics.ListCreateAPIView):
    queryset = Transaction.objects.all()
    serializer_class = TransactionSerializer
    pagination_class = CustomPaginationClass

    def get_queryset(self):
        queryset = super().get_queryset()

        # Filter by account ID
        account = self.request.query_params.get('account', None)
        if account:
            queryset = queryset.filter(account__id=account)

        # Filter by transaction type
        transaction_type = self.request.query_params.get('transaction_type', None)
        if transaction_type:
            queryset = queryset.filter(transaction_type=transaction_type)

        # Filter by status
        status = self.request.query_params.get('status', None)
        if status:
            queryset = queryset.filter(status=status)

        # Filter by date range
        date_from = self.request.query_params.get('date_from', None)
        date_to = self.request.query_params.get('date_to', None)
        if date_from:
            try:
                date_from = datetime.strptime(date_from, '%Y-%m-%d').date()
                queryset = queryset.filter(created_at__gte=date_from)
            except ValueError:
                pass  # Handle invalid date format as needed

        if date_to:
            try:
                date_to = datetime.strptime(date_to, '%Y-%m-%d').date()
                queryset = queryset.filter(created_at__lte=date_to)
            except ValueError:
                pass  # Handle invalid date format as needed

        return queryset

class TransactionDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Transaction.objects.all()
    serializer_class = TransactionSerializer

class TransactionSummaryView(generics.GenericAPIView):
    def get(self, request, *args, **kwargs):
        user = request.user
        transactions = Transaction.objects.filter(user=user)

        summary = {
            "total_deposits": transactions.filter(transaction_type='deposit').aggregate(Sum('amount'))['amount__sum'] or 0,
            "total_withdrawals": transactions.filter(transaction_type='withdrawal').aggregate(Sum('amount'))['amount__sum'] or 0,
            "total_balance": transactions.aggregate(Sum('balance_after'))['balance_after__sum'] or 0
        }
        return Response(summary, status=status.HTTP_200_OK)

class CheckBalanceView(generics.GenericAPIView):
    def get(self, request, *args, **kwargs):
        account_id = request.query_params.get('account_id', None)
        if not account_id:
            return Response({"error": "Account ID is required"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            account = Account.objects.get(id=account_id)
            last_transaction = Transaction.objects.filter(account=account).order_by('-created_at').first()
            balance = last_transaction.balance_after if last_transaction else 0
            return Response({"balance": str(balance)}, status=status.HTTP_200_OK)
        except Account.DoesNotExist:
            return Response({"error": "Account not found"}, status=status.HTTP_404_NOT_FOUND)

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAdminUser
from django.db.models import Sum, Count, Q
from .models import Transaction
from .serializers import TransactionAnalyticsSerializer
class TransactionAnalyticsView(APIView):
    """
    API view to provide overall system statistics (for admins).
    """
    permission_classes = [IsAdminUser]

    def get(self, request, *args, **kwargs):
        # Filter the transactions
        transactions = Transaction.objects.all()

        # Aggregate data from the Transaction model
        analytics_data = transactions.aggregate(
            total_transactions=Sum('amount'),
            total_deposits=Sum('amount', filter=Q(transaction_type='deposit')),
            total_withdrawals=Sum('amount', filter=Q(transaction_type='withdrawal')),
            total_fees=Sum('fee_amount'),
            total_refunds=Sum('amount', filter=Q(transaction_type='refund')),
            total_interest=Sum('amount', filter=Q(transaction_type='interest')),
            total_balance_before=Sum('balance_before'),
            total_balance_after=Sum('balance_after'),
            total_pending=Count('status', filter=Q(status='pending')),
            total_completed=Count('status', filter=Q(status='completed')),
            total_failed=Count('status', filter=Q(status='failed')),
            total_transactions_by_user=Count('user')
        )

        # Return aggregated data as a response using the serializer
        serializer = TransactionAnalyticsSerializer(analytics_data)
        return Response(serializer.data)
