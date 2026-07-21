"""
robust_watermark_test.py

Tests a proper, robust approach to removing the PropertyPro watermark.

The PropertyPro watermark ALWAYS appears in a fixed position:
- A circular logo icon: left-center of image (~10-35% x, ~38-62% y)
- Text "PropertyPro.ng": center of image (~25-80% x, ~42-58% y)

Strategy:
  1. Build a FIXED mask for the known watermark region (no brightness detection needed)
  2. Apply cv2.inpaint (TELEA) with a large enough radius to fill naturally
  3. No NESTOVA text - just clean removal

This avoids the color-threshold problem entirely.
"""

import io
import sys
import os
import cv2
import numpy as np
import requests
from PIL import Image

sys.path.insert(0, r'c:\Users\htdocs\nestova')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'nestova.settings')

TEST_URLS = [
    "https://images.propertypro.ng/large/luxury-1bedroom-with-rooftop-pool-amp-gym-SfcEB7L1e05zNFvS9Q9N.jpg",
    "https://images.propertypro.ng/large/aston-apartment-simply-magnificent-Aj3Ll8cHGdbF9dzwuMlk.jpeg",
    "https://images.propertypro.ng/large/1-bedroom-apartment-M14NJvgc0DSZrmNYGNpE.jpeg",
    "https://images.propertypro.ng/large/newly-built-1bedroom-apartment-harris-vTQoFXi8gt87JuZVG0kh.jpeg",
    "https://images.propertypro.ng/large/executive-self-contain-98FhbRWkGtD6ehL1eNlD.jpg",
]

HEADERS = {'User-Agent': 'Mozilla/5.0 (compatible; Nestova/1.0)'}


def build_watermark_mask(h: int, w: int) -> np.ndarray:
    """
    Build a fixed binary mask covering the two parts of the PropertyPro watermark:
      1. Circular logo icon (left side, center-ish height)
      2. "PropertyPro.ng" text (center-right, center height)
    
    PropertyPro ALWAYS places the watermark in the same relative position.
    Using fixed percentages is far more reliable than brightness detection.
    """
    mask = np.zeros((h, w), dtype=np.uint8)

    # ── Part 1: Circle/logo icon ──────────────────────────────────────────────
    # Roughly left 5%-40% horizontally, center 35%-65% vertically
    x1, x2 = int(w * 0.04), int(w * 0.38)
    y1, y2 = int(h * 0.35), int(h * 0.65)
    mask[y1:y2, x1:x2] = 255

    # ── Part 2: "PropertyPro.ng" text ─────────────────────────────────────────
    # Roughly 20%-90% horizontally, center 40%-62% vertically
    x1, x2 = int(w * 0.18), int(w * 0.90)
    y1, y2 = int(h * 0.40), int(h * 0.62)
    mask[y1:y2, x1:x2] = 255

    # Dilate a tiny bit to catch anti-aliased edges
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    mask = cv2.dilate(mask, kernel, iterations=2)

    return mask


def remove_watermark(image_bytes: bytes) -> bytes:
    """Remove PropertyPro watermark using fixed-region inpainting."""
    nparr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    if img is None:
        return image_bytes

    h, w = img.shape[:2]
    mask = build_watermark_mask(h, w)

    # Use TELEA inpainting — excellent at filling semi-transparent overlays
    # inpaintRadius=7 gives smoother results on larger watermark regions
    result = cv2.inpaint(img, mask, inpaintRadius=7, flags=cv2.INPAINT_TELEA)

    success, encoded = cv2.imencode('.jpg', result, [cv2.IMWRITE_JPEG_QUALITY, 92])
    if success:
        return encoded.tobytes()
    return image_bytes


def save_comparison(original_bytes: bytes, processed_bytes: bytes, filename: str):
    """Save side-by-side comparison image."""
    orig = Image.open(io.BytesIO(original_bytes)).resize((600, 400))
    proc = Image.open(io.BytesIO(processed_bytes)).resize((600, 400))

    combined = Image.new('RGB', (1200, 400))
    combined.paste(orig, (0, 0))
    combined.paste(proc, (600, 0))
    combined.save(filename)


if __name__ == '__main__':
    out_dir = r'c:\Users\htdocs\nestova\media\watermark_test'
    os.makedirs(out_dir, exist_ok=True)

    for i, url in enumerate(TEST_URLS, 1):
        name = url.split('/')[-1].split('.')[0][:40]
        print(f"\n[{i}/5] Testing: {name}")

        try:
            resp = requests.get(url, headers=HEADERS, timeout=30)
            resp.raise_for_status()
            raw = resp.content
            print(f"       Downloaded: {len(raw):,} bytes")

            processed = remove_watermark(raw)

            # Save original
            orig_path = os.path.join(out_dir, f"test_{i}_original.jpg")
            with open(orig_path, 'wb') as f:
                f.write(raw)

            # Save processed
            proc_path = os.path.join(out_dir, f"test_{i}_clean.jpg")
            with open(proc_path, 'wb') as f:
                f.write(processed)

            # Save comparison
            cmp_path = os.path.join(out_dir, f"test_{i}_comparison.jpg")
            save_comparison(raw, processed, cmp_path)

            print(f"       OK  Saved: test_{i}_clean.jpg  |  test_{i}_comparison.jpg")
        except Exception as e:
            print(f"       FAIL ERROR: {e}")

    print(f"\n{'='*60}")
    print(f"Done. Check: {out_dir}")
