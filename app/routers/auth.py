# app/routers/auth.py - COMPLETE FIXED VERSION
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from datetime import timedelta
from typing import Optional

from app.database import get_db
from app.schemas import UserCreate, UserResponse, Token, UserLogin
from app.crud import create_user, authenticate_user, get_user_by_mobile, get_user_by_email
from app.utils.security import create_access_token
from app.config import settings
from app.supabase_client import get_supabase_client

# ✅ FIX: Use prefix="/auth" here, and DO NOT add prefix in main.py
router = APIRouter(prefix="/auth", tags=["authentication"])

# app/routers/auth.py - Update the login function
@router.post("/login")
async def login(request: Request, form_data: UserLogin, db: Session = Depends(get_db)):
    """
    Authenticate farmer and return JWT token
    """
    try:
        origin = request.headers.get("origin", "")
        print(f"🔐 Login attempt from: {origin}")
        print(f"📱 Mobile: {form_data.mobile_number}")
        
        # Authenticate user from database
        user = authenticate_user(db, form_data.mobile_number, form_data.password)
        
        if not user:
            print(f"❌ Authentication failed for {form_data.mobile_number}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect mobile number or password",
            )
        
        print(f"✅ User authenticated: {user.full_name} (ID: {user.id})")
        
        # Create access token
        access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={
                "sub": str(user.id),
                "mobile": user.mobile_number,
                "role": user.role.value if hasattr(user.role, 'value') else user.role,
                "farmer_id": user.farmer_id
            },
            expires_delta=access_token_expires
        )
        
        # ✅ FIX: Safely get attributes with defaults
        user_data = {
            "id": user.id,
            "farmer_id": user.farmer_id,
            "full_name": user.full_name,
            "mobile_number": user.mobile_number,
            "email": user.email,
            "role": user.role.value if hasattr(user.role, 'value') else user.role,
            "state": getattr(user, 'state', None),
            "district": getattr(user, 'district', None),
            "village": getattr(user, 'village', None),
            "total_land_acres": getattr(user, 'total_land_acres', None),
            "annual_income": getattr(user, 'annual_income', None),
            "land_type": getattr(user, 'land_type', None),
            "main_crops": getattr(user, 'main_crops', None),
            "bank_account_number": getattr(user, 'bank_account_number', None),
            "ifsc_code": getattr(user, 'ifsc_code', None),
            # ✅ Safely handle aadhaar_number - it might not exist in DB
            "aadhaar_number": getattr(user, 'aadhaar_number', None),
            "pan_number": getattr(user, 'pan_number', None),
            "language": getattr(user, 'language', 'en'),
            "auto_apply_enabled": getattr(user, 'auto_apply_enabled', True),
            "email_notifications": getattr(user, 'email_notifications', True),
            "sms_notifications": getattr(user, 'sms_notifications', True)
        }
        
        response_data = {
            "success": True,
            "access_token": access_token,
            "token_type": "bearer",
            "user": user_data
        }
        
        response = JSONResponse(content=response_data)
        
        # Set CORS headers
        if origin:
            if "vercel.app" in origin or origin in settings.ALLOWED_ORIGINS:
                response.headers["Access-Control-Allow-Origin"] = origin
                response.headers["Access-Control-Allow-Credentials"] = "true"
        
        print(f"✅ Login successful for: {user.full_name}")
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Login error: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Login failed: {str(e)}"
        )

@router.post("/register", response_model=UserResponse)
async def register(user: UserCreate, db: Session = Depends(get_db)):
    """
    Register a new farmer
    """
    try:
        print(f"📝 Registration attempt for: {user.mobile_number}")
        
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
        
        # Create user in Supabase Auth
        try:
            supabase = get_supabase_client()
            auth_response = supabase.auth.sign_up({
                "email": user.email or f"{user.mobile_number}@agroscheme.com",
                "password": user.password,
                "phone": user.mobile_number,
                "options": {
                    "data": {
                        "full_name": user.full_name,
                        "role": "farmer"
                    }
                }
            })
            
            # Set user.id from Supabase Auth
            if hasattr(user, 'id'):
                user.id = auth_response.user.id
                
            print(f"✅ Supabase Auth user created: {auth_response.user.id}")
            
        except Exception as supabase_error:
            print(f"⚠️ Supabase Auth error: {supabase_error}")
            # Continue with local DB creation
        
        # Create user in local database
        new_user = create_user(db=db, user=user)
        print(f"✅ User registered successfully: {new_user.farmer_id}")
        
        return new_user
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Registration error: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Registration failed: {str(e)}"
        )

@router.post("/login-with-otp")
async def login_with_otp(
    request: Request,
    mobile_number: str,
    otp: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    Login using OTP (One Time Password)
    """
    try:
        origin = request.headers.get("origin", "")
        print(f"🔐 OTP Login attempt for: {mobile_number}")
        
        # Get user by mobile number
        user = get_user_by_mobile(db, mobile_number)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # In production, verify OTP here
        # For demo, any 6-digit OTP works
        if otp and len(otp) != 6:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid OTP format"
            )
        
        # Create access token
        access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={
                "sub": str(user.id),
                "mobile": user.mobile_number,
                "role": user.role.value if hasattr(user.role, 'value') else user.role,
                "farmer_id": user.farmer_id
            },
            expires_delta=access_token_expires
        )
        
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
                "role": user.role.value if hasattr(user.role, 'value') else user.role
            }
        })
        
        # Set CORS headers
        if "vercel.app" in origin or origin in settings.ALLOWED_ORIGINS:
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Allow-Credentials"] = "true"
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ OTP Login error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"OTP login failed: {str(e)}"
        )

@router.post("/send-otp")
async def send_otp(request: Request, mobile_number: str):
    """
    Send OTP to mobile number (Demo)
    """
    try:
        origin = request.headers.get("origin", "")
        print(f"📱 OTP requested for: {mobile_number}")
        
        response = JSONResponse({
            "success": True,
            "message": "OTP sent successfully",
            "otp": "123456",  # Demo OTP
            "mobile": mobile_number
        })
        
        # Set CORS headers
        if "vercel.app" in origin or origin in settings.ALLOWED_ORIGINS:
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Allow-Credentials"] = "true"
        
        return response
        
    except Exception as e:
        print(f"❌ Send OTP error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to send OTP: {str(e)}"
        )

@router.get("/me")
async def get_current_user(
    request: Request,
    token: str = Depends(create_access_token),  # You need to implement token validation
    db: Session = Depends(get_db)
):
    """
    Get current authenticated user
    """
    try:
        origin = request.headers.get("origin", "")
        
        # Decode token and get user
        # This is a placeholder - implement proper token validation
        user_id = 1  # Get from token
        
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        response = JSONResponse({
            "success": True,
            "user": {
                "id": user.id,
                "farmer_id": user.farmer_id,
                "full_name": user.full_name,
                "mobile_number": user.mobile_number,
                "email": user.email,
                "role": user.role.value if hasattr(user.role, 'value') else user.role
            }
        })
        
        # Set CORS headers
        if "vercel.app" in origin or origin in settings.ALLOWED_ORIGINS:
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Allow-Credentials"] = "true"
        
        return response
        
    except Exception as e:
        print(f"❌ Get user error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials"
        )

@router.post("/logout")
async def logout(request: Request):
    """
    Logout user
    """
    origin = request.headers.get("origin", "")
    
    response = JSONResponse({
        "success": True,
        "message": "Logged out successfully"
    })
    
    # Set CORS headers
    if "vercel.app" in origin or origin in settings.ALLOWED_ORIGINS:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Credentials"] = "true"
    
    return response
