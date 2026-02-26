# app/eligibility_checker.py - UPDATED (No Gemini dependency)
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.models import User, Application, GovernmentScheme, Notification
from app.config import settings
from datetime import datetime
import logging
import json
import asyncio
import uuid
from typing import List, Dict, Any, Optional, Tuple

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# REMOVED: from app.gemini_processor import GeminiDocumentProcessor
# REMOVED: processor = GeminiDocumentProcessor()

class EligibilityChecker:
    """Check user eligibility for government schemes and auto-apply"""
    
    def __init__(self, db: Session):
        self.db = db
    
    async def check_scheme_for_user(self, user_id: int, scheme_id: int) -> Dict[str, Any]:
        """
        Check if a specific user is eligible for a scheme
        
        Args:
            user_id: User ID
            scheme_id: Scheme ID
            
        Returns:
            Dictionary with eligibility results
        """
        logger.info(f"🔍 Checking eligibility for user {user_id} for scheme {scheme_id}")
        
        # Get user data
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            logger.error(f"User {user_id} not found")
            return {
                "eligible": False, 
                "reason": "User not found",
                "match_percentage": 0
            }
        
        # Get scheme
        scheme = self.db.query(GovernmentScheme).filter(GovernmentScheme.id == scheme_id).first()
        if not scheme:
            logger.error(f"Scheme {scheme_id} not found")
            return {
                "eligible": False, 
                "reason": "Scheme not found",
                "match_percentage": 0
            }
        
        # Get user's documents from all tables
        user_docs = await self._get_user_documents(user.farmer_id)
        
        if not user_docs:
            logger.info(f"User {user.farmer_id} has no documents uploaded")
            return {
                "eligible": False,
                "reason": "No documents uploaded",
                "match_percentage": 0,
                "missing_documents": scheme.required_documents or []
            }
        
        # Check if user has all required documents
        required_docs = scheme.required_documents or []
        has_docs, missing_docs, present_docs = self._check_required_documents(user_docs, required_docs)
        
        # Calculate document coverage percentage
        doc_coverage = 0
        if required_docs:
            doc_coverage = (len(present_docs) / len(required_docs)) * 100
        
        # Use rule-based eligibility checking (no Gemini)
        eligibility_result = self._check_eligibility_rules(user_docs, scheme.eligibility_criteria or {})
        
        # Combine results
        final_result = {
            "eligible": eligibility_result.get("eligible", False) and has_docs,
            "match_percentage": eligibility_result.get("match_percentage", doc_coverage),
            "reasons": eligibility_result.get("reasons", []),
            "matched_criteria": eligibility_result.get("matched_criteria", []),
            "missing_criteria": eligibility_result.get("missing_criteria", []),
            "has_required_documents": has_docs,
            "document_coverage": doc_coverage,
            "present_documents": present_docs,
            "missing_documents": missing_docs,
            "user_id": user_id,
            "farmer_id": user.farmer_id,
            "scheme_id": scheme_id,
            "scheme_name": scheme.scheme_name
        }
        
        # Add reason if documents are missing
        if not has_docs and missing_docs:
            final_result["reasons"].append(f"Missing documents: {', '.join(missing_docs)}")
        
        logger.info(f"✅ Eligibility check complete: Eligible={final_result['eligible']}, Match={final_result['match_percentage']}%")
        return final_result
    
    def _check_eligibility_rules(self, user_docs: Dict, criteria: Dict) -> Dict[str, Any]:
        """
        Check eligibility based on rules (no Gemini)
        
        Args:
            user_docs: User's documents with extracted data
            criteria: Scheme eligibility criteria
            
        Returns:
            Dictionary with eligibility results
        """
        
        matched = []
        missing = []
        reasons = []
        
        # Extract user data from documents
        user_data = self._extract_user_data_from_docs(user_docs)
        
        # Check each criterion
        for key, value in criteria.items():
            if key == "age_min" and "age" in user_data:
                if user_data["age"] >= value:
                    matched.append(f"Age >= {value}")
                else:
                    missing.append(f"Age < {value}")
                    reasons.append(f"Age {user_data['age']} is less than minimum {value}")
            
            elif key == "age_max" and "age" in user_data:
                if user_data["age"] <= value:
                    matched.append(f"Age <= {value}")
                else:
                    missing.append(f"Age > {value}")
                    reasons.append(f"Age {user_data['age']} is greater than maximum {value}")
            
            elif key == "annual_income_max" and "annual_income" in user_data:
                if user_data["annual_income"] <= value:
                    matched.append(f"Income <= ₹{value}")
                else:
                    missing.append(f"Income > ₹{value}")
                    reasons.append(f"Annual income ₹{user_data['annual_income']} exceeds maximum ₹{value}")
            
            elif key == "land_holding_min" and "land_area" in user_data:
                if user_data["land_area"] >= value:
                    matched.append(f"Land >= {value} acres")
                else:
                    missing.append(f"Land < {value} acres")
                    reasons.append(f"Land holding {user_data['land_area']} acres is less than minimum {value} acres")
            
            elif key == "caste_allowed" and "caste" in user_data:
                if user_data["caste"] in value:
                    matched.append(f"Caste {user_data['caste']} is allowed")
                else:
                    missing.append(f"Caste {user_data['caste']} not in allowed list")
                    reasons.append(f"Caste {user_data['caste']} is not eligible")
            
            elif key == "gender" and "gender" in user_data:
                if value == "all" or user_data["gender"].lower() == value.lower():
                    matched.append(f"Gender {user_data['gender']} is eligible")
                else:
                    missing.append(f"Gender {user_data['gender']} not eligible")
                    reasons.append(f"Gender {user_data['gender']} is not eligible (requires {value})")
        
        # Calculate match percentage
        total_criteria = len(criteria)
        if total_criteria == 0:
            match_percentage = 100
        else:
            match_percentage = (len(matched) / total_criteria) * 100
        
        # Determine eligibility
        eligible = len(missing) == 0
        
        return {
            "eligible": eligible,
            "match_percentage": match_percentage,
            "reasons": reasons,
            "matched_criteria": matched,
            "missing_criteria": missing,
            "confidence": "high"
        }
    
    def _extract_user_data_from_docs(self, user_docs: Dict) -> Dict[str, Any]:
        """Extract user information from documents for eligibility checking"""
        
        user_data = {}
        
        # Extract from Aadhaar
        if "aadhaar" in user_docs:
            aadhaar = user_docs["aadhaar"]
            if "date_of_birth" in aadhaar:
                # Calculate age from DOB
                try:
                    from datetime import date
                    dob = datetime.fromisoformat(aadhaar["date_of_birth"].replace('Z', '+00:00'))
                    today = date.today()
                    age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
                    user_data["age"] = age
                except:
                    pass
            
            if "gender" in aadhaar:
                user_data["gender"] = aadhaar["gender"]
        
        # Extract from income certificate
        if "income_certificate" in user_docs:
            income = user_docs["income_certificate"]
            if "annual_income" in income:
                try:
                    user_data["annual_income"] = float(income["annual_income"])
                except:
                    pass
        
        # Extract from land records
        if "land_record" in user_docs:
            land = user_docs["land_record"]
            if "land_area_acres" in land:
                try:
                    user_data["land_area"] = float(land["land_area_acres"])
                except:
                    pass
            elif "land_area_hectares" in land:
                try:
                    # Convert hectares to acres (1 hectare = 2.47 acres)
                    user_data["land_area"] = float(land["land_area_hectares"]) * 2.47
                except:
                    pass
        
        # Extract from caste certificate
        if "caste_certificate" in user_docs:
            caste = user_docs["caste_certificate"]
            if "caste_category" in caste:
                user_data["caste"] = caste["caste_category"]
        
        logger.info(f"📊 Extracted user data for eligibility: {user_data}")
        return user_data
    
    async def check_all_users_for_new_scheme(self, scheme_id: int) -> List[Dict[str, Any]]:
        """
        Check all users with auto-apply enabled for a new scheme
        
        Args:
            scheme_id: ID of newly added scheme
            
        Returns:
            List of applications created
        """
        logger.info(f"🔍 Checking all users for new scheme {scheme_id}")
        
        # Get scheme
        scheme = self.db.query(GovernmentScheme).filter(GovernmentScheme.id == scheme_id).first()
        if not scheme:
            logger.error(f"Scheme {scheme_id} not found")
            return []
        
        # Get all users with auto-apply enabled
        users = self.db.query(User).filter(User.auto_apply_enabled == True).all()
        logger.info(f"Found {len(users)} users with auto-apply enabled")
        
        applications_created = []
        
        for user in users:
            try:
                # Check eligibility
                result = await self.check_scheme_for_user(user.id, scheme_id)
                
                if result.get("eligible"):
                    # Auto-apply
                    application = await self._create_auto_application(user, scheme, result)
                    applications_created.append({
                        "user_id": user.id,
                        "farmer_id": user.farmer_id,
                        "application_id": application.id,
                        "application_number": application.application_id,
                        "match_percentage": result.get("match_percentage", 100)
                    })
                    
                    # Create notification
                    await self._create_notification(
                        user.id,
                        f"✅ Auto-Applied: {scheme.scheme_name}",
                        f"You have been automatically enrolled in {scheme.scheme_name} based on your documents. Application ID: {application.application_id}"
                    )
                    
                    logger.info(f"✅ Auto-applied user {user.farmer_id} to scheme {scheme_id}")
                else:
                    logger.info(f"❌ User {user.farmer_id} not eligible: {result.get('reasons', ['Unknown reason'])}")
                    
            except Exception as e:
                logger.error(f"Error checking user {user.id}: {str(e)}")
                import traceback
                traceback.print_exc()
                continue
        
        logger.info(f"✅ Auto-apply complete: {len(applications_created)} applications created")
        return applications_created
    
    async def manual_apply_for_user(self, user_id: int, scheme_id: int) -> Dict[str, Any]:
        """
        Manually apply for a scheme (for frontend use)
        
        Args:
            user_id: User ID
            scheme_id: Scheme ID
            
        Returns:
            Application result
        """
        logger.info(f"📝 Manual apply for user {user_id} to scheme {scheme_id}")
        
        # Check eligibility first
        result = await self.check_scheme_for_user(user_id, scheme_id)
        
        if not result.get("eligible"):
            return {
                "success": False,
                "message": "Not eligible for this scheme",
                "eligibility": result
            }
        
        # Get user and scheme
        user = self.db.query(User).filter(User.id == user_id).first()
        scheme = self.db.query(GovernmentScheme).filter(GovernmentScheme.id == scheme_id).first()
        
        # Check if already applied
        existing = self.db.query(Application).filter(
            Application.user_id == user_id,
            Application.scheme_id == scheme_id
        ).first()
        
        if existing:
            return {
                "success": False,
                "message": "Already applied for this scheme",
                "application_id": existing.id
            }
        
        # Create application
        application = await self._create_auto_application(user, scheme, result)
        
        return {
            "success": True,
            "message": "Successfully applied for scheme",
            "application_id": application.id,
            "application_number": application.application_id,
            "eligibility": result
        }
    
    async def _get_user_documents(self, farmer_id: str) -> Dict[str, Any]:
        """Fetch all documents for a user from all tables"""
        
        documents = {}
        tables = settings.DOCUMENT_TABLE_MAP
        
        for doc_type, table_name in tables.items():
            try:
                query = text(f"""
                    SELECT * FROM {table_name} 
                    WHERE farmer_id = :farmer_id 
                    ORDER BY created_at DESC 
                    LIMIT 1
                """)
                result = self.db.execute(query, {'farmer_id': farmer_id}).first()
                
                if result:
                    # Convert row to dict
                    row_dict = dict(result._mapping)
                    documents[doc_type] = row_dict
                    logger.debug(f"Found {doc_type} document for farmer {farmer_id}")
            except Exception as e:
                logger.warning(f"Could not fetch from {table_name}: {str(e)}")
                continue
        
        logger.info(f"Found {len(documents)} document types for farmer {farmer_id}")
        return documents
    
    def _check_required_documents(self, user_docs: Dict, required_docs: List) -> Tuple[bool, List, List]:
        """Check if user has all required documents"""
        
        if not required_docs:
            return True, [], []
        
        missing = []
        present = []
        
        # Map common document names to our document types
        doc_mapping = {
            'aadhaar': ['aadhaar', 'aadhar', 'uid'],
            'pan': ['pan'],
            'land_record': ['land', '7/12', 'satbara'],
            'bank_passbook': ['bank', 'passbook'],
            'income_certificate': ['income'],
            'caste_certificate': ['caste'],
            'domicile': ['domicile', 'residence'],
            'crop_insurance': ['insurance', 'crop'],
            'death_certificate': ['death']
        }
        
        for req in required_docs:
            req_lower = req.lower()
            found = False
            
            # Check if any of our document types match this requirement
            for doc_type, keywords in doc_mapping.items():
                if any(keyword in req_lower for keyword in keywords):
                    if doc_type in user_docs:
                        present.append(req)
                        found = True
                        break
            
            if not found:
                missing.append(req)
        
        return len(missing) == 0, missing, present
    
    async def _create_auto_application(self, user: User, scheme: GovernmentScheme, eligibility: Dict) -> Application:
        """Create an auto-application for a user with guaranteed unique ID"""
        
        # Generate a truly unique application ID using timestamp + UUID
        year = datetime.now().year
        timestamp = datetime.now().strftime("%m%d%H%M%S%f")
        unique_id = str(uuid.uuid4()).replace('-', '')[:8]
        application_id = f"APP{year}{timestamp}{unique_id}"
        
        logger.info(f"Generated application ID: {application_id}")
        
        # Prepare application data
        application_data = {
            "eligibility_check": eligibility,
            "auto_applied": True,
            "applied_at": datetime.now().isoformat(),
            "scheme_name": scheme.scheme_name,
            "scheme_code": scheme.scheme_code
        }
        
        # Calculate applied amount
        applied_amount = 0
        if scheme.benefit_amount:
            try:
                amount_str = ''.join(c for c in scheme.benefit_amount if c.isdigit() or c == '.')
                applied_amount = float(amount_str) if amount_str else 0
            except:
                applied_amount = 0
        
        # Create application
        application = Application(
            user_id=user.id,
            scheme_id=scheme.id,
            application_id=application_id,
            status="PENDING",
            applied_amount=applied_amount,
            application_data=application_data,
            applied_at=datetime.now()
        )
        
        # Add retry logic
        max_retries = 2
        for attempt in range(max_retries):
            try:
                self.db.add(application)
                self.db.commit()
                self.db.refresh(application)
                logger.info(f"✅ Created application {application_id} for user {user.farmer_id}")
                return application
                
            except Exception as e:
                self.db.rollback()
                
                if "duplicate key" in str(e).lower() and attempt < max_retries - 1:
                    logger.warning(f"Duplicate application ID {application_id}, retrying...")
                    year = datetime.now().year
                    timestamp = datetime.now().strftime("%m%d%H%M%S%f")
                    unique_id = str(uuid.uuid4()).replace('-', '')[:12]
                    application_id = f"APP{year}{timestamp}{unique_id}"
                    application.application_id = application_id
                else:
                    logger.error(f"Failed to create application: {str(e)}")
                    raise e
        
        raise Exception(f"Failed to create application after {max_retries} attempts")
    
    async def _create_notification(self, user_id: int, title: str, message: str):
        """Create a notification for user"""
        
        notification = Notification(
            user_id=user_id,
            title=title,
            message=message,
            notification_type="auto_apply",
            read=False,
            created_at=datetime.now()
        )
        
        self.db.add(notification)
        self.db.commit()
        logger.info(f"📨 Notification created for user {user_id}")


# ==================== BACKGROUND TASK FUNCTION ====================

async def run_auto_apply_check(scheme_id: int):
    """Background task to run auto-apply for a new scheme"""
    
    logger.info(f"🚀 Starting auto-apply background task for scheme {scheme_id}")
    
    try:
        from app.database import SessionLocal
        
        # Create a new database session for background task
        db = SessionLocal()
        checker = EligibilityChecker(db)
        
        # Run the check
        results = await checker.check_all_users_for_new_scheme(scheme_id)
        
        logger.info(f"✅ Auto-apply completed for scheme {scheme_id}: {len(results)} applications created")
        
        # Close session
        db.close()
        
    except Exception as e:
        logger.error(f"❌ Auto-apply background task failed for scheme {scheme_id}: {str(e)}")
        import traceback
        traceback.print_exc()
