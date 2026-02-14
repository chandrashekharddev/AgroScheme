from pydantic import BaseModel, EmailStr, field_validator, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum

class AdminDashboardStats(BaseModel):
    total_farmers: int
    total_applications: int
    total_schemes: int
    benefits_distributed: float
    pending_verifications: int
    ai_accuracy: float
    farmer_growth: float
    application_growth: float
    scheme_growth: float
    benefit_growth: float
    accuracy_growth: float
    recent_registrations: List[Dict[str, Any]]
    top_schemes: List[Dict[str, Any]]

    class Config:
        from_attributes = True
        
class UserRole(str, Enum):
    FARMER = "farmer"
    ADMIN = "admin"

class DocumentType(str, Enum):
    AADHAAR = "aadhaar"
    PAN = "pan"
    LAND_RECORD = "land_record"
    BANK_PASSBOOK = "bank_passbook"
    INCOME_CERTIFICATE = "income_certificate"
    DOMICILE = "domicile"
    OTHER = "other"

class ApplicationStatus(str, Enum):
    PENDING = "PENDING"
    UNDER_REVIEW = "UNDER_REVIEW"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    DOCS_NEEDED = "DOCS_NEEDED"

class SchemeType(str, Enum):
    CENTRAL = "central"
    STATE = "state"

class UserBase(BaseModel):
    full_name: str
    mobile_number: str
    email: Optional[EmailStr] = None
    state: str
    district: str
    village: Optional[str] = None
    language: Optional[str] = "en"
    
    @field_validator('mobile_number')
    def validate_mobile_number(cls, v):
        if not v.isdigit() or len(v) != 10:
            raise ValueError('Mobile number must be 10 digits')
        return v

class UserCreate(UserBase):
    password: str
    # Personal details
    aadhaar_number: Optional[str] = None
    
    # Farm details
    total_land_acres: Optional[float] = None
    land_type: Optional[str] = None
    main_crops: Optional[str] = None
    annual_income: Optional[float] = None
    
    # Bank details
    bank_account_number: Optional[str] = None
    bank_name: Optional[str] = None
    ifsc_code: Optional[str] = None
    
    @field_validator('password')
    def validate_password(cls, v):
        if len(v) < 6:
            raise ValueError('Password must be at least 6 characters')
        return v
    
    @field_validator('aadhaar_number')
    def validate_aadhaar(cls, v):
        if v and (not v.isdigit() or len(v) != 12):
            raise ValueError('Aadhaar number must be 12 digits')
        return v

class UserLogin(BaseModel):
    mobile_number: str
    password: str

class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    email: Optional[EmailStr] = None
    state: Optional[str] = None
    district: Optional[str] = None
    village: Optional[str] = None
    language: Optional[str] = None
    aadhaar_number: Optional[str] = None
    total_land_acres: Optional[float] = None
    land_type: Optional[str] = None
    main_crops: Optional[str] = None
    annual_income: Optional[float] = None
    bank_account_number: Optional[str] = None
    bank_name: Optional[str] = None
    ifsc_code: Optional[str] = None
    auto_apply_enabled: Optional[bool] = None
    email_notifications: Optional[bool] = None
    sms_notifications: Optional[bool] = None
    
    class Config:
        from_attributes = True

class UserResponse(UserBase):
    id: int
    farmer_id: str
    role: UserRole
    aadhaar_number: Optional[str] = None
    total_land_acres: Optional[float] = None
    land_type: Optional[str] = None
    main_crops: Optional[str] = None
    annual_income: Optional[float] = None
    bank_account_number: Optional[str] = None
    bank_name: Optional[str] = None
    ifsc_code: Optional[str] = None
    bank_verified: bool
    auto_apply_enabled: bool
    created_at: datetime
    
    class Config:
        from_attributes = True

class Token(BaseModel):
    access_token: str
    token_type: str
    user: UserResponse

class DocumentBase(BaseModel):
    document_type: DocumentType

class DocumentCreate(DocumentBase):
    pass

class DocumentResponse(DocumentBase):
    id: int
    user_id: int
    file_name: str
    file_size: int
    file_path: Optional[str] = None
    file_url: Optional[str] = None
    extracted_data: Optional[Dict[str, Any]] = None
    verified: bool
    uploaded_at: datetime
    
    class Config:
        from_attributes = True

class SchemeBase(BaseModel):
    scheme_name: str
    scheme_code: str
    description: str
    scheme_type: str
    department: str = "Agriculture"
    benefit_amount: Optional[str] = None
    last_date: Optional[datetime] = None
    is_active: bool = True
    eligibility_criteria: Dict[str, Any]
    required_documents: List[str]

class SchemeCreate(SchemeBase):
    pass

class SchemeResponse(SchemeBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True

class ApplicationBase(BaseModel):
    scheme_id: int

class ApplicationResponse(BaseModel):
    id: int
    user_id: int
    scheme_id: int
    application_id: str
    status: ApplicationStatus
    applied_amount: Optional[float] = None
    approved_amount: Optional[float] = None
    application_data: Dict[str, Any]
    submitted_documents: Optional[List[int]] = None
    applied_at: datetime
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True

class NotificationBase(BaseModel):
    title: str
    message: str
    notification_type: str
    related_scheme_id: Optional[int] = None
    related_application_id: Optional[int] = None

class NotificationResponse(NotificationBase):
    id: int
    user_id: int
    read: bool
    created_at: datetime
    
    class Config:
        from_attributes = True

class EligibilityCheck(BaseModel):
    scheme_id: int
    user_id: int
    eligible: bool
    match_percentage: float
    missing_documents: List[str]
    reasons: List[str]

class AdminStats(BaseModel):
    total_farmers: int
    total_applications: int
    total_schemes: int
    benefits_distributed: float
    pending_verifications: int
    ai_accuracy: float
