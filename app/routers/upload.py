from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.database import get_db
from app.models import User, Document
from app.ocr_processor import OCRDocumentProcessor  # Changed from gemini_processor
from app.supabase_storage import supabase_storage
from app.utils.security import get_current_user
from app.config import settings
from datetime import datetime
import mimetypes
import logging
import traceback

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/upload", tags=["document-upload"])

# Initialize OCR processor instead of Gemini
processor = OCRDocumentProcessor()

@router.post("/document")
async def upload_document(
    file: UploadFile = File(...),
    document_type: str = Form(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Upload and process any government document using OCR"""
    
    logger.info(f"📤 Upload request: user={current_user.farmer_id}, type={document_type}, file={file.filename}")
    
    # Validate document type using settings
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
        db.flush()  # Get document.id
        logger.info(f"✅ Document record created: ID={document.id}")
        
        # Process with OCR
        logger.info(f"🤖 Processing with OCR for {document_type}")
        result = await processor.process_document(
            file_bytes=file_bytes,
            file_name=file.filename,
            document_type=document_type,
            farmer_id=current_user.farmer_id
        )
        
        logger.info(f"🤖 OCR result success: {result['success']}")
        
        if result["success"]:
            # Insert into specific document table
            table_name = result["table_name"]
            extracted_data = result["extracted_data"]
            extracted_data['document_id'] = document.id
            extracted_data['farmer_id'] = current_user.farmer_id
            
            # Remove layout info from extracted data before inserting to DB
            if '_layout_info' in extracted_data:
                del extracted_data['_layout_info']
            
            logger.info(f"📊 Extracted data keys: {list(extracted_data.keys())}")
            logger.info(f"📋 Target table: {table_name}")
            
            # Check if table exists
            try:
                table_check = db.execute(text(f"""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_schema = 'public' 
                        AND table_name = '{table_name}'
                    )
                """)).scalar()
                
                if not table_check:
                    logger.error(f"❌ Table {table_name} does not exist!")
                    document.extraction_status = "failed"
                    document.extraction_error = f"Table {table_name} does not exist"
                    db.commit()
                    return {
                        "success": True,
                        "message": "Document uploaded but table does not exist",
                        "document_id": document.id,
                        "error": f"Table {table_name} does not exist"
                    }
            except Exception as table_error:
                logger.error(f"❌ Error checking table: {str(table_error)}")
            
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
                
                if len(filtered_data) == 0:
                    logger.error(f"❌ No matching columns found in table {table_name}")
                    document.extraction_status = "failed"
                    document.extraction_error = f"No matching columns in table {table_name}"
                    db.commit()
                    return {
                        "success": True,
                        "message": "Document uploaded but column mismatch",
                        "document_id": document.id,
                        "error": "No matching columns in target table",
                        "extracted_keys": list(extracted_data.keys()),
                        "table_columns": table_columns
                    }
                
            except Exception as column_error:
                logger.error(f"❌ Error getting table columns: {str(column_error)}")
                filtered_data = extracted_data  # Fallback to original
            
            # Build insert query dynamically
            if filtered_data:
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
                    db.flush()  # Ensure ID is available
                    logger.info(f"✅ Data inserted into {table_name}: ID={record_id}")
                    
                    # Update document with extraction info
                    document.extraction_id = record_id
                    document.extraction_table = table_name
                    document.extraction_status = "completed"
                    document.extraction_data = filtered_data
                    document.confidence_score = result.get("confidence", 0)
                    
                    db.commit()
                    logger.info(f"✅ Database commit successful")
                    
                    return {
                        "success": True,
                        "message": f"{document_type.replace('_', ' ').title()} uploaded and processed successfully",
                        "document_id": document.id,
                        "extraction_id": record_id,
                        "extracted_data": filtered_data,
                        "confidence": result.get("confidence", 0)
                    }
                    
                except Exception as db_error:
                    logger.error(f"❌ Database insert error: {str(db_error)}")
                    logger.error(traceback.format_exc())
                    db.rollback()
                    
                    document.extraction_status = "failed"
                    document.extraction_error = str(db_error)
                    db.commit()
                    
                    return {
                        "success": True,
                        "message": "Document uploaded but database insertion failed",
                        "document_id": document.id,
                        "error": str(db_error),
                        "extracted_data": filtered_data
                    }
            else:
                # No data to insert
                document.extraction_status = "completed"
                document.extraction_data = {}
                db.commit()
                
                return {
                    "success": True,
                    "message": "Document uploaded but no data extracted",
                    "document_id": document.id,
                    "extracted_data": {}
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

# All other endpoints (get_farmer_documents, get_document_status, debug_tables, etc.)
# remain exactly the same as in your original upload.py

@router.get("/{document_type}/{farmer_id}")
async def get_farmer_documents(
    document_type: str,
    farmer_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get all documents of a specific type for a farmer"""
    
    logger.info(f"📋 Fetching {document_type} documents for farmer {farmer_id}")
    
    # Security check - only allow farmers to view their own documents or admins
    if current_user.farmer_id != farmer_id and current_user.role != "admin":
        logger.error(f"❌ Unauthorized access: user {current_user.farmer_id} trying to access farmer {farmer_id}")
        raise HTTPException(status_code=403, detail="Not authorized to view these documents")
    
    # Validate document type
    if document_type not in settings.DOCUMENT_TABLE_MAP:
        logger.error(f"❌ Invalid document type: {document_type}")
        raise HTTPException(status_code=400, detail="Invalid document type")
    
    table_name = settings.DOCUMENT_TABLE_MAP[document_type]
    logger.info(f"📋 Using table: {table_name}")
    
    try:
        # Check if table exists
        table_check = db.execute(text(f"""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = '{table_name}'
            )
        """)).scalar()
        
        if not table_check:
            logger.error(f"❌ Table {table_name} does not exist")
            return {
                "success": True,
                "document_type": document_type,
                "count": 0,
                "documents": [],
                "warning": f"Table {table_name} does not exist"
            }
        
        # Query the table
        query = f"SELECT * FROM {table_name} WHERE farmer_id = :farmer_id ORDER BY created_at DESC"
        result = db.execute(text(query), {'farmer_id': farmer_id}).fetchall()
        
        # Convert to list of dicts with proper serialization
        documents = []
        for row in result:
            doc_dict = {}
            for key, value in row._mapping.items():
                # Handle datetime objects
                if hasattr(value, 'isoformat'):
                    doc_dict[key] = value.isoformat()
                # Handle other types
                elif value is None:
                    doc_dict[key] = None
                else:
                    doc_dict[key] = str(value) if not isinstance(value, (int, float, bool)) else value
            documents.append(doc_dict)
        
        logger.info(f"✅ Found {len(documents)} documents in {table_name}")
        
        return {
            "success": True,
            "document_type": document_type,
            "count": len(documents),
            "documents": documents
        }
        
    except Exception as e:
        logger.error(f"❌ Database error: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to fetch documents: {str(e)}")

@router.get("/status/{document_id}")
async def get_document_status(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get the processing status of a specific document"""
    
    logger.info(f"📋 Checking status for document ID: {document_id}")
    
    try:
        document = db.query(Document).filter(Document.id == document_id).first()
        
        if not document:
            logger.error(f"❌ Document {document_id} not found")
            raise HTTPException(status_code=404, detail="Document not found")
        
        # Security check
        if document.user_id != current_user.id and current_user.role != "admin":
            logger.error(f"❌ Unauthorized access: user {current_user.farmer_id} trying to access document {document_id}")
            raise HTTPException(status_code=403, detail="Not authorized to view this document")
        
        status_info = {
            "document_id": document.id,
            "file_name": document.file_name,
            "document_type": document.document_type,
            "uploaded_at": document.uploaded_at.isoformat() if document.uploaded_at else None,
            "extraction_status": document.extraction_status,
            "extraction_table": document.extraction_table,
            "extraction_id": document.extraction_id,
            "confidence_score": getattr(document, 'confidence_score', None)
        }
        
        # If extraction was successful, fetch the extracted data
        if document.extraction_status == "completed" and document.extraction_table and document.extraction_id:
            try:
                # Check if extraction table exists
                table_check = db.execute(text(f"""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_schema = 'public' 
                        AND table_name = '{document.extraction_table}'
                    )
                """)).scalar()
                
                if table_check:
                    query = f"SELECT * FROM {document.extraction_table} WHERE id = :extraction_id"
                    result = db.execute(text(query), {'extraction_id': document.extraction_id}).first()
                    
                    if result:
                        # Convert to dict for JSON response
                        extracted = {}
                        for key, value in result._mapping.items():
                            if hasattr(value, 'isoformat'):
                                extracted[key] = value.isoformat()
                            elif isinstance(value, (int, float, bool)):
                                extracted[key] = value
                            else:
                                extracted[key] = str(value) if value else None
                        status_info["extracted_data"] = extracted
                else:
                    logger.warning(f"⚠️ Extraction table {document.extraction_table} does not exist")
                    status_info["extraction_table_missing"] = True
                    
            except Exception as e:
                logger.error(f"❌ Failed to fetch extracted data: {str(e)}")
                status_info["extracted_data_error"] = str(e)
        
        if document.extraction_error:
            status_info["error"] = document.extraction_error
        
        return {
            "success": True,
            "status": status_info
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Unexpected error in get_document_status: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to get document status: {str(e)}")

# ==================== DEBUG ENDPOINTS ====================

@router.get("/debug/tables")
async def debug_tables(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Debug endpoint to check if document tables exist and have data"""
    results = {}
    
    for doc_type, table_name in settings.DOCUMENT_TABLE_MAP.items():
        try:
            # Check if table exists
            table_check = db.execute(text(f"""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_name = '{table_name}'
                )
            """)).scalar()
            
            results[table_name] = {
                "exists": table_check,
                "document_type": doc_type
            }
            
            if table_check:
                # Get total row count
                total_count = db.execute(text(f"SELECT COUNT(*) FROM {table_name}")).scalar()
                results[table_name]["total_rows"] = total_count
                
                # Get count for current user
                user_count = db.execute(
                    text(f"SELECT COUNT(*) FROM {table_name} WHERE farmer_id = :farmer_id"),
                    {'farmer_id': current_user.farmer_id}
                ).scalar()
                results[table_name]["user_rows"] = user_count
                
                # Get sample data for current user
                if user_count > 0:
                    sample = db.execute(
                        text(f"SELECT * FROM {table_name} WHERE farmer_id = :farmer_id LIMIT 1"),
                        {'farmer_id': current_user.farmer_id}
                    ).first()
                    
                    if sample:
                        # Convert to dict for JSON serialization
                        sample_dict = {}
                        for key, value in sample._mapping.items():
                            if hasattr(value, 'isoformat'):
                                sample_dict[key] = value.isoformat()
                            elif isinstance(value, (int, float, bool)):
                                sample_dict[key] = value
                            else:
                                sample_dict[key] = str(value) if value else None
                        results[table_name]["sample"] = sample_dict
                    
        except Exception as e:
            results[table_name] = {
                "error": str(e)
            }
    
    return {
        "success": True,
        "user_id": current_user.farmer_id,
        "tables": results
    }

@router.post("/test-insert")
async def test_insert(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Test endpoint to directly insert data into document table"""
    
    logger.info(f"🧪 Test insert for user {current_user.farmer_id}")
    
    try:
        # First create a document record
        test_document = Document(
            user_id=current_user.id,
            document_type="aadhaar",
            file_path="test/path.jpg",
            file_name="test.jpg",
            file_size=1024,
            uploaded_at=datetime.now()
        )
        db.add(test_document)
        db.flush()
        logger.info(f"✅ Test document created: ID={test_document.id}")
        
        # Test data for aadhaar table
        test_data = {
            "farmer_id": current_user.farmer_id,
            "document_id": test_document.id,
            "aadhaar_number": "123456789012",
            "full_name": "Test User",
            "date_of_birth": "1990-01-01",
            "gender": "Male",
            "address": "Test Address, Test City",
            "pincode": "400001",
            "father_name": "Test Father",
            "mobile_number": "9876543210"
        }
        
        # Check if aadhaar_documents table exists
        table_check = db.execute(text("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = 'aadhaar_documents'
            )
        """)).scalar()
        
        if not table_check:
            logger.error("❌ aadhaar_documents table does not exist!")
            return {
                "success": False,
                "error": "aadhaar_documents table does not exist"
            }
        
        # Try to insert into aadhaar_documents
        insert_query = """
            INSERT INTO aadhaar_documents 
            (farmer_id, document_id, aadhaar_number, full_name, date_of_birth, gender, address, pincode, father_name, mobile_number)
            VALUES 
            (:farmer_id, :document_id, :aadhaar_number, :full_name, :date_of_birth, :gender, :address, :pincode, :father_name, :mobile_number)
            RETURNING id
        """
        
        logger.info(f"🔍 Test data: {test_data}")
        
        result = db.execute(text(insert_query), test_data)
        record_id = result.scalar()
        
        # Update test document
        test_document.extraction_id = record_id
        test_document.extraction_table = "aadhaar_documents"
        test_document.extraction_status = "completed"
        test_document.extraction_data = test_data
        
        db.commit()
        logger.info(f"✅ Test data inserted successfully: ID={record_id}")
        
        return {
            "success": True,
            "message": "Test data inserted successfully",
            "document_id": test_document.id,
            "record_id": record_id
        }
        
    except Exception as e:
        db.rollback()
        logger.error(f"❌ Test insert failed: {str(e)}")
        logger.error(traceback.format_exc())
        return {
            "success": False,
            "error": str(e)
        }

# ==================== TEST ENDPOINTS ====================

@router.get("/test")
async def test_endpoint(current_user: User = Depends(get_current_user)):
    """Test if upload API is working"""
    return {
        "success": True,
        "message": "Upload API is working",
        "user": current_user.farmer_id,
        "document_types": settings.DOCUMENT_TYPES
    }

# ==================== TEST OCR ENDPOINT ====================
@router.get("/test/ocr")
async def test_ocr(
    current_user: User = Depends(get_current_user)
):
    """Test if OCR is configured correctly"""
    try:
        # Check OCR availability
        ocr_status = {
            "paddle_available": hasattr(processor, 'paddle_ocr') and processor.paddle_ocr is not None,
            "easyocr_available": hasattr(processor, 'easy_ocr') and processor.easy_ocr is not None,
            "layout_available": processor.use_layout,
            "current_engine": processor.ocr_engine,
            "use_gpu": processor.use_gpu
        }
        
        return {
            "success": True,
            "message": "OCR test endpoint",
            "user": {
                "id": current_user.id,
                "farmer_id": current_user.farmer_id,
                "name": current_user.full_name
            },
            "config": {
                "ocr_engine": settings.OCR_ENGINE,
                "document_types": settings.DOCUMENT_TYPES,
                "max_file_size": settings.MAX_FILE_SIZE,
                "allowed_extensions": list(settings.ALLOWED_EXTENSIONS),
                "ocr_status": ocr_status
            }
        }
    except Exception as e:
        logger.error(f"❌ OCR test error: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }

# ==================== UTILITY ENDPOINTS ====================

@router.get("/types")
async def get_document_types():
    """Get list of supported document types"""
    return {
        "success": True,
        "document_types": settings.DOCUMENT_TYPES,
        "document_table_map": settings.DOCUMENT_TABLE_MAP
    }

@router.get("/my-documents")
async def get_my_documents(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get all documents uploaded by current user across all types"""
    
    logger.info(f"📋 Fetching all documents for user {current_user.farmer_id}")
    
    all_documents = []
    
    for doc_type, table_name in settings.DOCUMENT_TABLE_MAP.items():
        try:
            query = f"SELECT * FROM {table_name} WHERE farmer_id = :farmer_id ORDER BY created_at DESC"
            result = db.execute(text(query), {'farmer_id': current_user.farmer_id}).fetchall()
            
            for row in result:
                doc_dict = dict(row._mapping)
                # Convert datetime objects to strings
                for key, value in doc_dict.items():
                    if hasattr(value, 'isoformat'):
                        doc_dict[key] = value.isoformat()
                doc_dict['document_type'] = doc_type
                all_documents.append(doc_dict)
                
        except Exception as e:
            logger.warning(f"⚠️ Could not fetch from {table_name}: {str(e)}")
            continue
    
    return {
        "success": True,
        "count": len(all_documents),
        "documents": all_documents
    }
