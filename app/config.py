# app/config.py - UPDATED FOR RENDER & VERCEL
import os
from dotenv import load_dotenv
from pathlib import Path

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
    
    # ==================== USER-SPECIFIC UPLOAD DIRECTORIES ====================
    
    @property
    def UPLOAD_ROOT(self) -> Path:
        """Get absolute path to uploads root directory"""
        return Path.cwd() / self.UPLOAD_DIR
    
    def get_user_upload_dir(self, user_id: int, farmer_id: str = None) -> Path:
        """
        Get user-specific upload directory.
        Creates directory if it doesn't exist.
        
        Args:
            user_id: Database user ID
            farmer_id: Farmer ID (preferred for folder name)
        
        Returns:
            Path object to user's upload directory
        """
        # Ensure uploads root exists
        self.UPLOAD_ROOT.mkdir(exist_ok=True)
        
        # Determine folder name
        if farmer_id:
            # Use farmer_id, sanitize for filesystem
            folder_name = "farmer_" + farmer_id.replace('/', '_').replace('\\', '_')
        else:
            folder_name = f"user_{user_id}"
        
        user_dir = self.UPLOAD_ROOT / folder_name
        user_dir.mkdir(exist_ok=True)
        
        # Create .gitkeep to maintain folder structure
        gitkeep = user_dir / ".gitkeep"
        if not gitkeep.exists():
            gitkeep.touch()
        
        return user_dir
    
    def get_user_folder_name(self, user_id: int, farmer_id: str = None) -> str:
        """Get folder name for user (without full path)"""
        if farmer_id:
            return f"farmer_{farmer_id.replace('/', '_').replace('\\', '_')}"
        return f"user_{user_id}"
    
    def get_relative_path(self, filename: str, user_id: int, farmer_id: str = None) -> str:
        """Generate relative path for database storage"""
        folder_name = self.get_user_folder_name(user_id, farmer_id)
        return f"{folder_name}/{filename}"
    
    def get_absolute_path(self, relative_path: str) -> Path:
        """Convert relative path to absolute path"""
        if not relative_path:
            return None
        
        # Handle already absolute paths
        if os.path.isabs(relative_path):
            return Path(relative_path)
        
        return self.UPLOAD_ROOT / relative_path
    
    # ✅ FILE URL HELPER METHOD (UPDATED)
    def get_file_url(self, file_path: str) -> str:
        """Generate full URL for a file"""
        if not file_path:
            return ""
        
        # If it's already a full URL, return as-is
        if file_path.startswith(('http://', 'https://')):
            return file_path
        
        # Remove leading slash if present
        if file_path.startswith('/'):
            file_path = file_path[1:]
        
        # Construct URL with uploads prefix
        return f"{self.API_BASE_URL}/uploads/{file_path}"
    
    def sanitize_filename(self, filename: str) -> str:
        """Sanitize filename to remove dangerous characters"""
        # Keep only safe characters
        safe_chars = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-")
        safe_name = ''.join(c for c in filename if c in safe_chars)
        
        # If empty after sanitization, use default
        if not safe_name:
            safe_name = "document"
            
        return safe_name
    
    # ✅ DEBUG METHOD: List all user uploads
    def list_user_uploads(self, user_id: int = None, farmer_id: str = None):
        """List files in user's upload directory (for debugging)"""
        user_dir = self.get_user_upload_dir(
            user_id=user_id if user_id else 0,
            farmer_id=farmer_id
        )
        
        if not user_dir.exists():
            return []
        
        files = []
        for file_path in user_dir.iterdir():
            if file_path.is_file() and file_path.name != ".gitkeep":
                files.append({
                    "name": file_path.name,
                    "size": file_path.stat().st_size,
                    "path": str(file_path.relative_to(self.UPLOAD_ROOT)),
                    "url": self.get_file_url(str(file_path.relative_to(self.UPLOAD_ROOT)))
                })
        
        return files
    
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

# Create uploads directory on startup
if __name__ == "__main__":
    # Create main uploads directory
    settings.UPLOAD_ROOT.mkdir(exist_ok=True)
    
    # Create .gitkeep in root uploads
    gitkeep = settings.UPLOAD_ROOT / ".gitkeep"
    if not gitkeep.exists():
        gitkeep.touch()
    
    print(f"Uploads directory: {settings.UPLOAD_ROOT}")
    print(f"Uploads directory exists: {settings.UPLOAD_ROOT.exists()}")
