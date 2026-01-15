import os
import sys
import time
import re
import httpx
import hashlib
import warnings
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters
from dotenv import load_dotenv
from . import passenger
from . import driver
from .logger_utils import create_trip_request_logger, generate_correlation_id

logger = create_trip_request_logger()

load_dotenv()
BOT_TOKEN = os.getenv('BOT_TOKEN')
TRIP_SERVICE_URL = os.getenv('TRIP_SERVICE_URL', 'http://localhost:8080')
DRIVER_SERVICE_URL = os.getenv('DRIVER_SERVICE_URL', 'http://localhost:8081')

DEBUGGING = os.getenv('DEBUG', 'False').lower() in ('true', '1', 't')

logger.info("DEBUG env var: %s", os.getenv('DEBUG'))
logger.info("DEBUGGING mode: %s", DEBUGGING)


def ensure_bot_token():
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN is not set in the environment or .env file.")
        sys.exit("ERROR: BOT_TOKEN is not configured.")

user_orders = {}
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
    role = user_roles.get(chat_id, 'passenger')
    return driver_menu() if role == 'driver' else passenger_menu()

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

async def submit_trip_request(chat_id, order):
    """
    Submit a trip request to the trip service.
    Logs the full lifecycle: request init -> validation -> response.
    
    Args:
        chat_id: Telegram user chat ID
        order: Dictionary with 'pickup', 'dropoff', 'comment' fields
    
    Returns:
        Dictionary with success status, trip_id, error details, etc.
    """
    start_time = time.time()
    correlation_id = generate_correlation_id()
    
    payload = {
        'pickup': order.get('pickup'),
        'dropoff': order.get('dropoff'),
        'passenger_id': order.get('passenger_id') or str(chat_id),
        'comment': order.get('comment'),
    }
    
    request_id = f"REQ-{chat_id}-{int(time.time())}"
    
    logger.info(
        "Trip request initiated: chat_id=%s request_id=%s",
        chat_id, request_id,
        extra={'correlationId': correlation_id}
    )
    
    try:
        url = f"{TRIP_SERVICE_URL}/trips"
        logger.info(
            "Sending POST %s with pickup=%s, dropoff=%s",
            url, payload['pickup'], payload['dropoff'],
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
    
    payload = {
        'name': name,
        'car_description': car_description,
        'telegram_id': str(chat_id),
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
        status: 'online' or 'offline'
    
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

    payload = {'status': status}

    logger.info(
        "Driver status update initiated: driver_id=%s status=%s",
        driver_id, status,
        extra={'correlationId': correlation_id}
    )
    
    try:
        url = f"{DRIVER_SERVICE_URL}/drivers/{driver_id}/status"
        logger.info(
            "Sending POST %s with status=%s",
            url, status,
            extra={'correlationId': correlation_id}
        )
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(url, json=payload)
        
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
            
            return {
                'success': True,
                'error': None,
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
    user_roles.pop(chat_id, None)
    user_orders.pop(chat_id, None)
    await update.message.reply_text(
        "\U0001F696 Вітаємо у службі таксі!\n\nОберіть вашу роль:",
        reply_markup=role_selection_menu()
    )

async def change_role(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_roles.pop(chat_id, None)
    user_orders.pop(chat_id, None)
    await update.message.reply_text(
        "\U0001F504 Оберіть нову роль:",
        reply_markup=role_selection_menu()
    )

def main():
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
    
    print("Бот запущений...")
    print("Модулі завантажено: passenger, driver")
    
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
