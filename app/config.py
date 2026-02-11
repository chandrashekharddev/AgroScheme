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
        # 1. Ensure postgresql:// protocol (not postgres://)
        if DATABASE_URL.startswith("postgres://"):
            DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
        
        # 2. Ensure SSL is enabled for PostgreSQL in production
        if "postgresql" in DATABASE_URL and "sslmode=" not in DATABASE_URL:
            if "?" in DATABASE_URL:
                DATABASE_URL += "&sslmode=require"
            else:
                DATABASE_URL += "?sslmode=require"
    
    # For debugging - safe URL without password
    @property
    def safe_database_url(self):
        """Return database URL with password masked for security"""
        if "@" in self.DATABASE_URL:
            # Hide password by masking the part before @
            parts = self.DATABASE_URL.split('@', 1)
            return f"postgresql://...@{parts[1]}"
        return self.DATABASE_URL
    
    # Debug method to show database type
    @property
    def database_type(self):
        """Return database type for logging"""
        if "postgresql" in self.DATABASE_URL:
            return "PostgreSQL (Supabase)"
        elif "sqlite" in self.DATABASE_URL:
            return "SQLite"
        else:
            return "Unknown"
    
    # CORS Configuration - UPDATED WITH YOUR VERCEL DOMAINS
    ALLOWED_ORIGINS = [
        # Local development
        "http://localhost:5500",
        "http://127.0.0.1:5500",
        "http://localhost:8000",
        "http://localhost:3000",
        "http://localhost:5173",
        "http://localhost:8080",
        "http://localhost:3001",
        
        # Production frontends
        "https://agroscheme-ai.vercel.app",
        "https://agroscheme.vercel.app",
        "https://agroscheme-backend.vercel.app",
        "https://agroscheme-backend-2.vercel.app",  # Your frontend domain
        
        # Render backend
        "https://agroscheme-6.onrender.com",
        
        # Wildcards for preview deployments
        "https://*.vercel.app",
        "https://*.onrender.com",
        "http://*.localhost",  # For local testing with subdomains
    ]
    
    # Additional CORS settings
    ALLOW_CREDENTIALS = True
    ALLOW_METHODS = ["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"]
    ALLOW_HEADERS = [
        "*",
        "Authorization",
        "Content-Type",
        "Accept",
        "Origin",
        "X-Requested-With",
        "Access-Control-Allow-Headers",
        "Access-Control-Request-Method",
        "Access-Control-Request-Headers",
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
