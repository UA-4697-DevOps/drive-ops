"""
Tests for driver registration and status management functionality.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

# Import bot modules
from bot import main
from bot import driver
from bot.api_client import APIClient


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


@pytest.fixture
def mock_api_client():
    """Mock APIClient for all tests"""
    with patch.object(APIClient, 'get_bot_user') as get_user, \
         patch.object(APIClient, 'get_or_create_bot_user') as create_user, \
         patch.object(APIClient, 'register_bot_user_as_driver') as register_driver, \
         patch.object(APIClient, 'update_bot_user_driver_status') as update_status, \
         patch.object(APIClient, 'change_bot_user_role') as change_role, \
         patch.object(APIClient, 'set_bot_user_active_trip') as set_trip:

        # Default successful responses
        get_user.return_value = {'success': False, 'data': None}
        create_user.return_value = {'success': True, 'data': {'current_role': 'driver', 'driver_id': None}}
        register_driver.return_value = {'success': True, 'data': {'driver_id': 'drv_123', 'current_role': 'driver'}}
        update_status.return_value = {'success': True}
        change_role.return_value = {'success': True}
        set_trip.return_value = {'success': True}

        yield {
            'get_bot_user': get_user,
            'get_or_create_bot_user': create_user,
            'register_bot_user_as_driver': register_driver,
            'update_bot_user_driver_status': update_status,
            'change_bot_user_role': change_role,
            'set_bot_user_active_trip': set_trip,
        }


# =============================================================================
# Driver Registration Tests
# =============================================================================


@pytest.mark.asyncio
async def test_process_driver_car_handler_service_unavailable(mock_update, mock_context, mock_api_client):
    """Ensure the handler surface handles service unavailability."""
    chat_id = 12345

    # Configure APIClient to return service unavailable error
    mock_api_client['register_bot_user_as_driver'].return_value = {
        'success': False,
        'data': None,
        'error': {
            'status_code': 503,
            'message': 'Сервіс недоступний. Спробуйте пізніше.'
        }
    }

    helpers = {
        'safe_send': main.safe_send,
        'fetch_driver_trips': AsyncMock(return_value={'success': True, 'trips': [], 'error': None}),
        'send_trip_response': AsyncMock(return_value={'success': True, 'error': None}),
        'finish_trip': AsyncMock(return_value={'success': True}),
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

    mock_api_client['register_bot_user_as_driver'].assert_called_once_with(chat_id, 'Test Driver', 'Toyota Camry')

    last_reply = mock_update.message.reply_text.call_args_list[-1][0][0]
    assert 'Помилка реєстрації' in last_reply
    assert 'Сервіс недоступний' in last_reply


@pytest.mark.asyncio
async def test_process_driver_car_handler_timeout(mock_update, mock_context, mock_api_client):
    """Ensure the handler surface handles timeouts gracefully."""
    chat_id = 12345

    # Configure APIClient to return timeout error
    mock_api_client['register_bot_user_as_driver'].return_value = {
        'success': False,
        'data': None,
        'error': {
            'status_code': 504,
            'message': 'Сервіс не відповідає. Спробуйте пізніше.'
        }
    }

    helpers = {
        'safe_send': main.safe_send,
        'fetch_driver_trips': AsyncMock(return_value={'success': True, 'trips': [], 'error': None}),
        'send_trip_response': AsyncMock(return_value={'success': True, 'error': None}),
        'finish_trip': AsyncMock(return_value={'success': True}),
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

    mock_api_client['register_bot_user_as_driver'].assert_called_once_with(chat_id, 'Test Driver', 'Toyota Camry')

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
            self.patch = AsyncMock(return_value=mock_response)
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
    # Status is converted to is_active boolean and sent via PATCH
    client.patch.assert_awaited_once_with(expected_url, params={'is_active': True})

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
async def test_driver_info_persistence(mock_update, mock_context, mock_api_client):
    """Test that driver info is properly registered via API."""
    chat_id = 12345

    # Configure APIClient to return successful registration
    mock_api_client['register_bot_user_as_driver'].return_value = {
        'success': True,
        'data': {
            'driver_id': 'drv_123',
            'current_role': 'driver',
            'driver_status': 'offline'
        },
        'error': None
    }

    # Build helpers passed into register_handlers
    helpers = {
        'safe_send': main.safe_send,
        'fetch_driver_trips': AsyncMock(return_value={'success': True, 'trips': [], 'error': None}),
        'send_trip_response': AsyncMock(return_value={'success': True, 'error': None}),
        'finish_trip': AsyncMock(return_value={'success': True}),
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

    # Verify API was called correctly
    mock_api_client['register_bot_user_as_driver'].assert_called_once_with(chat_id, 'Test Driver', 'Toyota Camry')


@pytest.mark.asyncio
async def test_driver_status_update(mock_update, mock_context, mock_api_client):
    """Test that driver status is properly updated via API."""
    chat_id = 12345

    # Configure APIClient to return registered driver
    mock_api_client['get_bot_user'].return_value = {
        'success': True,
        'data': {
            'current_role': 'driver',
            'driver_id': 'drv_123',
            'driver_name': 'Test Driver',
            'car_description': 'Toyota Camry',
            'driver_status': 'offline'
        }
    }

    # Configure status update to succeed
    mock_api_client['update_bot_user_driver_status'].return_value = {'success': True}

    helpers = {
        'safe_send': main.safe_send,
        'fetch_driver_trips': AsyncMock(return_value={'success': True, 'trips': [], 'error': None}),
        'send_trip_response': AsyncMock(return_value={'success': True, 'error': None}),
        'finish_trip': AsyncMock(return_value={'success': True}),
    }

    application = MagicMock()

    # Ensure mock_update.message has reply_text as AsyncMock
    mock_update.message = mock_update.effective_message
    mock_update.effective_chat.id = chat_id

    # Register handlers and invoke go_online handler
    driver.register_handlers(application, main.user_orders, main.user_roles, main.BUTTONS, main.KEYBOARDS, helpers, DEBUGGING=False)

    await driver.go_online_handler(mock_update, mock_context)
    mock_api_client['update_bot_user_driver_status'].assert_called_with(chat_id, is_online=True)

    # Now test going offline
    mock_api_client['update_bot_user_driver_status'].reset_mock()

    await driver.go_offline_handler(mock_update, mock_context)
    mock_api_client['update_bot_user_driver_status'].assert_called_with(chat_id, is_online=False)


@pytest.mark.asyncio
async def test_go_online_handler_service_unavailable(mock_update, mock_context, mock_api_client):
    """Handler shows error when the service cannot be reached."""
    chat_id = 12345

    # Configure APIClient to return registered driver
    mock_api_client['get_bot_user'].return_value = {
        'success': True,
        'data': {
            'current_role': 'driver',
            'driver_id': 'drv_123',
            'driver_name': 'Test Driver',
            'car_description': 'Toyota Camry',
            'driver_status': 'offline'
        }
    }

    # Configure status update to fail
    mock_api_client['update_bot_user_driver_status'].return_value = {
        'success': False,
        'error': {
            'status_code': 503,
            'message': 'Сервіс недоступний. Спробуйте пізніше.'
        }
    }

    helpers = {
        'safe_send': main.safe_send,
        'fetch_driver_trips': AsyncMock(return_value={'success': True, 'trips': [], 'error': None}),
        'send_trip_response': AsyncMock(return_value={'success': True, 'error': None}),
        'finish_trip': AsyncMock(return_value={'success': True}),
    }

    application = MagicMock()

    mock_update.message = mock_update.effective_message
    mock_update.effective_chat.id = chat_id

    driver.register_handlers(application, main.user_orders, main.user_roles, main.BUTTONS, main.KEYBOARDS, helpers, DEBUGGING=False)

    await driver.go_online_handler(mock_update, mock_context)
    mock_api_client['update_bot_user_driver_status'].assert_called_once_with(chat_id, is_online=True)

    last_reply = mock_update.message.reply_text.call_args_list[-1][0][0]
    assert 'Помилка' in last_reply
    assert 'Сервіс недоступний' in last_reply


# =============================================================================
# Edge Cases and Validation Tests
# =============================================================================


def _build_driver_helpers():
    return {
        'safe_send': main.safe_send,
        'fetch_driver_trips': AsyncMock(return_value={'success': True, 'trips': [], 'error': None}),
        'send_trip_response': AsyncMock(return_value={'success': True, 'error': None}),
        'finish_trip': AsyncMock(return_value={'success': True}),
    }


@pytest.mark.asyncio
async def test_driver_name_validation_too_short(mock_update, mock_context, mock_api_client):
    """Handler returns DRIVER_NAME when the supplied name is too short."""
    helpers = _build_driver_helpers()
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
    mock_api_client['register_bot_user_as_driver'].assert_not_called()


@pytest.mark.asyncio
async def test_driver_name_validation_accepts_valid_name(mock_update, mock_context, mock_api_client):
    """Handler proceeds to car step when the name is valid."""
    helpers = _build_driver_helpers()
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
    mock_api_client['register_bot_user_as_driver'].assert_not_called()


@pytest.mark.asyncio
async def test_driver_car_validation_too_short(mock_update, mock_context, mock_api_client):
    """Handler keeps asking for car description when the text is too short."""
    helpers = _build_driver_helpers()
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
    mock_api_client['register_bot_user_as_driver'].assert_not_called()


@pytest.mark.asyncio
async def test_driver_car_validation_accepts_valid_description(mock_update, mock_context, mock_api_client):
    """Handler registers the driver after receiving a valid car description."""
    # Configure API to return successful registration
    mock_api_client['register_bot_user_as_driver'].return_value = {
        'success': True,
        'data': {
            'driver_id': 'drv_123',
            'current_role': 'driver',
            'driver_status': 'offline'
        },
        'error': None
    }

    helpers = _build_driver_helpers()
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
    mock_api_client['register_bot_user_as_driver'].assert_called_once_with(chat_id, "Test Driver", "Toyota Camry")
    last_reply = mock_update.message.reply_text.call_args_list[-1][0][0]
    assert "Реєстрацію завершено" in last_reply


# =============================================================================
# Trip Request Handling Tests
# =============================================================================


def _build_trip_helpers(fetch_trips_response=None, trip_response_result=None):
    """Build helpers dict with mocked trip-related functions."""
    fetch_mock = AsyncMock(return_value=fetch_trips_response or {
        'success': True,
        'trips': [],
        'error': None,
    })
    send_response_mock = AsyncMock(return_value=trip_response_result or {
        'success': True,
        'error': None,
    })
    return {
        'safe_send': main.safe_send,
        'register_driver_in_service': AsyncMock(),
        'update_driver_status': AsyncMock(),
        'fetch_driver_trips': fetch_mock,
        'send_trip_response': send_response_mock,
        'finish_trip': AsyncMock(return_value={'success': True}),
    }, fetch_mock, send_response_mock


@pytest.mark.asyncio
async def test_show_driver_orders_unregistered(mock_update, mock_context, mock_api_client):
    """Test that unregistered drivers cannot see orders."""
    # Configure API to return no user data
    mock_api_client['get_bot_user'].return_value = {
        'success': False,
        'data': None
    }

    helpers, fetch_mock, _ = _build_trip_helpers()
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

    mock_update.message = mock_update.effective_message

    await driver.show_driver_orders_handler(mock_update, mock_context)

    last_reply = mock_update.message.reply_text.call_args_list[-1][0][0]
    assert 'зареєструйтесь як водій' in last_reply
    fetch_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_show_driver_orders_offline(mock_update, mock_context, mock_api_client):
    """Test that offline drivers get a message to go online first."""
    chat_id = mock_update.effective_chat.id

    # Configure API to return offline driver
    mock_api_client['get_bot_user'].return_value = {
        'success': True,
        'data': {
            'current_role': 'driver',
            'driver_id': 'drv_123',
            'driver_status': 'offline',
            'active_trip_id': None
        }
    }

    helpers, fetch_mock, _ = _build_trip_helpers()
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

    mock_update.message = mock_update.effective_message

    await driver.show_driver_orders_handler(mock_update, mock_context)

    last_reply = mock_update.message.reply_text.call_args_list[-1][0][0]
    assert 'офлайн' in last_reply.lower()
    fetch_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_show_driver_orders_no_trips(mock_update, mock_context, mock_api_client):
    """Test showing empty trips list for online driver."""
    chat_id = mock_update.effective_chat.id

    # Configure API to return online driver
    mock_api_client['get_bot_user'].return_value = {
        'success': True,
        'data': {
            'current_role': 'driver',
            'driver_id': 'drv_123',
            'driver_status': 'online',
            'active_trip_id': None
        }
    }

    helpers, fetch_mock, _ = _build_trip_helpers({
        'success': True,
        'trips': [],
        'error': None,
    })
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

    mock_update.message = mock_update.effective_message

    await driver.show_driver_orders_handler(mock_update, mock_context)

    fetch_mock.assert_awaited_once_with('drv_123')
    last_reply = mock_update.message.reply_text.call_args_list[-1][0][0]
    assert 'немає нових замовлень' in last_reply


@pytest.mark.asyncio
async def test_show_driver_orders_with_trips(mock_update, mock_context, mock_api_client):
    """Test showing pending trips for online driver."""
    chat_id = mock_update.effective_chat.id

    # Configure API to return online driver
    mock_api_client['get_bot_user'].return_value = {
        'success': True,
        'data': {
            'current_role': 'driver',
            'driver_id': 'drv_123',
            'driver_status': 'online',
            'active_trip_id': None
        }
    }

    trips = [
        {'id': 'trip_001', 'status': 'PENDING', 'pickup': 'вул. Хрещатик, 1', 'dropoff': 'пл. Незалежності', 'comment': 'Швидко'},
        {'id': 'trip_002', 'status': 'PENDING', 'pickup': 'Центральний вокзал', 'dropoff': 'Аеропорт', 'comment': ''}
    ]
    helpers, fetch_mock, _ = _build_trip_helpers({
        'success': True,
        'trips': trips,
        'error': None,
    })
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

    mock_update.message = mock_update.effective_message

    await driver.show_driver_orders_handler(mock_update, mock_context)

    fetch_mock.assert_awaited_once_with('drv_123')

    # Should have called reply_text multiple times (loading + trips + summary)
    reply_calls = mock_update.message.reply_text.call_args_list
    # At least: loading message, 2 trips, summary
    assert len(reply_calls) >= 4

    # Check that trip info is displayed (underscores may be escaped for Markdown)
    all_replies = ' '.join([call[0][0] for call in reply_calls])
    # trip_001 becomes trip\_001 in Markdown, so check for either
    assert 'trip' in all_replies and '001' in all_replies
    assert 'trip' in all_replies and '002' in all_replies
    assert 'Хрещатик' in all_replies
    assert 'Знайдено замовлень: 2' in all_replies


@pytest.mark.asyncio
async def test_show_driver_orders_service_error(mock_update, mock_context, mock_api_client):
    """Test error handling when trip service is unavailable."""
    chat_id = mock_update.effective_chat.id

    # Configure API to return online driver
    mock_api_client['get_bot_user'].return_value = {
        'success': True,
        'data': {
            'current_role': 'driver',
            'driver_id': 'drv_123',
            'driver_status': 'online',
            'active_trip_id': None
        }
    }

    helpers, fetch_mock, _ = _build_trip_helpers({
        'success': False,
        'trips': [],
        'error': {'status_code': 503, 'message': 'Сервіс недоступний. Спробуйте пізніше.'},
    })
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

    mock_update.message = mock_update.effective_message

    await driver.show_driver_orders_handler(mock_update, mock_context)

    fetch_mock.assert_awaited_once_with('drv_123')
    last_reply = mock_update.message.reply_text.call_args_list[-1][0][0]
    assert 'Помилка отримання замовлень' in last_reply
    assert 'Сервіс недоступний' in last_reply


@pytest.mark.asyncio
async def test_accept_trip_success(mock_update, mock_context, mock_callback_query, mock_api_client):
    """Test successful trip acceptance."""
    chat_id = 12345

    # Configure API to return online driver
    mock_api_client['get_bot_user'].return_value = {
        'success': True,
        'data': {
            'current_role': 'driver',
            'driver_id': 'drv_123',
            'driver_status': 'online',
            'active_trip_id': None
        }
    }

    helpers, _, send_mock = _build_trip_helpers(
        trip_response_result={'success': True, 'error': None}
    )
    application = MagicMock()

    mock_callback_query.data = 'accept_trip_trip_001'
    mock_callback_query.message.chat.id = chat_id
    mock_update.callback_query = mock_callback_query

    driver.register_handlers(
        application,
        main.user_orders,
        main.user_roles,
        main.BUTTONS,
        main.KEYBOARDS,
        helpers,
        DEBUGGING=False
    )

    await driver.accept_trip_handler(mock_update, mock_context)

    mock_callback_query.answer.assert_awaited_once()
    send_mock.assert_awaited_once_with('drv_123', 'trip_001', 'accept')

    # Check final message contains success
    last_edit = mock_callback_query.edit_message_text.call_args_list[-1]
    assert 'прийнято' in last_edit[1]['text'].lower()


@pytest.mark.asyncio
async def test_accept_trip_expired(mock_update, mock_context, mock_callback_query, mock_api_client):
    """Test accepting an expired trip."""
    chat_id = 12345

    # Configure API to return online driver
    mock_api_client['get_bot_user'].return_value = {
        'success': True,
        'data': {
            'current_role': 'driver',
            'driver_id': 'drv_123',
            'driver_status': 'online',
            'active_trip_id': None
        }
    }

    helpers, _, send_mock = _build_trip_helpers(
        trip_response_result={
            'success': False,
            'error': {'status_code': 410, 'message': 'Замовлення вже недоступне'}
        }
    )
    application = MagicMock()

    mock_callback_query.data = 'accept_trip_trip_001'
    mock_callback_query.message.chat.id = chat_id
    mock_update.callback_query = mock_callback_query

    driver.register_handlers(
        application,
        main.user_orders,
        main.user_roles,
        main.BUTTONS,
        main.KEYBOARDS,
        helpers,
        DEBUGGING=False
    )

    await driver.accept_trip_handler(mock_update, mock_context)

    send_mock.assert_awaited_once_with('drv_123', 'trip_001', 'accept')

    last_edit = mock_callback_query.edit_message_text.call_args_list[-1]
    assert 'недоступне' in last_edit[1]['text'].lower()


@pytest.mark.asyncio
async def test_decline_trip_success(mock_update, mock_context, mock_callback_query, mock_api_client):
    """Test successful trip rejection."""
    chat_id = 12345

    # Configure API to return online driver
    mock_api_client['get_bot_user'].return_value = {
        'success': True,
        'data': {
            'current_role': 'driver',
            'driver_id': 'drv_123',
            'driver_status': 'online',
            'active_trip_id': None
        }
    }

    helpers, _, send_mock = _build_trip_helpers(
        trip_response_result={'success': True, 'error': None}
    )
    application = MagicMock()

    mock_callback_query.data = 'decline_trip_trip_001'
    mock_callback_query.message.chat.id = chat_id
    mock_update.callback_query = mock_callback_query

    driver.register_handlers(
        application,
        main.user_orders,
        main.user_roles,
        main.BUTTONS,
        main.KEYBOARDS,
        helpers,
        DEBUGGING=False
    )

    await driver.decline_trip_handler(mock_update, mock_context)

    mock_callback_query.answer.assert_awaited_once()
    send_mock.assert_awaited_once_with('drv_123', 'trip_001', 'reject')

    last_edit = mock_callback_query.edit_message_text.call_args_list[-1]
    assert 'відхилено' in last_edit[1]['text'].lower()


@pytest.mark.asyncio
async def test_decline_trip_service_unavailable(mock_update, mock_context, mock_callback_query, mock_api_client):
    """Test rejecting trip when service is unavailable."""
    chat_id = 12345

    # Configure API to return online driver
    mock_api_client['get_bot_user'].return_value = {
        'success': True,
        'data': {
            'current_role': 'driver',
            'driver_id': 'drv_123',
            'driver_status': 'online',
            'active_trip_id': None
        }
    }

    helpers, _, send_mock = _build_trip_helpers(
        trip_response_result={
            'success': False,
            'error': {'status_code': 503, 'message': 'Сервіс недоступний. Спробуйте пізніше.'}
        }
    )
    application = MagicMock()

    mock_callback_query.data = 'decline_trip_trip_001'
    mock_callback_query.message.chat.id = chat_id
    mock_update.callback_query = mock_callback_query

    driver.register_handlers(
        application,
        main.user_orders,
        main.user_roles,
        main.BUTTONS,
        main.KEYBOARDS,
        helpers,
        DEBUGGING=False
    )

    await driver.decline_trip_handler(mock_update, mock_context)

    send_mock.assert_awaited_once_with('drv_123', 'trip_001', 'reject')

    last_edit = mock_callback_query.edit_message_text.call_args_list[-1]
    assert 'помилка' in last_edit[1]['text'].lower()


@pytest.mark.asyncio
async def test_accept_trip_unregistered_driver(mock_update, mock_context, mock_callback_query, mock_api_client):
    """Test that unregistered drivers cannot accept trips."""
    chat_id = 12345

    # Configure API to return no user
    mock_api_client['get_bot_user'].return_value = {
        'success': False,
        'data': None
    }

    helpers, _, send_mock = _build_trip_helpers()
    application = MagicMock()

    mock_callback_query.data = 'accept_trip_trip_001'
    mock_callback_query.message.chat.id = chat_id
    mock_update.callback_query = mock_callback_query

    driver.register_handlers(
        application,
        main.user_orders,
        main.user_roles,
        main.BUTTONS,
        main.KEYBOARDS,
        helpers,
        DEBUGGING=False
    )

    await driver.accept_trip_handler(mock_update, mock_context)

    send_mock.assert_not_awaited()
    last_edit = mock_callback_query.edit_message_text.call_args_list[-1]
    assert 'не зареєстровані' in last_edit[1]['text'].lower()


@pytest.mark.asyncio
async def test_fetch_driver_trips_calls_driver_service(monkeypatch):
    """Ensure `fetch_driver_trips` hits the driver service with the expected URL."""
    driver_id = 'drv_123'
    mock_response = MagicMock(
        status_code=200,
        json=MagicMock(return_value={'trips': [{'id': 'trip_001', 'pickup': 'A', 'dropoff': 'B'}]})
    )
    client_instances = []

    class DummyAsyncClient:
        def __init__(self, *args, **kwargs):
            self.get = AsyncMock(return_value=mock_response)
            client_instances.append(self)

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(main.httpx, 'AsyncClient', DummyAsyncClient)

    result = await main.fetch_driver_trips(driver_id)

    assert result['success'] is True
    assert len(result['trips']) == 1
    assert result['trips'][0]['id'] == 'trip_001'
    
    assert client_instances, 'AsyncClient should be instantiated'
    client = client_instances[-1]
    expected_url = f"{main.DRIVER_SERVICE_URL}/drivers/{driver_id}/trips"
    client.get.assert_awaited_once_with(expected_url)


@pytest.mark.asyncio
async def test_send_trip_response_accept(monkeypatch):
    """Ensure `send_trip_response` sends accept request to correct endpoint."""
    driver_id = 'drv_123'
    trip_id = 'trip_001'
    mock_response = MagicMock(status_code=200, text='ok')
    mock_response.json.return_value = {
        'pickup_address': 'Test Pickup',
        'dropoff_address': 'Test Dropoff'
    }
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

    result = await main.send_trip_response(driver_id, trip_id, 'accept')

    assert result == {
        'success': True,
        'error': None,
        'pickup_address': 'Test Pickup',
        'dropoff_address': 'Test Dropoff'
    }
    assert client_instances, 'AsyncClient should be instantiated'
    client = client_instances[-1]
    expected_url = f"{main.DRIVER_SERVICE_URL}/drivers/{driver_id}/trips/{trip_id}/accept"
    client.post.assert_awaited_once_with(expected_url)


@pytest.mark.asyncio
async def test_send_trip_response_reject(monkeypatch):
    """Ensure `send_trip_response` sends reject request to correct endpoint."""
    driver_id = 'drv_123'
    trip_id = 'trip_001'
    mock_response = MagicMock(status_code=200, text='ok')
    mock_response.json.return_value = {}
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

    result = await main.send_trip_response(driver_id, trip_id, 'reject')

    assert result == {
        'success': True,
        'error': None,
        'pickup_address': None,
        'dropoff_address': None
    }
    assert client_instances, 'AsyncClient should be instantiated'
    client = client_instances[-1]
    expected_url = f"{main.DRIVER_SERVICE_URL}/drivers/{driver_id}/trips/{trip_id}/reject"
    client.post.assert_awaited_once_with(expected_url)


@pytest.mark.asyncio
async def test_send_trip_response_invalid_action():
    """Ensure `send_trip_response` rejects invalid actions."""
    result = await main.send_trip_response('drv_123', 'trip_001', 'invalid_action')

    assert result['success'] is False
    assert result['error']['status_code'] == 400
    assert 'Invalid action' in result['error']['message']
