from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

app_name = 'accounts'

urlpatterns = [
    # Authentication URLs
    path('register/', views.UserRegistrationView.as_view(), name='user-register'),
    path('login/', views.UserLoginView.as_view(), name='user-login'),
    path('otp/request/', views.OTPRequestView.as_view(), name='otp-request'),
    path('otp/verify/', views.OTPVerifyView.as_view(), name='otp-verify'),
    
    # User Profile URLs
    path('profile/', views.UserProfileView.as_view(), name='user-profile'),
    path('change-password/', views.ChangePasswordView.as_view(), name='change-password'),
    
    # Account Management URLs
    path('accounts/', views.AccountListCreateView.as_view(), name='account-list-create'),
    path('accounts/<uuid:pk>/', views.AccountDetailView.as_view(), name='account-detail'),
    path('accounts/batch-create/', views.BatchAccountCreateView.as_view(), name='batch-account-create'),
    path('accounts/summary/', views.user_accounts_summary, name='accounts-summary'),
    path('accounts/<uuid:account_id>/statement/', views.request_account_statement, name='account-statement'),
    
    # Role Management URLs
    path('roles/', views.UserRoleListCreateView.as_view(), name='role-list-create'),
    path('roles/<int:pk>/', views.UserRoleDetailView.as_view(), name='role-detail'),
    path('role-assignments/', views.UserRoleAssignmentListCreateView.as_view(), name='role-assignment-list-create'),
    path('role-assignments/<int:pk>/', views.UserRoleAssignmentDetailView.as_view(), name='role-assignment-detail'),
    
    # Account Hold URLs
    path('account-holds/', views.AccountHoldListCreateView.as_view(), name='account-hold-list-create'),
    path('account-holds/<int:pk>/', views.AccountHoldDetailView.as_view(), name='account-hold-detail'),
    
    # Admin URLs
    path('admin/stats/', views.system_stats, name='system-stats'),
]
