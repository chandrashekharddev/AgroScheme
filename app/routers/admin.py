# app/routers/admin.py - UPDATED VERSION WITH PROPER ADMIN AUTH
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from sqlalchemy import func
from fastapi.responses import FileResponse

from app.database import get_db
from app.schemas import SchemeCreate, SchemeResponse, AdminStats, UserResponse, AdminDashboardStats
from app.models import User, Document, Application, GovernmentScheme, Notification, UserRole
from app.crud import (
    get_user_by_id, get_scheme_by_code, create_scheme, get_scheme_by_id,
    get_all_schemes, get_application_by_id, update_application_status,
    get_document_by_id, update_document_verification, mark_notification_as_read,
    get_user_applications, get_user_documents
)
from app.utils.security import get_current_admin_user

router = APIRouter(prefix="/admin", tags=["admin"])

# ✅ Admin dashboard page
@router.get("/admin.html")
async def serve_admin_page(current_user = Depends(get_current_admin_user)):
    """Serve the admin HTML page (admin only)"""
    try:
        return FileResponse("static/admin.html")
    except FileNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Admin page not found"
        )

# ✅ Check admin status
@router.get("/check")
async def check_admin_status(current_user = Depends(get_current_admin_user)):
    """Check if current user is admin"""
    return {
        "success": True,
        "is_admin": True,
        "user": {
            "id": current_user.id,
            "name": current_user.full_name,
            "mobile": current_user.mobile_number,
            "email": current_user.email,
            "role": current_user.role.value
        }
    }

# ✅ Get admin dashboard statistics
@router.get("/stats")
async def get_stats(
    current_user = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Get admin dashboard statistics"""
    try:
        # Calculate stats with proper Enum comparison
        total_farmers = db.query(func.count(User.id)).filter(User.role == UserRole.FARMER).scalar() or 0
        total_admins = db.query(func.count(User.id)).filter(User.role == UserRole.ADMIN).scalar() or 0
        total_applications = db.query(func.count(Application.id)).scalar() or 0
        total_schemes = db.query(func.count(GovernmentScheme.id)).scalar() or 0
        benefits_distributed = db.query(func.sum(Application.approved_amount)).filter(
            Application.status == "approved"
        ).scalar() or 0
        pending_verifications = db.query(func.count(Document.id)).filter(
            Document.verified == False
        ).scalar() or 0
        
        # Get pending applications
        pending_applications = db.query(func.count(Application.id)).filter(
            Application.status == "pending"
        ).scalar() or 0
        
        return {
            "success": True,
            "total_farmers": total_farmers,
            "total_admins": total_admins,
            "total_applications": total_applications,
            "total_schemes": total_schemes,
            "benefits_distributed": float(benefits_distributed),
            "pending_verifications": pending_verifications,
            "pending_applications": pending_applications,
            "ai_accuracy": 98.5,
            "admin_name": current_user.full_name,
            "admin_role": current_user.role.value
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch stats: {str(e)}"
        )

# ✅ Get comprehensive dashboard statistics
@router.get("/dashboard-stats", response_model=AdminDashboardStats)
async def get_dashboard_stats(
    current_user = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Get comprehensive dashboard statistics"""
    try:
        # Get basic stats
        total_farmers = db.query(func.count(User.id)).filter(User.role == UserRole.FARMER).scalar() or 0
        total_applications = db.query(func.count(Application.id)).scalar() or 0
        total_schemes = db.query(func.count(GovernmentScheme.id)).scalar() or 0
        benefits_distributed = db.query(func.sum(Application.approved_amount)).filter(
            Application.status == "approved"
        ).scalar() or 0
        pending_verifications = db.query(func.count(Document.id)).filter(
            Document.verified == False
        ).scalar() or 0
        
        # Get recent registrations
        recent_users = db.query(User)\
            .filter(User.role == UserRole.FARMER)\
            .order_by(User.created_at.desc())\
            .limit(5)\
            .all()
        
        recent_registrations = [
            {
                "farmer_id": user.farmer_id,
                "full_name": user.full_name,
                "mobile_number": user.mobile_number,
                "state": user.state,
                "created_at": user.created_at
            }
            for user in recent_users
        ]
        
        # Get top schemes
        top_schemes = db.query(
            GovernmentScheme.scheme_name,
            func.count(Application.id).label('application_count'),
            func.sum(Application.approved_amount).label('total_benefits')
        ).join(Application, GovernmentScheme.id == Application.scheme_id, isouter=True)\
         .group_by(GovernmentScheme.id)\
         .order_by(func.count(Application.id).desc())\
         .limit(5)\
         .all()
        
        top_schemes_list = [
            {
                "scheme_name": scheme.scheme_name,
                "application_count": scheme.application_count or 0,
                "total_benefits": float(scheme.total_benefits or 0)
            }
            for scheme in top_schemes
        ]
        
        # Combine all stats
        result = {
            "total_farmers": total_farmers,
            "total_applications": total_applications,
            "total_schemes": total_schemes,
            "benefits_distributed": float(benefits_distributed),
            "pending_verifications": pending_verifications,
            "ai_accuracy": 98.5,
            "farmer_growth": 12.5,
            "application_growth": 8.3,
            "scheme_growth": 5.2,
            "benefit_growth": 15.7,
            "accuracy_growth": 2.1,
            "recent_registrations": recent_registrations,
            "top_schemes": top_schemes_list
        }
        
        return result
        
    except Exception as e:
        print(f"Error in get_dashboard_stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch dashboard stats: {str(e)}"
        )

# ✅ Add a new government scheme
@router.post("/schemes", response_model=SchemeResponse)
async def add_scheme(
    scheme: SchemeCreate,
    current_user = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Add a new government scheme"""
    try:
        # Check if scheme code already exists
        existing_scheme = get_scheme_by_code(db, scheme.scheme_code)
        if existing_scheme:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Scheme with code '{scheme.scheme_code}' already exists"
            )
        
        return create_scheme(db=db, scheme=scheme, created_by=current_user.full_name)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to add scheme: {str(e)}"
        )

# ✅ Get all registered farmers/users
@router.get("/users", response_model=List[UserResponse])
async def get_all_users(
    skip: int = 0,
    limit: int = 100,
    search: Optional[str] = None,
    current_user = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Get all registered farmers/users"""
    try:
        # Get all farmers
        farmers = db.query(User).filter(User.role == UserRole.FARMER).offset(skip).limit(limit).all()
        
        # Apply search filter if provided
        if search:
            search = search.lower()
            farmers = [
                farmer for farmer in farmers
                if (search in farmer.full_name.lower() or
                    (farmer.farmer_id and search in farmer.farmer_id.lower()) or
                    search in farmer.mobile_number.lower() or
                    (farmer.email and search in farmer.email.lower()))
            ]
        
        return farmers
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch users: {str(e)}"
        )

# ✅ Get recent user registrations
@router.get("/users/recent")
async def get_recent_users(
    limit: int = 5,
    current_user = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Get recent user registrations"""
    try:
        recent_users = db.query(User)\
            .filter(User.role == UserRole.FARMER)\
            .order_by(User.created_at.desc())\
            .limit(limit)\
            .all()
        
        return [
            {
                "id": user.id,
                "farmer_id": user.farmer_id,
                "full_name": user.full_name,
                "mobile_number": user.mobile_number,
                "email": user.email,
                "state": user.state,
                "created_at": user.created_at
            }
            for user in recent_users
        ]
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch recent users: {str(e)}"
        )

# ✅ Get detailed information about a specific user
@router.get("/users/{user_id}")
async def get_user_details(
    user_id: int,
    current_user = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Get detailed information about a specific user"""
    try:
        user = get_user_by_id(db, user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # Get user's applications
        applications = get_user_applications(db, user_id)
        
        # Get user's documents
        documents = get_user_documents(db, user_id)
        
        return {
            "success": True,
            "user": {
                "id": user.id,
                "farmer_id": user.farmer_id,
                "full_name": user.full_name,
                "mobile_number": user.mobile_number,
                "email": user.email,
                "state": user.state,
                "district": user.district,
                "village": user.village,
                "total_land_acres": user.total_land_acres,
                "annual_income": user.annual_income,
                "land_type": user.land_type,
                "main_crops": user.main_crops,
                "bank_account_number": user.bank_account_number,
                "ifsc_code": user.ifsc_code,
                "created_at": user.created_at,
                "role": user.role.value
            },
            "applications": [
                {
                    "id": app.id,
                    "application_id": app.application_id,
                    "status": app.status.value if hasattr(app.status, 'value') else app.status,
                    "applied_amount": app.applied_amount,
                    "approved_amount": app.approved_amount,
                    "applied_at": app.applied_at
                }
                for app in applications
            ],
            "documents": [
                {
                    "id": doc.id,
                    "document_type": doc.document_type.value if hasattr(doc.document_type, 'value') else doc.document_type,
                    "file_name": doc.file_name,
                    "verified": doc.verified,
                    "uploaded_at": doc.uploaded_at
                }
                for doc in documents
            ],
            "stats": {
                "total_applications": len(applications),
                "total_verified_documents": len([d for d in documents if d.verified]),
                "approved_applications": len([a for a in applications if a.status == "approved"])
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch user details: {str(e)}"
        )

# ✅ Get all applications with filters
@router.get("/applications")
async def get_all_applications_admin(
    skip: int = 0,
    limit: int = 100,
    status: Optional[str] = None,
    search: Optional[str] = None,
    current_user = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Get all applications with filters"""
    try:
        # Build query
        query = db.query(Application)
        
        # Apply status filter
        if status:
            valid_statuses = ["pending", "under_review", "approved", "rejected", "docs_needed"]
            if status not in valid_statuses:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid status. Must be one of: {', '.join(valid_statuses)}"
                )
            query = query.filter(Application.status == status)
        
        applications = query.offset(skip).limit(limit).all()
        
        result = []
        for app in applications:
            # Get user details
            user = get_user_by_id(db, app.user_id)
            
            # Get scheme details
            scheme = get_scheme_by_id(db, app.scheme_id)
            
            app_data = {
                "id": app.id,
                "application_id": app.application_id,
                "status": app.status.value if hasattr(app.status, 'value') else app.status,
                "applied_amount": app.applied_amount,
                "approved_amount": app.approved_amount,
                "applied_at": app.applied_at,
                "updated_at": app.updated_at,
                "user": {
                    "id": user.id if user else None,
                    "farmer_id": user.farmer_id if user else None,
                    "full_name": user.full_name if user else "Unknown",
                    "mobile_number": user.mobile_number if user else None
                } if user else None,
                "scheme": {
                    "id": scheme.id if scheme else None,
                    "scheme_name": scheme.scheme_name if scheme else "Unknown",
                    "scheme_code": scheme.scheme_code if scheme else None
                } if scheme else None
            }
            
            # Apply search filter
            if search:
                search_lower = search.lower()
                matches = (
                    (app_data["application_id"] and search_lower in app_data["application_id"].lower()) or
                    (app_data["user"] and app_data["user"]["full_name"] and search_lower in app_data["user"]["full_name"].lower()) or
                    (app_data["scheme"] and app_data["scheme"]["scheme_name"] and search_lower in app_data["scheme"]["scheme_name"].lower())
                )
                if not matches:
                    continue
            
            result.append(app_data)
        
        return {
            "success": True,
            "count": len(result),
            "applications": result
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch applications: {str(e)}"
        )

# ✅ Get detailed application information
@router.get("/applications/{application_id}")
async def get_application_details(
    application_id: int,
    current_user = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Get detailed application information"""
    try:
        application = get_application_by_id(db, application_id)
        if not application:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Application not found"
            )
        
        # Get user details
        user = get_user_by_id(db, application.user_id)
        
        # Get scheme details
        scheme = get_scheme_by_id(db, application.scheme_id)
        
        # Get application data
        app_data = application.application_data or {}
        
        return {
            "success": True,
            "application": {
                "id": application.id,
                "application_id": application.application_id,
                "status": application.status.value if hasattr(application.status, 'value') else application.status,
                "applied_amount": application.applied_amount,
                "approved_amount": application.approved_amount,
                "applied_at": application.applied_at,
                "updated_at": application.updated_at,
                "status_history": application.status_history,
                "user": {
                    "id": user.id if user else None,
                    "farmer_id": user.farmer_id if user else None,
                    "full_name": user.full_name if user else "Unknown",
                    "mobile_number": user.mobile_number if user else None,
                    "email": user.email if user else None,
                    "state": user.state if user else None,
                    "district": user.district if user else None,
                    "village": user.village if user else None
                } if user else None,
                "scheme": {
                    "id": scheme.id if scheme else None,
                    "scheme_name": scheme.scheme_name if scheme else "Unknown",
                    "scheme_code": scheme.scheme_code if scheme else None,
                    "scheme_type": scheme.scheme_type.value if hasattr(scheme.scheme_type, 'value') else scheme.scheme_type,
                    "benefit_amount": scheme.benefit_amount if scheme else None,
                    "eligibility_criteria": scheme.eligibility_criteria if scheme else None,
                    "required_documents": scheme.required_documents if scheme else None
                } if scheme else None,
                "application_data": app_data
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch application details: {str(e)}"
        )

# ✅ Update application status (admin only)
@router.put("/applications/{application_id}/status")
async def update_application_status_admin(
    application_id: int,
    status: str,
    approved_amount: Optional[float] = None,
    remarks: Optional[str] = None,
    current_user = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Update application status (admin only)"""
    try:
        # Validate status
        valid_statuses = ["pending", "under_review", "approved", "rejected", "completed", "docs_needed"]
        if status not in valid_statuses:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid status. Must be one of: {', '.join(valid_statuses)}"
            )
        
        # Update application status
        application = update_application_status(db, application_id, status, approved_amount)
        if not application:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Application not found"
            )
        
        # Add remarks to application data if provided
        if remarks:
            app_data = application.application_data or {}
            if "admin_remarks" not in app_data:
                app_data["admin_remarks"] = []
            app_data["admin_remarks"].append({
                "remarks": remarks,
                "admin": current_user.full_name,
                "timestamp": datetime.utcnow().isoformat()
            })
            application.application_data = app_data
            db.commit()
        
        return {
            "success": True,
            "message": f"Application status updated to {status}",
            "application_id": application_id,
            "new_status": status,
            "approved_amount": approved_amount,
            "updated_at": application.updated_at,
            "admin": current_user.full_name
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update application status: {str(e)}"
        )

# ✅ Get all schemes (admin version - shows all including inactive)
@router.get("/schemes", response_model=List[SchemeResponse])
async def get_all_schemes_admin(
    active_only: bool = False,
    skip: int = 0,
    limit: int = 100,
    search: Optional[str] = None,
    current_user = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Get all schemes (admin version - shows all including inactive)"""
    try:
        schemes = get_all_schemes(db, skip, limit, active_only)
        
        # Apply search filter if provided
        if search:
            search = search.lower()
            schemes = [
                scheme for scheme in schemes
                if (search in scheme.scheme_name.lower() or
                    search in scheme.scheme_code.lower() or
                    (scheme.description and search in scheme.description.lower()))
            ]
        
        return schemes
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch schemes: {str(e)}"
        )

# ✅ Get top schemes by number of applications
@router.get("/schemes/top")
async def get_top_schemes(
    limit: int = 5,
    current_user = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Get top schemes by number of applications"""
    try:
        # Query to get top schemes
        top_schemes = db.query(
            GovernmentScheme.scheme_name,
            func.count(Application.id).label('application_count'),
            func.sum(Application.approved_amount).label('total_benefits')
        ).join(Application, GovernmentScheme.id == Application.scheme_id, isouter=True)\
         .group_by(GovernmentScheme.id)\
         .order_by(func.count(Application.id).desc())\
         .limit(limit)\
         .all()
        
        result = [
            {
                "scheme_name": scheme.scheme_name,
                "application_count": scheme.application_count or 0,
                "total_benefits": float(scheme.total_benefits or 0)
            }
            for scheme in top_schemes
        ]
        
        return {
            "success": True,
            "top_schemes": result
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch top schemes: {str(e)}"
        )

# ✅ Get all pending documents for verification
@router.get("/documents/pending")
async def get_pending_documents(
    skip: int = 0,
    limit: int = 100,
    search: Optional[str] = None,
    current_user = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Get all pending documents for verification"""
    try:
        documents = db.query(Document)\
            .filter(Document.verified == False)\
            .order_by(Document.uploaded_at.desc())\
            .offset(skip).limit(limit)\
            .all()
        
        result = []
        for doc in documents:
            # Get user details
            user = get_user_by_id(db, doc.user_id)
            
            doc_data = {
                "id": doc.id,
                "document_type": doc.document_type.value if hasattr(doc.document_type, 'value') else doc.document_type,
                "file_name": doc.file_name,
                "file_path": doc.file_path,
                "uploaded_at": doc.uploaded_at,
                "verified": doc.verified,
                "verification_date": doc.verification_date,
                "extracted_data": doc.extracted_data,
                "user": {
                    "id": user.id if user else None,
                    "farmer_id": user.farmer_id if user else None,
                    "full_name": user.full_name if user else "Unknown",
                    "mobile_number": user.mobile_number if user else None
                } if user else None
            }
            
            # Apply search filter
            if search:
                search_lower = search.lower()
                matches = (
                    (doc_data["user"] and doc_data["user"]["full_name"] and search_lower in doc_data["user"]["full_name"].lower()) or
                    (doc_data["document_type"] and search_lower in str(doc_data["document_type"]).lower())
                )
                if not matches:
                    continue
            
            result.append(doc_data)
        
        return {
            "success": True,
            "count": len(result),
            "pending_documents": result
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch pending documents: {str(e)}"
        )

# ✅ Get document details for verification
@router.get("/documents/{document_id}")
async def get_document_details(
    document_id: int,
    current_user = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Get document details for verification"""
    try:
        document = get_document_by_id(db, document_id)
        if not document:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document not found"
            )
        
        # Get user details
        user = get_user_by_id(db, document.user_id)
        
        return {
            "success": True,
            "document": {
                "id": document.id,
                "document_type": document.document_type.value if hasattr(document.document_type, 'value') else document.document_type,
                "file_name": document.file_name,
                "file_path": document.file_path,
                "file_size": document.file_size,
                "uploaded_at": document.uploaded_at,
                "verified": document.verified,
                "verification_date": document.verification_date,
                "extracted_data": document.extracted_data,
                "user": {
                    "id": user.id if user else None,
                    "farmer_id": user.farmer_id if user else None,
                    "full_name": user.full_name if user else "Unknown",
                    "mobile_number": user.mobile_number if user else None,
                    "email": user.email if user else None
                } if user else None,
                "file_url": f"/uploads/user_{document.user_id}/{document.file_name}" if document.file_path else None
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch document details: {str(e)}"
        )

# ✅ Verify or reject a document (admin only)
@router.put("/documents/{document_id}/verify")
async def verify_document_admin_endpoint(
    document_id: int,
    status: str,  # "verified" or "rejected"
    remarks: Optional[str] = None,
    current_user = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Verify or reject a document (admin only)"""
    try:
        if status not in ["verified", "rejected"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Status must be 'verified' or 'rejected'"
            )
        
        verified = status == "verified"
        
        # Verify document using crud function
        document = update_document_verification(db, document_id, verified, {"admin_remarks": remarks} if remarks else None)
        if not document:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document not found"
            )
        
        return {
            "success": True,
            "message": f"Document {'verified' if verified else 'rejected'} successfully",
            "document_id": document_id,
            "status": status,
            "verified": verified,
            "verification_date": document.verification_date,
            "admin": current_user.full_name
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to verify document: {str(e)}"
        )

# ✅ Get admin notifications (system-wide)
@router.get("/notifications")
async def get_admin_notifications(
    unread_only: bool = False,
    limit: int = 20,
    current_user = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Get admin notifications (system-wide)"""
    try:
        # Get system notifications
        query = db.query(Notification)\
            .order_by(Notification.created_at.desc())
        
        if unread_only:
            query = query.filter(Notification.read == False)
        
        notifications = query.limit(limit).all()
        
        result = []
        for notif in notifications:
            # Get user details for user-specific notifications
            user = None
            if notif.user_id:
                user = get_user_by_id(db, notif.user_id)
            
            result.append({
                "id": notif.id,
                "title": notif.title,
                "message": notif.message,
                "notification_type": notif.notification_type,
                "read": notif.read,
                "created_at": notif.created_at,
                "user": {
                    "id": user.id if user else None,
                    "full_name": user.full_name if user else None,
                    "farmer_id": user.farmer_id if user else None
                } if user else None
            })
        
        return {
            "success": True,
            "notifications": result
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch notifications: {str(e)}"
        )

# ✅ Mark notifications as read
@router.post("/notifications/mark-read")
async def mark_notifications_read(
    notification_ids: List[int],
    current_user = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Mark notifications as read"""
    try:
        updated = []
        for notif_id in notification_ids:
            notification = mark_notification_as_read(db, notif_id)
            if notification:
                updated.append(notif_id)
        
        return {
            "success": True,
            "message": f"Marked {len(updated)} notifications as read",
            "updated_ids": updated
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to mark notifications as read: {str(e)}"
        )

# ✅ Generate admin reports
@router.get("/reports/generate")
async def generate_report(
    period: str = "30",  # days
    current_user = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Generate admin reports"""
    try:
        days = int(period)
        start_date = datetime.utcnow() - timedelta(days=days)
        
        # Get statistics for the period
        total_applications = db.query(func.count(Application.id))\
            .filter(Application.applied_at >= start_date)\
            .scalar() or 0
        
        approved_applications = db.query(func.count(Application.id))\
            .filter(Application.applied_at >= start_date)\
            .filter(Application.status == "approved")\
            .scalar() or 0
        
        total_benefits = db.query(func.sum(Application.approved_amount))\
            .filter(Application.applied_at >= start_date)\
            .filter(Application.status == "approved")\
            .scalar() or 0
        
        new_users = db.query(func.count(User.id))\
            .filter(User.created_at >= start_date)\
            .filter(User.role == UserRole.FARMER)\
            .scalar() or 0
        
        # Get applications by status
        status_distribution = {}
        status_counts = db.query(Application.status, func.count(Application.id))\
            .filter(Application.applied_at >= start_date)\
            .group_by(Application.status)\
            .all()
        
        for status, count in status_counts:
            status_key = status.value if hasattr(status, 'value') else status
            status_distribution[status_key] = count
        
        # Get applications trend (last 7 days)
        if days <= 7:
            trend_labels = []
            trend_data = []
            
            for i in range(days):
                day = start_date + timedelta(days=i)
                day_end = day + timedelta(days=1)
                
                day_count = db.query(func.count(Application.id))\
                    .filter(Application.applied_at >= day)\
                    .filter(Application.applied_at < day_end)\
                    .scalar() or 0
                
                trend_labels.append(day.strftime("%d-%b"))
                trend_data.append(day_count)
        else:
            # Weekly aggregation for longer periods
            trend_labels = ["Week 1", "Week 2", "Week 3", "Week 4"]
            trend_data = [0, 0, 0, 0]
            
            for i in range(4):
                week_start = start_date + timedelta(weeks=i)
                week_end = week_start + timedelta(weeks=1)
                
                week_count = db.query(func.count(Application.id))\
                    .filter(Application.applied_at >= week_start)\
                    .filter(Application.applied_at < week_end)\
                    .scalar() or 0
                
                trend_data[i] = week_count
        
        return {
            "success": True,
            "period_days": days,
            "start_date": start_date.isoformat(),
            "end_date": datetime.utcnow().isoformat(),
            "total_applications": total_applications,
            "approved_applications": approved_applications,
            "approval_rate": (approved_applications / total_applications * 100) if total_applications > 0 else 0,
            "total_benefits": float(total_benefits),
            "new_users": new_users,
            "status_distribution": status_distribution,
            "applications_trend": {
                "labels": trend_labels,
                "data": trend_data
            }
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate report: {str(e)}"
        )

# ✅ Delete or deactivate a scheme
@router.delete("/schemes/{scheme_id}")
async def delete_scheme(
    scheme_id: int,
    current_user = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Delete a scheme (admin only)"""
    try:
        scheme = get_scheme_by_id(db, scheme_id)
        if not scheme:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Scheme not found"
            )
        
        # Check if scheme has applications
        applications_count = db.query(func.count(Application.id))\
            .filter(Application.scheme_id == scheme_id)\
            .scalar() or 0
        
        if applications_count > 0:
            # Don't delete, just deactivate
            scheme.is_active = False
            db.commit()
            
            return {
                "success": True,
                "message": "Scheme has applications. Deactivated instead of deleted.",
                "scheme_id": scheme_id,
                "deactivated": True,
                "applications_count": applications_count
            }
        else:
            # Delete the scheme
            db.delete(scheme)
            db.commit()
            
            return {
                "success": True,
                "message": "Scheme deleted successfully",
                "scheme_id": scheme_id,
                "deleted": True
            }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete scheme: {str(e)}"
        )

# ✅ Make a user admin
@router.post("/users/{user_id}/promote")
async def promote_to_admin(
    user_id: int,
    current_user = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Promote a user to admin role"""
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        if user.role == UserRole.ADMIN:
            raise HTTPException(status_code=400, detail="User is already admin")
        
        user.role = UserRole.ADMIN
        db.commit()
        db.refresh(user)
        
        return {
            "success": True,
            "message": f"User {user.full_name} promoted to admin",
            "user": {
                "id": user.id,
                "name": user.full_name,
                "mobile": user.mobile_number,
                "role": user.role.value
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to promote user: {str(e)}"
        )
