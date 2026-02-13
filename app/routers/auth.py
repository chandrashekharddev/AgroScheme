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
from app.models import User

router = APIRouter(prefix="/auth", tags=["authentication"])

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
        
        # ✅ Ensure farmer_id exists
        if not user.farmer_id:
            # Generate farmer ID if not exists
            import uuid
            user.farmer_id = f"AGRO{str(uuid.uuid4().int)[:8]}"
            db.commit()
            db.refresh(user)
        
        print(f"✅ User authenticated: {user.full_name} (ID: {user.id}, Farmer ID: {user.farmer_id})")
        
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
        
        # Prepare user data with ALL fields
        user_data = {
            "id": user.id,
            "farmer_id": user.farmer_id,
            "full_name": user.full_name,
            "mobile_number": user.mobile_number,
            "email": user.email,
            "aadhaar_number": user.aadhaar_number,  # ✅ NEW
            "role": user.role.value if hasattr(user.role, 'value') else user.role,
            "state": getattr(user, 'state', None),
            "district": getattr(user, 'district', None),
            "village": getattr(user, 'village', None),
            
            # Farm details
            "total_land_acres": getattr(user, 'total_land_acres', None),
            "land_type": getattr(user, 'land_type', None),
            "main_crops": getattr(user, 'main_crops', None),
            "annual_income": getattr(user, 'annual_income', None),
            
            # Bank details
            "bank_account_number": getattr(user, 'bank_account_number', None),
            "bank_name": getattr(user, 'bank_name', None),
            "ifsc_code": getattr(user, 'ifsc_code', None),
            "bank_verified": getattr(user, 'bank_verified', False),
            
            # Preferences
            "language": getattr(user, 'language', 'en'),
            "auto_apply_enabled": getattr(user, 'auto_apply_enabled', True),
            "email_notifications": getattr(user, 'email_notifications', True),
            "sms_notifications": getattr(user, 'sms_notifications', True),
            "created_at": user.created_at.isoformat() if user.created_at else None
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
        
        print(f"✅ Login successful for: {user.full_name} (Farmer ID: {user.farmer_id})")
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

@router.post("/register")
async def register(
    request: Request,
    user: UserCreate,  # Now includes all fields!
    db: Session = Depends(get_db)
):
    """
    Register a new farmer with complete profile
    """
    try:
        origin = request.headers.get("origin", "")
        print("="*50)
        print(f"📝 REGISTRATION ATTEMPT")
        print(f"   Origin: {origin}")
        print(f"   Mobile: {user.mobile_number}")
        print(f"   Name: {user.full_name}")
        print(f"   Aadhaar: {user.aadhaar_number}")
        print(f"   State: {user.state}")
        print(f"   District: {user.district}")
        print(f"   Village: {user.village}")
        print(f"   Language: {user.language}")
        print(f"   Land Size: {user.total_land_acres} acres")
        print(f"   Land Type: {user.land_type}")
        print(f"   Crops: {user.main_crops}")
        print(f"   Annual Income: {user.annual_income}")
        print(f"   Bank Account: {user.bank_account_number}")
        print(f"   Bank Name: {user.bank_name}")
        print(f"   IFSC: {user.ifsc_code}")
        print("="*50)
        
        # Check if user already exists
        db_user = get_user_by_mobile(db, mobile_number=user.mobile_number)
        if db_user:
            print(f"❌ Mobile number already registered: {user.mobile_number}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Mobile number already registered"
            )
        
        # Check email if provided
        if user.email:
            db_user_email = get_user_by_email(db, email=user.email)
            if db_user_email:
                print(f"❌ Email already registered: {user.email}")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Email already registered"
                )
        
        # Create user in database with ALL fields
        new_user = create_user(db=db, user=user)
        print(f"✅ User registered successfully!")
        print(f"   ID: {new_user.id}")
        print(f"   Farmer ID: {new_user.farmer_id}")
        print(f"   Saved fields: Aadhaar={new_user.aadhaar_number}, Land={new_user.total_land_acres}, Bank={new_user.bank_account_number}")
        
        response = JSONResponse({
            "success": True,
            "message": "Registration successful",
            "farmer_id": new_user.farmer_id,
            "user": {
                "id": new_user.id,
                "full_name": new_user.full_name,
                "farmer_id": new_user.farmer_id,
                "mobile_number": new_user.mobile_number
            }
        })
        
        # Set CORS headers
        if origin:
            if "vercel.app" in origin or origin in settings.ALLOWED_ORIGINS:
                response.headers["Access-Control-Allow-Origin"] = origin
                response.headers["Access-Control-Allow-Credentials"] = "true"
        
        return response
        
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
        if origin:
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
    origin = request.headers.get("origin", "")
    print(f"📱 OTP requested for: {mobile_number}")
    
    response = JSONResponse({
        "success": True,
        "message": "OTP sent successfully",
        "otp": "123456",  # Demo OTP
        "mobile": mobile_number
    })
    
    # Set CORS headers
    if origin:
        if "vercel.app" in origin or origin in settings.ALLOWED_ORIGINS:
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Allow-Credentials"] = "true"
    
    return response
