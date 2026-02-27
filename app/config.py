# app/config.py - COMPLETE FIXED VERSION (NO GEMINI OCR)
import os
from dotenv import load_dotenv
from typing import List, Dict

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
        "https://agroscheme-app.vercel.app",
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
    
    # ==================== GEMINI AI (ONLY FOR ELIGIBILITY CHECKING) ====================
    # ✅ Keep Gemini ONLY for eligibility checking (not for OCR)
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
    
    # ==================== FREE OCR CONFIGURATION ====================
    # ✅ OCR Engine Selection - Purely FREE!
    OCR_ENGINE: str = os.getenv("OCR_ENGINE", "paddle")  # "paddle" or "easyocr"
    OCR_USE_GPU: bool = os.getenv("OCR_USE_GPU", "false").lower() == "true"
    OCR_CONFIDENCE_THRESHOLD: float = float(os.getenv("OCR_CONFIDENCE_THRESHOLD", "0.5"))
    
    # ✅ OCR Languages (Indian languages supported)
    OCR_LANGUAGES: List[str] = [
        "en",  # English
        "hi",  # Hindi
        "mr",  # Marathi
        "ta",  # Tamil
        "te",  # Telugu
        "bn",  # Bengali
        "gu",  # Gujarati
        "kn",  # Kannada
        "ml",  # Malayalam
        "or",  # Odia
        "pa",  # Punjabi
        "ur"   # Urdu
    ]
    
    # ✅ Document types supported
    DOCUMENT_TYPES: List[str] = [
        'aadhaar',
        'pan',
        'land_record',
        'bank_passbook',
        'income_certificate',
        'caste_certificate',
        'domicile',
        'crop_insurance',
        'death_certificate'
    ]
    
    # ✅ Map document types to database tables
    DOCUMENT_TABLE_MAP: dict = {
        'aadhaar': 'aadhaar_documents',
        'pan': 'pan_documents',
        'land_record': 'land_records',
        'bank_passbook': 'bank_documents',
        'income_certificate': 'income_certificates',
        'caste_certificate': 'caste_certificates',
        'domicile': 'domicile_certificates',
        'crop_insurance': 'crop_insurance_docs',
        'death_certificate': 'death_certificates'
    }
    
    # ✅ Auto-apply settings
    AUTO_APPLY_ENABLED: bool = True
    AUTO_APPLY_CHECK_INTERVAL: int = 3600  # Check every hour (in seconds)

settings = Settings()
