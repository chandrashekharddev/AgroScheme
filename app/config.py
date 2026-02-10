# app/config.py - UPDATED FOR SUPABASE + RENDER
import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    PROJECT_NAME = "AgroScheme AI"
    PROJECT_VERSION = "1.0.0"
    
    # ✅ SUPABASE DATABASE URL
    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./agroscheme.db")
    
    # Fix PostgreSQL URL format
    if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
    
    # ✅ SUPABASE CONFIG
    SUPABASE_URL = "https://noalqaipwonqiiuccjdr.supabase.co"
    SUPABASE_KEY = "sb_publishable_6PrxUZbYma92m2amhLuBTg_0-Y3_xy_"
    
    # JWT
    SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-change-in-production")
    ALGORITHM = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
    
    # Gemini AI
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
    
    # File Upload - Use /tmp/uploads for Render
    MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
    ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".pdf"}
    UPLOAD_DIR = os.getenv("UPLOAD_DIR", "/tmp/uploads")
    
    # ✅ UPDATED CORS - Add your Render URL
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
        "https://agroscheme-backend-2.vercel.app",
        "https://agroscheme-backend-3.vercel.app",
        "https://agroscheme-backend-4.vercel.app",
        "https://agroscheme-backend.vercel.app",
        "https://agroscheme-ai.vercel.app",
        "https://agroscheme.vercel.app",
        
        # ✅ YOUR RENDER BACKEND (Add your actual Render URL here)
        "https://agroscheme-6.onrender.com",
        
        # Wildcards
        "https://*.vercel.app",
        "https://*.onrender.com",
    ]

settings = Settings()
