import re
import random
import string
from datetime import datetime
from typing import Dict, Any

def generate_farmer_id(state_code: str, district_code: str) -> str:
    timestamp = datetime.now().strftime("%y%m%d")
    random_num = ''.join(random.choices(string.digits, k=4))
    return f"AGRO{state_code}{district_code}{timestamp}{random_num}"

def generate_application_id(scheme_code: str) -> str:
    timestamp = datetime.now().strftime("%y%m%d%H%M%S")
    random_str = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
    return f"APP{scheme_code}{timestamp}{random_str}"

def validate_aadhaar(aadhaar_number: str) -> bool:
    pattern = r'^[2-9]{1}[0-9]{3}\s[0-9]{4}\s[0-9]{4}$'
    return bool(re.match(pattern, aadhaar_number))

def validate_pan(pan_number: str) -> bool:
    pattern = r'^[A-Z]{5}[0-9]{4}[A-Z]{1}$'
    return bool(re.match(pattern, pan_number))

def validate_ifsc(ifsc_code: str) -> bool:
    pattern = r'^[A-Z]{4}0[A-Z0-9]{6}$'
    return bool(re.match(pattern, ifsc_code))

def calculate_eligibility(user_data: Dict[str, Any], scheme_criteria: Dict[str, Any]) -> Dict[str, Any]:
    match_count = 0
    total_criteria = len(scheme_criteria)
    missing_docs = []
    reasons = []
    
    for criterion, requirement in scheme_criteria.items():
        if criterion in user_data:
            if criterion == "annual_income":
                if user_data[criterion] <= requirement:
                    match_count += 1
                else:
                    reasons.append(f"Income exceeds limit")
            elif criterion == "total_land_acres":
                if user_data[criterion] >= requirement:
                    match_count += 1
                else:
                    reasons.append(f"Land area insufficient")
            elif criterion in ["state", "district"]:
                if user_data[criterion].lower() == requirement.lower():
                    match_count += 1
                else:
                    reasons.append(f"Location mismatch")
            else:
                if user_data[criterion]:
                    match_count += 1
        else:
            reasons.append(f"Missing data: {criterion}")
    
    match_percentage = (match_count / total_criteria * 100) if total_criteria > 0 else 0
    
    return {
        "eligible": match_percentage >= 80,
        "match_percentage": round(match_percentage, 2),
        "missing_documents": missing_docs,
        "reasons": reasons
    }