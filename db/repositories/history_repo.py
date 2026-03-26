from sqlalchemy import text
from infra.logger import setup_logger

logger = setup_logger(__name__)

def add_record(account_id, market_hash_name, old_price, new_price, engine) -> None:

    sql_text = text("""
        INSERT INTO price_history(
            account_id,
            market_hash_name,
            old_price,
            new_price)
                    
        VALUES (
            :account_id,
            :market_hash_name,
            :old_price,
            :new_price)
    """)

    try:
        with engine.begin() as conn:
            result = conn.execute(
                sql_text,
                {'account_id': account_id, 'market_hash_name': market_hash_name,
                 'old_price' : old_price, 'new_price' : new_price})
            
            logger.info(f'Добавление информации по цене предметов: {result.rowcount}')

    except Exception as e:
        logger.error(f'Ошибка при добавлении информации по цене предметов: {e}')


def get_history_by_account(account_id, limit: 50, engine) -> dict:

    sql_text = text("""
        SELECT * FROM price_history
        WHERE account_id = :account_id
        ORDER BY updated_at
        LIMIT :limit
    """)

    try:
        with engine.begin() as conn:
            result = conn.execute(sql_text, {'account_id': account_id, 'limit' : limit})
            logger.info(f'Выдача информации по цене предметов: {result.rowcount}')

            return result.all()
        
    except Exception as e:
        logger.error(f'Ошибка при выдаче информации по цене предметов: {e}')
