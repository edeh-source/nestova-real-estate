import os
import cv2
import numpy as np
import requests
import sys
sys.path.insert(0, r'c:\Users\htdocs\nestova')
from bookings.image_processor import process_image_bytes

TEST_URLS = [
    "https://images.propertypro.ng/large/luxury-1bedroom-with-rooftop-pool-amp-gym-SfcEB7L1e05zNFvS9Q9N.jpg",
    "https://images.propertypro.ng/large/aston-apartment-simply-magnificent-Aj3Ll8cHGdbF9dzwuMlk.jpeg",
    "https://images.propertypro.ng/large/1-bedroom-apartment-M14NJvgc0DSZrmNYGNpE.jpeg",
    "https://images.propertypro.ng/large/newly-built-1bedroom-apartment-harris-vTQoFXi8gt87JuZVG0kh.jpeg",
    "https://images.propertypro.ng/large/executive-self-contain-98FhbRWkGtD6ehL1eNlD.jpg",
]

HEADERS = {'User-Agent': 'Mozilla/5.0 (compatible; Nestova/1.0)'}
OUT_DIR  = r'c:\Users\htdocs\nestova\media\watermark_test'

def main():
    for i, url in enumerate(TEST_URLS, 1):
        print(f"Testing {i}...")
        raw = requests.get(url, headers=HEADERS, timeout=15).content
        cleaned = process_image_bytes(raw, stamp_nestova=False)
        orig = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR)
        proc = cv2.imdecode(np.frombuffer(cleaned, np.uint8), cv2.IMREAD_COLOR)
        combined = np.hstack((orig, proc))
        out_path = os.path.join(OUT_DIR, f"prod_test_{i}.jpg")
        cv2.imwrite(out_path, combined)
        print(f"  OK Saved: {out_path}")

if __name__ == '__main__':
    main()
