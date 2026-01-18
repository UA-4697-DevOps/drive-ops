import re
import hashlib
import logging
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardRemove, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import MessageHandler, CallbackQueryHandler, ConversationHandler, ContextTypes, filters, CommandHandler
from telegram.helpers import escape_markdown

# Використовуємо налаштований логер
logger = logging.getLogger('drive_ops')

# Стейт-машина для реєстрації
DRIVER_NAME, DRIVER_CAR = range(2)

# --- Клавіатури рівня модуля ---
def driver_menu_unregistered():
    keyboard = [
        [KeyboardButton("📝 Зареєструватися як водій")],
        [KeyboardButton("🔄 Змінити роль")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def driver_menu_registered(is_online=False, active_trip=False):
    keyboard = [[KeyboardButton("📋 Мої замовлення"), KeyboardButton("📊 Мій статус")]]
    if active_trip:
        keyboard.append([KeyboardButton("🏁 Завершити поїздку")])
    else:
        btn_text = "🔴 Не приймати замовлення" if is_online else "🟢 Приймати замовлення"
        keyboard.append([KeyboardButton(btn_text)])
    keyboard.append([KeyboardButton("🔄 Змінити роль")])
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# --- Реєстрація хендлерів ---
def register_handlers(application, user_orders, user_roles, buttons, keyboards, helpers, DEBUGGING=False):
    
    # Витягуємо хелпери
    register_in_service = helpers['register_driver_in_service']
    update_status = helpers['update_driver_status']
    fetch_trips = helpers['fetch_driver_trips']
    send_trip_response = helpers['send_trip_response']
    finish_trip = helpers['finish_trip']

    # Кнопки
    BTN_DRIVER = buttons['BTN_DRIVER']
    BTN_REGISTER_DRIVER = buttons['BTN_REGISTER_DRIVER']
    BTN_GO_ONLINE = buttons['BTN_GO_ONLINE']
    BTN_GO_OFFLINE = buttons['BTN_GO_OFFLINE']

    async def select_driver_role(update: Update, context: ContextTypes.DEFAULT_TYPE):
        chat_id = update.effective_chat.id
        if chat_id in user_roles and user_roles[chat_id].get('role') == 'driver' and user_roles[chat_id].get('registered'):
            driver_info = user_roles[chat_id]
            is_online = driver_info.get('status') == 'online'
            has_active = driver_info.get('active_trip_id') is not None
            await update.message.reply_text(
                f"✅ Вітаємо, {driver_info.get('name')}!\nВаше авто: {driver_info.get('car_description')}",
                reply_markup=driver_menu_registered(is_online, has_active)
            )
        else:
            user_roles[chat_id] = {'role': 'driver', 'registered': False}
            await update.message.reply_text("🚖 Ви обрали роль водія. Для роботи пройдіть реєстрацію:", reply_markup=driver_menu_unregistered())

    async def start_registration(update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text("👤 Крок 1/2: Введіть ваше ім'я:", reply_markup=ReplyKeyboardRemove())
        return DRIVER_NAME

    async def process_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
        context.user_data['driver_name'] = update.message.text
        await update.message.reply_text("🚗 Крок 2/2: Опишіть ваше авто (марка, колір):")
        return DRIVER_CAR

    async def process_car(update: Update, context: ContextTypes.DEFAULT_TYPE):
        chat_id = update.effective_chat.id
        name = context.user_data['driver_name']
        car = update.message.text
        await update.message.reply_text("⏳ Реєструємо...")
        result = await register_in_service(chat_id, name, car)
        
        if result['success']:
            driver_id = result.get('data', {}).get('id', f"drv_{chat_id}")
            user_roles[chat_id] = {
                'role': 'driver', 'registered': True, 'driver_id': driver_id,
                'name': name, 'car_description': car, 'status': 'offline'
            }
            await update.message.reply_text("✅ Реєстрація успішна!", reply_markup=driver_menu_registered(False))
        else:
            await update.message.reply_text("❌ Помилка реєстрації.")
        return ConversationHandler.END

    async def toggle_online(update: Update, context: ContextTypes.DEFAULT_TYPE):
        chat_id = update.effective_chat.id
        driver_info = user_roles.get(chat_id, {})
        new_status = 'online' if update.message.text == BTN_GO_ONLINE else 'offline'
        result = await update_status(driver_info.get('driver_id'), new_status)
        if result['success']:
            user_roles[chat_id]['status'] = new_status
            await update.message.reply_text(f"Статус: {new_status}", reply_markup=driver_menu_registered(new_status == 'online'))
        else:
            await update.message.reply_text("❌ Помилка зміни статусу.")

    async def show_orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
        chat_id = update.effective_chat.id
        driver_id = user_roles.get(chat_id, {}).get('driver_id')
        result = await fetch_trips(driver_id)
        if result['success'] and result.get('data'):
            for trip in result['data']:
                t_id = trip.get('id')
                kb = InlineKeyboardMarkup([[InlineKeyboardButton("✅ Прийняти", callback_data=f"accept_trip_{t_id}")]])
                await update.message.reply_text(f"🚕 Замовлення: {trip.get('pickup')} -> {trip.get('dropoff')}", reply_markup=kb)
        else:
            await update.message.reply_text("📭 Нових замовлень немає.")

    async def accept_trip(update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        trip_id = query.data.replace('accept_trip_', '')
        dr_id = user_roles[query.message.chat.id]['driver_id']
        res = await send_trip_response(dr_id, trip_id, 'accept')
        if res['success']:
            user_roles[query.message.chat.id]['active_trip_id'] = trip_id
            await query.edit_message_text("✅ Поїздку прийнято! Ви в офлайні.")
            await context.bot.send_message(query.message.chat.id, "Керування:", reply_markup=driver_menu_registered(False, True))
        else:
            await query.answer("Помилка прийняття")

    async def finish_trip_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
        chat_id = update.effective_chat.id
        dr = user_roles.get(chat_id, {})
        res = await finish_trip(dr['driver_id'], dr['active_trip_id'])
        if res['success']:
            user_roles[chat_id]['active_trip_id'] = None
            await update.message.reply_text("🏁 Завершено!", reply_markup=driver_menu_registered(False))

    # --- Реєстрація хендлерів ---
    reg_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex(f"^{re.escape(BTN_REGISTER_DRIVER)}$"), start_registration)],
        states={DRIVER_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_name)],
                DRIVER_CAR: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_car)]},
        fallbacks=[CommandHandler("cancel", lambda u, c: ConversationHandler.END)]
    )
    application.add_handler(reg_conv)
    application.add_handler(MessageHandler(filters.Regex(f"^{re.escape(BTN_DRIVER)}$"), select_driver_role))
    application.add_handler(MessageHandler(filters.Regex(f"^{re.escape(BTN_GO_ONLINE)}|^{re.escape(BTN_GO_OFFLINE)}$"), toggle_online))
    application.add_handler(MessageHandler(filters.Regex(f"^📋 Мої замовлення$"), show_orders))
    application.add_handler(MessageHandler(filters.Regex(f"^🏁 Завершити поїздку$"), finish_trip_handler))
    application.add_handler(CallbackQueryHandler(accept_trip, pattern="^accept_trip_"))

# --- Push Notification ---
async def notify_new_order(bot, chat_id, order_info):
    t_id = order_info.get('trip_id')
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("✅ ПРИЙНЯТИ", callback_data=f"accept_trip_{t_id}")]])
    await bot.send_message(chat_id, f"🚨 **НОВЕ ЗАМОВЛЕННЯ!**\n📍 {order_info.get('pickup')}", reply_markup=kb, parse_mode='Markdown')
    return True
