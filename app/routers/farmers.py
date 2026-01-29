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
    """Upload and process document for a farmer with user-specific folder"""
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
        
        # ✅ FIXED: Get user-specific upload directory using new settings method
        user_dir = settings.get_user_upload_dir(
            user_id=current_user.id,
            farmer_id=current_user.farmer_id
        )
        
        # Generate unique filename
        unique_filename = f"{uuid.uuid4()}{file_ext}"
        file_path = user_dir / unique_filename
        
        # Save the file
        try:
            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to save file: {str(e)}"
            )
        
        # ✅ FIXED: Generate relative path using new settings method
        relative_path = settings.get_relative_path(
            filename=unique_filename,
            user_id=current_user.id,
            farmer_id=current_user.farmer_id
        )
        
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
        file_url = settings.get_file_url(relative_path)
        
        return {
            "success": True,
            "message": "Document uploaded successfully",
            "document_id": document.id,
            "document_type": document_type,
            "file_url": file_url,
            "file_path": relative_path,
            "folder_name": settings.get_user_folder_name(
                user_id=current_user.id,
                farmer_id=current_user.farmer_id
            ),
            "original_filename": file.filename,
            "file_size": file_size,
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
            doc.file_url = settings.get_file_url(doc.file_path)
    
    return documents

@router.get("/debug-uploads")
async def debug_uploads(
    current_user: UserResponse = Depends(get_current_user)
):
    """Debug endpoint to check user's upload directory"""
    from pathlib import Path
    
    # ✅ FIXED: Use new settings method
    user_dir = settings.get_user_upload_dir(
        user_id=current_user.id,
        farmer_id=current_user.farmer_id
    )
    
    if not user_dir.exists():
        return {
            "message": "Upload directory does not exist",
            "path": str(user_dir),
            "user_id": current_user.id,
            "farmer_id": current_user.farmer_id,
            "folder_name": settings.get_user_folder_name(
                user_id=current_user.id,
                farmer_id=current_user.farmer_id
            ),
            "upload_root": str(settings.UPLOAD_ROOT),
            "root_exists": settings.UPLOAD_ROOT.exists()
        }
    
    files = []
    for file in user_dir.iterdir():
        if file.is_file():
            # Get relative path from uploads root
            relative_path = file.relative_to(settings.UPLOAD_ROOT)
            
            files.append({
                "name": file.name,
                "size": file.stat().st_size,
                "absolute_path": str(file),
                "relative_path": str(relative_path),
                "url": settings.get_file_url(str(relative_path)),
                "created": file.stat().st_ctime,
                "modified": file.stat().st_mtime
            })
    
    # Check database documents
    from app.database import get_db
    from app.crud import get_user_documents
    from sqlalchemy.orm import Session
    
    db_docs = []
    try:
        db_session = next(get_db())
        db_documents = get_user_documents(db_session, current_user.id)
        for doc in db_documents:
            db_docs.append({
                "id": doc.id,
                "document_type": doc.document_type,
                "file_path": doc.file_path,
                "file_name": doc.file_name,
                "verified": doc.verified,
                "url": settings.get_file_url(doc.file_path) if doc.file_path else None
            })
    except:
        db_docs = []
    
    return {
        "user_id": current_user.id,
        "farmer_id": current_user.farmer_id,
        "folder_name": settings.get_user_folder_name(
            user_id=current_user.id,
            farmer_id=current_user.farmer_id
        ),
        "upload_dir": str(user_dir),
        "exists": user_dir.exists(),
        "files_on_disk": files,
        "files_in_database": db_docs,
        "total_files_on_disk": len(files),
        "total_files_in_db": len(db_docs),
        "api_base_url": settings.API_BASE_URL
    }

@router.get("/debug/uploads/list")
async def list_all_uploads(
    current_user: UserResponse = Depends(get_current_user)
):
    """List all files in uploads directory (admin/debug)"""
    if not settings.UPLOAD_ROOT.exists():
        return {"error": "Uploads root directory does not exist"}
    
    all_folders = []
    total_files = 0
    
    # List all user folders
    for folder in settings.UPLOAD_ROOT.iterdir():
        if folder.is_dir():
            folder_files = []
            for file in folder.iterdir():
                if file.is_file():
                    folder_files.append({
                        "name": file.name,
                        "size": file.stat().st_size,
                        "path": str(file.relative_to(settings.UPLOAD_ROOT))
                    })
                    total_files += 1
            
            all_folders.append({
                "name": folder.name,
                "path": str(folder),
                "file_count": len(folder_files),
                "files": folder_files
            })
    
    return {
        "upload_root": str(settings.UPLOAD_ROOT),
        "total_folders": len(all_folders),
        "total_files": total_files,
        "folders": all_folders
    }

@router.delete("/debug/uploads/clean")
async def clean_user_uploads(
    current_user: UserResponse = Depends(get_current_user)
):
    """Clean user's upload directory (debug only)"""
    user_dir = settings.get_user_upload_dir(
        user_id=current_user.id,
        farmer_id=current_user.farmer_id
    )
    
    if not user_dir.exists():
        return {
            "success": True,
            "message": "Directory does not exist",
            "directory": str(user_dir)
        }
    
    deleted_files = []
    for file in user_dir.iterdir():
        if file.is_file() and file.name != ".gitkeep":
            try:
                file.unlink()
                deleted_files.append(file.name)
            except Exception as e:
                return {
                    "success": False,
                    "message": f"Failed to delete {file.name}: {str(e)}"
                }
    
    return {
        "success": True,
        "message": f"Cleaned {len(deleted_files)} files",
        "directory": str(user_dir),
        "deleted_files": deleted_files
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

# ✅ NEW: Bulk upload endpoint
@router.post("/upload-documents/bulk")
async def upload_documents_bulk(
    files: List[UploadFile] = File(...),
    document_types: List[str] = Form(...),
    current_user: UserResponse = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Upload multiple documents at once"""
    if len(files) != len(document_types):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Number of files must match number of document types"
        )
    
    results = []
    errors = []
    
    for file, doc_type in zip(files, document_types):
        try:
            # Reuse the single upload logic
            form_data = {
                "document_type": doc_type,
                "file": file
            }
            
            # Note: In FastAPI, we can't directly call another endpoint
            # So we'll duplicate the logic here
            result = await upload_document_single(
                document_type=doc_type,
                file=file,
                current_user=current_user,
                db=db
            )
            results.append(result)
            
        except Exception as e:
            errors.append({
                "filename": file.filename,
                "error": str(e)
            })
    
    return {
        "success": True,
        "message": f"Uploaded {len(results)} files, {len(errors)} failed",
        "results": results,
        "errors": errors
    }

async def upload_document_single(
    document_type: str,
    file: UploadFile,
    current_user: UserResponse,
    db: Session
):
    """Helper function for single document upload (used by bulk)"""
    # Same logic as upload_document endpoint
    file.file.seek(0, 2)
    file_size = file.file.tell()
    file.file.seek(0)
    
    if file_size > settings.MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File too large: {file.filename}"
        )
    
    file_ext = Path(file.filename).suffix.lower()
    if file_ext not in settings.ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid file type: {file.filename}"
        )
    
    user_dir = settings.get_user_upload_dir(
        user_id=current_user.id,
        farmer_id=current_user.farmer_id
    )
    
    unique_filename = f"{uuid.uuid4()}{file_ext}"
    file_path = user_dir / unique_filename
    
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    relative_path = settings.get_relative_path(
        filename=unique_filename,
        user_id=current_user.id,
        farmer_id=current_user.farmer_id
    )
    
    document_data = DocumentCreate(document_type=document_type)
    document = create_document(
        db=db,
        document=document_data,
        user_id=current_user.id,
        file_path=relative_path,
        file_name=file.filename,
        file_size=file_size
    )
    
    return {
        "document_id": document.id,
        "filename": file.filename,
        "document_type": document_type,
        "file_url": settings.get_file_url(relative_path),
        "size": file_size
    }
