# app/utils/auth_utils.py - COMPLETE FIXED VERSION
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from typing import Optional

from app.database import get_db
from app.crud import get_user_by_id
from app.utils.security import verify_token
from app.config import settings

# ✅ Token URL must match your login endpoint
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)

async def get_current_user(
    token: Optional[str] = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
):
    """Get current authenticated user from token"""
    if not token:
        print("❌ No token provided")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    print(f"🔐 Verifying token: {token[:20]}..." if token else "🔐 No token")
    
    # Verify the token
    payload = verify_token(token)
    
    if payload is None:
        print("❌ Invalid or expired token")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    user_id = payload.get("sub")
    if not user_id:
        print("❌ No user ID in token payload")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    try:
        # ✅ FIX: Convert user_id to int properly
        user_id_int = int(user_id)
        user = get_user_by_id(db, user_id_int)
        
        if not user:
            print(f"❌ User not found with ID: {user_id_int}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        print(f"✅ User authenticated: {user.full_name} (ID: {user.id}, Farmer ID: {user.farmer_id})")
        return user
        
    except ValueError:
        print(f"❌ Invalid user ID format: {user_id}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid user ID format",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except Exception as e:
        print(f"❌ Error getting user: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving user: {str(e)}"
        )

async def get_current_active_user(
    current_user = Depends(get_current_user),
):
    """Get current active user"""
    # Check if user is active
    if hasattr(current_user, 'is_active') and not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user"
        )
    return current_user
