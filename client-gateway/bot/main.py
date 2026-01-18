import os
import sys
import time
import re
import uuid
import asyncio
import uvicorn
import warnings
from fastapi import FastAPI, Request
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters
from dotenv import load_dotenv

# Імпорт твоїх модулів
from . import passenger
from . import driver
from .api_client import APIClient  # Використовуємо твій окремий файл для запитів
from .logger_utils import create_trip_request_logger, generate_correlation_id

# --- Конфігурація ---
logger = create_trip_request_logger()
load_dotenv()

BOT_TOKEN = os.getenv('BOT_TOKEN')
DEBUGGING = os.getenv('DEBUG', 'False').lower() in ('true', '1', 't')

def ensure_bot_token():
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN is not set in environment.")
        sys.exit("ERROR: BOT_TOKEN is missing.")

# --- Глобальні стани ---
user_orders = {}
user_roles = {}
tg_application = None  # Посилання на бот-додаток для використання у FastAPI

# --- Кнопки (Твоя логіка) ---
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

# --- Клавіатури (Важливо: додаємо посилання на функції з твоїх файлів) ---
KEYBOARDS = {
    'role_selection_menu': lambda: ReplyKeyboardMarkup([[KeyboardButton(BTN_PASSENGER), KeyboardButton(BTN_DRIVER)]], resize_keyboard=True, one_time_keyboard=True),
    'passenger_menu': passenger.passenger_menu if hasattr(passenger, 'passenger_menu') else None,
    'driver_menu_unregistered': driver.driver_menu_unregistered if hasattr(driver, 'driver_menu_unregistered') else None,
    'driver_menu_registered': driver.driver_menu_registered if hasattr(driver, 'driver_menu_registered') else None,
    'skip_menu': lambda: ReplyKeyboardMarkup([[KeyboardButton(BUTTONS['BTN_SKIP'])]], resize_keyboard=True, one_time_keyboard=True),
    'get_user_menu': lambda chat_id: driver.driver_menu_registered() if (chat_id in user_roles and isinstance(user_roles[chat_id], dict) and user_roles[chat_id].get('role') == 'driver') else passenger.passenger_menu()
}

# --- HELPERS (Стандартизована взаємодія за Таском 1) ---
# Тут ми підв'язуємо функції з passenger.py та driver.py до APIClient
HELPERS = {
    'submit_trip_request': lambda chat_id, order: APIClient.create_trip({**order, 'passenger_id': str(uuid.uuid5(uuid.NAMESPACE_DNS, f"tg-{chat_id}"))}),
    'fetch_trip_status': lambda trip_id, user_id=None: APIClient.get_trip_status(trip_id),
    'register_driver_in_service': lambda chat_id, name, car: APIClient.register_driver({'name': name, 'car_description': car, 'telegram_id': str(chat_id)}),
    'update_driver_status': lambda driver_id, status: APIClient.update_driver_status(driver_id, status),
    'fetch_driver_trips': lambda driver_id: APIClient.fetch_driver_trips(driver_id),
    'send_trip_response': lambda driver_id, trip_id, action: APIClient.respond_to_trip(driver_id, trip_id, action),
    'finish_trip': lambda driver_id, trip_id: APIClient.finish_trip(driver_id, trip_id),
    'safe_send': lambda chat_id, text, context, **kwargs: context.bot.send_message(chat_id, text, **kwargs),
    'is_valid_address': lambda addr: addr is not None and len(addr) > 5
}

# --- Notification Server (FastAPI для Phase 2/4) ---
notification_app = FastAPI()

@notification_app.post("/notifications/driver/{chat_id}")
async def api_notify_driver(chat_id: int, request: Request):
    """Викликається Driver Service, коли знайдено замовлення (Phase 2)"""
    data = await request.json()
    success = await driver.notify_new_order(tg_application.bot, chat_id, data)
    return {"success": success}

@notification_app.post("/notifications/passenger/{chat_id}")
async def api_notify_passenger(chat_id: int, request: Request):
    """Викликається Trip Service при зміні статусу поїздки (Phase 4)"""
    data = await request.json()
    msg = f"🔔 *Оновлення поїздки!*\n\n{data.get('message', 'Статус змінився')}"
    await tg_application.bot.send_message(chat_id, msg, parse_mode='Markdown')
    return {"success": True}

# --- Основні хендлери ---
async def start_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_roles.pop(chat_id, None)
    user_orders.pop(chat_id, None)
    await update.message.reply_text(
        "👋 Вітаємо у Drive-Ops!\nОберіть вашу роль:", 
        reply_markup=KEYBOARDS['role_selection_menu']()
    )

# --- Запуск ---
async def run_bot_polling():
    global tg_application
    ensure_bot_token()
    
    # Ігноруємо попередження про CallbackHandler
    warnings.filterwarnings("ignore", message="If 'per_message=False'*")
    
    tg_application = Application.builder().token(BOT_TOKEN).build()
    
    # Реєстрація базових команд
    tg_application.add_handler(CommandHandler("start", start_message))
    tg_application.add_handler(MessageHandler(filters.Regex(f"^{re.escape(BTN_CHANGE_ROLE)}$"), start_message))
    
    # Реєстрація логіки з модулів
    passenger.register_handlers(tg_application, user_orders, user_roles, BUTTONS, KEYBOARDS, HELPERS)
    driver.register_handlers(tg_application, user_orders, user_roles, BUTTONS, KEYBOARDS, HELPERS, DEBUGGING=DEBUGGING)
    
    async with tg_application:
        await tg_application.initialize()
        await tg_application.start()
        await tg_application.updater.start_polling()
        logger.info("Бот запущений у режимі Polling...")
        while True:
            await asyncio.sleep(1)

if __name__ == "__main__":
    # Створюємо подію для запуску бота у фоні
    loop = asyncio.get_event_loop()
    loop.create_task(run_bot_polling())
    
    # Запускаємо сервер сповіщень (блокуючий виклик)
    logger.info("Запуск сервера сповіщень на порту 8080...")
    uvicorn.run(notification_app, host="0.0.0.0", port=8080)
