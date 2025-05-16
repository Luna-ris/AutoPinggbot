from telethon import TelegramClient, events
from telethon.sessions import StringSession
from telegram import Bot
import os
import re
import json
import asyncio
from dotenv import load_dotenv
from telethon.errors.rpcerrorlist import FloodWaitError

# Загрузка конфигурации
load_dotenv()
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH"))
PHONE = os.getenv("PHONE")
BOT_TOKEN = os.getenv("BOT_TOKEN")
SESSION_STRING = os.getenv("SESSION_STRING")  # Строка сессии из переменной окружения

# Инициализация клиента и бота
if SESSION_STRING:
    client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)
else:
    client = TelegramClient("session", API_ID, API_HASH)
bot = Bot(token=BOT_TOKEN)

# Хранение настроек
CONFIG_FILE = "config.json"
def save_config(config):
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f)

def load_config():
    try:
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return {"nicknames": [], "user_id": None}

# Обработчик команд
async def handle_commands():
    config = load_config()
    me = await client.get_me()

    @client.on(events.NewMessage(chats=[me.id]))
    async def handler(event):
        text = event.message.text
        user_id = event.sender_id

        if text.startswith("/start"):
            await event.reply("Введи токен бота для уведомлений.")
        elif text.startswith("/setbottoken"):
            config["bot_token"] = text.split(" ", 1)[1] if len(text.split(" ")) > 1 else ""
            save_config(config)
            await event.reply("Токен бота обновлен. Введи никнеймы для отслеживания (через запятую).")
        elif text.startswith("/setnicknames"):
            config["nicknames"] = [n.strip() for n in text.split(" ", 1)[1].split(",")] if len(text.split(" ")) > 1 else []
            config["user_id"] = user_id
            save_config(config)
            await event.reply(f"Никнеймы обновлены: {', '.join(config['nicknames'])}")
        elif text.startswith("/list"):
            await event.reply(f"Никнеймы: {', '.join(config['nicknames'])}\nУведомления для: {config['user_id']}")
        elif text.startswith("/stop"):
            config = {"nicknames": [], "user_id": None}
            save_config(config)
            await event.reply("Отслеживание остановлено.")

# Обработчик сообщений
@client.on(events.NewMessage)
@client.on(events.MessageEdited)
async def handle_messages(event):
    config = load_config()
    if not config["nicknames"] or not config["user_id"]:
        return

    message = event.message
    if not message.text:
        return

    chat = await event.get_chat()
    chat_title = getattr(chat, "title", "Unknown Chat")
    chat_id = event.chat_id
    message_id = event.message_id
    is_edited = event.is_edited
    message_text = message.text

    for nickname in config["nicknames"]:
        pattern = rf"(?:@?){re.escape(nickname.lstrip('@'))}\b"
        if re.search(pattern, message_text, re.IGNORECASE):
            notification = (
                f"{'[Edited] ' if is_edited else ''}Упоминание в группе '{chat_title}' (@{chat.username if hasattr(chat, 'username') else chat_id}):\n"
                f"{message_text}\n"
                f"Ссылка: t.me/c/{str(chat_id).replace('-100', '')}/{message_id}\n"
                f"Время: {event.date.strftime('%Y-%m-%d %H:%M:%S %Z')}"
            )
            try:
                await bot.send_message(chat_id=config["user_id"], text=notification)
            except FloodWaitError as e:
                print(f"Flood wait error: need to wait {e.seconds} seconds")
                await asyncio.sleep(e.seconds)
                await bot.send_message(chat_id=config["user_id"], text=notification)

async def main():
    while True:
        try:
            await client.start(phone=PHONE)
            if not SESSION_STRING:
                # Сохранить строку сессии после авторизации (для локального тестирования)
                session_string = client.session.save()
                print(f"Строка сессии: {session_string}")
                print("Сохраните эту строку в переменной окружения SESSION_STRING")
            break
        except FloodWaitError as e:
            print(f"Flood wait error: need to wait {e.seconds} seconds")
            await asyncio.sleep(e.seconds)
    await handle_commands()
    print("Клиент запущен...")
    await client.run_until_disconnected()

if __name__ == "__main__":
    asyncio.run(main())
