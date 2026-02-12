# app/supabase_storage.py
from supabase import create_client
from app.config import settings
from datetime import datetime, timedelta
import uuid
from typing import Optional, Dict, Any

class SupabaseStorage:
    def __init__(self):
        self.supabase = create_client(
            settings.SUPABASE_URL,
            settings.SUPABASE_KEY
        )
        self.bucket_name = "user-documents"  # Match your bucket name
    
    async def upload_document(
        self,
        user_id: int,
        document_type: str,
        file_content: bytes,
        filename: str,
        content_type: str
    ) -> Dict[str, Any]:
        """
        Upload document to Supabase Storage with organized folder structure
        Path: user_{user_id}/{document_type}/{YYYY}/{MM}/{UUID}_{filename}
        """
        # Generate organized path
        now = datetime.utcnow()
        unique_id = str(uuid.uuid4())[:8]
        safe_filename = filename.replace(" ", "_").replace("(", "").replace(")", "")
        
        file_path = (
            f"user_{user_id}/"
            f"{document_type}/"
            f"{now.year}/{now.month:02d}/"
            f"{unique_id}_{safe_filename}"
        )
        
        try:
            # Upload to Supabase Storage
            self.supabase.storage.from_(self.bucket_name).upload(
                path=file_path,
                file=file_content,
                file_options={"content-type": content_type}
            )
            
            # Generate signed URL for secure access (1 hour expiry)
            signed_url = self.supabase.storage.from_(self.bucket_name).create_signed_url(
                path=file_path,
                expires_in=3600
            )
            
            return {
                "success": True,
                "file_path": file_path,
                "file_url": signed_url["signedURL"] if signed_url else None,
                "file_size": len(file_content),
                "content_type": content_type
            }
            
        except Exception as e:
            print(f"❌ Upload failed: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def get_document_url(self, file_path: str, expires_in: int = 3600) -> Optional[str]:
        """Get signed URL for document access"""
        try:
            response = self.supabase.storage.from_(self.bucket_name).create_signed_url(
                path=file_path,
                expires_in=expires_in
            )
            return response["signedURL"] if response else None
        except Exception as e:
            print(f"❌ Failed to get URL: {e}")
            return None
    
    async def delete_document(self, file_path: str) -> bool:
        """Delete document from storage"""
        try:
            self.supabase.storage.from_(self.bucket_name).remove([file_path])
            return True
        except Exception as e:
            print(f"❌ Failed to delete: {e}")
            return False

supabase_storage = SupabaseStorage()
