import asyncio

from app.market_api import get_items, search_prices, set_price
from db.repositories import account_repo, history_repo, item_settings_repo
from infra.logger import setup_logger
from app.market_api import get_items, search_prices, set_price, ping_new

logger = setup_logger(__name__)


async def run_once(account, db_engine, cur: str = "USD") -> None:
    api_key    = account.api_key
    account_id = account.id

    logger.info(f"=== Цикл запущен | account_id={account_id} ===")


    items_data = await get_items(api_key)
    if not items_data:
        logger.warning(f"Не удалось получить предметы | account_id={account_id}")
        return

    unique = list({
        item["market_hash_name"]
        for item in items_data.get("items", [])
        if item["status"] == "1"
    })

    if not unique:
        logger.info(f"Нет активных предметов | account_id={account_id}")
        return

    logger.info(f"Активных предметов: {len(unique)}")


    settings = item_settings_repo.get_all_settings(account_id, db_engine)

    allowed = [
        name for name in unique
        if settings.get(name, {}).get("is_active", True)
    ]

    if not allowed:
        logger.info(f"Все предметы отключены вручную | account_id={account_id}")
        return


    to_update = []

    for i in range(0, len(allowed), 50):
        chunk       = allowed[i:i + 50]
        prices_data = await search_prices(api_key, chunk)

        if not prices_data:
            logger.warning(f"Не удалось получить цены, чанк {i // 50 + 1}")
            continue

        for hash_name, offers in prices_data.items():
            if not offers:
                continue

            top1_price = int(offers[0]["price"])
            min_price  = settings.get(hash_name, {}).get("min_price")

            if min_price and top1_price < min_price:
                logger.info(f"Пропущен (пол {min_price}) | {hash_name} топ-1={top1_price}")
                continue

            to_update.append({"market_hash_name": hash_name, "price": top1_price})
            logger.info(f"{hash_name} -> {top1_price}")

        if len(allowed) > 50:
            await asyncio.sleep(2)

    if not to_update:
        logger.info(f"Нечего обновлять | account_id={account_id}")
        return


    current_prices = {
        item["market_hash_name"]: item.get("price", 0)
        for item in items_data.get("items", [])
    }

    results = await set_price(api_key, to_update, cur)


    success_count = 0
    for r in results:
        if r["success"]:
            success_count += 1
            history_repo.add_record(
                account_id       = account_id,
                market_hash_name = r["market_hash_name"],
                old_price        = current_prices.get(r["market_hash_name"], 0),
                new_price        = r["price"],
                engine           = db_engine,
            )

    logger.info(
        f"=== Цикл завершён | account_id={account_id} | "
        f"обновлено={success_count} | ошибок={len(results) - success_count} ==="
    )


async def run_loop(db_engine, cur: str = "USD", interval: int = 60) -> None:

    logger.info("Движок запущен")

    while True:
        accounts = account_repo.get_all_active(db_engine)

        if not accounts:
            logger.info("Нет активных аккаунтов, ожидание...")
        else:
            for account in accounts:
                try:
                    await run_once(account, db_engine, cur)
                except Exception as e:
                    logger.error(f"Ошибка run_once account_id={account.id}: {e}")

        logger.info(f"Следующий цикл через {interval} сек")
        await asyncio.sleep(interval)


async def ping_loop(db_engine, interval: int = 120) -> None:
    """
    Каждые interval секунд вызывает ping-new для всех активных аккаунтов.
    Если продажи были выключены — включает их обратно.
    """
    logger.info("Ping-loop запущен")

    while True:
        accounts = account_repo.get_all_active(db_engine)

        for account in accounts:
            try:
                success = await ping_new(account.api_key)
                if not success:
                    logger.warning(
                        f"ping_new вернул false | account_id={account.id} — "
                        f"возможно продажи были выключены, повторная попытка"
                    )
                    # повторная попытка через 5 секунд
                    await asyncio.sleep(5)
                    await ping_new(account.api_key)
            except Exception as e:
                logger.error(f"Ошибка ping_loop account_id={account.id}: {e}")

        await asyncio.sleep(interval)


async def trades_loop(db_engine, bot, interval: int = 30) -> None:
    """
    Каждые interval секунд проверяет предметы со status=2 (проданы, ожидают передачи).
    Если появились новые — отправляет уведомление владельцу в Telegram.
    """
    logger.info("Trades-loop запущен")

    notified: set = set()

    while True:
        accounts = account_repo.get_all_active(db_engine)

        for account in accounts:
            try:
                items_data = await get_items(account.api_key)
                if not items_data:
                    continue

                sold_items = [
                    item for item in items_data.get("items", [])
                    if item["status"] == "2"
                ]

                for item in sold_items:
                    item_id = item.get("item_id")
                    key = (account.id, item_id)

                    if key in notified:
                        continue
                    
                    price_raw = item.get("price", "—")

                    account_label = account.label or f"Account #{account.id}"

                    msg = (
                        f"🔔 <b>Предмет продан!</b>\n\n"
                        f"👤 Аккаунт: <b>{account_label}</b>\n"
                        f"🎮 <b>{item.get('market_hash_name', '—')}</b>\n"
                        f"💰 Цена: {price_raw}\n"
                        f"🆔 Item ID: <code>{item_id}</code>\n\n"
                        f"✅ Подтвердите передачу в приложении Steam!"
                    )

                    try:
                        await bot.send_message(
                            chat_id=account.owner_telegram_id,
                            text=msg,
                            parse_mode="HTML"
                        )
                        notified.add(key)
                        logger.info(
                            f"Уведомление отправлено | "
                            f"item_id={item_id} | "
                            f"telegram_id={account.owner_telegram_id}"
                        )
                    except Exception as e:
                        logger.error(f"Ошибка отправки уведомления: {e}")

            except Exception as e:
                logger.error(f"Ошибка trades_loop account_id={account.id}: {e}")

        await asyncio.sleep(interval)