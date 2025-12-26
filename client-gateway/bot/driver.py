import logging
from telebot import types

logger = logging.getLogger('drive_ops')


def register_handlers(bot, user_orders, user_roles, buttons, keyboards, helpers):
    
    BTN_DRIVER = buttons['BTN_DRIVER']
    BTN_MY_ORDERS = buttons['BTN_MY_ORDERS']
    
    driver_menu = keyboards['driver_menu']
    
    @bot.message_handler(func=lambda message: message.text == BTN_DRIVER)
    def select_driver_role(message):
        chat_id = message.chat.id
        user_roles[chat_id] = 'driver'
        bot.send_message(
            chat_id,
            "\u2705 Ви обрали роль: Таксист\n\nОберіть опцію:",
            reply_markup=driver_menu()
        )

    @bot.message_handler(func=lambda message: message.text == BTN_MY_ORDERS)
    def show_driver_orders(message):
        chat_id = message.chat.id
        bot.send_message(
            chat_id,
            "\U0001F4ED У вас немає нових замовлень\n\n"
            "\U0001F4A1 Нові замовлення з'являться тут автоматично."
        )
    @bot.callback_query_handler(func=lambda call: call.data.startswith('accept_trip_'))
    def accept_trip(call):
        try:
            bot.answer_callback_query(call.id)
        except Exception:
            pass
        
        trip_id = call.data.replace('accept_trip_', '')
        chat_id = call.message.chat.id
        
        logger.info("Driver %s accepted trip %s", chat_id, trip_id)
        
        bot.edit_message_text(
            chat_id=chat_id,
            message_id=call.message.message_id,
            text=f"\u2705 Ви прийняли замовлення {trip_id}\n\nЗв'яжіться з клієнтом.",
            parse_mode='Markdown'
        )
    
    @bot.callback_query_handler(func=lambda call: call.data.startswith('decline_trip_'))
    def decline_trip(call):
        try:
            bot.answer_callback_query(call.id)
        except Exception:
            pass
        
        trip_id = call.data.replace('decline_trip_', '')
        chat_id = call.message.chat.id
        
        logger.info("Driver %s declined trip %s", chat_id, trip_id)
        
        bot.edit_message_text(
            chat_id=chat_id,
            message_id=call.message.message_id,
            text=f"\u274C Ви відхилили замовлення {trip_id}",
            parse_mode='Markdown'
        )


def notify_new_order(bot, driver_chat_id, order_info):
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
    
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("\u2705 Прийняти", callback_data=f"accept_trip_{trip_id}"),
        types.InlineKeyboardButton("\u274C Відхилити", callback_data=f"decline_trip_{trip_id}")
    )
    
    try:
        bot.send_message(driver_chat_id, text, parse_mode='Markdown', reply_markup=markup)
        return True
    except Exception as e:
        logger.exception("Failed to notify driver %s: %s", driver_chat_id, e)
        return False

