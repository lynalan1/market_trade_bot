from aiogram import Router
from aiogram.filters import CommandStart, Command
from aiogram.types import Message

from db.repositories import account_repo
from infra.logger import setup_logger

logger = setup_logger(__name__)
router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message, db_engine, **_):
    accounts = account_repo.get_accounts(message.from_user.id, db_engine)

    if accounts:
        active       = [a for a in accounts if a.is_active]
        account_info = (
            f"У тебя <b>{len(accounts)}</b> аккаунт(ов), активных: <b>{len(active)}</b>.\n"
            f"Управление → /accounts\n\n"
        )
    else:
        account_info = "Аккаунтов пока нет. Добавь первый → /addaccount\n\n"

    text = (
        "👋 <b>CS2 Market Price Bot</b>\n\n"
        "Автоматически обновляю цены твоих предметов на маркете — "
        "всегда на топ-1 позиции.\n\n"
        + account_info
        + "📋 <b>Команды:</b>\n"
        "/accounts     — управление аккаунтами\n"
        "/addaccount   — добавить аккаунт\n"
        "/items        — управление предметами\n"
        "/autosell on  — запустить автопродажи\n"
        "/autosell off — остановить автопродажи\n"
        "/help         — полная справка\n"
        "❗❗❗Если продажи будут выключены, то бот не сможет их включить автоматически"
    )
    await message.answer(text, parse_mode="HTML")
    logger.info(f"/start | user={message.from_user.id}")


@router.message(Command("help"))
async def cmd_help(message: Message, **_):
    text = (
        "📖 <b>Справка</b>\n\n"
        "<b>Аккаунты:</b>\n"
        "/addaccount           — добавить аккаунт по API-ключу\n"
        "/accounts             — список, вкл/откл, удалить\n\n"
        "<b>Предметы:</b>\n"
        "/items                        — список с управлением\n"
        "/disable <code>&lt;name&gt;</code>            — отключить предмет\n"
        "/enable  <code>&lt;name&gt;</code>            — включить предмет\n"
        "/setmin  <code>&lt;name&gt; &lt;usd&gt;</code>   — поставить ценовой пол\n"
        "/clearmin <code>&lt;name&gt;</code>           — снять ценовой пол\n\n"
        "<b>Автопродажи:</b>\n"
        "/autosell on          — запустить движок\n"
        "/autosell off         — остановить движок\n\n"
        "<b>Прочее:</b>\n"
        "/cancel               — отменить текущее действие\n\n"
        "<b>Формат цены:</b> в USD, например <code>12.50</code>"
    )
    await message.answer(text, parse_mode="HTML")
    logger.info(f"/help | user={message.from_user.id}")
