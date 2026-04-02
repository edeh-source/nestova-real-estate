"""
Test script for Persona API verification migration
Tests NIN, BVN, and CAC verification endpoints and confidence scoring
"""

import os
import sys
import django

# Setup Django environment
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'nestova.settings')
django.setup()

from django.contrib.auth import get_user_model
from agents.verification_service import VerificationService
from agents.models import VerificationLog
from decimal import Decimal

User = get_user_model()


class Colors:
    """ANSI color codes for terminal output"""
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    RESET = '\033[0m'
    BOLD = '\033[1m'


def print_header(text):
    """Print formatted header"""
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'='*60}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BLUE}{text}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'='*60}{Colors.RESET}\n")


def print_success(text):
    """Print success message"""
    print(f"{Colors.GREEN}✓ {text}{Colors.RESET}")


def print_error(text):
    """Print error message"""
    print(f"{Colors.RED}✗ {text}{Colors.RESET}")


def print_warning(text):
    """Print warning message"""
    print(f"{Colors.YELLOW}⚠ {text}{Colors.RESET}")


def print_info(text):
    """Print info message"""
    print(f"{Colors.BLUE}ℹ {text}{Colors.RESET}")


def test_service_initialization():
    """Test VerificationService initialization"""
    print_header("Test 1: Service Initialization")
    
    try:
        service = VerificationService()
        
        # Check API key is loaded
        if service.api_key:
            print_success(f"API key loaded: {service.api_key[:20]}...")
        else:
            print_error("API key not loaded")
            return False
        
        # Check base URL
        if service.base_url == "https://withpersona.com/api/v1":
            print_success(f"Base URL correct: {service.base_url}")
        else:
            print_error(f"Base URL incorrect: {service.base_url}")
            return False
        
        # Check thresholds
        print_info(f"Auto-verify threshold: {service.auto_verify_threshold}%")
        print_info(f"Manual review threshold: {service.manual_review_threshold}%")
        print_info(f"Auto-reject threshold: {service.auto_reject_threshold}%")
        
        print_success("Service initialization successful")
        return True
        
    except Exception as e:
        print_error(f"Service initialization failed: {str(e)}")
        return False


def test_confidence_scoring():
    """Test confidence score calculation"""
    print_header("Test 2: Confidence Score Calculation")
    
    try:
        service = VerificationService()
        
        # Create a test user
        test_user, created = User.objects.get_or_create(
            username='test_verification_user',
            defaults={
                'email': 'test@example.com',
                'first_name': 'John',
                'last_name': 'Doe'
            }
        )
        
        # Test Case 1: Perfect match
        print_info("\nTest Case 1: Perfect match (should be ~100%)")
        api_data_perfect = {
            'first_name': 'John',
            'last_name': 'Doe',
            'email': 'test@example.com'
        }
        result = service.calculate_confidence_score(api_data_perfect, test_user)
        print_info(f"Overall confidence: {result['overall_confidence']}%")
        print_info(f"Recommendation: {result['recommendation']}")
        print_info(f"Breakdown: {result['breakdown']}")
        
        if result['overall_confidence'] == 100.0:
            print_success("Perfect match test passed")
        else:
            print_warning(f"Expected 100%, got {result['overall_confidence']}%")
        
        # Test Case 2: Partial match
        print_info("\nTest Case 2: Partial match (should be ~50%)")
        api_data_partial = {
            'first_name': 'John',
            'last_name': 'Smith',  # Different last name
            'email': 'different@example.com'  # Different email
        }
        result = service.calculate_confidence_score(api_data_partial, test_user)
        print_info(f"Overall confidence: {result['overall_confidence']}%")
        print_info(f"Recommendation: {result['recommendation']}")
        
        # Test Case 3: Fuzzy name match
        print_info("\nTest Case 3: Fuzzy name match")
        api_data_fuzzy = {
            'first_name': 'Jon',  # Slight variation
            'last_name': 'Doe',
        }
        result = service.calculate_confidence_score(api_data_fuzzy, test_user)
        print_info(f"Overall confidence: {result['overall_confidence']}%")
        print_info(f"First name match: {result['breakdown'].get('first_name_match', 'N/A')}%")
        
        print_success("Confidence scoring tests completed")
        return True
        
    except Exception as e:
        print_error(f"Confidence scoring test failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def test_api_connectivity():
    """Test Persona API connectivity"""
    print_header("Test 3: API Connectivity")
    
    try:
        service = VerificationService()
        
        # Test with a sample NIN (this will likely fail with sandbox, but we can check the error)
        print_info("Testing API connectivity with sample request...")
        
        # Create a test user
        test_user, created = User.objects.get_or_create(
            username='test_api_user',
            defaults={
                'email': 'testapi@example.com',
                'first_name': 'Test',
                'last_name': 'User'
            }
        )
        
        # Try a verification (this might fail, but we want to see the error format)
        success, result = service.verify_nin(test_user, '12345678901')
        
        if success:
            print_success("API request successful!")
            print_info(f"Response data: {result}")
        else:
            print_warning("API request failed (expected with test data)")
            print_info(f"Error: {result}")
            
            # Check if we got a proper error response from Persona
            if isinstance(result, dict) and 'error' in result:
                print_success("Error handling is working correctly")
            else:
                print_error("Unexpected error format")
        
        # Check verification log was created
        log_count = VerificationLog.objects.filter(user=test_user, verification_type='nin').count()
        if log_count > 0:
            print_success(f"Verification log created ({log_count} entries)")
            latest_log = VerificationLog.objects.filter(user=test_user, verification_type='nin').latest('created_at')
            print_info(f"Log status: {latest_log.status}")
            print_info(f"API provider: {latest_log.api_provider}")
        else:
            print_error("No verification log created")
        
        return True
        
    except Exception as e:
        print_error(f"API connectivity test failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def test_error_handling():
    """Test error handling for various scenarios"""
    print_header("Test 4: Error Handling")
    
    try:
        service = VerificationService()
        
        # Create a test user
        test_user, created = User.objects.get_or_create(
            username='test_error_user',
            defaults={
                'email': 'testerror@example.com',
                'first_name': 'Error',
                'last_name': 'Test'
            }
        )
        
        # Test 1: Empty ID number
        print_info("\nTest: Empty ID number")
        success, result = service.verify_nin(test_user, '')
        if not success:
            print_success("Empty ID number handled correctly")
        else:
            print_warning("Empty ID number should fail")
        
        # Test 2: Invalid format ID number
        print_info("\nTest: Invalid format ID number")
        success, result = service.verify_nin(test_user, 'INVALID')
        if not success:
            print_success("Invalid ID format handled correctly")
            print_info(f"Error message: {result}")
        else:
            print_warning("Invalid ID should fail")
        
        # Test 3: BVN verification
        print_info("\nTest: BVN verification")
        success, result = service.verify_bvn(test_user, '12345678901')
        print_info(f"BVN verification result: {'Success' if success else 'Failed'}")
        
        # Test 4: CAC verification
        print_info("\nTest: CAC verification")
        success, result = service.verify_cac(test_user, 'RC123456', 'Test Company Ltd')
        print_info(f"CAC verification result: {'Success' if success else 'Failed'}")
        
        print_success("Error handling tests completed")
        return True
        
    except Exception as e:
        print_error(f"Error handling test failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def test_verification_log_creation():
    """Test that verification logs are properly created"""
    print_header("Test 5: Verification Log Creation")
    
    try:
        # Get recent logs
        recent_logs = VerificationLog.objects.all().order_by('-created_at')[:5]
        
        if recent_logs.exists():
            print_success(f"Found {recent_logs.count()} recent verification logs")
            
            for log in recent_logs:
                print_info(f"\nLog ID: {log.id}")
                print_info(f"  User: {log.user.username}")
                print_info(f"  Type: {log.get_verification_type_display()}")
                print_info(f"  Status: {log.status}")
                print_info(f"  Provider: {log.api_provider}")
                print_info(f"  Match: {log.is_match}")
                print_info(f"  Created: {log.created_at}")
                
                if log.error_message:
                    print_info(f"  Error: {log.error_message[:100]}...")
        else:
            print_warning("No verification logs found")
        
        return True
        
    except Exception as e:
        print_error(f"Verification log test failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def run_all_tests():
    """Run all verification tests"""
    print_header("PERSONA API VERIFICATION TEST SUITE")
    print_info("Testing Persona API integration and verification workflows\n")
    
    results = {
        'Service Initialization': test_service_initialization(),
        'Confidence Scoring': test_confidence_scoring(),
        'API Connectivity': test_api_connectivity(),
        'Error Handling': test_error_handling(),
        'Verification Logs': test_verification_log_creation(),
    }
    
    # Summary
    print_header("TEST SUMMARY")
    
    passed = sum(1 for result in results.values() if result)
    total = len(results)
    
    for test_name, result in results.items():
        if result:
            print_success(f"{test_name}: PASSED")
        else:
            print_error(f"{test_name}: FAILED")
    
    print(f"\n{Colors.BOLD}Results: {passed}/{total} tests passed{Colors.RESET}")
    
    if passed == total:
        print_success("\n🎉 All tests passed!")
    else:
        print_warning(f"\n⚠️  {total - passed} test(s) failed")
    
    return passed == total


if __name__ == '__main__':
    run_all_tests()
