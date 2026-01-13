import re
from datetime import datetime
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardRemove
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
CHECK_TRIP_ID = 10  # Separate state for check status flow


def register_handlers(application, user_orders, user_roles, buttons, keyboards, helpers):
    
    BTN_PASSENGER = buttons['BTN_PASSENGER']
    BTN_ORDER_TAXI = buttons['BTN_ORDER_TAXI']
    BTN_RATES = buttons['BTN_RATES']
    BTN_SKIP = buttons['BTN_SKIP']
    BTN_CHECK_STATUS = buttons['BTN_CHECK_STATUS']
    
    passenger_menu = keyboards['passenger_menu']
    skip_menu = keyboards['skip_menu']
    get_user_menu = keyboards['get_user_menu']
    
    safe_send = helpers['safe_send']
    submit_trip_request = helpers['submit_trip_request']
    is_valid_address = helpers['is_valid_address']
    fetch_trip_status = helpers['fetch_trip_status']
    
    async def select_passenger_role(update: Update, context: ContextTypes.DEFAULT_TYPE):
        chat_id = update.effective_chat.id
        user_roles[chat_id] = 'passenger'
        markup = InlineKeyboardMarkup([
            [InlineKeyboardButton("\U0001F695 Замовити таксі зараз", callback_data="quick_order_taxi")]
        ])
        
        await update.message.reply_text(
            "\u2705 Ви обрали роль: Замовник\n\n"
            "\U0001F697 Готові замовити таксі? Натисніть кнопку нижче або скористайтесь меню:",
            reply_markup=markup
        )
        await update.message.reply_text("Меню:", reply_markup=passenger_menu())

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
        
        summary = (
            f"\U0001F695 *Підтвердження замовлення*\n\n"
            f"\U0001F4CD *Звідки:* {order['pickup']}\n"
            f"\U0001F3C1 *Куди:* {order['dropoff']}\n"
            f"\U0001F4AC *Коментар:* {order['comment']}\n\n"
            f"\U0001F4B0 Вартість буде розрахована після підтвердження."
        )

        markup = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("\u2705 Підтвердити", callback_data="order_confirm"),
                InlineKeyboardButton("\u274C Скасувати", callback_data="order_cancel")
            ]
        ])
        
        logger.info("Sending confirmation message to chat_id=%s", chat_id)
        await update.message.reply_text(summary, parse_mode='Markdown', reply_markup=markup)
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

        try:
            if query.data == "order_confirm":
                chat_id = query.message.chat.id
                order = user_orders.get(chat_id) or {}
                logger.info(
                    "Trip request confirmed: chat_id=%s pickup=%s dropoff=%s comment=%s",
                    chat_id, order.get('pickup'), order.get('dropoff'), order.get('comment')
                )

            
                result = await submit_trip_request(chat_id, order)
                
                
                req_id = result.get('request_id')
                trip_id = result.get('trip_id')
                error = result.get('error')

                logger.info(
                    "Trip request response: success=%s trip_id=%s status=%s error=%s",
                    result.get('success'), trip_id, result.get('status'), error
                )

                if result.get('success'):
                    status = result.get('status', 'PENDING').upper()
                    status_text = {
                        'PENDING': '⏳ Очікує водія',
                        'CONFIRMED': '✅ Підтверджено',
                        'IN_PROGRESS': '🚗 В дорозі',
                        'COMPLETED': '🏁 Завершено',
                        'CANCELLED': '❌ Скасовано',
                    }.get(status, status)
                    
                    trip_display_id = trip_id or req_id or '—'
                    await query.edit_message_text(
                        text=(
                            "✅ Замовлення прийнято!\n"
                            "Шукаємо найближче авто...\n\n"
                            f"🆔 Trip ID: {trip_display_id}\n"
                            f"📦 Статус: {status_text}"
                        )
                    )
                else:
                    err_text = (error or {}).get('message')
                    code = (error or {}).get('status_code')
                    local_req = req_id if req_id is not None else 'N/A'
                    escaped_err = (err_text or 'сервіс недоступний.').replace('_', r'\_')
                    await query.edit_message_text(
                        text=(
                            "❌ Не вдалося створити поїздку.\n"
                            f"Причина: {escaped_err}\n"
                            + (f"Код: {code}\n" if code is not None else "")
                            + f"\nЛокальний запит: {local_req}"
                        ),
                        parse_mode='Markdown'
                    )
            elif query.data == "order_cancel":
                await query.edit_message_text(
                    text="❌ Замовлення скасовано."
                )
            
            chat_id = query.message.chat.id
            await context.bot.send_message(chat_id, "Головне меню:", reply_markup=get_user_menu(chat_id))
        finally:
            user_orders.pop(query.message.chat.id, None)

    # --- Check Trip Status Flow ---
    async def start_check_status_flow(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start the check trip status conversation flow."""
        chat_id = update.effective_chat.id
        
        if chat_id not in user_roles:
            await update.message.reply_text("Спочатку оберіть вашу роль за допомогою команди /start")
            return ConversationHandler.END
        
        await update.message.reply_text(
            "\U0001F50D *Перевірка статусу поїздки*\n\n"
            "Введіть ID поїздки (Trip ID), який ви отримали при замовленні:\n\n"
            "_Наприклад: `a1b2c3d4-e5f6-7890-abcd-ef1234567890`_\n\n"
            "Для скасування введіть /cancel",
            parse_mode='Markdown'
        )
        return CHECK_TRIP_ID
    
    async def process_trip_id_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Process the trip ID input and fetch status."""
        chat_id = update.effective_chat.id
        trip_id = update.message.text.strip()
        
        # Basic validation for UUID format
        uuid_pattern = re.compile(
            r'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$'
        )
        
        if not uuid_pattern.match(trip_id):
            await update.message.reply_text(
                "❌ *Невірний формат ID*\n\n"
                "Trip ID має бути у форматі UUID:\n"
                "`xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx`\n\n"
                "Спробуйте ще раз або введіть /cancel для скасування.",
                parse_mode='Markdown'
            )
            return CHECK_TRIP_ID
        
        # Show loading message
        loading_msg = await update.message.reply_text("⏳ Завантаження статусу поїздки...")
        
        # Fetch trip status from the service (passing chat_id for logging)
        result = await fetch_trip_status(trip_id, user_id=chat_id)
        
        if result.get('success'):
            trip_data = result.get('trip', {})
            status = trip_data.get('status', 'UNKNOWN').upper()
            pickup = trip_data.get('pickup', 'Не вказано')
            dropoff = trip_data.get('dropoff', 'Не вказано')
            created_at = trip_data.get('created_at', '')
            driver_id = trip_data.get('driver_id')
            
            status_emoji, status_description = STATUS_MAPPING.get(status, ('❓ Невідомий', 'Статус поїздки невідомий.'))
            
            # Format created_at if present
            created_info = ""
            if created_at:
                created_info = f"\n🕐 *Створено:* {created_at}"
            
            # Format driver info if assigned
            driver_info = ""
            if driver_id:
                driver_info = f"\n🚕 *Водій:* {driver_id}"
            else:
                driver_info = "\n🚕 *Водій:* Не призначено"
            
            response_text = (
                f"📋 *Інформація про поїздку*\n\n"
                f"🆔 *Trip ID:* `{trip_id}`\n"
                f"📦 *Статус:* {status_emoji}\n"
                f"📍 *Звідки:* {pickup}\n"
                f"🏁 *Куди:* {dropoff}"
                f"{driver_info}"
                f"{created_info}\n\n"
                f"💡 _{status_description}_"
            )
            
            # Add refresh button for non-final statuses
            if status not in ('COMPLETED', 'CANCELLED'):
                markup = InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔄 Оновити статус", callback_data=f"refresh_status_{trip_id}")]
                ])
                await loading_msg.edit_text(response_text, parse_mode='Markdown', reply_markup=markup)
            else:
                await loading_msg.edit_text(response_text, parse_mode='Markdown')
        else:
            error = result.get('error', {})
            error_code = error.get('status_code', 500)
            error_message = error.get('message', 'Невідома помилка')
            
            if error_code == 404:
                await loading_msg.edit_text(
                    f"❌ *Поїздку не знайдено*\n\n"
                    f"Trip ID: `{trip_id}`\n\n"
                    "Перевірте правильність введеного ID або зверніться до підтримки.",
                    parse_mode='Markdown'
                )
            else:
                await loading_msg.edit_text(
                    f"❌ *Помилка отримання статусу*\n\n"
                    f"Trip ID: `{trip_id}`\n"
                    f"Причина: {error_message}\n\n"
                    "Спробуйте пізніше або зверніться до підтримки.",
                    parse_mode='Markdown'
                )
        
        # Return to main menu
        await context.bot.send_message(chat_id, "Головне меню:", reply_markup=get_user_menu(chat_id))
        return ConversationHandler.END
    
    async def cancel_check_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Cancel the check status flow."""
        chat_id = update.effective_chat.id
        await update.message.reply_text(
            "❌ Перевірку статусу скасовано.",
            reply_markup=get_user_menu(chat_id)
        )
        return ConversationHandler.END
    
    async def handle_refresh_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle refresh status button callback."""
        query = update.callback_query
        
        trip_id = query.data[len('refresh_status_'):]
        
        # Validate trip_id is non-empty
        if not trip_id:
            await query.edit_message_text("❌ Невірний ID поїздки.")
            logger.warning("Empty trip_id in refresh_status callback")
            return
        
        # Validate UUID format
        uuid_pattern = re.compile(
            r'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$'
        )
        if not uuid_pattern.match(trip_id):
            await query.edit_message_text("❌ Невірний ID поїздки.")
            logger.warning("Invalid trip_id format in refresh_status: %s", trip_id)
            return
        
        await query.answer("Оновлення статусу...")
        
        chat_id = query.message.chat.id
        
        # Get current timestamp with milliseconds to ensure unique message
        updated_at = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        
        result = await fetch_trip_status(trip_id, user_id=chat_id)
        
        if result.get('success'):
            trip_data = result.get('trip', {})
            status = trip_data.get('status', 'UNKNOWN').upper()
            pickup = trip_data.get('pickup', 'Не вказано')
            dropoff = trip_data.get('dropoff', 'Не вказано')
            created_at = trip_data.get('created_at', '')
            driver_id = trip_data.get('driver_id')
            
            status_emoji, status_description = STATUS_MAPPING.get(status, ('❓ Невідомий', 'Статус поїздки невідомий.'))
            
            created_info = ""
            if created_at:
                created_info = f"\n🕐 *Створено:* {created_at}"
            
            # Format driver info if assigned
            driver_info = ""
            if driver_id:
                driver_info = f"\n🚕 *Водій:* {driver_id}"
            else:
                driver_info = "\n🚕 *Водій:* Не призначено"
            
            response_text = (
                f"📋 *Інформація про поїздку*\n\n"
                f"🆔 *Trip ID:* `{trip_id}`\n"
                f"📦 *Статус:* {status_emoji}\n"
                f"📍 *Звідки:* {pickup}\n"
                f"🏁 *Куди:* {dropoff}"
                f"{driver_info}"
                f"{created_info}\n\n"
                f"💡 _{status_description}_\n\n"
                f"🕐 _Оновлено: {updated_at}_"
            )
            
            try:
                if status not in ('COMPLETED', 'CANCELLED'):
                    markup = InlineKeyboardMarkup([
                        [InlineKeyboardButton("🔄 Оновити статус", callback_data=f"refresh_status_{trip_id}")]
                    ])
                    await query.edit_message_text(response_text, parse_mode='Markdown', reply_markup=markup)
                else:
                    await query.edit_message_text(response_text, parse_mode='Markdown')
            except BadRequest as e:
                logger.warning("Failed to edit message (possibly same content): %s", e)
        else:
            error = result.get('error', {})
            error_message = error.get('message', 'Невідома помилка')
            await query.edit_message_text(
                f"❌ *Помилка оновлення статусу*\n\n"
                f"Trip ID: `{trip_id}`\n"
                f"Причина: {error_message}\n\n"
                "Спробуйте пізніше.",
                parse_mode='Markdown'
            )

    # Conversation handler for ordering taxi
    conv_handler = ConversationHandler(
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
        # per_chat=True,
    )

    # Check trip status conversation handler
    check_status_conv_handler = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex(f"^{re.escape(BTN_CHECK_STATUS)}$"), start_check_status_flow),
        ],
        states={
            CHECK_TRIP_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_trip_id_step)],
        },
        fallbacks=[CommandHandler("cancel", cancel_check_status)],
    )

    application.add_handler(MessageHandler(filters.Regex(f"^{re.escape(BTN_PASSENGER)}$"), select_passenger_role))
    application.add_handler(MessageHandler(filters.Regex(f"^{re.escape(BTN_RATES)}$"), show_rates))
    application.add_handler(conv_handler)
    application.add_handler(check_status_conv_handler)
    application.add_handler(CallbackQueryHandler(handle_order_status, pattern="^order_"))
    application.add_handler(CallbackQueryHandler(handle_refresh_status, pattern="^refresh_status_"))
