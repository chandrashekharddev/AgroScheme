# app/models.py - FIXED with explicit foreign keys
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
    
    # Relationships - FIXED with explicit foreign_keys
    documents = relationship("Document", back_populates="user", foreign_keys="[Document.user_id]", cascade="all, delete-orphan")
    applications = relationship("Application", back_populates="user", foreign_keys="[Application.user_id]", cascade="all, delete-orphan")
    notifications = relationship("Notification", back_populates="user", foreign_keys="[Notification.user_id]", cascade="all, delete-orphan")

class Document(Base):
    __tablename__ = "documents"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    document_type = Column(Enum(DocumentType), nullable=False)
    file_path = Column(String(500), nullable=False)
    file_name = Column(String(200))
    file_size = Column(Integer)
    
    # ✅ OCR EXTRACTION FIELDS
    extraction_status = Column(String(20), default="pending")
    extraction_table = Column(String(50), nullable=True)
    extraction_id = Column(Integer, nullable=True)
    extraction_data = Column(JSON, nullable=True)
    extraction_error = Column(Text, nullable=True)
    confidence_score = Column(Float, nullable=True)
    
    # ✅ VERIFICATION FIELDS
    verified = Column(Boolean, default=False)
    verified_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    verification_date = Column(DateTime(timezone=True), nullable=True)
    verification_notes = Column(Text, nullable=True)
    
    # ✅ TIMESTAMPS
    uploaded_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships - FIXED with explicit foreign_keys
    user = relationship("User", back_populates="documents", foreign_keys=[user_id])
    verifier = relationship("User", foreign_keys=[verified_by])

class GovernmentScheme(Base):
    __tablename__ = "government_schemes"
    
    id = Column(Integer, primary_key=True, index=True)
    scheme_name = Column(String(200), nullable=False)
    scheme_code = Column(String(50), unique=True, index=True)
    description = Column(Text)
    scheme_type = Column(String(50), nullable=False, default="central")
    benefit_amount = Column(String(100))
    benefit_type = Column(String(50), default="cash")
    last_date = Column(DateTime(timezone=True), nullable=True)
    is_active = Column(Boolean, default=True)
    department = Column(String(100), default="Agriculture")
    
    eligibility_criteria = Column(JSON, nullable=False, default={})
    required_documents = Column(JSON, nullable=False, default=[])
    
    total_applications = Column(Integer, default=0)
    approved_applications = Column(Integer, default=0)
    rejected_applications = Column(Integer, default=0)
    
    created_by = Column(String(100), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    applications = relationship("Application", back_populates="scheme", foreign_keys="[Application.scheme_id]", cascade="all, delete-orphan")

class Application(Base):
    __tablename__ = "applications"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    scheme_id = Column(Integer, ForeignKey("government_schemes.id"), nullable=False)
    application_id = Column(String(50), unique=True, index=True)
    
    status = Column(Enum(ApplicationStatus), default=ApplicationStatus.PENDING)
    
    applied_amount = Column(Float, nullable=True)
    approved_amount = Column(Float, nullable=True)
    disbursed_amount = Column(Float, nullable=True)
    
    application_data = Column(JSON, nullable=False, default={})
    submitted_documents = Column(JSON, default=[])
    status_history = Column(JSON, default=[])
    eligibility_result = Column(JSON, nullable=True)
    
    approved_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    approved_at = Column(DateTime(timezone=True), nullable=True)
    approval_notes = Column(Text, nullable=True)
    
    rejected_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    rejected_at = Column(DateTime(timezone=True), nullable=True)
    rejection_reason = Column(Text, nullable=True)
    
    applied_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships - FIXED with explicit foreign_keys
    user = relationship("User", back_populates="applications", foreign_keys=[user_id])
    scheme = relationship("GovernmentScheme", back_populates="applications", foreign_keys=[scheme_id])
    approver = relationship("User", foreign_keys=[approved_by])
    rejecter = relationship("User", foreign_keys=[rejected_by])
    
    notifications = relationship("Notification", back_populates="application", foreign_keys="[Notification.related_application_id]", cascade="all, delete-orphan")

class Notification(Base):
    __tablename__ = "notifications"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    title = Column(String(200), nullable=False)
    message = Column(Text, nullable=False)
    notification_type = Column(String(50))
    
    related_scheme_id = Column(Integer, ForeignKey("government_schemes.id"), nullable=True)
    related_application_id = Column(Integer, ForeignKey("applications.id"), nullable=True)
    
    read = Column(Boolean, default=False)
    read_at = Column(DateTime(timezone=True), nullable=True)
    
    action_url = Column(String(500), nullable=True)
    action_text = Column(String(100), nullable=True)
    priority = Column(String(20), default="normal")
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships - FIXED with explicit foreign_keys
    user = relationship("User", back_populates="notifications", foreign_keys=[user_id])
    scheme = relationship("GovernmentScheme", foreign_keys=[related_scheme_id])
    application = relationship("Application", back_populates="notifications", foreign_keys=[related_application_id])

class AuditLog(Base):
    __tablename__ = "audit_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    action = Column(String(100), nullable=False)
    entity_type = Column(String(50), nullable=False)
    entity_id = Column(Integer, nullable=True)
    old_values = Column(JSON, nullable=True)
    new_values = Column(JSON, nullable=True)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(200), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationship
    user = relationship("User", foreign_keys=[user_id])
