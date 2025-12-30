import logging
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import MessageHandler, CallbackQueryHandler, ContextTypes, filters

logger = logging.getLogger('drive_ops')


def register_handlers(application, user_orders, user_roles, buttons, keyboards, helpers):
    
    BTN_DRIVER = buttons['BTN_DRIVER']
    BTN_MY_ORDERS = buttons['BTN_MY_ORDERS']
    
    driver_menu = keyboards['driver_menu']
    
    async def select_driver_role(update: Update, context: ContextTypes.DEFAULT_TYPE):
        chat_id = update.effective_chat.id
        user_roles[chat_id] = 'driver'
        await update.message.reply_text(
            "\u2705 Ви обрали роль: Таксист\n\nОберіть опцію:",
            reply_markup=driver_menu()
        )

    async def show_driver_orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
        chat_id = update.effective_chat.id
        await update.message.reply_text(
            "\U0001F4ED У вас немає нових замовлень\n\n"
            "\U0001F4A1 Нові замовлення з'являться тут автоматично."
        )

    async def accept_trip(update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        
        trip_id = query.data.replace('accept_trip_', '')
        chat_id = query.message.chat.id
        
        logger.info("Driver %s accepted trip %s", chat_id, trip_id)
        
        await query.edit_message_text(
            text=f"\u2705 Ви прийняли замовлення {trip_id}\n\nЗв'яжіться з клієнтом.",
            parse_mode='Markdown'
        )
    
    async def decline_trip(update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        
        trip_id = query.data.replace('decline_trip_', '')
        chat_id = query.message.chat.id
        
        logger.info("Driver %s declined trip %s", chat_id, trip_id)
        
        await query.edit_message_text(
            text=f"\u274C Ви відхилили замовлення {trip_id}",
            parse_mode='Markdown'
        )

    application.add_handler(MessageHandler(filters.Text([BTN_DRIVER]), select_driver_role))
    application.add_handler(MessageHandler(filters.Text([BTN_MY_ORDERS]), show_driver_orders))
    application.add_handler(CallbackQueryHandler(accept_trip, pattern="^accept_trip_"))
    application.add_handler(CallbackQueryHandler(decline_trip, pattern="^decline_trip_"))


async def notify_new_order(bot, driver_chat_id, order_info):
    trip_id = order_info.get('trip_id', 'N/A')
    pickup = order_info.get('pickup', 'Не вказано')
    dropoff = order_info.get('dropoff', 'Не вказано')
    comment = order_info.get('comment', '')
    
    text = (
        "\U0001F6A8 **Нове замовлення!**\n\n"
        f"\U0001F194 ID: {trip_id}\n"
        f"\U0001F4CD **Звідки:** {pickup}\n"
        f"\U0001F3C1 **Куди:** {dropoff}\n"
    )
    
    if comment:
        text += f"\U0001F4AC **Коментар:** {comment}\n"
    
    markup = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("\u2705 Прийняти", callback_data=f"accept_trip_{trip_id}"),
            InlineKeyboardButton("\u274C Відхилити", callback_data=f"decline_trip_{trip_id}")
        ]
    ])
    
    try:
        await bot.send_message(driver_chat_id, text, parse_mode='Markdown', reply_markup=markup)
        return True
    except Exception as e:
        logger.exception("Failed to notify driver %s: %s", driver_chat_id, e)
        return False
