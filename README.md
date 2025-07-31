Banking System Documentation
=============================

Welcome to the Banking System documentation! This comprehensive Django-based banking system provides a full-featured platform for modern banking operations.

Overview
--------

The Banking System is a full-featured Django application that provides:

* **User Management**: Registration, authentication, and profile management with 2FA
* **Account Management**: Multiple account types with unique account numbers and batch creation
* **Transaction Processing**: Deposits, withdrawals, transfers with real-time processing
* **Currency Support**: Multi-currency with real-time exchange rates and conversion
* **Security**: Advanced security features including rate limiting, CSRF protection, and secure password storage
* **Performance**: Optimized with caching, database indexing, and background task processing
* **Scalability**: Docker-based deployment with load balancing and horizontal scaling

Quick Start
-----------

1. **Installation**::

    git clone <repository-url>
    cd Banking
    python -m venv banking_env
    source banking_env/bin/activate  # On Windows: banking_env\Scripts\activate
    pip install -r requirements.txt

2. **Database Setup**::

    cp .env.example .env
    # Edit .env with your database credentials
    python manage.py migrate
    python manage.py init_banking_system

3. **Run the Server**::

    python manage.py runserver

4. **Access the API**::

    # Browse to http://localhost:8000/api/
    # API documentation at http://localhost:8000/api/schema/swagger-ui/

Architecture
------------

The system is built with a modular architecture consisting of four main Django apps:

* **Core**: Base models and utilities (Currency, ExchangeRate, TimeStampedModel)
* **Accounts**: User management, authentication, and account operations
* **Transactions**: Transaction processing, transfers, and financial operations  
* **Currency**: Currency management, exchange rates, and conversion services

Key Features
------------

Authentication & Security
~~~~~~~~~~~~~~~~~~~~~~~~~

* JWT-based authentication with refresh tokens
* Two-factor authentication (2FA) support
* Role-based access control (RBAC)
* API rate limiting and throttling
* CSRF protection and secure headers
* Secure password storage with Django's built-in hashing

Account Management
~~~~~~~~~~~~~~~~~~

* Multiple account types (Savings, Checking, etc.)
* Unique 10-digit account number generation
* Account holds and freezing capabilities
* Batch account creation with Celery
* Multi-tenancy support

Transaction Processing
~~~~~~~~~~~~~~~~~~~~~~

* Real-time deposit and withdrawal processing
* Internal and external transfers
* Transaction history with filtering and pagination
* Scheduled/recurring transactions
* Transaction limits and monitoring
* Comprehensive audit trail

Currency & Exchange
~~~~~~~~~~~~~~~~~~~

* Multi-currency support with real-time rates
* Currency conversion with spread calculation
* Exchange rate caching and updates
* Historical rate tracking
* Currency analytics and reporting

Performance & Scalability
~~~~~~~~~~~~~~~~~~~~~~~~~~

* Redis caching for improved performance
* Celery for background task processing
* Database indexing and query optimization
* Docker-based deployment
* Nginx load balancing
* Horizontal scaling capabilities

API Endpoints
-------------

The system provides comprehensive REST API endpoints:

Authentication
~~~~~~~~~~~~~~

* ``POST /api/auth/register/`` - User registration
* ``POST /api/auth/login/`` - User login
* ``POST /api/auth/logout/`` - User logout
* ``POST /api/auth/token/refresh/`` - Refresh JWT token
* ``POST /api/auth/2fa/enable/`` - Enable 2FA
* ``POST /api/auth/2fa/verify/`` - Verify 2FA token

Account Management
~~~~~~~~~~~~~~~~~~

* ``GET/POST /api/accounts/`` - List/create accounts
* ``GET/PUT/DELETE /api/accounts/{id}/`` - Account operations
* ``POST /api/accounts/batch/`` - Batch account creation
* ``GET /api/accounts/{id}/holds/`` - Account holds
* ``POST /api/accounts/{id}/freeze/`` - Freeze account

Transactions
~~~~~~~~~~~~

* ``POST /api/transactions/deposit/`` - Make deposit
* ``POST /api/transactions/withdraw/`` - Make withdrawal
* ``POST /api/transactions/transfer/`` - Internal transfer
* ``POST /api/transactions/external-transfer/`` - External transfer
* ``GET /api/transactions/history/`` - Transaction history
* ``GET/POST /api/transactions/scheduled/`` - Scheduled transactions

Currency & Exchange
~~~~~~~~~~~~~~~~~~~

* ``GET /api/currency/`` - List currencies
* ``GET /api/currency/{code}/`` - Currency details
* ``GET /api/currency/rates/`` - Exchange rates
* ``POST /api/currency/convert/`` - Currency conversion
* ``GET /api/currency/supported/`` - Supported currencies

Security Considerations
-----------------------

The system implements multiple layers of security:

* **Authentication**: JWT tokens with configurable expiration
* **Authorization**: Role-based permissions for all operations
* **Input Validation**: Comprehensive validation on all inputs
* **Rate Limiting**: API rate limiting to prevent abuse
* **Encryption**: All sensitive data encrypted at rest and in transit
* **Audit Logging**: Comprehensive logging of all operations
* **Security Headers**: CORS, HSTS, and other security headers configured

Development
-----------

The system is designed for easy development and testing:

* **Test Coverage**: Comprehensive test suite with >90% coverage
* **Code Quality**: Black formatting, flake8 linting, mypy type checking
* **Documentation**: Sphinx-generated documentation
* **CI/CD**: GitHub Actions for automated testing and deployment
* **Docker**: Development and production Docker environments

Production Deployment
---------------------

For production deployment:

1. **Environment Setup**::

    # Production environment variables
    DEBUG=False
    SECRET_KEY=your-secret-key
    DATABASE_URL=postgresql://...
    REDIS_URL=redis://...

