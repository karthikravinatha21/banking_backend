from django.urls import path
from . import views

app_name = 'transactions'

urlpatterns = [
    # Transaction Categories
    path('categories/', views.TransactionCategoryListCreateView.as_view(), name='category-list-create'),
    path('categories/<int:pk>/', views.TransactionCategoryDetailView.as_view(), name='category-detail'),
    
    # Basic Transaction Operations
    path('deposit/', views.DepositView.as_view(), name='deposit'),
    path('withdraw/', views.WithdrawView.as_view(), name='withdraw'),
    path('transfer/internal/', views.InternalTransferView.as_view(), name='internal-transfer'),
    path('transfer/external/', views.ExternalTransferView.as_view(), name='external-transfer'),
    
    # Transaction History and Details
    path('history', views.TransactionListView.as_view(), name='transaction-list'),
    path('<uuid:pk>/', views.TransactionDetailView.as_view(), name='transaction-detail'),
    path('summary/', views.TransactionSummaryView.as_view(), name='transaction-summary'),
    path('check-balance/', views.CheckBalanceView.as_view(), name='check-balance'),
    #
    # # Transfer Management
    # path('transfers/', views.TransferListView.as_view(), name='transfer-list'),
    # path('transfers/<int:pk>/', views.TransferDetailView.as_view(), name='transfer-detail'),
    #
    # # Scheduled Transactions
    # path('scheduled/', views.ScheduledTransactionListCreateView.as_view(), name='scheduled-list-create'),
    # path('scheduled/<int:pk>/', views.ScheduledTransactionDetailView.as_view(), name='scheduled-detail'),
    # path('scheduled/<int:pk>/cancel/', views.cancel_scheduled_transaction, name='cancel-scheduled'),
    #
    # # Transaction Limits
    # path('limits/', views.TransactionLimitListCreateView.as_view(), name='limit-list-create'),
    # path('limits/<int:pk>/', views.TransactionLimitDetailView.as_view(), name='limit-detail'),
    #
    # # Admin Analytics
    path('analytics/', views.TransactionAnalyticsView.as_view(), name='transaction-analytics'),
]
