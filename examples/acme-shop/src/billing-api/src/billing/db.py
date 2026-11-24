from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from billing.settings import settings

engine = create_engine(settings.database_url)
SessionLocal = sessionmaker(engine)
Base = declarative_base()


def get_db():
    with SessionLocal() as db:
        yield db
