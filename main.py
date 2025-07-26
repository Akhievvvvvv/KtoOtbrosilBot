import logging
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils import executor
from aiogram.dispatcher import FSMContext
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher.filters.state import State, StatesGroup
from datetime import datetime

from config import BOT_TOKEN, GROUP_CHAT_ID, MESSAGES, BUTTONS

logging.basicConfig(level=logging.INFO)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot, storage=MemoryStorage())

# Состояние для ожидания анонимного сообщения
class MessageState(StatesGroup):
    writing = State()

# Хранилище сообщений и их отправителей
user_messages = {}

@dp.message_handler(commands=['start'])
async def start_command(message: types.Message):
    user_id = message.from_user.id
    name = message.from_user.first_name
    bot_username = (await bot.get_me()).username

    msg = MESSAGES["start"].format(
        name=name,
        user_id=user_id,
        bot_username=bot_username
    )
    await message.answer(msg)

@dp.message_handler(lambda m: m.text and m.text.startswith("/start ") and len(m.text.split()) == 2)
async def referral_link(message: types.Message):
    recipient_id = int(message.text.split()[1])
    if recipient_id == message.from_user.id:
        return await message.answer("❗ Нельзя отправить сообщение самому себе.")
    await message.answer(MESSAGES["write_message"])
    await MessageState.writing.set()
    state = dp.current_state(user=message.from_user.id)
    await state.update_data(recipient_id=recipient_id)

@dp.message_handler(state=MessageState.writing, content_types=types.ContentTypes.TEXT)
async def handle_anonymous_message(message: types.Message, state: FSMContext):
    data = await state.get_data()
    recipient_id = data.get("recipient_id")
    sender_id = message.from_user.id
    msg_text = message.text

    # Клавиатура с кнопками
    keyboard = InlineKeyboardMarkup().add(
        InlineKeyboardButton(BUTTONS["reveal_sender"], callback_data=f"reveal_{sender_id}"),
        InlineKeyboardButton(BUTTONS["payment_done"], callback_data=f"paid_{sender_id}")
    )

    # Отправка сообщения в группу
    sent_msg = await bot.send_message(
        GROUP_CHAT_ID,
        MESSAGES["new_anonymous"].format(msg_text),
        reply_markup=keyboard
    )

    user_messages[sent_msg.message_id] = sender_id

    await message.answer(MESSAGES["message_sent"])
    await state.finish()

@dp.callback_query_handler(lambda c: c.data.startswith("paid_"))
async def handle_payment_submission(callback: types.CallbackQuery):
    sender_id = int(callback.data.split("_")[1])
    username = callback.from_user.username or f"id{callback.from_user.id}"
    msg_id = callback.message.message_id
    time_str = datetime.now().strftime("%d.%m.%Y %H:%M")

    text = MESSAGES["admin_payment_request"].format(
        username=username,
        time=time_str,
        msg_id=msg_id
    )

    keyboard = InlineKeyboardMarkup().add(
        InlineKeyboardButton(BUTTONS["approve_payment"], callback_data=f"approve_{msg_id}")
    )

    await bot.send_message(GROUP_CHAT_ID, text, reply_markup=keyboard)
    await callback.message.edit_reply_markup()
    await callback.answer(MESSAGES["payment_submitted"])

@dp.callback_query_handler(lambda c: c.data.startswith("approve_"))
async def handle_admin_approval(callback: types.CallbackQuery):
    msg_id = int(callback.data.split("_")[1])
    sender_id = user_messages.get(msg_id)

    if sender_id:
        user = await bot.get_chat(sender_id)
        sender_username = user.username or f"id{sender_id}"
        await bot.send_message(GROUP_CHAT_ID, MESSAGES["sender_revealed"].format(username=sender_username))
        await callback.answer(MESSAGES["payment_approved"])
    else:
        await callback.answer(MESSAGES["sender_not_found"], show_alert=True)
