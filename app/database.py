import os
from sqlalchemy import create_engine, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from urllib.parse import urlparse

from app.config import settings

# Get database URL from settings
DATABASE_URL = settings.DATABASE_URL

# Debug info
print(f"🔍 Database Type: {settings.database_type}")
if hasattr(settings, 'safe_database_url'):
    print(f"🔍 Database URL (masked): {settings.safe_database_url}")

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
    print("📁 Using SQLite database")
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
        "sslmode": "require"
    }
    print("📊 Using PostgreSQL database")

# Create the engine
try:
    engine = create_engine(
        DATABASE_URL,
        connect_args=connect_args,
        pool_pre_ping=True,  # Verify connections before using
        pool_recycle=300,    # Recycle connections every 5 minutes
        echo=False,          # Set to True for SQL debugging
        pool_size=5,
        max_overflow=10
    )
    
    # Test connection immediately - USING text() for raw SQL
    print("🔌 Testing database connection...")
    with engine.connect() as conn:
        result = conn.execute(text("SELECT version()"))
        version = result.fetchone()
        print(f"✅ Database connection successful!")
        print(f"   Database version: {version[0][:50]}...")
        
        if is_postgresql:
            # Get additional PostgreSQL info
            result = conn.execute(text("SELECT current_user, current_database(), current_timestamp"))
            user_info = result.fetchone()
            print(f"   Connected as: {user_info[0]}")
            print(f"   Database: {user_info[1]}")
            print(f"   Connection time: {user_info[2]}")
    
except Exception as e:
    print(f"❌ Failed to create database engine: {e}")
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

# Test connection function
def test_connection():
    """Test database connection manually"""
    try:
        with engine.connect() as conn:
            if is_postgresql:
                result = conn.execute(text("SELECT 1 as test_value, current_timestamp as timestamp"))
            else:
                result = conn.execute(text("SELECT 1 as test_value, datetime('now') as timestamp"))
            
            row = result.fetchone()
            print(f"✅ Connection test passed!")
            return True
    except Exception as e:
        print(f"❌ Connection test failed: {e}")
        return False
