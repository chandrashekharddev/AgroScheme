import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    PROJECT_NAME = "AgroScheme AI"
    PROJECT_VERSION = "1.0.0"
    
    # Database Configuration
    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./agroscheme.db")
    
    # Fix common PostgreSQL issues
    if DATABASE_URL:
        if DATABASE_URL.startswith("postgres://"):
            DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
        
        if "postgresql" in DATABASE_URL and "sslmode=" not in DATABASE_URL:
            if "?" in DATABASE_URL:
                DATABASE_URL += "&sslmode=require"
            else:
                DATABASE_URL += "?sslmode=require"
    
    # CORS Configuration - FIXED
    ALLOWED_ORIGINS = [
        # Your Vercel frontend
        "https://agroscheme-backend-2.vercel.app",
        
        # For Vercel deployments
        "https://*.vercel.app",
        
        # Your Render backend
        "https://agroscheme-6.onrender.com",
        
        # Local development
        "http://localhost:5500",
        "http://127.0.0.1:5500",
        "http://localhost:3000",
        "http://localhost:5173",
        "http://localhost:8080",
        "http://localhost:8000",
    ]
    
    # JWT Configuration
    SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-change-in-production")
    ALGORITHM = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
    
    # File Upload Configuration
    MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
    ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".pdf"}
    UPLOAD_DIR = os.getenv("UPLOAD_DIR", "uploads")

settings = Settings()
