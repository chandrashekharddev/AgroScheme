# app/config.py - COMPLETE FIXED VERSION
import os
from dotenv import load_dotenv
from typing import List

load_dotenv()

class Settings:
    PROJECT_NAME = "AgroScheme AI"
    PROJECT_VERSION = "1.0.0"
    
    # ✅ Supabase Configuration
    SUPABASE_URL = os.getenv("NEXT_PUBLIC_SUPABASE_URL", "")
    SUPABASE_KEY = os.getenv("NEXT_PUBLIC_SUPABASE_PUBLISHABLE_DEFAULT_KEY", "")
    SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "")
    
    # ✅ Database URL (from Supabase)
    DATABASE_URL = os.getenv("DATABASE_URL", "")
    
    # Fix PostgreSQL URL
    if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
    
    # ✅ CORS Configuration - EXACT origins only
    ALLOWED_ORIGINS: List[str] = [
        # Your Vercel frontend
        "https://agroscheme-backend-2.vercel.app",
        
        # Your Render backend
        "https://agroscheme-6.onrender.com",
        
        # Local development
        "http://localhost:3000",
        "http://localhost:8000",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:8000",
    ]
    
    # ✅ JWT Configuration
    SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-change-in-production")
    ALGORITHM = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "10080"))  # 7 days
    
    # ✅ File Upload Configuration
    MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
    ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".pdf"}
    UPLOAD_DIR = os.getenv("UPLOAD_DIR", "uploads")

settings = Settings()
