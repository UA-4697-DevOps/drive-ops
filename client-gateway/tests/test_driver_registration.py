"""
Tests for driver registration and status management functionality.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

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
async def test_process_driver_car_handler_service_unavailable(mock_update, mock_context):
    """Ensure the handler surface handles service unavailability."""
    chat_id = 12345
    mock_response = {
        'success': False,
        'driver_id': None,
        'error': {
            'status_code': 503,
            'message': 'Сервіс недоступний. Спробуйте пізніше.'
        },
        'raw_response': None
    }

    mock_register = AsyncMock(return_value=mock_response)
    helpers = {
        'safe_send': main.safe_send,
        'register_driver_in_service': mock_register,
        'update_driver_status': AsyncMock(),
    }
    application = MagicMock()

    mock_context.user_data['driver_name'] = 'Test Driver'
    mock_update.effective_message.text = 'Toyota Camry'
    mock_update.message = mock_update.effective_message
    mock_update.effective_chat.id = chat_id

    driver.register_handlers(
        application,
        main.user_orders,
        main.user_roles,
        main.BUTTONS,
        main.KEYBOARDS,
        helpers,
        DEBUGGING=False
    )

    await driver.process_driver_car_handler(mock_update, mock_context)

    mock_register.assert_called_once_with(chat_id, 'Test Driver', 'Toyota Camry')
    assert chat_id not in main.user_roles

    last_reply = mock_update.message.reply_text.call_args_list[-1][0][0]
    assert 'Помилка реєстрації' in last_reply
    assert 'Сервіс недоступний' in last_reply


@pytest.mark.asyncio
async def test_process_driver_car_handler_timeout(mock_update, mock_context):
    """Ensure the handler surface handles timeouts gracefully."""
    chat_id = 12345
    mock_response = {
        'success': False,
        'driver_id': None,
        'error': {
            'status_code': 504,
            'message': 'Сервіс не відповідає. Спробуйте пізніше.'
        },
        'raw_response': None
    }

    mock_register = AsyncMock(return_value=mock_response)
    helpers = {
        'safe_send': main.safe_send,
        'register_driver_in_service': mock_register,
        'update_driver_status': AsyncMock(),
    }
    application = MagicMock()

    mock_context.user_data['driver_name'] = 'Test Driver'
    mock_update.effective_message.text = 'Toyota Camry'
    mock_update.message = mock_update.effective_message
    mock_update.effective_chat.id = chat_id

    driver.register_handlers(
        application,
        main.user_orders,
        main.user_roles,
        main.BUTTONS,
        main.KEYBOARDS,
        helpers,
        DEBUGGING=False
    )

    await driver.process_driver_car_handler(mock_update, mock_context)

    mock_register.assert_called_once_with(chat_id, 'Test Driver', 'Toyota Camry')
    assert chat_id not in main.user_roles

    last_reply = mock_update.message.reply_text.call_args_list[-1][0][0]
    assert 'Помилка реєстрації' in last_reply
    assert 'Сервіс не відповідає' in last_reply


@pytest.mark.asyncio
async def test_update_driver_status_calls_driver_service(monkeypatch):
    """Ensure `update_driver_status` hits the driver service with the expected payload."""
    driver_id = 'drv_123'
    status = 'online'
    mock_response = MagicMock(status_code=200, text='ok')
    client_instances = []

    class DummyAsyncClient:
        def __init__(self, *args, **kwargs):
            self.post = AsyncMock(return_value=mock_response)
            client_instances.append(self)

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(main.httpx, 'AsyncClient', DummyAsyncClient)

    result = await main.update_driver_status(driver_id, status)

    assert result == {'success': True, 'error': None}
    assert client_instances, 'AsyncClient should be instantiated'
    client = client_instances[-1]
    expected_url = f"{main.DRIVER_SERVICE_URL}/drivers/{driver_id}/status"
    client.post.assert_awaited_once_with(expected_url, json={'status': status})

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
    mock_register.assert_called_once_with(chat_id, 'Test Driver', 'Toyota Camry')


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


@pytest.mark.asyncio
async def test_go_online_handler_service_unavailable(mock_update, mock_context):
    """Handler keeps driver offline when the service cannot be reached."""
    chat_id = 12345
    main.user_roles[chat_id] = {
        'role': 'driver',
        'registered': True,
        'driver_id': 'drv_123',
        'name': 'Test Driver',
        'car_description': 'Toyota Camry',
        'status': 'offline'
    }

    mock_update_status = AsyncMock()
    mock_update_status.return_value = {
        'success': False,
        'error': {
            'status_code': 503,
            'message': 'Сервіс недоступний. Спробуйте пізніше.'
        }
    }

    helpers = {
        'safe_send': main.safe_send,
        'register_driver_in_service': AsyncMock(),
        'update_driver_status': mock_update_status,
    }

    application = MagicMock()

    mock_update.message = mock_update.effective_message
    mock_update.effective_chat.id = chat_id

    driver.register_handlers(application, main.user_orders, main.user_roles, main.BUTTONS, main.KEYBOARDS, helpers, DEBUGGING=False)

    await driver.go_online_handler(mock_update, mock_context)
    assert main.user_roles[chat_id]['status'] == 'offline'
    mock_update_status.assert_called_once_with('drv_123', 'online')

    last_reply = mock_update.message.reply_text.call_args_list[-1][0][0]
    assert 'Помилка' in last_reply
    assert 'Сервіс недоступний' in last_reply


# =============================================================================
# Edge Cases and Validation Tests
# =============================================================================


def _build_driver_helpers(register_return=None):
    register_mock = AsyncMock(return_value=register_return or {
        'success': True,
        'driver_id': 'drv_test',
        'error': None,
        'raw_response': {'id': 'drv_test'}
    })
    return {
        'safe_send': main.safe_send,
        'register_driver_in_service': register_mock,
        'update_driver_status': AsyncMock(),
    }, register_mock


@pytest.mark.asyncio
async def test_driver_name_validation_too_short(mock_update, mock_context):
    """Handler returns DRIVER_NAME when the supplied name is too short."""
    helpers, register_mock = _build_driver_helpers()
    application = MagicMock()
    driver.register_handlers(
        application,
        main.user_orders,
        main.user_roles,
        main.BUTTONS,
        main.KEYBOARDS,
        helpers,
        DEBUGGING=False
    )

    mock_update.effective_message.text = "A"
    mock_update.message = mock_update.effective_message

    result = await driver.process_driver_name_handler(mock_update, mock_context)

    assert result == driver.DRIVER_NAME
    last_reply = mock_update.message.reply_text.call_args[0][0]
    assert "занадто коротке" in last_reply
    register_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_driver_name_validation_accepts_valid_name(mock_update, mock_context):
    """Handler proceeds to car step when the name is valid."""
    helpers, register_mock = _build_driver_helpers()
    application = MagicMock()
    driver.register_handlers(
        application,
        main.user_orders,
        main.user_roles,
        main.BUTTONS,
        main.KEYBOARDS,
        helpers,
        DEBUGGING=False
    )

    mock_update.effective_message.text = "John Doe"
    mock_update.message = mock_update.effective_message

    result = await driver.process_driver_name_handler(mock_update, mock_context)

    assert result == driver.DRIVER_CAR
    assert mock_context.user_data['driver_name'] == "John Doe"
    last_reply = mock_update.message.reply_text.call_args_list[-1][0][0]
    assert "Опишіть ваше авто" in last_reply
    register_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_driver_car_validation_too_short(mock_update, mock_context):
    """Handler keeps asking for car description when the text is too short."""
    helpers, register_mock = _build_driver_helpers()
    application = MagicMock()
    driver.register_handlers(
        application,
        main.user_orders,
        main.user_roles,
        main.BUTTONS,
        main.KEYBOARDS,
        helpers,
        DEBUGGING=False
    )

    mock_context.user_data['driver_name'] = "Test Driver"
    mock_update.effective_message.text = "Car"
    mock_update.message = mock_update.effective_message

    result = await driver.process_driver_car_handler(mock_update, mock_context)

    assert result == driver.DRIVER_CAR
    last_reply = mock_update.message.reply_text.call_args[0][0]
    assert "Опис авто занадто короткий" in last_reply
    register_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_driver_car_validation_accepts_valid_description(mock_update, mock_context):
    """Handler registers the driver after receiving a valid car description."""
    register_mock = AsyncMock(return_value={
        'success': True,
        'driver_id': 'drv_123',
        'error': None,
        'raw_response': {'id': 'drv_123'}
    })
    helpers = {
        'safe_send': main.safe_send,
        'register_driver_in_service': register_mock,
        'update_driver_status': AsyncMock(),
    }
    application = MagicMock()
    driver.register_handlers(
        application,
        main.user_orders,
        main.user_roles,
        main.BUTTONS,
        main.KEYBOARDS,
        helpers,
        DEBUGGING=False
    )

    chat_id = mock_update.effective_chat.id
    mock_context.user_data['driver_name'] = "Test Driver"
    mock_update.effective_message.text = "Toyota Camry"
    mock_update.message = mock_update.effective_message

    result = await driver.process_driver_car_handler(mock_update, mock_context)

    assert result == driver.ConversationHandler.END
    register_mock.assert_awaited_once_with(chat_id, "Test Driver", "Toyota Camry")
    role_entry = main.user_roles.get(chat_id)
    assert role_entry and role_entry['registered'] is True
    last_reply = mock_update.message.reply_text.call_args_list[-1][0][0]
    assert "Реєстрацію завершено" in last_reply
