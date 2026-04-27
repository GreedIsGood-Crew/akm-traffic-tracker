import os
import psycopg2
from psycopg2.extras import RealDictCursor

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session, declarative_base

from models.user import UserORM

Base = declarative_base()

_db_user = os.getenv("DB_USER", "tracker")
_db_pass = os.getenv("DB_PASSWORD", "tracker_local_dev")
_db_host = os.getenv("DB_HOST", "tracker-postgres")
_db_name = os.getenv("DB_NAME", "tracker")
_db_port = os.getenv("DB_PORT", "5432")
DATABASE_URL = f"postgresql+psycopg2://{_db_user}:{_db_pass}@{_db_host}:{_db_port}/{_db_name}"

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


# Функция подключения к базе
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_user(db: Session, username: str):
    return db.query(UserORM).filter(UserORM.username == username).first()
