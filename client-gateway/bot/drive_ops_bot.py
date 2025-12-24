import os
import telebot
from telebot import types
from dotenv import load_dotenv

# Завантажуємо змінні з файлу .env
load_dotenv()
BOT_TOKEN = os.getenv('BOT_TOKEN')

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

# --- Логіка замовлення (Trip Request Form) ---

@bot.message_handler(func=lambda message: message.text == "🚕 Замовити таксі")
def start_order(message):
    chat_id = message.chat.id
    # Ініціалізуємо дані замовлення
    user_orders[chat_id] = {'pickup': None, 'dropoff': None, 'comment': None}
    
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

    # Валідація Mandatory field
    if not is_valid_address(address):
        msg = bot.send_message(chat_id, "❌ Адреса занадто коротка або некоректна. Спробуйте ще раз:")
        bot.register_next_step_handler(msg, process_pickup_step)
        return

    user_orders[chat_id]['pickup'] = address
    msg = bot.send_message(chat_id, "🏁 **Крок 2/3**: Куди їдемо? (Введіть адресу призначення):", parse_mode='Markdown')
    bot.register_next_step_handler(msg, process_dropoff_step)

def process_dropoff_step(message):
    chat_id = message.chat.id
    address = message.text

    # Валідація Mandatory field
    if not is_valid_address(address):
        msg = bot.send_message(chat_id, "❌ Будь ласка, вкажіть повну адресу призначення:")
        bot.register_next_step_handler(msg, process_dropoff_step)
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

if __name__ == "__main__":
    print("Бот запущений...")
    bot.infinity_polling()
