
from bot.main import is_valid_address, role_selection_menu, passenger_menu, driver_menu, skip_menu

"""
Unit tests for Telegram utility functions from main.py.

Tests helper functions for:
- Address validation (is_valid_address)
- Safe message sending
- Keyboard generation
"""



class TestAddressValidation:
    """Test suite for address validation."""

    def test_validate_address_valid(self):
        """Test validation of valid addresses."""
        assert is_valid_address("вул. Хрещатик, 1") is True
        assert is_valid_address("Майдан Незалежності") is True
        assert is_valid_address("123456") is True  # Length > 5

    def test_validate_address_too_short(self):
        """Test validation rejects short addresses."""
        assert is_valid_address("вул") is False
        assert is_valid_address("12345") is False  # Exactly 5 chars
        assert is_valid_address("") is False
        assert is_valid_address("abc") is False

    def test_validate_address_none(self):
        """Test validation rejects None."""
        assert is_valid_address(None) is False


class TestKeyboardGenerators:
    """Test suite for keyboard generation functions."""

    def test_role_selection_menu(self):
        """Test role selection menu keyboard generation."""
        keyboard = role_selection_menu()
        
        assert keyboard is not None
        assert keyboard.resize_keyboard is True
        assert keyboard.one_time_keyboard is True

    def test_passenger_menu(self):
        """Test passenger menu keyboard generation."""
        keyboard = passenger_menu()
        
        assert keyboard is not None
        assert keyboard.resize_keyboard is True

    def test_driver_menu(self):
        """Test driver menu keyboard generation."""
        keyboard = driver_menu()
        
        assert keyboard is not None
        assert keyboard.resize_keyboard is True

    def test_skip_menu(self):
        """Test skip menu keyboard generation."""
        keyboard = skip_menu()
        
        assert keyboard is not None
        assert keyboard.resize_keyboard is True
        assert keyboard.one_time_keyboard is True



