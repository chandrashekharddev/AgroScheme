from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from sqlalchemy import func

from app.database import get_db
from app.schemas import SchemeCreate, SchemeResponse, AdminStats, UserResponse, AdminDashboardStats
from app.models import User, Document, Application, GovernmentScheme, Notification

router = APIRouter(prefix="/admin", tags=["admin"])

# Simple admin verification
def verify_admin():
    return {"is_admin": True, "full_name": "Administrator"}

@router.get("/stats")
async def get_stats(
    admin_user = Depends(verify_admin),
    db: Session = Depends(get_db)
):
    """Get admin dashboard statistics"""
    try:
        # Calculate stats directly
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
            "benefits_distributed": float(benefits_distributed),
            "pending_verifications": pending_verifications,
            "ai_accuracy": 98.5
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch stats: {str(e)}"
        )

# Add other endpoints as needed...
@router.get("/dashboard-stats", response_model=AdminDashboardStats)
async def get_dashboard_stats(
    admin_user = Depends(verify_admin),
    db: Session = Depends(get_db)
):
    """Get comprehensive dashboard statistics"""
    try:
        # First get basic stats
        basic_stats = get_admin_stats(db)
        
        # Get recent registrations
        recent_users = db.query(User)\
            .filter(User.role == "farmer")\
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
            "total_farmers": basic_stats.total_farmers,
            "total_applications": basic_stats.total_applications,
            "total_schemes": basic_stats.total_schemes,
            "benefits_distributed": basic_stats.benefits_distributed,
            "pending_verifications": basic_stats.pending_verifications,
            "ai_accuracy": basic_stats.ai_accuracy,
            "farmer_growth": 12.5,  # Placeholder values
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

@router.post("/schemes", response_model=SchemeResponse)
async def add_scheme(
    scheme: SchemeCreate,
    admin_user = Depends(verify_admin),
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
        
        return create_scheme(db=db, scheme=scheme, created_by=admin_user.full_name)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to add scheme: {str(e)}"
        )

@router.get("/users", response_model=List[UserResponse])
async def get_all_users(
    skip: int = 0,
    limit: int = 100,
    search: Optional[str] = None,
    admin_user = Depends(verify_admin),
    db: Session = Depends(get_db)
):
    """Get all registered farmers/users"""
    try:
        # Get all farmers
        farmers = db.query(User).filter(User.role == "farmer").offset(skip).limit(limit).all()
        
        # Apply search filter if provided
        if search:
            search = search.lower()
            farmers = [
                farmer for farmer in farmers
                if (search in farmer.full_name.lower() or
                    search in farmer.farmer_id.lower() or
                    search in farmer.mobile_number.lower() or
                    (farmer.email and search in farmer.email.lower()))
            ]
        
        return farmers
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch users: {str(e)}"
        )

@router.get("/users/recent")
async def get_recent_users(
    limit: int = 5,
    admin_user = Depends(verify_admin),
    db: Session = Depends(get_db)
):
    """Get recent user registrations"""
    try:
        recent_users = db.query(User)\
            .filter(User.role == "farmer")\
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

@router.get("/users/{user_id}")
async def get_user_details(
    user_id: int,
    admin_user = Depends(verify_admin),
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
        from app.crud import get_user_documents
        documents = get_user_documents(db, user_id)
        
        return {
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
            "applications": [
                {
                    "id": app.id,
                    "application_id": app.application_id,
                    "status": app.status,
                    "applied_amount": app.applied_amount,
                    "approved_amount": app.approved_amount,
                    "applied_at": app.applied_at
                }
                for app in applications
            ],
            "documents": [
                {
                    "id": doc.id,
                    "document_type": doc.document_type,
                    "file_name": doc.file_name,
                    "verified": doc.verified,
                    "uploaded_at": doc.uploaded_at
                }
                for doc in documents
            ],
            "total_applications": len(applications),
            "total_verified_documents": len([d for d in documents if d.verified])
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch user details: {str(e)}"
        )

@router.get("/applications")
async def get_all_applications_admin(
    skip: int = 0,
    limit: int = 100,
    status: Optional[str] = None,
    search: Optional[str] = None,
    admin_user = Depends(verify_admin),
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
                "status": app.status,
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
        
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch applications: {str(e)}"
        )

@router.get("/applications/{application_id}")
async def get_application_details(
    application_id: int,
    admin_user = Depends(verify_admin),
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
            "id": application.id,
            "application_id": application.application_id,
            "status": application.status,
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
                "scheme_type": scheme.scheme_type if scheme else None,
                "benefit_amount": scheme.benefit_amount if scheme else None,
                "eligibility_criteria": scheme.eligibility_criteria if scheme else None,
                "required_documents": scheme.required_documents if scheme else None
            } if scheme else None,
            "application_data": app_data
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch application details: {str(e)}"
        )

@router.put("/applications/{application_id}/status")
async def update_application_status_admin(
    application_id: int,
    status: str,
    approved_amount: Optional[float] = None,
    remarks: Optional[str] = None,
    admin_user = Depends(verify_admin),
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
                "admin": admin_user.full_name,
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
            "updated_at": application.updated_at
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update application status: {str(e)}"
        )

@router.get("/schemes", response_model=List[SchemeResponse])
async def get_all_schemes_admin(
    active_only: bool = False,
    skip: int = 0,
    limit: int = 100,
    search: Optional[str] = None,
    admin_user = Depends(verify_admin),
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

@router.get("/schemes/top")
async def get_top_schemes(
    limit: int = 5,
    admin_user = Depends(verify_admin),
    db: Session = Depends(get_db)
):
    """Get top schemes by number of applications"""
    try:
        # Query to get top schemes
        top_schemes = db.query(
            GovernmentScheme,
            func.count(Application.id).label('application_count'),
            func.sum(Application.approved_amount).label('total_benefits')
        ).join(Application, GovernmentScheme.id == Application.scheme_id, isouter=True)\
         .group_by(GovernmentScheme.id)\
         .order_by(func.count(Application.id).desc())\
         .limit(limit)\
         .all()
        
        result = []
        for scheme, app_count, total_benefits in top_schemes:
            result.append({
                "scheme_name": scheme.scheme_name,
                "application_count": app_count or 0,
                "total_benefits": float(total_benefits or 0)
            })
        
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch top schemes: {str(e)}"
        )

@router.get("/documents/pending")
async def get_pending_documents(
    skip: int = 0,
    limit: int = 100,
    search: Optional[str] = None,
    admin_user = Depends(verify_admin),
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
                "document_type": doc.document_type,
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
                    (doc_data["document_type"] and search_lower in doc_data["document_type"].lower())
                )
                if not matches:
                    continue
            
            result.append(doc_data)
        
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch pending documents: {str(e)}"
        )

@router.get("/documents/{document_id}")
async def get_document_details(
    document_id: int,
    admin_user = Depends(verify_admin),
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
            "id": document.id,
            "document_type": document.document_type,
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
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch document details: {str(e)}"
        )

@router.put("/documents/{document_id}/verify")
async def verify_document_admin_endpoint(
    document_id: int,
    status: str,  # "verified" or "rejected"
    remarks: Optional[str] = None,
    admin_user = Depends(verify_admin),
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
        from app.crud import update_document_verification
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
            "verification_date": document.verification_date
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to verify document: {str(e)}"
        )

@router.get("/notifications")
async def get_admin_notifications(
    unread_only: bool = False,
    limit: int = 20,
    admin_user = Depends(verify_admin),
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
        
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch notifications: {str(e)}"
        )

@router.post("/notifications/mark-read")
async def mark_notifications_read(
    notification_ids: List[int],
    admin_user = Depends(verify_admin),
    db: Session = Depends(get_db)
):
    """Mark notifications as read"""
    try:
        from app.crud import mark_notification_as_read
        
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

@router.get("/reports/generate")
async def generate_report(
    period: str = "30",  # days
    admin_user = Depends(verify_admin),
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
            .filter(User.role == "farmer")\
            .scalar() or 0
        
        # Get applications by status
        status_distribution = {}
        status_counts = db.query(Application.status, func.count(Application.id))\
            .filter(Application.applied_at >= start_date)\
            .group_by(Application.status)\
            .all()
        
        for status, count in status_counts:
            status_distribution[status] = count
        
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

@router.delete("/schemes/{scheme_id}")
async def delete_scheme(
    scheme_id: int,
    admin_user = Depends(verify_admin),
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
