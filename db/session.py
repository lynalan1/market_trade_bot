from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

from config.settings import settings
from infra.logger import setup_logger

logger = setup_logger(__name__)

# движок
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False
)

# фабрика сессий
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False
)

# базовый класс для моделей
class Base(DeclarativeBase):
    pass

# сессия для репозиториев
async def get_session():
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception as e:
            await session.rollback()
            logger.error(f"Ошибка сессии БД: {e}")
            raise
