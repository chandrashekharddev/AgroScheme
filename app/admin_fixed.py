# app/routers/admin_fixed.py
from fastapi import APIRouter, HTTPException, status
from datetime import timedelta, datetime
from pydantic import BaseModel
from app.utils.security import create_access_token
from app.config import settings

router = APIRouter(prefix="/api/admin", tags=["admin"])

class AdminLogin(BaseModel):
    username: str
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str
    user: dict

ADMIN_CREDENTIALS = {
    "username": "admin",
    "password": "admin123",
    "name": "System Administrator",
    "role": "admin"
}

@router.post("/login", response_model=TokenResponse)
async def admin_login(login_data: AdminLogin):
    """Simple admin login endpoint"""
    if (login_data.username != ADMIN_CREDENTIALS["username"] or 
        login_data.password != ADMIN_CREDENTIALS["password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid admin credentials"
        )
    
    admin_user = {
        "id": 0,
        "username": ADMIN_CREDENTIALS["username"],
        "full_name": ADMIN_CREDENTIALS["name"],
        "role": ADMIN_CREDENTIALS["role"],
        "is_admin": True
    }
    
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={
            "sub": "admin",
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

@router.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}

@router.get("/")
async def admin_root():
    return {
        "message": "Admin API",
        "endpoints": {
            "POST /api/admin/login": "Admin login",
            "GET /api/admin/health": "Health check"
        }
    }
