import os
import json
import logging
from telethon.sync import TelegramClient
from telethon.sessions import StringSession
from telethon.events import NewMessage
from telegram import Update
from telegram.ext import (
    Application, CommandHandler, ConversationHandler, MessageHandler,
    filters, ContextTypes
)
from dotenv import load_dotenv

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Состояния
STATE_API_ID, STATE_API_HASH, STATE_PHONE, STATE_CODE, STATE_PASSWORD, STATE_BOT_TOKEN, STATE_ADD_USER, STATE_REMOVE_USER = range(8)

CONFIG_FILE = "config.json"
TRACKED_USERS_FILE = "tracked_users.json"
load_dotenv()

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    return {}

def save_config(config):
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=4)

def load_tracked_users():
    if os.path.exists(TRACKED_USERS_FILE):
        with open(TRACKED_USERS_FILE, 'r') as f:
            return json.load(f)
    return []

def save_tracked_users(users):
    with open(TRACKED_USERS_FILE, 'w') as f:
        json.dump(users, f, indent=4)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    config = load_config()
    if not all(key in config for key in ["API_ID", "API_HASH", "SESSION_STRING", "BOT_TOKEN"]):
        await update.message.reply_text("Бот не настроен. Используйте /setup для настройки.")
        return ConversationHandler.END
    await update.message.reply_text("Привет! Бот готов к работе. Используйте /adduser для добавления пользователей или /setup для перенастройки.")
    return ConversationHandler.END

async def setup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    config = load_config()
    if all(key in config for key in ["API_ID", "API_HASH", "SESSION_STRING", "BOT_TOKEN"]):
        await update.message.reply_text("Бот уже настроен. Для перенастройки используйте /reconfigure.")
        return ConversationHandler.END
    await update.message.reply_text("Введите API_ID:")
    return STATE_API_ID

async def get_api_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_input = update.message.text.strip()
    if not user_input.isdigit():
        await update.message.reply_text("API_ID должен быть числом. Попробуйте снова:")
        return STATE_API_ID
    context.user_data['api_id'] = user_input
    await update.message.reply_text("Введите API_HASH:")
    return STATE_API_HASH

async def get_api_hash(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['api_hash'] = update.message.text
    await update.message.reply_text("Введите номер телефона (например, +1234567890):")
    return STATE_PHONE

async def get_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    phone = update.message.text.strip()
    context.user_data['phone'] = phone
    api_id = int(context.user_data['api_id'])
    api_hash = context.user_data['api_hash']
    client = TelegramClient(StringSession(), api_id, api_hash)
    try:
        await client.connect()
        sent_code = await client.send_code_request(phone)
        context.user_data['client'] = client
        context.user_data['phone_code_hash'] = sent_code.phone_code_hash
        await update.message.reply_text("Введите код из Telegram:")
        return STATE_CODE
    except Exception as e:
        logger.error(f"Ошибка при отправке кода: {e}")
        await update.message.reply_text("Ошибка при отправке кода. Попробуйте снова с /setup.")
        await client.disconnect()
        return ConversationHandler.END

async def get_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['code'] = update.message.text.strip()
    await update.message.reply_text("Если включена 2FA, введите пароль. Если нет, напишите 'нет':")
    return STATE_PASSWORD

async def get_password(update: Update, context: ContextTypes.DEFAULT_TYPE):
    password = update.message.text if update.message.text.lower() != 'нет' else None
    api_id = int(context.user_data['api_id'])
    api_hash = context.user_data['api_hash']
    phone = context.user_data['phone']
    code = context.user_data['code']
    phone_code_hash = context.user_data['phone_code_hash']
    client: TelegramClient = context.user_data['client']

    try:
        await client.sign_in(phone=phone, code=code, phone_code_hash=phone_code_hash, password=password)
        session_string = client.session.save()
        context.user_data['session_string'] = session_string
        await update.message.reply_text("Введите BOT_TOKEN от @BotFather:")
        return STATE_BOT_TOKEN
    except Exception as e:
        logger.error(f"Ошибка авторизации: {e}")
        await update.message.reply_text(f"Ошибка авторизации: {str(e)}. Попробуйте снова с /setup.")
        await client.disconnect()
        return ConversationHandler.END
    finally:
        await client.disconnect()

async def get_bot_token(update: Update, context: ContextTypes.DEFAULT_TYPE):
    bot_token = update.message.text.strip()
    config = {
        "API_ID": context.user_data['api_id'],
        "API_HASH": context.user_data['api_hash'],
        "SESSION_STRING": context.user_data['session_string'],
        "BOT_TOKEN": bot_token,
        "ADMIN_ID": str(update.message.from_user.id)
    }
    save_config(config)
    await update.message.reply_text("Настройка завершена! Бот готов к работе.")
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if 'client' in context.user_data:
        await context.user_data['client'].disconnect()
    context.user_data.clear()
    await update.message.reply_text("Настройка отменена.")
    return ConversationHandler.END

async def reconfigure(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if 'client' in context.user_data:
        await context.user_data['client'].disconnect()
    context.user_data.clear()
    await update.message.reply_text("Перенастройка начата. Введите /setup.")
    return ConversationHandler.END

async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if 'client' in context.user_data:
        await context.user_data['client'].disconnect()
    context.user_data.clear()
    await update.message.reply_text("Состояние сброшено. Введите /setup для начала.")
    return ConversationHandler.END

async def add_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    config = load_config()
    if str(update.message.from_user.id) != config.get("ADMIN_ID"):
        await update.message.reply_text("Только администратор может добавлять пользователей.")
        return ConversationHandler.END
    await update.message.reply_text("Введите имя пользователя для добавления (с @):")
    return STATE_ADD_USER

async def get_user_to_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    username = update.message.text.strip()
    if not username.startswith('@'):
        username = f"@{username}"
    tracked_users = load_tracked_users()
    if username not in tracked_users:
        tracked_users.append(username)
        save_tracked_users(tracked_users)
        await update.message.reply_text(f"Пользователь {username} добавлен в список отслеживания.")
    else:
        await update.message.reply_text(f"Пользователь {username} уже в списке отслеживания.")
    return ConversationHandler.END

async def remove_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    config = load_config()
    if str(update.message.from_user.id) != config.get("ADMIN_ID"):
        await update.message.reply_text("Только администратор может удалять пользователей.")
        return ConversationHandler.END
    await update.message.reply_text("Введите имя пользователя для удаления (с @):")
    return STATE_REMOVE_USER

async def get_user_to_remove(update: Update, context: ContextTypes.DEFAULT_TYPE):
    username = update.message.text.strip()
    if not username.startswith('@'):
        username = f"@{username}"
    tracked_users = load_tracked_users()
    if username in tracked_users:
        tracked_users.remove(username)
        save_tracked_users(tracked_users)
        await update.message.reply_text(f"Пользователь {username} удален из списка отслеживания.")
    else:
        await update.message.reply_text(f"Пользователь {username} не найден в списке отслеживания.")
    return ConversationHandler.END

async def handle_new_message(event, bot, admin_id):
    tracked_users = load_tracked_users()
    message_text = event.raw_text.lower()
    
    for user in tracked_users:
        if user.lower() in message_text:
            try:
                chat = await event.get_chat()
                message_link = f"https://t.me/c/{str(chat.id).replace('-100', '')}/{event.message.id}"
                await bot.send_message(
                    chat_id=admin_id,
                    text=f"Пользователь {user} был упомянут в сообщении: {message_link}"
                )
            except Exception as e:
                logger.error(f"Ошибка при отправке уведомления: {e}")

async def main():
    config = load_config()
    api_id = config.get("API_ID")
    api_hash = config.get("API_HASH")
    session_string = config.get("SESSION_STRING")
    bot_token = config.get("BOT_TOKEN")
    admin_id = config.get("ADMIN_ID")

    # Если конфигурация не заполнена, просто логируем и выходим
    if not all([api_id, api_hash, bot_token, session_string]):
        logger.info("Конфигурация не заполнена, бот ожидает команды /setup")
        return

    application = None
    try:
        # Инициализация бота только с валидным токеном
        application = Application.builder().token(bot_token).build()

        # Добавление обработчиков команд
        conv_handler = ConversationHandler(
            entry_points=[
                CommandHandler("setup", setup),
                CommandHandler("adduser", add_user),
                CommandHandler("removeuser", remove_user),
            ],
            states={
                STATE_API_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_api_id)],
                STATE_API_HASH: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_api_hash)],
                STATE_PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_phone)],
                STATE_CODE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_code)],
                STATE_PASSWORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_password)],
                STATE_BOT_TOKEN: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_bot_token)],
                STATE_ADD_USER: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_user_to_add)],
                STATE_REMOVE_USER: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_user_to_remove)],
            },
            fallbacks=[
                CommandHandler("cancel", cancel),
                CommandHandler("reset", reset),
            ],
        )

        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("reconfigure", reconfigure))
        application.add_handler(conv_handler)

        # Инициализация клиента Telethon
        client = TelegramClient(StringSession(session_string), int(api_id), api_hash)

        # Регистрация обработчика сообщений
        @client.on(NewMessage)
        async def handler(event):
            await handle_new_message(event, application.bot, admin_id)

        # Запуск клиента и бота
        async with client:
            await client.start()
            await application.initialize()
            await application.start()
            await application.updater.start_polling()
            await client.run_until_disconnected()

    except Exception as e:
        logger.error(f"Ошибка в главном цикле: {e}")
        if admin_id and application:
            await application.bot.send_message(
                chat_id=admin_id,
                text=f"Произошла ошибка при запуске бота: {str(e)}"
            )
    finally:
        if application:
            await application.stop()
            await application.shutdown()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
