from telethon import TelegramClient
from telethon.sessions import StringSession
import os
from dotenv import load_dotenv

# Загрузка конфигурации
load_dotenv()
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
PHONE = os.getenv("PHONE")

# Инициализация клиента
client = TelegramClient(StringSession(), API_ID, API_HASH)

async def main():
    await client.start(phone=PHONE)
    print(f"Строка сессии: {client.session.save()}")

import asyncio
asyncio.run(main())
