# app/ocr_processor.py - COMPLETE FIXED VERSION WITH DEBUGGING
import os
import re
import json
import logging
import numpy as np
from PIL import Image
import io
from datetime import datetime
from typing import Dict, Any, Optional, List, Tuple
import cv2
from pdf2image import convert_from_bytes
import traceback

# OCR Libraries
try:
    import easyocr
    EASYOCR_AVAILABLE = True
    print("✅ EasyOCR is available")
except ImportError:
    EASYOCR_AVAILABLE = False
    print("⚠️ EasyOCR not installed - run: pip install easyocr")

from app.config import settings

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class OCRDocumentProcessor:
    """Extract data from Indian government documents using EasyOCR"""
    
    def __init__(self):
        """Initialize EasyOCR processor"""
        self.languages = ['en', 'hi', 'mr', 'ta', 'te', 'bn']
        self.confidence_threshold = 0.3  # Lowered threshold
        
        logger.info(f"🚀 Initializing EasyOCR processor...")
        logger.info(f"📚 Languages: {self.languages}")
        
        # Initialize OCR engine
        self.reader = self._initialize_reader()
        
        # Document table map from settings
        self.doc_table_map = settings.DOCUMENT_TABLE_MAP
        
        if not self.reader:
            logger.error("❌ OCR engine could not be initialized!")
        else:
            logger.info("✅ OCR engine initialized successfully")
    
    def _initialize_reader(self):
        """Initialize EasyOCR"""
        if not EASYOCR_AVAILABLE:
            logger.error("❌ EasyOCR not available")
            return None
        
        try:
            logger.info("📡 Initializing EasyOCR (this may take a moment on first run)...")
            
            # Map language codes for EasyOCR
            easyocr_langs = ['en', 'hi', 'mr', 'ta', 'te', 'bn']
            
            reader = easyocr.Reader(
                easyocr_langs,
                gpu=False,  # CPU mode for Render
                model_storage_directory='~/.easyocr/model',
                download_enabled=True,
                verbose=False
            )
            logger.info("✅ EasyOCR initialized successfully")
            return reader
            
        except Exception as e:
            logger.error(f"❌ EasyOCR initialization failed: {e}")
            logger.error(traceback.format_exc())
            return None
    
    async def process_document(self,
                               file_bytes: bytes,
                               file_name: str,
                               document_type: str,
                               farmer_id: str) -> Dict[str, Any]:
        """
        Extract structured data from document using OCR
        
        Args:
            file_bytes: Raw file bytes
            file_name: Original filename
            document_type: Type of document (aadhaar, pan, etc.)
            farmer_id: Farmer ID for linking
        
        Returns:
            Dictionary with extracted data
        """
        try:
            logger.info(f"🔍 ===== STARTING OCR PROCESSING =====")
            logger.info(f"🔍 Processing {document_type} document for farmer {farmer_id}")
            logger.info(f"📄 File name: {file_name}")
            logger.info(f"📦 File size: {len(file_bytes)} bytes")
            
            if not self.reader:
                logger.error("❌ OCR reader not initialized!")
                # Try to re-initialize
                self.reader = self._initialize_reader()
                if not self.reader:
                    return {
                        "success": False,
                        "error": "OCR engine not initialized. Please check EasyOCR installation."
                    }
            
            # Convert to image if PDF
            logger.info("📸 Converting to images...")
            images = await self._convert_to_images(file_bytes, file_name)
            logger.info(f"📸 Got {len(images)} images")
            
            if not images:
                logger.error("❌ No images could be extracted from document")
                return {
                    "success": False,
                    "error": "Could not convert document to image. Unsupported format or corrupted file."
                }
            
            # Process each page (max 3 pages)
            all_text = []
            all_boxes = []
            
            for i, image in enumerate(images[:3]):
                logger.info(f"📄 Processing page {i+1}/{min(len(images), 3)}")
                
                try:
                    # Preprocess image for better OCR
                    processed_image = self._preprocess_image(image)
                    
                    # Perform OCR with EasyOCR
                    logger.info(f"🔍 Running OCR on page {i+1}...")
                    result = self.reader.readtext(
                        np.array(processed_image),
                        paragraph=True,
                        width_ths=0.5,
                        height_ths=0.5,
                        decoder='greedy'  # Faster decoding
                    )
                    logger.info(f"✅ Page {i+1} OCR complete, got {len(result)} text blocks")
                    
                    page_text, page_boxes = self._parse_easyocr_result(result)
                    logger.info(f"📝 Page {i+1} extracted {len(page_text)} text segments")
                    
                    all_text.extend(page_text)
                    all_boxes.extend(page_boxes)
                    
                except Exception as e:
                    logger.error(f"❌ Error processing page {i+1}: {str(e)}")
                    logger.error(traceback.format_exc())
                    continue
            
            # Combine all text
            full_text = " ".join(all_text)
            logger.info(f"📝 Total extracted text length: {len(full_text)} characters")
            
            if not full_text.strip():
                logger.warning("⚠️ No text extracted from document!")
                # Return raw text empty but don't fail completely
                return {
                    "success": True,  # Still return success to avoid breaking flow
                    "table_name": self.doc_table_map.get(document_type, 'documents'),
                    "extracted_data": {"raw_text": ""},
                    "raw_text": "",
                    "confidence": 0.0,
                    "warning": "No text could be extracted"
                }
            
            # Log first 200 chars of extracted text for debugging
            logger.info(f"📝 First 200 chars: {full_text[:200]}")
            
            # Extract structured data based on document type
            logger.info(f"🔍 Extracting structured data for {document_type}...")
            extracted_data = self._extract_structured_data(full_text, document_type)
            logger.info(f"📊 Extracted fields: {list(extracted_data.keys())}")
            
            # Add metadata
            extracted_data['farmer_id'] = farmer_id
            extracted_data['processed_at'] = datetime.now().isoformat()
            extracted_data['ocr_engine'] = 'easyocr'
            extracted_data['confidence'] = self._calculate_confidence(all_boxes)
            
            # Validate and clean data
            cleaned_data = self._validate_and_clean(extracted_data, document_type)
            logger.info(f"✅ Successfully extracted {len(cleaned_data)} fields from {document_type}")
            
            return {
                "success": True,
                "table_name": self.doc_table_map.get(document_type, 'documents'),
                "extracted_data": cleaned_data,
                "raw_text": full_text[:1000],  # Store more raw text for debugging
                "confidence": extracted_data.get('confidence', 0.7)
            }
            
        except Exception as e:
            logger.error(f"❌ OCR processing error for {document_type}: {str(e)}")
            logger.error(traceback.format_exc())
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _convert_to_images(self, file_bytes: bytes, file_name: str) -> List[Image.Image]:
        """Convert PDF to images or return single image"""
        images = []
        
        try:
            if file_name.lower().endswith('.pdf'):
                logger.info("📄 Detected PDF file, converting to images...")
                # Convert PDF to images
                images = convert_from_bytes(
                    file_bytes,
                    first_page=1,
                    last_page=3,
                    fmt='jpeg',
                    dpi=150  # Lower DPI for faster processing
                )
                logger.info(f"✅ Converted PDF to {len(images)} images")
            else:
                # Single image
                logger.info("🖼️ Processing as single image...")
                image = Image.open(io.BytesIO(file_bytes))
                if image.mode != 'RGB':
                    image = image.convert('RGB')
                images.append(image)
                logger.info(f"✅ Loaded single image: size {image.size}, mode {image.mode}")
        except Exception as e:
            logger.error(f"❌ Image conversion error: {str(e)}")
            logger.error(traceback.format_exc())
        
        return images
    
    def _preprocess_image(self, image: Image.Image) -> Image.Image:
        """Preprocess image for better OCR accuracy"""
        try:
            # Convert PIL to OpenCV
            img = np.array(image)
            if len(img.shape) == 3:
                gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
            else:
                gray = img
            
            # Denoise
            denoised = cv2.fastNlMeansDenoising(gray, h=30)
            
            # Increase contrast
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
            enhanced = clahe.apply(denoised)
            
            # Thresholding
            _, thresh = cv2.threshold(enhanced, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            
            # Convert back to PIL
            processed = Image.fromarray(thresh)
            return processed
            
        except Exception as e:
            logger.warning(f"⚠️ Image preprocessing failed: {e}")
            return image
    
    def _parse_easyocr_result(self, result) -> Tuple[List[str], List[Dict]]:
        """Parse EasyOCR result to text and confidence boxes"""
        texts = []
        boxes = []
        
        for item in result:
            if len(item) == 3:
                bbox, text, confidence = item
                if confidence > self.confidence_threshold:
                    texts.append(text)
                    boxes.append({
                        'text': text,
                        'confidence': confidence,
                        'bbox': bbox
                    })
            elif len(item) == 2:  # Paragraph mode
                bbox, text = item
                texts.append(text)
                boxes.append({
                    'text': text,
                    'confidence': 0.8,  # Default confidence
                    'bbox': bbox
                })
        
        return texts, boxes
    
    def _calculate_confidence(self, boxes: List[Dict]) -> float:
        """Calculate average confidence score"""
        if not boxes:
            return 0.0
        
        confidences = [b.get('confidence', 0) for b in boxes if 'confidence' in b]
        if not confidences:
            return 0.7
        
        return sum(confidences) / len(confidences)
    
    def _extract_structured_data(self, text: str, document_type: str) -> Dict[str, Any]:
        """Extract structured data based on document type using regex patterns"""
        
        # Always include raw text for debugging
        result = {"_raw_text_sample": text[:200]}
        
        if document_type == 'aadhaar':
            extracted = self._extract_aadhaar(text)
        elif document_type == 'pan':
            extracted = self._extract_pan(text)
        elif document_type == 'land_record':
            extracted = self._extract_land_record(text)
        elif document_type == 'bank_passbook':
            extracted = self._extract_bank_details(text)
        elif document_type == 'income_certificate':
            extracted = self._extract_income_certificate(text)
        elif document_type == 'caste_certificate':
            extracted = self._extract_caste_certificate(text)
        elif document_type == 'domicile':
            extracted = self._extract_domicile(text)
        elif document_type == 'crop_insurance':
            extracted = self._extract_crop_insurance(text)
        elif document_type == 'death_certificate':
            extracted = self._extract_death_certificate(text)
        else:
            extracted = {"raw_text": text[:500]}
        
        # Merge with result
        result.update(extracted)
        return result
    
    def _extract_aadhaar(self, text: str) -> Dict[str, Any]:
        """Extract Aadhaar card details using regex"""
        data = {}
        
        # Aadhaar number (12 digits, possibly with spaces)
        aadhaar_pattern = r'\b(\d{4}[-.\s]?\d{4}[-.\s]?\d{4})\b'
        match = re.search(aadhaar_pattern, text)
        if match:
            data['aadhaar_number'] = re.sub(r'\D', '', match.group(1))
            logger.info(f"✅ Found Aadhaar number: {data['aadhaar_number']}")
        
        # Name
        name_patterns = [
            r'(?:Name|नाम)[:\s]*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)',
            r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})'
        ]
        for pattern in name_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                data['full_name'] = match.group(1).strip()
                logger.info(f"✅ Found name: {data['full_name']}")
                break
        
        # Date of Birth
        dob_patterns = [
            r'(?:DOB|Date of Birth|जन्म तिथि)[:\s]*(\d{2}[/-]\d{2}[/-]\d{4})',
            r'(\d{2}[/-]\d{2}[/-]\d{4})'
        ]
        for pattern in dob_patterns:
            match = re.search(pattern, text)
            if match:
                data['date_of_birth'] = self._parse_date(match.group(1))
                logger.info(f"✅ Found DOB: {data['date_of_birth']}")
                break
        
        # Gender
        if re.search(r'\bMale\b|\bपुरुष\b', text, re.I):
            data['gender'] = 'Male'
            logger.info("✅ Found gender: Male")
        elif re.search(r'\bFemale\b|\bमहिला\b', text, re.I):
            data['gender'] = 'Female'
            logger.info("✅ Found gender: Female")
        
        return data
    
    def _extract_pan(self, text: str) -> Dict[str, Any]:
        """Extract PAN card details"""
        data = {}
        
        # PAN number (format: ABCDE1234F)
        pan_pattern = r'\b([A-Z]{5}\d{4}[A-Z])\b'
        match = re.search(pan_pattern, text, re.I)
        if match:
            data['pan_number'] = match.group(1).upper()
            logger.info(f"✅ Found PAN: {data['pan_number']}")
        
        # Name
        name_patterns = [
            r'(?:Name|नाम)[:\s]*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)',
            r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})'
        ]
        for pattern in name_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                data['full_name'] = match.group(1).strip()
                logger.info(f"✅ Found name: {data['full_name']}")
                break
        
        # Father's Name
        father_pattern = r'(?:Father|पिता)[:\s]*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)'
        match = re.search(father_pattern, text, re.I)
        if match:
            data['father_name'] = match.group(1).strip()
            logger.info(f"✅ Found father's name: {data['father_name']}")
        
        return data
    
    def _extract_land_record(self, text: str) -> Dict[str, Any]:
        """Extract land record (7/12) details"""
        data = {}
        
        # Survey number
        survey_patterns = [
            r'(?:सर्वे|Survey)[:\s]*(\d+[/\d]*)',
            r'(\d+[/\d]*)'
        ]
        for pattern in survey_patterns:
            match = re.search(pattern, text)
            if match:
                data['survey_number'] = match.group(1)
                logger.info(f"✅ Found survey number: {data['survey_number']}")
                break
        
        # Land area in acres/hectares
        area_patterns = [
            r'(?:क्षेत्रफल|Area)[:\s]*([\d.]+)\s*(?:एकर|acres?)',
            r'([\d.]+)\s*(?:हेक्टेअर|hectares?)'
        ]
        for pattern in area_patterns:
            match = re.search(pattern, text, re.I)
            if match:
                if 'एकर' in pattern or 'acre' in pattern:
                    data['land_area_acres'] = float(match.group(1))
                    logger.info(f"✅ Found land area (acres): {data['land_area_acres']}")
                else:
                    data['land_area_hectares'] = float(match.group(1))
                    logger.info(f"✅ Found land area (hectares): {data['land_area_hectares']}")
                break
        
        return data
    
    def _extract_bank_details(self, text: str) -> Dict[str, Any]:
        """Extract bank passbook details"""
        data = {}
        
        # Account number
        account_patterns = [
            r'(?:Account|खाता)[:\s]*(\d{9,18})',
            r'(\d{9,18})'
        ]
        for pattern in account_patterns:
            match = re.search(pattern, text)
            if match:
                data['account_number'] = match.group(1)
                logger.info(f"✅ Found account number: {data['account_number']}")
                break
        
        # IFSC code
        ifsc_pattern = r'\b([A-Z]{4}0[A-Z0-9]{6})\b'
        match = re.search(ifsc_pattern, text, re.I)
        if match:
            data['ifsc_code'] = match.group(1).upper()
            logger.info(f"✅ Found IFSC: {data['ifsc_code']}")
        
        return data
    
    def _extract_income_certificate(self, text: str) -> Dict[str, Any]:
        """Extract income certificate details"""
        data = {}
        
        # Annual income
        income_patterns = [
            r'(?:Annual Income|वार्षिक उत्पन्न)[:\s]*[₹Rs.\s]*([\d,]+)',
            r'([\d,]+)\s*(?:रुपये|rupees?)'
        ]
        for pattern in income_patterns:
            match = re.search(pattern, text, re.I)
            if match:
                income_str = match.group(1).replace(',', '')
                try:
                    data['annual_income'] = float(income_str)
                    logger.info(f"✅ Found annual income: {data['annual_income']}")
                except:
                    pass
                break
        
        return data
    
    def _extract_caste_certificate(self, text: str) -> Dict[str, Any]:
        """Extract caste certificate details"""
        data = {}
        
        # Caste category
        caste_categories = ['SC', 'ST', 'OBC', 'General', 'अनुसूचित जाती', 'अनुसूचित जमाती', 'इतर मागास वर्ग']
        for category in caste_categories:
            if category in text:
                data['caste_category'] = category
                logger.info(f"✅ Found caste category: {data['caste_category']}")
                break
        
        return data
    
    def _extract_domicile(self, text: str) -> Dict[str, Any]:
        """Extract domicile certificate details"""
        data = {}
        
        # Name
        name_pattern = r'(?:Name|नाम)[:\s]*([\u0900-\u097F\s]+)'
        match = re.search(name_pattern, text)
        if match:
            data['full_name'] = match.group(1).strip()
            logger.info(f"✅ Found name: {data['full_name']}")
        
        return data
    
    def _extract_crop_insurance(self, text: str) -> Dict[str, Any]:
        """Extract crop insurance document details"""
        data = {}
        
        # Policy number
        policy_pattern = r'(?:Policy|पॉलिसी)[:\s]*([A-Z0-9/_-]+)'
        match = re.search(policy_pattern, text, re.I)
        if match:
            data['policy_number'] = match.group(1)
            logger.info(f"✅ Found policy number: {data['policy_number']}")
        
        return data
    
    def _extract_death_certificate(self, text: str) -> Dict[str, Any]:
        """Extract death certificate details"""
        data = {}
        
        # Deceased name
        name_pattern = r'(?:Name|नाम)[:\s]*([\u0900-\u097F\s]+)'
        match = re.search(name_pattern, text)
        if match:
            data['deceased_name'] = match.group(1).strip()
            logger.info(f"✅ Found deceased name: {data['deceased_name']}")
        
        return data
    
    def _validate_and_clean(self, data: Dict[str, Any], document_type: str) -> Dict[str, Any]:
        """Validate and clean data based on document type"""
        cleaned = {}
        
        for key, value in data.items():
            if value is None or value == '':
                continue
            
            # Clean specific fields
            if key == 'aadhaar_number' and isinstance(value, str):
                # Remove non-digits and ensure 12 digits
                cleaned_num = re.sub(r'\D', '', value)
                if len(cleaned_num) >= 12:
                    cleaned[key] = cleaned_num[:12]
                else:
                    cleaned[key] = cleaned_num
            
            elif key == 'pan_number' and isinstance(value, str):
                # Clean PAN number
                cleaned[key] = re.sub(r'[^A-Z0-9]', '', value.upper())
            
            elif key == 'ifsc_code' and isinstance(value, str):
                # Clean IFSC code
                cleaned[key] = re.sub(r'[^A-Z0-9]', '', value.upper())
            
            elif key in ['land_area_acres', 'land_area_hectares', 'annual_income', 'sum_insured', 'premium_amount']:
                # Ensure numeric fields are numbers
                try:
                    cleaned[key] = float(value)
                except (ValueError, TypeError):
                    pass
            
            elif key in ['date_of_birth', 'issue_date', 'valid_until', 'date_of_death']:
                # Parse dates
                parsed = self._parse_date(value)
                if parsed:
                    cleaned[key] = parsed
            
            else:
                # Keep other fields as strings
                cleaned[key] = str(value)[:500]
        
        return cleaned
    
    def _parse_date(self, date_str: str) -> Optional[str]:
        """Parse various date formats to YYYY-MM-DD"""
        if not date_str or date_str == 'null' or date_str == 'None':
            return None
        
        date_str = str(date_str).strip()
        
        # Try common patterns
        patterns = [
            (r'(\d{4})[-\/](\d{2})[-\/](\d{2})', 'ymd'),
            (r'(\d{2})[-\/](\d{2})[-\/](\d{4})', 'dmy'),
            (r'(\d{2})[-\/](\d{2})[-\/](\d{2})', 'dmyy'),
        ]
        
        for pattern, format_type in patterns:
            match = re.search(pattern, date_str)
            if match:
                parts = match.groups()
                if format_type == 'ymd':
                    return f"{parts[0]}-{parts[1]}-{parts[2]}"
                elif format_type == 'dmy':
                    return f"{parts[2]}-{parts[1]}-{parts[0]}"
                elif format_type == 'dmyy':
                    year = int(parts[2])
                    if year > 70:
                        return f"19{year:02d}-{parts[1]}-{parts[0]}"
                    else:
                        return f"20{year:02d}-{parts[1]}-{parts[0]}"
        
        return date_str[:10]


# Create singleton instance
ocr_processor = OCRDocumentProcessor()
