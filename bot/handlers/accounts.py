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

from db.repositories import account_repo
from infra.logger import setup_logger

logger = setup_logger(__name__)
router = Router()


class AddAccountStates(StatesGroup):
    waiting_for_api_key = State()
    waiting_for_label   = State()


async def safe_edit(message, text, markup=None):
    try:
        await message.edit_text(text, reply_markup=markup, parse_mode="HTML")
    except TelegramBadRequest as e:
        if "message is not modified" not in str(e):
            raise


def _mask(key: str) -> str:
    return f"{key[:4]}…{key[-4:]}" if len(key) > 8 else "****"


def _build_keyboard(accounts: list) -> tuple[str, InlineKeyboardMarkup]:
    if not accounts:
        return (
            "📭 <b>Аккаунтов нет.</b>\nДобавь первый через /addaccount",
            InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="➕ Добавить аккаунт", callback_data="account:add"),
            ]]),
        )

    lines   = [f"👤 <b>Твои аккаунты</b> ({len(accounts)}):\n"]
    buttons = []

    for acc in accounts:
        icon  = "🟢" if acc.is_active else "🔴"
        label = acc.label or f"Аккаунт #{acc.id}"
        lines.append(f"{icon} <b>{label}</b>\n   Ключ: <code>{_mask(acc.api_key)}</code>  |  ID: {acc.id}")

        t_label = "🔴 Откл" if acc.is_active else "🟢 Вкл"
        t_cb    = f"account:deactivate:{acc.id}" if acc.is_active else f"account:activate:{acc.id}"

        buttons.append([
            InlineKeyboardButton(text=t_label,         callback_data=t_cb),
            InlineKeyboardButton(text="🗑 Удалить",    callback_data=f"account:delete:{acc.id}"),
            InlineKeyboardButton(text="📊 Статистика", callback_data=f"account:stats:{acc.id}"),
        ])

    buttons.append([
        InlineKeyboardButton(text="➕ Добавить", callback_data="account:add"),
        InlineKeyboardButton(text="🔄 Обновить", callback_data="account:refresh"),
    ])

    return "\n".join(lines), InlineKeyboardMarkup(inline_keyboard=buttons)



@router.message(Command("accounts"))
async def cmd_accounts(message: Message, db_engine, **_):
    accounts = account_repo.get_accounts(message.from_user.id, db_engine)
    text, markup = _build_keyboard(accounts)
    await message.answer(text, reply_markup=markup, parse_mode="HTML")


@router.callback_query(F.data == "account:refresh")
async def cb_refresh(call: CallbackQuery, db_engine, **_):
    accounts = account_repo.get_accounts(call.from_user.id, db_engine)
    text, markup = _build_keyboard(accounts)
    await safe_edit(call.message, text, markup)
    await call.answer("Обновлено ✅")


@router.message(Command("addaccount"))
@router.callback_query(F.data == "account:add")
async def cmd_addaccount(event: Message | CallbackQuery, state: FSMContext, **_):
    text = (
        "🔑 <b>Добавление аккаунта</b>\n\n"
        "Введи API-ключ от <b>market.csgo.com</b>.\n"
        "Найти: профиль → API.\n\n/cancel — отмена"
    )
    if isinstance(event, CallbackQuery):
        await event.message.answer(text, parse_mode="HTML")
        await event.answer()
    else:
        await event.answer(text, parse_mode="HTML")
    await state.set_state(AddAccountStates.waiting_for_api_key)


@router.message(AddAccountStates.waiting_for_api_key)
async def fsm_api_key(message: Message, state: FSMContext, **_):
    if (message.text or "").strip().lower() == "/cancel":
        await state.clear(); await message.answer("❌ Отменено."); return

    key = (message.text or "").strip()
    if len(key) < 16:
        await message.answer("⚠️ Ключ слишком короткий. Попробуй ещё раз или /cancel."); return

    await state.update_data(api_key=key)
    await state.set_state(AddAccountStates.waiting_for_label)
    await message.answer(
        "✏️ Введи название аккаунта (например <code>Основной</code>).\n"
        "Или отправь <code>-</code> чтобы пропустить.",
        parse_mode="HTML",
    )


@router.message(AddAccountStates.waiting_for_label)
async def fsm_label(message: Message, state: FSMContext, db_engine, **_):
    if (message.text or "").strip().lower() == "/cancel":
        await state.clear(); await message.answer("❌ Отменено."); return

    raw   = (message.text or "").strip()
    label = None if raw == "-" else raw
    data  = await state.get_data()

    try:
        account_repo.add_account(
            telegram_id=message.from_user.id,
            api_key=data["api_key"],
            label=label,
            engine=db_engine,
        )
        await state.clear()
        await message.answer(
            f"✅ <b>Аккаунт добавлен!</b>\n\n"
            f"Название: <b>{label or f'Аккаунт #{message.from_user.id}'}</b>\n"
            f"Ключ: <code>{_mask(data['api_key'])}</code>\n\n"
            f"Запусти автопродажи: /autosell on",
            parse_mode="HTML",
        )
    except Exception as e:
        logger.error(f"Ошибка add_account: {e}")
        await state.clear()
        await message.answer("❌ Не удалось добавить. Возможно, ключ уже добавлен.\n/addaccount")


@router.callback_query(F.data.startswith("account:activate:") | F.data.startswith("account:deactivate:"))
async def cb_toggle(call: CallbackQuery, db_engine, **_):
    parts      = call.data.split(":")
    is_active  = parts[1] == "activate"
    account_id = int(parts[2])

    account_repo.set_account_active(account_id, is_active, db_engine)
    await call.answer(f"Аккаунт {'включён 🟢' if is_active else 'отключён 🔴'}")

    accounts = account_repo.get_accounts(call.from_user.id, db_engine)
    text, markup = _build_keyboard(accounts)
    await safe_edit(call.message, text, markup)

@router.callback_query(F.data.startswith("account:delete:"))
async def cb_delete_confirm(call: CallbackQuery, **_):
    acc_id = call.data.split(":")[-1]
    markup = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Да, удалить", callback_data=f"account:confirm_delete:{acc_id}"),
        InlineKeyboardButton(text="❌ Отмена",      callback_data="account:refresh"),
    ]])
    await safe_edit(
        call.message,
        f"⚠️ <b>Удалить аккаунт #{acc_id}?</b>\n\nВся история тоже удалится.",
        markup,
    )
    await call.answer()


@router.callback_query(F.data.startswith("account:confirm_delete:"))
async def cb_delete_execute(call: CallbackQuery, db_engine, **_):
    acc_id = int(call.data.split(":")[-1])
    try:
        account_repo.delete_account(acc_id, db_engine)
        await call.answer("🗑 Удалён")
    except Exception as e:
        logger.error(f"Ошибка удаления {acc_id}: {e}")
        await call.answer("❌ Ошибка", show_alert=True)
        return

    accounts = account_repo.get_accounts(call.from_user.id, db_engine)
    text, markup = _build_keyboard(accounts)
    await safe_edit(call.message, text, markup)



@router.callback_query(F.data.startswith("account:stats:"))
async def cb_stats(call: CallbackQuery, db_engine, **_):
    acc_id = int(call.data.split(":")[-1])
    try:
        stats = account_repo.get_account_stats(acc_id, db_engine)
    except Exception as e:
        logger.error(f"Ошибка статистики {acc_id}: {e}")
        await call.answer("❌ Ошибка", show_alert=True)
        return

    text = (
        f"📊 <b>Статистика аккаунта #{acc_id}</b>\n\n"
        f"Всего обновлений: <b>{stats.get('total_updates', 0)}</b>\n"
        f"Последнее:        <b>{stats.get('last_run', '—')}</b>"
    )
    markup = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="◀ Назад", callback_data="account:refresh"),
    ]])
    await safe_edit(call.message, text, markup)
    await call.answer()

@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext, **_):
    if await state.get_state() is None:
        await message.answer("Нечего отменять."); return
    await state.clear()
    await message.answer("❌ Действие отменено.")
