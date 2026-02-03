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
    DOMICILE = "domicile"
    OTHER = "other"

class ApplicationStatus(str, enum.Enum):
    PENDING = "pending"
    UNDER_REVIEW = "under_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    DOCS_NEEDED = "docs_needed"

class SchemeType(str, enum.Enum):
    CENTRAL = "central"
    STATE = "state"

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
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    documents = relationship("Document", back_populates="user")
    applications = relationship("Application", back_populates="user")
    notifications = relationship("Notification", back_populates="user")

class Document(Base):
    __tablename__ = "documents"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    document_type = Column(Enum(DocumentType), nullable=False)
    file_path = Column(String(500), nullable=False)
    file_name = Column(String(200))
    file_size = Column(Integer)
    extracted_data = Column(JSON)
    verified = Column(Boolean, default=False)
    verification_date = Column(DateTime(timezone=True))
    uploaded_at = Column(DateTime(timezone=True), server_default=func.now())
    user = relationship("User", back_populates="documents")

class GovernmentScheme(Base):
    __tablename__ = "government_schemes"
    id = Column(Integer, primary_key=True, index=True)
    scheme_name = Column(String(200), nullable=False)
    scheme_code = Column(String(50), unique=True, index=True)
    description = Column(Text)
    scheme_type = Column(Enum(SchemeType), nullable=False)
    benefit_amount = Column(String(100))
    last_date = Column(DateTime(timezone=True))
    is_active = Column(Boolean, default=True)
    eligibility_criteria = Column(JSON, nullable=False)
    required_documents = Column(JSON, nullable=False)
    created_by = Column(String(100))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

class Application(Base):
    __tablename__ = "applications"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    scheme_id = Column(Integer, ForeignKey("government_schemes.id"), nullable=False)
    application_id = Column(String(50), unique=True, index=True)
    status = Column(Enum(ApplicationStatus), default=ApplicationStatus.PENDING)
    applied_amount = Column(Float)
    approved_amount = Column(Float)
    application_data = Column(JSON, nullable=False)
    submitted_documents = Column(JSON)
    status_history = Column(JSON)
    applied_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    user = relationship("User", back_populates="applications")
    scheme = relationship("GovernmentScheme")

class Notification(Base):
    __tablename__ = "notifications"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    title = Column(String(200), nullable=False)
    message = Column(Text, nullable=False)
    notification_type = Column(String(50))
    related_scheme_id = Column(Integer, ForeignKey("government_schemes.id"))
    related_application_id = Column(Integer, ForeignKey("applications.id"))
    read = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    user = relationship("User", back_populates="notifications")