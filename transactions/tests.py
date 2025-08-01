"""
Transactions app tests.
"""
from django.test import TestCase
from django.contrib.auth import get_user_model
from .models import TransactionCategory


User = get_user_model()


class TransactionCategoryModelTest(TestCase):
    """Test cases for TransactionCategory model."""

    def setUp(self):
        """Set up test data."""
        self.category = TransactionCategory.objects.create(
            name='Transfer',
            description='Money transfer transactions'
        )

    def test_category_creation(self):
        """Test transaction category creation."""
        self.assertEqual(self.category.name, 'Transfer')
        self.assertEqual(self.category.description, 'Money transfer transactions')
        self.assertTrue(self.category.is_active)


    def test_category_str_representation(self):
        """Test category string representation."""
        self.assertEqual(str(self.category), 'Transfer')
