import asyncio
import httpx

from infra.logger import setup_logger

logger = setup_logger(__name__)

BASE = "https://market.csgo.com/api/v2"


async def get_items(api_key: str) -> dict | None:
    async with httpx.AsyncClient(timeout=20.0) as client:
        try:
            r = await client.post(f"{BASE}/items?key={api_key}")
        except Exception as e:
            logger.error(f"get_items сетевая ошибка: {e}")
            return None

        if r.status_code != 200:
            logger.warning(f"get_items статус {r.status_code}")
            return None

        data = r.json()
        logger.info(f"Получено предметов: {len(data.get('items', []))}")
        return data


async def search_prices(api_key: str, hash_names: list) -> dict | None:
    async with httpx.AsyncClient(timeout=20.0) as client:
        try:
            params = [("key", api_key)] + [("list_hash_name[]", n) for n in hash_names]
            r = await client.get(
                f"{BASE}/search-list-items-by-hash-name-all",
                params=params,
            )
        except Exception as e:
            logger.error(f"search_prices сетевая ошибка: {e}")
            return None

        if r.status_code != 200:
            logger.warning(f"search_prices статус {r.status_code}")
            return None

        data = r.json()
        if not data.get("success"):
            logger.warning(f"search_prices success=false: {data}")
            return None

        prices = data.get("data", {})
        logger.info(f"Получено цен для {len(prices)} предметов")
        return prices


async def set_price(api_key: str, items: list, cur: str = "USD") -> list:
    """
    Обновляет цену каждого предмета по одному запросу.
    Между запросами пауза 1 секунда — как в рабочем скрипте.
    """
    results = []

    for item in items:
        async with httpx.AsyncClient(timeout=20.0) as client:
            try:
                r = await client.post(
                    f"{BASE}/mass-set-price-mhn",
                    params={"key": api_key, "cur": cur},
                    json={
                        "market_hash_name": item["market_hash_name"],
                        "price": item["price"],
                    },
                )
            except Exception as e:
                logger.error(f"set_price сетевая ошибка [{item['market_hash_name']}]: {e}")
                results.append({"market_hash_name": item["market_hash_name"], "success": False, "price": item["price"]})
                await asyncio.sleep(1)
                continue

            if r.status_code != 200:
                logger.warning(f"set_price статус {r.status_code} [{item['market_hash_name']}]")
                results.append({"market_hash_name": item["market_hash_name"], "success": False, "price": item["price"]})
                await asyncio.sleep(1)
                continue

            data    = r.json()
            success = data.get("success", False)

            if success:
                logger.info(f"Цена обновлена | {item['market_hash_name']} -> {item['price']}")
            else:
                logger.warning(f"Ошибка обновления | {item['market_hash_name']} | {data.get('error')}")

            results.append({
                "market_hash_name": item["market_hash_name"],
                "success": success,
                "price": item["price"],
            })

        await asyncio.sleep(1)   

    return results

async def ping_new(api_key: str) -> bool:


    async with httpx.AsyncClient(timeout=20.0) as client:
        try:
            r = await client.post(
                f"{BASE}/ping-new?key={api_key}"
            )
        except Exception as e:
            logger.error(f"ping_new сетевая ошибка: {e}")
            return False

        if r.status_code != 200:
            logger.warning(f"ping_new статус {r.status_code}")
            return False

        data = r.json()
        if data.get("success") and data.get("online"):
            logger.info("ping_new — продажи активны")
            return True
        else:
            logger.warning(f"ping_new success=false: {data}")
            return False


async def get_trades(api_key: str) -> list:

    async with httpx.AsyncClient(timeout=20.0) as client:
        try:
            r = await client.get(f"{BASE}/trades?key={api_key}")
        except Exception as e:
            logger.error(f"get_trades сетевая ошибка: {e}")
            return []

        if r.status_code != 200:
            logger.warning(f"get_trades статус {r.status_code}")
            return []

        data = r.json()
        if not data.get("success"):
            logger.warning(f"get_trades success=false: {data}")
            return []

        return data.get("trades", [])
    