from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional, Dict, Any
import random
import string
from datetime import datetime
from models import User, Document, GovernmentScheme, Application, Notification  # ✅ NEW
from schemas import UserCreate, UserUpdate, SchemeCreate, DocumentCreate  # ✅ NEW
from utils.security import get_password_hash, verify_password  # ✅ NEW
from utils.helpers import generate_farmer_id, generate_application_id, calculate_eligibility  # ✅ NEW

def get_user_by_id(db: Session, user_id: int) -> Optional[User]:
    return db.query(User).filter(User.id == user_id).first()

def get_user_by_mobile(db: Session, mobile_number: str) -> Optional[User]:
    return db.query(User).filter(User.mobile_number == mobile_number).first()

def get_user_by_email(db: Session, email: str) -> Optional[User]:
    return db.query(User).filter(User.email == email).first()

def get_user_by_farmer_id(db: Session, farmer_id: str) -> Optional[User]:
    return db.query(User).filter(User.farmer_id == farmer_id).first()

def create_user(db: Session, user: UserCreate) -> User:
    state_code = user.state[:2].upper()
    district_code = user.district[:2].upper()
    farmer_id = generate_farmer_id(state_code, district_code)
    
    while get_user_by_farmer_id(db, farmer_id):
        farmer_id = generate_farmer_id(state_code, district_code)
    
    db_user = User(
        full_name=user.full_name,
        mobile_number=user.mobile_number,
        email=user.email,
        password_hash=get_password_hash(user.password),
        state=user.state,
        district=user.district,
        village=user.village,
        language=user.language,
        farmer_id=farmer_id,
        role="farmer"
    )
    
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    
    notification = Notification(
        user_id=db_user.id,
        title="Welcome to AgroScheme AI!",
        message=f"Hello {db_user.full_name}, welcome to AgroScheme AI.",
        notification_type="system"
    )
    db.add(notification)
    db.commit()
    
    return db_user

def update_user(db: Session, user_id: int, user_update: UserUpdate) -> Optional[User]:
    db_user = get_user_by_id(db, user_id)
    if not db_user:
        return None
    
    update_data = user_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_user, field, value)
    
    db.commit()
    db.refresh(db_user)
    return db_user

def authenticate_user(db: Session, mobile_number: str, password: str) -> Optional[User]:
    user = get_user_by_mobile(db, mobile_number)
    if not user:
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user

def create_document(db: Session, document: DocumentCreate, user_id: int, file_path: str, file_name: str, file_size: int) -> Document:
    db_document = Document(
        user_id=user_id,
        document_type=document.document_type,
        file_path=file_path,
        file_name=file_name,
        file_size=file_size
    )
    
    db.add(db_document)
    db.commit()
    db.refresh(db_document)
    return db_document

def get_user_documents(db: Session, user_id: int) -> List[Document]:
    return db.query(Document).filter(Document.user_id == user_id).all()

def get_document_by_id(db: Session, document_id: int) -> Optional[Document]:
    return db.query(Document).filter(Document.id == document_id).first()

def update_document_verification(db: Session, document_id: int, verified: bool, extracted_data: Dict[str, Any] = None) -> Optional[Document]:
    document = get_document_by_id(db, document_id)
    if not document:
        return None
    
    document.verified = verified
    document.verification_date = datetime.utcnow()
    if extracted_data:
        document.extracted_data = extracted_data
    
    db.commit()
    db.refresh(document)
    return document

def create_scheme(db: Session, scheme: SchemeCreate, created_by: str) -> GovernmentScheme:
    db_scheme = GovernmentScheme(
        scheme_name=scheme.scheme_name,
        scheme_code=scheme.scheme_code,
        description=scheme.description,
        scheme_type=scheme.scheme_type,
        benefit_amount=scheme.benefit_amount,
        last_date=scheme.last_date,
        is_active=scheme.is_active,
        eligibility_criteria=scheme.eligibility_criteria,
        required_documents=scheme.required_documents,
        created_by=created_by
    )
    
    db.add(db_scheme)
    db.commit()
    db.refresh(db_scheme)
    return db_scheme

def get_scheme_by_id(db: Session, scheme_id: int) -> Optional[GovernmentScheme]:
    return db.query(GovernmentScheme).filter(GovernmentScheme.id == scheme_id).first()

def get_scheme_by_code(db: Session, scheme_code: str) -> Optional[GovernmentScheme]:
    return db.query(GovernmentScheme).filter(GovernmentScheme.scheme_code == scheme_code).first()

def get_all_schemes(db: Session, skip: int = 0, limit: int = 100, active_only: bool = True) -> List[GovernmentScheme]:
    query = db.query(GovernmentScheme)
    if active_only:
        query = query.filter(GovernmentScheme.is_active == True)
    return query.offset(skip).limit(limit).all()

def create_application(db: Session, user_id: int, scheme_id: int, application_data: Dict[str, Any]) -> Application:
    scheme = get_scheme_by_id(db, scheme_id)
    if not scheme:
        raise ValueError("Scheme not found")
    
    application_id = generate_application_id(scheme.scheme_code)
    user = get_user_by_id(db, user_id)
    
    app_data = {
        "user_info": {
            "full_name": user.full_name,
            "farmer_id": user.farmer_id,
            "mobile_number": user.mobile_number,
            "state": user.state,
            "district": user.district,
            "village": user.village,
            "total_land_acres": user.total_land_acres,
            "annual_income": user.annual_income,
            "bank_account": user.bank_account_number,
            "ifsc_code": user.ifsc_code
        },
        "scheme_info": {
            "scheme_name": scheme.scheme_name,
            "scheme_code": scheme.scheme_code,
            "benefit_amount": scheme.benefit_amount
        },
        **application_data
    }
    
    db_application = Application(
        user_id=user_id,
        scheme_id=scheme_id,
        application_id=application_id,
        application_data=app_data,
        applied_amount=scheme.benefit_amount
    )
    
    db.add(db_application)
    db.commit()
    db.refresh(db_application)
    
    notification = Notification(
        user_id=user_id,
        title=f"Application Submitted: {scheme.scheme_name}",
        message=f"Your application has been submitted. ID: {application_id}",
        notification_type="application",
        related_scheme_id=scheme_id,
        related_application_id=db_application.id
    )
    db.add(notification)
    db.commit()
    
    return db_application

def get_user_applications(db: Session, user_id: int) -> List[Application]:
    return db.query(Application).filter(Application.user_id == user_id).all()

def get_application_by_id(db: Session, application_id: int) -> Optional[Application]:
    return db.query(Application).filter(Application.id == application_id).first()

def update_application_status(db: Session, application_id: int, status: str, approved_amount: float = None) -> Optional[Application]:
    application = get_application_by_id(db, application_id)
    if not application:
        return None
    
    status_history = application.status_history or []
    status_history.append({
        "status": status,
        "timestamp": datetime.utcnow().isoformat(),
        "approved_amount": approved_amount
    })
    
    application.status = status
    application.approved_amount = approved_amount
    application.status_history = status_history
    
    db.commit()
    db.refresh(application)
    
    notification = Notification(
        user_id=application.user_id,
        title=f"Application Status Updated: {application.status}",
        message=f"Your application {application.application_id} status has been updated.",
        notification_type="application",
        related_scheme_id=application.scheme_id,
        related_application_id=application_id
    )
    db.add(notification)
    db.commit()
    
    return application

def check_user_eligibility(db: Session, user_id: int, scheme_id: int) -> Dict[str, Any]:
    user = get_user_by_id(db, user_id)
    scheme = get_scheme_by_id(db, scheme_id)
    
    if not user or not scheme:
        return {"eligible": False, "error": "User or scheme not found"}
    
    user_data = {
        "state": user.state,
        "district": user.district,
        "total_land_acres": user.total_land_acres,
        "annual_income": user.annual_income,
        "land_type": user.land_type,
        "main_crops": user.main_crops
    }
    
    eligibility_result = calculate_eligibility(user_data, scheme.eligibility_criteria)
    
    user_documents = get_user_documents(db, user_id)
    user_doc_types = [doc.document_type.value for doc in user_documents if doc.verified]
    missing_docs = []
    
    for required_doc in scheme.required_documents:
        if required_doc not in user_doc_types:
            missing_docs.append(required_doc)
    
    eligibility_result["missing_documents"] = missing_docs
    
    return eligibility_result

def create_notification(db: Session, user_id: int, title: str, message: str, notification_type: str, 
                       related_scheme_id: int = None, related_application_id: int = None) -> Notification:
    notification = Notification(
        user_id=user_id,
        title=title,
        message=message,
        notification_type=notification_type,
        related_scheme_id=related_scheme_id,
        related_application_id=related_application_id
    )
    
    db.add(notification)
    db.commit()
    db.refresh(notification)
    return notification

def get_user_notifications(db: Session, user_id: int, unread_only: bool = False) -> List[Notification]:
    query = db.query(Notification).filter(Notification.user_id == user_id)
    if unread_only:
        query = query.filter(Notification.read == False)
    return query.order_by(Notification.created_at.desc()).all()

def mark_notification_as_read(db: Session, notification_id: int) -> Optional[Notification]:
    notification = db.query(Notification).filter(Notification.id == notification_id).first()
    if not notification:
        return None
    
    notification.read = True
    db.commit()
    db.refresh(notification)
    return notification

def get_admin_stats(db: Session) -> Dict[str, Any]:
    total_farmers = db.query(func.count(User.id)).filter(User.role == "farmer").scalar() or 0
    total_applications = db.query(func.count(Application.id)).scalar() or 0
    total_schemes = db.query(func.count(GovernmentScheme.id)).scalar() or 0
    benefits_distributed = db.query(func.sum(Application.approved_amount)).filter(
        Application.status == "approved"
    ).scalar() or 0
    pending_verifications = db.query(func.count(Document.id)).filter(
        Document.verified == False
    ).scalar() or 0
    
    return {
        "total_farmers": total_farmers,
        "total_applications": total_applications,
        "total_schemes": total_schemes,
        "benefits_distributed": float(benefits_distributed or 0),
        "pending_verifications": pending_verifications,
        "ai_accuracy": 98.5
    }