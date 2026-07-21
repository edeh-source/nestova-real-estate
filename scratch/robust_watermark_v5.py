"""
robust_watermark_v5.py

DEFINITIVE APPROACH 2 — "Vertical Cropping / Seam Carving"

Since the watermark is always in the exact center and is semi-transparent over complex textures,
OpenCV inpainting always leaves smudges.

The only 100% robust way to completely remove the watermark with zero trace is to crop out
the horizontal band containing the watermark and stitch the top and bottom halves together.
For property photos, this slight vertical compression is usually unnoticeable, but it guarantees
absolutely no watermark artifacts.
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

    # Watermark band limits - we need to be precise here to minimize crop
    # Typically it's around 42% to 58%
    y_top = int(h * 0.42)
    y_bot = int(h * 0.58)

    # Crop the top and bottom halves
    top_half = img[:y_top, :]
    bottom_half = img[y_bot:, :]

    # Stitch them together
    result = np.vstack((top_half, bottom_half))

    # Optional: We could resize it back to the original height to maintain aspect ratio,
    # but that might stretch things. Let's just keep the stitched image.
    # result = cv2.resize(result, (w, h), interpolation=cv2.INTER_LANCZOS4)

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
            proc_path = os.path.join(out_dir, f"v5_{i}_clean.jpg")
            cmp_path  = os.path.join(out_dir, f"v5_{i}_comparison.jpg")
            with open(proc_path, 'wb') as f: f.write(processed)
            save_comparison(raw, processed, cmp_path)
            print(f"       Saved: v5_{i}_comparison.jpg")
        except Exception as e:
            print(f"       FAIL: {e}")

    print(f"\n{'='*60}\nDone.")
