import re
import html
from datetime import datetime
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardRemove, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import MessageHandler, CallbackQueryHandler, ConversationHandler, ContextTypes, filters, CommandHandler
from .logger_utils import create_trip_request_logger
from telegram.error import BadRequest

logger = create_trip_request_logger()

# Status mapping for trip statuses
STATUS_MAPPING = {
    'PENDING': ('⏳ Очікує водія', 'Ваше замовлення в черзі. Очікуємо підтвердження від водія.'),
    'CONFIRMED': ('✅ Підтверджено', 'Водій прийняв замовлення і прямує до вас.'),
    'ACTIVE': ('🚗 В дорозі', 'Водій прийняв замовлення. Ви в дорозі!'),
    'IN_PROGRESS': ('🚗 В дорозі', 'Ви в дорозі до місця призначення.'),
    'COMPLETED': ('🏁 Завершено', 'Поїздка успішно завершена. Дякуємо!'),
    'CANCELLED': ('❌ Скасовано', 'Цю поїздку було скасовано.'),
}

# Conversation states
PICKUP, DROPOFF, COMMENT = range(3)
CHECK_TRIP_ID = 10 

def escape_html(text: str) -> str:
    return html.escape(str(text))

def passenger_menu():
    keyboard = [
        [KeyboardButton("🚖 Замовити таксі"), KeyboardButton("💰 Тарифи")],
        [KeyboardButton("🔍 Перевірити статус")],
        [KeyboardButton("🔄 Змінити роль")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def register_handlers(application, user_orders, user_roles, buttons, keyboards, helpers):
    
    BTN_PASSENGER = buttons['BTN_PASSENGER']
    BTN_ORDER_TAXI = buttons['BTN_ORDER_TAXI']
    BTN_RATES = buttons['BTN_RATES']
    BTN_SKIP = buttons['BTN_SKIP']
    BTN_CHECK_STATUS = buttons['BTN_CHECK_STATUS']
    
    # Використовуємо передані клавіатури або локальну
    passenger_menu_kb = keyboards.get('passenger_menu', passenger_menu)
    skip_menu = keyboards['skip_menu']
    get_user_menu = keyboards['get_user_menu']
    
    safe_send = helpers['safe_send']
    submit_trip_request = helpers['submit_trip_request']
    is_valid_address = helpers['is_valid_address']
    fetch_trip_status = helpers['fetch_trip_status']
    
    async def select_passenger_role(update: Update, context: ContextTypes.DEFAULT_TYPE):
        chat_id = update.effective_chat.id
        user_roles[chat_id] = {'role': 'passenger'}
        markup = InlineKeyboardMarkup([
            [InlineKeyboardButton("\U0001F695 Замовити таксі зараз", callback_data="quick_order_taxi")]
        ])
        
        await update.message.reply_text(
            "\u2705 Ви обрали роль: Замовник\n\n"
            "\U0001F697 Готові замовити таксі? Натисніть кнопку нижче або скористайтесь меню:",
            reply_markup=markup
        )
        # Викликаємо меню як функцію, якщо це функція, або просто передаємо якщо об'єкт
        menu = passenger_menu_kb() if callable(passenger_menu_kb) else passenger_menu_kb
        await update.message.reply_text("Меню:", reply_markup=menu)

    async def show_rates(update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(
            "\U0001F695 Тариф 'Стандарт': 15 грн/км\n\U0001F3E2 Тариф 'Комфорт': 25 грн/км"
        )

    async def cancel_order_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
        chat_id = update.effective_chat.id
        if chat_id in user_orders:
            user_orders.pop(chat_id, None)
            await safe_send(chat_id, "\u274C Ваше незавершене замовлення скасовано.", context, reply_markup=get_user_menu(chat_id))
        else:
            await safe_send(chat_id, "У вас немає активного незавершеного замовлення.", context, reply_markup=get_user_menu(chat_id))
        return ConversationHandler.END

    async def start_order_flow(update: Update, context: ContextTypes.DEFAULT_TYPE):
        chat_id = update.effective_chat.id
        
        if chat_id not in user_roles:
            await update.message.reply_text("Спочатку оберіть вашу роль за допомогою команди /start")
            return ConversationHandler.END

        if chat_id in user_orders and user_orders[chat_id].get('_in_progress'):
            await update.message.reply_text("У вас вже є незавершене замовлення. Скасуйте командою /cancel_order або завершіть поточне.")
            return ConversationHandler.END

        user_orders[chat_id] = {'pickup': None, 'dropoff': None, 'comment': None, '_in_progress': True}
        
        await update.message.reply_text(
            "\U0001F4CD *Крок 1/3*: Введіть адресу відправлення (напр. вул. Хрещатик, 1):",
            parse_mode='Markdown',
            reply_markup=ReplyKeyboardRemove()
        )
        return PICKUP

    async def process_pickup_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
        chat_id = update.effective_chat.id
        
        if chat_id not in user_orders or not user_orders.get(chat_id):
            await safe_send(chat_id, "❌ Замовлення скасовано або закінчилось. Спробуйте знову.", context, reply_markup=get_user_menu(chat_id))
            return ConversationHandler.END
        
        address = update.message.text

        if not is_valid_address(address):
            await update.message.reply_text("\u274C Адреса занадто коротка. Спробуйте ще раз:")
            return PICKUP

        user_orders[chat_id]['pickup'] = address
        await update.message.reply_text(
            "\U0001F3C1 *Крок 2/3*: Куди їдемо? (Введіть адресу призначення):",
            parse_mode='Markdown'
        )
        return DROPOFF

    async def process_dropoff_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
        chat_id = update.effective_chat.id
        
        if chat_id not in user_orders or not user_orders.get(chat_id):
            await safe_send(chat_id, "❌ Замовлення скасовано або закінчилось. Спробуйте знову.", context, reply_markup=get_user_menu(chat_id))
            return ConversationHandler.END
        
        address = update.message.text

        if not is_valid_address(address):
            await update.message.reply_text("\u274C Будь ласка, вкажіть повну адресу призначення:")
            return DROPOFF

        user_orders[chat_id]['dropoff'] = address
        await update.message.reply_text(
            "\U0001F4AC *Крок 3/3*: Додайте коментар (під'їзд, дитяче крісло тощо) або натисніть кнопку нижче:", 
            reply_markup=skip_menu(),
            parse_mode='Markdown'
        )
        return COMMENT

    async def process_comment_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
        chat_id = update.effective_chat.id
        logger.info("process_comment_step called for chat_id=%s, text=%s", chat_id, update.message.text)
        
        if chat_id not in user_orders or not user_orders.get(chat_id):
            logger.warning("No active order for chat_id=%s in process_comment_step", chat_id)
            await safe_send(chat_id, "❌ Замовлення скасовано або закінчилось. Спробуйте знову.", context, reply_markup=get_user_menu(chat_id))
            return ConversationHandler.END
        
        if update.message.text == BTN_SKIP:
            user_orders[chat_id]['comment'] = "Не вказано"
        else:
            user_orders[chat_id]['comment'] = update.message.text

        order = user_orders[chat_id]
        logger.info("Order data: pickup=%s, dropoff=%s, comment=%s", order.get('pickup'), order.get('dropoff'), order.get('comment'))
        
        # Escape HTML special characters
        pickup = escape_html(order['pickup'])
        dropoff = escape_html(order['dropoff'])
        comment = escape_html(order['comment'])
        
        summary = (
            f"\U0001F695 <b>Підтвердження замовлення</b>\n\n"
            f"\U0001F4CD <b>Звідки:</b> {pickup}\n"
            f"\U0001F3C1 <b>Куди:</b> {dropoff}\n"
            f"\U0001F4AC <b>Коментар:</b> {comment}\n\n"
            f"\U0001F4B0 Вартість буде розрахована після підтвердження."
        )

        markup = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("\u2705 Підтвердити", callback_data="order_confirm"),
                InlineKeyboardButton("\u274C Скасувати", callback_data="order_cancel")
            ]
        ])
        
        logger.info("Sending confirmation message to chat_id=%s", chat_id)
        await update.message.reply_text(summary, parse_mode='HTML', reply_markup=markup)
        return ConversationHandler.END

    async def handle_quick_order_taxi(update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        
        chat_id = query.message.chat.id
        
        try:
            await query.edit_message_reply_markup(reply_markup=None)
        except Exception as e:
            logger.exception("Failed to clear inline keyboard markup for quick_order_taxi: %s", e)
        
        if chat_id not in user_roles:
            await context.bot.send_message(chat_id, "Спочатку оберіть вашу роль за допомогою команди /start")
            return ConversationHandler.END

        if chat_id in user_orders and user_orders[chat_id].get('_in_progress'):
            await context.bot.send_message(chat_id, "У вас вже є незавершене замовлення. Скасуйте командою /cancel_order або завершіть поточне.")
            return ConversationHandler.END

        user_orders[chat_id] = {'pickup': None, 'dropoff': None, 'comment': None, '_in_progress': True}
        
        await context.bot.send_message(
            chat_id, 
            "\U0001F4CD *Крок 1/3*: Введіть адресу відправлення (напр. вул. Хрещатик, 1):",
            parse_mode='Markdown',
            reply_markup=ReplyKeyboardRemove()
        )
        return PICKUP


    async def handle_order_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        chat_id = query.message.chat.id

        try:
            if query.data == "order_confirm":
                order = user_orders.get(chat_id) or {}
                
                # Логування спроби (важливо для дебагу)
                logger.info(
                    "Trip request confirmed: chat_id=%s pickup=%s dropoff=%s comment=%s",
                    chat_id, order.get('pickup'), order.get('dropoff'), order.get('comment')
                )

                await query.edit_message_text("⏳ Створюємо замовлення...")
                
                # Виклик API
                result = await submit_trip_request(chat_id, order)
                
                # Отримання даних з результату
                req_id = result.get('request_id')
                # APIClient повертає 'data', всередині якого 'id'
                trip_data = result.get('data', {})
                trip_id = trip_data.get('id') or trip_data.get('trip_id') or result.get('trip_id')
                error = result.get('error')

                logger.info(
                    "Trip request response: success=%s trip_id=%s error=%s",
                    result.get('success'), trip_id, error
                )

                if result.get('success'):
                    # Успішний сценарій
                    status = result.get('status', 'PENDING').upper()
                    
                    # Маппінг для красивого відображення
                    status_text_map = {
                        'PENDING': '⏳ Очікує водія',
                        'CONFIRMED': '✅ Підтверджено',
                        'IN_PROGRESS': '🚗 В дорозі',
                        'COMPLETED': '🏁 Завершено',
                        'CANCELLED': '❌ Скасовано',
                    }
                    status_display = status_text_map.get(status, status)
                    trip_display_id = trip_id or req_id or '—'
                    
                    await query.edit_message_text(
                        text=(
                            f"✅ <b>Замовлення прийнято!</b>\n"
                            f"Шукаємо найближче авто...\n\n"
                            f"🆔 Trip ID: <code>{trip_display_id}</code>\n"
                            f"📦 Статус: {status_display}"
                        ),
                        parse_mode='HTML'
                    )
                else:
                    # Сценарій помилки
                    err_data = error if isinstance(error, dict) else {}
                    err_msg = err_data.get('message', 'Невідома помилка бекенду')
                    code = err_data.get('status_code')
                    
                    # Екрануємо текст помилки, щоб HTML не поламався
                    safe_err_msg = html.escape(str(err_msg))
                    
                    error_text = f"❌ <b>Не вдалося створити поїздку</b>\nПричина: {safe_err_msg}"
                    if code:
                        error_text += f"\nКод: {code}"
                        
                    await query.edit_message_text(text=error_text, parse_mode='HTML')

            elif query.data == "order_cancel":
                await query.edit_message_text("❌ Замовлення скасовано.")

            # Повертаємо користувача в головне меню
            # Використовуємо get_user_menu, бо він знає контекст ролі
            menu = get_user_menu(chat_id)
            await context.bot.send_message(chat_id, "Головне меню:", reply_markup=menu)

        finally:
            # Очищуємо кошик замовлення в будь-якому випадку, щоб не зависало
            user_orders.pop(chat_id, None)

    # --- Check Trip Status Flow ---
    async def start_check_status_flow(update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(
            "\U0001F50D *Перевірка статусу поїздки*\nВведіть ID поїздки:",
            parse_mode='Markdown'
        )
        return CHECK_TRIP_ID
    
    async def process_trip_id_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
        chat_id = update.effective_chat.id
        trip_id = update.message.text.strip()
        
        result = await fetch_trip_status(trip_id, user_id=chat_id)
        
        if result.get('success'):
            trip = result['data']
            status = trip.get('status', 'UNKNOWN')
            emoji = STATUS_MAPPING.get(status, ('❓', ''))[0]
            await update.message.reply_text(f"Поїздка {trip_id}:\nСтатус: {emoji} {status}")
        else:
            await update.message.reply_text("❌ Поїздку не знайдено.")
            
        menu = get_user_menu(chat_id)
        await context.bot.send_message(chat_id, "Меню:", reply_markup=menu)
        return ConversationHandler.END

    async def cancel_check_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
        chat_id = update.effective_chat.id
        menu = get_user_menu(chat_id)
        await update.message.reply_text("❌ Скасовано.", reply_markup=menu)
        return ConversationHandler.END

    # --- Handlers ---
    order_conv = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex(f"^{re.escape(BTN_ORDER_TAXI)}$"), start_order_flow),
            CallbackQueryHandler(handle_quick_order_taxi, pattern="^quick_order_taxi$"),
        ],
        states={
            PICKUP: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_pickup_step)],
            DROPOFF: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_dropoff_step)],
            COMMENT: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_comment_step)],
        },
        fallbacks=[CommandHandler("cancel_order", cancel_order_command)],
    )

    status_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex(f"^{re.escape(BTN_CHECK_STATUS)}$"), start_check_status_flow)],
        states={CHECK_TRIP_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_trip_id_step)]},
        fallbacks=[CommandHandler("cancel", cancel_check_status)],
    )

    application.add_handler(MessageHandler(filters.Regex(f"^{re.escape(BTN_PASSENGER)}$"), select_passenger_role))
    application.add_handler(MessageHandler(filters.Regex(f"^{re.escape(BTN_RATES)}$"), show_rates))
    application.add_handler(order_conv)
    application.add_handler(status_conv)
    application.add_handler(CallbackQueryHandler(handle_order_status, pattern="^order_"))
