"""
Enhanced Kora API test script with detailed debugging
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

def test_kora_with_test_data():
    """Test Kora API with official test data"""
    print("=" * 60)
    print("KORA API TEST WITH OFFICIAL TEST DATA")
    print("=" * 60)
    
    # Check configuration
    secret_key = getattr(settings, 'KORA_SECRET_KEY', None)
    base_url = getattr(settings, 'KORA_BASE_URL', None)
    
    if not secret_key:
        print("\n❌ ERROR: KORA_SECRET_KEY is not configured!")
        return
    
    print(f"\n✓ API Key: {secret_key[:10]}...{secret_key[-4:]}")
    print(f"✓ Base URL: {base_url}")
    
    # Test with different official test numbers
    test_cases = [
        {
            "name": "Test NIN #1",
            "endpoint": "/identities/ng/nin",
            "payload": {
                "id": "12345678901",
                "verification_consent": True
            }
        },
        {
            "name": "Test BVN #1",
            "endpoint": "/identities/ng/bvn",
            "payload": {
                "id": "22222222222",
                "verification_consent": True
            }
        },
        {
            "name": "Test vNIN #1",
            "endpoint": "/identities/ng/vnin",
            "payload": {
                "id": "A12345678901234",
                "verification_consent": True
            }
        }
    ]
    
    headers = {
        "Authorization": f"Bearer {secret_key}",
        "Content-Type": "application/json"
    }
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n{'='*60}")
        print(f"TEST CASE {i}: {test_case['name']}")
        print(f"{'='*60}")
        print(f"Endpoint: {base_url}{test_case['endpoint']}")
        print(f"Payload: {json.dumps(test_case['payload'], indent=2)}")
        
        try:
            url = f"{base_url}{test_case['endpoint']}"
            print(f"\nSending request to: {url}")
            
            response = requests.post(
                url,
                json=test_case['payload'],
                headers=headers,
                timeout=30
            )
            
            print(f"\n📊 Response Status: {response.status_code}")
            print(f"📊 Response Headers: {dict(response.headers)}")
            
            try:
                response_data = response.json()
                print(f"\n📄 Response Body:")
                print(json.dumps(response_data, indent=2))
                
                # Analyze response
                if response.status_code == 200:
                    if response_data.get('status') is True:
                        print(f"\n✅ SUCCESS! Verification returned data")
                        if 'data' in response_data:
                            print(f"\n📋 Verified Data:")
                            for key, value in response_data['data'].items():
                                print(f"   - {key}: {value}")
                    else:
                        print(f"\n⚠️ API returned status=false")
                elif response.status_code == 404:
                    print(f"\n⚠️ Data not found - this test number may not be valid")
                elif response.status_code == 401:
                    print(f"\n❌ Authentication failed - check your API key")
                elif response.status_code == 422:
                    print(f"\n❌ Validation error - check request format")
                else:
                    print(f"\n⚠️ Unexpected status code")
                    
            except ValueError as e:
                print(f"\n❌ Could not parse JSON response")
                print(f"Raw response: {response.text}")
                
        except requests.exceptions.Timeout:
            print(f"\n❌ Request timed out after 30 seconds")
        except requests.exceptions.ConnectionError:
            print(f"\n❌ Connection error - check internet connection")
        except Exception as e:
            print(f"\n❌ Error: {str(e)}")
            import traceback
            traceback.print_exc()
    
    print(f"\n{'='*60}")
    print("TEST COMPLETE")
    print(f"{'='*60}")
    
    # Provide guidance
    print("\n📝 NEXT STEPS:")
    print("1. If you see 404 'Data not found' - the test numbers may be incorrect")
    print("2. Check Kora's documentation for the correct test NIN/BVN numbers")
    print("3. Contact Kora support to get official test data")
    print("4. Or switch to production keys to test with real data")

if __name__ == "__main__":
    test_kora_with_test_data()
