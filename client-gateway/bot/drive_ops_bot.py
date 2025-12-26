import os
import sys
import logging
import telebot
from telebot import types
from dotenv import load_dotenv

# Ensure basic logging configured
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

# Завантажуємо змінні з файлу .env
load_dotenv()
BOT_TOKEN = os.getenv('BOT_TOKEN')

# Fail fast with a clear message if BOT_TOKEN is not set
if not BOT_TOKEN:
    logging.error("BOT_TOKEN is not set in the environment or .env file. Please set BOT_TOKEN and restart the bot.")
    sys.exit("ERROR: BOT_TOKEN is not configured. Please set BOT_TOKEN in the environment or in the .env file.")

# Initialize bot only after validation
bot = telebot.TeleBot(BOT_TOKEN)

# Тимчасове сховище для замовлень (у пам'яті)
user_orders = {}

# --- Клавіатури ---

def main_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    btn_order = types.KeyboardButton("🚕 Замовити таксі")
    btn_rates = types.KeyboardButton("💰 Тарифи")
    markup.add(btn_order, btn_rates)
    return markup

def skip_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    markup.add(types.KeyboardButton("⏩ Пропустити"))
    return markup

# --- Валідатори (Заготовки) ---

def is_valid_address(address):
    """
    Заглушка для валідації адреси. 
    Поки що просто перевіряємо довжину (мінімум 5 символів).
    """
    return address is not None and len(address) > 5

# Helper wrappers for safe bot operations
def safe_send(chat_id, text, **kwargs):
    """Send a message and catch/log exceptions. Returns Message or None."""
    try:
        return bot.send_message(chat_id, text, **kwargs)
    except Exception as e:
        logging.exception("Failed to send message to %s: %s", chat_id, e)
        try:
            # best-effort notify minimal fallback
            bot.send_message(chat_id, "Виникла помилка при обробці вашого запиту. Спробуйте ще раз пізніше.")
        except Exception:
            logging.exception("Fallback notify failed for %s", chat_id)
        return None

def safe_edit_message_text(chat_id, message_id, text, **kwargs):
    """Edit a message and catch/log exceptions."""
    try:
        return bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=text, **kwargs)
    except Exception as e:
        logging.exception("Failed to edit message %s/%s: %s", chat_id, message_id, e)
        return None

# Shared helper to reduce duplicated validation + retry logic
def validate_address_and_retry(chat_id, address, error_message, retry_handler):
    """
    Checks is_valid_address(address). If invalid, sends error_message and registers
    retry_handler as the next step for the user. Returns True when valid, False otherwise.
    """
    if is_valid_address(address):
        return True

    msg = safe_send(chat_id, error_message)
    if msg is not None:
        try:
            bot.register_next_step_handler(msg, retry_handler)
        except Exception:
            logging.exception("Failed to register next step handler for %s", chat_id)
            safe_send(chat_id, "Виникла внутрішня помилка. Спробуйте ще раз.")
    return False

# --- Обробники команд ---

@bot.message_handler(commands=['start'])
def start_message(message):
    bot.send_message(
        message.chat.id,
        "Вітаємо у службі таксі! Оберіть опцію:",
        reply_markup=main_menu()
    )

@bot.message_handler(func=lambda message: message.text == "💰 Тарифи")
def show_rates(message):
    bot.send_message(message.chat.id, "🚕 Тариф 'Стандарт': 15 грн/км\n🏢 Тариф 'Комфорт': 25 грн/км")

# New: command to cancel an in-progress order
@bot.message_handler(commands=['cancel_order'])
def cancel_order_command(message):
    chat_id = message.chat.id
    if chat_id in user_orders:
        user_orders.pop(chat_id, None)
        safe_send(chat_id, "❌ Ваше незавершене замовлення скасовано. Повернулись до головного меню.", reply_markup=main_menu())
    else:
        safe_send(chat_id, "У вас немає активного незавершеного замовлення.", reply_markup=main_menu())

# --- Логіка замовлення (Trip Request Form) ---

@bot.message_handler(func=lambda message: message.text == "🚕 Замовити таксі")
def start_order(message):
    chat_id = message.chat.id

    # Prevent duplicate in-progress orders
    if chat_id in user_orders and user_orders[chat_id].get('_in_progress'):
        safe_send(chat_id, "У вас вже є незавершене замовлення. Скасуйте його командою /cancel_order або завершіть поточне замовлення.")
        return

    # Ініціалізуємо дані замовлення
    user_orders[chat_id] = {'pickup': None, 'dropoff': None, 'comment': None, '_in_progress': True}
    
    msg = bot.send_message(
        chat_id, 
        "📍 **Крок 1/3**: Введіть адресу відправлення (напр. вул. Хрещатик, 1):",
        parse_mode='Markdown',
        reply_markup=types.ReplyKeyboardRemove() # Ховаємо головне меню
    )
    bot.register_next_step_handler(msg, process_pickup_step)

def process_pickup_step(message):
    chat_id = message.chat.id
    address = message.text

    # Use shared helper for validation + retry registration
    if not validate_address_and_retry(chat_id, address, "❌ Адреса занадто коротка або некоректна. Спробуйте ще раз:", process_pickup_step):
        return

    user_orders[chat_id]['pickup'] = address
    msg = bot.send_message(chat_id, "🏁 **Крок 2/3**: Куди їдемо? (Введіть адресу призначення):", parse_mode='Markdown')
    bot.register_next_step_handler(msg, process_dropoff_step)

def process_dropoff_step(message):
    chat_id = message.chat.id
    address = message.text

    # Use shared helper for validation + retry registration
    if not validate_address_and_retry(chat_id, address, "❌ Будь ласка, вкажіть повну адресу призначення:", process_dropoff_step):
        return

    user_orders[chat_id]['dropoff'] = address
    msg = bot.send_message(
        chat_id, 
        "💬 **Крок 3/3**: Додайте коментар (під'їзд, дитяче крісло тощо) або натисніть кнопку нижче:", 
        reply_markup=skip_menu(),
        parse_mode='Markdown'
    )
    bot.register_next_step_handler(msg, process_comment_step)

def process_comment_step(message):
    chat_id = message.chat.id
    
    # Обробка опціонального поля
    if message.text == "⏩ Пропустити":
        user_orders[chat_id]['comment'] = "Не вказано"
    else:
        user_orders[chat_id]['comment'] = message.text

    # Вивід підсумку (Summary)
    order = user_orders[chat_id]
    summary = (
        f"🚕 **Підтвердження замовлення**\n\n"
        f"📍 **Звідки:** {order['pickup']}\n"
        f"🏁 **Куди:** {order['dropoff']}\n"
        f"💬 **Коментар:** {order['comment']}\n\n"
        f"💰 *Вартість буде розрахована після підтвердження.*"
    )

    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("✅ Підтвердити", callback_data="order_confirm"),
        types.InlineKeyboardButton("❌ Скасувати", callback_data="order_cancel")
    )
    
    bot.send_message(chat_id, summary, parse_mode='Markdown', reply_markup=markup)

# --- Обробка кнопок підтвердження ---

@bot.callback_query_handler(func=lambda call: call.data.startswith('order_'))
def handle_order_status(call):
    # Acknowledge callback immediately to stop Telegram spinner
    try:
        bot.answer_callback_query(call.id)
    except Exception:
        # best-effort; ignore failures to acknowledge
        pass

    try:
        if call.data == "order_confirm":
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text="✅ **Замовлення прийнято!**\nШукаємо найближче авто...",
                parse_mode='Markdown'
            )
        elif call.data == "order_cancel":
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text="❌ **Замовлення скасовано.**"
            )
        
        # Повертаємо головне меню
        bot.send_message(call.message.chat.id, "Головне меню:", reply_markup=main_menu())
    finally:
        # Clean up in-memory order data to avoid leak
        user_orders.pop(call.message.chat.id, None)

if __name__ == "__main__":
    print("Бот запущений...")
    bot.infinity_polling()
