import os
import telebot
from telebot import types
from dotenv import load_dotenv

# Завантажуємо змінні з файлу .env
load_dotenv()
BOT_TOKEN = os.getenv('BOT_TOKEN')

bot = telebot.TeleBot(BOT_TOKEN)

# Функція для створення головного меню
def main_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    btn_order = types.KeyboardButton("🚕 Замовити таксі")
    btn_rates = types.KeyboardButton("💰 Тарифи")
    markup.add(btn_order, btn_rates)
    return markup

@bot.message_handler(commands=['start'])
def start_message(message):
    bot.send_message(
        message.chat.id, 
        "Вітаємо у службі таксі! Оберіть опцію:", 
        reply_markup=main_menu()
    )

@bot.message_handler(func=lambda message: True)
def handle_text(message):
    if message.text == "🚕 Замовити таксі":
        bot.send_message(message.chat.id, "Шукаємо вільне авто... (кнопка поки неактивна)")
    elif message.text == "💰 Тарифи":
        bot.send_message(message.chat.id, "Тариф 'Стандарт': 15 грн/км")
    else:
        bot.send_message(message.chat.id, "Будь ласка, оберіть пункт з меню.")

if __name__ == "__main__":
    print("Бот запущений...")
    bot.infinity_polling()
