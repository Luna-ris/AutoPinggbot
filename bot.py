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
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Состояния
STATE_API_ID, STATE_API_HASH, STATE_PHONE, STATE_CODE, STATE_PASSWORD, STATE_BOT_TOKEN, STATE_ADD_USER, STATE_REMOVE_USER = range(8)

CONFIG_FILE = "config.json"
TRACKED_USERS_FILE = "tracked_users.json"
load_dotenv()

def load_config():
    logger.debug("Попытка загрузки конфигурации из %s", CONFIG_FILE)
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                config = json.load(f)
                logger.debug("Конфигурация загружена: %s", config)
                return config
        except Exception as e:
            logger.error("Ошибка при загрузке конфигурации: %s", e)
    return {}

def save_config(config):
    logger.debug("Сохранение конфигурации: %s", config)
    try:
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=4)
        logger.info("Конфигурация сохранена в %s", CONFIG_FILE)
    except Exception as e:
        logger.error("Ошибка при сохранении конфигурации: %s", e)

def load_tracked_users():
    logger.debug("Попытка загрузки отслеживаемых пользователей из %s", TRACKED_USERS_FILE)
    if os.path.exists(TRACKED_USERS_FILE):
        try:
            with open(TRACKED_USERS_FILE, 'r') as f:
                users = json.load(f)
                logger.debug("Отслеживаемые пользователи: %s", users)
                return users
        except Exception as e:
            logger.error("Ошибка при загрузке отслеживаемых пользователей: %s", e)
    return []

def save_tracked_users(users):
    logger.debug("Сохранение отслеживаемых пользователей: %s", users)
    try:
        with open(TRACKED_USERS_FILE, 'w') as f:
            json.dump(users, f, indent=4)
        logger.info("Отслеживаемые пользователи сохранены в %s", TRACKED_USERS_FILE)
    except Exception as e:
        logger.error("Ошибка при сохранении отслеживаемых пользователей: %s", e)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info("Команда /start вызвана пользователем %s", update.message.from_user.id)
    config = load_config()
    if not all(key in config for key in ["API_ID", "API_HASH", "SESSION_STRING", "BOT_TOKEN"]):
        await update.message.reply_text("Бот не настроен. Используйте /setup для настройки.")
        return ConversationHandler.END
    await update.message.reply_text("Привет! Бот готов к работе. Используйте /adduser для добавления пользователей или /setup для перенастройки.")
    return ConversationHandler.END

async def setup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info("Команда /setup вызвана пользователем %s", update.message.from_user.id)
    config = load_config()
    if all(key in config for key in ["API_ID", "API_HASH", "SESSION_STRING", "BOT_TOKEN"]):
        await update.message.reply_text("Бот уже настроен. Для перенастройки используйте /reconfigure.")
        return ConversationHandler.END
    await update.message.reply_text("Введите API_ID:")
    return STATE_API_ID

async def get_api_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_input = update.message.text.strip()
    logger.debug("Получен API_ID: %s", user_input)
    if not user_input.isdigit():
        await update.message.reply_text("API_ID должен быть числом. Попробуйте снова:")
        return STATE_API_ID
    context.user_data['api_id'] = user_input
    await update.message.reply_text("Введите API_HASH:")
    return STATE_API_HASH

async def get_api_hash(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['api_hash'] = update.message.text
    logger.debug("Получен API_HASH")
    await update.message.reply_text("Введите номер телефона (например, +1234567890):")
    return STATE_PHONE

async def get_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    phone = update.message.text.strip()
    context.user_data['phone'] = phone
    logger.debug("Получен номер телефона: %s", phone)
    api_id = int(context.user_data['api_id'])
    api_hash = context.user_data['api_hash']
    client = TelegramClient(StringSession(), api_id, api_hash)
    try:
        await client.connect()
        sent_code = await client.send_code_request(phone)
        context.user_data['client'] = client
        context.user_data['phone_code_hash'] = sent_code.phone_code_hash
        logger.info("Код авторизации отправлен на номер %s", phone)
        await update.message.reply_text("Введите код из Telegram:")
        return STATE_CODE
    except Exception as e:
        logger.error("Ошибка при отправке кода: %s", e)
        await update.message.reply_text("Ошибка при отправке кода. Попробуйте снова с /setup.")
        await client.disconnect()
        return ConversationHandler.END

async def get_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['code'] = update.message.text.strip()
    logger.debug("Получен код авторизации")
    await update.message.reply_text("Если включена 2FA, введите пароль. Если нет, напишите 'нет':")
    return STATE_PASSWORD

async def get_password(update: Update, context: ContextTypes.DEFAULT_TYPE):
    password = update.message.text if update.message.text.lower() != 'нет' else None
    logger.debug("Получен пароль: %s", "задан" if password else "не задан")
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
        logger.info("Авторизация успешна, сессия сохранена")
        await update.message.reply_text("Введите BOT_TOKEN от @BotFather:")
        return STATE_BOT_TOKEN
    except Exception as e:
        logger.error("Ошибка авторизации: %s", e)
        await update.message.reply_text(f"Ошибка авторизации: {str(e)}. Попробуйте снова с /setup.")
        await client.disconnect()
        return ConversationHandler.END
    finally:
        await client.disconnect()

async def get_bot_token(update: Update, context: ContextTypes.DEFAULT_TYPE):
    bot_token = update.message.text.strip()
    logger.debug("Получен BOT_TOKEN")
    config = {
        "API_ID": context.user_data['api_id'],
        "API_HASH": context.user_data['api_hash'],
        "SESSION_STRING": context.user_data['session_string'],
        "BOT_TOKEN": bot_token,
        "ADMIN_ID": str(update.message.from_user.id)
    }
    save_config(config)
    await update.message.reply_text("Настройка завершена! Перезапустите бота для применения изменений.")
    logger.info("Настройка завершена для пользователя %s", update.message.from_user.id)
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info("Команда /cancel вызвана пользователем %s", update.message.from_user.id)
    if 'client' in context.user_data:
        await context.user_data['client'].disconnect()
    context.user_data.clear()
    await update.message.reply_text("Настройка отменена.")
    return ConversationHandler.END

async def reconfigure(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info("Команда /reconfigure вызвана пользователем %s", update.message.from_user.id)
    if 'client' in context.user_data:
        await context.user_data['client'].disconnect()
    context.user_data.clear()
    await update.message.reply_text("Перенастройка начата. Введите /setup.")
    return ConversationHandler.END

async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info("Команда /reset вызвана пользователем %s", update.message.from_user.id)
    if 'client' in context.user_data:
        await context.user_data['client'].disconnect()
    context.user_data.clear()
    await update.message.reply_text("Состояние сброшено. Введите /setup для начала.")
    return ConversationHandler.END

async def add_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info("Команда /adduser вызвана пользователем %s", update.message.from_user.id)
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
    logger.debug("Добавление пользователя: %s", username)
    tracked_users = load_tracked_users()
    if username not in tracked_users:
        tracked_users.append(username)
        save_tracked_users(tracked_users)
        await update.message.reply_text(f"Пользователь {username} добавлен в список отслеживания.")
    else:
        await update.message.reply_text(f"Пользователь {username} уже в списке отслеживания.")
    return ConversationHandler.END

async def remove_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info("Команда /removeuser вызвана пользователем %s", update.message.from_user.id)
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
    logger.debug("Удаление пользователя: %s", username)
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
                logger.info("Уведомление отправлено админу %s о пользователе %s", admin_id, user)
            except Exception as e:
                logger.error("Ошибка при отправке уведомления: %s", e)

async def main():
    config = load_config()
    api_id = config.get("API_ID")
    api_hash = config.get("API_HASH")
    session_string = config.get("SESSION_STRING")
    bot_token = config.get("BOT_TOKEN") or os.getenv("BOT_TOKEN")
    admin_id = config.get("ADMIN_ID")

    application = None
    try:
        if not bot_token:
            logger.error("BOT_TOKEN не указан в config.json или .env. Бот не может запуститься.")
            return

        # Инициализация бота
        logger.info("Инициализация Application с BOT_TOKEN")
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

        # Проверка полной конфигурации для запуска Telethon
        if not all([api_id, api_hash, session_string]):
            logger.info("Конфигурация не полная, но бот запущен для обработки /setup")
        else:
            # Инициализация клиента Telethon
            logger.info("Инициализация Telethon клиента")
            client = TelegramClient(StringSession(session_string), int(api_id), api_hash)

            # Регистрация обработчика сообщений
            @client.on(NewMessage)
            async def handler(event):
                await handle_new_message(event, application.bot, admin_id)

            async with client:
                await client.start()
                logger.info("Telethon клиент запущен")

        # Запуск polling
        logger.info("Запуск polling")
        await application.initialize()
        await application.start()
        await application.updater.start_polling()
        logger.info("Бот успешно запущен и ожидает команды")
        
        if all([api_id, api_hash, session_string]):
            await client.run_until_disconnected()
        else:
            logger.info("Ожидание завершения polling без Telethon")
            await application.updater.wait_for_shutdown()

    except Exception as e:
        logger.error("Ошибка в главном цикле: %s", e)
        if admin_id and application:
            await application.bot.send_message(
                chat_id=admin_id,
                text=f"Произошла ошибка при запуске бота: {str(e)}"
            )
    finally:
        if application:
            logger.info("Остановка Application")
            await application.stop()
            await application.shutdown()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
