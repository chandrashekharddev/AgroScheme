import os
from sqlalchemy import create_engine, text  # ← ADDED 'text' import
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from urllib.parse import urlparse  # For debugging

from app.config import settings

# Get database URL from settings
DATABASE_URL = settings.DATABASE_URL
print(f"🔍 Initial DATABASE_URL (masked): {settings.safe_database_url if hasattr(settings, 'safe_database_url') else DATABASE_URL[:50]}...")

# Fix PostgreSQL URL format if needed
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
    print(f"🔧 Fixed protocol to postgresql://")

# Parse URL for debugging (if PostgreSQL)
if DATABASE_URL and "postgresql" in DATABASE_URL:
    try:
        parsed = urlparse(DATABASE_URL)
        print(f"📊 Parsed URL Details:")
        print(f"   Hostname: {parsed.hostname}")
        print(f"   Port: {parsed.port}")
        print(f"   Username: {parsed.username[:10]}...")
        print(f"   Database: {parsed.path[1:] if parsed.path else 'None'}")
    except:
        pass

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
        print(f"🔧 Added sslmode=require")
    
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
        result = conn.execute(text("SELECT version()"))  # ← FIXED: Added text()
        version = result.fetchone()
        print(f"✅ Database connection successful!")
        print(f"   Database version: {version[0][:50]}...")
        
        if is_postgresql:
            # Get additional PostgreSQL info
            result = conn.execute(text("SELECT current_user, current_database()"))  # ← FIXED: Added text()
            user_info = result.fetchone()
            print(f"   Connected as: {user_info[0]}")
            print(f"   Database: {user_info[1]}")
    
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

# Optional: Add a function to test connection manually
def test_connection():
    """Test database connection manually"""
    try:
        with engine.connect() as conn:
            if is_postgresql:
                result = conn.execute(text("SELECT 1 as test_value, current_timestamp as timestamp"))  # ← FIXED: Added text()
            else:
                result = conn.execute(text("SELECT 1 as test_value, datetime('now') as timestamp"))  # ← FIXED: Added text()
            
            row = result.fetchone()
            print(f"✅ Connection test passed!")
            print(f"   Test value: {row[0]}")
            print(f"   Timestamp: {row[1]}")
            return True
    except Exception as e:
        print(f"❌ Connection test failed: {e}")
        return False

if __name__ == "__main__":
    # Run test if script is executed directly
    test_connection()
