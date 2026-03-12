"""Entry point for the Sekto Telegram bot."""

from __future__ import annotations

import asyncio
import logging
import os
import sys

from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.exceptions import TelegramConflictError

from bot.config import BOT_TOKEN
from bot.handlers import register_handlers

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger(__name__)

class ConflictErrorFilter(logging.Filter):
    def filter(self, record):
        msg = record.getMessage()
        if "TelegramConflictError" in msg and "Conflict: terminated by other getUpdates" in msg:
            return False
        return True

logging.getLogger("aiogram.dispatcher").addFilter(ConflictErrorFilter())


async def health_check(request):
    """Health check endpoint for Render."""
    return web.json_response({"status": "ok", "service": "telegram-bot"})


async def start_bot_polling(bot: Bot, dp: Dispatcher) -> None:
    """Start bot polling in background task."""
    logger.info("Starting bot with polling...")

    try:
        await dp.start_polling(
            bot,
            allowed_updates=dp.resolve_used_update_types(),
            handle_as_tasks=False
        )
    except TelegramConflictError as e:
        logger.info(
            f"Telegram conflict detected (this is normal during deployment): {e}. "
            "Another instance is handling updates. This instance will continue running HTTP server."
        )
    except KeyboardInterrupt:
        logger.info("Bot polling stopped by user")
    except Exception as e:
        logger.error(f"Failed to start bot polling: {e}", exc_info=True)


async def main() -> None:
    """Create the bot, wire handlers, start HTTP server and bot polling."""
    port = int(os.environ.get("PORT", 10000))

    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=MemoryStorage())
    register_handlers(dp)

    app = web.Application()
    app.router.add_get("/", health_check)
    app.router.add_get("/health", health_check)

    bot_task = asyncio.create_task(start_bot_polling(bot, dp))

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()

    logger.info(f"HTTP server started on port {port} for health checks")
    logger.info("Bot polling started in background")

    try:
        await asyncio.Event().wait()
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        bot_task.cancel()
        await runner.cleanup()
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
        sys.exit(0)
