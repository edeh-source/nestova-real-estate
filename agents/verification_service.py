import requests
import logging
from django.conf import settings
from .models import VerificationLog
from fuzzywuzzy import fuzz
from datetime import datetime
import time
import uuid

logger = logging.getLogger(__name__)

class VerificationService:
    """
    Handles interactions with Kora API for identity verification in Nigeria.
    Supports NIN, vNIN, BVN, and CAC verification with confidence scoring and auto-approval capabilities.
    """

    def __init__(self, provider='kora'):
        self.provider = provider
        # Get API key from settings
        self.api_key = getattr(settings, 'KORA_SECRET_KEY', None)
        self.public_key = getattr(settings, 'KORA_PUBLIC_KEY', None)
        self.base_url = getattr(settings, 'KORA_BASE_URL', 'https://api.korapay.com/merchant/api/v1')
        
        # Confidence thresholds
        self.auto_verify_threshold = getattr(settings, 'AUTO_VERIFY_CONFIDENCE_THRESHOLD', 85)
        self.manual_review_threshold = getattr(settings, 'REQUIRE_MANUAL_REVIEW_BELOW', 70)
        self.auto_reject_threshold = getattr(settings, 'AUTO_REJECT_BELOW', 50)

    def _get_headers(self):
        """Get authorization headers for Kora API"""
        if not self.api_key:
            raise ValueError("Kora API key not configured")
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

    def _generate_reference(self):
        """Generate unique reference for verification request"""
        return f"VER-{uuid.uuid4().hex[:12].upper()}"

    def _log_attempt(self, user, v_type, request_data, response_data, status, is_match=False, confidence_score=None, error=None):
        """Internal helper to log verification attempts"""
        return VerificationLog.objects.create(
            user=user,
            verification_type=v_type,
            api_provider=self.provider,
            request_data=request_data,
            response_data=response_data,
            status=status,
            is_match=is_match,
            confidence_score=confidence_score,
            error_message=error
        )

    def _make_verification_request(self, endpoint, payload):
        """
        Make verification request to Kora API
        
        Args:
            endpoint: API endpoint (e.g., '/identities/ng/nin')
            payload: Request payload
        
        Returns:
            tuple: (success: bool, response_data: dict)
        """
        if not self.api_key:
            logger.error("Kora API key not configured.")
            return False, {"error": "Verification system is temporarily unavailable."}

        url = f"{self.base_url}{endpoint}"
        
        try:
            headers = self._get_headers()
            
            # Log the request details for debugging
            logger.info(f"Kora API Request: {url}")
            logger.info(f"Payload: {payload}")
            
            response = requests.post(url, json=payload, headers=headers, timeout=30)
            data = response.json()
            
            # Log the response for debugging
            logger.info(f"Kora API Response Status: {response.status_code}")
            logger.info(f"Kora API Response Data: {data}")
            
            if response.status_code == 200 and data.get('status') is True:
                # Successful verification
                logger.info(f"Kora verification successful!")
                return True, data
            else:
                # Error response
                error_msg = data.get('message', 'Verification failed')
                logger.error(f"Kora verification failed: {error_msg}")
                logger.error(f"Full response: {data}")
                return False, {"error": error_msg, "raw_response": data}
                
        except requests.exceptions.Timeout:
            error_msg = "Verification request timed out"
            logger.exception(error_msg)
            return False, {"error": error_msg}
        except requests.exceptions.RequestException as e:
            error_msg = f"Network error during verification: {str(e)}"
            logger.exception(error_msg)
            return False, {"error": error_msg}
        except Exception as e:
            error_msg = f"Unexpected error during verification: {str(e)}"
            logger.exception(error_msg)
            return False, {"error": error_msg}

    def _extract_verification_data(self, response_data):
        """
        Extract verification data from Kora API response
        
        Returns:
            dict: Normalized verification data
        """
        try:
            if 'data' in response_data:
                data = response_data['data']
                
                # Extract relevant fields
                extracted = {
                    'status': 'verified' if response_data.get('status') else 'failed',
                    'first_name': data.get('first_name') or data.get('firstname'),
                    'last_name': data.get('last_name') or data.get('lastname') or data.get('surname'),
                    'middle_name': data.get('middle_name') or data.get('middlename'),
                    'date_of_birth': data.get('date_of_birth') or data.get('dob') or data.get('birthdate'),
                    'phone': data.get('phone') or data.get('phone_number') or data.get('mobile'),
                    'email': data.get('email'),
                    'gender': data.get('gender'),
                    'address': data.get('address'),
                    'photo': data.get('photo'),
                    'nin': data.get('nin'),
                    'vnin': data.get('vnin'),
                    'bvn': data.get('bvn'),
                    'match_status': data.get('match_status'),
                    'raw_data': data  # Keep raw data for debugging
                }
                
                return extracted
            return {}
        except Exception as e:
            logger.exception(f"Error extracting verification data: {e}")
            return {}

    def verify_nin(self, user, nin, first_name=None, last_name=None, dob=None):
        """
        Verify NIN (National Identity Number) using Kora API
        
        Args:
            user: User object
            nin: National Identity Number
            first_name: Optional - for data validation
            last_name: Optional - for data validation
            dob: Optional - for data validation (YYYY-MM-DD format)
        """
        payload = {
            "id": nin,
            "verification_consent": True
        }
        
        # Add optional validation fields
        if first_name:
            payload['first_name'] = first_name
        if last_name:
            payload['last_name'] = last_name
        if dob:
            payload['dob'] = dob
        
        params = {"nin": nin}
        
        try:
            success, result = self._make_verification_request('/identities/ng/nin', payload)
            
            if success:
                # Extract and normalize data
                extracted_data = self._extract_verification_data(result)
                
                # Check verification status
                is_match = extracted_data.get('status') == 'verified'
                
                self._log_attempt(user, 'nin', params, result, 'success' if is_match else 'failed', is_match=is_match)
                
                return True, extracted_data
            else:
                error_msg = result.get('error', 'Verification failed')
                self._log_attempt(user, 'nin', params, result, 'failed', error=error_msg)
                return False, error_msg

        except Exception as e:
            logger.exception("Error during NIN verification")
            self._log_attempt(user, 'nin', params, {}, 'failed', error=str(e))
            return False, str(e)

    def verify_vnin(self, user, vnin, first_name=None, last_name=None, dob=None):
        """
        Verify vNIN (Virtual NIN) using Kora API
        
        Args:
            user: User object
            vnin: Virtual National Identity Number
            first_name: Optional - for data validation
            last_name: Optional - for data validation
            dob: Optional - for data validation (YYYY-MM-DD format)
        """
        payload = {
            "id": vnin,
            "verification_consent": True
        }
        
        # Add optional validation fields
        if first_name:
            payload['first_name'] = first_name
        if last_name:
            payload['last_name'] = last_name
        if dob:
            payload['dob'] = dob
        
        params = {"vnin": vnin}
        
        try:
            success, result = self._make_verification_request('/identities/ng/vnin', payload)
            
            if success:
                # Extract and normalize data
                extracted_data = self._extract_verification_data(result)
                
                # Check verification status
                is_match = extracted_data.get('status') == 'verified'
                
                self._log_attempt(user, 'vnin', params, result, 'success' if is_match else 'failed', is_match=is_match)
                
                return True, extracted_data
            else:
                error_msg = result.get('error', 'Verification failed')
                self._log_attempt(user, 'vnin', params, result, 'failed', error=error_msg)
                return False, error_msg

        except Exception as e:
            logger.exception("Error during vNIN verification")
            self._log_attempt(user, 'vnin', params, {}, 'failed', error=str(e))
            return False, str(e)

    def verify_bvn(self, user, bvn, first_name=None, last_name=None, dob=None):
        """
        Verify BVN (Bank Verification Number) using Kora API
        
        Args:
            user: User object
            bvn: Bank Verification Number
            first_name: Optional - for data validation
            last_name: Optional - for data validation
            dob: Optional - for data validation (YYYY-MM-DD format)
        """
        payload = {
            "id": bvn,
            "verification_consent": True
        }
        
        # Add optional validation fields
        if first_name:
            payload['first_name'] = first_name
        if last_name:
            payload['last_name'] = last_name
        if dob:
            payload['dob'] = dob
        
        params = {"bvn": bvn}
        
        try:
            success, result = self._make_verification_request('/identities/ng/bvn', payload)
            
            if success:
                # Extract and normalize data
                extracted_data = self._extract_verification_data(result)
                
                # Check verification status
                is_match = extracted_data.get('status') == 'verified'
                
                self._log_attempt(user, 'bvn', params, result, 'success' if is_match else 'failed', is_match=is_match)
                
                return True, extracted_data
            else:
                error_msg = result.get('error', 'Verification failed')
                self._log_attempt(user, 'bvn', params, result, 'failed', error=error_msg)
                return False, error_msg

        except Exception as e:
            logger.exception("Error during BVN verification")
            self._log_attempt(user, 'bvn', params, {}, 'failed', error=str(e))
            return False, str(e)

    def verify_cac(self, user, rc_number, company_name=None):
        """
        Verify CAC (Corporate Affairs Commission) Registration
        Note: Check Kora API documentation for CAC endpoint availability
        """
        payload = {
            "rc_number": rc_number,
            "verification_consent": True
        }
        
        if company_name:
            payload['company_name'] = company_name
        
        params = {"rc_number": rc_number}
        
        try:
            # Note: Verify this endpoint exists in Kora API
            success, result = self._make_verification_request('/identities/ng/cac', payload)
            
            if success:
                # Extract and normalize data
                extracted_data = self._extract_verification_data(result)
                
                # Check verification status
                is_match = extracted_data.get('status') == 'verified'
                
                # Add company name from response if available
                if 'company_name' not in extracted_data and 'data' in result:
                    extracted_data['company_name'] = result['data'].get('company_name')
                
                self._log_attempt(user, 'cac', params, result, 'success' if is_match else 'failed', is_match=is_match)
                
                return True, extracted_data
            else:
                error_msg = result.get('error', 'Verification failed')
                self._log_attempt(user, 'cac', params, result, 'failed', error=error_msg)
                return False, error_msg

        except Exception as e:
            logger.exception("Error during CAC verification")
            self._log_attempt(user, 'cac', params, {}, 'failed', error=str(e))
            return False, str(e)

    def calculate_confidence_score(self, api_data, user, user_profile=None):
        """
        Calculate confidence score based on data matching between API response and user data.
        Returns: Dictionary with overall score (0-100) and breakdown
        """
        scores = []
        breakdown = {}
        
        # Name matching (First Name)
        if 'first_name' in api_data or 'firstname' in api_data:
            api_first_name = api_data.get('first_name') or api_data.get('firstname', '')
            user_first_name = user.first_name or ''
            
            if api_first_name and user_first_name:
                name_score = self._fuzzy_match_name(api_first_name, user_first_name)
                scores.append(name_score)
                breakdown['first_name_match'] = name_score
        
        # Name matching (Last Name)
        if 'last_name' in api_data or 'lastname' in api_data or 'surname' in api_data:
            api_last_name = api_data.get('last_name') or api_data.get('lastname') or api_data.get('surname', '')
            user_last_name = user.last_name or ''
            
            if api_last_name and user_last_name:
                surname_score = self._fuzzy_match_name(api_last_name, user_last_name)
                scores.append(surname_score)
                breakdown['last_name_match'] = surname_score
        
        # Phone matching
        if 'phone' in api_data or 'phone_number' in api_data or 'mobile' in api_data:
            api_phone_raw = api_data.get('phone') or api_data.get('phone_number') or api_data.get('mobile')
            api_phone = str(api_phone_raw).replace('+234', '0').replace(' ', '') if api_phone_raw else ''
            
            # Try to get phone from user profile
            user_phone = ''
            if user_profile and hasattr(user_profile, 'phone') and user_profile.phone:
                user_phone = str(user_profile.phone).replace('+234', '0').replace(' ', '')
            elif hasattr(user, 'phone_number') and user.phone_number:
                user_phone = str(user.phone_number).replace('+234', '0').replace(' ', '')
            
            if api_phone and user_phone and len(api_phone) >= 10 and len(user_phone) >= 10:
                # Exact match for phone numbers (last 10 digits)
                phone_score = 100 if api_phone[-10:] == user_phone[-10:] else 0
                scores.append(phone_score)
                breakdown['phone_match'] = phone_score
        
        # Date of birth matching
        if 'date_of_birth' in api_data or 'dob' in api_data or 'birthdate' in api_data:
            api_dob = api_data.get('date_of_birth') or api_data.get('dob') or api_data.get('birthdate')
            
            user_dob = None
            if user_profile and hasattr(user_profile, 'date_of_birth'):
                user_dob = user_profile.date_of_birth
            
            if api_dob and user_dob:
                # Parse API DOB if it's a string
                if isinstance(api_dob, str):
                    try:
                        api_dob = datetime.strptime(api_dob, '%Y-%m-%d').date()
                    except:
                        try:
                            api_dob = datetime.strptime(api_dob, '%d-%m-%Y').date()
                        except:
                            api_dob = None
                
                if api_dob:
                    dob_score = 100 if api_dob == user_dob else 0
                    scores.append(dob_score)
                    breakdown['dob_match'] = dob_score
        
        # Email matching
        if 'email' in api_data:
            api_email = api_data.get('email') or ''
            user_email = user.email or ''
            
            # Convert to lowercase safely
            api_email = api_email.lower() if api_email else ''
            user_email = user_email.lower() if user_email else ''
            
            if api_email and user_email:
                email_score = 100 if api_email == user_email else 0
                scores.append(email_score)
                breakdown['email_match'] = email_score
        
        # Calculate overall confidence
        overall_confidence = sum(scores) / len(scores) if scores else 0
        
        return {
            'overall_confidence': round(overall_confidence, 2),
            'breakdown': breakdown,
            'checks_performed': len(scores),
            'recommendation': self._get_recommendation(overall_confidence)
        }
    
    def _fuzzy_match_name(self, name1, name2):
        """
        Fuzzy match two names using multiple algorithms.
        Returns: 0-100 score
        """
        if not name1 or not name2:
            return 0
        
        name1 = name1.lower().strip()
        name2 = name2.lower().strip()
        
        # Use multiple fuzzy matching algorithms and take the best score
        ratio_score = fuzz.ratio(name1, name2)
        partial_score = fuzz.partial_ratio(name1, name2)
        token_sort_score = fuzz.token_sort_ratio(name1, name2)
        
        # Return the highest score (most lenient)
        return max(ratio_score, partial_score, token_sort_score)
    
    def _get_recommendation(self, confidence):
        """Get verification recommendation based on confidence score"""
        if confidence >= self.auto_verify_threshold:
            return 'auto_approve'
        elif confidence >= self.manual_review_threshold:
            return 'manual_review'
        else:
            return 'auto_reject'
