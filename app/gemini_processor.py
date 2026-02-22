# app/gemini_processor.py - UPDATED TO USE CONFIG

import os
import google.generativeai as genai
from PIL import Image
import io
import json
from typing import Dict, Any, Optional
import base64
from pdf2image import convert_from_bytes
import re
from datetime import datetime
from app.config import settings  # ✅ Import settings

# Configure Gemini using settings
GEMINI_API_KEY = settings.GEMINI_API_KEY
GEMINI_MODEL = settings.GEMINI_MODEL

if not GEMINI_API_KEY:
    print("⚠️ WARNING: GEMINI_API_KEY not set in environment variables")
    print("Please add GEMINI_API_KEY to your Render environment variables")
else:
    print(f"✅ Gemini AI configured with model: {GEMINI_MODEL}")
    
genai.configure(api_key=GEMINI_API_KEY)

class GeminiDocumentProcessor:
    """Process Indian government documents using Gemini AI"""
    
    def __init__(self, model_name=None):
        # Use model from settings or default
        self.model_name = model_name or GEMINI_MODEL
        self.model = genai.GenerativeModel(self.model_name)
        
        # Use document table map from settings
        self.doc_table_map = settings.DOCUMENT_TABLE_MAP
    
    async def process_document(self, 
                               file_bytes: bytes, 
                               file_name: str, 
                               document_type: str,
                               farmer_id: str) -> Dict[str, Any]:
        """
        Extract structured data from any document using Gemini
        """
        try:
            print(f"🔍 Processing {document_type} document for farmer {farmer_id}")
            
            # Convert to image if PDF
            if file_name.lower().endswith('.pdf'):
                try:
                    images = convert_from_bytes(file_bytes, first_page=1, last_page=1)
                    if not images:
                        return {"success": False, "error": "Could not convert PDF to image"}
                    image = images[0]
                    img_byte_arr = io.BytesIO()
                    image.save(img_byte_arr, format='PNG')
                    image_data = img_byte_arr.getvalue()
                    mime_type = "image/png"
                except Exception as pdf_error:
                    print(f"❌ PDF conversion error: {pdf_error}")
                    return {"success": False, "error": f"PDF conversion failed: {str(pdf_error)}"}
            else:
                image_data = file_bytes
                mime_type = "image/jpeg" if file_name.lower().endswith(('.jpg', '.jpeg')) else "image/png"
            
            # Get extraction prompt for document type
            prompt = self._get_extraction_prompt(document_type)
            
            # Prepare content for Gemini
            image_part = {
                "mime_type": mime_type,
                "data": base64.b64encode(image_data).decode('utf-8')
            }
            
            # Call Gemini API
            print("📡 Calling Gemini API...")
            response = self.model.generate_content([prompt, image_part])
            
            # Parse JSON response
            extracted_data = self._parse_response(response.text, document_type)
            
            # Validate and clean data
            cleaned_data = self._validate_and_clean(extracted_data, document_type)
            
            # Add metadata
            cleaned_data['farmer_id'] = farmer_id
            cleaned_data['processed_at'] = datetime.now().isoformat()
            
            print(f"✅ Successfully extracted data from {document_type}")
            
            return {
                "success": True,
                "table_name": self.doc_table_map.get(document_type, 'documents'),
                "extracted_data": cleaned_data,
                "confidence": 0.95
            }
            
        except Exception as e:
            print(f"❌ Gemini processing error for {document_type}: {str(e)}")
            import traceback
            traceback.print_exc()
            return {
                "success": False,
                "error": str(e)
            }
    
    def _get_extraction_prompt(self, document_type: str) -> str:
        """Get extraction prompt for each document type"""
        
        base_instruction = """
        You are an expert at extracting information from Indian government documents.
        Extract the requested fields and return ONLY a valid JSON object.
        Do not include any explanations, markdown, or additional text.
        Use YYYY-MM-DD format for dates.
        If a field is not found, use null or omit it.
        """
        
        prompts = {
            'aadhaar': base_instruction + """
            Extract from this Aadhaar card:
            - aadhaar_number: 12-digit number (remove spaces)
            - full_name: Name as printed
            - date_of_birth: In YYYY-MM-DD format
            - gender: Male/Female/Transgender
            - address: Complete address
            - pincode: 6-digit PIN
            - father_name: Father's name if present
            - mobile_number: Linked mobile if present
            - email: Email if present
            
            Example:
            {
                "aadhaar_number": "123456789012",
                "full_name": "Rajesh Kumar",
                "date_of_birth": "1990-08-15",
                "gender": "Male",
                "address": "123 Main Street, Village, District, State",
                "pincode": "400001",
                "father_name": "Suresh Kumar",
                "mobile_number": "9876543210"
            }
            """,
            
            'pan': base_instruction + """
            Extract from this PAN card:
            - pan_number: 10-character PAN (format: ABCDE1234F)
            - full_name: Name as printed
            - father_name: Father's name
            - date_of_birth: In YYYY-MM-DD format
            - pan_type: Individual/Company/Trust
            
            Example:
            {
                "pan_number": "ABCDE1234F",
                "full_name": "Rajesh Kumar",
                "father_name": "Suresh Kumar",
                "date_of_birth": "1990-08-15",
                "pan_type": "Individual"
            }
            """,
            
            'land_record': base_instruction + """
            Extract from this land record (7/12, 8A):
            - survey_number: Land survey number
            - land_area_acres: Area in acres (number)
            - land_area_hectares: Area in hectares (number)
            - land_type: irrigated/rainfed/barren/forest
            - owner_name: Primary owner name
            - co_owners: Comma-separated list of co-owners
            - village_name: Village name
            - taluka: Taluka/Tehsil name
            - district: District name
            - state: State name
            - land_value: Estimated value if available
            - crop_pattern: Crops grown
            - irrigation_source: Source of irrigation
            
            Example:
            {
                "survey_number": "123/A",
                "land_area_acres": 5.5,
                "land_area_hectares": 2.23,
                "land_type": "irrigated",
                "owner_name": "Rajesh Kumar",
                "co_owners": "Suresh Kumar, Anita Kumar",
                "village_name": "Dindori",
                "taluka": "Dindori",
                "district": "Nashik",
                "state": "Maharashtra",
                "land_value": 2500000,
                "crop_pattern": "Sugarcane, Wheat",
                "irrigation_source": "Canal"
            }
            """,
            
            'bank_passbook': base_instruction + """
            Extract from this bank passbook:
            - account_number: Bank account number
            - ifsc_code: 11-character IFSC code
            - bank_name: Bank name
            - branch_name: Branch name
            - account_holder_name: Name on account
            - account_type: Savings/Current
            - micr_code: 9-digit MICR code if visible
            
            Example:
            {
                "account_number": "12345678901",
                "ifsc_code": "SBIN0001234",
                "bank_name": "State Bank of India",
                "branch_name": "Main Branch",
                "account_holder_name": "Rajesh Kumar",
                "account_type": "Savings",
                "micr_code": "400002123"
            }
            """,
            
            'income_certificate': base_instruction + """
            Extract from this income certificate:
            - certificate_number: Certificate number
            - issue_date: Date of issue (YYYY-MM-DD)
            - valid_until: Validity date (YYYY-MM-DD)
            - annual_income: Annual income in rupees
            - income_source: Source of income
            - issuing_authority: Authority that issued
            - district: District name
            
            Example:
            {
                "certificate_number": "INC/2024/12345",
                "issue_date": "2024-01-15",
                "valid_until": "2025-01-14",
                "annual_income": 150000,
                "income_source": "Agriculture",
                "issuing_authority": "Tehsildar Office",
                "district": "Nashik"
            }
            """,
            
            'caste_certificate': base_instruction + """
            Extract from this caste certificate:
            - certificate_number: Certificate number
            - caste_category: SC/ST/OBC/General
            - caste_name: Specific caste name
            - issue_date: Date of issue (YYYY-MM-DD)
            - valid_until: Validity date (YYYY-MM-DD)
            - issuing_authority: Authority that issued
            - district: District name
            - full_name: Name of beneficiary
            - father_name: Father's name
            
            Example:
            {
                "certificate_number": "CST/2024/5678",
                "caste_category": "OBC",
                "caste_name": "Kunbi",
                "issue_date": "2024-02-10",
                "valid_until": "2029-02-09",
                "issuing_authority": "Tehsildar Office",
                "district": "Nashik",
                "full_name": "Rajesh Kumar",
                "father_name": "Suresh Kumar"
            }
            """,
            
            'domicile': base_instruction + """
            Extract from this domicile certificate:
            - certificate_number: Certificate number
            - full_name: Name of person
            - father_name: Father's name
            - permanent_address: Complete address
            - district: District name
            - state: State name
            - issue_date: Date of issue (YYYY-MM-DD)
            - valid_until: Validity date (YYYY-MM-DD)
            - issuing_authority: Authority that issued
            
            Example:
            {
                "certificate_number": "DOM/2024/9876",
                "full_name": "Rajesh Kumar",
                "father_name": "Suresh Kumar",
                "permanent_address": "123 Main Street, Dindori, Nashik",
                "district": "Nashik",
                "state": "Maharashtra",
                "issue_date": "2024-01-01",
                "valid_until": "2029-12-31",
                "issuing_authority": "Tehsildar Office"
            }
            """,
            
            'crop_insurance': base_instruction + """
            Extract from this crop insurance document:
            - policy_number: Insurance policy number
            - insurance_company: Company name
            - crop_name: Name of insured crop
            - land_area_insured: Area insured in acres
            - sum_insured: Total insured amount
            - premium_amount: Premium paid
            - policy_start_date: Start date (YYYY-MM-DD)
            - policy_end_date: End date (YYYY-MM-DD)
            
            Example:
            {
                "policy_number": "PMFBY/2024/123456",
                "insurance_company": "Agriculture Insurance Company",
                "crop_name": "Sugarcane",
                "land_area_insured": 5.5,
                "sum_insured": 275000,
                "premium_amount": 2750,
                "policy_start_date": "2024-06-01",
                "policy_end_date": "2024-12-31"
            }
            """,
            
            'death_certificate': base_instruction + """
            Extract from this death certificate:
            - deceased_name: Name of deceased person
            - date_of_death: Date of death (YYYY-MM-DD)
            - certificate_number: Certificate number
            - place_of_death: Place where death occurred
            - cause_of_death: Cause of death
            
            Example:
            {
                "deceased_name": "Suresh Kumar",
                "date_of_death": "2024-01-15",
                "certificate_number": "DC/2024/12345",
                "place_of_death": "Civil Hospital, Nashik",
                "cause_of_death": "Natural causes"
            }
            """
        }
        
        return prompts.get(document_type, base_instruction + "Extract all text from this document.")
    
    def _parse_response(self, response_text: str, document_type: str) -> Dict[str, Any]:
        """Parse Gemini response into JSON"""
        try:
            # Remove markdown code blocks
            cleaned = re.sub(r'```json\s*|\s*```', '', response_text)
            cleaned = re.sub(r'```\s*|\s*```', '', cleaned)
            
            # Find JSON object
            json_match = re.search(r'\{.*\}', cleaned, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
            else:
                print(f"⚠️ No JSON found in response, using raw text")
                return {"raw_text": cleaned[:500]}
        except json.JSONDecodeError as e:
            print(f"⚠️ JSON parse error: {e}")
            return {"raw_text": response_text[:500]}
    
    def _validate_and_clean(self, data: Dict[str, Any], document_type: str) -> Dict[str, Any]:
        """Validate and clean data based on document type"""
        cleaned = {}
        
        if document_type == 'aadhaar':
            # Clean Aadhaar number
            if 'aadhaar_number' in data:
                aadhaar = re.sub(r'\D', '', str(data['aadhaar_number']))
                if len(aadhaar) == 12:
                    cleaned['aadhaar_number'] = aadhaar
                else:
                    cleaned['aadhaar_number'] = aadhaar
            
            # Clean date
            if 'date_of_birth' in data:
                cleaned['date_of_birth'] = self._parse_date(data['date_of_birth'])
            
            # Clean pincode
            if 'pincode' in data:
                pincode = re.sub(r'\D', '', str(data['pincode']))
                if len(pincode) == 6:
                    cleaned['pincode'] = pincode
                else:
                    cleaned['pincode'] = pincode
            
            # Pass through other fields
            for field in ['full_name', 'gender', 'address', 'father_name', 'mobile_number', 'email']:
                if field in data:
                    cleaned[field] = str(data[field])[:200]
        
        elif document_type == 'pan':
            if 'pan_number' in data:
                pan = re.sub(r'[^A-Z0-9]', '', str(data['pan_number']).upper())
                cleaned['pan_number'] = pan
            if 'date_of_birth' in data:
                cleaned['date_of_birth'] = self._parse_date(data['date_of_birth'])
            for field in ['full_name', 'father_name', 'pan_type']:
                if field in data:
                    cleaned[field] = str(data[field])[:200]
        
        elif document_type == 'bank_passbook':
            if 'ifsc_code' in data:
                ifsc = re.sub(r'[^A-Z0-9]', '', str(data['ifsc_code']).upper())
                cleaned['ifsc_code'] = ifsc
            if 'account_number' in data:
                acc = re.sub(r'\D', '', str(data['account_number']))
                cleaned['account_number'] = acc
            for field in ['bank_name', 'branch_name', 'account_holder_name', 'account_type', 'micr_code']:
                if field in data:
                    cleaned[field] = str(data[field])[:200]
        
        elif document_type == 'land_record':
            for num_field in ['land_area_acres', 'land_area_hectares', 'land_value']:
                if num_field in data:
                    try:
                        cleaned[num_field] = float(data[num_field])
                    except:
                        cleaned[num_field] = 0.0
            for field in ['survey_number', 'land_type', 'owner_name', 'co_owners', 
                          'village_name', 'taluka', 'district', 'state', 
                          'crop_pattern', 'irrigation_source']:
                if field in data:
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
            for field in ['certificate_number', 'caste_category', 'caste_name', 'issuing_authority',
                          'district', 'full_name', 'father_name', 'permanent_address', 'state',
                          'deceased_name', 'place_of_death', 'cause_of_death']:
                if field in data:
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
            for field in ['policy_number', 'insurance_company', 'crop_name']:
                if field in data:
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
