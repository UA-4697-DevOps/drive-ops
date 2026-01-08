"""
Pytest configuration and shared fixtures for bot tests.

Provides reusable fixtures for:
- Mock Telegram objects (Update, Message, Context, etc.)
- Common test data (addresses, trip payloads)
- Test environment setup
"""

# Make `client-gateway` package importable during tests (so `import bot` works)
import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
from unittest.mock import AsyncMock, MagicMock
from telegram import Update, Message, Chat, User, CallbackQuery, Bot
from telegram.ext import ContextTypes


# =============================================================================
# Mock Telegram Object Fixtures
# =============================================================================


@pytest.fixture
def mock_user():
    """Create a mock Telegram User."""
    user = MagicMock(spec=User)
    user.id = 12345
    user.first_name = "TestUser"
    user.last_name = "LastName"
    user.username = "testuser"
    user.is_bot = False
    return user


@pytest.fixture
def mock_chat():
    """Create a mock Telegram Chat."""
    chat = MagicMock(spec=Chat)
    chat.id = 12345
    chat.type = "private"
    chat.first_name = "TestUser"
    return chat


@pytest.fixture
def mock_message(mock_chat, mock_user):
    """Create a mock Telegram Message."""
    message = MagicMock(spec=Message)
    message.message_id = 1
    message.chat = mock_chat
    message.from_user = mock_user
    message.text = ""
    message.reply_text = AsyncMock()
    message.reply_markup = None
    return message


@pytest.fixture
def mock_update(mock_message, mock_chat, mock_user):
    """Create a mock Telegram Update."""
    update = MagicMock(spec=Update)
    update.update_id = 1
    update.effective_message = mock_message
    update.effective_chat = mock_chat
    update.effective_user = mock_user
    update.callback_query = None
    return update


@pytest.fixture
def mock_callback_query(mock_message, mock_user):
    """Create a mock Telegram CallbackQuery."""
    query = MagicMock(spec=CallbackQuery)
    query.id = "callback_123"
    query.from_user = mock_user
    query.message = mock_message
    query.data = ""
    query.answer = AsyncMock()
    query.edit_message_text = AsyncMock()
    query.edit_message_reply_markup = AsyncMock()
    return query


@pytest.fixture
def mock_bot():
    """Create a mock Telegram Bot."""
    bot = MagicMock(spec=Bot)
    bot.send_message = AsyncMock()
    bot.edit_message_text = AsyncMock()
    bot.delete_message = AsyncMock()
    bot.answer_callback_query = AsyncMock()
    return bot


@pytest.fixture
def mock_context(mock_bot):
    """Create a mock Context."""
    context = MagicMock(spec=ContextTypes.DEFAULT_TYPE)
    context.bot = mock_bot
    context.user_data = {}
    context.chat_data = {}
    context.bot_data = {}
    return context


# =============================================================================
# User-Specific Fixtures
# =============================================================================


@pytest.fixture
def passenger_user():
    """Create a mock passenger user."""
    user = MagicMock(spec=User)
    user.id = 11111
    user.first_name = "Passenger"
    user.username = "passenger_user"
    user.is_bot = False
    return user


@pytest.fixture
def driver_user():
    """Create a mock driver user."""
    user = MagicMock(spec=User)
    user.id = 22222
    user.first_name = "Driver"
    user.username = "driver_user"
    user.is_bot = False
    return user


@pytest.fixture
def passenger_update(passenger_user):
    """Create a mock Update for passenger."""
    update = MagicMock(spec=Update)
    chat = MagicMock(spec=Chat)
    chat.id = passenger_user.id
    chat.type = "private"

    message = MagicMock(spec=Message)
    message.chat = chat
    message.from_user = passenger_user
    message.reply_text = AsyncMock()

    update.effective_user = passenger_user
    update.effective_chat = chat
    update.effective_message = message
    update.callback_query = None

    return update


@pytest.fixture
def driver_update(driver_user):
    """Create a mock Update for driver."""
    update = MagicMock(spec=Update)
    chat = MagicMock(spec=Chat)
    chat.id = driver_user.id
    chat.type = "private"

    message = MagicMock(spec=Message)
    message.chat = chat
    message.from_user = driver_user
    message.reply_text = AsyncMock()

    update.effective_user = driver_user
    update.effective_chat = chat
    update.effective_message = message
    update.callback_query = None

    return update


# =============================================================================
# Test Data Fixtures
# =============================================================================


@pytest.fixture
def valid_addresses():
    """Provide valid Ukrainian addresses for testing."""
    return [
        "вул. Хрещатик, 1",
        "пл. Незалежності",
        "вул. Бессарабська, 2",
        "Центральний вокзал",
        "Міжнародний аеропорт Бориспіль",
        "вул. Велика Васильківська, 10",
    ]


@pytest.fixture
def invalid_addresses():
    """Provide invalid addresses for testing."""
    return ["", "abc", "12", "test", "     ", "\t\n"]


@pytest.fixture
def sample_trip_data():
    """Provide sample trip data for testing."""
    return {
        "pickup_location": "вул. Хрещатик, 1",
        "dropoff_location": "вул. Бессарабська, 2",
        "passenger_id": "12345",
        "comment": "Швидко будь ласка",
    }


@pytest.fixture
def sample_trip_response():
    """Provide sample trip service response for testing."""
    return {
        "trip_id": "trip-123",
        "status": "pending",
        "pickup_location": "вул. Хрещатик, 1",
        "dropoff_location": "вул. Бессарабська, 2",
        "passenger_id": "12345",
        "created_at": "2026-01-08T10:00:00Z",
    }


@pytest.fixture
def multiple_trips():
    """Provide multiple trip data for testing."""
    return [
        {
            "trip_id": "trip-001",
            "pickup_location": "вул. Хрещатик, 1",
            "dropoff_location": "вул. Бессарабська, 2",
            "passenger_id": "11111",
            "comment": "Urgent",
        },
        {
            "trip_id": "trip-002",
            "pickup_location": "пл. Незалежності",
            "dropoff_location": "Вокзал",
            "passenger_id": "22222",
            "comment": "",
        },
        {
            "trip_id": "trip-003",
            "pickup_location": "Аеропорт",
            "dropoff_location": "Готель Київ",
            "passenger_id": "33333",
            "comment": "Багато багажу",
        },
    ]


# =============================================================================
# Environment and State Management Fixtures
# =============================================================================


@pytest.fixture
def clean_environment(monkeypatch):
    """Provide a clean test environment with environment variables."""
    monkeypatch.setenv("BOT_TOKEN", "test_token_123456789")
    monkeypatch.setenv("TRIP_SERVICE_URL", "http://localhost:8080")
    return monkeypatch


@pytest.fixture
def custom_service_url(monkeypatch):
    """Set custom trip service URL."""
    url = "http://custom-service:9090"
    monkeypatch.setenv("TRIP_SERVICE_URL", url)
    return url


@pytest.fixture(autouse=True)
def reset_global_state():
    """Automatically reset global state before each test."""
    from bot.main import user_orders, user_roles

    # Clear before test
    user_orders.clear()
    user_roles.clear()

    yield

    # Clear after test
    user_orders.clear()
    user_roles.clear()


# =============================================================================
# Async Test Support
# =============================================================================

# Note: event_loop fixture removed - pytest-asyncio provides its own
# Using custom event_loop fixtures is deprecated


# =============================================================================
# HTTP Mocking Fixtures
# =============================================================================


# =============================================================================
# Logging and Debugging Fixtures
# =============================================================================


@pytest.fixture
def disable_logging():
    """Disable logging during tests to reduce noise."""
    import logging

    logging.disable(logging.CRITICAL)
    yield
    logging.disable(logging.NOTSET)


@pytest.fixture
def capture_logs(caplog):
    """Capture logs for assertion."""
    import logging

    caplog.set_level(logging.DEBUG)
    return caplog


# =============================================================================
# Pytest Configuration
# =============================================================================


def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line("markers", "asyncio: mark test as an async test")
    config.addinivalue_line("markers", "integration: mark test as an integration test")
    config.addinivalue_line("markers", "unit: mark test as a unit test")
    config.addinivalue_line("markers", "slow: mark test as slow running")


def pytest_collection_modifyitems(config, items):
    """Modify test collection to add markers automatically."""
    for item in items:
        # Add asyncio marker to async tests
        if "asyncio" in item.keywords:
            item.add_marker(pytest.mark.asyncio)

        # Add integration marker to integration tests
        if "integration" in item.nodeid:
            item.add_marker(pytest.mark.integration)

        # Add unit marker to unit tests
        if any(x in item.nodeid for x in ["test_http_client", "test_telegram_utils"]):
            item.add_marker(pytest.mark.unit)
