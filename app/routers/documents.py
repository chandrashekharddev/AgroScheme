# app/routers/documents.py - CORRECTED VERSION
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List

# ✅ CORRECT IMPORTS - ADD "app." prefix
from app.database import get_db
from app.schemas import DocumentResponse
from app.crud import get_user_documents
from app.routers.farmers import get_current_user  # ✅ Fixed import path

router = APIRouter(prefix="/documents", tags=["documents"])

@router.get("/", response_model=List[DocumentResponse])
async def get_all_documents(
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    documents = get_user_documents(db, current_user.id)
    
    # Add file_url to each document
    for doc in documents:
        if doc.file_path:
            doc.file_url = f"/uploads/{doc.file_path}"
    
    return documentsid)
