import asyncio
import logging
import os

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.enums import ParseMode

from config import BOT_TOKEN
from database.db import init_db
from handlers import setup_routers
from middleware.access import AccessMiddleware
from scheduler import start_scheduler, stop_scheduler


def build_session() -> AiohttpSession:
    proxy_url = os.getenv("HTTPS_PROXY") or os.getenv("HTTP_PROXY")
    timeout_seconds = 40

    if proxy_url:
        safe_proxy = proxy_url.split("@")[-1] if "@" in proxy_url else proxy_url
        logging.info("Используется прокси: %s", safe_proxy)
        return AiohttpSession(proxy=proxy_url, timeout=timeout_seconds)

    logging.info("Прокси не задан, работаем напрямую")
    return AiohttpSession(timeout=timeout_seconds)


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    await init_db()

    session = build_session()
    bot = Bot(
        token=BOT_TOKEN,
        session=session,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )

    dp = Dispatcher()
    dp.update.middleware(AccessMiddleware())
    dp.include_router(setup_routers())

    start_scheduler(bot)
    logging.info("Бот запущен, начинаю polling")

    try:
        await dp.start_polling(bot, polling_timeout=20)
    finally:
        stop_scheduler()
        await bot.session.close()
        logging.info("Сессия бота закрыта")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Бот остановлен вручную")