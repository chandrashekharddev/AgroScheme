# app/routers/schemes.py - COMPLETE FIXED VERSION
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from typing import List, Optional

from app.database import get_db
from app.schemas import SchemeResponse, EligibilityCheck, ApplicationResponse
from app.crud import (
    get_all_schemes, get_scheme_by_id, check_user_eligibility, create_application,
    get_scheme_by_code
)
from app.utils.auth_utils import get_current_user  # ✅ Use auth_utils

router = APIRouter(prefix="/schemes", tags=["schemes"])

# app/routers/schemes.py - Update the get_schemes function
@router.get("/")
async def get_schemes(
    request: Request,
    active_only: bool = True,
    skip: int = 0,
    limit: int = 100,
    search: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Get all government schemes"""
    origin = request.headers.get("origin", "")
    
    try:
        schemes = get_all_schemes(db, skip, limit, active_only)
        
        # Apply search filter if provided
        if search:
            search = search.lower()
            schemes = [
                scheme for scheme in schemes
                if (search in scheme.scheme_name.lower() or
                    (scheme.scheme_code and search in scheme.scheme_code.lower()) or
                    (scheme.description and search in scheme.description.lower()))
            ]
        
        result = []
        for scheme in schemes:
            # ✅ FIX: Handle scheme_type safely
            scheme_type = "central"  # default
            if scheme.scheme_type:
                if hasattr(scheme.scheme_type, 'value'):
                    scheme_type = scheme.scheme_type.value
                else:
                    scheme_type = str(scheme.scheme_type).lower()
            
            result.append({
                "id": scheme.id,
                "scheme_name": scheme.scheme_name,
                "scheme_code": scheme.scheme_code,
                "description": scheme.description,
                "scheme_type": scheme_type,  # ✅ Always lowercase
                "benefit_amount": scheme.benefit_amount,
                "last_date": scheme.last_date.isoformat() if scheme.last_date else None,
                "is_active": scheme.is_active,
                "eligibility_criteria": scheme.eligibility_criteria,
                "required_documents": scheme.required_documents,
                "department": getattr(scheme, 'department', 'Agriculture'),
                "created_at": scheme.created_at.isoformat() if scheme.created_at else None,
                "updated_at": scheme.updated_at.isoformat() if hasattr(scheme, 'updated_at') and scheme.updated_at else None
            })
        
        response = JSONResponse({
            "success": True,
            "count": len(result),
            "schemes": result
        })
        
        # Set CORS headers
        if origin and "vercel.app" in origin:
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Allow-Credentials"] = "true"
        
        return response
        
    except Exception as e:
        print(f"❌ Error in get_schemes: {str(e)}")
        return JSONResponse({
            "success": False,
            "message": "Failed to fetch schemes",
            "schemes": []
        })

@router.get("/{scheme_id}")
async def get_scheme(
    request: Request,
    scheme_id: int,
    db: Session = Depends(get_db)
):
    """Get scheme by ID"""
    origin = request.headers.get("origin", "")
    
    try:
        scheme = get_scheme_by_id(db, scheme_id)
        if not scheme:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Scheme not found"
            )
        
        response = JSONResponse({
            "success": True,
            "scheme": {
                "id": scheme.id,
                "scheme_name": scheme.scheme_name,
                "scheme_code": scheme.scheme_code,
                "description": scheme.description,
                "scheme_type": scheme.scheme_type.value if hasattr(scheme.scheme_type, 'value') else scheme.scheme_type,
                "benefit_amount": scheme.benefit_amount,
                "last_date": scheme.last_date.isoformat() if scheme.last_date else None,
                "is_active": scheme.is_active,
                "eligibility_criteria": scheme.eligibility_criteria,
                "required_documents": scheme.required_documents,
                "department": getattr(scheme, 'department', 'Agriculture'),
                "created_at": scheme.created_at.isoformat() if scheme.created_at else None,
                "updated_at": scheme.updated_at.isoformat() if hasattr(scheme, 'updated_at') and scheme.updated_at else None
            }
        })
        
        # Set CORS headers
        if origin and "vercel.app" in origin:
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Allow-Credentials"] = "true"
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error in get_scheme: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch scheme"
        )

@router.get("/{scheme_id}/check-eligibility")
async def check_scheme_eligibility(
    request: Request,
    scheme_id: int,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Check if current user is eligible for a scheme"""
    origin = request.headers.get("origin", "")
    
    try:
        eligibility = check_user_eligibility(db, current_user.id, scheme_id)
        
        response = JSONResponse({
            "success": True,
            "eligible": eligibility.get("eligible", False),
            "match_percentage": eligibility.get("match_percentage", 0),
            "missing_documents": eligibility.get("missing_documents", []),
            "criteria_met": eligibility.get("criteria_met", []),
            "criteria_missing": eligibility.get("criteria_missing", [])
        })
        
        # Set CORS headers
        if origin and "vercel.app" in origin:
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Allow-Credentials"] = "true"
        
        return response
        
    except Exception as e:
        print(f"❌ Error in check_eligibility: {str(e)}")
        return JSONResponse({
            "success": False,
            "eligible": False,
            "message": "Failed to check eligibility"
        })

@router.get("/debug/emergency")
async def debug_emergency(db: Session = Depends(get_db)):
    """EMERGENCY DEBUG - Direct SQL query"""
    try:
        # Use raw SQL to bypass all ORM issues
        from sqlalchemy import text
        
        result = db.execute(
            text("SELECT id, scheme_code, scheme_name, scheme_type, benefit_amount, is_active FROM government_schemes")
        ).fetchall()
        
        schemes = []
        for row in result:
            schemes.append({
                "id": row[0],
                "scheme_code": row[1],
                "scheme_name": row[2] or row[1],  # Use code as name if name is NULL
                "scheme_type": row[3] or "central",
                "benefit_amount": row[4] or "0",
                "is_active": row[5] if row[5] is not None else True
            })
        
        return {
            "success": True,
            "count": len(schemes),
            "schemes": schemes,
            "message": "EMERGENCY DEBUG - Raw SQL query"
        }
    except Exception as e:
        return {"success": False, "error": str(e)}
        
@router.post("/{scheme_id}/apply")
async def apply_for_scheme(
    request: Request,
    scheme_id: int,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Apply for a scheme"""
    origin = request.headers.get("origin", "")
    
    try:
        # Check eligibility
        eligibility = check_user_eligibility(db, current_user.id, scheme_id)
        
        if not eligibility.get("eligible", False):
            response = JSONResponse({
                "success": False,
                "message": "Not eligible for this scheme",
                "missing_documents": eligibility.get("missing_documents", [])
            }, status_code=status.HTTP_400_BAD_REQUEST)
            
            if origin and "vercel.app" in origin:
                response.headers["Access-Control-Allow-Origin"] = origin
                response.headers["Access-Control-Allow-Credentials"] = "true"
            
            return response
        
        # Check missing documents
        missing_docs = eligibility.get("missing_documents", [])
        if missing_docs:
            response = JSONResponse({
                "success": False,
                "message": f"Missing required documents: {', '.join(missing_docs)}",
                "missing_documents": missing_docs
            }, status_code=status.HTTP_400_BAD_REQUEST)
            
            if origin and "vercel.app" in origin:
                response.headers["Access-Control-Allow-Origin"] = origin
                response.headers["Access-Control-Allow-Credentials"] = "true"
            
            return response
        
        # Get scheme details
        scheme = get_scheme_by_id(db, scheme_id)
        if not scheme:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Scheme not found"
            )
        
        # Create application
        application = create_application(
            db=db,
            user_id=current_user.id,
            scheme_id=scheme_id,
            application_data={
                "eligibility_check": eligibility,
                "auto_applied": True,
                "applied_at": str(datetime.utcnow()),
                "farmer_name": current_user.full_name,
                "farmer_id": current_user.farmer_id,
                "scheme_name": scheme.scheme_name,
                "scheme_code": scheme.scheme_code
            }
        )
        
        response = JSONResponse({
            "success": True,
            "message": "Application submitted successfully",
            "application_id": application.application_id,
            "status": application.status.value if hasattr(application.status, 'value') else application.status,
            "applied_amount": application.applied_amount,
            "applied_at": application.applied_at.isoformat() if application.applied_at else None
        })
        
        # Set CORS headers
        if origin and "vercel.app" in origin:
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Allow-Credentials"] = "true"
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error in apply_for_scheme: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to apply for scheme: {str(e)}"
        )

@router.get("/code/{scheme_code}")
async def get_scheme_by_code(
    request: Request,
    scheme_code: str,
    db: Session = Depends(get_db)
):
    """Get scheme by code"""
    origin = request.headers.get("origin", "")
    
    try:
        scheme = get_scheme_by_code(db, scheme_code)
        if not scheme:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Scheme not found"
            )
        
        response = JSONResponse({
            "success": True,
            "scheme": {
                "id": scheme.id,
                "scheme_name": scheme.scheme_name,
                "scheme_code": scheme.scheme_code,
                "description": scheme.description,
                "scheme_type": scheme.scheme_type.value if hasattr(scheme.scheme_type, 'value') else scheme.scheme_type,
                "benefit_amount": scheme.benefit_amount,
                "last_date": scheme.last_date.isoformat() if scheme.last_date else None,
                "is_active": scheme.is_active,
                "eligibility_criteria": scheme.eligibility_criteria,
                "required_documents": scheme.required_documents
            }
        })
        
        # Set CORS headers
        if origin and "vercel.app" in origin:
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Allow-Credentials"] = "true"
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error in get_scheme_by_code: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch scheme"
        )
