# app/ai_processor.py - FIXED VERSION
import os
from PIL import Image
from typing import Dict, Any
import json

# Disable Gemini AI for now to avoid warnings
# We'll use simple OCR instead

try:
    import pytesseract
    TESSERACT_AVAILABLE = True
except ImportError:
    TESSERACT_AVAILABLE = False

class DocumentProcessor:
    def __init__(self):
        self.gemini_available = False
        self.ocr_available = TESSERACT_AVAILABLE
    
    async def extract_document_data(self, document_type: str, file_path: str) -> Dict[str, Any]:
        """
        Extract data from document using simple OCR
        """
        try:
            if not self.ocr_available:
                return {
                    "extracted_data": {"message": "OCR not available"},
                    "confidence_score": 0.0,
                    "processing_method": "none"
                }
            
            # Simple text extraction for now
            if file_path.lower().endswith(('.jpg', '.jpeg', '.png')):
                image = Image.open(file_path)
                text = self.extract_text_from_image(image)
            else:
                text = "File type not supported for OCR"
            
            # Basic parsing based on document type
            parsed_data = self.parse_text(text, document_type)
            
            return {
                "extracted_data": parsed_data,
                "confidence_score": 0.7,
                "processing_method": "ocr",
                "raw_text": text[:500]  # First 500 chars
            }
            
        except Exception as e:
            print(f"Error processing document: {str(e)}")
            return {
                "extracted_data": {"error": str(e)},
                "confidence_score": 0.0,
                "processing_method": "failed"
            }
    
    def extract_text_from_image(self, image: Image.Image) -> str:
        """Extract text using pytesseract"""
        if not self.ocr_available:
            return "OCR not available"
        
        try:
            return pytesseract.image_to_string(image)
        except:
            return "Failed to extract text"
    
    def parse_text(self, text: str, doc_type: str) -> Dict[str, Any]:
        """Simple text parsing"""
        import re
        
        parsed_data = {}
        
        if doc_type == "aadhaar":
            # Look for Aadhaar-like patterns
            aadhaar_pattern = r'\d{4}\s\d{4}\s\d{4}'
            matches = re.findall(aadhaar_pattern, text)
            if matches:
                parsed_data["aadhaar_number"] = matches[0]
        
        elif doc_type == "pan":
            # Look for PAN-like patterns
            pan_pattern = r'[A-Z]{5}[0-9]{4}[A-Z]{1}'
            matches = re.findall(pan_pattern, text)
            if matches:
                parsed_data["pan_number"] = matches[0]
        
        # Add more document type parsing as needed
        
        return parsed_data

# Global instance
document_processor = DocumentProcessor()