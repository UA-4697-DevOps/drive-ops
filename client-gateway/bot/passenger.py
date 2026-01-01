import logging
import re
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardRemove
from telegram.ext import MessageHandler, CallbackQueryHandler, ConversationHandler, ContextTypes, filters, CommandHandler

logger = logging.getLogger('drive_ops')

# Conversation states
PICKUP, DROPOFF, COMMENT = range(3)


def register_handlers(application, user_orders, user_roles, buttons, keyboards, helpers):
    
    BTN_PASSENGER = buttons['BTN_PASSENGER']
    BTN_ORDER_TAXI = buttons['BTN_ORDER_TAXI']
    BTN_RATES = buttons['BTN_RATES']
    BTN_SKIP = buttons['BTN_SKIP']
    
    passenger_menu = keyboards['passenger_menu']
    skip_menu = keyboards['skip_menu']
    get_user_menu = keyboards['get_user_menu']
    
    safe_send = helpers['safe_send']
    submit_trip_request = helpers['submit_trip_request']
    is_valid_address = helpers['is_valid_address']
    
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
            "\U0001F4CD **Крок 1/3**: Введіть адресу відправлення (напр. вул. Хрещатик, 1):",
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
            "\U0001F3C1 **Крок 2/3**: Куди їдемо? (Введіть адресу призначення):",
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
            "\U0001F4AC **Крок 3/3**: Додайте коментар (під'їзд, дитяче крісло тощо) або натисніть кнопку нижче:", 
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
            f"\U0001F695 **Підтвердження замовлення**\n\n"
            f"\U0001F4CD **Звідки:** {order['pickup']}\n"
            f"\U0001F3C1 **Куди:** {order['dropoff']}\n"
            f"\U0001F4AC **Коментар:** {order['comment']}\n\n"
            f"\U0001F4B0 *Вартість буде розрахована після підтвердження.*"
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
            "\U0001F4CD **Крок 1/3**: Введіть адресу відправлення (напр. вул. Хрещатик, 1):",
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
                    
                    await query.edit_message_text(
                        text=(
                            "\u2705 **Замовлення прийнято!**\n"
                            "Шукаємо найближче авто...\n\n"
                            f"\U0001F194 Trip ID: {trip_id or req_id}\n"
                            f"\U0001F4E6 Статус: {status_text}"
                        ),
                        parse_mode='Markdown'
                    )
                else:
                    err_text = (error or {}).get('message')
                    code = (error or {}).get('status_code')
                    await query.edit_message_text(
                        text=(
                            "\u274C **Не вдалося створити поїздку.**\n"
                            f"Причина: {err_text or 'сервіс недоступний.'}\n"
                            + (f"Код: {code}\n" if code is not None else "")
                            + f"\nЛокальний запит: {req_id}"
                        ),
                        parse_mode='Markdown'
                    )
            elif query.data == "order_cancel":
                await query.edit_message_text(
                    text="\u274C **Замовлення скасовано.**",
                    parse_mode='Markdown'
                )
            
            chat_id = query.message.chat.id
            await context.bot.send_message(chat_id, "Головне меню:", reply_markup=get_user_menu(chat_id))
        finally:
            user_orders.pop(query.message.chat.id, None)

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
    )

    application.add_handler(MessageHandler(filters.Regex(f"^{re.escape(BTN_PASSENGER)}$"), select_passenger_role))
    application.add_handler(MessageHandler(filters.Regex(f"^{re.escape(BTN_RATES)}$"), show_rates))
    application.add_handler(conv_handler)
    application.add_handler(CallbackQueryHandler(handle_order_status, pattern="^order_"))
