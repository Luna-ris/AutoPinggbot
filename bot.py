import os
import json
import logging
from telethon.sync import TelegramClient
from telethon.sessions import StringSession
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
STATE_API_ID, STATE_API_HASH, STATE_PHONE, STATE_CODE, STATE_PASSWORD, STATE_BOT_TOKEN = range(6)

CONFIG_FILE = "config.json"
load_dotenv()

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    return {}

def save_config(config):
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=4)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Привет! Используйте /setup для настройки бота.")
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
    try:
        client = TelegramClient(StringSession(), api_id, api_hash)
        await client.connect()
        await client.send_code_request(phone)
        context.user_data['client'] = client
        await update.message.reply_text("Введите код из Telegram:")
        return STATE_CODE
    except Exception as e:
        logger.error(f"Ошибка при отправке кода: {e}")
        await update.message.reply_text("Ошибка при отправке кода. Попробуйте снова с /setup.")
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
    client: TelegramClient = context.user_data['client']

    try:
        await client.sign_in(phone=phone, code=code, password=password)
        session_string = client.session.save()
        context.user_data['session_string'] = session_string
        await client.disconnect()
        await update.message.reply_text("Введите BOT_TOKEN от @BotFather:")
        return STATE_BOT_TOKEN
    except Exception as e:
        logger.error(f"Ошибка авторизации: {e}")
        await update.message.reply_text("Ошибка авторизации. Попробуйте снова с /setup.")
        return ConversationHandler.END

async def get_bot_token(update: Update, context: ContextTypes.DEFAULT_TYPE):
    bot_token = update.message.text
    config = {
        "API_ID": context.user_data['api_id'],
        "API_HASH": context.user_data['api_hash'],
        "SESSION_STRING": context.user_data['session_string'],
        "BOT_TOKEN": bot_token
    }
    save_config(config)
    await update.message.reply_text("Настройка завершена! Бот готов к работе.")
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Настройка отменена.")
    return ConversationHandler.END

async def reconfigure(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("Перенастройка начата. Введите /setup.")
    return ConversationHandler.END

async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("Состояние сброшено. Введите /setup для начала.")
    return ConversationHandler.END

def main():
    config = load_config()
    api_id = config.get("API_ID", os.getenv("API_ID"))
    api_hash = config.get("API_HASH", os.getenv("API_HASH"))
    session_string = config.get("SESSION_STRING", os.getenv("SESSION_STRING"))
    bot_token = config.get("BOT_TOKEN", os.getenv("BOT_TOKEN"))

    application = Application.builder().token(bot_token or "dummy_token").build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("setup", setup)],
        states={
            STATE_API_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_api_id)],
            STATE_API_HASH: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_api_hash)],
            STATE_PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_phone)],
            STATE_CODE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_code)],
            STATE_PASSWORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_password)],
            STATE_BOT_TOKEN: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_bot_token)],
        },
        fallbacks=[
            CommandHandler("cancel", cancel),
            CommandHandler("reset", reset),
        ],
    )

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("reconfigure", reconfigure))
    application.add_handler(conv_handler)

    application.run_polling()

if __name__ == "__main__":
    main()
