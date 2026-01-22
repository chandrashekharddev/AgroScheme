# app/routers/farmers.py - CORRECTED VERSION
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from sqlalchemy.orm import Session
from typing import List
import os
import shutil
import uuid
from pathlib import Path


# ✅ CORRECT IMPORTS - ADD "app." prefix
from app.database import get_db
from app.schemas import UserResponse, UserUpdate, DocumentResponse, NotificationResponse, ApplicationResponse, DocumentCreate
from app.crud import (
    get_user_by_id, update_user, get_user_documents, create_document, 
    get_user_notifications, mark_notification_as_read, get_user_applications,
    update_document_verification
)
from app.utils.security import verify_token
from app.ai_processor import document_processor
from app.config import settings

router = APIRouter(prefix="/farmers", tags=["farmers"])

def get_current_user(token: str = Depends(verify_token), db: Session = Depends(get_db)):
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated"
        )
    
    user_id = token.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token"
        )
    
    user = get_user_by_id(db, int(user_id))
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    return user

@router.get("/me", response_model=UserResponse)
async def get_current_user_info(current_user: UserResponse = Depends(get_current_user)):
    return current_user

@router.put("/me", response_model=UserResponse)
async def update_user_info(
    user_update: UserUpdate,
    current_user: UserResponse = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return update_user(db, current_user.id, user_update)

@router.post("/upload-document")
async def upload_document(
    document_type: str = Form(...),
    file: UploadFile = File(...),
    current_user: UserResponse = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    file.file.seek(0, 2)
    file_size = file.file.tell()
    file.file.seek(0)
    
    if file_size > settings.MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File too large. Maximum size is {settings.MAX_FILE_SIZE // (1024*1024)}MB"
        )
    
    file_ext = Path(file.filename).suffix.lower()
    if file_ext not in settings.ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File type not allowed."
        )
    
    user_upload_dir = Path(settings.UPLOAD_DIR) / str(current_user.id)
    user_upload_dir.mkdir(parents=True, exist_ok=True)
    
    unique_filename = f"{uuid.uuid4()}{file_ext}"
    file_path = user_upload_dir / unique_filename
    
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    document_data = DocumentCreate(document_type=document_type)
    
    document = create_document(
        db=db,
        document=document_data,
        user_id=current_user.id,
        file_path=str(file_path),
        file_name=file.filename,
        file_size=file_size
    )
    
    extracted_data = await document_processor.extract_document_data(
        document_type, str(file_path)
    )
    
    update_document_verification(
        db=db,
        document_id=document.id,
        verified=True,
        extracted_data=extracted_data.get("extracted_data", {})
    )
    
    return {
        "success": True,
        "message": "Document uploaded and processed successfully",
        "document_id": document.id,
        "extracted_data": extracted_data
    }

@router.get("/documents", response_model=List[DocumentResponse])
async def get_my_documents(
    current_user: UserResponse = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return get_user_documents(db, current_user.id)

@router.get("/notifications", response_model=List[NotificationResponse])
async def get_my_notifications(
    unread_only: bool = False,
    current_user: UserResponse = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return get_user_notifications(db, current_user.id, unread_only)

@router.post("/notifications/{notification_id}/read")
async def mark_notification_read(
    notification_id: int,
    current_user: UserResponse = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    notification = mark_notification_as_read(db, notification_id)
    if not notification:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found"
        )
    
    return {"success": True, "message": "Notification marked as read"}

@router.get("/applications", response_model=List[ApplicationResponse])
async def get_my_applications(
    current_user: UserResponse = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    applications = get_user_applications(db, current_user.id)
    result = []
    for app in applications:
        app_dict = app.__dict__
        # ✅ FIXED: Add app. prefix
        from app.crud import get_scheme_by_id
        scheme = get_scheme_by_id(db, app.scheme_id)
        if scheme:
            # ✅ FIXED: Add app. prefix
            from app.schemas import SchemeResponse
            app_dict["scheme"] = SchemeResponse.from_orm(scheme)
        result.append(app_dict)
    
    return result

@router.get("/dashboard-stats")
async def get_dashboard_stats(
    current_user: UserResponse = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    applications = get_user_applications(db, current_user.id)
    total_applied = len(applications)
    approved_applications = [app for app in applications if app.status == "approved"]
    total_benefits = sum([app.approved_amount or 0 for app in approved_applications])
    # ✅ FIXED: Add app. prefix
    from app.crud import get_all_schemes
    all_schemes = get_all_schemes(db, active_only=True)
    eligible_count = min(len(all_schemes), 12)
    documents = get_user_documents(db, current_user.id)
    pending_docs = [doc for doc in documents if not doc.verified]
    
    return {
        "benefits_this_year": total_benefits,
        "applied_schemes": total_applied,
        "pending_actions": len(pending_docs),
        "eligible_schemes": eligible_count,
        "profile_complete": 75
    }