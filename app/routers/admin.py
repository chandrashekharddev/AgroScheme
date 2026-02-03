# app/routers/admin.py - FIXED VERSION
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional

from app.database import get_db
from app.schemas import SchemeCreate, SchemeResponse, AdminStats, UserResponse, ApplicationResponse
from app.crud import (
    create_scheme, get_all_schemes, get_all_farmers,
    get_admin_stats, get_user_by_id, get_user_applications, update_application_status,
    get_scheme_by_id
)
from app.dependencies import get_current_user

router = APIRouter(prefix="/admin", tags=["admin"])

def verify_admin(current_user = Depends(get_current_user)):
    """Verify if current user has admin role"""
    if not hasattr(current_user, 'role') or current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized. Admin privileges required."
        )
    return current_user

@router.get("/stats", response_model=AdminStats)
async def get_stats(
    admin_user = Depends(verify_admin),
    db: Session = Depends(get_db)
):
    """Get admin dashboard statistics"""
    try:
        return get_admin_stats(db)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch stats: {str(e)}"
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
        existing_scheme = get_scheme_by_id(db, scheme.scheme_code)
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
    admin_user = Depends(verify_admin),
    db: Session = Depends(get_db)
):
    """Get all registered farmers/users"""
    try:
        farmers = get_all_farmers(db, skip, limit)
        return farmers
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch users: {str(e)}"
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
        
        return {
            "user": UserResponse.from_orm(user),
            "applications": applications,
            "total_applications": len(applications)
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch user details: {str(e)}"
        )

@router.get("/users/{user_id}/applications")
async def get_user_applications_admin(
    user_id: int,
    admin_user = Depends(verify_admin),
    db: Session = Depends(get_db)
):
    """Get all applications for a specific user"""
    try:
        # Check if user exists
        user = get_user_by_id(db, user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        applications = get_user_applications(db, user_id)
        result = []
        
        for app in applications:
            app_data = {
                "id": app.id,
                "application_id": app.application_id,
                "status": app.status,
                "applied_amount": app.applied_amount,
                "approved_amount": app.approved_amount,
                "applied_at": app.applied_at,
                "updated_at": app.updated_at
            }
            
            # Get scheme details
            scheme = get_scheme_by_id(db, app.scheme_id)
            if scheme:
                app_data["scheme"] = {
                    "id": scheme.id,
                    "scheme_name": scheme.scheme_name,
                    "scheme_code": scheme.scheme_code,
                    "scheme_type": scheme.scheme_type,
                    "benefit_amount": scheme.benefit_amount
                }
            
            result.append(app_data)
        
        return {
            "user_id": user_id,
            "user_name": user.full_name,
            "farmer_id": user.farmer_id,
            "applications": result,
            "total_applications": len(applications)
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch user applications: {str(e)}"
        )

@router.put("/applications/{application_id}/status")
async def update_application_status_admin(
    application_id: int,
    status: str,
    approved_amount: Optional[float] = None,
    admin_user = Depends(verify_admin),
    db: Session = Depends(get_db)
):
    """Update application status (admin only)"""
    try:
        # Validate status
        valid_statuses = ["pending", "under_review", "approved", "rejected", "docs_needed"]
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
        
        return {
            "success": True,
            "message": f"Application status updated to {status}",
            "application_id": application_id,
            "new_status": status,
            "approved_amount": approved_amount
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update application status: {str(e)}"
        )

@router.get("/applications")
async def get_all_applications(
    skip: int = 0,
    limit: int = 100,
    status: Optional[str] = None,
    admin_user = Depends(verify_admin),
    db: Session = Depends(get_db)
):
    """Get all applications with filtering options"""
    try:
        # Note: You need to implement get_all_applications in crud.py
        # For now, we'll get all users and their applications
        from app.models import Application
        from sqlalchemy import or_
        
        query = db.query(Application)
        
        # Apply status filter if provided
        if status:
            valid_statuses = ["pending", "under_review", "approved", "rejected", "docs_needed"]
            if status not in valid_statuses:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid status. Must be one of: {', '.join(valid_statuses)}"
                )
            query = query.filter(Application.status == status)
        
        # Apply pagination
        total = query.count()
        applications = query.offset(skip).limit(limit).all()
        
        result = []
        for app in applications:
            app_data = {
                "id": app.id,
                "application_id": app.application_id,
                "user_id": app.user_id,
                "scheme_id": app.scheme_id,
                "status": app.status,
                "applied_amount": app.applied_amount,
                "approved_amount": app.approved_amount,
                "applied_at": app.applied_at,
                "updated_at": app.updated_at
            }
            
            # Get user details
            user = get_user_by_id(db, app.user_id)
            if user:
                app_data["user"] = {
                    "id": user.id,
                    "full_name": user.full_name,
                    "farmer_id": user.farmer_id,
                    "mobile_number": user.mobile_number,
                    "district": user.district,
                    "state": user.state
                }
            
            # Get scheme details
            scheme = get_scheme_by_id(db, app.scheme_id)
            if scheme:
                app_data["scheme"] = {
                    "id": scheme.id,
                    "scheme_name": scheme.scheme_name,
                    "scheme_code": scheme.scheme_code,
                    "scheme_type": scheme.scheme_type,
                    "benefit_amount": scheme.benefit_amount
                }
            
            result.append(app_data)
        
        return {
            "total": total,
            "skip": skip,
            "limit": limit,
            "status_filter": status,
            "applications": result
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch applications: {str(e)}"
        )

@router.get("/schemes", response_model=List[SchemeResponse])
async def get_all_schemes_admin(
    active_only: bool = True,
    skip: int = 0,
    limit: int = 100,
    admin_user = Depends(verify_admin),
    db: Session = Depends(get_db)
):
    """Get all schemes (admin version - shows all including inactive)"""
    try:
        schemes = get_all_schemes(db, skip, limit, active_only=False)  # Admin sees all
        return schemes
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch schemes: {str(e)}"
        )
