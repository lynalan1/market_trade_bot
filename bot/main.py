import asyncio

from aiogram import Bot, Dispatcher
from aiogram.types import BotCommand
from aiogram.fsm.storage.memory import MemoryStorage
from sqlalchemy import create_engine

from config.settings import BOT_TOKEN, DB_URL, CURRENCY, INTERVAL, PING_INTERVAL, TRADES_INTERVAL
from bot.handlers import start, accounts, items
from bot.middlewares.db_middlewares import DbMiddleware
from app.engine import run_loop
from infra.logger import setup_logger
from app.engine import run_loop, ping_loop, trades_loop

logger = setup_logger(__name__)


async def set_commands(bot: Bot) -> None:
    commands = [
        BotCommand(command="start",       description="Запустить бота"),
        BotCommand(command="help",        description="Помощь"),
        BotCommand(command="accounts",    description="Управление аккаунтами"),
        BotCommand(command="addaccount",  description="Добавить аккаунт"),
        BotCommand(command="items",       description="Управление предметами"),
        BotCommand(command="autosell",    description="Включить/выключить автопродажи"),
        BotCommand(command="cancel",      description="Отменить действие"),
    ]
    await bot.set_my_commands(commands)


async def run_bot(db_engine) -> None:
    bot = Bot(token=BOT_TOKEN)
    dp  = Dispatcher(storage=MemoryStorage())

    dp.message.middleware(DbMiddleware(db_engine))
    dp.callback_query.middleware(DbMiddleware(db_engine))


    dp.include_router(start.router)
    dp.include_router(accounts.router)
    dp.include_router(items.router)

    await set_commands(bot)
    logger.info("Бот запущен")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


async def main() -> None:
    db_engine = create_engine(DB_URL, echo=False)
    bot = Bot(token=BOT_TOKEN)

    logger.info("Запуск бота и движка...")

    await asyncio.gather(
        run_bot(db_engine),
        run_loop(
            db_engine=db_engine,
            cur=CURRENCY,
            interval=INTERVAL,
        ),
        ping_loop(
            db_engine=db_engine,
            interval=PING_INTERVAL,
        ),
        trades_loop(
            db_engine=db_engine,
            bot=bot,
            interval=TRADES_INTERVAL,
        ),
    )

if __name__ == "__main__":
    asyncio.run(main())
