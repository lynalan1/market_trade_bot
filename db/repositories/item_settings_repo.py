from sqlalchemy import text
from infra.logger import setup_logger

logger = setup_logger(__name__)



def _upsert(account_id: int, market_hash_name: str, engine, **fields) -> None:

    set_clause = ", ".join(f"{k} = :{k}" for k in fields)
    sql = text(f"""
        INSERT INTO item_settings (account_id, market_hash_name, {", ".join(fields)})
        VALUES (:account_id, :market_hash_name, {", ".join(f":{k}" for k in fields)})
        ON CONFLICT (account_id, market_hash_name)
        DO UPDATE SET {set_clause}
    """)
    params = {"account_id": account_id, "market_hash_name": market_hash_name, **fields}
    with engine.begin() as conn:
        conn.execute(sql, params)


def get_all_settings(account_id: int, engine) -> dict:
    """
    Возвращает все настройки предметов аккаунта в виде словаря:
      { "AK-47 | Redline (FT)": {"is_active": True, "min_price": 1500}, ... }
    """
    sql = text("""
        SELECT market_hash_name, is_active, min_price
        FROM item_settings
        WHERE account_id = :account_id
    """)
    try:
        with engine.begin() as conn:
            rows = conn.execute(sql, {"account_id": account_id}).fetchall()
            return {
                row.market_hash_name: {
                    "is_active": row.is_active,
                    "min_price": row.min_price,
                }
                for row in rows
            }
    except Exception as e:
        logger.error(f"Ошибка get_all_settings: {e}")
        return {}


def set_item_active(account_id: int, market_hash_name: str, is_active: bool, engine) -> None:
    try:
        _upsert(account_id, market_hash_name, engine, is_active=is_active)
        logger.info(f"item_settings | {market_hash_name} | is_active={is_active}")
    except Exception as e:
        logger.error(f"Ошибка set_item_active: {e}")
        raise


def set_item_min_price(account_id: int, market_hash_name: str, min_price: int | None, engine) -> None:
    try:
        _upsert(account_id, market_hash_name, engine, min_price=min_price)
        logger.info(f"item_settings | {market_hash_name} | min_price={min_price}")
    except Exception as e:
        logger.error(f"Ошибка set_item_min_price: {e}")
        raise


def is_item_active(account_id: int, market_hash_name: str, engine) -> bool:
    
    sql = text("""
        SELECT is_active FROM item_settings
        WHERE account_id = :account_id AND market_hash_name = :market_hash_name
    """)
    try:
        with engine.begin() as conn:
            row = conn.execute(sql, {
                "account_id": account_id,
                "market_hash_name": market_hash_name,
            }).fetchone()
            return row.is_active if row else True
    except Exception as e:
        logger.error(f"Ошибка is_item_active: {e}")
        return True
