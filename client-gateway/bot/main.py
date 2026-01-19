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

# --- КОНСТАНТИ КНОПОК ---
# Визначаємо всі кнопки, які можуть знадобитися в passenger.py та driver.py
BTN_PASSENGER = "\U0001F64B Я замовник таксі"
BTN_DRIVER = "\U0001F697 Я таксист"
BTN_CHANGE_ROLE = "\U0001F504 Змінити роль"
BTN_RATES = "\U0001F4B0 Тарифи"
BTN_MY_ORDERS = "\U0001F4CB Мої замовлення"
BTN_ORDER_TAXI = "\U0001F695 Замовити таксі"
BTN_SKIP = "\u23E9 Пропустити"
BTN_REGISTER_DRIVER = "\U0001F4DD Зареєструватися як водій"
BTN_GO_ONLINE = "\U0001F7E2 Приймати замовлення"
BTN_GO_OFFLINE = "\U0001F534 Не приймати замовлення"
BTN_DRIVER_STATUS = "\U0001F4CA Мій статус"
BTN_FINISH_TRIP = "\U0001F3C1 Завершити поїздку"
BTN_CHECK_STATUS = "\U0001F50D Перевірити статус"

# Ін'єкція в модулі для уникнення NameError
passenger.BTN_PASSENGER = BTN_PASSENGER
driver.BTN_DRIVER = BTN_DRIVER

# Повний словник кнопок (виправляє KeyError: 'BTN_RATES')
BUTTONS = {
    'BTN_PASSENGER': BTN_PASSENGER,
    'BTN_DRIVER': BTN_DRIVER,
    'BTN_CHANGE_ROLE': BTN_CHANGE_ROLE,
    'BTN_RATES': BTN_RATES,
    'BTN_MY_ORDERS': BTN_MY_ORDERS,
    'BTN_ORDER_TAXI': BTN_ORDER_TAXI,
    'BTN_SKIP': BTN_SKIP,
    'BTN_REGISTER_DRIVER': BTN_REGISTER_DRIVER,
    'BTN_GO_ONLINE': BTN_GO_ONLINE,
    'BTN_GO_OFFLINE': BTN_GO_OFFLINE,
    'BTN_DRIVER_STATUS': BTN_DRIVER_STATUS,
    'BTN_FINISH_TRIP': BTN_FINISH_TRIP,
    'BTN_CHECK_STATUS': BTN_CHECK_STATUS,
}

user_orders, user_roles = {}, {}
tg_application = None

# --- HELPERS ---
async def fetch_trip_status(trip_id, user_id=None):
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{TRIP_SERVICE_URL}/trips/{trip_id}")
            if resp.status_code == 200:
                return {'success': True, 'trip': resp.json()}
    except Exception: pass
    return {'success': False, 'error': 'Сервіс недоступний'}

HELPERS = {
    'submit_trip_request': lambda c, o: APIClient.create_trip({**o, 'passenger_id': str(uuid.uuid4())}),
    'register_driver_in_service': lambda c, n, car: APIClient.register_driver({'name': n, 'car_description': car, 'telegram_id': str(c)}),
    'update_driver_status': lambda d, s: APIClient.update_driver_status(d, s),
    'fetch_trip_status': fetch_trip_status,
    'safe_send': lambda c_id, txt, ctx, **kw: ctx.bot.send_message(c_id, txt, **kw),
    'is_valid_address': lambda addr: addr is not None and len(addr) > 5
}

KEYBOARDS = {
    'role_selection_menu': lambda: ReplyKeyboardMarkup([[KeyboardButton(BTN_PASSENGER), KeyboardButton(BTN_DRIVER)]], resize_keyboard=True),
    'passenger_menu': passenger.passenger_menu,
    'driver_menu_unregistered': driver.driver_menu_unregistered,
    'driver_menu_registered': driver.driver_menu_registered,
}

# --- FastAPI ---
notification_app = FastAPI()

@notification_app.get("/health")
async def health():
    return {"status": "ok", "bot_running": tg_application is not None}

@notification_app.post("/notifications/driver/{chat_id}")
async def notify(chat_id: int, request: Request):
    data = await request.json()
    if tg_application:
        await driver.notify_new_order(tg_application.bot, chat_id, data)
    return {"success": True}

# --- Основний запуск ---
async def start_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 Вітаємо! Оберіть роль:", reply_markup=KEYBOARDS['role_selection_menu']())

async def main():
    global tg_application
    tg_application = Application.builder().token(BOT_TOKEN).build()
    tg_application.add_handler(CommandHandler("start", start_message))
    
    passenger.register_handlers(tg_application, user_orders, user_roles, BUTTONS, KEYBOARDS, HELPERS)
    driver.register_handlers(tg_application, user_roles, BUTTONS, KEYBOARDS, HELPERS)

    config = uvicorn.Config(notification_app, host="0.0.0.0", port=8080, log_level="info")
    server = uvicorn.Server(config)

    logger.info("🚀 Бот та Сервер готові до запуску...")
    async with tg_application:
        await tg_application.initialize()
        await tg_application.start()
        await tg_application.updater.start_polling()
        await server.serve()

if __name__ == "__main__":
    asyncio.run(main())

