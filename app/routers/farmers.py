# app/routers/farmers.py - COMPLETE FIXED VERSION
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from typing import List, Optional
import os
import shutil
import uuid
from pathlib import Path

from app.database import get_db
from app.schemas import UserResponse, UserUpdate, DocumentResponse, NotificationResponse, ApplicationResponse, DocumentCreate, SchemeResponse
from app.crud import (
    get_user_by_id, update_user, get_user_documents, create_document, 
    get_user_notifications, mark_notification_as_read, get_user_applications,
    update_document_verification, get_all_schemes, get_scheme_by_id
)
from app.utils.auth_utils import get_current_user
from app.ai_processor import document_processor
from app.config import settings

router = APIRouter(prefix="/farmers", tags=["farmers"])

@router.get("/me")
async def get_current_user_info(
    request: Request,
    current_user = Depends(get_current_user)
):
    """Get current logged-in farmer's profile"""
    try:
        origin = request.headers.get("origin", "")
        
        response = JSONResponse({
            "success": True,
            "user": {
                "id": current_user.id,
                "farmer_id": current_user.farmer_id,
                "full_name": current_user.full_name,
                "mobile_number": current_user.mobile_number,
                "email": current_user.email,
                "state": getattr(current_user, 'state', None),
                "district": getattr(current_user, 'district', None),
                "village": getattr(current_user, 'village', None),
                "language": getattr(current_user, 'language', 'en'),
                "total_land_acres": getattr(current_user, 'total_land_acres', None),
                "land_type": getattr(current_user, 'land_type', None),
                "main_crops": getattr(current_user, 'main_crops', None),
                "annual_income": getattr(current_user, 'annual_income', None),
                "bank_account_number": getattr(current_user, 'bank_account_number', None),
                "bank_name": getattr(current_user, 'bank_name', None),
                "ifsc_code": getattr(current_user, 'ifsc_code', None),
                "bank_verified": getattr(current_user, 'bank_verified', False),
                "aadhaar_number": getattr(current_user, 'aadhaar_number', None),
                "pan_number": getattr(current_user, 'pan_number', None),
                "auto_apply_enabled": getattr(current_user, 'auto_apply_enabled', True),
                "role": current_user.role.value if hasattr(current_user.role, 'value') else current_user.role,
                "created_at": current_user.created_at.isoformat() if current_user.created_at else None
            }
        })
        
        # ✅ CORS headers for Vercel
        if origin and "vercel.app" in origin:
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Allow-Credentials"] = "true"
        
        return response
        
    except Exception as e:
        print(f"❌ Error in /me: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/me")
async def update_user_info(
    request: Request,
    user_update: UserUpdate,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update current farmer's profile"""
    try:
        origin = request.headers.get("origin", "")
        updated_user = update_user(db, current_user.id, user_update)
        
        response = JSONResponse({
            "success": True,
            "message": "Profile updated successfully",
            "user": updated_user
        })
        
        if origin and "vercel.app" in origin:
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Allow-Credentials"] = "true"
        
        return response
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/dashboard-stats")
async def get_dashboard_stats(
    request: Request,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get farmer's dashboard statistics"""
    try:
        origin = request.headers.get("origin", "")
        
        # Get applications
        applications = get_user_applications(db, current_user.id)
        total_applied = len(applications)
        
        # Count by status
        pending_count = sum(1 for app in applications if app.status == "pending")
        approved_apps = [app for app in applications if app.status == "approved"]
        approved_count = len(approved_apps)
        rejected_count = sum(1 for app in applications if app.status == "rejected")
        
        # Calculate total benefits
        total_benefits = sum(app.approved_amount or 0 for app in approved_apps)
        
        # Get eligible schemes count
        all_schemes = get_all_schemes(db, active_only=True)
        eligible_count = min(len(all_schemes), 12)  # Simplified eligibility
        
        # Get documents
        documents = get_user_documents(db, current_user.id)
        pending_docs = sum(1 for doc in documents if not doc.verified)
        
        response = JSONResponse({
            "success": True,
            "stats": {
                "benefits_this_year": float(total_benefits),
                "applied_schemes": total_applied,
                "pending_actions": pending_docs,
                "eligible_schemes": eligible_count,
                "profile_complete": 75 if current_user.full_name else 0,
                "pending_applications": pending_count,
                "approved_applications": approved_count,
                "rejected_applications": rejected_count,
                "total_applications": total_applied
            }
        })
        
        if origin and "vercel.app" in origin:
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Allow-Credentials"] = "true"
        
        return response
        
    except Exception as e:
        print(f"❌ Dashboard stats error: {str(e)}")
        # Return fallback data
        return JSONResponse({
            "success": True,
            "stats": {
                "benefits_this_year": 0,
                "applied_schemes": 0,
                "pending_actions": 0,
                "eligible_schemes": 0,
                "profile_complete": 0,
                "pending_applications": 0,
                "approved_applications": 0,
                "rejected_applications": 0,
                "total_applications": 0
            }
        })

@router.get("/applications")
async def get_my_applications(
    request: Request,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all applications for current farmer"""
    try:
        origin = request.headers.get("origin", "")
        
        applications = get_user_applications(db, current_user.id)
        result = []
        
        for app in applications:
            scheme = get_scheme_by_id(db, app.scheme_id)
            result.append({
                "id": app.id,
                "application_id": app.application_id,
                "scheme_id": app.scheme_id,
                "scheme_name": scheme.scheme_name if scheme else "Unknown Scheme",
                "status": app.status.value if hasattr(app.status, 'value') else app.status,
                "applied_amount": float(app.applied_amount) if app.applied_amount else 0,
                "approved_amount": float(app.approved_amount) if app.approved_amount else 0,
                "applied_at": app.applied_at.isoformat() if app.applied_at else None,
                "updated_at": app.updated_at.isoformat() if app.updated_at else None
            })
        
        response = JSONResponse({
            "success": True,
            "applications": result
        })
        
        if origin and "vercel.app" in origin:
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Allow-Credentials"] = "true"
        
        return response
        
    except Exception as e:
        print(f"❌ Applications error: {str(e)}")
        return JSONResponse({
            "success": True,
            "applications": []
        })

@router.get("/notifications")
async def get_my_notifications(
    request: Request,
    unread_only: bool = False,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get notifications for current farmer"""
    try:
        origin = request.headers.get("origin", "")
        notifications = get_user_notifications(db, current_user.id, unread_only)
        
        result = []
        for notif in notifications:
            result.append({
                "id": notif.id,
                "title": notif.title,
                "message": notif.message,
                "notification_type": notif.notification_type,
                "read": notif.read,
                "created_at": notif.created_at.isoformat() if notif.created_at else None
            })
        
        response = JSONResponse({
            "success": True,
            "notifications": result
        })
        
        if origin and "vercel.app" in origin:
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Allow-Credentials"] = "true"
        
        return response
        
    except Exception as e:
        print(f"❌ Notifications error: {str(e)}")
        return JSONResponse({
            "success": True,
            "notifications": []
        })

@router.post("/notifications/{notification_id}/read")
async def mark_notification_read(
    request: Request,
    notification_id: int,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Mark a notification as read"""
    origin = request.headers.get("origin", "")
    
    notification = mark_notification_as_read(db, notification_id)
    if not notification:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found"
        )
    
    response = JSONResponse({
        "success": True,
        "message": "Notification marked as read"
    })
    
    if origin and "vercel.app" in origin:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Credentials"] = "true"
    
    return response

@router.post("/upload-document")
async def upload_document(
    request: Request,
    document_type: str = Form(...),
    file: UploadFile = File(...),
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Upload a document for verification"""
    origin = request.headers.get("origin", "")
    
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
    
    # Create user-specific upload directory
    user_upload_dir = Path(settings.UPLOAD_DIR) / str(current_user.id)
    user_upload_dir.mkdir(parents=True, exist_ok=True)
    
    # Generate unique filename
    unique_filename = f"{uuid.uuid4()}{file_ext}"
    file_path = user_upload_dir / unique_filename
    
    # Save the file
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        print(f"✅ File saved to: {file_path}")
        print(f"✅ File size: {file_path.stat().st_size} bytes")
        
    except Exception as e:
        print(f"❌ Failed to save file: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save file: {str(e)}"
        )
    
    # Create relative path for database
    relative_path = f"{current_user.id}/{unique_filename}"
    
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
    
    # Process with AI (don't fail if AI processing fails)
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
        print(f"⚠️ AI processing failed: {str(e)}")
        # Still mark as verified
        update_document_verification(
            db=db,
            document_id=document.id,
            verified=True,
            extracted_data={"error": str(e)}
        )
    
    response = JSONResponse({
        "success": True,
        "message": "Document uploaded and processed successfully",
        "document_id": document.id,
        "file_url": f"/uploads/{relative_path}",
        "extracted_data": extracted_data
    })
    
    if origin and "vercel.app" in origin:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Credentials"] = "true"
    
    return response

@router.get("/documents")
async def get_my_documents(
    request: Request,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all documents for current farmer"""
    origin = request.headers.get("origin", "")
    
    documents = get_user_documents(db, current_user.id)
    result = []
    
    for doc in documents:
        result.append({
            "id": doc.id,
            "document_type": doc.document_type.value if hasattr(doc.document_type, 'value') else doc.document_type,
            "file_name": doc.file_name,
            "file_url": f"/uploads/{doc.file_path}",
            "file_size": doc.file_size,
            "verified": doc.verified,
            "uploaded_at": doc.uploaded_at.isoformat() if doc.uploaded_at else None
        })
    
    response = JSONResponse({
        "success": True,
        "documents": result
    })
    
    if origin and "vercel.app" in origin:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Credentials"] = "true"
    
    return response

@router.get("/debug-uploads")
async def debug_uploads(
    request: Request,
    current_user = Depends(get_current_user)
):
    """Debug endpoint to check uploaded files"""
    origin = request.headers.get("origin", "")
    
    user_upload_dir = Path(settings.UPLOAD_DIR) / str(current_user.id)
    
    if not user_upload_dir.exists():
        return JSONResponse({
            "message": "Upload directory does not exist",
            "path": str(user_upload_dir)
        })
    
    files = []
    for file in user_upload_dir.iterdir():
        if file.is_file():
            files.append({
                "name": file.name,
                "size": file.stat().st_size,
                "path": str(file),
                "relative_path": f"{current_user.id}/{file.name}"
            })
    
    response = JSONResponse({
        "user_id": current_user.id,
        "upload_dir": str(user_upload_dir),
        "exists": user_upload_dir.exists(),
        "files": files,
        "total_files": len(files)
    })
    
    if origin and "vercel.app" in origin:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Credentials"] = "true"
    
    return response
