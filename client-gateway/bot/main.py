import os
import sys
import logging
from logging.handlers import RotatingFileHandler
import time
<<<<<<< HEAD
import re
import httpx
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters
=======
import requests
import telebot
from telebot import types
>>>>>>> main
from dotenv import load_dotenv
import passenger
import driver

LOG_DIR = os.path.join(os.path.dirname(__file__), 'logs')
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, 'bot.log')

logger = logging.getLogger('drive_ops')
logger.setLevel(logging.INFO)

log_format = logging.Formatter("%(asctime)s %(levelname)s %(message)s")

file_handler = RotatingFileHandler(LOG_FILE, maxBytes=5*1024*1024, backupCount=3, encoding='utf-8')
file_handler.setFormatter(log_format)
logger.addHandler(file_handler)

console_handler = logging.StreamHandler()
console_handler.setFormatter(log_format)
logger.addHandler(console_handler)

load_dotenv()
BOT_TOKEN = os.getenv('BOT_TOKEN')
TRIP_SERVICE_URL = os.getenv('TRIP_SERVICE_URL', 'http://localhost:8080')

if not BOT_TOKEN:
    logger.error("BOT_TOKEN is not set in the environment or .env file.")
    sys.exit("ERROR: BOT_TOKEN is not configured.")

<<<<<<< HEAD
=======
bot = telebot.TeleBot(BOT_TOKEN)

>>>>>>> main
user_orders = {}
user_roles = {}

BTN_PASSENGER = "\U0001F64B Я замовник таксі"
BTN_DRIVER = "\U0001F697 Я таксист"
BTN_MY_ORDERS = "\U0001F4CB Мої замовлення"
BTN_ORDER_TAXI = "\U0001F695 Замовити таксі"
BTN_RATES = "\U0001F4B0 Тарифи"
BTN_SKIP = "\u23E9 Пропустити"
BTN_CHANGE_ROLE = "\U0001F504 Змінити роль"

BUTTONS = {
    'BTN_PASSENGER': BTN_PASSENGER,
    'BTN_DRIVER': BTN_DRIVER,
    'BTN_MY_ORDERS': BTN_MY_ORDERS,
    'BTN_ORDER_TAXI': BTN_ORDER_TAXI,
    'BTN_RATES': BTN_RATES,
    'BTN_SKIP': BTN_SKIP,
    'BTN_CHANGE_ROLE': BTN_CHANGE_ROLE,
}

def role_selection_menu():
<<<<<<< HEAD
    keyboard = [[KeyboardButton(BTN_PASSENGER), KeyboardButton(BTN_DRIVER)]]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)

def passenger_menu():
    keyboard = [
        [KeyboardButton(BTN_ORDER_TAXI), KeyboardButton(BTN_RATES)],
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
=======
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    markup.add(types.KeyboardButton(BTN_PASSENGER), types.KeyboardButton(BTN_DRIVER))
    return markup

def passenger_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(types.KeyboardButton(BTN_ORDER_TAXI), types.KeyboardButton(BTN_RATES))
    markup.add(types.KeyboardButton(BTN_CHANGE_ROLE))
    return markup

def driver_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(types.KeyboardButton(BTN_MY_ORDERS))
    markup.add(types.KeyboardButton(BTN_CHANGE_ROLE))
    return markup

def skip_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    markup.add(types.KeyboardButton(BTN_SKIP))
    return markup
>>>>>>> main

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

<<<<<<< HEAD
async def safe_send(chat_id, text, context, **kwargs):
    try:
        return await context.bot.send_message(chat_id, text, **kwargs)
=======
def safe_send(chat_id, text, **kwargs):
    try:
        return bot.send_message(chat_id, text, **kwargs)
>>>>>>> main
    except Exception as e:
        logger.exception("Failed to send message to %s: %s", chat_id, e)
        return None

<<<<<<< HEAD
async def safe_edit_message_text(chat_id, message_id, text, context, **kwargs):
    try:
        return await context.bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=text, **kwargs)
=======
def safe_edit_message_text(chat_id, message_id, text, **kwargs):
    try:
        return bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=text, **kwargs)
>>>>>>> main
    except Exception as e:
        logger.exception("Failed to edit message %s/%s: %s", chat_id, message_id, e)
        return None

<<<<<<< HEAD
async def submit_trip_request(chat_id, order):
=======
def validate_address_and_retry(chat_id, address, error_message, retry_handler):
    if is_valid_address(address):
        return True
    msg = safe_send(chat_id, error_message)
    if msg is not None:
        try:
            bot.register_next_step_handler(msg, retry_handler)
        except Exception:
            logger.exception("Failed to register next step handler for %s", chat_id)
            safe_send(chat_id, "Виникла внутрішня помилка. Спробуйте ще раз.")
    return False

def submit_trip_request(chat_id, order):
>>>>>>> main
    payload = {
        'pickup': order.get('pickup'),
        'dropoff': order.get('dropoff'),
        'comment': order.get('comment'),
        'source': 'telegram_bot',
        'user_chat_id': chat_id,
<<<<<<< HEAD
        'passenger_id': order.get('passenger_id') or str(chat_id),
=======
>>>>>>> main
    }
    logger.info(
        "Trip request payload: chat_id=%s pickup=%s dropoff=%s comment=%s",
        chat_id, payload['pickup'], payload['dropoff'], payload['comment']
    )

    request_id = f"REQ-{chat_id}-{int(time.time())}"
    
    try:
<<<<<<< HEAD
        url = f"{TRIP_SERVICE_URL}/trips"
        logger.info("Sending trip request to %s", url)
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(url, json=payload)
=======
        url = f"{TRIP_SERVICE_URL}/requests"
        logger.info("Sending trip request to %s", url)
        
        resp = requests.post(url, json=payload, timeout=10)
>>>>>>> main
        
        if resp.status_code in (200, 201):
            data = resp.json()
            trip_id = data.get('id') or data.get('trip_id') or request_id
            status = data.get('status', 'pending')
            
            logger.info(
                "Trip request success: trip_id=%s status=%s",
                trip_id, status
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
            logger.error(
                "Trip request failed: status_code=%s response=%s",
                resp.status_code, resp.text
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
<<<<<<< HEAD
    except httpx.TimeoutException:
=======
    except requests.exceptions.Timeout:
>>>>>>> main
        logger.error("Trip request timeout for chat_id=%s", chat_id)
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
<<<<<<< HEAD
    except httpx.ConnectError:
=======
    except requests.exceptions.ConnectionError:
>>>>>>> main
        logger.error("Trip request connection error for chat_id=%s", chat_id)
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
        logger.exception("Trip request unexpected error for chat_id=%s: %s", chat_id, e)
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
<<<<<<< HEAD
    'submit_trip_request': submit_trip_request,
    'is_valid_address': is_valid_address,
}

async def start_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_roles.pop(chat_id, None)
    user_orders.pop(chat_id, None)
    await update.message.reply_text(
=======
    'validate_address_and_retry': validate_address_and_retry,
    'submit_trip_request': submit_trip_request,
}

@bot.message_handler(commands=['start'])
def start_message(message):
    chat_id = message.chat.id
    user_roles.pop(chat_id, None)
    user_orders.pop(chat_id, None)
    bot.send_message(
        chat_id,
>>>>>>> main
        "\U0001F696 Вітаємо у службі таксі!\n\nОберіть вашу роль:",
        reply_markup=role_selection_menu()
    )

<<<<<<< HEAD
async def change_role(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_roles.pop(chat_id, None)
    user_orders.pop(chat_id, None)
    await update.message.reply_text(
=======
@bot.message_handler(func=lambda message: message.text == BTN_CHANGE_ROLE)
def change_role(message):
    chat_id = message.chat.id
    user_roles.pop(chat_id, None)
    user_orders.pop(chat_id, None)
    bot.send_message(
        chat_id,
>>>>>>> main
        "\U0001F504 Оберіть нову роль:",
        reply_markup=role_selection_menu()
    )

<<<<<<< HEAD
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
=======
passenger.register_handlers(bot, user_orders, user_roles, BUTTONS, KEYBOARDS, HELPERS)
driver.register_handlers(bot, user_orders, user_roles, BUTTONS, KEYBOARDS, HELPERS)

if __name__ == "__main__":
    print("Бот запущений...")
    print("Модулі завантажено: passenger, driver")
    bot.infinity_polling()
>>>>>>> main
