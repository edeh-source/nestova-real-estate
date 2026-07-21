"""
robust_watermark_v7.py
Test to find the absolute tightest crop limits for the watermark to minimize distortion.
"""

import io
import os
import cv2
import numpy as np
import requests
from PIL import Image

TEST_URLS = [
    "https://images.propertypro.ng/large/luxury-1bedroom-with-rooftop-pool-amp-gym-SfcEB7L1e05zNFvS9Q9N.jpg",
    "https://images.propertypro.ng/large/aston-apartment-simply-magnificent-Aj3Ll8cHGdbF9dzwuMlk.jpeg",
    "https://images.propertypro.ng/large/1-bedroom-apartment-M14NJvgc0DSZrmNYGNpE.jpeg",
    "https://images.propertypro.ng/large/newly-built-1bedroom-apartment-harris-vTQoFXi8gt87JuZVG0kh.jpeg",
    "https://images.propertypro.ng/large/executive-self-contain-98FhbRWkGtD6ehL1eNlD.jpg",
]

HEADERS = {'User-Agent': 'Mozilla/5.0 (compatible; Nestova/1.0)'}

def test_crop_limits():
    out_dir = r'c:\Users\htdocs\nestova\media\watermark_test'
    os.makedirs(out_dir, exist_ok=True)

    for i, url in enumerate(TEST_URLS, 1):
        try:
            raw = requests.get(url, headers=HEADERS, timeout=10).content
            nparr = np.frombuffer(raw, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            h, w = img.shape[:2]

            # Let's draw lines at various percentages to see exactly where the watermark sits
            # Draw red lines for 40-60
            # Draw green lines for 43-57
            # Draw blue lines for 45-55
            
            test_img = img.copy()
            
            cv2.line(test_img, (0, int(h * 0.40)), (w, int(h * 0.40)), (0, 0, 255), 2)
            cv2.line(test_img, (0, int(h * 0.60)), (w, int(h * 0.60)), (0, 0, 255), 2)
            
            cv2.line(test_img, (0, int(h * 0.43)), (w, int(h * 0.43)), (0, 255, 0), 2)
            cv2.line(test_img, (0, int(h * 0.57)), (w, int(h * 0.57)), (0, 255, 0), 2)
            
            cv2.line(test_img, (0, int(h * 0.45)), (w, int(h * 0.45)), (255, 0, 0), 2)
            cv2.line(test_img, (0, int(h * 0.55)), (w, int(h * 0.55)), (255, 0, 0), 2)
            
            cv2.line(test_img, (0, int(h * 0.47)), (w, int(h * 0.47)), (0, 255, 255), 2)
            cv2.line(test_img, (0, int(h * 0.53)), (w, int(h * 0.53)), (0, 255, 255), 2)
            
            cv2.imwrite(os.path.join(out_dir, f"crop_test_{i}.jpg"), test_img)
            print(f"Saved crop_test_{i}.jpg")
        except Exception as e:
            print(f"Error on {i}: {e}")

if __name__ == '__main__':
    test_crop_limits()
