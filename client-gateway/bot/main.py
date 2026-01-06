import os
import sys
import time
import re
import httpx
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters
from dotenv import load_dotenv
import passenger
import driver
from logger_utils import create_trip_request_logger, generate_correlation_id

logger = create_trip_request_logger()

load_dotenv()
BOT_TOKEN = os.getenv('BOT_TOKEN')
TRIP_SERVICE_URL = os.getenv('TRIP_SERVICE_URL', 'http://localhost:8080')

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
BTN_CHECK_STATUS = "\U0001F50D Перевірити статус"

BUTTONS = {
    'BTN_PASSENGER': BTN_PASSENGER,
    'BTN_DRIVER': BTN_DRIVER,
    'BTN_MY_ORDERS': BTN_MY_ORDERS,
    'BTN_ORDER_TAXI': BTN_ORDER_TAXI,
    'BTN_RATES': BTN_RATES,
    'BTN_SKIP': BTN_SKIP,
    'BTN_CHANGE_ROLE': BTN_CHANGE_ROLE,
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
    'skip_menu': skip_menu,
    'get_user_menu': get_user_menu,
}

def is_valid_address(address):
    return address is not None and len(address) > 5


async def fetch_trip_status(trip_id):
    """
    Fetch trip status from the trip service.
    
    Args:
        trip_id: The UUID of the trip to check
    
    Returns:
        Dictionary with success status, trip data, error details, etc.
    """
    start_time = time.time()
    correlation_id = generate_correlation_id()
    
    logger.info(
        "Trip status check initiated: trip_id=%s",
        trip_id,
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
                "Trip status check SUCCESS: trip_id=%s status=%s latency=%dms",
                trip_id, data.get('status'), latency,
                extra={'correlationId': correlation_id}
            )
            
            return {
                'success': True,
                'trip': data,
                'error': None,
            }
        elif resp.status_code == 404:
            logger.warning(
                "Trip status check NOT_FOUND: trip_id=%s latency=%dms",
                trip_id, latency,
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
                "Trip status check FAILED: trip_id=%s status_code=%s latency=%dms response=%s",
                trip_id, resp.status_code, latency, response_preview,
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
            "Trip status check TIMEOUT: trip_id=%s latency=%dms",
            trip_id, latency,
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
            "Trip status check CONNECTION_ERROR: trip_id=%s latency=%dms",
            trip_id, latency,
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
            "Trip status check UNEXPECTED_ERROR: trip_id=%s latency=%dms error=%s",
            trip_id, latency, str(e),
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

HELPERS = {
    'safe_send': safe_send,
    'safe_edit_message_text': safe_edit_message_text,
    'submit_trip_request': submit_trip_request,
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

status_mapping = {
    'PENDING': ('⏳ Очікує водія', 'Ваше замовлення в черзі...'),
    'CONFIRMED': ('✅ Підтверджено', 'Водій прийняв замовлення...'),
    'IN_PROGRESS': ('🚗 В дорозі', 'Ви в дорозі...'),
    'COMPLETED': ('🏁 Завершено', 'Поїздка успішно завершена...'),
    'CANCELLED': ('❌ Скасовано', 'Цю поїздку було скасовано.'),
}

def main():
    application = Application.builder().token(BOT_TOKEN).build()
    
    application.add_handler(CommandHandler("start", start_message))
    application.add_handler(MessageHandler(filters.Regex(f"^{re.escape(BTN_CHANGE_ROLE)}$"), change_role))
    
    passenger.register_handlers(application, user_orders, user_roles, BUTTONS, KEYBOARDS, HELPERS)
    driver.register_handlers(application, user_orders, user_roles, BUTTONS, KEYBOARDS, HELPERS)
    
    print("Бот запущений...")
    print("Модулі завантажено: passenger, driver")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
