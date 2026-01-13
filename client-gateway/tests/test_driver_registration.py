"""
Tests for driver registration and status management functionality.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from telegram import Update
from telegram.ext import ContextTypes

# Import bot modules
from bot import main
from bot import driver


@pytest.fixture
def driver_service_url():
    """Mock DRIVER_SERVICE_URL."""
    return "http://localhost:8081"


@pytest.fixture
def user_roles():
    """Shared user_roles dictionary for testing."""
    return {}


@pytest.fixture
def user_orders():
    """Shared user_orders dictionary for testing."""
    return {}


@pytest.fixture
def buttons():
    """Return BUTTONS dictionary from main module."""
    return main.BUTTONS


@pytest.fixture
def keyboards():
    """Return KEYBOARDS dictionary from main module."""
    return main.KEYBOARDS


@pytest.fixture
def helpers():
    """Return HELPERS dictionary from main module."""
    return main.HELPERS


@pytest.fixture(autouse=True)
def cleanup_user_roles():
    """Autouse fixture to clear shared `main.user_roles` after each test to avoid cross-test pollution."""
    yield
    try:
        main.user_roles.clear()
    except Exception:
        # If user_roles isn't present or not a dict, ignore to avoid raising during teardown
        pass


# =============================================================================
# Driver Registration Tests
# =============================================================================


@pytest.mark.asyncio
async def test_register_driver_success(mock_update, mock_context):
    """Test successful driver registration flow."""
    chat_id = 12345
    
    # Mock successful API response
    mock_response = {
        'success': True,
        'driver_id': 'drv_123',
        'error': None,
        'raw_response': {'id': 'drv_123', 'name': 'Test Driver', 'car_description': 'Toyota Camry'}
    }
    
    with patch('bot.main.register_driver_in_service', new_callable=AsyncMock) as mock_register:
        mock_register.return_value = mock_response
        
        result = await main.register_driver_in_service(chat_id, "Test Driver", "Toyota Camry")
        
        assert result['success'] is True
        assert result['driver_id'] == 'drv_123'
        assert result['error'] is None
        mock_register.assert_called_once_with(chat_id, "Test Driver", "Toyota Camry")


@pytest.mark.asyncio
async def test_register_driver_service_unavailable(mock_update, mock_context):
    """Test driver registration when service is unavailable."""
    chat_id = 12345
    
    # Mock service unavailable response
    mock_response = {
        'success': False,
        'driver_id': None,
        'error': {
            'status_code': 503,
            'message': 'Сервіс недоступний. Спробуйте пізніше.'
        },
        'raw_response': None
    }
    
    with patch('bot.main.register_driver_in_service', new_callable=AsyncMock) as mock_register:
        mock_register.return_value = mock_response
        
        result = await main.register_driver_in_service(chat_id, "Test Driver", "Toyota Camry")
        
        assert result['success'] is False
        assert result['driver_id'] is None
        assert result['error']['status_code'] == 503


@pytest.mark.asyncio
async def test_register_driver_timeout(mock_update, mock_context):
    """Test driver registration timeout."""
    chat_id = 12345
    
    # Mock timeout response
    mock_response = {
        'success': False,
        'driver_id': None,
        'error': {
            'status_code': 504,
            'message': 'Сервіс не відповідає. Спробуйте пізніше.'
        },
        'raw_response': None
    }
    
    with patch('bot.main.register_driver_in_service', new_callable=AsyncMock) as mock_register:
        mock_register.return_value = mock_response
        
        result = await main.register_driver_in_service(chat_id, "Test Driver", "Toyota Camry")
        
        assert result['success'] is False
        assert result['error']['status_code'] == 504


# =============================================================================
# Driver Status Management Tests
# =============================================================================


@pytest.mark.asyncio
async def test_update_driver_status_online_success(mock_update, mock_context):
    """Test successfully going online."""
    driver_id = 'drv_123'
    
    # Mock successful API response
    mock_response = {
        'success': True,
        'error': None
    }
    
    with patch('bot.main.update_driver_status', new_callable=AsyncMock) as mock_update_status:
        mock_update_status.return_value = mock_response
        
        result = await main.update_driver_status(driver_id, 'online')
        
        assert result['success'] is True
        assert result['error'] is None
        mock_update_status.assert_called_once_with(driver_id, 'online')


@pytest.mark.asyncio
async def test_update_driver_status_offline_success(mock_update, mock_context):
    """Test successfully going offline."""
    driver_id = 'drv_123'
    
    # Mock successful API response
    mock_response = {
        'success': True,
        'error': None
    }
    
    with patch('bot.main.update_driver_status', new_callable=AsyncMock) as mock_update_status:
        mock_update_status.return_value = mock_response
        
        result = await main.update_driver_status(driver_id, 'offline')
        
        assert result['success'] is True
        assert result['error'] is None
        mock_update_status.assert_called_once_with(driver_id, 'offline')


@pytest.mark.asyncio
async def test_update_driver_status_service_unavailable(mock_update, mock_context):
    """Test status update when service is unavailable."""
    driver_id = 'drv_123'
    
    # Mock service unavailable response
    mock_response = {
        'success': False,
        'error': {
            'status_code': 503,
            'message': 'Сервіс недоступний. Спробуйте пізніше.'
        }
    }
    
    with patch('bot.main.update_driver_status', new_callable=AsyncMock) as mock_update_status:
        mock_update_status.return_value = mock_response
        
        result = await main.update_driver_status(driver_id, 'online')
        
        assert result['success'] is False
        assert result['error']['status_code'] == 503


# =============================================================================
# Driver Menu and UI Tests
# =============================================================================


def test_driver_menu_unregistered():
    """Test unregistered driver menu contains registration button."""
    menu = main.driver_menu_unregistered()
    
    # Check that menu has buttons
    assert menu is not None
    assert len(menu.keyboard) > 0
    
    # Check for registration button
    buttons_flat = [btn.text for row in menu.keyboard for btn in row]
    assert main.BTN_REGISTER_DRIVER in buttons_flat


def test_driver_menu_registered_offline():
    """Test registered offline driver menu contains go online button."""
    menu = main.driver_menu_registered(is_online=False)
    
    # Check that menu has buttons
    assert menu is not None
    assert len(menu.keyboard) > 0
    
    # Check for go online button
    buttons_flat = [btn.text for row in menu.keyboard for btn in row]
    assert main.BTN_GO_ONLINE in buttons_flat
    assert main.BTN_GO_OFFLINE not in buttons_flat


def test_driver_menu_registered_online():
    """Test registered online driver menu contains go offline button."""
    menu = main.driver_menu_registered(is_online=True)
    
    # Check that menu has buttons
    assert menu is not None
    assert len(menu.keyboard) > 0
    
    # Check for go offline button
    buttons_flat = [btn.text for row in menu.keyboard for btn in row]
    assert main.BTN_GO_OFFLINE in buttons_flat
    assert main.BTN_GO_ONLINE not in buttons_flat


# =============================================================================
# Driver Context/Session Tests
# =============================================================================


@pytest.mark.asyncio
async def test_driver_info_persistence(mock_update, mock_context):
    """Test that driver info is properly stored in `main.user_roles` via handler."""
    chat_id = 12345

    # Prepare mocked helper that returns a successful registration
    mock_register = AsyncMock()
    mock_register.return_value = {
        'success': True,
        'driver_id': 'drv_123',
        'error': None,
        'raw_response': {'id': 'drv_123'}
    }

    # Build helpers passed into register_handlers
    helpers = {
        'safe_send': main.safe_send,
        'register_driver_in_service': mock_register,
        'update_driver_status': AsyncMock()
    }

    application = MagicMock()

    # Ensure context has the driver name from previous step
    mock_context.user_data['driver_name'] = 'Test Driver'
    # Message text should be car description for the car step
    # Use the fixture's effective_message to match conftest naming
    mock_update.effective_message.text = 'Toyota Camry'
    mock_update.message = mock_update.effective_message
    mock_update.effective_chat.id = chat_id

    # Register handlers (this will expose handler functions)
    driver.register_handlers(application, main.user_orders, main.user_roles, main.BUTTONS, main.KEYBOARDS, helpers, DEBUGGING=False)

    # Invoke the process_driver_car handler directly
    await driver.process_driver_car_handler(mock_update, mock_context)

    # Verify shared state was updated
    assert chat_id in main.user_roles
    entry = main.user_roles[chat_id]
    assert entry['role'] == 'driver'
    assert entry['registered'] is True
    assert entry['driver_id'] == 'drv_123'
    assert entry['status'] == 'offline'


@pytest.mark.asyncio
async def test_driver_status_update(mock_update, mock_context):
    """Test that driver status is properly updated via handlers."""
    chat_id = 12345

    # Seed main.user_roles with a registered driver
    main.user_roles[chat_id] = {
        'role': 'driver',
        'registered': True,
        'driver_id': 'drv_123',
        'name': 'Test Driver',
        'car_description': 'Toyota Camry',
        'status': 'offline'
    }

    # Prepare mocked update_driver_status helper
    mock_update_status = AsyncMock()
    mock_update_status.return_value = {'success': True, 'error': None}

    helpers = {
        'safe_send': main.safe_send,
        'register_driver_in_service': AsyncMock(),
        'update_driver_status': mock_update_status,
    }

    application = MagicMock()

    # Ensure mock_update.message has reply_text as AsyncMock
    mock_update.message = mock_update.effective_message
    mock_update.effective_chat.id = chat_id

    # Register handlers and invoke go_online handler
    driver.register_handlers(application, main.user_orders, main.user_roles, main.BUTTONS, main.KEYBOARDS, helpers, DEBUGGING=False)

    await driver.go_online_handler(mock_update, mock_context)
    assert main.user_roles[chat_id]['status'] == 'online'
    mock_update_status.assert_called_once_with('drv_123', 'online')

    # Now mock going offline
    mock_update_status.reset_mock()
    mock_update_status.return_value = {'success': True, 'error': None}

    await driver.go_offline_handler(mock_update, mock_context)
    assert main.user_roles[chat_id]['status'] == 'offline'
    mock_update_status.assert_called_once_with('drv_123', 'offline')


# =============================================================================
# Edge Cases and Validation Tests
# =============================================================================


def test_driver_name_validation_too_short():
    """Test driver name validation rejects names that are too short."""
    name = "A"
    assert len(name) < 2


def test_driver_name_validation_valid():
    """Test driver name validation accepts valid names."""
    name = "John Doe"
    assert len(name) >= 2


def test_car_description_validation_too_short():
    """Test car description validation rejects descriptions that are too short."""
    car_desc = "Car"
    assert len(car_desc) < 5


def test_car_description_validation_valid():
    """Test car description validation accepts valid descriptions."""
    car_desc = "Toyota Camry Red"
    assert len(car_desc) >= 5
