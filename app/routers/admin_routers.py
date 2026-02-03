# app/routers/admin_routers.py
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional

from app.database import get_db
from app.dependencies import verify_admin
from app.schemas import (
    AdminStatsResponse, FarmerDetail, DocumentResponse, 
    SchemeCreate, SchemeResponse, ApplicationResponse,
    DocumentVerificationRequest
)
from app.crud import (
    get_all_farmers_with_stats, get_all_documents_for_verification,
    get_detailed_stats, verify_document_admin, create_scheme,
    get_all_schemes, get_all_applications, update_application_status,
    get_user_by_id, get_user_applications
)

router = APIRouter(prefix="/admin", tags=["admin"])

@router.get("/stats", response_model=AdminStatsResponse)
async def get_admin_stats(
    admin_user = Depends(verify_admin),
    db: Session = Depends(get_db)
):
    """Get admin dashboard statistics"""
    try:
        stats = get_detailed_stats(db)
        return stats
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch stats: {str(e)}"
        )

@router.get("/farmers", response_model=List[FarmerDetail])
async def get_all_farmers_admin(
    skip: int = 0,
    limit: int = 100,
    search: Optional[str] = None,
    admin_user = Depends(verify_admin),
    db: Session = Depends(get_db)
):
    """Get all farmers with detailed information"""
    try:
        farmers = get_all_farmers_with_stats(db, skip, limit)
        
        # Apply search filter if provided
        if search:
            search_lower = search.lower()
            farmers = [
                farmer for farmer in farmers
                if (search_lower in farmer["full_name"].lower() or
                    search_lower in farmer["farmer_id"].lower() or
                    search_lower in farmer["mobile_number"] or
                    (farmer["email"] and search_lower in farmer["email"].lower()))
            ]
        
        return farmers
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch farmers: {str(e)}"
        )

@router.get("/farmers/{farmer_id}")
async def get_farmer_details(
    farmer_id: int,
    admin_user = Depends(verify_admin),
    db: Session = Depends(get_db)
):
    """Get detailed information about a specific farmer"""
    try:
        farmer = get_user_by_id(db, farmer_id)
        if not farmer:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Farmer not found"
            )
        
        # Get farmer's applications
        applications = get_user_applications(db, farmer_id)
        
        # Get farmer's documents
        from app.crud import get_user_documents
        documents = get_user_documents(db, farmer_id)
        
        return {
            "id": farmer.id,
            "farmer_id": farmer.farmer_id,
            "full_name": farmer.full_name,
            "mobile_number": farmer.mobile_number,
            "email": farmer.email,
            "state": farmer.state,
            "district": farmer.district,
            "village": farmer.village,
            "language": farmer.language,
            "total_land_acres": farmer.total_land_acres,
            "land_type": farmer.land_type,
            "main_crops": farmer.main_crops,
            "annual_income": farmer.annual_income,
            "bank_account_number": farmer.bank_account_number,
            "bank_name": farmer.bank_name,
            "ifsc_code": farmer.ifsc_code,
            "bank_verified": farmer.bank_verified,
            "auto_apply_enabled": farmer.auto_apply_enabled,
            "created_at": farmer.created_at,
            "applications": [
                {
                    "id": app.id,
                    "application_id": app.application_id,
                    "scheme_name": app.scheme.scheme_name if app.scheme else "Unknown",
                    "status": app.status,
                    "applied_amount": app.applied_amount,
                    "approved_amount": app.approved_amount,
                    "applied_at": app.applied_at
                }
                for app in applications
            ],
            "documents": [
                {
                    "id": doc.id,
                    "document_type": doc.document_type,
                    "file_name": doc.file_name,
                    "verified": doc.verified,
                    "uploaded_at": doc.uploaded_at
                }
                for doc in documents
            ],
            "total_applications": len(applications),
            "total_documents": len(documents)
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch farmer details: {str(e)}"
        )

@router.get("/documents/pending", response_model=List[DocumentResponse])
async def get_pending_documents(
    skip: int = 0,
    limit: int = 50,
    admin_user = Depends(verify_admin),
    db: Session = Depends(get_db)
):
    """Get all documents pending verification"""
    try:
        documents = get_all_documents_for_verification(db, skip, limit)
        
        # Add file URLs
        from app.config import settings
        for doc in documents:
            if doc.file_path:
                doc.file_url = settings.get_file_url(doc.file_path)
        
        return documents
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch pending documents: {str(e)}"
        )

@router.post("/documents/verify")
async def verify_document(
    verification: DocumentVerificationRequest,
    admin_user = Depends(verify_admin),
    db: Session = Depends(get_db)
):
    """Verify or reject a document"""
    try:
        document = verify_document_admin(
            db, 
            verification.document_id, 
            verification.verified,
            verification.remarks
        )
        
        if not document:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document not found"
            )
        
        return {
            "success": True,
            "message": f"Document {'verified' if verification.verified else 'rejected'} successfully",
            "document_id": document.id,
            "verified": document.verified
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to verify document: {str(e)}"
        )

@router.post("/schemes", response_model=SchemeResponse)
async def add_scheme(
    scheme: SchemeCreate,
    admin_user = Depends(verify_admin),
    db: Session = Depends(get_db)
):
    """Add a new government scheme"""
    try:
        # Check if scheme code already exists
        from app.crud import get_scheme_by_code
        existing_scheme = get_scheme_by_code(db, scheme.scheme_code)
        if existing_scheme:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Scheme with code '{scheme.scheme_code}' already exists"
            )
        
        return create_scheme(db=db, scheme=scheme, created_by=admin_user.get("full_name", "Admin"))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to add scheme: {str(e)}"
        )

@router.get("/applications", response_model=List[ApplicationResponse])
async def get_all_applications_admin(
    status: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    admin_user = Depends(verify_admin),
    db: Session = Depends(get_db)
):
    """Get all applications with optional status filter"""
    try:
        applications = get_all_applications(db, skip, limit, status)
        return applications
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch applications: {str(e)}"
        )

@router.put("/applications/{application_id}/status")
async def update_application_status_admin(
    application_id: int,
    status: str,
    approved_amount: Optional[float] = None,
    admin_user = Depends(verify_admin),
    db: Session = Depends(get_db)
):
    """Update application status (admin only)"""
    try:
        # Validate status
        valid_statuses = ["pending", "under_review", "approved", "rejected", "docs_needed"]
        if status not in valid_statuses:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid status. Must be one of: {', '.join(valid_statuses)}"
            )
        
        # Update application status
        application = update_application_status(db, application_id, status, approved_amount)
        if not application:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Application not found"
            )
        
        return {
            "success": True,
            "message": f"Application status updated to {status}",
            "application_id": application_id,
            "new_status": status,
            "approved_amount": approved_amount
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update application status: {str(e)}"
        )

@router.get("/schemes", response_model=List[SchemeResponse])
async def get_all_schemes_admin(
    active_only: bool = False,
    skip: int = 0,
    limit: int = 100,
    admin_user = Depends(verify_admin),
    db: Session = Depends(get_db)
):
    """Get all schemes (admin version - shows all including inactive)"""
    try:
        schemes = get_all_schemes(db, skip, limit, active_only)
        return schemes
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch schemes: {str(e)}"
        )
