# app/utils/security.py - FIXED VERSION
from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from app.config import settings
from fastapi import HTTPException, status
def get_current_user(token: Optional[dict] = Depends(verify_token), db: Session = Depends(get_db)):
    # Add debug logging
    print(f"DEBUG: verify_token returned: {token}")
    print(f"DEBUG: Type of token: {type(token)}")
    
    if token is None:  # ✅ Explicitly check for None
        print("DEBUG: Token is None - verification failed")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token"
        )
    
    user_id = token.get("sub")
    if not user_id:
        print(f"DEBUG: No 'sub' in token payload: {token}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload"
        )
    
    print(f"DEBUG: Looking for user ID: {user_id}")
    user = get_user_by_id(db, int(user_id))
    
    if not user:
        print(f"DEBUG: User ID {user_id} not found in database")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    print(f"DEBUG: User found: {user.full_name}")
    return user
pwd_context = CryptContext(schemes=["sha256_crypt"], deprecated="auto")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    # Truncate password if too long (just in case)
    if len(password) > 72:
        password = password[:72]
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt

def verify_token(token: str) -> Optional[dict]:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload
    except JWTError:
        return None
