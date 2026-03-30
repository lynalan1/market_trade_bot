from sqlalchemy import text, Row
from infra.logger import setup_logger

logger = setup_logger(__name__)


# ── helpers ──────────────────────────────────────────────────────────────────

def _row_to_obj(row: Row):
    """Превращает строку SQLAlchemy в простой объект с атрибутами."""
    class Account:
        pass
    a = Account()
    for key in row._fields:
        setattr(a, key, getattr(row, key))
    return a


# ── CRUD ─────────────────────────────────────────────────────────────────────

def add_account(telegram_id: int, api_key: str, engine, label: str | None = None) -> None:
    sql = text("""
        INSERT INTO accounts (api_key, owner_telegram_id, label, created_at)
        VALUES (:api_key, :telegram_id, :label, now())
    """)
    try:
        with engine.begin() as conn:
            result = conn.execute(sql, {
                "api_key": api_key,
                "telegram_id": telegram_id,
                "label": label,
            })
            logger.info(f"Аккаунт добавлен | telegram_id={telegram_id} | строк={result.rowcount}")
    except Exception as e:
        logger.error(f"Ошибка add_account: {e}")
        raise


def get_accounts(telegram_id: int, engine) -> list:
    """Все аккаунты пользователя (активные и нет)."""
    sql = text("""
        SELECT * FROM accounts
        WHERE owner_telegram_id = :telegram_id
        ORDER BY created_at
    """)
    try:
        with engine.begin() as conn:
            rows = conn.execute(sql, {"telegram_id": telegram_id}).fetchall()
            return [_row_to_obj(r) for r in rows]
    except Exception as e:
        logger.error(f"Ошибка get_accounts: {e}")
        return []


def get_all_active(engine) -> list:
    """Все активные аккаунты всех пользователей — для движка."""
    sql = text("SELECT * FROM accounts WHERE is_active = TRUE ORDER BY id")
    try:
        with engine.begin() as conn:
            rows = conn.execute(sql).fetchall()
            return [_row_to_obj(r) for r in rows]
    except Exception as e:
        logger.error(f"Ошибка get_all_active: {e}")
        return []


def delete_account(account_id: int, engine) -> None:
    sql = text("DELETE FROM accounts WHERE id = :account_id")
    try:
        with engine.begin() as conn:
            result = conn.execute(sql, {"account_id": account_id})
            logger.info(f"Аккаунт удалён | id={account_id} | строк={result.rowcount}")
    except Exception as e:
        logger.error(f"Ошибка delete_account: {e}")
        raise


def set_account_active(account_id: int, is_active: bool, engine) -> None:
    sql = text("UPDATE accounts SET is_active = :is_active WHERE id = :account_id")
    try:
        with engine.begin() as conn:
            conn.execute(sql, {"account_id": account_id, "is_active": is_active})
            logger.info(f"Статус аккаунта id={account_id} → {is_active}")
    except Exception as e:
        logger.error(f"Ошибка set_account_active: {e}")
        raise


def get_account_stats(account_id: int, engine) -> dict:
    """Статистика по истории цен для аккаунта."""
    sql = text("""
        SELECT
            COUNT(*)                          AS total_updates,
            MAX(updated_at)                   AS last_run
        FROM price_history
        WHERE account_id = :account_id
    """)
    try:
        with engine.begin() as conn:
            row = conn.execute(sql, {"account_id": account_id}).fetchone()
            if not row:
                return {"total_updates": 0, "last_run": "—"}
            return {
                "total_updates": row.total_updates or 0,
                "last_run": row.last_run.strftime("%Y-%m-%d %H:%M") if row.last_run else "—",
            }
    except Exception as e:
        logger.error(f"Ошибка get_account_stats: {e}")
        return {"total_updates": 0, "last_run": "—"}
