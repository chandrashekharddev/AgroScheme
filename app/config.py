from pydantic_settings import BaseSettings
from typing import List, Dict, Set
import os
from dotenv import load_dotenv

load_dotenv()

class Settings(BaseSettings):
    # App Settings
    APP_NAME: str = "AgroScheme API"
    DEBUG: bool = False
    API_V1_STR: str = "/api/v1"
    
    # Database
    DATABASE_URL: str = os.getenv("DATABASE_URL", "")
    
    # Security
    SECRET_KEY: str = os.getenv("SECRET_KEY", "your-secret-key-here")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # Supabase Storage
    SUPABASE_URL: str = os.getenv("SUPABASE_URL", "")
    SUPABASE_KEY: str = os.getenv("SUPABASE_KEY", "")
    SUPABASE_BUCKET: str = "farmer-documents"
    
    # File Upload Settings
    MAX_FILE_SIZE: int = 10 * 1024 * 1024  # 10MB
    ALLOWED_EXTENSIONS: Set = {'.pdf', '.jpg', '.jpeg', '.png', '.tiff', '.bmp'}
    
    # OCR Settings
    OCR_ENGINE: str = "paddle"  # paddle, easyocr, tesseract
    OCR_LANG: str = "en"  # English (can add 'hi' for Hindi)
    OCR_USE_GPU: bool = False  # Set to True if you have GPU
    OCR_BATCH_SIZE: int = 4
    OCR_CONFIDENCE_THRESHOLD: float = 0.7
    
    # Layout Parser Settings
    USE_LAYOUT_PARSER: bool = True
    LAYOUT_MODEL: str = "lp://PubLayNet/faster_rcnn_r50_fpn_dcn"  # For document layout
    
    # Document Types
    DOCUMENT_TYPES: List = [
        "aadhaar",
        "pan",
        "land_record",
        "bank_passbook",
        "income_certificate",
        "caste_certificate",
        "domicile",
        "crop_insurance",
        "death_certificate"
    ]
    
    # Document to Table Mapping
    DOCUMENT_TABLE_MAP: Dict = {
        "aadhaar": "aadhaar_documents",
        "pan": "pan_documents",
        "land_record": "land_records",
        "bank_passbook": "bank_documents",
        "income_certificate": "income_certificates",
        "caste_certificate": "caste_certificates",
        "domicile": "domicile_certificates",
        "crop_insurance": "crop_insurance_docs",
        "death_certificate": "death_certificates"
    }
    
    # Field mappings for each document type
    DOCUMENT_FIELD_MAPPINGS: Dict = {
        "aadhaar": {
            "required": ["aadhaar_number", "full_name"],
            "optional": ["date_of_birth", "gender", "address", "pincode", "father_name", "mobile_number", "email"],
            "patterns": {
                "aadhaar_number": r'\d{4}\s?\d{4}\s?\d{4}',
                "pincode": r'\d{6}',
                "mobile": r'\d{10}'
            }
        },
        "pan": {
            "required": ["pan_number", "full_name"],
            "optional": ["father_name", "date_of_birth", "pan_type"],
            "patterns": {
                "pan_number": r'[A-Z]{5}[0-9]{4}[A-Z]{1}'
            }
        },
        "land_record": {
            "required": ["survey_number", "owner_name"],
            "optional": ["land_area_acres", "land_area_hectares", "land_type", "co_owners", 
                        "village_name", "taluka", "district", "state", "crop_pattern", "irrigation_source"]
        },
        "bank_passbook": {
            "required": ["account_number", "ifsc_code", "account_holder_name"],
            "optional": ["bank_name", "branch_name", "account_type", "micr_code"],
            "patterns": {
                "ifsc_code": r'[A-Z]{4}0[A-Z0-9]{6}',
                "micr_code": r'\d{9}'
            }
        }
    }
    
    class Config:
        case_sensitive = True

settings = Settings()
