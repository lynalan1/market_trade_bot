from __future__ import annotations

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton,
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.exceptions import TelegramBadRequest

from db.repositories import item_settings_repo, account_repo
from app.market_api import get_items, search_prices
from infra.logger import setup_logger

logger = setup_logger(__name__)
router = Router()


class SetMinPriceStates(StatesGroup):
    waiting_for_price_value = State()


async def safe_edit(message, text, markup=None):
    try:
        await message.edit_text(text, reply_markup=markup, parse_mode="HTML")
    except TelegramBadRequest as e:
        if "message is not modified" not in str(e):
            raise


def _cents_to_usd(cents: int) -> str:
   
    return f"${cents / 1000:.2f}"


def _usd_to_cents(value: str) -> int | None:
    try:
        return round(float(value.strip().lstrip("$")) * 1000)
    except ValueError:
        return None


def _mask_key(key: str) -> str:
    return f"{key[:4]}…{key[-4:]}" if len(key) > 8 else "****"


def _get_account_by_id(db_engine, account_id: int, telegram_id: int):
    """Возвращает аккаунт по id, если он принадлежит пользователю."""
    accs = account_repo.get_accounts(telegram_id, db_engine)
    for a in accs:
        if a.id == account_id:
            return a
    return None


def _first_active_account(db_engine, telegram_id: int):
    accs = account_repo.get_accounts(telegram_id, db_engine)
    active = [a for a in accs if a.is_active]
    return active[0] if active else None


def _build_account_select_keyboard(accounts: list) -> tuple[str, InlineKeyboardMarkup]:
    lines = ["👤 <b>Выбери аккаунт для просмотра предметов:</b>\n"]
    buttons = []

    for acc in accounts:
        icon  = "🟢" if acc.is_active else "🔴"
        label = acc.label or f"Аккаунт #{acc.id}"
        lines.append(f"{icon} <b>{label}</b>  |  <code>{_mask_key(acc.api_key)}</code>")
        buttons.append([
            InlineKeyboardButton(
                text=f"{icon} {label}",
                callback_data=f"items:acc:{acc.id}:0",
            )
        ])

    return "\n".join(lines), InlineKeyboardMarkup(inline_keyboard=buttons)



def _build_keyboard(
    items: list,
    settings: dict,
    acc_id: int,
    page: int = 0,
    page_size: int = 8,
) -> tuple[str, InlineKeyboardMarkup]:
    total      = len(items)
    start      = page * page_size
    end        = min(start + page_size, total)
    pages      = max(1, -(-total // page_size))
    page_items = items[start:end]

    lines   = [f"📦 <b>Предметы</b>  (стр. {page + 1}/{pages}, всего {total})\n"]
    buttons = []

    for item in page_items:
        name      = item["market_hash_name"]
        price     = item.get("market_price", 0)  
        cfg       = settings.get(name, {})
        active    = cfg.get("is_active", True)
        min_price = cfg.get("min_price")

        icon      = "🟢" if active else "🔴"
        floor_str = f" | пол {_cents_to_usd(min_price)}" if min_price else ""
        price_str = _cents_to_usd(price) if price else "нет данных"

        lines.append(f"{icon} <code>{name}</code>\n   Цена: {price_str}{floor_str}")

        t_label = "🔴 Откл" if active else "🟢 Вкл"
        t_cb    = f"item:disable:{acc_id}:{name}" if active else f"item:enable:{acc_id}:{name}"

        buttons.append([
            InlineKeyboardButton(text=t_label,   callback_data=t_cb),
            InlineKeyboardButton(text="💲 Пол",  callback_data=f"item:setmin:{acc_id}:{name}"),
            InlineKeyboardButton(text="✖ Сброс", callback_data=f"item:clearmin:{acc_id}:{name}"),
        ])

    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="◀ Назад",  callback_data=f"items:acc:{acc_id}:{page - 1}"))
    if end < total:
        nav.append(InlineKeyboardButton(text="Вперёд ▶", callback_data=f"items:acc:{acc_id}:{page + 1}"))
    if nav:
        buttons.append(nav)

    buttons.append([
        InlineKeyboardButton(text="🔄 Обновить",    callback_data=f"items:refresh:{acc_id}:{page}"),
        InlineKeyboardButton(text="◀ К аккаунтам", callback_data="items:select"),
    ])

    return "\n".join(lines), InlineKeyboardMarkup(inline_keyboard=buttons)


async def _load_items_with_prices(api_key: str) -> list | None:
    """
    Получает список активных предметов из /items,
    затем подтягивает реальные рыночные цены через search_prices
    и добавляет поле market_price к каждому предмету.
    """
    items_data = await get_items(api_key)
    if not items_data:
        return None

    active_items = [i for i in items_data.get("items", []) if i["status"] == "1"]
    if not active_items:
        return []

   
    hash_names = list({i["market_hash_name"] for i in active_items})
    price_map: dict[str, int] = {}

    for chunk_start in range(0, len(hash_names), 50):
        chunk = hash_names[chunk_start:chunk_start + 50]
        prices_data = await search_prices(api_key, chunk)
        if prices_data:
            for hash_name, offers in prices_data.items():
                if offers:
                    price_map[hash_name] = int(offers[0]["price"])

   
    for item in active_items:
        item["market_price"] = price_map.get(item["market_hash_name"], 0)

    return active_items


async def _show_items(target, db_engine, account, page: int = 0, edit: bool = False):

    items = await _load_items_with_prices(account.api_key)

    if items is None:
        txt = "❌ Не удалось получить предметы."
        if edit:
            await safe_edit(target.message, txt)
        else:
            await target.answer(txt)
        return

    if not items:
        txt = "📭 Нет активных предметов на маркете."
        if edit:
            await safe_edit(target.message, txt)
        else:
            await target.answer(txt)
        return

    settings     = item_settings_repo.get_all_settings(account.id, db_engine)
    text, markup = _build_keyboard(items, settings, account.id, page=page)

    if edit:
        await safe_edit(target.message, text, markup)
    else:
        await target.answer(text, reply_markup=markup, parse_mode="HTML")



@router.message(Command("items"))
async def cmd_items(message: Message, db_engine, **_):
    accounts = account_repo.get_accounts(message.from_user.id, db_engine)
    if not accounts:
        await message.answer("❌ Нет аккаунтов. Добавь через /addaccount.")
        return

    if len(accounts) == 1:

        await message.answer("⏳ Загружаю предметы…")
        await _show_items(message, db_engine, accounts[0], page=0, edit=False)
    else:

        text, markup = _build_account_select_keyboard(accounts)
        await message.answer(text, reply_markup=markup, parse_mode="HTML")



@router.callback_query(F.data == "items:select")
async def cb_select_account(call: CallbackQuery, db_engine, **_):
    accounts = account_repo.get_accounts(call.from_user.id, db_engine)
    if not accounts:
        await call.answer("Нет аккаунтов.", show_alert=True)
        return
    text, markup = _build_account_select_keyboard(accounts)
    await safe_edit(call.message, text, markup)
    await call.answer()



@router.callback_query(F.data.startswith("items:acc:"))
async def cb_load_account_items(call: CallbackQuery, db_engine, **_):

    parts  = call.data.split(":")
    acc_id = int(parts[2])
    page   = int(parts[3])

    account = _get_account_by_id(db_engine, acc_id, call.from_user.id)
    if not account:
        await call.answer("Аккаунт не найден.", show_alert=True)
        return

    await call.answer("⏳ Загружаю…")
    await _show_items(call, db_engine, account, page=page, edit=True)


@router.callback_query(F.data.startswith("items:refresh:"))
async def cb_refresh(call: CallbackQuery, db_engine, **_):

    parts  = call.data.split(":")
    acc_id = int(parts[2])
    page   = int(parts[3])

    account = _get_account_by_id(db_engine, acc_id, call.from_user.id)
    if not account:
        await call.answer("Аккаунт не найден.", show_alert=True)
        return

    await call.answer("🔄 Обновляю…")
    await _show_items(call, db_engine, account, page=page, edit=True)


@router.callback_query(F.data.startswith("item:disable:") | F.data.startswith("item:enable:"))
async def cb_toggle_item(call: CallbackQuery, db_engine, **_):

    parts     = call.data.split(":", 3)
    action    = parts[1]       
    acc_id    = int(parts[2])
    hash_name = parts[3]
    is_active = action == "enable"

    account = _get_account_by_id(db_engine, acc_id, call.from_user.id)
    if not account:
        await call.answer("Аккаунт не найден.", show_alert=True)
        return

    item_settings_repo.set_item_active(account.id, hash_name, is_active, db_engine)
    await call.answer("🟢 Включён" if is_active else "🔴 Отключён")
    await _show_items(call, db_engine, account, page=0, edit=True)



@router.callback_query(F.data.startswith("item:setmin:"))
async def cb_setmin_start(call: CallbackQuery, state: FSMContext, **_):
    parts     = call.data.split(":", 3)
    acc_id    = int(parts[2])
    hash_name = parts[3]

    await state.set_state(SetMinPriceStates.waiting_for_price_value)
    await state.update_data(hash_name=hash_name, acc_id=acc_id)
    await call.message.answer(
        f"💲 <b>Ценовой пол для:</b>\n<code>{hash_name}</code>\n\n"
        f"Введи минимальную цену в USD (например <code>12.50</code>).\n/cancel — отмена",
        parse_mode="HTML",
    )
    await call.answer()


@router.message(SetMinPriceStates.waiting_for_price_value)
async def fsm_setmin_value(message: Message, state: FSMContext, db_engine, **_):
    if (message.text or "").strip().lower() == "/cancel":
        await state.clear()
        await message.answer("❌ Отменено.")
        return

    cents = _usd_to_cents(message.text or "")
    if cents is None or cents <= 0:
        await message.answer("⚠️ Неверный формат. Например: <code>12.50</code>", parse_mode="HTML")
        return

    data      = await state.get_data()
    hash_name = data["hash_name"]
    acc_id    = data["acc_id"]
    account   = _get_account_by_id(db_engine, acc_id, message.from_user.id)

    if not account:
        await state.clear()
        await message.answer("❌ Аккаунт не найден.")
        return

    item_settings_repo.set_item_min_price(account.id, hash_name, cents, db_engine)
    await state.clear()
    await message.answer(
        f"✅ Ценовой пол установлен:\n<code>{hash_name}</code>\nМинимум: <b>{_cents_to_usd(cents)}</b>",
        parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("item:clearmin:"))
async def cb_clearmin(call: CallbackQuery, db_engine, **_):
    parts     = call.data.split(":", 3)
    acc_id    = int(parts[2])
    hash_name = parts[3]

    account = _get_account_by_id(db_engine, acc_id, call.from_user.id)
    if not account:
        await call.answer("Аккаунт не найден.", show_alert=True)
        return

    item_settings_repo.set_item_min_price(account.id, hash_name, None, db_engine)
    await call.answer("✖ Пол снят")
    await _show_items(call, db_engine, account, page=0, edit=True)


@router.message(Command("disable"))
async def cmd_disable(message: Message, db_engine, **_):
    args = (message.text or "").split(maxsplit=1)
    if len(args) < 2:
        await message.answer("Использование: <code>/disable AK-47 | Redline (FT)</code>", parse_mode="HTML")
        return
    account = _first_active_account(db_engine, message.from_user.id)
    if not account:
        await message.answer("❌ Нет активного аккаунта.")
        return
    item_settings_repo.set_item_active(account.id, args[1].strip(), False, db_engine)
    await message.answer(f"🔴 Отключён:\n<code>{args[1].strip()}</code>", parse_mode="HTML")


@router.message(Command("enable"))
async def cmd_enable(message: Message, db_engine, **_):
    args = (message.text or "").split(maxsplit=1)
    if len(args) < 2:
        await message.answer("Использование: <code>/enable AK-47 | Redline (FT)</code>", parse_mode="HTML")
        return
    account = _first_active_account(db_engine, message.from_user.id)
    if not account:
        await message.answer("❌ Нет активного аккаунта.")
        return
    item_settings_repo.set_item_active(account.id, args[1].strip(), True, db_engine)
    await message.answer(f"🟢 Включён:\n<code>{args[1].strip()}</code>", parse_mode="HTML")


@router.message(Command("setmin"))
async def cmd_setmin(message: Message, db_engine, **_):
    args = (message.text or "").split(maxsplit=2)
    if len(args) < 3:
        await message.answer("Использование: <code>/setmin AK-47 | Redline (FT) 12.50</code>", parse_mode="HTML")
        return
    cents = _usd_to_cents(args[2])
    if cents is None or cents <= 0:
        await message.answer("⚠️ Неверная цена.")
        return
    account = _first_active_account(db_engine, message.from_user.id)
    if not account:
        await message.answer("❌ Нет активного аккаунта.")
        return
    item_settings_repo.set_item_min_price(account.id, args[1].strip(), cents, db_engine)
    await message.answer(f"✅ Пол: <code>{args[1].strip()}</code> → <b>{_cents_to_usd(cents)}</b>", parse_mode="HTML")


@router.message(Command("clearmin"))
async def cmd_clearmin(message: Message, db_engine, **_):
    args = (message.text or "").split(maxsplit=1)
    if len(args) < 2:
        await message.answer("Использование: <code>/clearmin AK-47 | Redline (FT)</code>", parse_mode="HTML")
        return
    account = _first_active_account(db_engine, message.from_user.id)
    if not account:
        await message.answer("❌ Нет активного аккаунта.")
        return
    item_settings_repo.set_item_min_price(account.id, args[1].strip(), None, db_engine)
    await message.answer(f"✖ Пол снят:\n<code>{args[1].strip()}</code>", parse_mode="HTML")


@router.message(Command("autosell"))
async def cmd_autosell(message: Message, db_engine, **_):
    args = (message.text or "").split(maxsplit=1)
    if len(args) < 2 or args[1].lower() not in ("on", "off"):
        await message.answer(
            "Использование:\n<code>/autosell on</code> — включить\n<code>/autosell off</code> — выключить",
            parse_mode="HTML",
        )
        return

    enable  = args[1].lower() == "on"
    account = _first_active_account(db_engine, message.from_user.id)
    if not account:
        await message.answer("❌ Нет активного аккаунта.")
        return

    account_repo.set_account_active(account.id, enable, db_engine)

    if enable:
        await message.answer("✅ <b>Автопродажи включены.</b>\nДвижок обновит цены на следующем цикле.", parse_mode="HTML")
    else:
        await message.answer("⏸ <b>Автопродажи остановлены.</b>", parse_mode="HTML")
