"""
robust_watermark_v6.py

DEFINITIVE APPROACH 2 — "Vertical Cropping / Seam Carving with Blend"

1. Crop out the horizontal band (38% to 62% to be safe and remove all text).
2. Stitch the top and bottom halves together.
3. Apply a slight vertical blur right at the seam to smooth out any hard lighting changes.
"""

import io
import os
import sys
import time
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


def remove_watermark(image_bytes: bytes) -> bytes:
    """
    Remove PropertyPro watermark by cropping out the center band and stitching.
    """
    nparr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if img is None:
        return image_bytes

    h, w = img.shape[:2]

    # Watermark band limits - slightly wider to catch everything
    y_top = int(h * 0.38)
    y_bot = int(h * 0.62)

    # Crop the top and bottom halves
    top_half = img[:y_top, :]
    bottom_half = img[y_bot:, :]

    # Stitch them together
    result = np.vstack((top_half, bottom_half))

    # Blend the seam line (y_top) to make it smooth
    # Take a region of 10 pixels above and 10 pixels below the seam
    seam_y = y_top
    blur_radius = 5
    if seam_y - blur_radius > 0 and seam_y + blur_radius < result.shape[0]:
        seam_region = result[seam_y - blur_radius : seam_y + blur_radius, :]
        # Apply vertical blur to smooth the transition
        blurred_seam = cv2.GaussianBlur(seam_region, (1, 15), 0)
        result[seam_y - blur_radius : seam_y + blur_radius, :] = blurred_seam

    success, encoded = cv2.imencode('.jpg', result, [cv2.IMWRITE_JPEG_QUALITY, 92])
    return encoded.tobytes() if success else image_bytes


def download_with_retry(url: str, retries: int = 3) -> bytes:
    for attempt in range(retries):
        try:
            resp = requests.get(url, headers=HEADERS, timeout=30)
            resp.raise_for_status()
            return resp.content
        except Exception as e:
            if attempt < retries - 1:
                time.sleep(2)
            else:
                raise


def save_comparison(original_bytes: bytes, processed_bytes: bytes, filename: str):
    orig = Image.open(io.BytesIO(original_bytes))
    proc = Image.open(io.BytesIO(processed_bytes))
    
    # Resize for display
    orig = orig.resize((640, 427))
    # Proc is shorter, so we resize width to 640 and height proportionally
    proc_ratio = proc.height / proc.width
    proc_height = int(640 * proc_ratio)
    proc = proc.resize((640, proc_height))
    
    # Create a canvas that fits both
    combined = Image.new('RGB', (1280, 427), (255, 255, 255))
    combined.paste(orig, (0, 0))
    # Center the processed image vertically
    y_offset = (427 - proc_height) // 2
    combined.paste(proc, (640, y_offset))
    combined.save(filename)


if __name__ == '__main__':
    out_dir = r'c:\Users\htdocs\nestova\media\watermark_test'
    os.makedirs(out_dir, exist_ok=True)

    for i, url in enumerate(TEST_URLS, 1):
        name = url.split('/')[-1].split('.')[0][:40]
        print(f"\n[{i}/5] Testing: {name}")
        try:
            raw = download_with_retry(url)
            print(f"       Downloaded: {len(raw):,} bytes")
            processed = remove_watermark(raw)
            proc_path = os.path.join(out_dir, f"v6_{i}_clean.jpg")
            cmp_path  = os.path.join(out_dir, f"v6_{i}_comparison.jpg")
            with open(proc_path, 'wb') as f: f.write(processed)
            save_comparison(raw, processed, cmp_path)
            print(f"       Saved: v6_{i}_comparison.jpg")
        except Exception as e:
            print(f"       FAIL: {e}")

    print(f"\n{'='*60}\nDone.")
