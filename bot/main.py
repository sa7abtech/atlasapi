"""
ATLAS Telegram Bot
Main bot application entry point
"""

import logging
import logging.config
import sys
sys.path.append("..")

from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
)

from config import settings, get_log_config
from bot.handlers import (
    start_command,
    help_command,
    stats_command,
    language_command,
    language_callback,
    clear_command,
    analytics_command,
    handle_message,
    error_handler,
)

# Configure logging
logging.config.dictConfig(get_log_config())
logger = logging.getLogger("atlas.bot")


def main():
    """Start the ATLAS Telegram bot"""

    try:
        # Validate settings
        settings.validate()
        logger.info("Settings validated successfully")

        # Create the Application
        application = Application.builder().token(settings.TELEGRAM_BOT_TOKEN).build()

        # Register command handlers
        application.add_handler(CommandHandler("start", start_command))
        application.add_handler(CommandHandler("help", help_command))
        application.add_handler(CommandHandler("stats", stats_command))
        application.add_handler(CommandHandler("language", language_command))
        application.add_handler(CommandHandler("clear", clear_command))
        application.add_handler(CommandHandler("analytics", analytics_command))

        # Register callback query handler for inline buttons
        application.add_handler(CallbackQueryHandler(language_callback, pattern="^lang_"))

        # Register message handler (for all text messages that aren't commands)
        application.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)
        )

        # Register error handler
        application.add_error_handler(error_handler)

        # Log startup
        logger.info("ATLAS Telegram Bot started successfully")
        logger.info(f"Environment: {settings.ENVIRONMENT}")
        logger.info(f"Supported languages: {', '.join(settings.SUPPORTED_LANGUAGES)}")

        # Start the bot
        print("\n" + "=" * 50)
        print("🤖 ATLAS Telegram Bot is running!")
        print("=" * 50)
        print(f"Environment: {settings.ENVIRONMENT}")
        print(f"Log Level: {settings.LOG_LEVEL}")
        print(f"Max Context Tokens: {settings.MAX_CONTEXT_TOKENS}")
        print(f"Cache Expiry: {settings.CACHE_EXPIRY_HOURS} hours")
        print("=" * 50 + "\n")

        # Run the bot until interrupted
        application.run_polling(allowed_updates=["message", "callback_query"])

    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        print(f"\n❌ Configuration Error: {e}")
        print("Please check your .env file and ensure all required variables are set.\n")
        sys.exit(1)

    except Exception as e:
        logger.error(f"Error starting bot: {e}")
        print(f"\n❌ Error: {e}\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
