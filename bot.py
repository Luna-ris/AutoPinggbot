from telethon import TelegramClient, events
from telethon.sessions import StringSession
from telegram import Bot
import os
import re
import json
import asyncio
import logging
from dotenv import load_dotenv
from telethon.errors.rpcerrorlist import FloodWaitError, SessionPasswordNeededError

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Загрузка конфигурации
load_dotenv()
API_ID = os.getenv("API_ID")
API_HASH = os.getenv("API_HASH")
PHONE = os.getenv("PHONE")
BOT_TOKEN = os.getenv("BOT_TOKEN")
SESSION_STRING = os.getenv("SESSION_STRING")  # Строка сессии из переменной окружения

# Проверка обязательных переменных
if not all([API_ID, API_HASH, PHONE, BOT_TOKEN, SESSION_STRING]):
    missing = [k for k, v in {"API_ID": API_ID, "API_HASH": API_HASH, "PHONE": PHONE, "BOT_TOKEN": BOT_TOKEN, "SESSION_STRING": SESSION_STRING}.items() if not v]
    logger.error(f"Отсутствуют переменные окружения: {', '.join(missing)}")
    raise ValueError(f"Необходимо указать все переменные окружения: {', '.join(missing)}")

# Инициализация клиента и бота
client = TelegramClient(StringSession(SESSION_STRING), int(API_ID), API_HASH)
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
                logger.warning(f"Flood wait error: need to wait {e.seconds} seconds")
                await asyncio.sleep(e.seconds)
                await bot.send_message(chat_id=config["user_id"], text=notification)
            except Exception as e:
                logger.error(f"Ошибка отправки уведомления: {e}")

async def main():
    while True:
        try:
            await client.start(phone=PHONE)
            logger.info("Клиент успешно авторизован")
            break
        except FloodWaitError as e:
            logger.warning(f"Flood wait error: need to wait {e.seconds} seconds")
            await asyncio.sleep(e.seconds)
        except SessionPasswordNeededError:
            logger.error("Требуется пароль для двухфакторной аутентификации, но он не поддерживается в этой версии")
            raise
        except Exception as e:
            logger.error(f"Ошибка авторизации: {e}")
            raise
    await handle_commands()
    logger.info("Клиент запущен...")
    await client.run_until_disconnected()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}")
        raise
