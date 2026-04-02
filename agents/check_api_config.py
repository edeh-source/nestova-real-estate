"""
Quick diagnostic script to check Persona API key configuration
"""

import os
import sys
import django

# Setup Django environment
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'nestova.settings')
django.setup()

from django.conf import settings

print("=" * 60)
print("PERSONA API KEY CONFIGURATION CHECK")
print("=" * 60)

# Check settings
print(f"\n1. PERSONA_API_KEY from settings: {settings.PERSONA_API_KEY[:30] if settings.PERSONA_API_KEY else 'NOT SET'}...")
print(f"2. PERSONA_TEMPLATE_ID: {settings.PERSONA_TEMPLATE_ID or 'NOT SET'}")
print(f"3. DEFAULT_PERSONA_KEY: {getattr(settings, 'DEFAULT_PERSONA_KEY', 'NOT SET')[:30] if hasattr(settings, 'DEFAULT_PERSONA_KEY') else 'NOT SET'}...")

# Check environment variables
print(f"\n4. PERSONA_API_KEY env var: {os.environ.get('PERSONA_API_KEY', 'NOT SET')}")
print(f"5. DEFAULT_PERSONA_KEY env var: {os.environ.get('DEFAULT_PERSONA_KEY', 'NOT SET')[:30] if os.environ.get('DEFAULT_PERSONA_KEY') else 'NOT SET'}...")

# Check thresholds
print(f"\n6. Auto-verify threshold: {settings.AUTO_VERIFY_CONFIDENCE_THRESHOLD}%")
print(f"7. Manual review threshold: {settings.REQUIRE_MANUAL_REVIEW_BELOW}%")
print(f"8. Auto-reject threshold: {settings.AUTO_REJECT_BELOW}%")

# Test VerificationService
print("\n" + "=" * 60)
print("VERIFICATION SERVICE CHECK")
print("=" * 60)

from agents.verification_service import VerificationService

service = VerificationService()
print(f"\nService API key: {service.api_key[:30] if service.api_key else 'NOT LOADED'}...")
print(f"Service base URL: {service.base_url}")
print(f"Service provider: {service.provider}")

if service.api_key:
    print("\n✓ API key is properly loaded!")
else:
    print("\n✗ API key is NOT loaded!")
    print("\nSuggested fix:")
    print("Add to your .env file:")
    print(f"PERSONA_API_KEY={getattr(settings, 'DEFAULT_PERSONA_KEY', 'your_key_here')}")
