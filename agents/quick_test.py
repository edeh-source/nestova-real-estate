"""
Quick test to verify API key is now loaded correctly
"""

import os
import sys
import django

# Setup Django environment
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'nestova.settings')
django.setup()

from django.conf import settings
from agents.verification_service import VerificationService

print("Checking API key configuration...")
print(f"PERSONA_API_KEY: {settings.PERSONA_API_KEY[:30] if settings.PERSONA_API_KEY else 'NOT SET'}...")

service = VerificationService()
print(f"Service API key: {service.api_key[:30] if service.api_key else 'NOT LOADED'}...")

if service.api_key:
    print("\n✓ SUCCESS: API key is properly loaded!")
else:
    print("\n✗ FAILED: API key is NOT loaded!")
