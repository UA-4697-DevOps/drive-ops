import re
import html
import logging
from datetime import datetime
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardRemove, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import MessageHandler, CallbackQueryHandler, ConversationHandler, ContextTypes, filters, CommandHandler
from telegram.error import BadRequest

# Використовуємо стандартний логер, який ти налаштував
logger = logging.getLogger('drive_ops')

# Словник статусів для Phase 4
STATUS_MAPPING = {
    'PENDING': ('⏳ Очікує водія', 'Ваше замовлення в черзі. Очікуємо підтвердження від водія.'),
    'CONFIRMED': ('✅ Підтверджено', 'Водій прийняв замовлення і прямує до вас.'),
    'ACTIVE': ('🚗 В дорозі', 'Водій прийняв замовлення. Ви в дорозі!'),
    'IN_PROGRESS': ('🚗 В дорозі', 'Ви в дорозі до місця призначення.'),
    'COMPLETED': ('🏁 Завершено', 'Поїздка успішно завершена. Дякуємо!'),
    'CANCELLED': ('❌ Скасовано', 'Цю поїздку було скасовано.'),
}

# Стейт-машина для діалогів
PICKUP, DROPOFF, COMMENT = range(3)
CHECK_TRIP_ID = 10

# --- Глобальні функції меню (щоб main.py їх бачив) ---
def passenger_menu():
    keyboard = [
        [KeyboardButton("🚖 Замовити таксі"), KeyboardButton("💰 Тарифи")],
        [KeyboardButton("🔍 Перевірити статус")],
        [KeyboardButton("🔄 Змінити роль")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def escape_html(text: str) -> str:
    return html.escape(str(text))

# --- Реєстрація хендлерів ---
def register_handlers(application, user_orders, user_roles, buttons, keyboards, helpers):
    
    # Витягуємо хелпери, які ми прописали в main.py
    submit_trip_request = helpers['submit_trip_request']
    fetch_trip_status = helpers['fetch_trip_status']
    is_valid_address = helpers['is_valid_address']
    safe_send = helpers['safe_send']
    
    # Кнопки з main.py
    BTN_ORDER_TAXI = buttons['BTN_ORDER_TAXI']
    BTN_RATES = buttons['BTN_RATES']
    BTN_CHECK_STATUS = buttons['BTN_CHECK_STATUS']
    BTN_SKIP = buttons['BTN_SKIP']

    async def select_passenger_role(update: Update, context: ContextTypes.DEFAULT_TYPE):
        chat_id = update.effective_chat.id
        user_roles[chat_id] = {'role': 'passenger'}
        markup = InlineKeyboardMarkup([[InlineKeyboardButton("🚖 Замовити зараз", callback_data="quick_order_taxi")]])
        await update.message.reply_text("✅ Ви обрали роль: Замовник", reply_markup=passenger_menu())
        await update.message.reply_text("Бажаєте поїхати?", reply_markup=markup)

    # --- Потік створення замовлення (Phase 1) ---
    async def start_order_flow(update: Update, context: ContextTypes.DEFAULT_TYPE):
        chat_id = update.effective_chat.id
        user_orders[chat_id] = {'pickup': None, 'dropoff': None, 'comment': None, '_in_progress': True}
        await update.message.reply_text("📍 **Крок 1/3**: Звідки вас забрати?", parse_mode='Markdown', reply_markup=ReplyKeyboardRemove())
        return PICKUP

    async def process_pickup_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
        chat_id = update.effective_chat.id
        address = update.message.text
        if not is_valid_address(address):
            await update.message.reply_text("❌ Адреса занадто коротка. Спробуйте ще раз:")
            return PICKUP
        user_orders[chat_id]['pickup'] = address
        await update.message.reply_text("🏁 **Крок 2/3**: Куди їдемо?", parse_mode='Markdown')
        return DROPOFF

    async def process_dropoff_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
        chat_id = update.effective_chat.id
        address = update.message.text
        if not is_valid_address(address):
            await update.message.reply_text("❌ Будь ласка, вкажіть повну адресу:")
            return DROPOFF
        user_orders[chat_id]['dropoff'] = address
        skip_kb = ReplyKeyboardMarkup([[KeyboardButton(BTN_SKIP)]], resize_keyboard=True)
        await update.message.reply_text("💬 **Крок 3/3**: Коментар для водія?", reply_markup=skip_kb, parse_mode='Markdown')
        return COMMENT

    async def process_comment_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
        chat_id = update.effective_chat.id
        text = update.message.text
        user_orders[chat_id]['comment'] = "Не вказано" if text == BTN_SKIP else text
        
        order = user_orders[chat_id]
        summary = (
            f"🚖 <b>Підтвердження замовлення</b>\n\n"
            f"📍 <b>Звідки:</b> {escape_html(order['pickup'])}\n"
            f"🏁 <b>Куди:</b> {escape_html(order['dropoff'])}\n"
            f"💬 <b>Коментар:</b> {escape_html(order['comment'])}"
        )
        markup = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Підтвердити", callback_data="order_confirm"),
             InlineKeyboardButton("❌ Скасувати", callback_data="order_cancel")]
        ])
        await update.message.reply_text(summary, parse_mode='HTML', reply_markup=markup)
        return ConversationHandler.END

    # --- Обробка результату (Phase 1 Response) ---
    async def handle_order_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        chat_id = query.message.chat.id

        if query.data == "order_confirm":
            order = user_orders.get(chat_id, {})
            await query.edit_message_text("⏳ Створюємо замовлення...")
            
            # Виклик API через наш новий APIClient
            result = await submit_trip_request(chat_id, order)
            
            if result['success']:
                # Витягуємо ID з поля data, як прописано в APIClient
                trip_id = result.get('data', {}).get('id', 'N/A')
                await query.edit_message_text(
                    f"✅ <b>Замовлення створено!</b>\n\n🆔 ID поїздки: <code>{trip_id}</code>\n"
                    f"Шукаємо водія. Ви отримаєте сповіщення.", 
                    parse_mode='HTML'
                )
            else:
                msg = result.get('error', {}).get('message', 'Бекенд недоступний')
                await query.edit_message_text(f"❌ Помилка: {msg}")
        
        else:
            await query.edit_message_text("❌ Замовлення скасовано.")
        
        user_orders.pop(chat_id, None)
        await context.bot.send_message(chat_id, "Головне меню:", reply_markup=passenger_menu())

    # --- Перевірка статусу (Phase 4) ---
    async def start_check_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text("🔍 Введіть ID поїздки для перевірки:", reply_markup=ReplyKeyboardRemove())
        return CHECK_TRIP_ID

    async def process_trip_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
        trip_id = update.message.text.strip()
        msg = await update.message.reply_text("⏳ Отримуємо дані...")
        
        result = await fetch_trip_status(trip_id, update.effective_chat.id)
        
        if result['success']:
            trip = result['data'] # Дані тепер тут
            status = trip.get('status', 'PENDING').upper()
            emoji, desc = STATUS_MAPPING.get(status, ('❓', 'Невідомий статус'))
            
            response = (
                f"📋 <b>Статус поїздки</b>\n\n"
                f"🆔 <code>{trip_id}</code>\n"
                f"📦 Статус: {emoji} {status}\n"
                f"📍 Від: {escape_html(trip.get('pickup', '—'))}\n"
                f"🏁 До: {escape_html(trip.get('dropoff', '—'))}\n\n"
                f"💡 <i>{desc}</i>"
            )
            markup = InlineKeyboardMarkup([[InlineKeyboardButton("🔄 Оновити", callback_data=f"refresh_status_{trip_id}")]])
            await msg.edit_text(response, parse_mode='HTML', reply_markup=markup)
        else:
            await msg.edit_text("❌ Поїздку не знайдено або сервіс тимчасово лежить.")
        
        await context.bot.send_message(update.effective_chat.id, "Меню:", reply_markup=passenger_menu())
        return ConversationHandler.END

    # --- Реєстрація в Telegram Application ---
    order_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex(f"^{re.escape(BTN_ORDER_TAXI)}$"), start_order_flow),
                      CallbackQueryHandler(start_order_flow, pattern="^quick_order_taxi$")],
        states={
            PICKUP: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_pickup_step)],
            DROPOFF: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_dropoff_step)],
            COMMENT: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_comment_step)],
        },
        fallbacks=[CommandHandler("cancel", lambda u, c: ConversationHandler.END)]
    )

    status_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex(f"^{re.escape(BTN_CHECK_STATUS)}$"), start_check_status)],
        states={CHECK_TRIP_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_trip_id)]},
        fallbacks=[CommandHandler("cancel", lambda u, c: ConversationHandler.END)]
    )

    application.add_handler(order_conv)
    application.add_handler(status_conv)
    application.add_handler(MessageHandler(filters.Regex(f"^{re.escape(BTN_PASSENGER)}$"), select_passenger_role))
    application.add_handler(MessageHandler(filters.Regex(f"^{re.escape(BTN_RATES)}$"), lambda u, c: u.message.reply_text("💰 Тариф: 15 грн/км")))
    application.add_handler(CallbackQueryHandler(handle_order_callback, pattern="^order_"))
