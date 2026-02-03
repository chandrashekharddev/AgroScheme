from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from sqlalchemy.orm import Session
from typing import List
import shutil
import uuid
from pathlib import Path

from app.database import get_db
from app.schemas import UserResponse, UserUpdate, DocumentResponse, NotificationResponse, ApplicationResponse, DocumentCreate
from app.crud import (
    get_user_by_id, update_user, get_user_documents, create_document, 
    get_user_notifications, mark_notification_as_read, get_user_applications,
    update_document_verification, get_scheme_by_id
)
from app.dependencies import get_current_user
from app.ai_processor import document_processor
from app.config import settings

router = APIRouter(prefix="/farmers", tags=["farmers"])

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
    """Upload and process document for a farmer"""
    try:
        # Validate file size
        file.file.seek(0, 2)
        file_size = file.file.tell()
        file.file.seek(0)
        
        if file_size > settings.MAX_FILE_SIZE:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File too large. Maximum size is {settings.MAX_FILE_SIZE // (1024*1024)}MB"
            )
        
        # Validate file extension
        file_ext = Path(file.filename).suffix.lower()
        if file_ext not in settings.ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File type {file_ext} not allowed. Allowed: {settings.ALLOWED_EXTENSIONS}"
            )
        
        # ✅ FIXED: Create farmer-specific folder with farmer_id
        farmer_folder = str(current_user.id)
        if hasattr(current_user, 'farmer_id') and current_user.farmer_id:
            farmer_folder = str(current_user.farmer_id).replace('/', '_')
        
        user_upload_dir = Path(settings.UPLOAD_DIR) / farmer_folder
        user_upload_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate unique filename
        unique_filename = f"{uuid.uuid4()}{file_ext}"
        file_path = user_upload_dir / unique_filename
        
        # Save the file
        try:
            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to save file: {str(e)}"
            )
        
        # Create relative path for database
        relative_path = f"{farmer_folder}/{unique_filename}"
        
        # Create document in database
        document_data = DocumentCreate(document_type=document_type)
        
        document = create_document(
            db=db,
            document=document_data,
            user_id=current_user.id,
            file_path=relative_path,
            file_name=file.filename,
            file_size=file_size
        )
        
        # Process with AI
        extracted_data = {}
        try:
            extracted_data = await document_processor.extract_document_data(
                document_type, str(file_path)
            )
            
            update_document_verification(
                db=db,
                document_id=document.id,
                verified=True,
                extracted_data=extracted_data.get("extracted_data", {})
            )
            
        except Exception as e:
            print(f"AI processing failed: {str(e)}")
            # Mark as unverified if AI fails
            update_document_verification(
                db=db,
                document_id=document.id,
                verified=False,
                extracted_data={"error": str(e)}
            )
        
        # ✅ FIXED: Generate correct file URL
        file_url = f"{settings.API_BASE_URL}/uploads/{relative_path}"
        
        return {
            "success": True,
            "message": "Document uploaded successfully",
            "document_id": document.id,
            "document_type": document_type,
            "file_url": file_url,
            "file_path": relative_path,
            "extracted_data": extracted_data,
            "verified": document.verified
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Upload failed: {str(e)}"
        )

@router.get("/documents", response_model=List[DocumentResponse])
async def get_my_documents(
    current_user: UserResponse = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    documents = get_user_documents(db, current_user.id)
    
    # ✅ FIXED: Add proper file_url to each document
    for doc in documents:
        if doc.file_path:
            # Use API base URL from settings
            doc.file_url = f"{settings.API_BASE_URL}/uploads/{doc.file_path}"
    
    return documents

@router.get("/debug-uploads")
async def debug_uploads(
    current_user: UserResponse = Depends(get_current_user)
):
    import os
    from pathlib import Path
    
    # Get farmer folder name
    farmer_folder = str(current_user.id)
    if hasattr(current_user, 'farmer_id') and current_user.farmer_id:
        farmer_folder = str(current_user.farmer_id).replace('/', '_')
    
    user_upload_dir = Path(settings.UPLOAD_DIR) / farmer_folder
    
    if not user_upload_dir.exists():
        return {
            "message": "Upload directory does not exist",
            "path": str(user_upload_dir),
            "farmer_id": farmer_folder
        }
    
    files = []
    for file in user_upload_dir.iterdir():
        if file.is_file():
            files.append({
                "name": file.name,
                "size": file.stat().st_size,
                "path": str(file),
                "relative_path": f"{farmer_folder}/{file.name}",
                "url": f"{settings.API_BASE_URL}/uploads/{farmer_folder}/{file.name}"
            })
    
    return {
        "farmer_id": farmer_folder,
        "upload_dir": str(user_upload_dir),
        "exists": user_upload_dir.exists(),
        "files": files,
        "total_files": len(files)
    }

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
        app_dict = app.__dict__.copy()
        
        # Add scheme info
        scheme = get_scheme_by_id(db, app.scheme_id)
        if scheme:
            from app.schemas import SchemeResponse
            app_dict["scheme"] = SchemeResponse.from_orm(scheme)
        
        result.append(app_dict)
    
    return result

@router.get("/dashboard-stats")
async def get_dashboard_stats(
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    applications = get_user_applications(db, current_user.id)
    total_applied = len(applications)
    approved_applications = [app for app in applications if app.status == "approved"]
    total_benefits = sum([app.approved_amount or 0 for app in approved_applications])
    
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
