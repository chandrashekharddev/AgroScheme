# app/database.py - SIMPLIFIED VERSION
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os

from config import settings

# ✅ Use regular sqlite, not aiosqlite
DATABASE_URL = settings.DATABASE_URL.replace("aiosqlite", "sqlite") if "aiosqlite" in settings.DATABASE_URL else settings.DATABASE_URL

# Create uploads directory
os.makedirs(settings.UPLOAD_DIR, exist_ok=True)

# ✅ Create engine WITHOUT async
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False}  # Only for SQLite
)

# ✅ Create session
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

# ✅ Dependency for database sessions
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()