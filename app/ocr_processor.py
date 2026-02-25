# app/ocr_processor.py - COMPLETE FREE OCR (NO GEMINI)
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

# OCR Libraries
try:
    from paddleocr import PaddleOCR
    PADDLE_AVAILABLE = True
    print("✅ PaddleOCR is available")
except ImportError:
    PADDLE_AVAILABLE = False
    print("⚠️ PaddleOCR not installed - run: pip install paddlepaddle paddleocr")

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
    """Extract data from Indian government documents using FREE OCR (NO GEMINI)"""
    
    def __init__(self, engine: str = None):
        """
        Initialize OCR processor
        
        Args:
            engine: 'paddle' or 'easyocr' (default from settings)
        """
        self.engine = engine or settings.OCR_ENGINE
        self.languages = settings.OCR_LANGUAGES
        self.confidence_threshold = settings.OCR_CONFIDENCE_THRESHOLD
        self.use_gpu = settings.OCR_USE_GPU
        
        logger.info(f"🚀 Initializing FREE OCR processor with engine: {self.engine}")
        logger.info(f"📚 Languages: {self.languages}")
        logger.info(f"🎮 Use GPU: {self.use_gpu}")
        
        # Initialize OCR engine
        self.reader = self._initialize_reader()
        
        # Document table map from settings
        self.doc_table_map = settings.DOCUMENT_TABLE_MAP
        
        if not self.reader:
            logger.error("❌ No OCR engine available!")
    
    def _initialize_reader(self):
        """Initialize the selected OCR engine"""
        
        # Try PaddleOCR first if selected
        if self.engine == "paddle" and PADDLE_AVAILABLE:
            try:
                logger.info("📡 Initializing PaddleOCR...")
                
                return PaddleOCR(
                    use_angle_cls=True,
                    lang='en',  # PaddleOCR handles multilingual automatically
                    show_log=False,
                    use_gpu=self.use_gpu,
                    ocr_version='PP-OCRv4'
                )
            except Exception as e:
                logger.error(f"❌ PaddleOCR initialization failed: {e}")
                logger.info("⚠️ Falling back to EasyOCR...")
                self.engine = "easyocr"
        
        # Try EasyOCR
        if (self.engine == "easyocr" or not PADDLE_AVAILABLE) and EASYOCR_AVAILABLE:
            try:
                logger.info("📡 Initializing EasyOCR...")
                
                # EasyOCR language mapping
                easyocr_langs = []
                lang_map = {
                    'en': 'en', 'hi': 'hi', 'mr': 'mr', 'ta': 'ta',
                    'te': 'te', 'bn': 'bn', 'gu': 'gu', 'kn': 'kn',
                    'ml': 'ml', 'or': 'or', 'pa': 'pa', 'ur': 'ur'
                }
                
                for lang in self.languages:
                    if lang in lang_map:
                        easyocr_langs.append(lang_map[lang])
                
                if not easyocr_langs:
                    easyocr_langs = ['en']
                
                logger.info(f"📚 EasyOCR languages: {easyocr_langs}")
                
                return easyocr.Reader(
                    easyocr_langs,
                    gpu=self.use_gpu,
                    model_storage_directory='~/.easyocr/model',
                    download_enabled=True
                )
            except Exception as e:
                logger.error(f"❌ EasyOCR initialization failed: {e}")
        
        logger.error("❌ No OCR engine could be initialized!")
        return None
    
    async def process_document(self,
                               file_bytes: bytes,
                               file_name: str,
                               document_type: str,
                               farmer_id: str) -> Dict[str, Any]:
        """
        Extract structured data from document using FREE OCR
        
        Args:
            file_bytes: Raw file bytes
            file_name: Original filename
            document_type: Type of document (aadhaar, pan, etc.)
            farmer_id: Farmer ID for linking
        
        Returns:
            Dictionary with extracted data
        """
        try:
            logger.info(f"🔍 Processing {document_type} document for farmer {farmer_id}")
            
            if not self.reader:
                return {
                    "success": False,
                    "error": "OCR engine not initialized. Please check your installation."
                }
            
            # Convert to image if PDF
            images = await self._convert_to_images(file_bytes, file_name)
            
            if not images:
                return {
                    "success": False,
                    "error": "Could not convert document to image"
                }
            
            # Process each page (max 3 pages)
            all_text = []
            all_boxes = []
            
            for i, image in enumerate(images[:3]):
                logger.info(f"📄 Processing page {i+1}/{min(len(images), 3)}")
                
                # Preprocess image for better OCR
                processed_image = self._preprocess_image(image)
                
                # Perform OCR based on engine
                if self.engine == "paddle" and PADDLE_AVAILABLE:
                    result = self.reader.ocr(np.array(processed_image), cls=True)
                    page_text, page_boxes = self._parse_paddle_result(result)
                else:
                    result = self.reader.readtext(np.array(processed_image))
                    page_text, page_boxes = self._parse_easyocr_result(result)
                
                all_text.extend(page_text)
                all_boxes.extend(page_boxes)
            
            # Combine all text
            full_text = " ".join(all_text)
            logger.info(f"📝 Extracted text length: {len(full_text)} chars")
            
            # Extract structured data based on document type
            extracted_data = self._extract_structured_data(full_text, document_type)
            
            # Add metadata
            extracted_data['farmer_id'] = farmer_id
            extracted_data['processed_at'] = datetime.now().isoformat()
            extracted_data['ocr_engine'] = self.engine
            extracted_data['confidence'] = self._calculate_confidence(all_boxes)
            
            # Validate and clean data
            cleaned_data = self._validate_and_clean(extracted_data, document_type)
            
            logger.info(f"✅ Successfully extracted data from {document_type}")
            logger.info(f"📊 Extracted fields: {list(cleaned_data.keys())}")
            
            return {
                "success": True,
                "table_name": self.doc_table_map.get(document_type, 'documents'),
                "extracted_data": cleaned_data,
                "raw_text": full_text[:500],
                "confidence": extracted_data.get('confidence', 0.7)
            }
            
        except Exception as e:
            logger.error(f"❌ OCR processing error for {document_type}: {str(e)}")
            import traceback
            traceback.print_exc()
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _convert_to_images(self, file_bytes: bytes, file_name: str) -> List[Image.Image]:
        """Convert PDF to images or return single image"""
        images = []
        
        try:
            if file_name.lower().endswith('.pdf'):
                # Convert PDF to images
                images = convert_from_bytes(
                    file_bytes,
                    first_page=1,
                    last_page=3,
                    fmt='jpeg',
                    dpi=200
                )
                logger.info(f"✅ Converted PDF to {len(images)} images")
            else:
                # Single image
                image = Image.open(io.BytesIO(file_bytes))
                if image.mode != 'RGB':
                    image = image.convert('RGB')
                images.append(image)
                logger.info("✅ Loaded single image")
        except Exception as e:
            logger.error(f"❌ Image conversion error: {str(e)}")
        
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
    
    def _parse_paddle_result(self, result) -> Tuple[List[str], List[Dict]]:
        """Parse PaddleOCR result to text and confidence boxes"""
        texts = []
        boxes = []
        
        if not result:
            return texts, boxes
        
        for line in result:
            for word_info in line:
                text = word_info[1][0]
                confidence = word_info[1][1]
                
                if confidence > self.confidence_threshold:
                    texts.append(text)
                    boxes.append({
                        'text': text,
                        'confidence': confidence,
                        'bbox': word_info[0]
                    })
        
        return texts, boxes
    
    def _parse_easyocr_result(self, result) -> Tuple[List[str], List[Dict]]:
        """Parse EasyOCR result to text and confidence boxes"""
        texts = []
        boxes = []
        
        for (bbox, text, confidence) in result:
            if confidence > self.confidence_threshold:
                texts.append(text)
                boxes.append({
                    'text': text,
                    'confidence': confidence,
                    'bbox': bbox
                })
        
        return texts, boxes
    
    def _calculate_confidence(self, boxes: List[Dict]) -> float:
        """Calculate average confidence score"""
        if not boxes:
            return 0.0
        
        confidences = [b.get('confidence', 0) for b in boxes]
        return sum(confidences) / len(confidences)
    
    def _extract_structured_data(self, text: str, document_type: str) -> Dict[str, Any]:
        """Extract structured data based on document type using regex patterns"""
        
        if document_type == 'aadhaar':
            return self._extract_aadhaar(text)
        elif document_type == 'pan':
            return self._extract_pan(text)
        elif document_type == 'land_record':
            return self._extract_land_record(text)
        elif document_type == 'bank_passbook':
            return self._extract_bank_details(text)
        elif document_type == 'income_certificate':
            return self._extract_income_certificate(text)
        elif document_type == 'caste_certificate':
            return self._extract_caste_certificate(text)
        elif document_type == 'domicile':
            return self._extract_domicile(text)
        elif document_type == 'crop_insurance':
            return self._extract_crop_insurance(text)
        elif document_type == 'death_certificate':
            return self._extract_death_certificate(text)
        else:
            return {"raw_text": text[:500]}
    
    def _extract_aadhaar(self, text: str) -> Dict[str, Any]:
        """Extract Aadhaar card details using regex"""
        data = {}
        
        # Aadhaar number (12 digits, possibly with spaces)
        aadhaar_pattern = r'\b(\d{4}[-.\s]?\d{4}[-.\s]?\d{4})\b'
        match = re.search(aadhaar_pattern, text)
        if match:
            data['aadhaar_number'] = re.sub(r'\D', '', match.group(1))
        
        # Name (English or Hindi)
        name_patterns = [
            r'(?:Name|नाम)[:\s]*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)',
            r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})'
        ]
        for pattern in name_patterns:
            match = re.search(pattern, text)
            if match:
                data['full_name'] = match.group(1).strip()
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
                break
        
        # Gender
        if re.search(r'\bMale\b|\bपुरुष\b', text, re.I):
            data['gender'] = 'Male'
        elif re.search(r'\bFemale\b|\bमहिला\b', text, re.I):
            data['gender'] = 'Female'
        
        # Address
        address_pattern = r'(?:Address|पता)[:\s]*([^\n]+(?:\n[^\n]+){0,3})'
        match = re.search(address_pattern, text)
        if match:
            data['address'] = match.group(1).strip()
        
        # Mobile number
        mobile_pattern = r'\b(\d{10})\b'
        match = re.search(mobile_pattern, text)
        if match:
            data['mobile_number'] = match.group(1)
        
        return data
    
    def _extract_pan(self, text: str) -> Dict[str, Any]:
        """Extract PAN card details"""
        data = {}
        
        # PAN number (format: ABCDE1234F)
        pan_pattern = r'\b([A-Z]{5}\d{4}[A-Z])\b'
        match = re.search(pan_pattern, text, re.I)
        if match:
            data['pan_number'] = match.group(1).upper()
        
        # Name
        name_patterns = [
            r'(?:Name|नाम)[:\s]*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)',
            r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})'
        ]
        for pattern in name_patterns:
            match = re.search(pattern, text)
            if match:
                data['full_name'] = match.group(1).strip()
                break
        
        # Father's Name
        father_pattern = r'(?:Father|पिता)[:\s]*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)'
        match = re.search(father_pattern, text, re.I)
        if match:
            data['father_name'] = match.group(1).strip()
        
        # Date of Birth
        dob_pattern = r'(\d{2}[/-]\d{2}[/-]\d{4})'
        match = re.search(dob_pattern, text)
        if match:
            data['date_of_birth'] = self._parse_date(match.group(1))
        
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
                else:
                    data['land_area_hectares'] = float(match.group(1))
                break
        
        # Owner name
        owner_patterns = [
            r'(?:मालक|Owner)[:\s]*([\u0900-\u097F\s]+)',
            r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})'
        ]
        for pattern in owner_patterns:
            match = re.search(pattern, text)
            if match:
                data['owner_name'] = match.group(1).strip()
                break
        
        # Village/Taluka/District
        village_pattern = r'(?:गाव|Village)[:\s]*([\u0900-\u097F\s]+)'
        match = re.search(village_pattern, text)
        if match:
            data['village_name'] = match.group(1).strip()
        
        taluka_pattern = r'(?:तालुका|Taluka)[:\s]*([\u0900-\u097F\s]+)'
        match = re.search(taluka_pattern, text)
        if match:
            data['taluka'] = match.group(1).strip()
        
        district_pattern = r'(?:जिल्हा|District)[:\s]*([\u0900-\u097F\s]+)'
        match = re.search(district_pattern, text)
        if match:
            data['district'] = match.group(1).strip()
        
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
                break
        
        # IFSC code
        ifsc_pattern = r'\b([A-Z]{4}0[A-Z0-9]{6})\b'
        match = re.search(ifsc_pattern, text, re.I)
        if match:
            data['ifsc_code'] = match.group(1).upper()
        
        # Bank name
        bank_patterns = [
            r'(?:Bank|बैंक)[:\s]*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)',
            r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3}\s+Bank)'
        ]
        for pattern in bank_patterns:
            match = re.search(pattern, text, re.I)
            if match:
                data['bank_name'] = match.group(1).strip()
                break
        
        # Account holder name
        name_pattern = r'(?:Name|नाम)[:\s]*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)'
        match = re.search(name_pattern, text, re.I)
        if match:
            data['account_holder_name'] = match.group(1).strip()
        
        return data
    
    def _extract_income_certificate(self, text: str) -> Dict[str, Any]:
        """Extract income certificate details"""
        data = {}
        
        # Certificate number
        cert_pattern = r'(?:Certificate|प्रमाणपत्र)[:\s]*([A-Z0-9/_-]+)'
        match = re.search(cert_pattern, text, re.I)
        if match:
            data['certificate_number'] = match.group(1)
        
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
                except:
                    pass
                break
        
        # Issue date
        date_pattern = r'(\d{2}[/-]\d{2}[/-]\d{4})'
        dates = re.findall(date_pattern, text)
        if dates:
            data['issue_date'] = self._parse_date(dates[0])
            if len(dates) > 1:
                data['valid_until'] = self._parse_date(dates[1])
        
        return data
    
    def _extract_caste_certificate(self, text: str) -> Dict[str, Any]:
        """Extract caste certificate details"""
        data = {}
        
        # Certificate number
        cert_pattern = r'(?:Certificate|प्रमाणपत्र)[:\s]*([A-Z0-9/_-]+)'
        match = re.search(cert_pattern, text, re.I)
        if match:
            data['certificate_number'] = match.group(1)
        
        # Caste category
        caste_categories = ['SC', 'ST', 'OBC', 'General', 'अनुसूचित जाती', 'अनुसूचित जमाती', 'इतर मागास वर्ग']
        for category in caste_categories:
            if category in text:
                data['caste_category'] = category
                break
        
        # Name
        name_pattern = r'(?:Name|नाम)[:\s]*([\u0900-\u097F\s]+)'
        match = re.search(name_pattern, text)
        if match:
            data['full_name'] = match.group(1).strip()
        
        return data
    
    def _extract_domicile(self, text: str) -> Dict[str, Any]:
        """Extract domicile certificate details"""
        data = {}
        
        # Certificate number
        cert_pattern = r'(?:Certificate|प्रमाणपत्र)[:\s]*([A-Z0-9/_-]+)'
        match = re.search(cert_pattern, text, re.I)
        if match:
            data['certificate_number'] = match.group(1)
        
        # Name
        name_pattern = r'(?:Name|नाम)[:\s]*([\u0900-\u097F\s]+)'
        match = re.search(name_pattern, text)
        if match:
            data['full_name'] = match.group(1).strip()
        
        # Father's name
        father_pattern = r'(?:Father|पिता)[:\s]*([\u0900-\u097F\s]+)'
        match = re.search(father_pattern, text)
        if match:
            data['father_name'] = match.group(1).strip()
        
        # Address
        address_pattern = r'(?:Address|पता)[:\s]*([^\n]+(?:\n[^\n]+){0,2})'
        match = re.search(address_pattern, text)
        if match:
            data['permanent_address'] = match.group(1).strip()
        
        return data
    
    def _extract_crop_insurance(self, text: str) -> Dict[str, Any]:
        """Extract crop insurance document details"""
        data = {}
        
        # Policy number
        policy_pattern = r'(?:Policy|पॉलिसी)[:\s]*([A-Z0-9/_-]+)'
        match = re.search(policy_pattern, text, re.I)
        if match:
            data['policy_number'] = match.group(1)
        
        # Crop name
        crop_pattern = r'(?:Crop|पीक)[:\s]*([\u0900-\u097F\s]+)'
        match = re.search(crop_pattern, text)
        if match:
            data['crop_name'] = match.group(1).strip()
        
        # Sum insured
        sum_pattern = r'(?:Sum Insured|बीमा रक्कम)[:\s]*[₹Rs.\s]*([\d,]+)'
        match = re.search(sum_pattern, text, re.I)
        if match:
            sum_str = match.group(1).replace(',', '')
            try:
                data['sum_insured'] = float(sum_str)
            except:
                pass
        
        return data
    
    def _extract_death_certificate(self, text: str) -> Dict[str, Any]:
        """Extract death certificate details"""
        data = {}
        
        # Certificate number
        cert_pattern = r'(?:Certificate|प्रमाणपत्र)[:\s]*([A-Z0-9/_-]+)'
        match = re.search(cert_pattern, text, re.I)
        if match:
            data['certificate_number'] = match.group(1)
        
        # Deceased name
        name_pattern = r'(?:Name|नाम)[:\s]*([\u0900-\u097F\s]+)'
        match = re.search(name_pattern, text)
        if match:
            data['deceased_name'] = match.group(1).strip()
        
        # Date of death
        date_pattern = r'(\d{2}[/-]\d{2}[/-]\d{4})'
        match = re.search(date_pattern, text)
        if match:
            data['date_of_death'] = self._parse_date(match.group(1))
        
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
            
            elif key in ['land_area_acres', 'land_area_hectares', 'annual_income', 
                        'sum_insured', 'premium_amount']:
                # Ensure numeric fields are numbers
                try:
                    cleaned[key] = float(value)
                except (ValueError, TypeError):
                    pass
            
            elif key in ['date_of_birth', 'issue_date', 'valid_until', 
                        'date_of_death', 'policy_start_date', 'policy_end_date']:
                # Parse dates
                parsed = self._parse_date(value)
                if parsed:
                    cleaned[key] = parsed
            
            else:
                # Keep other fields as strings
                cleaned[key] = str(value)[:500]  # Limit length
        
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
