# app/routers/admin_auth.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import timedelta

from app.database import get_db
from app.schemas import AdminLogin, Token, UserResponse
from app.crud import authenticate_admin, get_user_by_id
from app.utils.security import create_access_token
from app.config import settings

router = APIRouter(prefix="/admin", tags=["admin-auth"])

# Admin credentials (in production, store in database)
ADMIN_CREDENTIALS = {
    "username": "admin",
    "password": "admin123",
    "name": "System Administrator",
    "role": "admin"
}

@router.post("/login", response_model=Token)
async def admin_login(login_data: AdminLogin, db: Session = Depends(get_db)):
    """Admin login endpoint"""
    # Check admin credentials
    if (login_data.username != ADMIN_CREDENTIALS["username"] or 
        login_data.password != ADMIN_CREDENTIALS["password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid admin credentials"
        )
    
    # Create admin user object
    admin_user = {
        "id": 0,  # Special ID for admin
        "username": ADMIN_CREDENTIALS["username"],
        "full_name": ADMIN_CREDENTIALS["name"],
        "role": ADMIN_CREDENTIALS["role"],
        "is_admin": True
    }
    
    # Create access token
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={
            "sub": "admin",  # Special subject for admin
            "role": "admin",
            "is_admin": True
        },
        expires_delta=access_token_expires
    )
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": admin_user
    }

@router.get("/verify")
async def verify_admin_token(current_user: dict = Depends(get_current_user)):
    """Verify admin token"""
    if not current_user.get("is_admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    return {"valid": True, "user": current_user}
