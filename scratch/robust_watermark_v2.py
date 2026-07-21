"""
robust_watermark_v2.py

Smarter approach:
1. The PropertyPro watermark is ALWAYS a semi-transparent white overlay
2. Instead of a big blunt mask, detect the ACTUAL watermark pixels using
   channel saturation analysis (watermark pixels have low saturation / high brightness)
3. Only mask pixels that are genuinely part of the watermark (not walls/ceilings)
4. Apply inpainting with a smaller, tighter radius

Key insight: The watermark pixels are white/light-grey AND they overlay colourful
backgrounds - so in the watermark region, saturation drops abnormally compared to
adjacent rows above and below.
"""

import io
import sys
import os
import cv2
import numpy as np
import requests
from PIL import Image

sys.path.insert(0, r'c:\Users\htdocs\nestova')

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
    Remove the PropertyPro watermark cleanly.

    Method:
    - Convert to HSV. In the watermark band (35-65% height), the watermark pixels
      are high-value (bright) AND low-saturation (washed-out grey/white).
    - A pixel in the watermark region that is BOTH very bright (V > 200) AND
      very de-saturated (S < 60) is almost certainly part of the watermark.
    - For the logo circle on the left (0-25% x), we also catch semi-transparent grey pixels.
    - Inpaint only those pixels — not the whole band.
    """
    nparr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    if img is None:
        return image_bytes

    h, w = img.shape[:2]

    # ── Step 1: Define the watermark search band ──────────────────────────────
    y_top = int(h * 0.33)
    y_bot = int(h * 0.67)

    # ── Step 2: Convert to HSV and analyse the band ───────────────────────────
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    # H: 0-179, S: 0-255, V: 0-255
    S = hsv[:, :, 1]  # saturation channel
    V = hsv[:, :, 2]  # value (brightness) channel

    # ── Step 3: Build the mask ────────────────────────────────────────────────
    mask = np.zeros((h, w), dtype=np.uint8)

    band_S = S[y_top:y_bot, :]
    band_V = V[y_top:y_bot, :]

    # Watermark pixel: very bright AND very desaturated
    # Threshold tuned for PropertyPro's semi-transparent white overlay
    wm_pixels = ((band_V > 185) & (band_S < 55)).astype(np.uint8) * 255
    mask[y_top:y_bot, :] = wm_pixels

    # ── Step 4: Morphological cleanup ────────────────────────────────────────
    # Close small gaps within the watermark text strokes
    kernel_close = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel_close)

    # Remove tiny specks that aren't part of the watermark (e.g. bright highlights on lamps)
    # Keep only connected components larger than 50px
    n_labels, labels, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    clean_mask = np.zeros_like(mask)
    for label in range(1, n_labels):
        area = stats[label, cv2.CC_STAT_AREA]
        if area > 50:
            clean_mask[labels == label] = 255
    mask = clean_mask

    # Dilate just slightly to catch anti-aliased edges
    kernel_dilate = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    mask = cv2.dilate(mask, kernel_dilate, iterations=1)

    # ── Step 5: Inpaint ──────────────────────────────────────────────────────
    # inpaintRadius=5 is tight enough to not bleed into surroundings
    result = cv2.inpaint(img, mask, inpaintRadius=5, flags=cv2.INPAINT_TELEA)

    # ── Step 6: Encode ────────────────────────────────────────────────────────
    success, encoded = cv2.imencode('.jpg', result, [cv2.IMWRITE_JPEG_QUALITY, 92])
    return encoded.tobytes() if success else image_bytes


def save_comparison(original_bytes: bytes, processed_bytes: bytes, filename: str):
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

            orig_path = os.path.join(out_dir, f"v2_{i}_original.jpg")
            proc_path = os.path.join(out_dir, f"v2_{i}_clean.jpg")
            cmp_path  = os.path.join(out_dir, f"v2_{i}_comparison.jpg")

            with open(orig_path, 'wb') as f: f.write(raw)
            with open(proc_path, 'wb') as f: f.write(processed)
            save_comparison(raw, processed, cmp_path)

            print(f"       Saved: {proc_path}")
        except Exception as e:
            print(f"       FAIL: {e}")

    print(f"\n{'='*60}\nDone.")
