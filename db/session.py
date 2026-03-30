from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from config.settings import DB_URL
from infra.logger import setup_logger

logger = setup_logger(__name__)


engine = create_engine(
    DB_URL,
    echo=False,             
)

SessionLocal = sessionmaker(bind=engine)


from sqlalchemy.orm import DeclarativeBase
class Base(DeclarativeBase):
    pass