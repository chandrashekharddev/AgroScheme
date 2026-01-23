# app/routers/auth.py - CORRECTED VERSION
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import timedelta

# ✅ CORRECT IMPORTS - ADD "app." prefix
from app.database import get_db
from ..schemas import UserCreate, UserResponse, Token, UserLogin
from app.crud import create_user, authenticate_user, get_user_by_mobile, get_user_by_email
from app.utils.security import create_access_token
from app.config import settings

router = APIRouter(prefix="/auth", tags=["authentication"])

@router.post("/register", response_model=UserResponse)
async def register(user: UserCreate, db: Session = Depends(get_db)):
    # Check if user already exists
    db_user = get_user_by_mobile(db, mobile_number=user.mobile_number)
    if db_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Mobile number already registered"
        )
    
    # Check email if provided
    if user.email:
        db_user_email = get_user_by_email(db, email=user.email)
        if db_user_email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )
    
    # Create user
    return create_user(db=db, user=user)

@router.post("/login", response_model=Token)
async def login(form_data: UserLogin, db: Session = Depends(get_db)):
    user = authenticate_user(db, form_data.mobile_number, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect mobile number or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Create access token
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": str(user.id), "role": user.role},
        expires_delta=access_token_expires
    )
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": user
    }

@router.post("/login-with-otp", response_model=Token)
async def login_with_otp(mobile_number: str, db: Session = Depends(get_db)):
    user = get_user_by_mobile(db, mobile_number)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Create access token
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": str(user.id), "role": user.role},
        expires_delta=access_token_expires
    )
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": user
    }

@router.post("/send-otp")
async def send_otp(mobile_number: str):
    return {
        "success": True,
        "message": "OTP sent successfully (demo: 123456)",
        "otp": "123456"
    }
