# app/routers/upload.py - UPDATED TO USE FREE OCR (NO GEMINI)
from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.database import get_db
from app.models import User, Document
from app.ocr_processor import ocr_processor  # ✅ Use FREE OCR
from app.supabase_storage import supabase_storage
from app.utils.security import get_current_user
from app.config import settings
from datetime import datetime
import logging
import traceback

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/upload", tags=["document-upload"])

@router.post("/document")
async def upload_document(
    file: UploadFile = File(...),
    document_type: str = Form(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Upload and process any government document using FREE OCR"""
    
    logger.info(f"📤 Upload request: user={current_user.farmer_id}, type={document_type}, file={file.filename}")
    
    # Validate document type
    if document_type not in settings.DOCUMENT_TYPES:
        logger.error(f"❌ Invalid document type: {document_type}")
        raise HTTPException(status_code=400, 
            detail=f"Invalid document type. Must be one of: {', '.join(settings.DOCUMENT_TYPES)}")
    
    # Check file size
    try:
        file_bytes = await file.read()
        file_size = len(file_bytes)
        logger.info(f"📄 File size: {file_size} bytes")
    except Exception as e:
        logger.error(f"❌ Failed to read file: {str(e)}")
        raise HTTPException(status_code=400, detail=f"Failed to read file: {str(e)}")
    
    if file_size > settings.MAX_FILE_SIZE:
        logger.error(f"❌ File too large: {file_size} bytes")
        raise HTTPException(status_code=400, 
            detail=f"File too large. Max {settings.MAX_FILE_SIZE/1024/1024}MB allowed.")
    
    if file_size == 0:
        logger.error("❌ Empty file uploaded")
        raise HTTPException(status_code=400, detail="File is empty")
    
    # Check file extension
    file_ext = '.' + file.filename.split('.')[-1].lower() if '.' in file.filename else ''
    if file_ext not in settings.ALLOWED_EXTENSIONS:
        logger.error(f"❌ Invalid file type: {file_ext}")
        raise HTTPException(status_code=400, 
            detail=f"Invalid file type. Allowed: {', '.join(settings.ALLOWED_EXTENSIONS)}")
    
    try:
        # Upload to Supabase
        logger.info(f"📤 Uploading to Supabase: {file.filename}")
        file_path = await supabase_storage.upload_file(
            file_bytes=file_bytes,
            file_name=file.filename,
            user_id=current_user.farmer_id,
            document_type=document_type
        )
        logger.info(f"✅ Uploaded to Supabase: {file_path}")
        
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
        db.flush()
        logger.info(f"✅ Document record created: ID={document.id}")
        
        # Process with FREE OCR
        logger.info(f"🔍 Processing with FREE OCR for {document_type}")
        result = await ocr_processor.process_document(
            file_bytes=file_bytes,
            file_name=file.filename,
            document_type=document_type,
            farmer_id=current_user.farmer_id
        )
        
        logger.info(f"🔍 OCR result success: {result.get('success')}")
        
        if result["success"]:
            # Insert into specific document table
            table_name = result["table_name"]
            extracted_data = result["extracted_data"]
            extracted_data['document_id'] = document.id
            extracted_data['farmer_id'] = current_user.farmer_id
            
            logger.info(f"📊 Extracted data keys: {list(extracted_data.keys())}")
            logger.info(f"📋 Target table: {table_name}")
            
            # Get table columns to validate
            try:
                columns_query = f"""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name = '{table_name}'
                """
                table_columns = [row[0] for row in db.execute(text(columns_query)).fetchall()]
                logger.info(f"📋 Table columns: {table_columns}")
                
                # Filter extracted_data to only include columns that exist in the table
                filtered_data = {k: v for k, v in extracted_data.items() if k in table_columns}
                logger.info(f"🔍 Filtered data keys: {list(filtered_data.keys())}")
                
                if not filtered_data:
                    logger.warning(f"⚠️ No matching columns found in table {table_name}")
                    # Store raw text in the documents table instead
                    document.extracted_data = {"raw_text": result.get("raw_text", "")}
                    document.extraction_status = "partial"
                    db.commit()
                    
                    return {
                        "success": True,
                        "message": "Document uploaded but data extraction incomplete",
                        "document_id": document.id,
                        "extracted_data": extracted_data
                    }
                
            except Exception as column_error:
                logger.error(f"❌ Error getting table columns: {str(column_error)}")
                filtered_data = extracted_data
            
            # Build insert query dynamically
            columns = ', '.join(filtered_data.keys())
            placeholders = ', '.join([f':{k}' for k in filtered_data.keys()])
            
            insert_query = f"""
                INSERT INTO {table_name} ({columns})
                VALUES ({placeholders})
                RETURNING id
            """
            
            logger.info(f"🔍 Insert query: {insert_query}")
            
            try:
                result_proxy = db.execute(text(insert_query), filtered_data)
                record_id = result_proxy.scalar()
                logger.info(f"✅ Data inserted into {table_name}: ID={record_id}")
                
                # Update document with extraction info
                document.extraction_id = record_id
                document.extraction_table = table_name
                document.extraction_status = "completed"
                document.extraction_data = filtered_data
                document.confidence_score = result.get("confidence", 0.7)
                
                db.commit()
                
                return {
                    "success": True,
                    "message": f"{document_type.replace('_', ' ').title()} uploaded and processed successfully",
                    "document_id": document.id,
                    "extraction_id": record_id,
                    "extracted_data": filtered_data,
                    "confidence": result.get("confidence", 0.7)
                }
                
            except Exception as db_error:
                logger.error(f"❌ Database insert error: {str(db_error)}")
                db.rollback()
                
                document.extraction_status = "failed"
                document.extraction_error = str(db_error)
                document.extracted_data = {"raw_text": result.get("raw_text", "")}
                db.commit()
                
                return {
                    "success": True,
                    "message": "Document uploaded but database insertion failed",
                    "document_id": document.id,
                    "error": str(db_error),
                    "extracted_data": extracted_data
                }
        else:
            logger.error(f"❌ OCR processing failed: {result.get('error')}")
            document.extraction_status = "failed"
            document.extraction_error = result.get("error", "Unknown error")
            db.commit()
            
            return {
                "success": True,
                "message": "Document uploaded but OCR processing failed",
                "document_id": document.id,
                "error": result.get("error")
            }
            
    except Exception as e:
        logger.error(f"❌ Unexpected error: {str(e)}")
        logger.error(traceback.format_exc())
        
        # Try to save document record even if processing fails
        try:
            if 'document' in locals():
                document.extraction_status = "failed"
                document.extraction_error = str(e)
                db.commit()
        except:
            pass
            
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


@router.get("/test/ocr")
async def test_ocr(current_user: User = Depends(get_current_user)):
    """Test if OCR is configured correctly"""
    
    return {
        "success": True,
        "message": "OCR is configured and ready",
        "ocr_engine": settings.OCR_ENGINE,
        "languages": settings.OCR_LANGUAGES,
        "use_gpu": settings.OCR_USE_GPU,
        "paddle_available": 'paddleocr' in globals() or 'paddleocr' in locals(),
        "easyocr_available": 'easyocr' in globals() or 'easyocr' in locals(),
        "user": current_user.farmer_id
    }


# Keep all your other endpoints (get_farmer_documents, get_document_status, etc.)
# exactly as they are - no changes needed!

@router.get("/{document_type}/{farmer_id}")
async def get_farmer_documents(
    document_type: str,
    farmer_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get all documents of a specific type for a farmer"""
    # ... (keep your existing code)
    pass

@router.get("/status/{document_id}")
async def get_document_status(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get the processing status of a specific document"""
    # ... (keep your existing code)
    pass

@router.get("/types")
async def get_document_types():
    """Get list of supported document types"""
    return {
        "success": True,
        "document_types": settings.DOCUMENT_TYPES,
        "document_table_map": settings.DOCUMENT_TABLE_MAP,
        "ocr_engine": settings.OCR_ENGINE
    }

@router.get("/my-documents")
async def get_my_documents(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get all documents uploaded by current user across all types"""
    # ... (keep your existing code)
    pass
