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
    
    # ✅ FILE UPLOAD SETTINGS (CRITICAL FIXES)
    # Upload directory - always use "uploads" for consistency
    UPLOAD_DIR = "uploads"
    
    # Maximum file size (5MB)
    MAX_FILE_SIZE = 5 * 1024 * 1024
    
    # Allowed file extensions
    ALLOWED_EXTENSIONS = [".jpg", ".jpeg", ".png", ".pdf", ".heic", ".heif", ".webp"]
    
    # ✅ API BASE URL FOR FILE SERVING (MOST IMPORTANT!)
    # This is used to generate file URLs in responses
    @property
    def API_BASE_URL(self):
        """
        Get the base URL for file serving.
        In production (Render), use the Render URL.
        In development, use localhost.
        """
        # Check for environment variable first
        env_url = os.getenv("API_BASE_URL")
        if env_url:
            return env_url.rstrip('/')  # Remove trailing slash
        
        # Check if running on Render
        if "RENDER" in os.environ:
            # Get Render external URL
            render_url = os.getenv("RENDER_EXTERNAL_URL")
            if render_url:
                return render_url.rstrip('/')
        
        # Default to localhost for development
        return "http://localhost:8000"
    
    # ✅ FILE URL HELPER METHOD (add this method)
    def get_file_url(self, file_path: str) -> str:
        """Generate full URL for a file"""
        if not file_path:
            return ""
        
        # Remove leading slash if present
        if file_path.startswith('/'):
            file_path = file_path[1:]
        
        # If it's already a full URL, return as-is
        if file_path.startswith('http'):
            return file_path
        
        # Otherwise, construct URL
        return f"{self.API_BASE_URL}/uploads/{file_path}"
    
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
        "https://agroscheme-backend-2.vercel.app",
        "https://agroscheme-backend-3.vercel.app",
        "https://agroscheme-backend-4.vercel.app",
        "https://agroscheme-backend.vercel.app",
        "https://agroscheme-ai.vercel.app",
        "https://agroscheme.vercel.app",
        
        # Render backend (if you want to allow API-to-API calls)
        "https://agroscheme-6.onrender.com",
        
        # Wildcards for Vercel preview deployments
        "https://*.vercel.app",
        
        # Add wildcard for local development
        "http://localhost:*",
        "http://127.0.0.1:*",
    ]

settings = Settings()
