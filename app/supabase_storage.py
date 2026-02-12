# app/supabase_storage.py - Use Service Role Key
from supabase import create_client
from app.config import settings
from datetime import datetime
import uuid
from typing import Optional, Dict, Any

class SupabaseStorage:
    def __init__(self):
        # ALWAYS use service role key for storage operations (bypasses RLS)
        self.supabase = create_client(
            settings.SUPABASE_URL,
            settings.SUPABASE_SERVICE_KEY  # Use service key, not anon key
        )
        self.bucket_name = "user-documents"
    
    async def upload_document(
        self,
        user_id: int,
        document_type: str,
        file_content: bytes,
        filename: str,
        content_type: str
    ) -> Dict[str, Any]:
        """Upload document to Supabase Storage using service role"""
        
        # Generate path
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
            # Upload with service role (bypasses RLS)
            self.supabase.storage.from_(self.bucket_name).upload(
                path=file_path,
                file=file_content,
                file_options={"content-type": content_type}
            )
            
            # Generate signed URL
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
        """Get signed URL using service role"""
        try:
            response = self.supabase.storage.from_(self.bucket_name).create_signed_url(
                path=file_path,
                expires_in=expires_in
            )
            return response["signedURL"] if response else None
        except Exception as e:
            print(f"❌ Failed to get URL: {e}")
            return None

supabase_storage = SupabaseStorage()
