import os

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base


DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./ai_interview.db")

engine = create_engine(
    DATABASE_URL,
    echo=False,
    pool_pre_ping=True,
    pool_recycle=1800,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
