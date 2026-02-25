import os
import cv2
import numpy as np
import re
import json
import logging
from typing import Dict, Any, Optional, List, Tuple
from PIL import Image
import io
import base64
from datetime import datetime
import pandas as pd

# OCR Engines
try:
    from paddleocr import PaddleOCR
    PADDLE_AVAILABLE = True
except ImportError:
    PADDLE_AVAILABLE = False
    print("⚠️ PaddleOCR not available")

try:
    import easyocr
    EASYOCR_AVAILABLE = True
except ImportError:
    EASYOCR_AVAILABLE = False
    print("⚠️ EasyOCR not available")

# Layout Parser
try:
    import layoutparser as lp
    LAYOUTPARSER_AVAILABLE = True
except ImportError:
    LAYOUTPARSER_AVAILABLE = False
    print("⚠️ LayoutParser not available")

# Image Processing
from pdf2image import convert_from_bytes
from app.config import settings

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class OCRDocumentProcessor:
    """Process Indian government documents using OCR + Layout Analysis + KIE"""
    
    def __init__(self):
        self.ocr_engine = settings.OCR_ENGINE
        self.use_gpu = settings.OCR_USE_GPU
        self.confidence_threshold = settings.OCR_CONFIDENCE_THRESHOLD
        self.use_layout = settings.USE_LAYOUT_PARSER
        
        # Initialize OCR engines
        self._init_ocr()
        
        # Initialize Layout Parser if available
        if self.use_layout and LAYOUTPARSER_AVAILABLE:
            self._init_layout_parser()
        
        # Document type field mappings
        self.field_mappings = settings.DOCUMENT_FIELD_MAPPINGS
        
        logger.info(f"✅ OCR Processor initialized with engine: {self.ocr_engine}")
    
    def _init_ocr(self):
        """Initialize selected OCR engine"""
        if self.ocr_engine == "paddle" and PADDLE_AVAILABLE:
            try:
                self.paddle_ocr = PaddleOCR(
                    use_angle_cls=True,
                    lang=settings.OCR_LANG,
                    use_gpu=self.use_gpu,
                    show_log=False,
                    rec_algorithm='SVTR_LCNet',
                    det_db_thresh=0.3,
                    det_db_box_thresh=0.5,
                    det_db_unclip_ratio=1.6,
                    max_batch_size=settings.OCR_BATCH_SIZE
                )
                logger.info("✅ PaddleOCR initialized")
            except Exception as e:
                logger.error(f"❌ Failed to initialize PaddleOCR: {e}")
                self.paddle_ocr = None
        
        elif self.ocr_engine == "easyocr" and EASYOCR_AVAILABLE:
            try:
                self.easy_ocr = easyocr.Reader([settings.OCR_LANG], gpu=self.use_gpu)
                logger.info("✅ EasyOCR initialized")
            except Exception as e:
                logger.error(f"❌ Failed to initialize EasyOCR: {e}")
                self.easy_ocr = None
    
    def _init_layout_parser(self):
        """Initialize Layout Parser for document structure analysis"""
        try:
            # Use pre-trained model for document layout analysis
            self.layout_model = lp.Detectron2LayoutModel(
                settings.LAYOUT_MODEL,
                extra_config=[
                    "MODEL.ROI_HEADS.SCORE_THRESH_TEST", 0.5,
                    "MODEL.DEVICE", "cuda" if self.use_gpu else "cpu"
                ],
                label_map={0: "Text", 1: "Title", 2: "List", 3: "Table", 4: "Figure"}
            )
            logger.info("✅ Layout Parser initialized")
        except Exception as e:
            logger.error(f"❌ Failed to initialize Layout Parser: {e}")
            self.use_layout = False
    
    async def process_document(self, 
                               file_bytes: bytes, 
                               file_name: str, 
                               document_type: str,
                               farmer_id: str) -> Dict[str, Any]:
        """
        Extract structured data from any document using OCR + Layout Analysis
        
        Args:
            file_bytes: Raw file bytes
            file_name: Original file name
            document_type: Type of document (aadhaar, pan, etc.)
            farmer_id: Farmer ID
            
        Returns:
            Dictionary with extracted data
        """
        try:
            logger.info(f"🔍 Processing {document_type} document for farmer {farmer_id}")
            
            # Convert to image if PDF
            image = await self._convert_to_image(file_bytes, file_name)
            if image is None:
                return {"success": False, "error": "Failed to convert document to image"}
            
            # Step 1: Layout Analysis (if enabled)
            layout_results = None
            if self.use_layout:
                layout_results = self._analyze_layout(image)
            
            # Step 2: OCR Processing
            ocr_results = await self._perform_ocr(image)
            
            # Step 3: Extract structured data based on document type
            extracted_data = self._extract_structured_data(
                ocr_results, 
                document_type,
                layout_results
            )
            
            # Step 4: Post-process and validate
            cleaned_data = self._validate_and_clean(extracted_data, document_type)
            
            # Add metadata
            cleaned_data['farmer_id'] = farmer_id
            cleaned_data['processed_at'] = datetime.now().isoformat()
            cleaned_data['ocr_engine'] = self.ocr_engine
            cleaned_data['confidence_score'] = self._calculate_confidence(extracted_data, document_type)
            
            logger.info(f"✅ Successfully extracted data from {document_type}")
            
            return {
                "success": True,
                "table_name": settings.DOCUMENT_TABLE_MAP.get(document_type, 'documents'),
                "extracted_data": cleaned_data,
                "confidence": cleaned_data['confidence_score'],
                "ocr_text": ocr_results.get('full_text', '')[:500]  # Store preview
            }
            
        except Exception as e:
            logger.error(f"❌ OCR processing error for {document_type}: {str(e)}")
            import traceback
            traceback.print_exc()
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _convert_to_image(self, file_bytes: bytes, file_name: str) -> Optional[np.ndarray]:
        """Convert PDF or image to numpy array for processing"""
        try:
            if file_name.lower().endswith('.pdf'):
                # Convert PDF to image
                images = convert_from_bytes(file_bytes, first_page=1, last_page=1)
                if not images:
                    return None
                # Convert PIL to numpy array
                return cv2.cvtColor(np.array(images[0]), cv2.COLOR_RGB2BGR)
            else:
                # Read image bytes
                nparr = np.frombuffer(file_bytes, np.uint8)
                return cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        except Exception as e:
            logger.error(f"❌ Image conversion error: {e}")
            return None
    
    def _analyze_layout(self, image: np.ndarray) -> Dict:
        """Analyze document layout to identify text regions"""
        if not self.use_layout:
            return {}
        
        try:
            # Convert to RGB for layout parser
            image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            
            # Detect layout
            layout = self.layout_model.detect(image_rgb)
            
            # Organize by type
            text_blocks = []
            title_blocks = []
            table_blocks = []
            
            for block in layout:
                if block.type == 'Text':
                    text_blocks.append(block)
                elif block.type == 'Title':
                    title_blocks.append(block)
                elif block.type == 'Table':
                    table_blocks.append(block)
            
            return {
                'text_regions': [b.block.coordinates for b in text_blocks],
                'title_regions': [b.block.coordinates for b in title_blocks],
                'table_regions': [b.block.coordinates for b in table_blocks]
            }
        except Exception as e:
            logger.error(f"❌ Layout analysis error: {e}")
            return {}
    
    async def _perform_ocr(self, image: np.ndarray) -> Dict[str, Any]:
        """Perform OCR based on selected engine"""
        results = {
            'full_text': '',
            'text_blocks': [],
            'words': [],
            'confidences': []
        }
        
        try:
            if self.ocr_engine == "paddle" and self.paddle_ocr:
                # PaddleOCR returns [boxes, text, confidence]
                paddle_result = self.paddle_ocr.ocr(image, cls=True)
                
                if paddle_result and paddle_result[0]:
                    full_text_parts = []
                    for line in paddle_result[0]:
                        if len(line) >= 2:
                            box, (text, confidence) = line[0], line[1]
                            if confidence >= self.confidence_threshold:
                                full_text_parts.append(text)
                                results['words'].append({
                                    'text': text,
                                    'confidence': confidence,
                                    'bbox': box
                                })
                                results['confidences'].append(confidence)
                    
                    results['full_text'] = ' '.join(full_text_parts)
            
            elif self.ocr_engine == "easyocr" and self.easy_ocr:
                # EasyOCR returns [bbox, text, confidence]
                easy_result = self.easy_ocr.readtext(image)
                
                for (bbox, text, confidence) in easy_result:
                    if confidence >= self.confidence_threshold:
                        results['words'].append({
                            'text': text,
                            'confidence': confidence,
                            'bbox': bbox
                        })
                        results['confidences'].append(confidence)
                
                results['full_text'] = ' '.join([w['text'] for w in results['words']])
            
            else:
                # Fallback to simple message
                results['full_text'] = "OCR engine not available"
            
            logger.info(f"✅ OCR completed: extracted {len(results['words'])} words")
            
        except Exception as e:
            logger.error(f"❌ OCR execution error: {e}")
            results['error'] = str(e)
        
        return results
    
    def _extract_structured_data(self, 
                                 ocr_results: Dict, 
                                 document_type: str,
                                 layout_results: Dict = None) -> Dict[str, Any]:
        """Extract structured data from OCR results based on document type"""
        
        full_text = ocr_results.get('full_text', '')
        words = ocr_results.get('words', [])
        
        extracted = {}
        
        # Document-specific extraction
        if document_type == 'aadhaar':
            extracted = self._extract_aadhaar(full_text, words)
        elif document_type == 'pan':
            extracted = self._extract_pan(full_text, words)
        elif document_type == 'land_record':
            extracted = self._extract_land_record(full_text, words)
        elif document_type == 'bank_passbook':
            extracted = self._extract_bank_passbook(full_text, words)
        elif document_type == 'income_certificate':
            extracted = self._extract_income_certificate(full_text, words)
        elif document_type == 'caste_certificate':
            extracted = self._extract_caste_certificate(full_text, words)
        elif document_type == 'domicile':
            extracted = self._extract_domicile(full_text, words)
        elif document_type == 'crop_insurance':
            extracted = self._extract_crop_insurance(full_text, words)
        elif document_type == 'death_certificate':
            extracted = self._extract_death_certificate(full_text, words)
        
        # Add layout info if available
        if layout_results:
            extracted['_layout_info'] = {
                'has_tables': len(layout_results.get('table_regions', [])) > 0,
                'text_region_count': len(layout_results.get('text_regions', []))
            }
        
        return extracted
    
    def _extract_aadhaar(self, text: str, words: List) -> Dict:
        """Extract Aadhaar card data"""
        extracted = {}
        
        # Extract Aadhaar number (12 digits, possibly with spaces)
        aadhaar_pattern = r'(\d{4}\s?\d{4}\s?\d{4})'
        aadhaar_match = re.search(aadhaar_pattern, text)
        if aadhaar_match:
            aadhaar = re.sub(r'\s', '', aadhaar_match.group(1))
            extracted['aadhaar_number'] = aadhaar
        
        # Extract date of birth
        dob_patterns = [
            r'DOB\s*:?\s*(\d{2}[/-]\d{2}[/-]\d{4})',
            r'Birth\s*:?\s*(\d{2}[/-]\d{2}[/-]\d{4})',
            r'(\d{2}[/-]\d{2}[/-]\d{4})'
        ]
        for pattern in dob_patterns:
            dob_match = re.search(pattern, text, re.IGNORECASE)
            if dob_match:
                extracted['date_of_birth'] = self._parse_date(dob_match.group(1))
                break
        
        # Extract gender
        if re.search(r'Male|MALE|male', text):
            extracted['gender'] = 'Male'
        elif re.search(r'Female|FEMALE|female', text):
            extracted['gender'] = 'Female'
        elif re.search(r'Trans|TRANS|trans', text):
            extracted['gender'] = 'Transgender'
        
        # Extract name (usually before DOB or in specific format)
        lines = text.split('\n')
        for i, line in enumerate(lines):
            line = line.strip()
            if line and len(line) > 5 and i < len(lines)-1:
                next_line = lines[i+1] if i+1 < len(lines) else ""
                # Check if next line contains DOB or year
                if re.search(r'\d{4}', next_line) and not re.search(r'[0-9]', line):
                    extracted['full_name'] = line.strip()
                    break
        
        # Extract address
        address_lines = []
        in_address = False
        for line in lines:
            if re.search(r'Address|Add|ADDR', line, re.IGNORECASE):
                in_address = True
                continue
            if in_address and line.strip():
                if re.search(r'Pin|Pincode|P\.?O\.?', line, re.IGNORECASE):
                    break
                address_lines.append(line.strip())
        
        if address_lines:
            extracted['address'] = ' '.join(address_lines)
        
        # Extract pincode
        pincode_pattern = r'(\d{6})'
        pincode_match = re.search(pincode_pattern, text)
        if pincode_match:
            extracted['pincode'] = pincode_match.group(1)
        
        # Extract mobile
        mobile_pattern = r'Mobile|Mob|Phone.*?(\d{10})'
        mobile_match = re.search(mobile_pattern, text, re.IGNORECASE)
        if mobile_match:
            extracted['mobile_number'] = mobile_match.group(1)
        
        # Extract father's name
        father_patterns = [
            r'Father|FATHER.*?[:\s]+([A-Za-z\s]+)',
            r'S/O|S\.O\.|W/O.*?[:\s]+([A-Za-z\s]+)'
        ]
        for pattern in father_patterns:
            father_match = re.search(pattern, text, re.IGNORECASE)
            if father_match:
                extracted['father_name'] = father_match.group(1).strip()
                break
        
        return extracted
    
    def _extract_pan(self, text: str, words: List) -> Dict:
        """Extract PAN card data"""
        extracted = {}
        
        # Extract PAN number (format: ABCDE1234F)
        pan_pattern = r'[A-Z]{5}[0-9]{4}[A-Z]{1}'
        pan_match = re.search(pan_pattern, text)
        if pan_match:
            extracted['pan_number'] = pan_match.group(0)
        
        # Extract name (usually capitalized, multiple words)
        lines = text.split('\n')
        for line in lines:
            line = line.strip()
            # Look for name lines (all caps, not containing PAN or Income Tax)
            if line and line.isupper() and len(line.split()) >= 2:
                if not re.search(r'INCOME|TAX|PAN|GOVT|INDIA', line):
                    extracted['full_name'] = line
                    break
        
        # Extract father's name
        for line in lines:
            if re.search(r"Father|FATHER|S/O|S\.O\.", line, re.IGNORECASE):
                father_name = re.sub(r"Father|FATHER|S/O|S\.O\.|:", "", line, flags=re.IGNORECASE).strip()
                if father_name:
                    extracted['father_name'] = father_name
                    break
        
        # Extract date of birth
        dob_pattern = r'(\d{2}[/-]\d{2}[/-]\d{4})'
        dob_match = re.search(dob_pattern, text)
        if dob_match:
            extracted['date_of_birth'] = self._parse_date(dob_match.group(1))
        
        # Determine PAN type
        if 'individual' in text.lower():
            extracted['pan_type'] = 'Individual'
        elif 'company' in text.lower():
            extracted['pan_type'] = 'Company'
        elif 'trust' in text.lower():
            extracted['pan_type'] = 'Trust'
        
        return extracted
    
    def _extract_land_record(self, text: str, words: List) -> Dict:
        """Extract land record (7/12, 8A) data"""
        extracted = {}
        
        # Extract survey number
        survey_patterns = [
            r'Survey\s*No\.?\s*:?\s*([A-Z0-9/\-]+)',
            r'S\.No\.?\s*:?\s*([A-Z0-9/\-]+)',
            r'Gat\s*No\.?\s*:?\s*([0-9]+)',
            r'Plot\s*No\.?\s*:?\s*([0-9]+)'
        ]
        for pattern in survey_patterns:
            survey_match = re.search(pattern, text, re.IGNORECASE)
            if survey_match:
                extracted['survey_number'] = survey_match.group(1).strip()
                break
        
        # Extract land area
        area_patterns = [
            r'Area\s*:?\s*([0-9.]+)\s*(?:Hector|Hec|Ha|Acres?)',
            r'([0-9.]+)\s*(?:Hector|Hec|Ha)',
            r'([0-9.]+)\s*(?:Acres?|Acre)'
        ]
        for pattern in area_patterns:
            area_match = re.search(pattern, text, re.IGNORECASE)
            if area_match:
                area_value = float(area_match.group(1)) if '.' in area_match.group(1) else int(area_match.group(1))
                if 'acre' in pattern.lower() or 'acre' in text[area_match.end():area_match.end()+10].lower():
                    extracted['land_area_acres'] = area_value
                    extracted['land_area_hectares'] = area_value * 0.4047
                else:
                    extracted['land_area_hectares'] = area_value
                    extracted['land_area_acres'] = area_value * 2.471
                break
        
        # Extract owner name
        owner_patterns = [
            r'Owner\s*:?\s*([A-Za-z\s]+)',
            r'Name of\s*owner\s*:?\s*([A-Za-z\s]+)',
            r'Occupant\s*:?\s*([A-Za-z\s]+)'
        ]
        for pattern in owner_patterns:
            owner_match = re.search(pattern, text, re.IGNORECASE)
            if owner_match:
                extracted['owner_name'] = owner_match.group(1).strip()
                break
        
        # Extract village
        village_patterns = [
            r'Village\s*:?\s*([A-Za-z\s]+)',
            r'Gram\s*:?\s*([A-Za-z\s]+)'
        ]
        for pattern in village_patterns:
            village_match = re.search(pattern, text, re.IGNORECASE)
            if village_match:
                extracted['village_name'] = village_match.group(1).strip()
                break
        
        # Extract taluka
        taluka_pattern = r'Taluka|Tehsil|Taluk\s*:?\s*([A-Za-z\s]+)'
        taluka_match = re.search(taluka_pattern, text, re.IGNORECASE)
        if taluka_match:
            extracted['taluka'] = taluka_match.group(1).strip()
        
        # Extract district
        district_pattern = r'District|Dist\.?\s*:?\s*([A-Za-z\s]+)'
        district_match = re.search(district_pattern, text, re.IGNORECASE)
        if district_match:
            extracted['district'] = district_match.group(1).strip()
        
        # Extract state
        state_pattern = r'State\s*:?\s*([A-Za-z\s]+)'
        state_match = re.search(state_pattern, text, re.IGNORECASE)
        if state_match:
            extracted['state'] = state_match.group(1).strip()
        
        return extracted
    
    def _extract_bank_passbook(self, text: str, words: List) -> Dict:
        """Extract bank passbook data"""
        extracted = {}
        
        # Extract account number (usually 9-18 digits)
        account_pattern = r'A/C\s*No\.?\s*:?\s*([0-9]{9,18})'
        account_match = re.search(account_pattern, text, re.IGNORECASE)
        if account_match:
            extracted['account_number'] = account_match.group(1)
        else:
            # Try to find long number sequences
            numbers = re.findall(r'\b([0-9]{9,18})\b', text)
            if numbers:
                extracted['account_number'] = numbers[0]
        
        # Extract IFSC code (format: ABCD0123456)
        ifsc_pattern = r'[A-Z]{4}0[A-Z0-9]{6}'
        ifsc_match = re.search(ifsc_pattern, text)
        if ifsc_match:
            extracted['ifsc_code'] = ifsc_match.group(0)
        
        # Extract bank name
        bank_names = ['State Bank of India', 'SBI', 'Bank of India', 'Bank of Baroda', 
                     'Punjab National Bank', 'PNB', 'Canara Bank', 'HDFC', 'ICICI']
        for bank in bank_names:
            if bank in text:
                extracted['bank_name'] = bank
                break
        
        # Extract account holder name
        name_patterns = [
            r'Name\s*:?\s*([A-Za-z\s]+)',
            r'Account\s*Holder\s*:?\s*([A-Za-z\s]+)'
        ]
        for pattern in name_patterns:
            name_match = re.search(pattern, text, re.IGNORECASE)
            if name_match:
                extracted['account_holder_name'] = name_match.group(1).strip()
                break
        
        # Extract account type
        if 'savings' in text.lower():
            extracted['account_type'] = 'Savings'
        elif 'current' in text.lower():
            extracted['account_type'] = 'Current'
        elif 'salary' in text.lower():
            extracted['account_type'] = 'Salary'
        
        return extracted
    
    def _extract_income_certificate(self, text: str, words: List) -> Dict:
        """Extract income certificate data"""
        extracted = {}
        
        # Extract certificate number
        cert_pattern = r'Certificate\s*No\.?\s*:?\s*([A-Z0-9/\-]+)'
        cert_match = re.search(cert_pattern, text, re.IGNORECASE)
        if cert_match:
            extracted['certificate_number'] = cert_match.group(1).strip()
        
        # Extract annual income
        income_patterns = [
            r'Annual\s*Income\s*:?\s*Rs\.?\s*([0-9,]+)',
            r'Income\s*:?\s*Rs\.?\s*([0-9,]+)',
            r'([0-9,]+)\s*(?:Rs\.?|Rupees?)'
        ]
        for pattern in income_patterns:
            income_match = re.search(pattern, text, re.IGNORECASE)
            if income_match:
                income_str = income_match.group(1).replace(',', '')
                try:
                    extracted['annual_income'] = float(income_str)
                except:
                    pass
                break
        
        # Extract issue date
        issue_patterns = [
            r'Issue\s*Date\s*:?\s*(\d{2}[/-]\d{2}[/-]\d{4})',
            r'Date\s*of\s*Issue\s*:?\s*(\d{2}[/-]\d{2}[/-]\d{4})'
        ]
        for pattern in issue_patterns:
            issue_match = re.search(pattern, text, re.IGNORECASE)
            if issue_match:
                extracted['issue_date'] = self._parse_date(issue_match.group(1))
                break
        
        # Extract issuing authority
        authority_pattern = r'Issuing\s*Authority\s*:?\s*([A-Za-z\s]+)'
        authority_match = re.search(authority_pattern, text, re.IGNORECASE)
        if authority_match:
            extracted['issuing_authority'] = authority_match.group(1).strip()
        
        return extracted
    
    def _extract_caste_certificate(self, text: str, words: List) -> Dict:
        """Extract caste certificate data"""
        extracted = {}
        
        # Extract certificate number
        cert_pattern = r'Certificate\s*No\.?\s*:?\s*([A-Z0-9/\-]+)'
        cert_match = re.search(cert_pattern, text, re.IGNORECASE)
        if cert_match:
            extracted['certificate_number'] = cert_match.group(1).strip()
        
        # Extract caste category
        categories = ['SC', 'ST', 'OBC', 'General', 'NT', 'VJNT', 'SBC']
        for cat in categories:
            if cat in text.upper():
                extracted['caste_category'] = cat
                break
        
        # Extract caste name
        caste_pattern = r'Caste\s*:?\s*([A-Za-z\s]+)'
        caste_match = re.search(caste_pattern, text, re.IGNORECASE)
        if caste_match:
            extracted['caste_name'] = caste_match.group(1).strip()
        
        # Extract issue date
        issue_pattern = r'Date\s*:?\s*(\d{2}[/-]\d{2}[/-]\d{4})'
        issue_match = re.search(issue_pattern, text, re.IGNORECASE)
        if issue_match:
            extracted['issue_date'] = self._parse_date(issue_match.group(1))
        
        return extracted
    
    def _extract_domicile(self, text: str, words: List) -> Dict:
        """Extract domicile certificate data"""
        extracted = {}
        
        # Extract certificate number
        cert_pattern = r'Certificate\s*No\.?\s*:?\s*([A-Z0-9/\-]+)'
        cert_match = re.search(cert_pattern, text, re.IGNORECASE)
        if cert_match:
            extracted['certificate_number'] = cert_match.group(1).strip()
        
        # Extract name
        name_patterns = [
            r'Name\s*:?\s*([A-Za-z\s]+)',
            r'Shri|Smt\.?\s*([A-Za-z\s]+)'
        ]
        for pattern in name_patterns:
            name_match = re.search(pattern, text, re.IGNORECASE)
            if name_match:
                extracted['full_name'] = name_match.group(1).strip()
                break
        
        # Extract father's name
        father_pattern = r'S/O|W/O|D/O\s*:?\s*([A-Za-z\s]+)'
        father_match = re.search(father_pattern, text, re.IGNORECASE)
        if father_match:
            extracted['father_name'] = father_match.group(1).strip()
        
        # Extract address
        address_pattern = r'Address|Resident\s*:?\s*([A-Za-z0-9\s,.-]+)'
        address_match = re.search(address_pattern, text, re.IGNORECASE)
        if address_match:
            extracted['permanent_address'] = address_match.group(1).strip()
        
        # Extract district
        district_pattern = r'District\s*:?\s*([A-Za-z\s]+)'
        district_match = re.search(district_pattern, text, re.IGNORECASE)
        if district_match:
            extracted['district'] = district_match.group(1).strip()
        
        return extracted
    
    def _extract_crop_insurance(self, text: str, words: List) -> Dict:
        """Extract crop insurance document data"""
        extracted = {}
        
        # Extract policy number
        policy_pattern = r'Policy\s*No\.?\s*:?\s*([A-Z0-9/\-]+)'
        policy_match = re.search(policy_pattern, text, re.IGNORECASE)
        if policy_match:
            extracted['policy_number'] = policy_match.group(1).strip()
        
        # Extract crop name
        crop_pattern = r'Crop\s*:?\s*([A-Za-z\s]+)'
        crop_match = re.search(crop_pattern, text, re.IGNORECASE)
        if crop_match:
            extracted['crop_name'] = crop_match.group(1).strip()
        
        # Extract sum insured
        sum_pattern = r'Sum\s*Insured\s*:?\s*Rs\.?\s*([0-9,]+)'
        sum_match = re.search(sum_pattern, text, re.IGNORECASE)
        if sum_match:
            sum_str = sum_match.group(1).replace(',', '')
            try:
                extracted['sum_insured'] = float(sum_str)
            except:
                pass
        
        # Extract dates
        date_pattern = r'(\d{2}[/-]\d{2}[/-]\d{4})'
        dates = re.findall(date_pattern, text)
        if len(dates) >= 2:
            extracted['policy_start_date'] = self._parse_date(dates[0])
            extracted['policy_end_date'] = self._parse_date(dates[1])
        
        return extracted
    
    def _extract_death_certificate(self, text: str, words: List) -> Dict:
        """Extract death certificate data"""
        extracted = {}
        
        # Extract deceased name
        name_patterns = [
            r'Name\s*of\s*Deceased\s*:?\s*([A-Za-z\s]+)',
            r'Deceased\s*Name\s*:?\s*([A-Za-z\s]+)'
        ]
        for pattern in name_patterns:
            name_match = re.search(pattern, text, re.IGNORECASE)
            if name_match:
                extracted['deceased_name'] = name_match.group(1).strip()
                break
        
        # Extract date of death
        death_pattern = r'Date\s*of\s*Death\s*:?\s*(\d{2}[/-]\d{2}[/-]\d{4})'
        death_match = re.search(death_pattern, text, re.IGNORECASE)
        if death_match:
            extracted['date_of_death'] = self._parse_date(death_match.group(1))
        
        # Extract certificate number
        cert_pattern = r'Certificate\s*No\.?\s*:?\s*([A-Z0-9/\-]+)'
        cert_match = re.search(cert_pattern, text, re.IGNORECASE)
        if cert_match:
            extracted['certificate_number'] = cert_match.group(1).strip()
        
        # Extract place of death
        place_pattern = r'Place\s*of\s*Death\s*:?\s*([A-Za-z\s,.-]+)'
        place_match = re.search(place_pattern, text, re.IGNORECASE)
        if place_match:
            extracted['place_of_death'] = place_match.group(1).strip()
        
        return extracted
    
    def _validate_and_clean(self, data: Dict[str, Any], document_type: str) -> Dict[str, Any]:
        """Validate and clean data based on document type"""
        cleaned = {}
        
        # Get field mappings for document type
        mappings = self.field_mappings.get(document_type, {})
        required_fields = mappings.get('required', [])
        optional_fields = mappings.get('optional', [])
        patterns = mappings.get('patterns', {})
        
        # Clean based on document type
        if document_type == 'aadhaar':
            # Clean Aadhaar number
            if 'aadhaar_number' in data:
                aadhaar = re.sub(r'\D', '', str(data['aadhaar_number']))
                if len(aadhaar) == 12:
                    cleaned['aadhaar_number'] = aadhaar
            
            # Clean date
            if 'date_of_birth' in data:
                cleaned['date_of_birth'] = self._parse_date(data['date_of_birth'])
            
            # Clean pincode
            if 'pincode' in data:
                pincode = re.sub(r'\D', '', str(data['pincode']))
                if len(pincode) == 6:
                    cleaned['pincode'] = pincode
            
            # Pass through other fields
            for field in required_fields + optional_fields:
                if field in data and field not in cleaned:
                    cleaned[field] = str(data[field])[:200]
        
        elif document_type == 'pan':
            if 'pan_number' in data:
                pan = re.sub(r'[^A-Z0-9]', '', str(data['pan_number']).upper())
                cleaned['pan_number'] = pan
            if 'date_of_birth' in data:
                cleaned['date_of_birth'] = self._parse_date(data['date_of_birth'])
            for field in required_fields + optional_fields:
                if field in data and field not in cleaned:
                    cleaned[field] = str(data[field])[:200]
        
        elif document_type == 'bank_passbook':
            if 'ifsc_code' in data:
                ifsc = re.sub(r'[^A-Z0-9]', '', str(data['ifsc_code']).upper())
                cleaned['ifsc_code'] = ifsc
            if 'account_number' in data:
                acc = re.sub(r'\D', '', str(data['account_number']))
                cleaned['account_number'] = acc
            for field in required_fields + optional_fields:
                if field in data and field not in cleaned:
                    cleaned[field] = str(data[field])[:200]
        
        elif document_type == 'land_record':
            for num_field in ['land_area_acres', 'land_area_hectares', 'land_value']:
                if num_field in data:
                    try:
                        cleaned[num_field] = float(data[num_field])
                    except:
                        cleaned[num_field] = 0.0
            for field in required_fields + optional_fields:
                if field in data and field not in cleaned:
                    cleaned[field] = str(data[field])[:200]
        
        elif document_type in ['income_certificate', 'caste_certificate', 'domicile']:
            if 'annual_income' in data:
                try:
                    cleaned['annual_income'] = float(data['annual_income'])
                except:
                    cleaned['annual_income'] = 0.0
            for date_field in ['issue_date', 'valid_until', 'date_of_death']:
                if date_field in data:
                    cleaned[date_field] = self._parse_date(data[date_field])
            for field in required_fields + optional_fields:
                if field in data and field not in cleaned:
                    cleaned[field] = str(data[field])[:500]
        
        elif document_type == 'crop_insurance':
            for num_field in ['land_area_insured', 'sum_insured', 'premium_amount']:
                if num_field in data:
                    try:
                        cleaned[num_field] = float(data[num_field])
                    except:
                        cleaned[num_field] = 0.0
            for date_field in ['policy_start_date', 'policy_end_date']:
                if date_field in data:
                    cleaned[date_field] = self._parse_date(data[date_field])
            for field in required_fields + optional_fields:
                if field in data and field not in cleaned:
                    cleaned[field] = str(data[field])[:200]
        
        return cleaned
    
    def _parse_date(self, date_str: str) -> Optional[str]:
        """Parse various date formats to YYYY-MM-DD"""
        if not date_str or date_str == 'null' or date_str == 'None':
            return None
        
        date_str = str(date_str).strip()
        
        # Try common patterns
        patterns = [
            (r'(\d{4})[-\/](\d{2})[-\/](\d{2})', 'ymd'),  # YYYY-MM-DD
            (r'(\d{2})[-\/](\d{2})[-\/](\d{4})', 'dmy'),  # DD-MM-YYYY
            (r'(\d{2})[-\/](\d{2})[-\/](\d{2})', 'dmyy'), # DD-MM-YY
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
        
        # If no pattern matches, return as is (first 10 chars)
        return date_str[:10]
    
    def _calculate_confidence(self, data: Dict, document_type: str) -> float:
        """Calculate overall confidence score for extraction"""
        if not data:
            return 0.0
        
        mappings = self.field_mappings.get(document_type, {})
        required_fields = mappings.get('required', [])
        
        if not required_fields:
            return 0.8  # Default confidence
        
        # Count how many required fields were extracted
        found_fields = sum(1 for field in required_fields if field in data and data[field])
        confidence = (found_fields / len(required_fields)) * 100
        
        return min(confidence, 100)  # Cap at 100
