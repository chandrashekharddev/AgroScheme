# app/routers/upload.py

from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import User, Document
from app.gemini_processor import GeminiDocumentProcessor
from app.supabase_storage import supabase_storage
from app.utils.security import get_current_user
from datetime import datetime
import json

router = APIRouter(prefix="/upload", tags=["document-upload"])
processor = GeminiDocumentProcessor()

@router.post("/document")
async def upload_document(
    file: UploadFile = File(...),
    document_type: str = Form(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Upload and process any government document"""
    
    valid_types = [
        'aadhaar', 'pan', 'land_record', 'bank_passbook', 'income_certificate',
        'caste_certificate', 'domicile', 'crop_insurance', 'death_certificate'
    ]
    
    if document_type not in valid_types:
        raise HTTPException(status_code=400, 
            detail=f"Invalid document type. Must be one of: {', '.join(valid_types)}")
    
    # Check file size (10MB limit)
    file_size = 0
    file_bytes = await file.read()
    file_size = len(file_bytes)
    
    if file_size > 10 * 1024 * 1024:  # 10MB
        raise HTTPException(status_code=400, detail="File too large. Max 10MB allowed.")
    
    # Upload to Supabase
    file_path = await supabase_storage.upload_file(
        file_bytes=file_bytes,
        file_name=file.filename,
        user_id=current_user.farmer_id,
        document_type=document_type
    )
    
    # Create document record
    document = Document(
        user_id=current_user.id,
        document_type=document_type,
        file_path=file_path,
        file_name=file.filename,
        file_size=file_size,
        uploaded_at=datetime.now()
    )
    db.add(document)
    db.flush()  # Get document.id
    
    # Process with Gemini
    result = await processor.process_document(
        file_bytes=file_bytes,
        file_name=file.filename,
        document_type=document_type,
        farmer_id=current_user.farmer_id
    )
    
    if result["success"]:
        # Insert into specific document table
        table_name = result["table_name"]
        extracted_data = result["extracted_data"]
        extracted_data['document_id'] = document.id
        
        # Build insert query dynamically
        columns = ', '.join(extracted_data.keys())
        placeholders = ', '.join([f':{k}' for k in extracted_data.keys()])
        
        insert_query = f"""
            INSERT INTO {table_name} ({columns})
            VALUES ({placeholders})
            RETURNING id
        """
        
        record_id = db.execute(insert_query, extracted_data).scalar()
        
        # Update document
        document.extraction_id = record_id
        document.extraction_table = table_name
        document.extraction_status = "completed"
        document.extraction_data = extracted_data
        
        db.commit()
        
        return {
            "success": True,
            "message": f"{document_type.replace('_', ' ').title()} uploaded and processed successfully",
            "document_id": document.id,
            "extraction_id": record_id,
            "extracted_data": extracted_data
        }
    else:
        document.extraction_status = "failed"
        document.extraction_error = result.get("error", "Unknown error")
        db.commit()
        
        return {
            "success": True,
            "message": "Document uploaded but processing failed",
            "document_id": document.id,
            "error": result.get("error")
        }

@router.get("/{document_type}/{farmer_id}")
async def get_farmer_documents(
    document_type: str,
    farmer_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get all documents of a specific type for a farmer"""
    
    # Security check - only allow farmers to view their own documents
    if current_user.farmer_id != farmer_id and current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Not authorized to view these documents")
    
    table_map = {
        'aadhaar': 'aadhaar_documents',
        'pan': 'pan_documents',
        'land_record': 'land_records',
        'bank_passbook': 'bank_documents',
        'income_certificate': 'income_certificates',
        'caste_certificate': 'caste_certificates',
        'domicile': 'domicile_certificates',
        'crop_insurance': 'crop_insurance_docs',
        'death_certificate': 'death_certificates'
    }
    
    table_name = table_map.get(document_type)
    if not table_name:
        raise HTTPException(status_code=400, detail="Invalid document type")
    
    query = f"SELECT * FROM {table_name} WHERE farmer_id = :farmer_id ORDER BY created_at DESC"
    result = db.execute(query, {'farmer_id': farmer_id}).fetchall()
    
    # Convert to list of dicts
    documents = []
    for row in result:
        doc_dict = dict(row._mapping)
        documents.append(doc_dict)
    
    return {
        "success": True,
        "document_type": document_type,
        "count": len(documents),
        "documents": documents
    }
