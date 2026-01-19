import os, sys, re, uuid, asyncio, warnings, uvicorn, httpx
from fastapi import FastAPI, Request
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters
from dotenv import load_dotenv

# Імпортуємо логіку пасажира та водія
from . import passenger, driver
from .api_client import APIClient
from .logger_utils import create_trip_request_logger

logger = create_trip_request_logger()
load_dotenv()

# --- Конфігурація ---
BOT_TOKEN = os.getenv('BOT_TOKEN')
TRIP_SERVICE_URL = os.getenv('TRIP_SERVICE_URL', 'http://trip-service:8081')
DRIVER_SERVICE_URL = os.getenv('DRIVER_SERVICE_URL', 'http://driver-service:8082')

# Кнопки
BTN_PASSENGER = "\U0001F64B Я замовник таксі"
BTN_DRIVER = "\U0001F697 Я таксист"
BTN_CHANGE_ROLE = "\U0001F504 Змінити роль"

# Експортуємо кнопки в модулі, щоб уникнути NameError
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

user_orders, user_roles = {}, {}
tg_application = None

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
    'safe_send': lambda c_id, txt, ctx, **kw: ctx.bot.send_message(c_id, txt, **kw)
}

# --- FastAPI ---
notification_app = FastAPI()

@notification_app.get("/health")
async def health():
    return {"status": "ok", "bot_initialized": tg_application is not None}

@notification_app.post("/notifications/driver/{chat_id}")
async def api_notify_driver(chat_id: int, request: Request):
    data = await request.json()
    if tg_application:
        await driver.notify_new_order(tg_application.bot, chat_id, data)
    return {"success": True}

# --- Bot Handlers ---
async def start_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 Вітаємо! Оберіть роль:", reply_markup=KEYBOARDS['role_selection_menu']())

async def main():
    global tg_application
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN missing!")
        return

    # Ініціалізація бота
    tg_application = Application.builder().token(BOT_TOKEN).build()
    tg_application.add_handler(CommandHandler("start", start_message))
    
    passenger.register_handlers(tg_application, user_orders, user_roles, BUTTONS, KEYBOARDS, HELPERS)
    driver.register_handlers(tg_application, user_orders, user_roles, BUTTONS, KEYBOARDS, HELPERS)

    # Конфігурація сервера
    config = uvicorn.Config(notification_app, host="0.0.0.0", port=8080, log_level="info")
    server = uvicorn.Server(config)

    logger.info("🚀 Запуск Bot Polling та FastAPI Server...")
    
    # Запускаємо бота та сервер паралельно
    async with tg_application:
        await tg_application.initialize()
        await tg_application.start()
        await tg_application.updater.start_polling()
        
        # Запускаємо сервер FastAPI і чекаємо на його завершення
        await server.serve()
        
        await tg_application.updater.stop()
        await tg_application.stop()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
