# app/routers/admin.py - COMPLETE JSON VERSION
from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from sqlalchemy.orm import Session
from sqlalchemy import func, extract
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
from app.database import get_db
from app.schemas import SchemeCreate, SchemeResponse, AdminStats, UserResponse, AdminDashboardStats
from app.models import User, Document, Application, GovernmentScheme, Notification, UserRole
from app.crud import (
    get_user_by_id, get_scheme_by_code, create_scheme, get_scheme_by_id,
    get_all_schemes, get_application_by_id, update_application_status,
    get_document_by_id, update_document_verification, mark_notification_as_read,
    get_user_applications, get_user_documents
)

router = APIRouter(prefix="/admin", tags=["admin"])

# ==================== PYDANTIC MODELS ====================

class ApplicationCreate(BaseModel):
    scheme_id: int
    farmer_id: Optional[str] = None
    farmer_name: Optional[str] = None
    applied_amount: float = 0

class ApplicationStatusUpdate(BaseModel):
    status: str
    approved_amount: Optional[float] = None
    remarks: Optional[str] = None

class DocumentVerifyRequest(BaseModel):
    status: str  # "verified" or "rejected"
    remarks: Optional[str] = None

class NotificationMarkReadRequest(BaseModel):
    notification_ids: List[int]

class PromoteUserRequest(BaseModel):
    user_id: int

# ==================== STATIC PAGES ====================

@router.get("/admin.html")
async def serve_admin_page():
    """Serve the admin HTML page"""
    try:
        return FileResponse("static/admin.html")
    except FileNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Admin page not found"
        )

# ==================== ADMIN AUTH ====================

@router.get("/check")
async def check_admin_status():
    """Check admin status"""
    return JSONResponse({
        "success": True,
        "is_admin": True,
        "user": {
            "id": 1,
            "name": "Administrator",
            "mobile": "9999999999",
            "email": "admin@agroscheme.com",
            "role": "admin"
        }
    })

# ==================== DASHBOARD STATS ====================

@router.get("/stats")
async def get_stats(db: Session = Depends(get_db)):
    """Get admin dashboard statistics"""
    try:
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
        
        pending_applications = db.query(func.count(Application.id)).filter(
            Application.status == "pending"
        ).scalar() or 0
        
        return JSONResponse({
            "success": True,
            "total_farmers": total_farmers,
            "total_admins": total_admins,
            "total_applications": total_applications,
            "total_schemes": total_schemes,
            "benefits_distributed": float(benefits_distributed),
            "pending_verifications": pending_verifications,
            "pending_applications": pending_applications,
            "ai_accuracy": 98.5,
            "admin_name": "Administrator",
            "admin_role": "admin"
        })
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch stats: {str(e)}"
        )

@router.get("/dashboard-stats")
async def get_dashboard_stats(db: Session = Depends(get_db)):
    """Get comprehensive dashboard statistics"""
    try:
        total_farmers = db.query(func.count(User.id)).filter(User.role == UserRole.FARMER).scalar() or 0
        total_applications = db.query(func.count(Application.id)).scalar() or 0
        total_schemes = db.query(func.count(GovernmentScheme.id)).scalar() or 0
        benefits_distributed = db.query(func.sum(Application.approved_amount)).filter(
            Application.status == "approved"
        ).scalar() or 0
        pending_verifications = db.query(func.count(Document.id)).filter(
            Document.verified == False
        ).scalar() or 0
        
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
                "created_at": user.created_at.isoformat() if user.created_at else None
            }
            for user in recent_users
        ]
        
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
        
        return JSONResponse({
            "success": True,
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
        })
        
    except Exception as e:
        print(f"Error in get_dashboard_stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch dashboard stats: {str(e)}"
        )

# ==================== APPLICATIONS ====================

@router.post("/applications")
async def create_application(
    request: Request,
    application: ApplicationCreate,
    db: Session = Depends(get_db)
):
    """Submit a new application - JSON ONLY"""
    origin = request.headers.get("origin", "")
    
    try:
        print("="*50)
        print(f"📝 CREATE APPLICATION CALLED")
        print(f"   scheme_id: {application.scheme_id}")
        print(f"   farmer_id: {application.farmer_id}")
        print(f"   farmer_name: {application.farmer_name}")
        print(f"   applied_amount: {application.applied_amount}")
        
        # Get user by farmer_id or find by name
        user = None
        if application.farmer_id:
            user = db.query(User).filter(User.farmer_id == application.farmer_id).first()
        
        if not user and application.farmer_name:
            user = db.query(User).filter(User.full_name.ilike(f"%{application.farmer_name}%")).first()
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Farmer not found"
            )
        
        scheme = get_scheme_by_id(db, application.scheme_id)
        if not scheme:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Scheme not found"
            )
        
        current_year = datetime.utcnow().year
        app_count = db.query(func.count(Application.id)).filter(
            extract('year', Application.applied_at) == current_year
        ).scalar() or 0
        
        application_id = f"APP{current_year}{str(app_count + 1).zfill(5)}"
        
        new_application = Application(
            application_id=application_id,
            user_id=user.id,
            scheme_id=scheme.id,
            applied_amount=application.applied_amount,
            status="pending",
            applied_at=datetime.utcnow(),
            application_data={
                "farmer_id": user.farmer_id,
                "farmer_name": user.full_name,
                "scheme_name": scheme.scheme_name,
                "scheme_code": scheme.scheme_code,
                "applied_amount": application.applied_amount,
                "applied_at": datetime.utcnow().isoformat(),
                "applied_via": "farmer_portal"
            },
            submitted_documents=[],
            status_history=[{
                "status": "pending",
                "timestamp": datetime.utcnow().isoformat(),
                "note": "Application submitted by farmer"
            }]
        )
        
        db.add(new_application)
        db.commit()
        db.refresh(new_application)
        
        print(f"✅✅✅ APPLICATION SAVED! ID: {new_application.id}")
        
        notification = Notification(
            user_id=user.id,
            title="Application Submitted",
            message=f"Your application for {scheme.scheme_name} has been submitted",
            notification_type="application",
            related_scheme_id=scheme.id,
            related_application_id=new_application.id,
            read=False,
            created_at=datetime.utcnow()
        )
        db.add(notification)
        db.commit()
        
        response = JSONResponse({
            "success": True,
            "message": "Application submitted successfully",
            "application_id": application_id,
            "application_db_id": new_application.id,
            "status": "pending"
        })
        
        if origin and "vercel.app" in origin:
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Allow-Credentials"] = "true"
        
        return response
        
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        print(f"❌ ERROR: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to submit application: {str(e)}"
        )

@router.get("/applications")  # ✅ NO trailing slash
async def get_all_applications_admin(
    skip: int = 0,
    limit: int = 100,
    status: Optional[str] = Query(None, description="Filter by status"),
    search: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Get all applications with filters - ENHANCED VERSION"""
    try:
        print("="*50)
        print(f"📋 GET /admin/applications called")
        print(f"   Params: skip={skip}, limit={limit}, status={status}, search={search}")
        
        # Build query with eager loading
        query = db.query(Application).options(
            db.joinedload(Application.user),
            db.joinedload(Application.scheme)
        )
        
        # Apply status filter
        if status:
            valid_statuses = ["pending", "under_review", "approved", "rejected", "docs_needed", "completed"]
            if status not in valid_statuses:
                return JSONResponse({
                    "success": False,
                    "error": f"Invalid status. Must be one of: {', '.join(valid_statuses)}",
                    "applications": []
                })
            query = query.filter(Application.status == status)
        
        # Get total count first
        total_count = query.count()
        print(f"📊 Total applications in DB (with filters): {total_count}")
        
        # Get applications with order
        applications = query.order_by(Application.applied_at.desc()).offset(skip).limit(limit).all()
        
        print(f"✅ Found {len(applications)} applications in this batch")
        
        result = []
        for app in applications:
            try:
                # Safely get status string
                status_value = app.status
                if hasattr(status_value, 'value'):
                    status_value = status_value.value
                
                # Safely get user data
                user_data = None
                if app.user:
                    user_data = {
                        "id": app.user.id,
                        "farmer_id": app.user.farmer_id,
                        "full_name": app.user.full_name or "Unknown",
                        "mobile_number": app.user.mobile_number,
                        "email": app.user.email,
                        "state": app.user.state,
                        "district": app.user.district
                    }
                else:
                    # Try to get user from database if not loaded
                    if app.user_id:
                        user = db.query(User).filter(User.id == app.user_id).first()
                        if user:
                            user_data = {
                                "id": user.id,
                                "farmer_id": user.farmer_id,
                                "full_name": user.full_name or "Unknown",
                                "mobile_number": user.mobile_number,
                                "email": user.email,
                                "state": user.state,
                                "district": user.district
                            }
                
                # Safely get scheme data
                scheme_data = None
                if app.scheme:
                    scheme_data = {
                        "id": app.scheme.id,
                        "scheme_name": app.scheme.scheme_name or "Unknown",
                        "scheme_code": app.scheme.scheme_code,
                        "benefit_amount": float(app.scheme.benefit_amount) if app.scheme.benefit_amount else 0,
                        "scheme_type": app.scheme.scheme_type.value if hasattr(app.scheme.scheme_type, 'value') else app.scheme.scheme_type
                    }
                else:
                    # Try to get scheme from database if not loaded
                    if app.scheme_id:
                        scheme = db.query(GovernmentScheme).filter(GovernmentScheme.id == app.scheme_id).first()
                        if scheme:
                            scheme_data = {
                                "id": scheme.id,
                                "scheme_name": scheme.scheme_name or "Unknown",
                                "scheme_code": scheme.scheme_code,
                                "benefit_amount": float(scheme.benefit_amount) if scheme.benefit_amount else 0,
                                "scheme_type": scheme.scheme_type.value if hasattr(scheme.scheme_type, 'value') else scheme.scheme_type
                            }
                
                app_data = {
                    "id": app.id,
                    "application_id": app.application_id or f"APP{app.id}",
                    "status": status_value,
                    "applied_amount": float(app.applied_amount) if app.applied_amount else 0,
                    "approved_amount": float(app.approved_amount) if app.approved_amount else 0,
                    "applied_at": app.applied_at.isoformat() if app.applied_at else None,
                    "updated_at": app.updated_at.isoformat() if app.updated_at else None,
                    "user_id": app.user_id,
                    "scheme_id": app.scheme_id,
                    "user": user_data,
                    "scheme": scheme_data,
                    "application_data": app.application_data or {}
                }
                
                # Apply search filter if needed
                if search and search.strip():
                    search_lower = search.lower().strip()
                    matches = False
                    
                    if app_data["application_id"] and search_lower in app_data["application_id"].lower():
                        matches = True
                    if app_data["user"] and app_data["user"]["full_name"] and search_lower in app_data["user"]["full_name"].lower():
                        matches = True
                    if app_data["scheme"] and app_data["scheme"]["scheme_name"] and search_lower in app_data["scheme"]["scheme_name"].lower():
                        matches = True
                    
                    if not matches:
                        continue
                
                result.append(app_data)
                
            except Exception as e:
                print(f"⚠️ Error processing application {app.id}: {e}")
                import traceback
                traceback.print_exc()
                continue
        
        print(f"✅ Returning {len(result)} applications after processing")
        
        # ENSURE THE RESPONSE FORMAT MATCHES WHAT FRONTEND EXPECTS
        response_data = {
            "success": True,
            "count": len(result),
            "applications": result,  # This is what frontend looks for
            "total": total_count
        }
        
        # Log the first application for debugging
        if result and len(result) > 0:
            print(f"📋 Sample application: ID={result[0]['id']}, Status={result[0]['status']}, Farmer={result[0]['user']['full_name'] if result[0]['user'] else 'None'}")
        
        return JSONResponse(response_data)
        
    except Exception as e:
        print(f"❌ CRITICAL ERROR in get_all_applications_admin: {str(e)}")
        import traceback
        traceback.print_exc()
        # Return empty array with error info - but maintain the format frontend expects
        return JSONResponse({
            "success": False,
            "error": str(e),
            "applications": [],  # Empty array, not null
            "count": 0
        })

@router.get("/applications/{application_id}")
async def get_application_details(
    application_id: int,
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
        
        user = get_user_by_id(db, application.user_id)
        scheme = get_scheme_by_id(db, application.scheme_id)
        app_data = application.application_data or {}
        
        return JSONResponse({
            "success": True,
            "application": {
                "id": application.id,
                "application_id": application.application_id,
                "status": application.status.value if hasattr(application.status, 'value') else application.status,
                "applied_amount": float(application.applied_amount) if application.applied_amount else 0,
                "approved_amount": float(application.approved_amount) if application.approved_amount else 0,
                "applied_at": application.applied_at.isoformat() if application.applied_at else None,
                "updated_at": application.updated_at.isoformat() if application.updated_at else None,
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
        })
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
    status_update: ApplicationStatusUpdate,
    db: Session = Depends(get_db)
):
    """Update application status - JSON ONLY"""
    try:
        valid_statuses = ["pending", "under_review", "approved", "rejected", "completed", "docs_needed"]
        if status_update.status not in valid_statuses:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid status. Must be one of: {', '.join(valid_statuses)}"
            )
        
        application = update_application_status(
            db, 
            application_id, 
            status_update.status, 
            status_update.approved_amount
        )
        
        if not application:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Application not found"
            )
        
        if status_update.remarks:
            app_data = application.application_data or {}
            if "admin_remarks" not in app_data:
                app_data["admin_remarks"] = []
            app_data["admin_remarks"].append({
                "remarks": status_update.remarks,
                "admin": "Administrator",
                "timestamp": datetime.utcnow().isoformat()
            })
            application.application_data = app_data
            db.commit()
        
        return JSONResponse({
            "success": True,
            "message": f"Application status updated to {status_update.status}",
            "application_id": application_id,
            "new_status": status_update.status,
            "approved_amount": status_update.approved_amount,
            "updated_at": application.updated_at.isoformat() if application.updated_at else None,
            "admin": "Administrator"
        })
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update application status: {str(e)}"
        )

# ==================== SCHEMES ====================

@router.post("/schemes", response_model=SchemeResponse)
async def add_scheme(
    scheme: SchemeCreate,
    db: Session = Depends(get_db)
):
    """Add a new government scheme"""
    try:
        existing_scheme = get_scheme_by_code(db, scheme.scheme_code)
        if existing_scheme:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Scheme with code '{scheme.scheme_code}' already exists"
            )
        
        return create_scheme(db=db, scheme=scheme, created_by="Administrator")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to add scheme: {str(e)}"
        )

@router.get("/schemes", response_model=List[SchemeResponse])
async def get_all_schemes_admin(
    active_only: bool = False,
    skip: int = 0,
    limit: int = 100,
    search: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Get all schemes (admin version)"""
    try:
        schemes = get_all_schemes(db, skip, limit, active_only)
        
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
    db: Session = Depends(get_db)
):
    """Get top schemes by number of applications"""
    try:
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
        
        return JSONResponse({
            "success": True,
            "top_schemes": result
        })
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch top schemes: {str(e)}"
        )

@router.delete("/schemes/{scheme_id}")
async def delete_scheme(
    scheme_id: int,
    db: Session = Depends(get_db)
):
    """Delete or deactivate a scheme"""
    try:
        scheme = get_scheme_by_id(db, scheme_id)
        if not scheme:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Scheme not found"
            )
        
        applications_count = db.query(func.count(Application.id))\
            .filter(Application.scheme_id == scheme_id)\
            .scalar() or 0
        
        if applications_count > 0:
            scheme.is_active = False
            db.commit()
            return JSONResponse({
                "success": True,
                "message": "Scheme has applications. Deactivated instead of deleted.",
                "scheme_id": scheme_id,
                "deactivated": True,
                "applications_count": applications_count
            })
        else:
            db.delete(scheme)
            db.commit()
            return JSONResponse({
                "success": True,
                "message": "Scheme deleted successfully",
                "scheme_id": scheme_id,
                "deleted": True
            })
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete scheme: {str(e)}"
        )

# ==================== USERS ====================

@router.get("/users", response_model=List[UserResponse])
async def get_all_users(
    skip: int = 0,
    limit: int = 100,
    search: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Get all registered farmers/users"""
    try:
        farmers = db.query(User).filter(User.role == UserRole.FARMER).offset(skip).limit(limit).all()
        
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

@router.get("/users/recent")
async def get_recent_users(
    limit: int = 5,
    db: Session = Depends(get_db)
):
    """Get recent user registrations"""
    try:
        recent_users = db.query(User)\
            .filter(User.role == UserRole.FARMER)\
            .order_by(User.created_at.desc())\
            .limit(limit)\
            .all()
        
        return JSONResponse([
            {
                "id": user.id,
                "farmer_id": user.farmer_id,
                "full_name": user.full_name,
                "mobile_number": user.mobile_number,
                "email": user.email,
                "state": user.state,
                "created_at": user.created_at.isoformat() if user.created_at else None
            }
            for user in recent_users
        ])
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch recent users: {str(e)}"
        )

@router.get("/users/{user_id}")
async def get_user_details(
    user_id: int,
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
        
        applications = get_user_applications(db, user_id)
        documents = get_user_documents(db, user_id)
        
        return JSONResponse({
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
                "total_land_acres": float(user.total_land_acres) if user.total_land_acres else None,
                "annual_income": float(user.annual_income) if user.annual_income else None,
                "land_type": user.land_type,
                "main_crops": user.main_crops,
                "bank_account_number": user.bank_account_number,
                "ifsc_code": user.ifsc_code,
                "created_at": user.created_at.isoformat() if user.created_at else None,
                "role": user.role.value
            },
            "applications": [
                {
                    "id": app.id,
                    "application_id": app.application_id,
                    "status": app.status.value if hasattr(app.status, 'value') else app.status,
                    "applied_amount": float(app.applied_amount) if app.applied_amount else 0,
                    "approved_amount": float(app.approved_amount) if app.approved_amount else 0,
                    "applied_at": app.applied_at.isoformat() if app.applied_at else None
                }
                for app in applications
            ],
            "documents": [
                {
                    "id": doc.id,
                    "document_type": doc.document_type.value if hasattr(doc.document_type, 'value') else doc.document_type,
                    "file_name": doc.file_name,
                    "verified": doc.verified,
                    "uploaded_at": doc.uploaded_at.isoformat() if doc.uploaded_at else None
                }
                for doc in documents
            ],
            "stats": {
                "total_applications": len(applications),
                "total_verified_documents": len([d for d in documents if d.verified]),
                "approved_applications": len([a for a in applications if a.status == "approved"])
            }
        })
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch user details: {str(e)}"
        )

@router.post("/users/{user_id}/promote")
async def promote_to_admin(
    user_id: int,
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
        
        return JSONResponse({
            "success": True,
            "message": f"User {user.full_name} promoted to admin",
            "user": {
                "id": user.id,
                "name": user.full_name,
                "mobile": user.mobile_number,
                "role": user.role.value
            }
        })
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to promote user: {str(e)}"
        )

# ==================== DOCUMENTS ====================

@router.get("/documents/pending")
async def get_pending_documents(
    skip: int = 0,
    limit: int = 100,
    search: Optional[str] = None,
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
            user = get_user_by_id(db, doc.user_id)
            
            doc_data = {
                "id": doc.id,
                "document_type": doc.document_type.value if hasattr(doc.document_type, 'value') else doc.document_type,
                "file_name": doc.file_name,
                "file_path": doc.file_path,
                "uploaded_at": doc.uploaded_at.isoformat() if doc.uploaded_at else None,
                "verified": doc.verified,
                "verification_date": doc.verification_date.isoformat() if doc.verification_date else None,
                "extracted_data": doc.extracted_data,
                "user": {
                    "id": user.id if user else None,
                    "farmer_id": user.farmer_id if user else None,
                    "full_name": user.full_name if user else "Unknown",
                    "mobile_number": user.mobile_number if user else None
                } if user else None
            }
            
            if search:
                search_lower = search.lower()
                matches = (
                    (doc_data["user"] and doc_data["user"]["full_name"] and search_lower in doc_data["user"]["full_name"].lower()) or
                    (doc_data["document_type"] and search_lower in str(doc_data["document_type"]).lower())
                )
                if not matches:
                    continue
            
            result.append(doc_data)
        
        return JSONResponse({
            "success": True,
            "count": len(result),
            "pending_documents": result
        })
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch pending documents: {str(e)}"
        )

# ==================== DOCUMENTS - FIXED WITH SUPABASE STORAGE ====================

@router.get("/documents/{document_id}")
async def get_document_details(
    document_id: int,
    db: Session = Depends(get_db)
):
    """Get document details for verification with Supabase signed URL"""
    try:
        document = get_document_by_id(db, document_id)
        if not document:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document not found"
            )
        
        user = get_user_by_id(db, document.user_id)
        
        # ✅ GENERATE SIGNED URL FROM SUPABASE STORAGE
        file_url = None
        if document.file_path:
            try:
                from app.supabase_storage import supabase_storage
                # Generate signed URL with 1 hour expiry
                file_url = await supabase_storage.get_document_url(document.file_path)
            except Exception as e:
                print(f"⚠️ Failed to generate signed URL: {e}")
                # Fallback to null - frontend will show placeholder
        
        return JSONResponse({
            "success": True,
            "document": {
                "id": document.id,
                "document_type": document.document_type.value if hasattr(document.document_type, 'value') else document.document_type,
                "file_name": document.file_name,
                "file_path": document.file_path,
                "file_size": document.file_size,
                "file_url": file_url,  # ✅ Now returns Supabase signed URL
                "uploaded_at": document.uploaded_at.isoformat() if document.uploaded_at else None,
                "verified": document.verified,
                "verification_date": document.verification_date.isoformat() if document.verification_date else None,
                "extracted_data": document.extracted_data,
                "user": {
                    "id": user.id if user else None,
                    "farmer_id": user.farmer_id if user else None,
                    "full_name": user.full_name if user else "Unknown",
                    "mobile_number": user.mobile_number if user else None,
                    "email": user.email if user else None
                } if user else None
            }
        })
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error fetching document details: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch document details: {str(e)}"
        )

@router.get("/documents")
async def get_all_documents_admin(
    skip: int = 0,
    limit: int = 100,
    verified: Optional[bool] = None,
    search: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Get all documents with signed URLs (admin view)"""
    try:
        query = db.query(Document)
        
        if verified is not None:
            query = query.filter(Document.verified == verified)
        
        documents = query.order_by(Document.uploaded_at.desc()).offset(skip).limit(limit).all()
        
        result = []
        for doc in documents:
            user = get_user_by_id(db, doc.user_id)
            
            # Generate signed URL for each document
            file_url = None
            if doc.file_path:
                try:
                    from app.supabase_storage import supabase_storage
                    file_url = await supabase_storage.get_document_url(doc.file_path)
                except Exception as e:
                    print(f"⚠️ Failed to generate URL for doc {doc.id}: {e}")
            
            doc_data = {
                "id": doc.id,
                "document_type": doc.document_type.value if hasattr(doc.document_type, 'value') else doc.document_type,
                "file_name": doc.file_name,
                "file_path": doc.file_path,
                "file_url": file_url,
                "file_size": doc.file_size,
                "uploaded_at": doc.uploaded_at.isoformat() if doc.uploaded_at else None,
                "verified": doc.verified,
                "verification_date": doc.verification_date.isoformat() if doc.verification_date else None,
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
                    (doc_data["document_type"] and search_lower in str(doc_data["document_type"]).lower()) or
                    (doc.file_name and search_lower in doc.file_name.lower())
                )
                if not matches:
                    continue
            
            result.append(doc_data)
        
        return JSONResponse({
            "success": True,
            "count": len(result),
            "documents": result
        })
    except Exception as e:
        print(f"❌ Error fetching documents: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch documents: {str(e)}"
        )

@router.put("/documents/{document_id}/verify")
async def verify_document_admin_endpoint(
    document_id: int,
    verify_request: DocumentVerifyRequest,
    db: Session = Depends(get_db)
):
    """Verify or reject a document - JSON ONLY"""
    try:
        if verify_request.status not in ["verified", "rejected"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Status must be 'verified' or 'rejected'"
            )
        
        verified = verify_request.status == "verified"
        
        document = update_document_verification(
            db, 
            document_id, 
            verified, 
            {"admin_remarks": verify_request.remarks} if verify_request.remarks else None
        )
        
        if not document:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document not found"
            )
        
        return JSONResponse({
            "success": True,
            "message": f"Document {'verified' if verified else 'rejected'} successfully",
            "document_id": document_id,
            "status": verify_request.status,
            "verified": verified,
            "verification_date": document.verification_date.isoformat() if document.verification_date else None,
            "admin": "Administrator"
        })
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to verify document: {str(e)}"
        )

# ==================== NOTIFICATIONS ====================

@router.get("/notifications")
async def get_admin_notifications(
    unread_only: bool = False,
    limit: int = 20,
    db: Session = Depends(get_db)
):
    """Get admin notifications"""
    try:
        query = db.query(Notification)\
            .order_by(Notification.created_at.desc())
        
        if unread_only:
            query = query.filter(Notification.read == False)
        
        notifications = query.limit(limit).all()
        
        result = []
        for notif in notifications:
            user = None
            if notif.user_id:
                user = get_user_by_id(db, notif.user_id)
            
            result.append({
                "id": notif.id,
                "title": notif.title,
                "message": notif.message,
                "notification_type": notif.notification_type,
                "read": notif.read,
                "created_at": notif.created_at.isoformat() if notif.created_at else None,
                "user": {
                    "id": user.id if user else None,
                    "full_name": user.full_name if user else None,
                    "farmer_id": user.farmer_id if user else None
                } if user else None
            })
        
        return JSONResponse({
            "success": True,
            "notifications": result
        })
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch notifications: {str(e)}"
        )

@router.post("/notifications/mark-read")
async def mark_notifications_read(
    mark_request: NotificationMarkReadRequest,
    db: Session = Depends(get_db)
):
    """Mark notifications as read - JSON ONLY"""
    try:
        updated = []
        for notif_id in mark_request.notification_ids:
            notification = mark_notification_as_read(db, notif_id)
            if notification:
                updated.append(notif_id)
        
        return JSONResponse({
            "success": True,
            "message": f"Marked {len(updated)} notifications as read",
            "updated_ids": updated
        })
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to mark notifications as read: {str(e)}"
        )

# ==================== REPORTS ====================

@router.get("/reports/generate")
async def generate_report(
    period: str = "30",
    db: Session = Depends(get_db)
):
    """Generate admin reports"""
    try:
        days = int(period)
        start_date = datetime.utcnow() - timedelta(days=days)
        
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
        
        status_distribution = {}
        status_counts = db.query(Application.status, func.count(Application.id))\
            .filter(Application.applied_at >= start_date)\
            .group_by(Application.status)\
            .all()
        
        for status, count in status_counts:
            status_key = status.value if hasattr(status, 'value') else status
            status_distribution[status_key] = count
        
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
        
        return JSONResponse({
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
        })
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate report: {str(e)}"
        )

# ==================== DEBUG ENDPOINTS ====================

@router.get("/debug/applications")
async def debug_applications(db: Session = Depends(get_db)):
    """Debug endpoint to check applications"""
    try:
        applications = db.query(Application).all()
        return JSONResponse({
            "success": True,
            "count": len(applications),
            "applications": [
                {
                    "id": a.id,
                    "application_id": a.application_id,
                    "user_id": a.user_id,
                    "scheme_id": a.scheme_id,
                    "status": a.status.value if hasattr(a.status, 'value') else a.status,
                    "applied_at": a.applied_at.isoformat() if a.applied_at else None
                }
                for a in applications
            ]
        })
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)})

@router.get("/debug/users")
async def debug_users(db: Session = Depends(get_db)):
    """Debug endpoint to check users"""
    try:
        users = db.query(User).all()
        return JSONResponse({
            "success": True,
            "count": len(users),
            "users": [
                {
                    "id": u.id,
                    "farmer_id": u.farmer_id,
                    "full_name": u.full_name,
                    "mobile_number": u.mobile_number,
                    "role": u.role.value if hasattr(u.role, 'value') else u.role
                }
                for u in users
            ]
        })
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)})
