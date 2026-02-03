# app/dependencies.py
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.database import get_db
from app.crud import get_user_by_id
from app.utils.security import verify_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")

def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
):
    """Get current authenticated user"""
    payload = verify_token(token)
    
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token"
        )
        
    if payload.get("is_admin"):
        return {
            "id": 0,
            "is_admin": True,
            "role": "admin",
            "full_name": "System Administrator",
            "username": "admin"
        }
        
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload"
        )
    
    user = get_user_by_id(db, int(user_id))
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    user_dict = {
        "id": user.id,
        "farmer_id": user.farmer_id,
        "full_name": user.full_name,
        "mobile_number": user.mobile_number,
        "email": user.email,
        "state": user.state,
        "district": user.district,
        "village": user.village,
        "role": user.role,
        "is_admin": False
    }
    
    return user_dict
   

def verify_admin(current_user = Depends(get_current_user)):
    """Verify if current user has admin role"""
    if not current_user.get("is_admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized. Admin privileges required."
        )
    return current_user
