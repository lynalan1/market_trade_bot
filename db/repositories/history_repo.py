from sqlalchemy import text
from infra.logger import setup_logger

logger = setup_logger(__name__)


def add_record(
    account_id: int,
    market_hash_name: str,
    old_price: int,
    new_price: int,
    engine,
) -> None:
    sql = text("""
        INSERT INTO price_history (account_id, market_hash_name, old_price, new_price)
        VALUES (:account_id, :market_hash_name, :old_price, :new_price)
    """)
    try:
        with engine.begin() as conn:
            conn.execute(sql, {
                "account_id": account_id,
                "market_hash_name": market_hash_name,
                "old_price": old_price,
                "new_price": new_price,
            })
            logger.debug(f"История записана | {market_hash_name} {old_price} → {new_price}")
    except Exception as e:
        logger.error(f"Ошибка add_record: {e}")


def get_history_by_account(account_id: int, engine, limit: int = 50) -> list:
    sql = text("""
        SELECT * FROM price_history
        WHERE account_id = :account_id
        ORDER BY updated_at DESC
        LIMIT :limit
    """)
    try:
        with engine.begin() as conn:
            rows = conn.execute(sql, {"account_id": account_id, "limit": limit}).fetchall()
            logger.debug(f"История получена | account_id={account_id} | строк={len(rows)}")
            return rows
    except Exception as e:
        logger.error(f"Ошибка get_history_by_account: {e}")
        return []
