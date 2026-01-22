import re
import hashlib
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardRemove
from telegram.ext import MessageHandler, CallbackQueryHandler, ConversationHandler, ContextTypes, filters
from telegram.helpers import escape_markdown
from .logger_utils import create_trip_request_logger
from .api_client import APIClient

logger = create_trip_request_logger()

# Conversation states for driver registration
DRIVER_NAME, DRIVER_CAR = range(2)


def generate_fake_orders(chat_id):
    """
    Generate consistent fake orders for testing purposes.
    Orders are deterministic based on chat_id to ensure consistency across calls.
    
    Args:
        chat_id: The Telegram chat ID to base fake data on
        
    Returns:
        A list of 3 sample trip dictionaries with realistic pickup/dropoff locations
    """
    fake_orders_templates = [
        {
            "id": f"fake_trip_{chat_id}_001",
            "pickup": "м. Київ, вул. Хрещатик, 15",
            "dropoff": "м. Київ, Борисфіль аеропорт",
            "comment": "Поспішаю на рейс в 14:00"
        },
        {
            "id": f"fake_trip_{chat_id}_002",
            "pickup": "м. Київ, Центральний залізничний вокзал",
            "dropoff": "м. Київ, вул. Червоноармійська, 85",
            "comment": "Обережно з багажем"
        },
        {
            "id": f"fake_trip_{chat_id}_003",
            "pickup": "м. Київ, ТЦ 'Дніпро'",
            "dropoff": "м. Київ, вул. Мельникова, 50",
            "comment": ""
        }
    ]
    
    return fake_orders_templates


def register_handlers(application, user_orders, user_roles, buttons, keyboards, helpers, DEBUGGING=False):
    
    BTN_DRIVER = buttons['BTN_DRIVER']
    BTN_MY_ORDERS = buttons['BTN_MY_ORDERS']
    BTN_REGISTER_DRIVER = buttons['BTN_REGISTER_DRIVER']
    BTN_GO_ONLINE = buttons['BTN_GO_ONLINE']
    BTN_GO_OFFLINE = buttons['BTN_GO_OFFLINE']
    BTN_DRIVER_STATUS = buttons['BTN_DRIVER_STATUS']
    BTN_FINISH_TRIP = buttons['BTN_FINISH_TRIP']
    
    driver_menu_unregistered = keyboards['driver_menu_unregistered']
    driver_menu_registered = keyboards['driver_menu_registered']

    # Helper functions for API calls (some now replaced by APIClient methods)
    update_driver_status = helpers['update_driver_status']
    fetch_driver_trips = helpers['fetch_driver_trips']
    send_trip_response = helpers['send_trip_response']
    finish_trip = helpers['finish_trip']
    
    async def select_driver_role(update: Update, context: ContextTypes.DEFAULT_TYPE):
        chat_id = update.effective_chat.id

        # Get or create user from database
        result = await APIClient.get_or_create_bot_user(chat_id, current_role='driver')

        if not result['success']:
            await update.message.reply_text(
                "\u274C Помилка при підключенні до сервера. Спробуйте пізніше."
            )
            return

        bot_user = result['data']

        # Update current role to driver
        await APIClient.change_bot_user_role(chat_id, 'driver')

        # Check if driver is already registered
        if bot_user.get('driver_id'):
            # Driver already registered
            is_online = bot_user.get('driver_status') == 'online'
            has_active_trip = bot_user.get('active_trip_id') is not None
            await update.message.reply_text(
                f"\u2705 Ви вже зареєстровані як водій\n\n"
                f"\U0001F464 Ім'я: {bot_user.get('driver_name', 'Не вказано')}\n"
                f"\U0001F697 Авто: {bot_user.get('car_description', 'Не вказано')}\n"
                f"\U0001F7E2 Статус: {'На лінії' if is_online else 'Офлайн'}\n\n"
                "Оберіть опцію:",
                reply_markup=driver_menu_registered(is_online, has_active_trip)
            )
        else:
            # New driver - needs registration
            await update.message.reply_text(
                "\u2705 Ви обрали роль: Таксист\n\n"
                "\U0001F4DD Для початку роботи потрібно зареєструватися.\n"
                "Натисніть кнопку нижче:",
                reply_markup=driver_menu_unregistered()
            )

    async def start_registration(update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(
            "\U0001F4DD *Реєстрація водія*\n\n"
            "\U0001F464 *Крок 1/2*: Введіть ваше ім'я:",
            parse_mode='Markdown',
            reply_markup=ReplyKeyboardRemove()
        )
        return DRIVER_NAME

    async def process_driver_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
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

        # Register driver via API
        result = await APIClient.register_bot_user_as_driver(chat_id, name, car_description)

        if result['success']:
            bot_user = result['data']
            driver_id = bot_user['driver_id']

            # Sanitize PII for logs: use short hash instead of raw name
            try:
                sanitized_name = hashlib.sha256(name.encode()).hexdigest()[:8] if name else 'none'
            except Exception:
                sanitized_name = 'err'

            logger.info("Driver registered successfully: chat_id=%s driver_id=%s name_hash=%s", chat_id, driver_id, sanitized_name)

            await update.message.reply_text(
                "\u2705 *Реєстрацію завершено!*\n\n"
                f"\U0001F464 Ім'я: {escape_markdown(name)}\n"
                f"\U0001F697 Авто: {escape_markdown(car_description)}\n"
                f"\U0001F194 ID водія: {escape_markdown(str(driver_id))}\n\n"
                "\U0001F4A1 Тепер ви можете вийти на лінію та отримувати замовлення.",
                parse_mode='Markdown',
                reply_markup=driver_menu_registered(is_online=False, active_trip=False)
            )
        else:
            if DEBUGGING:
                # In debug mode, still use API to store test data
                driver_id = f"drv_{chat_id}"
                await update.message.reply_text(
                    "\u26A0\uFE0F *Режим налагодження*: Реєстрація змодельована успішно.\n\n"
                    f"\U0001F194 ID водія: {escape_markdown(driver_id)}\n\n"
                    "Ви можете вийти на лінію та отримувати замовлення.",
                    parse_mode='Markdown',
                    reply_markup=driver_menu_registered(is_online=False, active_trip=False)
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
        await update.message.reply_text(
            "\u274C Реєстрацію скасовано.",
            reply_markup=driver_menu_unregistered()
        )
        return ConversationHandler.END

    async def go_online(update: Update, context: ContextTypes.DEFAULT_TYPE):
        chat_id = update.effective_chat.id

        # Get user from database
        result = await APIClient.get_bot_user(chat_id)
        if not result['success'] or not result['data'].get('driver_id'):
            await update.message.reply_text("\u274C Спочатку зареєструйтесь як водій.")
            return

        bot_user = result['data']

        if bot_user.get('driver_status') == 'online':
            await update.message.reply_text(
                "\U0001F7E2 Ви вже на лінії!",
                reply_markup=driver_menu_registered(is_online=True)
            )
            return

        driver_id = bot_user['driver_id']

        # Show processing message
        await update.message.reply_text("\u23F3 Виходимо на лінію...")

        # Update status via API
        result = await APIClient.update_bot_user_driver_status(chat_id, is_online=True)

        if result['success']:
            logger.info("Driver went online: chat_id=%s driver_id=%s", chat_id, driver_id)

            # Also update driver service status
            await update_driver_status(driver_id, 'online')

            await update.message.reply_text(
                "\U0001F7E2 *Ви на лінії!*\n\n"
                "\U0001F4E2 Тепер ви будете отримувати нові замовлення.",
                parse_mode='Markdown',
                reply_markup=driver_menu_registered(is_online=True, active_trip=False)
            )
        else:
            if DEBUGGING:
                logger.info("[DEBUG] Driver went online (mocked): chat_id=%s driver_id=%s", chat_id, driver_id)

                await update.message.reply_text(
                    "\u26A0\uFE0F *Режим налагодження*: Статус оновлено\n\n"
                    "\U0001F7E2 Ви на лінії!",
                    parse_mode='Markdown',
                    reply_markup=driver_menu_registered(is_online=True, active_trip=False)
                )
            else:
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

        # Get user from database
        result = await APIClient.get_bot_user(chat_id)
        if not result['success'] or not result['data'].get('driver_id'):
            await update.message.reply_text("\u274C Спочатку зареєструйтесь як водій.")
            return

        bot_user = result['data']

        if bot_user.get('driver_status') == 'offline':
            await update.message.reply_text(
                "\U0001F534 Ви вже офлайн!",
                reply_markup=driver_menu_registered(is_online=False)
            )
            return

        driver_id = bot_user['driver_id']

        # Show processing message
        await update.message.reply_text("\u23F3 Виходимо з лінії...")

        # Update status via API
        result = await APIClient.update_bot_user_driver_status(chat_id, is_online=False)

        if result['success']:
            logger.info("Driver went offline: chat_id=%s driver_id=%s", chat_id, driver_id)

            # Also update driver service status
            await update_driver_status(driver_id, 'offline')

            await update.message.reply_text(
                "\U0001F534 *Ви офлайн*\n\n"
                "\U0001F6AB Ви більше не отримуватимете нові замовлення.",
                parse_mode='Markdown',
                reply_markup=driver_menu_registered(is_online=False, active_trip=False)
            )
        else:
            if DEBUGGING:
                logger.info("[DEBUG] Driver went offline (mocked): chat_id=%s driver_id=%s", chat_id, driver_id)

                await update.message.reply_text(
                    "\u26A0\uFE0F *Режим налагодження*: Статус оновлено\n\n"
                    "\U0001F534 Ви офлайн",
                    parse_mode='Markdown',
                    reply_markup=driver_menu_registered(is_online=False, active_trip=False)
                )
            else:
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

        # Get user from database
        result = await APIClient.get_bot_user(chat_id)
        if not result['success']:
            await update.message.reply_text("\u274C Спочатку зареєструйтесь як водій.")
            return

        bot_user = result['data']

        # Check if registered as driver
        if not bot_user.get('driver_id'):
            await update.message.reply_text(
                "\u274C Ви ще не зареєстровані як водій.",
                reply_markup=driver_menu_unregistered()
            )
            return

        is_online = bot_user.get('driver_status') == 'online'
        has_active_trip = bot_user.get('active_trip_id') is not None
        status_emoji = "\U0001F7E2" if is_online else "\U0001F534"
        status_text = "На лінії" if is_online else "Офлайн"

        # Coerce values to safe strings before escaping to avoid TypeError
        safe_name = str(bot_user.get('driver_name') or '')
        safe_car = str(bot_user.get('car_description') or '')
        safe_driver_id = str(bot_user.get('driver_id') or '')

        await update.message.reply_text(
            f"\U0001F4CA *Ваш статус*\n\n"
            f"\U0001F464 Ім'я: {escape_markdown(safe_name)}\n"
            f"\U0001F697 Авто: {escape_markdown(safe_car)}\n"
            f"\U0001F194 ID: {escape_markdown(safe_driver_id)}\n"
            f"{status_emoji} Статус: *{status_text}*",
            parse_mode='Markdown',
            reply_markup=driver_menu_registered(is_online, has_active_trip)
        )

    async def show_driver_orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
        chat_id = update.effective_chat.id

        # Get user from database
        result = await APIClient.get_bot_user(chat_id)
        if not result['success']:
            await update.message.reply_text("\u274C Спочатку зареєструйтесь як водій.")
            return

        bot_user = result['data']

        # Check if registered as driver
        if not bot_user.get('driver_id'):
            await update.message.reply_text(
                "\u274C Спочатку зареєструйтесь як водій.",
                reply_markup=driver_menu_unregistered()
            )
            return

        is_online = bot_user.get('driver_status') == 'online'
        active_trip_id = bot_user.get('active_trip_id')

        # If driver has active trip, show only active trip info
        if active_trip_id:
            await update.message.reply_text(
                f"\U0001F6A8 *У вас є активна поїздка*\n\n"
                f"\U0001F194 ID поїздки: `{escape_markdown(str(active_trip_id))}`\n\n"
                "🏁 Завершіть поточну поїздку, щоб побачити нові замовлення.\n"
                "Натисніть кнопку *Завершити поїздку* внизу.",
                parse_mode='Markdown',
                reply_markup=driver_menu_registered(is_online=False, active_trip=True)
            )
            return

        if not is_online:
            await update.message.reply_text(
                "\U0001F534 Ви офлайн\n\n"
                "\U0001F4A1 Вийдіть на лінію, щоб отримувати замовлення.",
                reply_markup=driver_menu_registered(is_online=False, active_trip=False)
            )
            return

        driver_id = bot_user.get('driver_id')
        
        # Show loading message
        await update.message.reply_text("\u23F3 Завантаження замовлень...")
        
        # Fetch trips from Driver Service
        result = await fetch_driver_trips(driver_id)
        
        trips = []
        
        if result['success']:
            trips = result.get('trips', [])
        elif DEBUGGING:
            logger.info("[DEBUG] Generating fake orders for driver: chat_id=%s driver_id=%s", chat_id, driver_id)
            trips = generate_fake_orders(chat_id)
        else:
            # API call failed and we're not in debug mode
            error_obj = result.get('error') if isinstance(result, dict) else None
            if isinstance(error_obj, dict):
                error_msg = error_obj.get('message') or 'Невідома помилка'
            elif isinstance(error_obj, str) and error_obj:
                error_msg = error_obj
            else:
                error_msg = 'Невідома помилка'
            
            logger.error("Failed to fetch trips: chat_id=%s driver_id=%s error=%s", chat_id, driver_id, error_msg)
            
            await update.message.reply_text(
                f"\u274C *Помилка отримання замовлень*\n\n{escape_markdown(str(error_msg))}\n\n"
                "Спробуйте ще раз пізніше.",
                parse_mode='Markdown',
                reply_markup=driver_menu_registered(is_online=True, active_trip=False)
            )
            return
        
        if not trips:
            if result['success']:
                logger.info("No pending trips for driver: chat_id=%s driver_id=%s", chat_id, driver_id)
                await update.message.reply_text(
                    "\U0001F4ED У вас немає нових замовлень\n\n"
                    "\U0001F4A1 Нові замовлення з'являться тут автоматично.",
                    reply_markup=driver_menu_registered(is_online=True, active_trip=False)
                )
            return
        
        # Prepare debug prefix if we're using fake orders
        debug_prefix = ""
        if DEBUGGING and not result['success']:
            debug_prefix = "\u26A0\uFE0F *Режим налагодження*: Змодельовані замовлення\n\n"
        
        logger.info("Found %d trips for driver: chat_id=%s driver_id=%s", len(trips), chat_id, driver_id)

        # Filter only PENDING trips (exclude ACTIVE/assigned trips)
        pending_trips = [trip for trip in trips if trip.get('status') == 'PENDING']

        if not pending_trips:
            await update.message.reply_text(
                "\U0001F4ED У вас немає нових замовлень\n\n"
                "\U0001F4A1 Нові замовлення з'являться тут автоматично.",
                reply_markup=driver_menu_registered(is_online=True, active_trip=False)
            )
            return

        logger.info("Showing %d pending trips (filtered from %d total)", len(pending_trips), len(trips))

        # Display each PENDING trip with Accept/Reject buttons
        for trip in pending_trips:
            trip_id = trip.get('id') or trip.get('trip_id') or 'N/A'
            pickup = trip.get('pickup') or trip.get('pickup_address') or 'Не вказано'
            dropoff = trip.get('dropoff') or trip.get('dropoff_address') or 'Не вказано'
            comment = trip.get('comment') or ''

            text = (
                "\U0001F6A8 *Нове замовлення*\n\n"
                f"\U0001F194 ID: `{escape_markdown(str(trip_id))}`\n"
                f"\U0001F4CD *Звідки:* {escape_markdown(str(pickup))}\n"
                f"\U0001F3C1 *Куди:* {escape_markdown(str(dropoff))}\n"
            )

            if comment:
                text += f"\U0001F4AC *Коментар:* {escape_markdown(str(comment))}\n"

            markup = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("\u2705 Прийняти", callback_data=f"accept_trip_{trip_id}"),
                    InlineKeyboardButton("\u274C Відхилити", callback_data=f"decline_trip_{trip_id}")
                ]
            ])

            await update.message.reply_text(
                text,
                parse_mode='Markdown',
                reply_markup=markup
            )
        
        summary_text = f"\U0001F4CB Знайдено замовлень: {len(pending_trips)}"
        if debug_prefix:
            summary_text = debug_prefix + summary_text
        
        await update.message.reply_text(
            summary_text,
            parse_mode='Markdown',
            reply_markup=driver_menu_registered(is_online=True, active_trip=False)
        )

    async def accept_trip(update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()

        trip_id = query.data.replace('accept_trip_', '')
        chat_id = query.message.chat.id

        # Get driver info from database
        result = await APIClient.get_bot_user(chat_id)
        if not result['success'] or not result['data'].get('driver_id'):
            logger.warning("Accept trip attempted by unregistered driver: chat_id=%s trip_id=%s", chat_id, trip_id)
            await query.edit_message_text(
                text="\u274C Ви не зареєстровані як водій.",
                parse_mode='Markdown'
            )
            return

        bot_user = result['data']
        driver_id = bot_user.get('driver_id')

        logger.info("Driver accepting trip: chat_id=%s driver_id=%s trip_id=%s", chat_id, driver_id, trip_id)

        # Show processing state
        await query.edit_message_text(
            text=f"\u23F3 Приймаємо замовлення {escape_markdown(str(trip_id))}...",
            parse_mode='Markdown'
        )

        # Call Driver Service
        result = await send_trip_response(driver_id, trip_id, 'accept')

        if result['success']:
            # Update status to offline and set active trip in database
            await APIClient.update_bot_user_driver_status(chat_id, is_online=False)
            await APIClient.set_bot_user_active_trip(chat_id, trip_id)

            logger.info("Trip accepted successfully: chat_id=%s driver_id=%s trip_id=%s", chat_id, driver_id, trip_id)
            await query.edit_message_text(
                text=(
                    f"\u2705 *Замовлення прийнято!*\n\n"
                    f"\U0001F194 ID: `{escape_markdown(str(trip_id))}`\n\n"
                    "\U0001F4DE Зв'яжіться з клієнтом для уточнення деталей.\n"
                    "\U0001F534 Ви перейшли в офлайн."
                ),
                parse_mode='Markdown'
            )

            # Automatically refresh status with updated menu
            try:
                await query.message.reply_text(
                    f"\U0001F4CA *Ваш статус*\n\n"
                    f"\U0001F464 Ім'я: {escape_markdown(str(bot_user.get('driver_name') or ''))}\n"
                    f"\U0001F697 Авто: {escape_markdown(str(bot_user.get('car_description') or ''))}\n"
                    f"\U0001F194 ID: {escape_markdown(str(driver_id))}\n"
                    f"\U0001F534 Статус: *Офлайн (активна поїздка)*",
                    parse_mode='Markdown',
                    reply_markup=driver_menu_registered(is_online=False, active_trip=True)
                )

                # Send message about active trip
                await query.message.reply_text(
                    f"\U0001F6A8 *Активна поїздка*\n\n"
                    f"\U0001F194 ID поїздки: `{escape_markdown(str(trip_id))}`\n\n"
                    f"📍 Відправна точка: {escape_markdown(str(result.get('pickup_address') or 'Не вказано'))}\n"
                    f"🏁 Точка призначення: {escape_markdown(str(result.get('dropoff_address') or 'Не вказано'))}\n\n"
                    "🏁 Натисніть кнопку *Завершити поїздку* коли закінчите",
                    parse_mode='Markdown'
                )
            except Exception as e:
                logger.warning("Failed to send status refresh after trip acceptance: %s", e)
        else:
            if DEBUGGING:
                # Set driver offline in debug mode as well
                await APIClient.update_bot_user_driver_status(chat_id, is_online=False)
                await APIClient.set_bot_user_active_trip(chat_id, trip_id)
                
                logger.info("[DEBUG] Mocking trip acceptance: chat_id=%s driver_id=%s trip_id=%s", chat_id, driver_id, trip_id)
                await query.edit_message_text(
                    text=(
                        "\u26A0\uFE0F *Режим налагодження*\n\n"
                        f"\u2705 Замовлення {escape_markdown(str(trip_id))} прийнято\n"
                        "\U0001F534 Ви перейшли в офлайн."
                    ),
                    parse_mode='Markdown'
                )
                
                # Automatically refresh status with updated menu in debug mode
                try:
                    await query.message.reply_text(
                        f"\U0001F4CA *Ваш статус*\n\n"
                        f"\U0001F464 Ім'я: {escape_markdown(str(user_roles[chat_id].get('name') or ''))}\n"
                        f"\U0001F697 Авто: {escape_markdown(str(user_roles[chat_id].get('car_description') or ''))}\n"
                        f"\U0001F194 ID: {escape_markdown(str(driver_id))}\n"
                        f"\U0001F534 Статус: *Офлайн (активна поїздка)*",
                        parse_mode='Markdown',
                        reply_markup=driver_menu_registered(is_online=False, active_trip=True)
                    )
                    
                    # Send message about active trip in debug mode
                    await query.message.reply_text(
                        f"\U0001F6A8 *Активна поїздка*\n\n"
                        f"\U0001F194 ID поїздки: `{escape_markdown(str(trip_id))}`\n\n"
                        "✅ Поїздка готова до початку\n"
                        "📱 Зв'яжіться з пасажиром\n"
                        "🏁 Натисніть кнопку *Завершити поїздку* коли закінчите",
                        parse_mode='Markdown'
                    )
                except Exception as e:
                    logger.warning("Failed to send status refresh after trip acceptance in debug mode: %s", e)
            else:
                error_obj = result.get('error') if isinstance(result, dict) else None
                if isinstance(error_obj, dict):
                    error_msg = error_obj.get('message') or 'Невідома помилка'
                    status_code = error_obj.get('status_code', 500)
                elif isinstance(error_obj, str) and error_obj:
                    error_msg = error_obj
                    status_code = 500
                else:
                    error_msg = 'Невідома помилка'
                    status_code = 500
                
                logger.error("Failed to accept trip: chat_id=%s driver_id=%s trip_id=%s error=%s status=%d", 
                           chat_id, driver_id, trip_id, error_msg, status_code)
                
                # Specific message for expired trips
                if status_code == 410:
                    await query.edit_message_text(
                        text=(
                            f"\u23F0 *Замовлення недоступне*\n\n"
                            f"\U0001F194 ID: `{escape_markdown(str(trip_id))}`\n\n"
                            "Це замовлення вже прийняте іншим водієм або закінчився час очікування."
                        ),
                        parse_mode='Markdown'
                    )
                elif status_code == 404:
                    await query.edit_message_text(
                        text=(
                            f"\u274C *Замовлення не знайдено*\n\n"
                            f"\U0001F194 ID: `{escape_markdown(str(trip_id))}`\n\n"
                            "Можливо, замовлення було скасовано."
                        ),
                        parse_mode='Markdown'
                    )
                else:
                    await query.edit_message_text(
                        text=(
                            f"\u274C *Помилка*\n\n"
                            f"{escape_markdown(str(error_msg))}\n\n"
                            "Спробуйте ще раз пізніше."
                        ),
                        parse_mode='Markdown'
                    )
    
    async def finish_trip_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
        chat_id = update.effective_chat.id

        # Get driver info from database
        result = await APIClient.get_bot_user(chat_id)
        if not result['success'] or not result['data'].get('driver_id'):
            await update.message.reply_text(
                "\u274C Ви не зареєстровані як водій.",
                reply_markup=driver_menu_unregistered()
            )
            return

        bot_user = result['data']
        active_trip_id = bot_user.get('active_trip_id')

        if not active_trip_id:
            await update.message.reply_text(
                "\u274C У вас немає активної поїздки.",
                reply_markup=driver_menu_registered(is_online=False, active_trip=False)
            )
            return

        driver_id = bot_user.get('driver_id')

        logger.info("Driver finishing trip: chat_id=%s driver_id=%s trip_id=%s", chat_id, driver_id, active_trip_id)

        # Show processing message
        await update.message.reply_text(f"\u23F3 Завершуємо поїздку {escape_markdown(str(active_trip_id))}...", parse_mode='Markdown')

        # Call finish_trip helper
        result = await finish_trip(driver_id, active_trip_id)

        if result['success']:
            # Clear active trip in database
            await APIClient.set_bot_user_active_trip(chat_id, None)

            logger.info("Trip finished successfully: chat_id=%s driver_id=%s trip_id=%s", chat_id, driver_id, active_trip_id)

            await update.message.reply_text(
                f"\U0001F3C1 *Поїздку завершено!*\n\n"
                f"\U0001F194 ID: `{escape_markdown(str(active_trip_id))}`\n\n"
                "\U0001F4B5 Дякуємо за роботу!\n"
                "\U0001F7E2 Вийдіть на лінію, щоб отримувати нові замовлення.",
                parse_mode='Markdown',
                reply_markup=driver_menu_registered(is_online=False, active_trip=False)
            )
        else:
            if DEBUGGING:
                # Clear active trip in debug mode
                await APIClient.set_bot_user_active_trip(chat_id, None)

                logger.info("[DEBUG] Mocking trip completion: chat_id=%s driver_id=%s trip_id=%s", chat_id, driver_id, active_trip_id)
                
                await update.message.reply_text(
                    "\u26A0\uFE0F *Режим налагодження*\n\n"
                    f"\U0001F3C1 Поїздку {escape_markdown(str(active_trip_id))} завершено",
                    parse_mode='Markdown',
                    reply_markup=driver_menu_registered(is_online=False, active_trip=False)
                )
            else:
                error_obj = result.get('error') if isinstance(result, dict) else None
                if isinstance(error_obj, dict):
                    error_msg = error_obj.get('message') or 'Невідома помилка'
                    status_code = error_obj.get('status_code', 500)
                elif isinstance(error_obj, str) and error_obj:
                    error_msg = error_obj
                    status_code = 500
                else:
                    error_msg = 'Невідома помилка'
                    status_code = 500
                
                logger.error("Failed to finish trip: chat_id=%s driver_id=%s trip_id=%s error=%s status=%d", 
                           chat_id, driver_id, active_trip_id, error_msg, status_code)
                
                await update.message.reply_text(
                    f"\u274C *Помилка*\n\n"
                    f"{escape_markdown(str(error_msg))}\n\n"
                    "Спробуйте ще раз пізніше.",
                    parse_mode='Markdown',
                    reply_markup=driver_menu_registered(is_online=False, active_trip=True)
                )
    
    async def decline_trip(update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()

        trip_id = query.data.replace('decline_trip_', '')
        chat_id = query.message.chat.id

        # Get driver info from database
        result = await APIClient.get_bot_user(chat_id)
        if not result['success'] or not result['data'].get('driver_id'):
            logger.warning("Decline trip attempted by unregistered driver: chat_id=%s trip_id=%s", chat_id, trip_id)
            await query.edit_message_text(
                text="\u274C Ви не зареєстровані як водій.",
                parse_mode='Markdown'
            )
            return

        bot_user = result['data']
        driver_id = bot_user.get('driver_id')
        
        logger.info("Driver declining trip: chat_id=%s driver_id=%s trip_id=%s", chat_id, driver_id, trip_id)
        
        # Show processing state
        await query.edit_message_text(
            text=f"\u23F3 Відхиляємо замовлення {escape_markdown(str(trip_id))}...",
            parse_mode='Markdown'
        )
        
        # Call Driver Service
        result = await send_trip_response(driver_id, trip_id, 'reject')
        
        if result['success']:
            logger.info("Trip declined successfully: chat_id=%s driver_id=%s trip_id=%s", chat_id, driver_id, trip_id)
            await query.edit_message_text(
                text=(
                    f"\u274C *Замовлення відхилено*\n\n"
                    f"\U0001F194 ID: `{escape_markdown(str(trip_id))}`\n\n"
                    "Ви можете переглянути інші замовлення."
                ),
                parse_mode='Markdown'
            )
        else:
            if DEBUGGING:
                logger.info("[DEBUG] Mocking trip rejection: chat_id=%s driver_id=%s trip_id=%s", chat_id, driver_id, trip_id)
                await query.edit_message_text(
                    text=(
                        "\u26A0\uFE0F *Режим налагодження*\n\n"
                        f"\u274C Замовлення {escape_markdown(str(trip_id))} відхилено"
                    ),
                    parse_mode='Markdown'
                )
            else:
                error_obj = result.get('error') if isinstance(result, dict) else None
                if isinstance(error_obj, dict):
                    error_msg = error_obj.get('message') or 'Невідома помилка'
                    status_code = error_obj.get('status_code', 500)
                elif isinstance(error_obj, str) and error_obj:
                    error_msg = error_obj
                    status_code = 500
                else:
                    error_msg = 'Невідома помилка'
                    status_code = 500
                
                logger.error("Failed to decline trip: chat_id=%s driver_id=%s trip_id=%s error=%s status=%d", 
                           chat_id, driver_id, trip_id, error_msg, status_code)
                
                # Specific message for expired trips
                if status_code == 410:
                    await query.edit_message_text(
                        text=(
                            f"\u23F0 *Замовлення недоступне*\n\n"
                            f"\U0001F194 ID: `{escape_markdown(str(trip_id))}`\n\n"
                            "Це замовлення вже оброблене або закінчився час очікування."
                        ),
                        parse_mode='Markdown'
                    )
                elif status_code == 404:
                    await query.edit_message_text(
                        text=(
                            f"\u274C *Замовлення не знайдено*\n\n"
                            f"\U0001F194 ID: `{escape_markdown(str(trip_id))}`\n\n"
                            "Можливо, замовлення було скасовано."
                        ),
                        parse_mode='Markdown'
                    )
                else:
                    await query.edit_message_text(
                        text=(
                            f"\u274C *Помилка*\n\n"
                            f"{escape_markdown(str(error_msg))}\n\n"
                            "Спробуйте ще раз пізніше."
                        ),
                        parse_mode='Markdown'
                    )

    # Expose inner handlers to module-level so tests can invoke them directly.
    # They close over the `user_orders` and `user_roles` passed to `register_handlers`.
    globals()['process_driver_car_handler'] = process_driver_car
    globals()['process_driver_name_handler'] = process_driver_name
    globals()['start_registration_handler'] = start_registration
    globals()['go_online_handler'] = go_online
    globals()['go_offline_handler'] = go_offline
    globals()['show_driver_status_handler'] = show_driver_status
    globals()['show_driver_orders_handler'] = show_driver_orders
    globals()['accept_trip_handler'] = accept_trip
    globals()['decline_trip_handler'] = decline_trip
    globals()['finish_trip_handler'] = finish_trip_handler

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
    application.add_handler(MessageHandler(filters.Regex(f"^{re.escape(BTN_FINISH_TRIP)}$"), finish_trip_handler))
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
