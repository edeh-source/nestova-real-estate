"""
Test script to verify Kora API configuration and connectivity
"""
import os
import sys
import django

# Setup Django environment
sys.path.insert(0, os.path.dirname(__file__))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'nestova.settings')
django.setup()

from django.conf import settings
import requests
import json

def test_kora_configuration():
    """Test Kora API configuration"""
    print("=" * 60)
    print("KORA API CONFIGURATION TEST")
    print("=" * 60)
    
    # Check if API keys are configured
    public_key = getattr(settings, 'KORA_PUBLIC_KEY', None)
    secret_key = getattr(settings, 'KORA_SECRET_KEY', None)
    base_url = getattr(settings, 'KORA_BASE_URL', None)
    
    print(f"\n1. Configuration Check:")
    print(f"   - Public Key: {'✓ Set' if public_key else '✗ NOT SET'}")
    if public_key:
        print(f"     Value: {public_key[:10]}...{public_key[-4:] if len(public_key) > 14 else ''}")
    
    print(f"   - Secret Key: {'✓ Set' if secret_key else '✗ NOT SET'}")
    if secret_key:
        print(f"     Value: {secret_key[:10]}...{secret_key[-4:] if len(secret_key) > 14 else ''}")
    
    print(f"   - Base URL: {base_url}")
    
    if not secret_key:
        print("\n❌ ERROR: KORA_SECRET_KEY is not configured!")
        print("   Please set KORA_SECRET_KEY in your environment variables or .env file")
        return False
    
    # Test API connectivity with a sample request
    print(f"\n2. API Connectivity Test:")
    print(f"   Testing endpoint: {base_url}/identities/ng/nin")
    
    headers = {
        "Authorization": f"Bearer {secret_key}",
        "Content-Type": "application/json"
    }
    
    # Use test NIN data (this should fail gracefully with proper error message)
    test_payload = {
        "id": "12345678901",  # Test NIN
        "verification_consent": True
    }
    
    print(f"\n3. Sample Request:")
    print(f"   Headers: Authorization: Bearer {secret_key[:10]}...")
    print(f"   Payload: {json.dumps(test_payload, indent=6)}")
    
    try:
        response = requests.post(
            f"{base_url}/identities/ng/nin",
            json=test_payload,
            headers=headers,
            timeout=30
        )
        
        print(f"\n4. Response:")
        print(f"   Status Code: {response.status_code}")
        
        try:
            response_data = response.json()
            print(f"   Response Body:")
            print(f"   {json.dumps(response_data, indent=6)}")
            
            if response.status_code == 200:
                print("\n✓ API is accessible and responding")
                if response_data.get('status') is True:
                    print("✓ Test verification successful (using test data)")
                else:
                    print("⚠ Verification failed (expected for test data)")
            elif response.status_code == 401:
                print("\n❌ AUTHENTICATION FAILED!")
                print("   Your API key may be incorrect or expired")
                print("   Please verify your KORA_SECRET_KEY")
            elif response.status_code == 400:
                print("\n⚠ Bad Request")
                print("   The request format is correct, but the data may be invalid")
                print("   This is expected for test data")
            else:
                print(f"\n⚠ Unexpected response code: {response.status_code}")
                
        except ValueError:
            print(f"   Response Text: {response.text}")
            
    except requests.exceptions.Timeout:
        print("\n❌ REQUEST TIMEOUT")
        print("   The API did not respond within 30 seconds")
    except requests.exceptions.ConnectionError:
        print("\n❌ CONNECTION ERROR")
        print("   Could not connect to Kora API")
        print("   Please check your internet connection")
    except Exception as e:
        print(f"\n❌ ERROR: {str(e)}")
        
    print("\n" + "=" * 60)
    print("TEST COMPLETE")
    print("=" * 60)
    
    return True

if __name__ == "__main__":
    test_kora_configuration()
