import os
import json
import logging
from telethon.sync import TelegramClient
from telethon.sessions import StringSession
from telegram import Update
from telegram.ext import Application, CommandHandler, ConversationHandler, MessageHandler, filters, ContextTypes
from dotenv import load_dotenv

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Состояния для ConversationHandler
API_ID, API_HASH, PHONE, CODE, PASSWORD, BOT_TOKEN = range(6)

# Путь для сохранения конфигурации
CONFIG_FILE = "config.json"

# Загрузка переменных окружения
load_dotenv()

# Функция для загрузки конфигурации из файла
def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    return {}

# Функция для сохранения конфигурации в файл
def save_config(config):
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=4)

# Функция для проверки и генерации сессии
async def generate_session(api_id, api_hash, phone, code, password=None):
    try:
        async with TelegramClient(StringSession(), api_id, api_hash) as client:
            await client.start(phone=phone, code_callback=lambda: code, password=password)
            session_string = client.session.save()
            return session_string
    except Exception as e:
        logger.error(f"Ошибка генерации сессии: {e}")
        return None

# Команда /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info("Start command received")
    await update.message.reply_text("Привет! Используйте /setup для настройки бота.")
    return ConversationHandler.END

# Начало настройки
async def setup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info("Setup command received")
    config = load_config()
    if all(key in config for key in ["API_ID", "API_HASH", "SESSION_STRING", "BOT_TOKEN"]):
        await update.message.reply_text("Бот уже настроен. Для перенастройки используйте /reconfigure.")
        return ConversationHandler.END  # ✅ Теперь завершаем диалог
    await update.message.reply_text("Введите API_ID:")
    return API_ID

# Обработка API_ID
async def get_api_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info("API_ID received")
    context.user_data['api_id'] = update.message.text
    await update.message.reply_text("Введите API_HASH:")
    return API_HASH

# Обработка API_HASH
async def get_api_hash(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['api_hash'] = update.message.text
    await update.message.reply_text("Введите номер телефона (например, +1234567890):")
    return PHONE

# Обработка номера телефона
async def get_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['phone'] = update.message.text
    await update.message.reply_text("Введите код авторизации, который пришел в Telegram:")
    return CODE

# Обработка кода авторизации
async def get_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['code'] = update.message.text
    await update.message.reply_text("Если включена двухфакторная аутентификация, введите пароль. Если нет, напишите 'нет':")
    return PASSWORD

# Обработка пароля (или его отсутствия)
async def get_password(update: Update, context: ContextTypes.DEFAULT_TYPE):
    password = update.message.text if update.message.text.lower() != 'нет' else None
    api_id = int(context.user_data['api_id'])
    api_hash = context.user_data['api_hash']
    phone = context.user_data['phone']
    code = context.user_data['code']

    # Генерация сессии
    session_string = await generate_session(api_id, api_hash, phone, code, password)
    if session_string:
        context.user_data['session_string'] = session_string
        await update.message.reply_text("Введите BOT_TOKEN (получите от @BotFather):")
        return BOT_TOKEN
    else:
        await update.message.reply_text("Ошибка генерации сессии. Попробуйте снова с /setup.")
        return ConversationHandler.END

# Обработка BOT_TOKEN и завершение настройки
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

# Отмена настройки
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Настройка отменена.")
    return ConversationHandler.END

# Команда /reconfigure — безопасный перезапуск
async def reconfigure(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info("Reconfigure command received")
    await update.message.reply_text("Начинаем перенастройку. Введите /setup.")
    return ConversationHandler.END

# Основная функция
def main():
    # Загрузка конфигурации
    config = load_config()

    # Проверка переменных окружения
    API_ID = config.get("API_ID", os.getenv("API_ID"))
    API_HASH = config.get("API_HASH", os.getenv("API_HASH"))
    SESSION_STRING = config.get("SESSION_STRING", os.getenv("SESSION_STRING"))
    BOT_TOKEN = config.get("BOT_TOKEN", os.getenv("BOT_TOKEN"))

    # Если данные отсутствуют, бот запустится и будет ждать команды /setup
    if not all([API_ID, API_HASH, SESSION_STRING, BOT_TOKEN]):
        logger.info("Конфигурация неполная. Запустите бота и используйте /setup.")
    else:
        logger.info("Конфигурация загружена. Запуск бота...")

    # Настройка python-telegram-bot
    application = Application.builder().token(BOT_TOKEN or "dummy_token").build()

    # Настройка ConversationHandler для процесса настройки
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("setup", setup)],
        states={
            API_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_api_id)],
            API_HASH: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_api_hash)],
            PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_phone)],
            CODE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_code)],
            PASSWORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_password)],
            BOT_TOKEN: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_bot_token)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    # Добавление обработчиков
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("reconfigure", reconfigure))  # 🆕 добавлено
    application.add_handler(conv_handler)

    # Запуск бота
    application.run_polling()

if __name__ == "__main__":
    main()
