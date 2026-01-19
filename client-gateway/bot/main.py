import os, sys, re, uuid, asyncio, warnings, uvicorn, httpx
from fastapi import FastAPI, Request
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters
from dotenv import load_dotenv

from . import passenger, driver
from .api_client import APIClient
from .logger_utils import create_trip_request_logger, generate_correlation_id

logger = create_trip_request_logger()
load_dotenv()

# --- КОНСТАНТИ ---
BOT_TOKEN = os.getenv('BOT_TOKEN')
TRIP_SERVICE_URL = os.getenv('TRIP_SERVICE_URL', 'http://trip-service:8081')
DRIVER_SERVICE_URL = os.getenv('DRIVER_SERVICE_URL', 'http://driver-service:8082')

BTN_PASSENGER = "\U0001F64B Я замовник таксі"
BTN_DRIVER = "\U0001F697 Я таксист"
BTN_CHANGE_ROLE = "\U0001F504 Змінити роль"

# !!! ВАЖЛИВО: Передаємо кнопки безпосередньо в модулі, щоб уникнути NameError
passenger.BTN_PASSENGER = BTN_PASSENGER
driver.BTN_DRIVER = BTN_DRIVER

BUTTONS = {
    'BTN_PASSENGER': BTN_PASSENGER,
    'BTN_DRIVER': BTN_DRIVER,
    'BTN_ORDER_TAXI': "\U0001F695 Замовити таксі",
    'BTN_REGISTER_DRIVER': "\U0001F4DD Зареєструватися як водій",
    'BTN_CHANGE_ROLE': BTN_CHANGE_ROLE,
    'BTN_SKIP': "\u23E9 Пропустити",
}

user_orders, user_roles, tg_application = {}, {}, None

KEYBOARDS = {
    'role_selection_menu': lambda: ReplyKeyboardMarkup([[KeyboardButton(BTN_PASSENGER), KeyboardButton(BTN_DRIVER)]], resize_keyboard=True),
    'passenger_menu': passenger.passenger_menu,
    'driver_menu_unregistered': driver.driver_menu_unregistered,
    'driver_menu_registered': driver.driver_menu_registered,
}

HELPERS = {
    'submit_trip_request': lambda c, o: APIClient.create_trip({**o, 'passenger_id': str(uuid.uuid4())}),
    'register_driver_in_service': lambda c, n, car: APIClient.register_driver({'name': n, 'car_description': car, 'telegram_id': str(c)}),
    'update_driver_status': lambda d, s: APIClient.update_driver_status(d, s),
    'safe_send': lambda c_id, txt, ctx, **kw: ctx.bot.send_message(c_id, txt, **kw),
    'fetch_trip_status': lambda t_id: httpx.get(f"{TRIP_SERVICE_URL}/trips/{t_id}").json()
}

notification_app = FastAPI()

@notification_app.get("/health")
async def health():
    return {"status": "ok", "bot_running": tg_application is not None}

@notification_app.post("/notifications/driver/{chat_id}")
async def api_notify_driver(chat_id: int, request: Request):
    data = await request.json()
    await driver.notify_new_order(tg_application.bot, chat_id, data)
    return {"success": True}

async def start_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 Вітаємо! Оберіть роль:", reply_markup=KEYBOARDS['role_selection_menu']())

async def run_bot_polling():
    global tg_application
    tg_application = Application.builder().token(BOT_TOKEN).build()
    tg_application.add_handler(CommandHandler("start", start_message))
    
    passenger.register_handlers(tg_application, user_orders, user_roles, BUTTONS, KEYBOARDS, HELPERS)
    driver.register_handlers(tg_application, user_orders, user_roles, BUTTONS, KEYBOARDS, HELPERS)
    
    await tg_application.initialize()
    await tg_application.start()
    await tg_application.updater.start_polling()
    logger.info("✅ БОТ ЗАПУЩЕНИЙ І СЛУХАЄ ТЕЛЕГРАМ")

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.create_task(run_bot_polling())
    logger.info("📡 Запуск сервера сповіщень...")
    uvicorn.run(notification_app, host="0.0.0.0", port=8080)

