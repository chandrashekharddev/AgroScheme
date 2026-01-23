# app/routers/schemes.py - CREATE THIS FILE
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from app.database import get_db
from app.schemas import SchemeResponse, EligibilityCheck, ApplicationResponse
from app.crud import (
    get_all_schemes, get_scheme_by_id, check_user_eligibility, create_application
)
from app.routers.farmers import get_current_user

router = APIRouter(prefix="/schemes", tags=["schemes"])

# ✅ GET /schemes endpoint - THIS FIXES THE 405 ERROR
@router.get("/", response_model=List[SchemeResponse])
async def get_schemes(
    active_only: bool = True,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """Get all government schemes"""
    return get_all_schemes(db, skip, limit, active_only)

# ✅ GET /schemes/{scheme_id} endpoint
@router.get("/{scheme_id}", response_model=SchemeResponse)
async def get_scheme(scheme_id: int, db: Session = Depends(get_db)):
    """Get a specific scheme by ID"""
    scheme = get_scheme_by_id(db, scheme_id)
    if not scheme:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Scheme not found"
        )
    return scheme

# ✅ GET /schemes/{scheme_id}/check-eligibility endpoint
@router.get("/{scheme_id}/check-eligibility", response_model=EligibilityCheck)
async def check_scheme_eligibility(
    scheme_id: int,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Check if user is eligible for a scheme"""
    return check_user_eligibility(db, current_user.id, scheme_id)

# ✅ POST /schemes/{scheme_id}/apply endpoint
@router.post("/{scheme_id}/apply", response_model=ApplicationResponse)
async def apply_for_scheme(
    scheme_id: int,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Apply for a scheme"""
    eligibility = check_user_eligibility(db, current_user.id, scheme_id)
    if not eligibility.get("eligible", False):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Not eligible for this scheme."
        )
    
    missing_docs = eligibility.get("missing_documents", [])
    if missing_docs:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Missing required documents: {', '.join(missing_docs)}"
        )
    
    application = create_application(
        db=db,
        user_id=current_user.id,
        scheme_id=scheme_id,
        application_data={
            "eligibility_check": eligibility,
            "auto_applied": True
        }
    )
    
    return application
