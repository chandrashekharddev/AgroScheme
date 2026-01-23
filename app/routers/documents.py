# app/routers/documents.py - CORRECTED VERSION
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List

# ✅ CORRECT IMPORTS - ADD "app." prefix
from app.database import get_db
from ..schemas import DocumentResponse
from app.crud import get_user_documents
from app.routers.farmers import get_current_user  # ✅ Fixed import path

router = APIRouter(prefix="/documents", tags=["documents"])

@router.get("/", response_model=List[DocumentResponse])
async def get_all_documents(
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return get_user_documents(db, current_user.id)
