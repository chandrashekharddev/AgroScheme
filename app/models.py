# app/models.py - COMPLETE FILE WITH OCR FIELDS
from sqlalchemy import Column, Integer, String, Boolean, Float, DateTime, Text, ForeignKey, JSON, Enum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum
from app.database import Base

class UserRole(str, enum.Enum):
    FARMER = "farmer"
    ADMIN = "admin"

class DocumentType(str, enum.Enum):
    AADHAAR = "aadhaar"
    PAN = "pan"
    LAND_RECORD = "land_record"
    BANK_PASSBOOK = "bank_passbook"
    INCOME_CERTIFICATE = "income_certificate"
    CASTE_CERTIFICATE = "caste_certificate"
    DOMICILE = "domicile"
    CROP_INSURANCE = "crop_insurance"
    DEATH_CERTIFICATE = "death_certificate"
    OTHER = "other"

class ApplicationStatus(str, enum.Enum):
    PENDING = "PENDING"              
    UNDER_REVIEW = "UNDER_REVIEW"  
    APPROVED = "APPROVED"           
    REJECTED = "REJECTED"          
    DOCS_NEEDED = "DOCS_NEEDED"     
    COMPLETED = "COMPLETED"       

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String(100), nullable=False)
    mobile_number = Column(String(10), unique=True, index=True, nullable=False)
    email = Column(String(100), unique=True, index=True)
    password_hash = Column(String(255), nullable=False)
    state = Column(String(50), nullable=False)
    district = Column(String(50), nullable=False)
    village = Column(String(50))
    language = Column(String(10), default="en")
    farmer_id = Column(String(20), unique=True, index=True)
    role = Column(Enum(UserRole), default=UserRole.FARMER)
    total_land_acres = Column(Float)
    land_type = Column(String(50))
    main_crops = Column(String(200))
    annual_income = Column(Float)
    bank_account_number = Column(String(20))
    bank_name = Column(String(100))
    ifsc_code = Column(String(11))
    bank_verified = Column(Boolean, default=False)
    auto_apply_enabled = Column(Boolean, default=True)
    email_notifications = Column(Boolean, default=True)
    sms_notifications = Column(Boolean, default=True)
    aadhaar_number = Column(String(12), nullable=True)
    pan_number = Column(String(10), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    documents = relationship("Document", back_populates="user", cascade="all, delete-orphan")
    applications = relationship("Application", back_populates="user", cascade="all, delete-orphan")
    notifications = relationship("Notification", back_populates="user", cascade="all, delete-orphan")

class Document(Base):
    __tablename__ = "documents"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    document_type = Column(Enum(DocumentType), nullable=False)
    file_path = Column(String(500), nullable=False)
    file_name = Column(String(200))
    file_size = Column(Integer)
    
    # ✅ OCR EXTRACTION FIELDS
    extraction_status = Column(String(20), default="pending")  # pending, processing, completed, failed, partial
    extraction_table = Column(String(50), nullable=True)  # Which table data was inserted into (aadhaar_documents, etc.)
    extraction_id = Column(Integer, nullable=True)  # ID in that specific document table
    extraction_data = Column(JSON, nullable=True)  # Backup of extracted data (raw OCR output)
    extraction_error = Column(Text, nullable=True)  # Error message if failed
    confidence_score = Column(Float, nullable=True)  # OCR confidence score (0-1)
    
    # ✅ VERIFICATION FIELDS
    verified = Column(Boolean, default=False)
    verified_by = Column(Integer, ForeignKey("users.id"), nullable=True)  # Admin who verified
    verification_date = Column(DateTime(timezone=True), nullable=True)
    verification_notes = Column(Text, nullable=True)
    
    # ✅ TIMESTAMPS
    uploaded_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    user = relationship("User", back_populates="documents")
    verifier = relationship("User", foreign_keys=[verified_by])

class GovernmentScheme(Base):
    __tablename__ = "government_schemes"
    
    id = Column(Integer, primary_key=True, index=True)
    scheme_name = Column(String(200), nullable=False)
    scheme_code = Column(String(50), unique=True, index=True)
    description = Column(Text)
    scheme_type = Column(String(50), nullable=False, default="central")  # central, state, district
    benefit_amount = Column(String(100))  # Can be string like "₹5000/month" or number
    benefit_type = Column(String(50), default="cash")  # cash, subsidy, scholarship, etc.
    last_date = Column(DateTime(timezone=True), nullable=True)
    is_active = Column(Boolean, default=True)
    department = Column(String(100), default="Agriculture")
    
    # ✅ ELIGIBILITY CRITERIA (JSON)
    eligibility_criteria = Column(JSON, nullable=False, default={})
    # Example:
    # {
    #   "age_min": 18,
    #   "age_max": 60,
    #   "land_holding_min": 1,
    #   "annual_income_max": 50000,
    #   "caste_allowed": ["SC", "ST", "OBC"],
    #   "gender": "all",
    #   "marital_status": "all"
    # }
    
    # ✅ REQUIRED DOCUMENTS (JSON array)
    required_documents = Column(JSON, nullable=False, default=[])
    # Example: ["aadhaar", "land_record", "income_certificate"]
    
    # ✅ APPLICATION COUNTER
    total_applications = Column(Integer, default=0)
    approved_applications = Column(Integer, default=0)
    rejected_applications = Column(Integer, default=0)
    
    created_by = Column(String(100), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    applications = relationship("Application", back_populates="scheme", cascade="all, delete-orphan")

class Application(Base):
    __tablename__ = "applications"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    scheme_id = Column(Integer, ForeignKey("government_schemes.id"), nullable=False)
    application_id = Column(String(50), unique=True, index=True)  # User-friendly application number
    
    # ✅ STATUS
    status = Column(Enum(ApplicationStatus), default=ApplicationStatus.PENDING)
    
    # ✅ AMOUNTS
    applied_amount = Column(Float, nullable=True)
    approved_amount = Column(Float, nullable=True)
    disbursed_amount = Column(Float, nullable=True)
    
    # ✅ APPLICATION DATA (JSON)
    application_data = Column(JSON, nullable=False, default={})
    # Stores all form data submitted by user
    
    # ✅ DOCUMENTS SUBMITTED (JSON array of document IDs)
    submitted_documents = Column(JSON, default=[])
    
    # ✅ STATUS HISTORY (JSON array)
    status_history = Column(JSON, default=[])
    # Example: [
    #   {"status": "PENDING", "timestamp": "2024-01-01", "note": "Application submitted"},
    #   {"status": "UNDER_REVIEW", "timestamp": "2024-01-02", "note": "Verification started"}
    # ]
    
    # ✅ ELIGIBILITY CHECK RESULT
    eligibility_result = Column(JSON, nullable=True)
    # Stores the result from eligibility checker
    
    # ✅ APPROVAL DETAILS
    approved_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    approved_at = Column(DateTime(timezone=True), nullable=True)
    approval_notes = Column(Text, nullable=True)
    
    # ✅ REJECTION DETAILS
    rejected_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    rejected_at = Column(DateTime(timezone=True), nullable=True)
    rejection_reason = Column(Text, nullable=True)
    
    # ✅ TIMESTAMPS
    applied_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    user = relationship("User", back_populates="applications")
    scheme = relationship("GovernmentScheme", back_populates="applications")
    approver = relationship("User", foreign_keys=[approved_by])
    rejecter = relationship("User", foreign_keys=[rejected_by])
    
    # Notifications for this application
    notifications = relationship("Notification", back_populates="application", cascade="all, delete-orphan")

class Notification(Base):
    __tablename__ = "notifications"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # ✅ NOTIFICATION CONTENT
    title = Column(String(200), nullable=False)
    message = Column(Text, nullable=False)
    notification_type = Column(String(50))  # scheme_alert, application_update, document_verified, auto_apply, etc.
    
    # ✅ RELATED ENTITIES
    related_scheme_id = Column(Integer, ForeignKey("government_schemes.id"), nullable=True)
    related_application_id = Column(Integer, ForeignKey("applications.id"), nullable=True)
    
    # ✅ STATUS
    read = Column(Boolean, default=False)
    read_at = Column(DateTime(timezone=True), nullable=True)
    
    # ✅ ACTION (optional deep link)
    action_url = Column(String(500), nullable=True)  # URL to navigate when clicked
    action_text = Column(String(100), nullable=True)  # Button text like "View Application"
    
    # ✅ PRIORITY
    priority = Column(String(20), default="normal")  # high, normal, low
    
    # ✅ TIMESTAMPS
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    user = relationship("User", back_populates="notifications")
    scheme = relationship("GovernmentScheme")
    application = relationship("Application", back_populates="notifications")

class AuditLog(Base):
    __tablename__ = "audit_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    action = Column(String(100), nullable=False)  # CREATE, UPDATE, DELETE, VIEW, LOGIN, LOGOUT
    entity_type = Column(String(50), nullable=False)  # User, Document, Scheme, Application
    entity_id = Column(Integer, nullable=True)
    old_values = Column(JSON, nullable=True)
    new_values = Column(JSON, nullable=True)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(200), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    user = relationship("User")
