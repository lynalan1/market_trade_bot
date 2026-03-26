from sqlalchemy import text
from infra.logger import setup_logger

logger = setup_logger(__name__)

def add_account(api_key, telegram_id, engine) -> None:

    
    sql_text = text("""
        INSERT INTO accounts(
            api_key,
            owner_telegram_id,
            created_at)
        VALUES (
            :api_key,
            :owner_telegram_id,
            now())
    """)

    try:
        with engine.begin() as conn:
            result = conn.execute(
                sql_text,
                {'api_key': api_key, 'owner_telegram_id': telegram_id})
            
            print(result)
            logger.info(f'Аккаунт добавлен, строк: {result.rowcount}')

    except Exception as e:
        logger.error(f'Ошибка при добавлении аккаунта: {e}')

def get_accounts(telegram_id, engine) -> dict:

    
    sql_text = text("""
        SELECT * FROM accounts
        WHERE is_active = True AND owner_telegram_id = :telegram_id
        ORDER BY created_at
    """)

    try:
        with engine.begin() as conn:

            result = conn.execute(sql_text, {'telegram_id' : telegram_id})
            logger.info(f'Выдача данных произведена: {result.rowcount}')
            return result.all()
        
    except Exception as e:

        logger.error(f'Ошибка при получение данных аккаунтов: {e}')
        return None

def delete_account(account_id, engine) -> None:


    sql_text = text("""
        DELETE FROM accounts
        WHERE id = :account_id
    """)

    try:
        with engine.begin() as conn:

            result = conn.execute(sql_text, {'account_id' : account_id})
            logger.info(f'Удаление аккаунта: {result.rowcount}')
        
    except Exception as e:

        logger.error(f'Ошибка при удалении аккаунта: {e}')
    

def set_account(account_id, is_active, engine) -> None:

    sql_text = text("""
        UPDATE accounts
        SET is_active = :is_active
        WHERE id = :account_id; 
    """)

    try:
        with engine.begin() as conn:

            conn.execute(sql_text, {'account_id' : account_id, 'is_active' : is_active})
            logger.info(f'Статус аккаунта изменен: {is_active}')
        
    except Exception as e:

        logger.error(f'Ошибка при изменении статуса аккаунта: {e}')



