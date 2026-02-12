# app/routers/farmers.py - COMPLETE WITH SUPABASE STORAGE
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
import os
from pathlib import Path

from app.database import get_db
from app.schemas import UserResponse, UserUpdate, DocumentResponse, NotificationResponse, ApplicationResponse, DocumentCreate, SchemeResponse
from app.crud import (
    get_user_by_id, update_user, get_user_documents, create_document, 
    get_user_notifications, mark_notification_as_read, get_user_applications,
    update_document_verification, get_all_schemes, get_scheme_by_id
)
from app.utils.auth_utils import get_current_user
from app.config import settings
from app.supabase_storage import supabase_storage  # ✅ Supabase Storage

router = APIRouter(prefix="/farmers", tags=["farmers"])

# ==================== GET CURRENT USER INFO ====================
@router.get("/me")
async def get_current_user_info(
    request: Request,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get current logged-in farmer's profile - FIXED JSON serialization"""
    try:
        origin = request.headers.get("origin", "")
        
        # Refresh user from database
        from app.crud import get_user_by_id
        user = get_user_by_id(db, current_user.id)
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # Return a DICT, not the SQLAlchemy object
        user_data = {
            "id": user.id,
            "farmer_id": user.farmer_id,
            "full_name": user.full_name,
            "mobile_number": user.mobile_number,
            "email": user.email,
            "state": user.state,
            "district": user.district,
            "village": user.village,
            "language": user.language or "en",
            "total_land_acres": float(user.total_land_acres) if user.total_land_acres else 0,
            "land_type": user.land_type,
            "main_crops": user.main_crops,
            "annual_income": float(user.annual_income) if user.annual_income else 0,
            "bank_account_number": user.bank_account_number,
            "bank_name": user.bank_name,
            "ifsc_code": user.ifsc_code,
            "bank_verified": user.bank_verified or False,
            "aadhaar_number": user.aadhaar_number,
            "pan_number": user.pan_number,
            "auto_apply_enabled": user.auto_apply_enabled if user.auto_apply_enabled is not None else True,
            "email_notifications": user.email_notifications if user.email_notifications is not None else True,
            "sms_notifications": user.sms_notifications if user.sms_notifications is not None else True,
            "role": user.role.value if hasattr(user.role, 'value') else user.role,
            "created_at": user.created_at.isoformat() if user.created_at else None
        }
        
        response = JSONResponse({
            "success": True,
            "user": user_data
        })
        
        if origin and "vercel.app" in origin:
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Allow-Credentials"] = "true"
        
        return response
        
    except Exception as e:
        print(f"❌ Error in /me: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

# ==================== UPDATE USER PROFILE ====================
@router.put("/me")
async def update_user_info(
    request: Request,
    user_update: UserUpdate,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update current farmer's profile - FIXED JSON serialization"""
    try:
        origin = request.headers.get("origin", "")
        
        # Update user in database
        updated_user = update_user(db, current_user.id, user_update)
        
        if not updated_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # Return a DICT, not the SQLAlchemy object
        user_data = {
            "id": updated_user.id,
            "farmer_id": updated_user.farmer_id,
            "full_name": updated_user.full_name,
            "mobile_number": updated_user.mobile_number,
            "email": updated_user.email,
            "state": updated_user.state,
            "district": updated_user.district,
            "village": updated_user.village,
            "language": updated_user.language or "en",
            "total_land_acres": float(updated_user.total_land_acres) if updated_user.total_land_acres else 0,
            "land_type": updated_user.land_type,
            "main_crops": updated_user.main_crops,
            "annual_income": float(updated_user.annual_income) if updated_user.annual_income else 0,
            "bank_account_number": updated_user.bank_account_number,
            "bank_name": updated_user.bank_name,
            "ifsc_code": updated_user.ifsc_code,
            "bank_verified": updated_user.bank_verified or False,
            "aadhaar_number": updated_user.aadhaar_number,
            "pan_number": updated_user.pan_number,
            "auto_apply_enabled": updated_user.auto_apply_enabled if updated_user.auto_apply_enabled is not None else True,
            "email_notifications": updated_user.email_notifications if updated_user.email_notifications is not None else True,
            "sms_notifications": updated_user.sms_notifications if updated_user.sms_notifications is not None else True,
            "role": updated_user.role.value if hasattr(updated_user.role, 'value') else updated_user.role,
            "created_at": updated_user.created_at.isoformat() if updated_user.created_at else None
        }
        
        response = JSONResponse({
            "success": True,
            "message": "Profile updated successfully",
            "user": user_data
        })
        
        if origin and "vercel.app" in origin:
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Allow-Credentials"] = "true"
        
        return response
        
    except Exception as e:
        print(f"❌ Error updating profile: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update profile: {str(e)}"
        )

# ==================== GET DASHBOARD STATS ====================
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
        
        # Get eligible schemes count safely
        try:
            all_schemes = get_all_schemes(db, active_only=True)
            eligible_count = min(len(all_schemes), 12)
        except Exception as e:
            print(f"⚠️ Error getting schemes: {e}")
            eligible_count = 0
        
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

# ==================== GET MY APPLICATIONS ====================
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

# ==================== GET MY NOTIFICATIONS ====================
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

# ==================== MARK NOTIFICATION AS READ ====================
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

# ==================== UPLOAD DOCUMENT TO SUPABASE STORAGE ====================
@router.post("/upload-document")
async def upload_document(
    request: Request,
    document_type: str = Form(...),
    file: UploadFile = File(...),
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Upload document to Supabase Storage"""
    origin = request.headers.get("origin", "")
    
    try:
        # Read file content
        file_content = await file.read()
        file_size = len(file_content)
        
        # Validate file size (10MB limit)
        if file_size > 10 * 1024 * 1024:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File too large. Maximum size is 10MB"
            )
        
        # Validate file extension
        file_ext = Path(file.filename).suffix.lower()
        allowed_extensions = {'.jpg', '.jpeg', '.png', '.pdf', '.heic', '.heif'}
        if file_ext not in allowed_extensions:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File type {file_ext} not allowed. Allowed: {allowed_extensions}"
            )
        
        # ✅ UPLOAD TO SUPABASE STORAGE
        storage_result = await supabase_storage.upload_document(
            user_id=current_user.id,
            document_type=document_type,
            file_content=file_content,
            filename=file.filename,
            content_type=file.content_type or "application/octet-stream"
        )
        
        if not storage_result["success"]:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Upload failed: {storage_result.get('error')}"
            )
        
        # ✅ SAVE METADATA TO DATABASE
        document_data = DocumentCreate(document_type=document_type)
        
        document = create_document(
            db=db,
            document=document_data,
            user_id=current_user.id,
            file_path=storage_result["file_path"],
            file_name=file.filename,
            file_size=storage_result["file_size"]
        )
        
        # Update document with file_url
        document.file_url = storage_result["file_url"]
        db.commit()
        
        response = JSONResponse({
            "success": True,
            "message": "Document uploaded to Supabase Storage successfully",
            "document_id": document.id,
            "file_url": storage_result["file_url"],
            "file_path": storage_result["file_path"],
            "file_size": storage_result["file_size"],
            "document_type": document_type
        })
        
        if origin and "vercel.app" in origin:
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Allow-Credentials"] = "true"
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Upload error: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload document: {str(e)}"
        )

# ==================== GET MY DOCUMENTS WITH SIGNED URLS ====================
@router.get("/documents")
async def get_my_documents(
    request: Request,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all documents for current farmer with signed URLs"""
    origin = request.headers.get("origin", "")
    
    documents = get_user_documents(db, current_user.id)
    result = []
    
    for doc in documents:
        # Generate fresh signed URL (1 hour expiry)
        file_url = await supabase_storage.get_document_url(doc.file_path)
        
        result.append({
            "id": doc.id,
            "document_type": doc.document_type.value if hasattr(doc.document_type, 'value') else doc.document_type,
            "file_name": doc.file_name,
            "file_url": file_url,  # ✅ Fresh signed URL from Supabase
            "file_size": doc.file_size,
            "verified": doc.verified,
            "extracted_data": doc.extracted_data,
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

# ==================== DEBUG UPLOADS (SUPABASE) ====================
@router.get("/debug-uploads")
async def debug_uploads(
    request: Request,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Debug endpoint to check uploaded files in Supabase"""
    origin = request.headers.get("origin", "")
    
    try:
        # Get documents from database
        documents = get_user_documents(db, current_user.id)
        
        files = []
        for doc in documents:
            # Generate signed URL
            file_url = await supabase_storage.get_document_url(doc.file_path)
            files.append({
                "id": doc.id,
                "name": doc.file_name,
                "path": doc.file_path,
                "url": file_url,
                "size": doc.file_size,
                "type": doc.document_type,
                "verified": doc.verified,
                "uploaded_at": doc.uploaded_at.isoformat() if doc.uploaded_at else None
            })
        
        response = JSONResponse({
            "user_id": current_user.id,
            "total_files": len(files),
            "files": files
        })
        
        if origin and "vercel.app" in origin:
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Allow-Credentials"] = "true"
        
        return response
        
    except Exception as e:
        print(f"❌ Debug uploads error: {str(e)}")
        return JSONResponse({
            "success": False,
            "error": str(e)
        })

# ==================== DELETE DOCUMENT ====================
@router.delete("/documents/{document_id}")
async def delete_document(
    request: Request,
    document_id: int,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete document from Supabase Storage and database"""
    origin = request.headers.get("origin", "")
    
    try:
        # Get document from database
        document = db.query(Document).filter(
            Document.id == document_id,
            Document.user_id == current_user.id
        ).first()
        
        if not document:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document not found"
            )
        
        # Delete from Supabase Storage
        await supabase_storage.delete_document(document.file_path)
        
        # Delete from database
        db.delete(document)
        db.commit()
        
        response = JSONResponse({
            "success": True,
            "message": "Document deleted successfully"
        })
        
        if origin and "vercel.app" in origin:
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Allow-Credentials"] = "true"
        
        return response
        
    except Exception as e:
        print(f"❌ Delete error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete document: {str(e)}"
        )
