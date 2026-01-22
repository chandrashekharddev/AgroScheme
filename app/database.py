# app/database.py
import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# ✅ Fix import: use app.config
from app.config import settings

# Handle PostgreSQL URL format for Render
DATABASE_URL = settings.DATABASE_URL
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# Check if using SQLite
is_sqlite = "sqlite" in DATABASE_URL

# Create engine with appropriate arguments
connect_args = {}
if is_sqlite:
    connect_args = {"check_same_thread": False}
    # Create uploads directory
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)

engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args,
    pool_pre_ping=True if not is_sqlite else False,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()