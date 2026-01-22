from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List

# ✅ Use relative imports
from database import get_db
from schemas import DocumentResponse
from crud import get_user_documents
from .farmers import get_current_user

router = APIRouter(prefix="/documents", tags=["documents"])

@router.get("/", response_model=List[DocumentResponse])
async def get_all_documents(
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return get_user_documents(db, current_user.id)