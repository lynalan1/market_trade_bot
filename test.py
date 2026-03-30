import httpx
import asyncio
from config.settings import api_market

API_KEY = api_market

async def get_items(API):
    async with httpx.AsyncClient(timeout=20.0) as client:
        try:
            r = await client.post(f"https://market.csgo.com/api/v2/items?key={API}")
        except Exception as e:
            print(f"Ошибка get_items: {e}")
            return None
        if r.status_code != 200:
            print(f"Ошибка сервера get_items: {r.status_code}")
            return None
        return r.json()

async def search_list_by_hash_names(API, hash_names: list):
    async with httpx.AsyncClient(timeout=20.0) as client:
        try:
            params = [("key", API)] + [("list_hash_name[]", name) for name in hash_names]
            r = await client.get(
                "https://market.csgo.com/api/v2/search-list-items-by-hash-name-all",
                params=params
            )
        except Exception as e:
            print(f"Ошибка search_list: {e}")
            return None
        if r.status_code != 200:
            print(f"Ошибка сервера search_list: {r.status_code}")
            return None
        return r.json().get('data')

async def set_price_single(API, hash_name: str, price: int, cur="USD"):
    async with httpx.AsyncClient(timeout=20.0) as client:
        try:
            r = await client.post(
                "https://market.csgo.com/api/v2/mass-set-price-mhn",
                params={"key": API, "cur": cur},
                json={"market_hash_name": hash_name, "price": price}
            )
        except Exception as e:
            print(f"Ошибка set_price: {e}")
            return None
        if r.status_code != 200:
            print(f"Ошибка сервера set_price: {r.status_code}")
            return None
        return r.json()

async def update_price(API, cur="USD"):
    items = await get_items(API)
    if not items:
        return

    unique = list({
        item['market_hash_name']
        for item in items['items']
        if item['status'] == '1'
    })

    if not unique:
        print("Нет активных предметов на продаже")
        return

    print(f"Активных предметов: {len(unique)}")


    to_update = []
    for i in range(0, len(unique), 50):
        chunk = unique[i:i+50]
        prices_data = await search_list_by_hash_names(API, chunk)

        if not prices_data:
            continue

        for hash_name, offers in prices_data.items():
            if offers:
                top1_price = int(offers[0]['price'])
                to_update.append({"market_hash_name": hash_name, "price": top1_price})
                print(f"{hash_name} -> {top1_price}")

    for item in to_update:
        result = await set_price_single(API, item['market_hash_name'], item['price'], cur)
        print(f"Результат {item['market_hash_name']}: {result}")
        await asyncio.sleep(1)


async def main():
    while True:
        try:
            print("--- Запуск обновления цен ---")
            await update_price(API_KEY)
        except Exception as e:
            print(f"Ошибка: {e}")
        print("--- Ожидание следующего цикла ---")
        await asyncio.sleep(10)

if __name__ == "__main__":
    asyncio.run(main())