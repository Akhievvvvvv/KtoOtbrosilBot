import logging
from aiogram import Bot, Dispatcher, executor, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import datetime
import asyncio
import config  # файл config.py должен быть в той же папке

logging.basicConfig(level=logging.INFO)

bot = Bot(token=config.BOT_TOKEN)
dp = Dispatcher(bot)

# Временное хранилище сообщений и оплат (на время работы бота)
messages = {}
payments = {}

def get_start_keyboard():
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton(config.BUTTONS["reveal_sender"], callback_data="reveal_sender"))
    return kb

def get_payment_keyboard():
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton(config.BUTTONS["payment_done"], callback_data="payment_done"))
    return kb

@dp.message_handler(commands=['start'])
async def cmd_start(message: types.Message):
    text = config.MESSAGES["start"].format(
        name=message.from_user.first_name or "пользователь",
        bot_username=(await bot.get_me()).username,
        user_id=message.from_user.id
    )
    await message.answer(text)

@dp.message_handler(commands=['write'])
async def cmd_write(message: types.Message):
    await message.answer(config.MESSAGES["write_message"])

@dp.message_handler()
async def handle_message(message: types.Message):
    # Сохраняем анонимное сообщение с ID пользователя
    messages[message.message_id] = {
        "user_id": message.from_user.id,
        "username": message.from_user.username or "без ника",
        "text": message.text,
    }
    # Отправляем в группу админу уведомление
    await bot.send_message(
        config.GROUP_CHAT_ID,
        config.MESSAGES["new_anonymous"].format(message.text),
        reply_markup=get_payment_keyboard()
    )
    await message.answer(config.MESSAGES["message_sent"])

@dp.callback_query_handler(lambda c: c.data == "payment_done")
async def payment_done_callback(callback_query: types.CallbackQuery):
    user = callback_query.from_user
    # Регистрируем заявку на оплату
    payments[user.id] = {
        "username": user.username or "без ника",
        "time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    await bot.send_message(config.GROUP_CHAT_ID,
                           config.MESSAGES["admin_payment_request"].format(
                               username=payments[user.id]["username"],
                               time=payments[user.id]["time"],
                               msg_id="сообщение"
                           ))
    await callback_query.answer(config.MESSAGES["payment_submitted"])

@dp.callback_query_handler(lambda c: c.data == "reveal_sender")
async def reveal_sender_callback(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    # Проверяем оплату
    if user_id not in payments:
        await callback_query.answer(config.MESSAGES["payment_not_found"], show_alert=True)
        return
    # На примере берём первого отправителя
    if not messages:
        await callback_query.answer(config.MESSAGES["message_not_found"], show_alert=True)
        return
    first_msg_id = next(iter(messages))
    sender = messages[first_msg_id]["username"]
    await callback_query.message.answer(config.MESSAGES["sender_revealed"].format(username=sender))
    await callback_query.answer()

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
