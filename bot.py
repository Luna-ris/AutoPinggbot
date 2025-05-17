import os
import json
import logging
import asyncio
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
STATE_BOT_TOKEN, STATE_ADD_USER, STATE_REMOVE_USER = range(3)

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
    logger.info("Команда /start вызвана пользователем %s в чате %s", update.message.from_user.id, update.message.chat_id)
    config = load_config()
    if not config.get("BOT_TOKEN"):
        await update.message.reply_text("Бот не настроен. Используйте /setup для настройки.")
        return ConversationHandler.END
    await update.message.reply_text("Привет! Бот готов к работе. Используйте /adduser для добавления пользователей или /setup для перенастройки.")
    return ConversationHandler.END

async def setup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info("Команда /setup вызвана пользователем %s в чате %s", update.message.from_user.id, update.message.chat_id)
    config = load_config()
    if config.get("BOT_TOKEN"):
        await update.message.reply_text("Бот уже настроен. Для перенастройки используйте /reconfigure.")
        return ConversationHandler.END
    await update.message.reply_text("Введите BOT_TOKEN от @BotFather:")
    return STATE_BOT_TOKEN

async def get_bot_token(update: Update, context: ContextTypes.DEFAULT_TYPE):
    bot_token = update.message.text.strip()
    logger.debug("Получен BOT_TOKEN")
    config = {
        "BOT_TOKEN": bot_token,
        "ADMIN_ID": str(update.message.from_user.id)
    }
    save_config(config)
    await update.message.reply_text("Настройка завершена! Перезапустите бота для применения изменений.")
    logger.info("Настройка завершена для пользователя %s", update.message.from_user.id)
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info("Команда /cancel вызвана пользователем %s в чате %s", update.message.from_user.id, update.message.chat_id)
    context.user_data.clear()
    await update.message.reply_text("Настройка отменена.")
    return ConversationHandler.END

async def reconfigure(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info("Команда /reconfigure вызвана пользователем %s в чате %s", update.message.from_user.id, update.message.chat_id)
    context.user_data.clear()
    await update.message.reply_text("Перенастройка начата. Введите /setup.")
    return ConversationHandler.END

async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info("Команда /reset вызвана пользователем %s в чате %s", update.message.from_user.id, update.message.chat_id)
    context.user_data.clear()
    await update.message.reply_text("Состояние сброшено. Введите /setup для начала.")
    return ConversationHandler.END

async def add_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info("Команда /adduser вызвана пользователем %s в чате %s", update.message.from_user.id, update.message.chat_id)
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
    logger.info("Команда /removeuser вызвана пользователем %s в чате %s", update.message.from_user.id, update.message.chat_id)
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

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.debug("Получено сообщение в чате %s: %s", update.message.chat_id, update.message.text)
    config = load_config()
    admin_id = config.get("ADMIN_ID")
    if not admin_id:
        logger.warning("ADMIN_ID отсутствует, пропуск обработки сообщения")
        return

    tracked_users = load_tracked_users()
    message_text = update.message.text.lower() if update.message.text else ""
    
    for user in tracked_users:
        if user.lower() in message_text:
            try:
                chat_id = update.message.chat_id
                message_id = update.message.message_id
                message_link = f"https://t.me/c/{str(chat_id).replace('-100', '')}/{message_id}"
                await context.bot.send_message(
                    chat_id=admin_id,
                    text=f"Пользователь {user} был упомянут в сообщении: {message_link}"
                )
                logger.info("Уведомление отправлено админу %s о пользователе %s", admin_id, user)
            except Exception as e:
                logger.error("Ошибка при отправке уведомления: %s", e)

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info("Команда /status вызвана пользователем %s в чате %s", update.message.from_user.id, update.message.chat_id)
    config = load_config()
    tracked_users = load_tracked_users()
    status_text = "Статус бота:\n"
    status_text += f"Конфигурация: {'Полная' if config.get('BOT_TOKEN') and config.get('ADMIN_ID') else 'Неполная'}\n"
    status_text += f"Отслеживаемые пользователи: {', '.join(tracked_users) if tracked_users else 'Нет'}\n"
    status_text += "Бот работает в режиме обработки сообщений.\n"
    # Проверка прав бота
    try:
        chat_member = await context.bot.get_chat_member(update.message.chat_id, context.bot.id)
        status_text += f"Права бота в чате: {chat_member.status}\n"
        if chat_member.status not in ['administrator', 'member']:
            status_text += "Внимание: Бот не имеет прав для чтения сообщений!\n"
    except Exception as e:
        status_text += f"Ошибка проверки прав: {str(e)}\n"
    await update.message.reply_text(status_text)

async def main():
    logger.info("Запуск бота")
    config = load_config()
    bot_token = config.get("BOT_TOKEN") or os.getenv("BOT_TOKEN")
    admin_id = config.get("ADMIN_ID")

    if not bot_token:
        logger.error("BOT_TOKEN не указан в config.json или .env. Бот не может запуститься.")
        return

    application = None
    try:
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
        application.add_handler(CommandHandler("status", status))
        application.add_handler(conv_handler)
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

        logger.info("Запуск polling")
        await application.initialize()
        await application.start()
        await application.updater.start_polling(drop_pending_updates=True)
        logger.info("Бот успешно запущен и ожидает команды")

        # Ожидание сигнала завершения
        while application.updater.running:
            await asyncio.sleep(1)

    except Exception as e:
        logger.error("Ошибка в главном цикле: %s", e)
        if admin_id and application:
            await application.bot.send_message(
                chat_id=admin_id,
                text=f"Произошла ошибка при запуске бота: {str(e)}"
            )
    finally:
        if application and application.updater.running:
            logger.info("Остановка Application")
            await application.updater.stop()
            await application.stop()
            await application.shutdown()
            logger.info("Application полностью остановлен")

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
