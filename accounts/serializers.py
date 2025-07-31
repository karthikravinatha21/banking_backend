from rest_framework import serializers
from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from django.db import transaction

from core.models import Currency
from .models import User, Account, UserRole, UserRoleAssignment, AccountHold
from .tasks import send_otp_email
import secrets
import string


class UserRegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, validators=[validate_password])
    password_confirm = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ('email', 'first_name', 'last_name', 'phone_number',
                  'password', 'password_confirm', 'timezone')

    def validate(self, attrs):
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError("Passwords don't match")
        return attrs

    def create(self, validated_data):
        validated_data.pop('password_confirm')
        if 'username' not in validated_data or not validated_data['username']:
            validated_data['username'] = validated_data['email']  # .split('@')[0]
        user = User.objects.create_user(**validated_data)
        try:
            currency = Currency.objects.get(code='INR')  # Assuming 'code' is the field storing currency codes
        except Exception as ex:
            raise ValueError("Currency 'USD' does not exist.")
        # Create default account for user
        Account.objects.create(
            user=user,
            account_type='SAVINGS',
            currency=currency
        )
        return user


class UserLoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        email = attrs.get('email')
        password = attrs.get('password')

        if email and password:
            user = authenticate(username=email, password=password)
            if not user:
                raise serializers.ValidationError('Invalid credentials')
            if not user.is_active:
                raise serializers.ValidationError('Account is disabled')
            attrs['user'] = user
        else:
            raise serializers.ValidationError('Must include email and password')

        return attrs


class OTPRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()

    def validate_email(self, value):
        try:
            user = User.objects.get(email=value)
            self.user = user
            return value
        except User.DoesNotExist:
            raise serializers.ValidationError("User with this email does not exist")


class OTPVerifySerializer(serializers.Serializer):
    email = serializers.EmailField()
    otp = serializers.CharField(max_length=6)

    def validate(self, attrs):
        try:
            user = User.objects.get(email=attrs['email'])
            if not user.verify_otp(attrs['otp']):
                raise serializers.ValidationError("Invalid or expired OTP")
            attrs['user'] = user
        except User.DoesNotExist:
            raise serializers.ValidationError("User not found")
        return attrs


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ('id', 'email', 'first_name', 'last_name', 'phone_number',
                  'is_active', 'date_joined', 'timezone', 'last_login')
        read_only_fields = ('id', 'date_joined', 'last_login')


class AccountSerializer(serializers.ModelSerializer):
    balance = serializers.DecimalField(max_digits=15, decimal_places=2, read_only=True)
    user_email = serializers.EmailField(source='user.email', read_only=True)

    class Meta:
        model = Account
        fields = ('id', 'account_number', 'account_type', 'balance',
                  'currency', 'is_active', 'created_at', 'user_email')
        read_only_fields = ('id', 'account_number', 'balance', 'created_at')


class AccountCreateSerializer(serializers.ModelSerializer):
    user_email = serializers.EmailField(write_only=True)

    class Meta:
        model = Account
        fields = ('account_type', 'user_email')  # 'currency',

    def validate_user_email(self, value):
        try:
            user = User.objects.get(email=value)
            self.user = user
            return value
        except User.DoesNotExist:
            raise serializers.ValidationError("User with this email does not exist")

    def create(self, validated_data):
        validated_data.pop('user_email')
        validated_data['user'] = self.user
        # validated_data['tenant_id'] = getattr(self.user, 'tenant_id', 1)
        return super().create(validated_data)


class AccountCreateSerializerProxy(serializers.ModelSerializer):
    user_email = serializers.EmailField(write_only=True)

    class Meta:
        model = Account
        fields = ('id', 'account_type', 'currency', 'user_email')

    def validate_user_email(self, value):
        try:
            user = User.objects.get(email=value)
            self.user = user
            return value
        except User.DoesNotExist:
            raise serializers.ValidationError("User with this email does not exist")

    def create(self, validated_data):
        validated_data.pop('user_email')
        validated_data['user'] = self.user
        # validated_data['tenant_id'] = getattr(self.user, 'tenant_id', 1)
        return super().create(validated_data)


class BatchAccountCreateSerializer(serializers.Serializer):
    accounts = serializers.ListSerializer(child=AccountCreateSerializer())

    def create(self, validated_data):
        accounts_data = validated_data['accounts']
        created_accounts = []

        with transaction.atomic():
            for account_data in accounts_data:
                serializer = AccountCreateSerializer(data=account_data)
                serializer.is_valid(raise_exception=True)
                account = serializer.save()
                created_accounts.append(account)

        return {'accounts': created_accounts}


class UserRoleSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserRole
        fields = ('id', 'name', 'description', 'permissions', 'is_active')


class UserRoleAssignmentSerializer(serializers.ModelSerializer):
    role_name = serializers.CharField(source='role.name', read_only=True)
    user_email = serializers.EmailField(source='user.email', read_only=True)

    class Meta:
        model = UserRoleAssignment
        fields = ('id', 'user', 'role', 'user_email', 'role_name',
                  'assigned_at', 'assigned_by', 'is_active')
        read_only_fields = ('id', 'assigned_at', 'assigned_by')


class AccountHoldSerializer(serializers.ModelSerializer):
    account_number = serializers.CharField(source='account.account_number', read_only=True)

    class Meta:
        model = AccountHold
        fields = ('id', 'account', 'account_number', 'amount', 'reason',
                  'hold_type', 'expires_at', 'is_active', 'created_at')
        read_only_fields = ('id', 'created_at')


class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True, validators=[validate_password])
    confirm_password = serializers.CharField(write_only=True)

    def validate_old_password(self, value):
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError("Current password is incorrect")
        return value

    def validate(self, attrs):
        if attrs['new_password'] != attrs['confirm_password']:
            raise serializers.ValidationError("New passwords don't match")
        return attrs

    def save(self):
        user = self.context['request'].user
        user.set_password(self.validated_data['new_password'])
        user.save()
        return user
