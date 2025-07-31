from django.urls import path
from . import views

app_name = 'currency'

urlpatterns = [
    # Currency Management
    path('currencies/', views.CurrencyListView.as_view(), name='currency-list'),
    path('currencies/<str:code>/', views.CurrencyDetailView.as_view(), name='currency-detail'),
    
    # Exchange Rates
    path('rates/', views.ExchangeRateListView.as_view(), name='exchange-rate-list'),
    path('rates/<str:from_currency>/<str:to_currency>/', views.get_cached_exchange_rate, name='exchange-rate-detail'),
    
    # Currency Conversion
    path('convert/', views.CurrencyConvertView.as_view(), name='currency-convert'),
    path('calculator/', views.currency_conversion_calculator, name='conversion-calculator'),
    
    # Utility Endpoints
    # path('supported/', views.supported_currencies, name='supported-currencies'),
]
