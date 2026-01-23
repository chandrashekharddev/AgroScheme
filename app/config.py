# app/config.py - UPDATED FOR RENDER & VERCEL
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
    
    # ✅ UPDATED CORS - ADD YOUR VERCEL FRONTEND HERE
    ALLOWED_ORIGINS = [
        # Local development
        "http://localhost:5500",
        "http://127.0.0.1:5500",
        "http://localhost:8000",
        "http://localhost:3000",
        "http://localhost:5173",
        "http://localhost:8080",
        
        # ✅ YOUR VERCEL FRONTEND
        "https://agroscheme-backend-1.vercel.app",
        "https://agroscheme-backend.vercel.app",
        "https://agroscheme-ai.vercel.app",
        "https://agroscheme.vercel.app",
        
        # Render backend (if you want to allow API-to-API calls)
        "https://agroscheme-6.onrender.com",
        
        # Wildcards for Vercel preview deployments
        "https://*.vercel.app",
    ]

settings = Settings()