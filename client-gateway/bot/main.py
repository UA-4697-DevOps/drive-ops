import os
import sys
import time
import re
import uuid
import httpx
import hashlib
import asyncio
import uvicorn
import warnings
from fastapi import FastAPI, Request
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters
from dotenv import load_dotenv

# Імпорт твоїх модулів логіки
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
        logger.error("BOT_TOKEN is not set.")
        sys.exit("ERROR: BOT_TOKEN is missing.")

# --- Глобальні стани (краще потім винести в Redis) ---
user_orders = {}
user_roles = {}
tg_application = None 

# --- Кнопки та Меню (Твоя логіка) ---
BTN_PASSENGER = "\U0001F64B Я замовник таксі"
BTN_DRIVER = "\U0001F697 Я таксист"
BTN_CHANGE_ROLE = "\U0001F504 Змінити роль"

BUTTONS = {
    'BTN_PASSENGER': BTN_PASSENGER,
    'BTN_DRIVER': BTN_DRIVER,
    'BTN_MY_ORDERS': "\U0001F4CB Мої замовлення",
    'BTN_ORDER_TAXI': "\U0001F695 Замовити таксі",
    'BTN_RATES': "\U0001F4B0 Тарифи",
    'BTN_SKIP': "\u23E9 Пропустити",
    'BTN_CHANGE_ROLE': BTN_CHANGE_ROLE,
    'BTN_REGISTER_DRIVER': "\U0001F4DD Зареєструватися як водій",
    'BTN_GO_ONLINE': "\U0001F7E2 Приймати замовлення",
    'BTN_GO_OFFLINE': "\U0001F534 Не приймати замовлення",
    'BTN_DRIVER_STATUS': "\U0001F4CA Мій статус",
    'BTN_FINISH_TRIP': "\U0001F3C1 Завершити поїздку",
    'BTN_CHECK_STATUS': "\U0001F50D Перевірити статус",
}

def role_selection_menu():
    keyboard = [[KeyboardButton(BTN_PASSENGER), KeyboardButton(BTN_DRIVER)]]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)

KEYBOARDS = {
    'role_selection_menu': role_selection_menu,
    'passenger_menu': passenger.passenger_menu if hasattr(passenger, 'passenger_menu') else None,
    'driver_menu_unregistered': driver.driver_menu_unregistered if hasattr(driver, 'driver_menu_unregistered') else None,
    'driver_menu_registered': driver.driver_menu_registered if hasattr(driver, 'driver_menu_registered') else None,
    'get_user_menu': lambda chat_id: driver.driver_menu_registered() if chat_id in user_roles and user_roles[chat_id].get('role') == 'driver' else passenger.passenger_menu()
}

# --- Уніфікований API Helper (Твої 500 рядків коду в одному методі) ---
async def call_backend(method, url, payload=None, params=None):
    cid = generate_correlation_id()
    start = time.time()
    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            resp = await client.request(method, url, json=payload, params=params)
            latency = int((time.time() - start) * 1000)
            logger.info(f"{method} {url} | Status: {resp.status_code} | {latency}ms", extra={'correlationId': cid})
            if resp.status_code in (200, 201, 204):
                return {'success': True, 'data': resp.json() if resp.text else {}}
            return {'success': False, 'error': {'status_code': resp.status_code, 'message': resp.text}}
        except Exception as e:
            logger.error(f"Backend unreachable: {e}", extra={'correlationId': cid})
            return {'success': False, 'error': {'status_code': 500, 'message': "Сервіс недоступний"}}

# Словник хелперів для модулів passenger та driver
HELPERS = {
    'submit_trip_request': lambda chat_id, order: call_backend("POST", f"{TRIP_SERVICE_URL}/trips", payload={**order, 'passenger_id': str(uuid.uuid5(uuid.NAMESPACE_DNS, f"tg-{chat_id}"))}),
    'fetch_trip_status': lambda trip_id, user_id: call_backend("GET", f"{TRIP_SERVICE_URL}/trips/{trip_id}"),
    'register_driver_in_service': lambda chat_id, name, car: call_backend("POST", f"{DRIVER_SERVICE_URL}/drivers", payload={'name': name, 'car_description': car, 'telegram_id': str(chat_id)}),
    'update_driver_status': lambda driver_id, status: call_backend("POST", f"{DRIVER_SERVICE_URL}/drivers/{driver_id}/status", params={'status': status.upper()}),
    'fetch_driver_trips': lambda driver_id: call_backend("GET", f"{DRIVER_SERVICE_URL}/drivers/{driver_id}/trips"),
    'send_trip_response': lambda driver_id, trip_id, action: call_backend("POST", f"{DRIVER_SERVICE_URL}/drivers/{driver_id}/trips/{trip_id}/{action}"),
    'finish_trip': lambda driver_id, trip_id: call_backend("POST", f"{DRIVER_SERVICE_URL}/drivers/{driver_id}/trips/{trip_id}/complete"),
    'safe_send': lambda chat_id, text, context, **kwargs: context.bot.send_message(chat_id, text, **kwargs),
    'is_valid_address': lambda addr: addr and len(addr) > 5
}

# --- Notification Server (FastAPI) ---
# Це серце Phase 2 та 3 архітектури
notification_app = FastAPI()

@notification_app.post("/notifications/driver/{chat_id}")
async def notify_driver_endpoint(chat_id: int, request: Request):
    data = await request.json()
    # Виклик функції сповіщення водія з модуля driver.py
    await driver.notify_new_order(tg_application.bot, chat_id, data)
    return {"status": "ok"}

@notification_app.post("/notifications/passenger/{chat_id}")
async def notify_passenger_endpoint(chat_id: int, request: Request):
    data = await request.json()
    await tg_application.bot.send_message(chat_id, f"🔔 *Оновлення:* {data.get('message', 'Ваш статус змінився')}", parse_mode='Markdown')
    return {"status": "ok"}

# --- Основні хендлери бота ---
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_roles.pop(chat_id, None)
    await update.message.reply_text("👋 Вітаємо у Drive-Ops! Оберіть роль:", reply_markup=role_selection_menu())

async def run_bot_polling():
    global tg_application
    ensure_bot_token()
    warnings.filterwarnings("ignore", message="If 'per_message=False'...")
    
    tg_application = Application.builder().token(BOT_TOKEN).build()
    tg_application.add_handler(CommandHandler("start", start_command))
    tg_application.add_handler(MessageHandler(filters.Regex(f"^{re.escape(BTN_CHANGE_ROLE)}$"), start_command))
    
    # Підключення хендлерів з інших файлів
    passenger.register_handlers(tg_application, user_orders, user_roles, BUTTONS, KEYBOARDS, HELPERS)
    driver.register_handlers(tg_application, user_orders, user_roles, BUTTONS, KEYBOARDS, HELPERS, DEBUGGING=DEBUGGING)
    
    async with tg_application:
        await tg_application.initialize()
        await tg_application.start()
        await tg_application.updater.start_polling()
        logger.info("Telegram Bot Polling started...")
        while True: await asyncio.sleep(1)

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.create_task(run_bot_polling())
    
    logger.info("Starting Notification Server on port 8080...")
    uvicorn.run(notification_app, host="0.0.0.0", port=8080)
