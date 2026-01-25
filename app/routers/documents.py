# app/routers/documents.py - CORRECTED VERSION
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List

from app.database import get_db
from app.schemas import DocumentResponse
from app.crud import get_user_documents
# Import from farmers module
from app.routers.farmers import get_current_user

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
            # Check if it's already a full URL or relative path
            if doc.file_path.startswith('http'):
                doc.file_url = doc.file_path
            else:
                # Add the /uploads/ prefix
                doc.file_url = f"/uploads/{doc.file_path}"
    
    return documents
