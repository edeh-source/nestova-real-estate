import sys, os, io, requests
sys.path.insert(0, r'c:\Users\htdocs\nestova')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'nestova.settings')
import django; django.setup()

from bookings.image_processor import process_image_bytes

test_url = "https://images.propertypro.ng/large/executive-fully-furnished-2bed-yaba-gBrxV3lhvnWvZj8yWFn8.jpg"
resp = requests.get(test_url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=20)
print(f"Download status: {resp.status_code}, size: {len(resp.content)} bytes")

processed = process_image_bytes(resp.content, fmt='JPEG')
out = r'c:\Users\htdocs\nestova\media\test_nestova_final.jpg'
with open(out, 'wb') as f:
    f.write(processed)
print(f"Saved: {out}")
