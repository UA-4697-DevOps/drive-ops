import os
import re
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardRemove
from telegram.ext import MessageHandler, CallbackQueryHandler, ConversationHandler, ContextTypes, filters
from telegram.helpers import escape_markdown
from .logger_utils import create_trip_request_logger

logger = create_trip_request_logger()

# Conversation states for driver registration
DRIVER_NAME, DRIVER_CAR = range(2)


def register_handlers(application, user_orders, user_roles, buttons, keyboards, helpers, DEBUGGING=False):
    
    BTN_DRIVER = buttons['BTN_DRIVER']
    BTN_MY_ORDERS = buttons['BTN_MY_ORDERS']
    BTN_REGISTER_DRIVER = buttons['BTN_REGISTER_DRIVER']
    BTN_GO_ONLINE = buttons['BTN_GO_ONLINE']
    BTN_GO_OFFLINE = buttons['BTN_GO_OFFLINE']
    BTN_DRIVER_STATUS = buttons['BTN_DRIVER_STATUS']
    
    driver_menu_unregistered = keyboards['driver_menu_unregistered']
    driver_menu_registered = keyboards['driver_menu_registered']
    
    safe_send = helpers['safe_send']
    register_driver_in_service = helpers['register_driver_in_service']
    update_driver_status = helpers['update_driver_status']
    
    async def select_driver_role(update: Update, context: ContextTypes.DEFAULT_TYPE):
        chat_id = update.effective_chat.id
        
        # Check if driver is already registered
        if chat_id in user_roles and isinstance(user_roles[chat_id], dict) and user_roles[chat_id].get('role') == 'driver':
            driver_info = user_roles[chat_id]
            is_online = driver_info.get('status') == 'online'
            await update.message.reply_text(
                f"\u2705 Ви вже зареєстровані як водій\n\n"
                f"\U0001F464 Ім'я: {driver_info.get('name')}\n"
                f"\U0001F697 Авто: {driver_info.get('car_description')}\n"
                f"\U0001F7E2 Статус: {'На лінії' if is_online else 'Офлайн'}\n\n"
                "Оберіть опцію:",
                reply_markup=driver_menu_registered(is_online)
            )
        else:
            # New driver - needs registration
            user_roles[chat_id] = {'role': 'driver', 'registered': False}
            await update.message.reply_text(
                "\u2705 Ви обрали роль: Таксист\n\n"
                "\U0001F4DD Для початку роботи потрібно зареєструватися.\n"
                "Натисніть кнопку нижче:",
                reply_markup=driver_menu_unregistered()
            )

    async def start_registration(update: Update, context: ContextTypes.DEFAULT_TYPE):
        chat_id = update.effective_chat.id
        
        await update.message.reply_text(
            "\U0001F4DD *Реєстрація водія*\n\n"
            "\U0001F464 *Крок 1/2*: Введіть ваше ім'я:",
            parse_mode='Markdown',
            reply_markup=ReplyKeyboardRemove()
        )
        return DRIVER_NAME

    async def process_driver_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
        chat_id = update.effective_chat.id
        name = update.message.text
        
        if len(name) < 2:
            await update.message.reply_text("\u274C Ім'я занадто коротке. Спробуйте ще раз:")
            return DRIVER_NAME
        
        context.user_data['driver_name'] = name
        
        await update.message.reply_text(
            "\U0001F697 *Крок 2/2*: Опишіть ваше авто (марка, модель, колір):",
            parse_mode='Markdown'
        )
        return DRIVER_CAR

    async def process_driver_car(update: Update, context: ContextTypes.DEFAULT_TYPE):
        chat_id = update.effective_chat.id
        car_description = update.message.text
        
        if len(car_description) < 5:
            await update.message.reply_text("\u274C Опис авто занадто короткий. Спробуйте ще раз:")
            return DRIVER_CAR
        
        name = context.user_data.get('driver_name')
        
        # Show processing message
        await update.message.reply_text(
            "\u23F3 Реєструємо вас у системі...",
            parse_mode='Markdown'
        )
        
        # Call Driver Service API
        result = await register_driver_in_service(chat_id, name, car_description)
        
        if result['success']:
            driver_id = result['driver_id']
            
            # Store driver info in user_roles
            user_roles[chat_id] = {
                'role': 'driver',
                'registered': True,
                'driver_id': driver_id,
                'name': name,
                'car_description': car_description,
                'status': 'offline'
            }
            
            logger.info("Driver registered successfully: chat_id=%s driver_id=%s name=%s", 
                       chat_id, driver_id, name)
            
            await update.message.reply_text(
                "\u2705 *Реєстрацію завершено!*\n\n"
                f"\U0001F464 Ім'я: {escape_markdown(name)}\n"
                f"\U0001F697 Авто: {escape_markdown(car_description)}\n"
                f"\U0001F194 ID водія: {escape_markdown(driver_id)}\n\n"
                "\U0001F4A1 Тепер ви можете вийти на лінію та отримувати замовлення.",
                parse_mode='Markdown',
                reply_markup=driver_menu_registered(is_online=False)
            )
        else:
            if DEBUGGING:

                driver_id = f"drv_{chat_id}"
                user_roles[chat_id] = {
                    'role': 'driver',
                    'registered': True,
                    'driver_id': driver_id,
                    'name': name,
                    'car_description': car_description,
                    'status': 'offline'
                }
                await update.message.reply_text(
                    "\u26A0\uFE0F *Режим налагодження*: Реєстрація змодельована успішно.\n\n"
                    f"\U0001F194 ID водія: {escape_markdown(driver_id)}\n\n"
                    "Ви можете вийти на лінію та отримувати замовлення.",
                    parse_mode='Markdown',
                    reply_markup=driver_menu_registered(is_online=False)
                )
            else:
                # Safely extract error message
                error_obj = result.get('error') if isinstance(result, dict) else None
                if isinstance(error_obj, dict):
                    error_msg = error_obj.get('message') or 'Невідома помилка'
                elif isinstance(error_obj, str) and error_obj:
                    error_msg = error_obj
                else:
                    error_msg = 'Невідома помилка'

                logger.error("Driver registration failed: chat_id=%s error=%s", chat_id, error_msg)

                await update.message.reply_text(
                    f"\u274C *Помилка реєстрації*\n\n{escape_markdown(str(error_msg or ''))}\n\n"
                    "Спробуйте ще раз пізніше.",
                    parse_mode='Markdown',
                    reply_markup=driver_menu_unregistered()
                )
            

        
        return ConversationHandler.END

    async def cancel_registration(update: Update, context: ContextTypes.DEFAULT_TYPE):
        chat_id = update.effective_chat.id
        await update.message.reply_text(
            "\u274C Реєстрацію скасовано.",
            reply_markup=driver_menu_unregistered()
        )
        return ConversationHandler.END

    async def go_online(update: Update, context: ContextTypes.DEFAULT_TYPE):
        chat_id = update.effective_chat.id
        
        if chat_id not in user_roles or not isinstance(user_roles[chat_id], dict):
            await update.message.reply_text("\u274C Спочатку зареєструйтесь як водій.")
            return
        
        driver_info = user_roles[chat_id]
        
        if not driver_info.get('registered'):
            await update.message.reply_text("\u274C Спочатку зареєструйтесь як водій.")
            return
        
        if driver_info.get('status') == 'online':
            await update.message.reply_text(
                "\U0001F7E2 Ви вже на лінії!",
                reply_markup=driver_menu_registered(is_online=True)
            )
            return
        
        driver_id = driver_info['driver_id']
        
        # Show processing message
        await update.message.reply_text("\u23F3 Виходимо на лінію...")
        
        # Call Driver Service API
        result = await update_driver_status(driver_id, 'online')
        
        if result['success']:
            user_roles[chat_id]['status'] = 'online'
            
            logger.info("Driver went online: chat_id=%s driver_id=%s", chat_id, driver_id)
            
            await update.message.reply_text(
                "\U0001F7E2 *Ви на лінії!*\n\n"
                "\U0001F4E2 Тепер ви будете отримувати нові замовлення.",
                parse_mode='Markdown',
                reply_markup=driver_menu_registered(is_online=True)
            )
        else:
            if DEBUGGING:
                user_roles[chat_id]['status'] = 'online'
                logger.info("[DEBUG] Driver went online (mocked): chat_id=%s driver_id=%s", chat_id, driver_id)
                
                await update.message.reply_text(
                    "\u26A0\uFE0F *Режим налагодження*: Статус оновлено\n\n"
                    "\U0001F7E2 Ви на лінії!",
                    parse_mode='Markdown',
                    reply_markup=driver_menu_registered(is_online=True)
                )
            else:
                # Safely extract error message
                error_obj = result.get('error') if isinstance(result, dict) else None
                if isinstance(error_obj, dict):
                    error_msg = error_obj.get('message') or 'Невідома помилка'
                elif isinstance(error_obj, str) and error_obj:
                    error_msg = error_obj
                else:
                    error_msg = 'Невідома помилка'

                logger.error("Failed to set driver online: chat_id=%s error=%s", chat_id, error_msg)
                
                await update.message.reply_text(
                    f"\u274C *Помилка*\n\n{escape_markdown(str(error_msg or ''))}",
                    parse_mode='Markdown'
                )

    async def go_offline(update: Update, context: ContextTypes.DEFAULT_TYPE):
        chat_id = update.effective_chat.id
        
        if chat_id not in user_roles or not isinstance(user_roles[chat_id], dict):
            await update.message.reply_text("\u274C Спочатку зареєструйтесь як водій.")
            return
        
        driver_info = user_roles[chat_id]
        
        if not driver_info.get('registered'):
            await update.message.reply_text("\u274C Спочатку зареєструйтесь як водій.")
            return
        
        if driver_info.get('status') == 'offline':
            await update.message.reply_text(
                "\U0001F534 Ви вже офлайн!",
                reply_markup=driver_menu_registered(is_online=False)
            )
            return
        
        driver_id = driver_info['driver_id']
        
        # Show processing message
        await update.message.reply_text("\u23F3 Виходимо з лінії...")
        
        # Call Driver Service API
        result = await update_driver_status(driver_id, 'offline')
        
        if result['success']:
            user_roles[chat_id]['status'] = 'offline'
            
            logger.info("Driver went offline: chat_id=%s driver_id=%s", chat_id, driver_id)
            
            await update.message.reply_text(
                "\U0001F534 *Ви офлайн*\n\n"
                "\U0001F6AB Ви більше не отримуватимете нові замовлення.",
                parse_mode='Markdown',
                reply_markup=driver_menu_registered(is_online=False)
            )
        else:
            if DEBUGGING:
                user_roles[chat_id]['status'] = 'offline'
                logger.info("[DEBUG] Driver went offline (mocked): chat_id=%s driver_id=%s", chat_id, driver_id)
                
                await update.message.reply_text(
                    "\u26A0\uFE0F *Режим налагодження*: Статус оновлено\n\n"
                    "\U0001F534 Ви офлайн",
                    parse_mode='Markdown',
                    reply_markup=driver_menu_registered(is_online=False)
                )
            else:
                # Safely extract error message
                error_obj = result.get('error') if isinstance(result, dict) else None
                if isinstance(error_obj, dict):
                    error_msg = error_obj.get('message') or 'Невідома помилка'
                elif isinstance(error_obj, str) and error_obj:
                    error_msg = error_obj
                else:
                    error_msg = 'Невідома помилка'

                logger.error("Failed to set driver offline: chat_id=%s error=%s", chat_id, error_msg)
                
                await update.message.reply_text(
                    f"\u274C *Помилка*\n\n{escape_markdown(str(error_msg or ''))}",
                    parse_mode='Markdown'
                )

    async def show_driver_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
        chat_id = update.effective_chat.id
        
        if chat_id not in user_roles or not isinstance(user_roles[chat_id], dict):
            await update.message.reply_text("\u274C Спочатку зареєструйтесь як водій.")
            return
        
        driver_info = user_roles[chat_id]
        
        if not driver_info.get('registered'):
            await update.message.reply_text(
                "\u274C Ви ще не зареєстровані як водій.",
                reply_markup=driver_menu_unregistered()
            )
            return
        
        is_online = driver_info.get('status') == 'online'
        status_emoji = "\U0001F7E2" if is_online else "\U0001F534"
        status_text = "На лінії" if is_online else "Офлайн"

        # Coerce values to safe strings before escaping to avoid TypeError
        safe_name = str(driver_info.get('name') or '')
        safe_car = str(driver_info.get('car_description') or '')
        safe_driver_id = str(driver_info.get('driver_id') or '')

        await update.message.reply_text(
            f"\U0001F4CA *Ваш статус*\n\n"
            f"\U0001F464 Ім'я: {escape_markdown(safe_name)}\n"
            f"\U0001F697 Авто: {escape_markdown(safe_car)}\n"
            f"\U0001F194 ID: {escape_markdown(safe_driver_id)}\n"
            f"{status_emoji} Статус: *{status_text}*",
            parse_mode='Markdown',
            reply_markup=driver_menu_registered(is_online)
        )

    async def show_driver_orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
        chat_id = update.effective_chat.id
        
        if chat_id not in user_roles or not isinstance(user_roles[chat_id], dict):
            await update.message.reply_text("\u274C Спочатку зареєструйтесь як водій.")
            return
        
        driver_info = user_roles[chat_id]
        
        if not driver_info.get('registered'):
            await update.message.reply_text(
                "\u274C Спочатку зареєструйтесь як водій.",
                reply_markup=driver_menu_unregistered()
            )
            return
        
        is_online = driver_info.get('status') == 'online'
        
        if is_online:
            await update.message.reply_text(
                "\U0001F4ED У вас немає нових замовлень\n\n"
                "\U0001F4A1 Нові замовлення з'являться тут автоматично."
            )
        else:
            await update.message.reply_text(
                "\U0001F534 Ви офлайн\n\n"
                "\U0001F4A1 Вийдіть на лінію, щоб отримувати замовлення.",
                reply_markup=driver_menu_registered(is_online=False)
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

    # Expose inner handlers to module-level so tests can invoke them directly.
    # They close over the `user_orders` and `user_roles` passed to `register_handlers`.
    globals()['process_driver_car_handler'] = process_driver_car
    globals()['start_registration_handler'] = start_registration
    globals()['go_online_handler'] = go_online
    globals()['go_offline_handler'] = go_offline
    globals()['show_driver_status_handler'] = show_driver_status

    # Registration conversation handler
    registration_handler = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex(f"^{re.escape(BTN_REGISTER_DRIVER)}$"), start_registration)
        ],
        states={
            DRIVER_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_driver_name)],
            DRIVER_CAR: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_driver_car)],
        },
        fallbacks=[
            MessageHandler(filters.Regex("^/cancel$"), cancel_registration)
        ],
        allow_reentry=True
    )
    
    application.add_handler(registration_handler)
    application.add_handler(MessageHandler(filters.Regex(f"^{re.escape(BTN_DRIVER)}$"), select_driver_role))
    application.add_handler(MessageHandler(filters.Regex(f"^{re.escape(BTN_MY_ORDERS)}$"), show_driver_orders))
    application.add_handler(MessageHandler(filters.Regex(f"^{re.escape(BTN_GO_ONLINE)}$"), go_online))
    application.add_handler(MessageHandler(filters.Regex(f"^{re.escape(BTN_GO_OFFLINE)}$"), go_offline))
    application.add_handler(MessageHandler(filters.Regex(f"^{re.escape(BTN_DRIVER_STATUS)}$"), show_driver_status))
    application.add_handler(CallbackQueryHandler(accept_trip, pattern="^accept_trip_"))
    application.add_handler(CallbackQueryHandler(decline_trip, pattern="^decline_trip_"))


async def notify_new_order(bot, driver_chat_id, order_info):
    trip_id = order_info.get('trip_id', 'N/A')
    pickup = order_info.get('pickup', 'Не вказано')
    dropoff = order_info.get('dropoff', 'Не вказано')
    comment = order_info.get('comment', '')
    
    text = (
        "\U0001F6A8 **Нове замовлення!**\n\n"
        f"\U0001F194 ID: {escape_markdown(trip_id)}\n"
        f"\U0001F4CD **Звідки:** {escape_markdown(pickup)}\n"
        f"\U0001F3C1 **Куди:** {escape_markdown(dropoff)}\n"
    )
    
    if comment:
        text += f"\U0001F4AC **Коментар:** {escape_markdown(comment)}\n"
    
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
