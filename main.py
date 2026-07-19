"""Personal Assistant Bot - Main Entry Point"""
import asyncio
import logging
from telegram.ext import Application, CommandHandler, MessageHandler, filters

from config import settings
from database import init_db
from handlers import (
    start, help_cmd, tasks_cmd, alltasks_cmd, done_cmd, delete_cmd,
    settings_cmd, research_cmd, handle_text, handle_photo, handle_voice,
    handle_video, handle_document
)

# Setup logging so you can see what's happening
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

async def main():
    """Start the bot"""
    logger.info("🚀 Starting Personal Assistant...")

    # 1. Initialize database (creates tables on first run)
    await init_db()
    logger.info("✅ Database ready")

    # 2. Build the bot application
    application = Application.builder().token(settings.TELEGRAM_BOT_TOKEN).build()

    # 3. Register command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_cmd))
    application.add_handler(CommandHandler("tasks", tasks_cmd))
    application.add_handler(CommandHandler("alltasks", alltasks_cmd))
    application.add_handler(CommandHandler("done", done_cmd))
    application.add_handler(CommandHandler("delete", delete_cmd))
    application.add_handler(CommandHandler("settings", settings_cmd))
    application.add_handler(CommandHandler("research", research_cmd))

    # 4. Register message handlers (for all media types)
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    application.add_handler(MessageHandler(filters.VOICE, handle_voice))
    application.add_handler(MessageHandler(filters.VIDEO, handle_video))
    application.add_handler(MessageHandler(filters.Document.ALL, handle_document))

    # 5. Start the bot
    logger.info("🤖 Bot is running! Send /start in Telegram to activate.")

    await application.initialize()
    await application.start()
    await application.updater.start_polling(drop_pending_updates=True)

    # Keep running forever
    while True:
        await asyncio.sleep(3600)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("👋 Bot stopped by user")
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")
