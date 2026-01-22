from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional

# ✅ Use relative imports
from database import get_db
from schemas import SchemeCreate, SchemeResponse, AdminStats, UserResponse
from crud import (
    create_scheme, get_all_schemes,
    get_admin_stats, get_user_by_id, get_user_applications, update_application_status
)
from .farmers import get_current_user  # ✅ Note: single dot for same directory

router = APIRouter(prefix="/admin", tags=["admin"])

def verify_admin(current_user = Depends(get_current_user)):
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized"
        )
    return current_user

@router.get("/stats", response_model=AdminStats)
async def get_stats(
    admin_user = Depends(verify_admin),
    db: Session = Depends(get_db)
):
    return get_admin_stats(db)

@router.post("/schemes", response_model=SchemeResponse)
async def add_scheme(
    scheme: SchemeCreate,
    admin_user = Depends(verify_admin),
    db: Session = Depends(get_db)
):
    return create_scheme(db=db, scheme=scheme, created_by=admin_user.full_name)

@router.get("/users")
async def get_all_users(
    skip: int = 0,
    limit: int = 100,
    admin_user = Depends(verify_admin),
    db: Session = Depends(get_db)
):
    from ..crud import get_all_farmers
    return get_all_farmers(db, skip, limit)

@router.get("/users/{user_id}/applications")
async def get_user_applications_admin(
    user_id: int,
    admin_user = Depends(verify_admin),
    db: Session = Depends(get_db)
):
    applications = get_user_applications(db, user_id)
    result = []
    for app in applications:
        app_dict = app.__dict__
        from ..crud import get_scheme_by_id
        scheme = get_scheme_by_id(db, app.scheme_id)
        if scheme:
            from ..schemas import SchemeResponse
            app_dict["scheme"] = SchemeResponse.from_orm(scheme)
        
        user = get_user_by_id(db, app.user_id)
        if user:
            app_dict["user"] = UserResponse.from_orm(user)
        
        result.append(app_dict)
    
    return result

@router.put("/applications/{application_id}/status")
async def update_application_status_admin(
    application_id: int,
    status: str,
    approved_amount: Optional[float] = None,
    admin_user = Depends(verify_admin),
    db: Session = Depends(get_db)
):
    application = update_application_status(db, application_id, status, approved_amount)
    if not application:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Application not found"
        )
    
    return {
        "success": True,
        "message": f"Application status updated to {status}",
        "application": application
    }