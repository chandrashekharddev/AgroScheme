# app/routers/auth.py - UPDATED WITH CORS FIX
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from datetime import timedelta
from typing import Optional

from app.database import get_db
from app.schemas import UserCreate, UserResponse, Token, UserLogin
from app.crud import create_user, authenticate_user, get_user_by_mobile
from app.utils.security import create_access_token
from app.config import settings
from app.supabase_client import get_supabase_client

router = APIRouter(prefix="/auth", tags=["authentication"])

@router.post("/login")
async def login(request: Request, form_data: UserLogin, db: Session = Depends(get_db)):
    try:
        origin = request.headers.get("origin", "")
        print(f"🔐 Login attempt from: {origin}")
        print(f"📱 Mobile: {form_data.mobile_number}")
        
        # Authenticate user
        user = authenticate_user(db, form_data.mobile_number, form_data.password)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect mobile number or password",
            )
        
        # Create access token
        access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={
                "sub": str(user.id),
                "mobile": user.mobile_number,
                "role": user.role.value if hasattr(user.role, 'value') else user.role
            },
            expires_delta=access_token_expires
        )
        
        # Create response
        response = JSONResponse({
            "success": True,
            "access_token": access_token,
            "token_type": "bearer",
            "user": {
                "id": user.id,
                "farmer_id": user.farmer_id,
                "full_name": user.full_name,
                "mobile_number": user.mobile_number,
                "email": user.email,
                "role": user.role.value if hasattr(user.role, 'value') else user.role,
                "state": user.state,
                "district": user.district,
                "village": user.village
            }
        })
        
        # ✅ CRITICAL: Set CORS headers for Vercel
        if "vercel.app" in origin:
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Allow-Credentials"] = "true"
        elif origin in settings.ALLOWED_ORIGINS:
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Allow-Credentials"] = "true"
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Login error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Login failed: {str(e)}")
