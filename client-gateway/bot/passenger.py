import time
import logging
from telebot import types

logger = logging.getLogger('drive_ops')


def register_handlers(bot, user_orders, user_roles, buttons, keyboards, helpers):
    
    BTN_PASSENGER = buttons['BTN_PASSENGER']
    BTN_ORDER_TAXI = buttons['BTN_ORDER_TAXI']
    BTN_RATES = buttons['BTN_RATES']
    BTN_SKIP = buttons['BTN_SKIP']
    
    passenger_menu = keyboards['passenger_menu']
    skip_menu = keyboards['skip_menu']
    get_user_menu = keyboards['get_user_menu']
    
    safe_send = helpers['safe_send']
    validate_address_and_retry = helpers['validate_address_and_retry']
    submit_trip_request = helpers['submit_trip_request']
    
    @bot.message_handler(func=lambda message: message.text == BTN_PASSENGER)
    def select_passenger_role(message):
        chat_id = message.chat.id
        user_roles[chat_id] = 'passenger'
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("\U0001F695 Замовити таксі зараз", callback_data="quick_order_taxi"))
        
        bot.send_message(
            chat_id,
            "\u2705 Ви обрали роль: Замовник\n\n"
            "\U0001F697 Готові замовити таксі? Натисніть кнопку нижче або скористайтесь меню:",
            reply_markup=markup
        )
        bot.send_message(chat_id, "Меню:", reply_markup=passenger_menu())

    @bot.message_handler(func=lambda message: message.text == BTN_RATES)
    def show_rates(message):
        bot.send_message(
            message.chat.id,
            "\U0001F695 Тариф 'Стандарт': 15 грн/км\n\U0001F3E2 Тариф 'Комфорт': 25 грн/км"
        )

    @bot.message_handler(commands=['cancel_order'])
    def cancel_order_command(message):
        chat_id = message.chat.id
        if chat_id in user_orders:
            user_orders.pop(chat_id, None)
            safe_send(chat_id, "\u274C Ваше незавершене замовлення скасовано.", reply_markup=get_user_menu(chat_id))
        else:
            safe_send(chat_id, "У вас немає активного незавершеного замовлення.", reply_markup=get_user_menu(chat_id))

    def process_pickup_step(message):
        chat_id = message.chat.id
        
        if chat_id not in user_orders or not user_orders.get(chat_id):
            safe_send(chat_id, "❌ Замовлення скасовано або закінчилось. Спробуйте знову.", reply_markup=get_user_menu(chat_id))
            return
        
        address = message.text

        if not validate_address_and_retry(chat_id, address, "\u274C Адреса занадто коротка. Спробуйте ще раз:", process_pickup_step):
            return

        user_orders[chat_id]['pickup'] = address
        msg = bot.send_message(chat_id, "\U0001F3C1 **Крок 2/3**: Куди їдемо? (Введіть адресу призначення):", parse_mode='Markdown')
        bot.register_next_step_handler(msg, process_dropoff_step)

    def process_dropoff_step(message):
        chat_id = message.chat.id
        
        if chat_id not in user_orders or not user_orders.get(chat_id):
            safe_send(chat_id, "❌ Замовлення скасовано або закінчилось. Спробуйте знову.", reply_markup=get_user_menu(chat_id))
            return
        
        address = message.text

        if not validate_address_and_retry(chat_id, address, "\u274C Будь ласка, вкажіть повну адресу призначення:", process_dropoff_step):
            return

        user_orders[chat_id]['dropoff'] = address
        msg = bot.send_message(
            chat_id, 
            "\U0001F4AC **Крок 3/3**: Додайте коментар (під'їзд, дитяче крісло тощо) або натисніть кнопку нижче:", 
            reply_markup=skip_menu(),
            parse_mode='Markdown'
        )
        bot.register_next_step_handler(msg, process_comment_step)

    def process_comment_step(message):
        chat_id = message.chat.id
        
        if chat_id not in user_orders or not user_orders.get(chat_id):
            safe_send(chat_id, "❌ Замовлення скасовано або закінчилось. Спробуйте знову.", reply_markup=get_user_menu(chat_id))
            return
        
        if message.text == BTN_SKIP:
            user_orders[chat_id]['comment'] = "Не вказано"
        else:
            user_orders[chat_id]['comment'] = message.text

        order = user_orders[chat_id]
        summary = (
            f"\U0001F695 **Підтвердження замовлення**\n\n"
            f"\U0001F4CD **Звідки:** {order['pickup']}\n"
            f"\U0001F3C1 **Куди:** {order['dropoff']}\n"
            f"\U0001F4AC **Коментар:** {order['comment']}\n\n"
            f"\U0001F4B0 *Вартість буде розрахована після підтвердження.*"
        )

        markup = types.InlineKeyboardMarkup()
        markup.add(
            types.InlineKeyboardButton("\u2705 Підтвердити", callback_data="order_confirm"),
            types.InlineKeyboardButton("\u274C Скасувати", callback_data="order_cancel")
        )
        
        bot.send_message(chat_id, summary, parse_mode='Markdown', reply_markup=markup)

    def start_order_flow(chat_id):
        if chat_id not in user_roles:
            safe_send(chat_id, "Спочатку оберіть вашу роль за допомогою команди /start")
            return

        if chat_id in user_orders and user_orders[chat_id].get('_in_progress'):
            safe_send(chat_id, "У вас вже є незавершене замовлення. Скасуйте командою /cancel_order або завершіть поточне.")
            return

        user_orders[chat_id] = {'pickup': None, 'dropoff': None, 'comment': None, '_in_progress': True}
        
        msg = bot.send_message(
            chat_id, 
            "\U0001F4CD **Крок 1/3**: Введіть адресу відправлення (напр. вул. Хрещатик, 1):",
            parse_mode='Markdown',
            reply_markup=types.ReplyKeyboardRemove()
        )
        bot.register_next_step_handler(msg, process_pickup_step)

    @bot.message_handler(func=lambda message: message.text == BTN_ORDER_TAXI)
    def start_order(message):
        start_order_flow(message.chat.id)

    @bot.callback_query_handler(func=lambda call: call.data == 'quick_order_taxi')
    def handle_quick_order_taxi(call):
        try:
            bot.answer_callback_query(call.id)
        except Exception:
            pass
        
        chat_id = call.message.chat.id
        
        try:
            bot.edit_message_reply_markup(chat_id=chat_id, message_id=call.message.message_id, reply_markup=None)
        except Exception:
            pass
        
        start_order_flow(chat_id)

    @bot.callback_query_handler(func=lambda call: call.data.startswith('order_'))
    def handle_order_status(call):
        try:
            bot.answer_callback_query(call.id)
        except Exception:
            pass

        try:
            if call.data == "order_confirm":
                chat_id = call.message.chat.id
                order = user_orders.get(chat_id) or {}
                # Log request before submitting to TripService
                logger.info(
                    "Trip request confirmed: chat_id=%s pickup=%s dropoff=%s comment=%s",
                    chat_id, order.get('pickup'), order.get('dropoff'), order.get('comment')
                )

                result = submit_trip_request(chat_id, order)
                req_id = result.get('request_id')
                status = result.get('status', 'created')
                trip_id = result.get('trip_id')
                error = result.get('error')

                # Log response from TripService
                logger.info(
                    "Trip request response: success=%s trip_id=%s status=%s error=%s",
                    result.get('success'), trip_id, status, error
                )

                if result.get('success'):
                    bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=call.message.message_id,
                        text=(
                            "\u2705 **Замовлення прийнято!**\n"
                            "Шукаємо найближче авто...\n\n"
                            f"\U0001F194 Trip ID: {trip_id or req_id}\n"
                            f"\U0001F4E6 Статус: {status}"
                        ),
                        parse_mode='Markdown'
                    )
                else:
                    err_text = (error or {}).get('message')
                    code = (error or {}).get('status_code')
                    bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=call.message.message_id,
                        text=(
                            "\u274C **Не вдалося створити поїздку.**\n"
                            f"Причина: {err_text or 'сервіс недоступний.'}\n"
                            + (f"Код: {code}\n" if code is not None else "")
                            + f"\nЛокальний запит: {req_id}"
                        ),
                        parse_mode='Markdown'
                    )
            elif call.data == "order_cancel":
                bot.edit_message_text(
                    chat_id=call.message.chat.id,
                    message_id=call.message.message_id,
                    text="\u274C **Замовлення скасовано.**"
                )
            
            chat_id = call.message.chat.id
            bot.send_message(chat_id, "Головне меню:", reply_markup=get_user_menu(chat_id))
        finally:
            user_orders.pop(call.message.chat.id, None)

