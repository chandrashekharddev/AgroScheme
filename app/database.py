import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from app.config import settings

# Get database URL from settings
DATABASE_URL = settings.DATABASE_URL

# Fix PostgreSQL URL format if needed
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# Determine database type
is_postgresql = "postgresql" in DATABASE_URL
is_sqlite = "sqlite" in DATABASE_URL

# Create engine with appropriate configuration
connect_args = {}
if is_sqlite:
    # SQLite configuration
    connect_args = {"check_same_thread": False}
    # Ensure uploads directory exists
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
elif is_postgresql:
    # PostgreSQL configuration for Supabase
    # Ensure SSL is required
    if "sslmode=" not in DATABASE_URL:
        if "?" in DATABASE_URL:
            DATABASE_URL += "&sslmode=require"
        else:
            DATABASE_URL += "?sslmode=require"
    
    # PostgreSQL connection arguments
    connect_args = {
        "connect_timeout": 10,
        "keepalives": 1,
        "keepalives_idle": 30,
    }

# Create the engine
try:
    engine = create_engine(
        DATABASE_URL,
        connect_args=connect_args,
        pool_pre_ping=True,  # Verify connections before using
        pool_recycle=300,    # Recycle connections every 5 minutes
        echo=False           # Set to True for SQL debugging
    )
    print(f"✅ Database engine created for {'PostgreSQL' if is_postgresql else 'SQLite'}")
except Exception as e:
    print(f"❌ Failed to create database engine: {e}")
    # Fallback to SQLite in memory
    print("🔄 Falling back to in-memory SQLite")
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False}
    )

# Create session and base
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    """
    Dependency to get database session.
    Use this in your route dependencies.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
