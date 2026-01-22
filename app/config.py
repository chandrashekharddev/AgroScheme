# app/config.py - UPDATED FOR RENDER
import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    PROJECT_NAME = "AgroScheme AI"
    PROJECT_VERSION = "1.0.0"
    
    # ✅ RENDER FIX: Handle both SQLite and PostgreSQL
    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./agroscheme.db")
    
    # Fix for Render's PostgreSQL URL (postgres:// → postgresql://)
    if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
    
    # JWT
    SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-change-in-production")
    ALGORITHM = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES = 30
    
    # Gemini AI
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
    
    # File Upload
    MAX_FILE_SIZE = 5 * 1024 * 1024
    ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".pdf"}
    UPLOAD_DIR = "uploads"
    
    # CORS - Add your Render URL here after deployment
    ALLOWED_ORIGINS = [
        "http://localhost:5500",
        "http://127.0.0.1:5500",
        "http://localhost:8000",
        "http://localhost:3000",
        # Add after deployment:
        # "https://agroscheme-backend.onrender.com",
        # "https://your-frontend.onrender.com",
    ]

settings = Settings()