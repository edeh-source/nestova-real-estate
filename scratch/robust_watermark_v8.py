"""
robust_watermark_v8.py
Test a much tighter crop (41% to 59%) to minimize the vertical distortion.
"""

import os
import cv2
import numpy as np
import requests

TEST_URLS = [
    "https://images.propertypro.ng/large/luxury-1bedroom-with-rooftop-pool-amp-gym-SfcEB7L1e05zNFvS9Q9N.jpg",
    "https://images.propertypro.ng/large/aston-apartment-simply-magnificent-Aj3Ll8cHGdbF9dzwuMlk.jpeg",
    "https://images.propertypro.ng/large/1-bedroom-apartment-M14NJvgc0DSZrmNYGNpE.jpeg",
    "https://images.propertypro.ng/large/newly-built-1bedroom-apartment-harris-vTQoFXi8gt87JuZVG0kh.jpeg",
    "https://images.propertypro.ng/large/executive-self-contain-98FhbRWkGtD6ehL1eNlD.jpg",
]

HEADERS = {'User-Agent': 'Mozilla/5.0 (compatible; Nestova/1.0)'}

def test_tighter_crop():
    out_dir = r'c:\Users\htdocs\nestova\media\watermark_test'
    os.makedirs(out_dir, exist_ok=True)

    for i, url in enumerate(TEST_URLS, 1):
        try:
            raw = requests.get(url, headers=HEADERS, timeout=10).content
            nparr = np.frombuffer(raw, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            h, w = img.shape[:2]

            # Tighter crop: 41% to 59% (18% removed instead of 24%)
            y_top = int(h * 0.41)
            y_bot = int(h * 0.59)

            top_half = img[:y_top, :]
            bottom_half = img[y_bot:, :]

            result = np.vstack((top_half, bottom_half))

            # Blend seam
            seam_y = y_top
            blur_radius = 5
            if seam_y - blur_radius > 0 and seam_y + blur_radius < result.shape[0]:
                seam_region = result[seam_y - blur_radius : seam_y + blur_radius, :]
                blurred_seam = cv2.GaussianBlur(seam_region, (1, 15), 0)
                result[seam_y - blur_radius : seam_y + blur_radius, :] = blurred_seam

            cv2.imwrite(os.path.join(out_dir, f"v8_{i}_clean.jpg"), result)

            # Create side-by-side
            # Original needs to be resized to match the compressed height for side-by-side, 
            # OR we pad the result to match original height
            h_res = result.shape[0]
            orig_resized = cv2.resize(img, (w, h_res))
            
            combined = np.hstack((orig_resized, result))
            cv2.imwrite(os.path.join(out_dir, f"v8_{i}_comparison.jpg"), combined)
            print(f"Saved v8_{i}_comparison.jpg")
        except Exception as e:
            print(f"Error on {i}: {e}")

if __name__ == '__main__':
    test_tighter_crop()
