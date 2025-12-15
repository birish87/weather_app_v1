"""
Database configuration for SQLAlchemy + SQLite.

We intentionally use SQLite because:
- It's trivial to run locally (no extra services needed)
- It satisfies persistence requirements for the assessment
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from .settings import settings

DATABASE_URL = f"sqlite:///{settings.sqlite_path}"

# SQLite needs check_same_thread=False for FastAPI because FastAPI uses threads.
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
)

# Session factory used by dependency injection
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    """Base class for ORM models."""
    pass


def get_db():
    """
    FastAPI dependency that yields a DB session per request,
    then closes it cleanly afterwards.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
