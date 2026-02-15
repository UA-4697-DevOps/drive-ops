import os
import sys
import time
import re
import uuid
import httpx
import hashlib
import warnings
import asyncio
import signal
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters
from dotenv import load_dotenv
from fastapi import FastAPI
import uvicorn
from . import passenger
from . import driver
from .logger_utils import create_trip_request_logger, generate_correlation_id
from .api_client import APIClient

logger = create_trip_request_logger()

load_dotenv()
BOT_TOKEN = os.getenv('BOT_TOKEN')
TRIP_SERVICE_URL = os.getenv('TRIP_SERVICE_URL')
DRIVER_SERVICE_URL = os.getenv('DRIVER_SERVICE_URL')

_missing_vars = [
    name for name, val in {
        'TRIP_SERVICE_URL': TRIP_SERVICE_URL,
        'DRIVER_SERVICE_URL': DRIVER_SERVICE_URL,
    }.items()
    if not val
]
if _missing_vars:
    sys.exit(f"ERROR: Required environment variables not set: {', '.join(_missing_vars)}")
# Parse HEALTH_CHECK_PORT with fallback to 8080 for invalid/missing values
try:
    HEALTH_CHECK_PORT = int(os.getenv('HEALTH_CHECK_PORT', '8080'))
except (ValueError, TypeError):
    HEALTH_CHECK_PORT = 8080

DEBUGGING = os.getenv('DEBUG', 'False').lower() in ('true', '1', 't')

logger.info("DEBUG env var: %s", os.getenv('DEBUG'), extra={'correlationId': 'STARTUP'})
logger.info("DEBUGGING mode: %s", DEBUGGING, extra={'correlationId': 'STARTUP'})


def ensure_bot_token():
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN is not set in the environment or .env file.")
        sys.exit("ERROR: BOT_TOKEN is not configured.")

# Keep user_orders in memory for now (temporary state)
user_orders = {}
# user_roles kept as empty dict for backward compatibility with passenger/driver modules
# Actual role data is now stored in database via API
user_roles = {}

BTN_PASSENGER = "\U0001F64B Я замовник таксі"
BTN_DRIVER = "\U0001F697 Я таксист"
BTN_MY_ORDERS = "\U0001F4CB Мої замовлення"
BTN_ORDER_TAXI = "\U0001F695 Замовити таксі"
BTN_RATES = "\U0001F4B0 Тарифи"
BTN_SKIP = "\u23E9 Пропустити"
BTN_CHANGE_ROLE = "\U0001F504 Змінити роль"
BTN_REGISTER_DRIVER = "\U0001F4DD Зареєструватися як водій"
BTN_GO_ONLINE = "\U0001F7E2 Приймати замовлення"
BTN_GO_OFFLINE = "\U0001F534 Не приймати замовлення"
BTN_DRIVER_STATUS = "\U0001F4CA Мій статус"
BTN_FINISH_TRIP = "\U0001F3C1 Завершити поїздку"
BTN_CHECK_STATUS = "\U0001F50D Перевірити статус"

BUTTONS = {
    'BTN_PASSENGER': BTN_PASSENGER,
    'BTN_DRIVER': BTN_DRIVER,
    'BTN_MY_ORDERS': BTN_MY_ORDERS,
    'BTN_ORDER_TAXI': BTN_ORDER_TAXI,
    'BTN_RATES': BTN_RATES,
    'BTN_SKIP': BTN_SKIP,
    'BTN_CHANGE_ROLE': BTN_CHANGE_ROLE,
    'BTN_REGISTER_DRIVER': BTN_REGISTER_DRIVER,
    'BTN_GO_ONLINE': BTN_GO_ONLINE,
    'BTN_GO_OFFLINE': BTN_GO_OFFLINE,
    'BTN_DRIVER_STATUS': BTN_DRIVER_STATUS,
    'BTN_FINISH_TRIP': BTN_FINISH_TRIP,
    'BTN_CHECK_STATUS': BTN_CHECK_STATUS,
}

def role_selection_menu():
    keyboard = [[KeyboardButton(BTN_PASSENGER), KeyboardButton(BTN_DRIVER)]]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)

def passenger_menu():
    keyboard = [
        [KeyboardButton(BTN_ORDER_TAXI), KeyboardButton(BTN_RATES)],
        [KeyboardButton(BTN_CHECK_STATUS)],
        [KeyboardButton(BTN_CHANGE_ROLE)]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def driver_menu():
    keyboard = [
        [KeyboardButton(BTN_MY_ORDERS)],
        [KeyboardButton(BTN_CHANGE_ROLE)]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def driver_menu_unregistered():
    keyboard = [
        [KeyboardButton(BTN_REGISTER_DRIVER)],
        [KeyboardButton(BTN_CHANGE_ROLE)]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def driver_menu_registered(is_online=False, active_trip=False):
    keyboard = [
        [KeyboardButton(BTN_MY_ORDERS), KeyboardButton(BTN_DRIVER_STATUS)],
    ]
    
    if active_trip:
        keyboard.append([KeyboardButton(BTN_FINISH_TRIP)])
    else:
        keyboard.append([KeyboardButton(BTN_GO_OFFLINE if is_online else BTN_GO_ONLINE)])
    
    keyboard.append([KeyboardButton(BTN_CHANGE_ROLE)])
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def skip_menu():
    keyboard = [[KeyboardButton(BTN_SKIP)]]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)

def get_user_menu(chat_id):
    """
    Get user menu based on current role.
    Note: This is a fallback function, actual role is managed via API in async handlers.
    Returns passenger menu by default.
    """
    # This function is kept synchronous for backward compatibility with KEYBOARDS dict
    # Actual role switching is handled in async handler functions via API
    return passenger_menu()  # Default to passenger menu

KEYBOARDS = {
    'role_selection_menu': role_selection_menu,
    'passenger_menu': passenger_menu,
    'driver_menu': driver_menu,
    'driver_menu_unregistered': driver_menu_unregistered,
    'driver_menu_registered': driver_menu_registered,
    'skip_menu': skip_menu,
    'get_user_menu': get_user_menu,
}

def is_valid_address(address):
    return address is not None and len(address) > 5


async def fetch_trip_status(trip_id, user_id=None):
    """
    Fetch trip status from the trip service.
    
    Args:
        trip_id: The UUID of the trip to check
        user_id: The ID of the user making the request (for logging)
    
    Returns:
        Dictionary with success status, trip data, error details, etc.
    """
    start_time = time.time()
    correlation_id = generate_correlation_id()
    
    logger.info(
        "Trip status check initiated: user_id=%s trip_id=%s",
        user_id, trip_id,
        extra={'correlationId': correlation_id}
    )
    
    try:
        url = f"{TRIP_SERVICE_URL}/trips/{trip_id}"
        logger.info(
            "Sending GET %s",
            url,
            extra={'correlationId': correlation_id}
        )
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url)
        
        latency = int((time.time() - start_time) * 1000)
        
        if resp.status_code == 200:
            data = resp.json()
            logger.info(
                "Trip status check SUCCESS: user_id=%s trip_id=%s status=%s latency=%dms",
                user_id, trip_id, data.get('status'), latency,
                extra={'correlationId': correlation_id}
            )
            
            return {
                'success': True,
                'trip': data,
                'error': None,
            }
        elif resp.status_code == 404:
            logger.warning(
                "Trip status check NOT_FOUND: user_id=%s trip_id=%s latency=%dms",
                user_id, trip_id, latency,
                extra={'correlationId': correlation_id}
            )
            return {
                'success': False,
                'trip': None,
                'error': {
                    'status_code': 404,
                    'message': 'Поїздку не знайдено',
                },
            }
        else:
            response_preview = resp.text.encode('utf-8')[:200].decode('utf-8', errors='ignore')
            logger.error(
                "Trip status check FAILED: user_id=%s trip_id=%s status_code=%s latency=%dms response=%s",
                user_id, trip_id, resp.status_code, latency, response_preview,
                extra={'correlationId': correlation_id}
            )
            return {
                'success': False,
                'trip': None,
                'error': {
                    'status_code': resp.status_code,
                    'message': resp.text or 'Помилка сервісу',
                },
            }
    except httpx.TimeoutException:
        latency = int((time.time() - start_time) * 1000)
        logger.error(
            "Trip status check TIMEOUT: user_id=%s trip_id=%s latency=%dms",
            user_id, trip_id, latency,
            extra={'correlationId': correlation_id}
        )
        return {
            'success': False,
            'trip': None,
            'error': {
                'status_code': 504,
                'message': 'Сервіс не відповідає. Спробуйте пізніше.',
            },
        }
    except httpx.ConnectError:
        latency = int((time.time() - start_time) * 1000)
        logger.error(
            "Trip status check CONNECTION_ERROR: user_id=%s trip_id=%s latency=%dms",
            user_id, trip_id, latency,
            extra={'correlationId': correlation_id}
        )
        return {
            'success': False,
            'trip': None,
            'error': {
                'status_code': 503,
                'message': 'Сервіс недоступний. Спробуйте пізніше.',
            },
        }
    except Exception as e:
        latency = int((time.time() - start_time) * 1000)
        logger.exception(
            "Trip status check UNEXPECTED_ERROR: user_id=%s trip_id=%s latency=%dms error=%s",
            user_id, trip_id, latency, str(e),
            extra={'correlationId': correlation_id}
        )
        return {
            'success': False,
            'trip': None,
            'error': {
                'status_code': 500,
                'message': str(e),
            },
        }


async def safe_send(chat_id, text, context, **kwargs):
    try:
        return await context.bot.send_message(chat_id, text, **kwargs)
    except Exception as e:
        logger.exception("Failed to send message to %s: %s", chat_id, e)
        return None

async def safe_edit_message_text(chat_id, message_id, text, context, **kwargs):
    try:
        return await context.bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=text, **kwargs)
    except Exception as e:
        logger.exception("Failed to edit message %s/%s: %s", chat_id, message_id, e)
        return None

def sanitize_payload(payload):
    """
    Sanitize payload by masking PII fields (addresses, locations).

    Args:
        payload: Dictionary with trip data

    Returns:
        Dictionary with sensitive fields masked
    """
    sanitized = payload.copy()

    # Mask address fields
    pii_fields = ['pickup', 'dropoff', 'address', 'location']
    for field in pii_fields:
        if field in sanitized and sanitized[field]:
            # Show only first 3 chars + ***
            value = str(sanitized[field])
            sanitized[field] = f"{value[:3]}***" if len(value) > 3 else "***"

    return sanitized

async def submit_trip_request(chat_id, order):
    """
    Submit a trip request to the trip service.
    Logs the full lifecycle: request init -> validation -> response.

    Args:
        chat_id: Telegram user chat ID
        order: Dictionary with 'pickup' and 'dropoff' fields

    Returns:
        Dictionary with success status, trip_id, error details, etc.
    """
    start_time = time.time()
    correlation_id = generate_correlation_id()

    # Validate and normalize passenger_id
    provided_passenger_id = order.get('passenger_id')
    if provided_passenger_id:
        try:
            # Validate it's a proper UUID format
            uuid.UUID(str(provided_passenger_id))
            passenger_uuid = str(provided_passenger_id)
        except (ValueError, AttributeError):
            # Invalid UUID, fall back to generated one
            logger.warning(
                "Invalid passenger_id provided: %s, generating deterministic UUID",
                provided_passenger_id
            )
            passenger_uuid = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"telegram-{chat_id}"))
    else:
        # No passenger_id provided, generate deterministic UUID from chat_id
        passenger_uuid = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"telegram-{chat_id}"))

    payload = {
        'pickup': order.get('pickup'),
        'dropoff': order.get('dropoff'),
        'passenger_id': passenger_uuid,
    }
    
    request_id = f"REQ-{chat_id}-{int(time.time())}"
    
    logger.info(
        "Trip request initiated: chat_id=%s request_id=%s",
        chat_id, request_id,
        extra={'correlationId': correlation_id}
    )
    
    try:
        url = f"{TRIP_SERVICE_URL}/trips"
        # Sanitize payload before logging to protect PII
        sanitized_payload = sanitize_payload(payload)
        logger.info(
            "Sending POST %s with payload=%s",
            url, sanitized_payload,
            extra={'correlationId': correlation_id}
        )
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(url, json=payload)
        
        latency = int((time.time() - start_time) * 1000)
        
        if resp.status_code in (200, 201):
            data = resp.json()
            trip_id = data.get('id') or data.get('trip_id') or request_id
            status = data.get('status', 'pending')
            
            logger.info(
                "Trip request SUCCESS: trip_id=%s status=%s latency=%dms",
                trip_id, status, latency,
                extra={'correlationId': correlation_id}
            )
            
            return {
                'success': True,
                'trip_id': trip_id,
                'request_id': request_id,
                'status': status,
                'error': None,
                'raw_response': data,
            }
        else:
            response_preview = resp.text.encode('utf-8')[:200].decode('utf-8', errors='ignore')
            logger.error(
                "Trip request FAILED: status_code=%s latency=%dms response=%s",
                resp.status_code, latency, response_preview,
                extra={'correlationId': correlation_id}
            )
            return {
                'success': False,
                'trip_id': None,
                'request_id': request_id,
                'status': 'error',
                'error': {
                    'status_code': resp.status_code,
                    'message': resp.text or 'Unknown error',
                },
                'raw_response': None,
            }
    except httpx.TimeoutException:
        latency = int((time.time() - start_time) * 1000)
        logger.error(
            "Trip request TIMEOUT: chat_id=%s latency=%dms request_id=%s",
            chat_id, latency, request_id,
            extra={'correlationId': correlation_id}
        )
        return {
            'success': False,
            'trip_id': None,
            'request_id': request_id,
            'status': 'error',
            'error': {
                'status_code': 504,
                'message': 'Сервіс не відповідає. Спробуйте пізніше.',
            },
            'raw_response': None,
        }
    except httpx.ConnectError:
        latency = int((time.time() - start_time) * 1000)
        logger.error(
            "Trip request CONNECTION_ERROR: chat_id=%s latency=%dms request_id=%s",
            chat_id, latency, request_id,
            extra={'correlationId': correlation_id}
        )
        return {
            'success': False,
            'trip_id': None,
            'request_id': request_id,
            'status': 'error',
            'error': {
                'status_code': 503,
                'message': 'Сервіс недоступний. Спробуйте пізніше.',
            },
            'raw_response': None,
        }
    except Exception as e:
        latency = int((time.time() - start_time) * 1000)
        logger.exception(
            "Trip request UNEXPECTED_ERROR: chat_id=%s latency=%dms request_id=%s error=%s",
            chat_id, latency, request_id, str(e),
            extra={'correlationId': correlation_id}
        )
        return {
            'success': False,
            'trip_id': None,
            'request_id': request_id,
            'status': 'error',
            'error': {
                'status_code': 500,
                'message': str(e),
            },
            'raw_response': None,
        }

async def register_driver_in_service(chat_id, name, car_description):
    """
    Register a new driver in the Driver Service.
    
    Args:
        chat_id: Telegram user chat ID
        name: Driver's name
        car_description: Description of the driver's car
    
    Returns:
        Dictionary with success status, driver_id, error details, etc.
    """
    start_time = time.time()
    correlation_id = generate_correlation_id()
    
    # Split name into first_name and last_name (simple split by space)
    name_parts = name.strip().split(maxsplit=1)
    first_name = name_parts[0] if name_parts else "Driver"
    last_name = name_parts[1] if len(name_parts) > 1 else str(chat_id)

    payload = {
        'first_name': first_name,
        'last_name': last_name,
        'phone_number': f"+{chat_id}",  # Use Telegram ID as phone for now
        'is_active': True
    }
    
    # Sanitize PII for logs: use short hashes instead of raw values
    try:
        sanitized_name = hashlib.sha256(name.encode()).hexdigest()[:8] if name else 'none'
    except Exception:
        sanitized_name = 'err'
    try:
        sanitized_car = hashlib.sha256(car_description.encode()).hexdigest()[:8] if car_description else 'none'
    except Exception:
        sanitized_car = 'err'

    logger.info(
        "Driver registration initiated: chat_id=%s name_hash=%s",
        chat_id, sanitized_name,
        extra={'correlationId': correlation_id}
    )
    
    try:
        url = f"{DRIVER_SERVICE_URL}/drivers"
        logger.info(
            "Sending POST %s with name_hash=%s, car_hash=%s",
            url, sanitized_name, sanitized_car,
            extra={'correlationId': correlation_id}
        )
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(url, json=payload)
        
        latency = int((time.time() - start_time) * 1000)
        
        if resp.status_code in (200, 201):
            data = resp.json()
            driver_id = data.get('id') or data.get('driver_id')
            
            logger.info(
                "Driver registration SUCCESS: driver_id=%s latency=%dms",
                driver_id, latency,
                extra={'correlationId': correlation_id}
            )
            
            return {
                'success': True,
                'driver_id': driver_id,
                'error': None,
                'raw_response': data,
            }
        else:
            response_preview = resp.text.encode('utf-8')[:200].decode('utf-8', errors='ignore')
            logger.error(
                "Driver registration FAILED: status_code=%s latency=%dms response=%s",
                resp.status_code, latency, response_preview,
                extra={'correlationId': correlation_id}
            )
            return {
                'success': False,
                'driver_id': None,
                'error': {
                    'status_code': resp.status_code,
                    'message': resp.text or 'Помилка при реєстрації',
                },
                'raw_response': None,
            }
    except httpx.TimeoutException:
        latency = int((time.time() - start_time) * 1000)
        logger.error(
            "Driver registration TIMEOUT: chat_id=%s latency=%dms",
            chat_id, latency,
            extra={'correlationId': correlation_id}
        )
        return {
            'success': False,
            'driver_id': None,
            'error': {
                'status_code': 504,
                'message': 'Сервіс не відповідає. Спробуйте пізніше.',
            },
            'raw_response': None,
        }
    except httpx.ConnectError:
        latency = int((time.time() - start_time) * 1000)
        logger.error(
            "Driver registration CONNECTION_ERROR: chat_id=%s latency=%dms",
            chat_id, latency,
            extra={'correlationId': correlation_id}
        )
        return {
            'success': False,
            'driver_id': None,
            'error': {
                'status_code': 503,
                'message': 'Сервіс недоступний. Спробуйте пізніше.',
            },
            'raw_response': None,
        }
    except Exception as e:
        latency = int((time.time() - start_time) * 1000)
        logger.exception(
            "Driver registration UNEXPECTED_ERROR: chat_id=%s latency=%dms error=%s",
            chat_id, latency, str(e),
            extra={'correlationId': correlation_id}
        )
        return {
            'success': False,
            'driver_id': None,
            'error': {
                'status_code': 500,
                'message': str(e),
            },
            'raw_response': None,
        }

async def update_driver_status(driver_id, status):
    """
    Update driver's online/offline status in the Driver Service.

    Args:
        driver_id: The driver's ID
        status: 'online' or 'offline' (will be converted to uppercase for API)

    Returns:
        Dictionary with success status and error details if any.
    """
    start_time = time.time()
    correlation_id = generate_correlation_id()
    
    # Validate status input to prevent sending invalid values downstream
    allowed_statuses = ('online', 'offline')
    if status not in allowed_statuses:
        logger.error(
            "Driver status update INVALID_INPUT: driver_id=%s status=%s",
            driver_id, status,
            extra={'correlationId': correlation_id}
        )
        return {
            'success': False,
            'error': {
                'status_code': 400,
                'message': f"Invalid status '{status}'. Allowed: {allowed_statuses}",
            },
        }

    logger.info(
        "Driver status update initiated: driver_id=%s status=%s",
        driver_id, status,
        extra={'correlationId': correlation_id}
    )

    try:
        url = f"{DRIVER_SERVICE_URL}/drivers/{driver_id}/status"
        # Convert status to is_active boolean (online → True, offline → False)
        is_active = (status.lower() == 'online')
        logger.info(
            "Sending PATCH %s with is_active=%s",
            url, is_active,
            extra={'correlationId': correlation_id}
        )

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.patch(url, params={'is_active': is_active})
        
        latency = int((time.time() - start_time) * 1000)
        
        if resp.status_code in (200, 201, 204):
            logger.info(
                "Driver status update SUCCESS: driver_id=%s status=%s latency=%dms",
                driver_id, status, latency,
                extra={'correlationId': correlation_id}
            )
            
            return {
                'success': True,
                'error': None,
            }
        else:
            response_preview = resp.text.encode('utf-8')[:200].decode('utf-8', errors='ignore')
            logger.error(
                "Driver status update FAILED: status_code=%s latency=%dms response=%s",
                resp.status_code, latency, response_preview,
                extra={'correlationId': correlation_id}
            )
            return {
                'success': False,
                'error': {
                    'status_code': resp.status_code,
                    'message': resp.text or 'Помилка при оновленні статусу',
                },
            }
    except httpx.TimeoutException:
        latency = int((time.time() - start_time) * 1000)
        logger.error(
            "Driver status update TIMEOUT: driver_id=%s latency=%dms",
            driver_id, latency,
            extra={'correlationId': correlation_id}
        )
        return {
            'success': False,
            'error': {
                'status_code': 504,
                'message': 'Сервіс не відповідає. Спробуйте пізніше.',
            },
        }
    except httpx.ConnectError:
        latency = int((time.time() - start_time) * 1000)
        logger.error(
            "Driver status update CONNECTION_ERROR: driver_id=%s latency=%dms",
            driver_id, latency,
            extra={'correlationId': correlation_id}
        )
        return {
            'success': False,
            'error': {
                'status_code': 503,
                'message': 'Сервіс недоступний. Спробуйте пізніше.',
            },
        }
    except Exception as e:
        latency = int((time.time() - start_time) * 1000)
        logger.exception(
            "Driver status update UNEXPECTED_ERROR: driver_id=%s latency=%dms error=%s",
            driver_id, latency, str(e),
            extra={'correlationId': correlation_id}
        )
        return {
            'success': False,
            'error': {
                'status_code': 500,
                'message': str(e),
            },
        }


async def fetch_driver_trips(driver_id):
    """
    Fetch pending trip requests assigned to a driver from the Driver Service.
    
    Args:
        driver_id: The driver's ID
    
    Returns:
        Dictionary with success status, trips list, and error details if any.
    """
    start_time = time.time()
    correlation_id = generate_correlation_id()
    
    logger.info(
        "Fetching driver trips: driver_id=%s",
        driver_id,
        extra={'correlationId': correlation_id}
    )
    
    try:
        url = f"{DRIVER_SERVICE_URL}/drivers/{driver_id}/trips"
        logger.info(
            "Sending GET %s",
            url,
            extra={'correlationId': correlation_id}
        )
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url)
        
        latency = int((time.time() - start_time) * 1000)
        
        if resp.status_code in (200, 201):
            data = resp.json()
            trips = data.get('trips', []) if isinstance(data, dict) else data if isinstance(data, list) else []
            
            logger.info(
                "Fetch driver trips SUCCESS: driver_id=%s trip_count=%d latency=%dms",
                driver_id, len(trips), latency,
                extra={'correlationId': correlation_id}
            )
            
            return {
                'success': True,
                'trips': trips,
                'error': None,
                'raw_response': data,
            }
        elif resp.status_code == 404:
            logger.info(
                "Fetch driver trips: no trips found driver_id=%s latency=%dms",
                driver_id, latency,
                extra={'correlationId': correlation_id}
            )
            return {
                'success': True,
                'trips': [],
                'error': None,
                'raw_response': None,
            }
        else:
            response_preview = resp.text.encode('utf-8')[:200].decode('utf-8', errors='ignore')
            logger.error(
                "Fetch driver trips FAILED: status_code=%s latency=%dms response=%s",
                resp.status_code, latency, response_preview,
                extra={'correlationId': correlation_id}
            )
            return {
                'success': False,
                'trips': [],
                'error': {
                    'status_code': resp.status_code,
                    'message': resp.text or 'Помилка при отриманні замовлень',
                },
                'raw_response': None,
            }
    except httpx.TimeoutException:
        latency = int((time.time() - start_time) * 1000)
        logger.error(
            "Fetch driver trips TIMEOUT: driver_id=%s latency=%dms",
            driver_id, latency,
            extra={'correlationId': correlation_id}
        )
        return {
            'success': False,
            'trips': [],
            'error': {
                'status_code': 504,
                'message': 'Сервіс не відповідає. Спробуйте пізніше.',
            },
            'raw_response': None,
        }
    except httpx.ConnectError:
        latency = int((time.time() - start_time) * 1000)
        logger.error(
            "Fetch driver trips CONNECTION_ERROR: driver_id=%s latency=%dms",
            driver_id, latency,
            extra={'correlationId': correlation_id}
        )
        return {
            'success': False,
            'trips': [],
            'error': {
                'status_code': 503,
                'message': 'Сервіс недоступний. Спробуйте пізніше.',
            },
            'raw_response': None,
        }
    except Exception as e:
        latency = int((time.time() - start_time) * 1000)
        logger.exception(
            "Fetch driver trips UNEXPECTED_ERROR: driver_id=%s latency=%dms error=%s",
            driver_id, latency, str(e),
            extra={'correlationId': correlation_id}
        )
        return {
            'success': False,
            'trips': [],
            'error': {
                'status_code': 500,
                'message': str(e),
            },
            'raw_response': None,
        }


async def finish_trip(driver_id, trip_id):
    """
    Mark a trip as completed by the driver.
    
    Args:
        driver_id: The driver's ID
        trip_id: The trip's ID to finish
    
    Returns:
        Dictionary with success status and error details if any.
    """
    start_time = time.time()
    correlation_id = generate_correlation_id()
    
    logger.info(
        "Finish trip initiated: driver_id=%s trip_id=%s",
        driver_id, trip_id,
        extra={'correlationId': correlation_id}
    )
    
    try:
        url = f"{DRIVER_SERVICE_URL}/drivers/{driver_id}/trips/{trip_id}/complete"
        logger.info(
            "Sending POST %s",
            url,
            extra={'correlationId': correlation_id}
        )
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(url)
        
        latency = int((time.time() - start_time) * 1000)
        
        if resp.status_code in (200, 201, 204):
            logger.info(
                "Finish trip SUCCESS: driver_id=%s trip_id=%s latency=%dms",
                driver_id, trip_id, latency,
                extra={'correlationId': correlation_id}
            )
            return {'success': True}
        else:
            try:
                error_data = resp.json()
            except Exception:
                error_data = {'message': resp.text or 'Unknown error'}
            
            logger.error(
                "Finish trip FAILED: driver_id=%s trip_id=%s status=%d latency=%dms error=%s",
                driver_id, trip_id, resp.status_code, latency, error_data,
                extra={'correlationId': correlation_id}
            )
            
            return {
                'success': False,
                'error': {
                    'status_code': resp.status_code,
                    'message': error_data.get('message') or error_data.get('error') or f"HTTP {resp.status_code}",
                },
            }
    
    except httpx.TimeoutException:
        latency = int((time.time() - start_time) * 1000)
        logger.error(
            "Finish trip TIMEOUT: driver_id=%s trip_id=%s latency=%dms",
            driver_id, trip_id, latency,
            extra={'correlationId': correlation_id}
        )
        return {
            'success': False,
            'error': {
                'status_code': 504,
                'message': 'Час очікування вичерпано. Спробуйте ще раз.',
            },
        }
    
    except httpx.ConnectError as e:
        latency = int((time.time() - start_time) * 1000)
        logger.error(
            "Finish trip CONNECTION_ERROR: driver_id=%s trip_id=%s latency=%dms error=%s",
            driver_id, trip_id, latency, str(e),
            extra={'correlationId': correlation_id}
        )
        return {
            'success': False,
            'error': {
                'status_code': 503,
                'message': 'Не вдалося підключитися до сервісу. Перевірте підключення.',
            },
        }
    
    except Exception as e:
        latency = int((time.time() - start_time) * 1000)
        logger.error(
            "Finish trip EXCEPTION: driver_id=%s trip_id=%s latency=%dms error=%s",
            driver_id, trip_id, latency, str(e),
            extra={'correlationId': correlation_id}
        )
        return {
            'success': False,
            'error': {
                'status_code': 500,
                'message': str(e),
            },
        }


async def send_trip_response(driver_id, trip_id, action):
    """
    Send driver's accept/reject response for a trip to the Driver Service.
    
    Args:
        driver_id: The driver's ID
        trip_id: The trip's ID
        action: 'accept' or 'reject'
    
    Returns:
        Dictionary with success status and error details if any.
    """
    start_time = time.time()
    correlation_id = generate_correlation_id()
    
    # Validate action input
    allowed_actions = ('accept', 'reject')
    if action not in allowed_actions:
        logger.error(
            "Trip response INVALID_ACTION: driver_id=%s trip_id=%s action=%s",
            driver_id, trip_id, action,
            extra={'correlationId': correlation_id}
        )
        return {
            'success': False,
            'error': {
                'status_code': 400,
                'message': f"Invalid action '{action}'. Allowed: {allowed_actions}",
            },
        }
    
    logger.info(
        "Trip response initiated: driver_id=%s trip_id=%s action=%s",
        driver_id, trip_id, action,
        extra={'correlationId': correlation_id}
    )
    
    try:
        url = f"{DRIVER_SERVICE_URL}/drivers/{driver_id}/trips/{trip_id}/{action}"
        logger.info(
            "Sending POST %s",
            url,
            extra={'correlationId': correlation_id}
        )
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(url)
        
        latency = int((time.time() - start_time) * 1000)
        
        if resp.status_code in (200, 201, 204):
            logger.info(
                "Trip response SUCCESS: driver_id=%s trip_id=%s action=%s latency=%dms",
                driver_id, trip_id, action, latency,
                extra={'correlationId': correlation_id}
            )

            # Parse response data (includes pickup_address, dropoff_address for accept)
            try:
                data = resp.json()
            except Exception:
                data = {}

            return {
                'success': True,
                'error': None,
                'pickup_address': data.get('pickup_address'),
                'dropoff_address': data.get('dropoff_address'),
            }
        elif resp.status_code == 410:
            # Trip request expired
            logger.warning(
                "Trip response EXPIRED: driver_id=%s trip_id=%s latency=%dms",
                driver_id, trip_id, latency,
                extra={'correlationId': correlation_id}
            )
            return {
                'success': False,
                'error': {
                    'status_code': 410,
                    'message': 'Замовлення вже недоступне або прийняте іншим водієм.',
                },
            }
        elif resp.status_code == 404:
            logger.warning(
                "Trip response NOT_FOUND: driver_id=%s trip_id=%s latency=%dms",
                driver_id, trip_id, latency,
                extra={'correlationId': correlation_id}
            )
            return {
                'success': False,
                'error': {
                    'status_code': 404,
                    'message': 'Замовлення не знайдено.',
                },
            }
        else:
            response_preview = resp.text.encode('utf-8')[:200].decode('utf-8', errors='ignore')
            logger.error(
                "Trip response FAILED: status_code=%s latency=%dms response=%s",
                resp.status_code, latency, response_preview,
                extra={'correlationId': correlation_id}
            )
            
            if DEBUGGING:
                logger.info(
                    "[DEBUG] Mocking trip response success: driver_id=%s trip_id=%s action=%s",
                    driver_id, trip_id, action,
                    extra={'correlationId': correlation_id}
                )
                return {
                    'success': True,
                    'error': None,
                }
            
            return {
                'success': False,
                'error': {
                    'status_code': resp.status_code,
                    'message': resp.text or 'Помилка при обробці відповіді',
                },
            }
    except httpx.TimeoutException:
        latency = int((time.time() - start_time) * 1000)
        logger.error(
            "Trip response TIMEOUT: driver_id=%s trip_id=%s latency=%dms",
            driver_id, trip_id, latency,
            extra={'correlationId': correlation_id}
        )
        
        if DEBUGGING:
            logger.info(
                "[DEBUG] Mocking trip response success after timeout: driver_id=%s trip_id=%s action=%s",
                driver_id, trip_id, action,
                extra={'correlationId': correlation_id}
            )
            return {
                'success': True,
                'error': None,
            }
        
        return {
            'success': False,
            'error': {
                'status_code': 504,
                'message': 'Сервіс не відповідає. Спробуйте пізніше.',
            },
        }
    except httpx.ConnectError:
        latency = int((time.time() - start_time) * 1000)
        logger.error(
            "Trip response CONNECTION_ERROR: driver_id=%s trip_id=%s latency=%dms",
            driver_id, trip_id, latency,
            extra={'correlationId': correlation_id}
        )
        
        if DEBUGGING:
            logger.info(
                "[DEBUG] Mocking trip response success after connection error: driver_id=%s trip_id=%s action=%s",
                driver_id, trip_id, action,
                extra={'correlationId': correlation_id}
            )
            return {
                'success': True,
                'error': None,
            }
        
        return {
            'success': False,
            'error': {
                'status_code': 503,
                'message': 'Сервіс недоступний. Спробуйте пізніше.',
            },
        }
    except Exception as e:
        latency = int((time.time() - start_time) * 1000)
        logger.exception(
            "Trip response UNEXPECTED_ERROR: driver_id=%s trip_id=%s latency=%dms error=%s",
            driver_id, trip_id, latency, str(e),
            extra={'correlationId': correlation_id}
        )
        
        if DEBUGGING:
            logger.info(
                "[DEBUG] Mocking trip response success after unexpected error: driver_id=%s trip_id=%s action=%s",
                driver_id, trip_id, action,
                extra={'correlationId': correlation_id}
            )
            return {
                'success': True,
                'error': None,
            }
        
        return {
            'success': False,
            'error': {
                'status_code': 500,
                'message': str(e),
            },
        }


HELPERS = {
    'safe_send': safe_send,
    'safe_edit_message_text': safe_edit_message_text,
    'submit_trip_request': submit_trip_request,
    'register_driver_in_service': register_driver_in_service,
    'update_driver_status': update_driver_status,
    'fetch_driver_trips': fetch_driver_trips,
    'send_trip_response': send_trip_response,
    'finish_trip': finish_trip,
    'is_valid_address': is_valid_address,
    'fetch_trip_status': fetch_trip_status,
}

async def start_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    # Clear temporary orders
    user_orders.pop(chat_id, None)

    # Create or get user from database
    try:
        await APIClient.get_or_create_bot_user(chat_id, current_role='passenger')
    except Exception as e:
        # Log the error but continue - we don't want failures in driver-service to prevent the welcome message
        logger.error("Failed to create/get bot user on start: chat_id=%s error=%s", chat_id, str(e))

    await update.message.reply_text(
        "\U0001F696 Вітаємо у службі таксі!\n\nОберіть вашу роль:",
        reply_markup=role_selection_menu()
    )

async def change_role(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    # Clear temporary orders
    user_orders.pop(chat_id, None)

    # Note: We don't delete user data from DB, just show role selection
    await update.message.reply_text(
        "\U0001F504 Оберіть нову роль:",
        reply_markup=role_selection_menu()
    )

# Create FastAPI app for health endpoint
app = FastAPI(title="Client Gateway Health API", version="1.0.0")

@app.get("/health")
async def health_check():
    """
    Health check endpoint for container orchestration and monitoring.
    Returns 200 OK if the service is running.
    """
    return {
        "status": "ok",
        "service": "client-gateway",
        "version": "1.0.0"
    }

# Global reference to uvicorn.Server for shutdown handling
# Initialized to None to prevent race conditions during initialization
uvicorn_server: "uvicorn.Server | None" = None

async def run_fastapi():
    """Run FastAPI server for health checks."""
    global uvicorn_server
    config = uvicorn.Config(
        app,
        host="0.0.0.0",
        port=HEALTH_CHECK_PORT,
        log_level="info",
        access_log=False  # Disable access logs to reduce noise
    )
    uvicorn_server = uvicorn.Server(config)
    logger.info("Starting FastAPI health server on port %d", HEALTH_CHECK_PORT, extra={'correlationId': 'STARTUP'})
    try:
        await uvicorn_server.serve()
    except asyncio.CancelledError:
        logger.info("FastAPI server received cancellation signal", extra={'correlationId': 'SHUTDOWN'})
        # Ensure graceful shutdown is signaled to uvicorn
        if uvicorn_server:
            uvicorn_server.should_exit = True
        raise

async def run_telegram_bot(shutdown_event: asyncio.Event):
    """
    Run Telegram bot with polling and graceful shutdown handling.
    
    Args:
        shutdown_event: Asyncio event signaled by main_async() on shutdown signal
    """
    ensure_bot_token()
    # Suppress PTBUserWarning about mixing CallbackQueryHandler entry points
    warnings.filterwarnings(
        "ignore",
        message="If 'per_message=False', 'CallbackQueryHandler' will not be tracked for every message.*",
    )
    
    application = Application.builder().token(BOT_TOKEN).build()
    
    application.add_handler(CommandHandler("start", start_message))
    application.add_handler(MessageHandler(filters.Regex(f"^{re.escape(BTN_CHANGE_ROLE)}$"), change_role))
    
    passenger.register_handlers(application, user_orders, user_roles, BUTTONS, KEYBOARDS, HELPERS)
    driver.register_handlers(application, user_orders, user_roles, BUTTONS, KEYBOARDS, HELPERS, DEBUGGING=DEBUGGING)
    
    logger.info("Telegram bot starting...", extra={'correlationId': 'STARTUP'})
    logger.info("Modules loaded: passenger, driver", extra={'correlationId': 'STARTUP'})
    
    # Initialize the application with proper error handling and cleanup
    try:
        logger.info("Initializing Telegram bot application...", extra={'correlationId': 'STARTUP'})
        await application.initialize()
        await application.start()
        await application.updater.start_polling(allowed_updates=Update.ALL_TYPES)
        
        logger.info("Bot is running and listening for messages", extra={'correlationId': 'STARTUP'})
        
        # Wait for shutdown signal
        await shutdown_event.wait()
    except Exception as e:
        logger.error("Error during bot startup or execution: %s", str(e), extra={'correlationId': 'SHUTDOWN'})
    finally:
        # Perform graceful shutdown - always cleanup even on errors
        logger.info("Stopping bot updater...", extra={'correlationId': 'SHUTDOWN'})
        try:
            await application.updater.stop_polling()
        except Exception as e:
            logger.warning("Error stopping polling: %s", str(e), extra={'correlationId': 'SHUTDOWN'})
        
        try:
            await application.updater.stop()
        except Exception as e:
            logger.warning("Error stopping updater: %s", str(e), extra={'correlationId': 'SHUTDOWN'})
        
        # Allow any in-flight tasks to complete
        logger.info("Waiting for in-flight tasks to complete...", extra={'correlationId': 'SHUTDOWN'})
        await asyncio.sleep(0.1)  # Brief delay for task completion
        
        logger.info("Stopping application...", extra={'correlationId': 'SHUTDOWN'})
        try:
            await application.stop()
        except Exception as e:
            logger.warning("Error stopping application: %s", str(e), extra={'correlationId': 'SHUTDOWN'})
        
        logger.info("Shutting down application...", extra={'correlationId': 'SHUTDOWN'})
        try:
            await application.shutdown()
        except Exception as e:
            logger.warning("Error during shutdown: %s", str(e), extra={'correlationId': 'SHUTDOWN'})
        
        logger.info("Bot shutdown complete", extra={'correlationId': 'SHUTDOWN'})

async def main_async():
    """
    Async main that runs both FastAPI health server and Telegram bot concurrently.
    Registers signal handlers to ensure both services shut down gracefully.
    Coordinates shutdown to signal uvicorn before task cancellation.
    """
    # Create shutdown event for signal handling
    shutdown_event = asyncio.Event()
    
    # Signal handler - synchronous function
    def signal_handler(sig):
        """Handle SIGINT/SIGTERM signals for graceful shutdown."""
        signal_name = signal.Signals(sig).name
        logger.info("Received %s, initiating graceful shutdown...", signal_name, extra={'correlationId': 'SHUTDOWN'})
        shutdown_event.set()
        # Signal uvicorn server to exit gracefully (handles race condition)
        if uvicorn_server is not None:
            uvicorn_server.should_exit = True
    
    # Register signal handlers with platform compatibility
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, signal_handler, sig)
        except NotImplementedError:
            # Windows doesn't support signal.signal for SIGTERM in asyncio
            logger.warning("Signal %s not supported on this platform", signal.Signals(sig).name, extra={'correlationId': 'STARTUP'})
    
    # Create tasks for both services
    fastapi_task = asyncio.create_task(run_fastapi())
    telegram_task = asyncio.create_task(run_telegram_bot(shutdown_event))
    
    # Wait for either task to complete (bot shutdown or FastAPI crash)
    done, pending = await asyncio.wait(
        [fastapi_task, telegram_task],
        return_when=asyncio.FIRST_COMPLETED
    )
    
    # Before canceling, allow graceful shutdown to complete
    logger.info("First service completed, initiating graceful shutdown...", extra={'correlationId': 'SHUTDOWN'})
    
    # Signal graceful shutdown to both services
    shutdown_event.set()
    
    # Set uvicorn shutdown flag to ensure graceful HTTP server shutdown
    if uvicorn_server is not None:
        uvicorn_server.should_exit = True
    
    # Cancel the remaining task(s) with graceful handling
    for task in pending:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            logger.info("Task cancelled during shutdown", extra={'correlationId': 'SHUTDOWN'})
        except Exception as e:
            logger.warning("Exception during task cancellation: %s", str(e), extra={'correlationId': 'SHUTDOWN'})
    
    logger.info("All services have shut down", extra={'correlationId': 'SHUTDOWN'})

def main():
    """
    Main entry point that runs both FastAPI health server and Telegram bot concurrently.
    """
    print("Starting client-gateway service...")
    print(f"- FastAPI health endpoint on port {HEALTH_CHECK_PORT}")
    print("- Telegram bot with polling")
    
    # Run both services concurrently
    asyncio.run(main_async())

if __name__ == "__main__":
    main()
