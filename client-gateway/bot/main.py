import os
import sys
import time
import re
import uuid
import httpx
import hashlib
import warnings
import asyncio
import uvicorn
from fastapi import FastAPI, Request
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters
from dotenv import load_dotenv

# Імпорт модулів логіки
from . import passenger
from . import driver
from .logger_utils import create_trip_request_logger, generate_correlation_id

# --- Конфігурація ---
logger = create_trip_request_logger()
load_dotenv()

BOT_TOKEN = os.getenv('BOT_TOKEN')
TRIP_SERVICE_URL = os.getenv('TRIP_SERVICE_URL', 'http://trip-service:8081')
DRIVER_SERVICE_URL = os.getenv('DRIVER_SERVICE_URL', 'http://driver-service:8082')
DEBUGGING = os.getenv('DEBUG', 'False').lower() in ('true', '1', 't')

def ensure_bot_token():
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN is not set in environment.")
        sys.exit("ERROR: BOT_TOKEN is missing.")

# --- Глобальні стани ---
user_orders = {}
user_roles = {}
tg_application = None  # Глобальний об'єкт для FastAPI

# --- UI Дефініції ---
BUTTONS = {
    'BTN_PASSENGER': "\U0001F64B Я замовник таксі",
    'BTN_DRIVER': "\U0001F697 Я таксист",
    'BTN_MY_ORDERS': "\U0001F4CB Мої замовлення",
    'BTN_ORDER_TAXI': "\U0001F695 Замовити таксі",
    'BTN_RATES': "\U0001F4B0 Тарифи",
    'BTN_SKIP': "\u23E9 Пропустити",
    'BTN_CHANGE_ROLE': "\U0001F504 Змінити роль",
    'BTN_REGISTER_DRIVER': "\U0001F4DD Зареєструватися як водій",
    'BTN_GO_ONLINE': "\U0001F7E2 Приймати замовлення",
    'BTN_GO_OFFLINE': "\U0001F534 Не приймати замовлення",
    'BTN_DRIVER_STATUS': "\U0001F4CA Мій статус",
    'BTN_FINISH_TRIP': "\U0001F3C1 Завершити поїздку",
    'BTN_CHECK_STATUS': "\U0001F50D Перевірити статус",
}

# --- Клієнтська логіка (Повертаємо твої 1100 рядків логіки) ---

async def submit_trip_request(chat_id, order):
    correlation_id = generate_correlation_id()
    passenger_uuid = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"tg-{chat_id}"))
    payload = {
        'pickup': order.get('pickup'),
        'dropoff': order.get('dropoff'),
        'passenger_id': passenger_uuid,
    }
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(f"{TRIP_SERVICE_URL}/trips", json=payload)
            if resp.status_code in (200, 201):
                return {'success': True, 'trip_id': resp.json().get('id'), 'status': 'pending'}
    except Exception as e:
        logger.error(f"Trip request failed: {e}")
    return {'success': False, 'error': 'Сервіс недоступний'}

async def register_driver_in_service(chat_id, name, car_description):
    payload = {'name': name, 'car_description': car_description, 'telegram_id': str(chat_id)}
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(f"{DRIVER_SERVICE_URL}/drivers", json=payload)
            return {'success': resp.status_code in (200, 201), 'driver_id': resp.json().get('id')}
    except Exception as e:
        logger.error(f"Driver reg failed: {e}")
    return {'success': False}

async def update_driver_status(driver_id, status_val):
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(f"{DRIVER_SERVICE_URL}/drivers/{driver_id}/status", params={'status': status_val.upper()})
            return {'success': resp.status_code == 200}
    except Exception as e:
        logger.error(f"Status update failed: {e}")
    return {'success': False}

HELPERS = {
    'submit_trip_request': submit_trip_request,
    'register_driver_in_service': register_driver_in_service,
    'update_driver_status': update_driver_status,
    'safe_send': lambda chat_id, text, context, **kwargs: context.bot.send_message(chat_id, text, **kwargs),
    'is_valid_address': lambda addr: addr is not None and len(addr) > 5,
    'fetch_trip_status': lambda trip_id: httpx.get(f"{TRIP_SERVICE_URL}/trips/{trip_id}").json()
}

KEYBOARDS = {
    'role_selection_menu': lambda: ReplyKeyboardMarkup([[KeyboardButton(BUTTONS['BTN_PASSENGER']), KeyboardButton(BUTTONS['BTN_DRIVER'])]], resize_keyboard=True),
    'passenger_menu': passenger.passenger_menu,
    'driver_menu_unregistered': driver.driver_menu_unregistered,
    'driver_menu_registered': driver.driver_menu_registered,
}

# --- Notification Server (FastAPI) ---
notification_app = FastAPI()

@notification_app.get("/health")
async def health_check():
    return {"status": "ok", "bot_running": tg_application is not None}

@notification_app.post("/notifications/driver/{chat_id}")
async def api_notify_driver(chat_id: int, request: Request):
    data = await request.json()
    # Викликаємо логіку з модуля driver
    await driver.notify_new_order(tg_application.bot, chat_id, data)
    return {"success": True}

# --- Основні хендлери бота ---
async def start_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 Вітаємо! Оберіть роль:", reply_markup=KEYBOARDS['role_selection_menu']())

# --- Запуск обох систем паралельно ---
async def run_bot_polling():
    global tg_application
    ensure_bot_token()
    
    tg_application = Application.builder().token(BOT_TOKEN).build()
    tg_application.add_handler(CommandHandler("start", start_message))
    
    # Реєструємо твої розширені хендлери з модулів
    passenger.register_handlers(tg_application, user_orders, user_roles, BUTTONS, KEYBOARDS, HELPERS)
    driver.register_handlers(tg_application, user_orders, user_roles, BUTTONS, KEYBOARDS, HELPERS, DEBUGGING=DEBUGGING)
    
    await tg_application.initialize()
    await tg_application.start()
    await tg_application.updater.start_polling()
    logger.info("✅ Бот успішно запущений та слухає Telegram")

if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    # Запускаємо бота в бекграунді
    loop.create_task(run_bot_polling())
    
    # Запускаємо FastAPI (цей виклик блокуючий, тому він останній)
    logger.info("📡 Запуск сервера сповіщень на порту 8080...")
    config = uvicorn.Config(notification_app, host="0.0.0.0", port=8080, loop=loop)
    server = uvicorn.Server(config)
    loop.run_until_complete(server.serve())
